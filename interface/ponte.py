################################
#                              #
#            PONTE             #
#                              #
################################

# O que a interface em HTML pode pedir ao programa.
#
# Cada metodo publico da Api vira uma funcao em window.pywebview.api, devolve
# dados que viram JSON e NAO desenha nada: a regra de cada tela mora aqui, a
# aparencia mora em web/. Assim da para testar a interface inteira sem janela
# (testes/testar_ponte.py), e trocar a aparencia nao mexe em regra.
#
# NADA QUE TOCA NO JOGO RODA NA THREAD DE QUEM CHAMOU. Uma varredura leva
# dezenas de minutos: _rodar() poe a funcao numa thread e liga a saida do
# comum.relatar(), do progresso, dos avisos e do placar numa fila. Uma thread de
# entrega esvazia a fila em lotes e manda para a janela com evaluate_js - um
# evaluate_js por linha de log afogaria a janela.
#
# Antes de alterar: python -m pyflakes ponte.py

import base64
import io
import json
import os
import queue
import threading
import time
import traceback

from motor import ajustes
from motor import catalogo
from motor import categorias
from motor import comprador
from motor import comum
from motor import conferidor
from motor import coordenadas
from motor import escuta
from motor import historico
from motor import lucro
from motor import mercado
from motor import mercado_negro
from motor import republicar
from motor import vendedor

TITULO = 'Albion Arbitragem'

# Acima disto quase sempre e um digito a mais sem querer - e um zero a mais num
# campo de quantidade vira ordem de compra gigante la na frente.
MAXIMO_POR_COMBINACAO = 999

MAXIMO_NO_HISTORICO = 400

PERIODOS = {'tudo': None, 'hoje': 'hoje', '24h': 24, '7d': 24 * 7,
            '30d': 24 * 30}

# A cor de cada linha do log, pelo comeco dela. A mesma regra do app antigo.
_ERRO = ('ERRO', 'ABORTADO', 'PARANDO', 'RECUSADO')
_AVISO = ('ATENCAO', 'PULADO', '>>>', 'SEM ', 'DESCARTADO')


def etiqueta(texto):
    """'erro', 'aviso', 'forte', 'fraco' ou '' para uma linha do log."""

    limpo = texto.strip()

    if limpo.startswith(_ERRO):
        return 'erro'
    if limpo.startswith(_AVISO):
        return 'aviso'
    if limpo.startswith('['):
        return 'forte'
    if texto.startswith('  '):
        return 'fraco'
    return ''


def _numero(texto, inteiro=False):
    """'23,5' -> 23.5, '1.000.000' -> 1000000. None se nao for numero."""

    texto = str(texto if texto is not None else '').strip().replace(' ', '')

    if not texto:
        return None

    if inteiro:
        texto = texto.replace('.', '').replace(',', '')
        return int(texto) if texto.isdigit() else None

    try:
        return float(texto.replace(',', '.'))
    except ValueError:
        return None


def _registrar_erro(onde, erro):
    """Guarda o erro da interface em registros/, para ninguem ter que adivinhar."""

    try:
        caminho = os.path.join(comum.pasta_registro(), 'interface-erros.txt')
        with open(caminho, 'a', encoding='utf-8') as f:
            f.write(f'--- {time.strftime("%Y-%m-%d %H:%M:%S")} {onde}\n{erro}\n')
    except OSError:
        pass


class Api:

    def __init__(self, sobreposicao=None):

        self._janela = None
        self._abrir_janela = None        # quem sabe criar janelas (o app)
        self._sobreposicao = sobreposicao
        self._fila = queue.Queue()
        self._trava = threading.RLock()
        self._rodando = None
        self._saindo = False

        self._compra = None              # (origem, linhas) do ultimo calculo
        self._venda = None               # (carga, margem, perto)
        self._venda_mochila = None       # o resumo da ultima venda pela mochila
        self._rede_msg = ''              # por que a leitura pela rede nao ligou

        self._erro_ao_abrir = None

        for carregar, nome in ((ajustes.carregar, 'ajustes'),
                               (self._carregar_catalogo, 'catálogo'),
                               (mercado.carregar, 'preços')):
            ok, erro = carregar()
            if not ok:
                self._erro_ao_abrir = f'{nome}: {erro}'

        coordenadas.carregar_perfil()

        threading.Thread(target=self._entregar, daemon=True).start()

    # --- ligacao com as janelas (nada disto e exposto ao JS) --------------

    def _ligar(self, janela, abrir_janela=None):
        self._janela = janela
        self._abrir_janela = abrir_janela

    def _emitir(self, tipo, **dados):
        self._fila.put(dict(dados, tipo=tipo))

    def _entregar(self):
        """Esvazia a fila em lotes. Roda numa thread so dela."""

        while True:

            lote = [self._fila.get()]
            time.sleep(0.08)

            try:
                while True:
                    lote.append(self._fila.get_nowait())
            except queue.Empty:
                pass

            texto = json.dumps(lote, ensure_ascii=False)

            if self._janela is not None:
                try:
                    self._janela.evaluate_js(
                        f'window.app && window.app.eventos({texto})')
                except Exception:
                    pass

            if self._sobreposicao is not None:
                try:
                    self._sobreposicao.eventos(lote)
                except Exception:
                    pass

    # --- o que a interface pede --------------------------------------------

    def estado(self):
        """O resumo que a casca usa: catalogo, precos, carga, operacao."""

        r = catalogo.resumo()
        conf = ajustes.atuais()

        return {
            'titulo': TITULO,
            'versao': comum.VERSAO,
            'tema': conf.get('tema', 'escuro'),
            'erro_ao_abrir': self._erro_ao_abrir,
            'rodando': self._rodando,
            'catalogo': {'nome': catalogo.nome_atual(), **r},
            'precos': mercado.quantidade(),
            'mercados_lidos': len(mercado.mercados_lidos()),
            'carga': sum(e['unidades'] for e in vendedor.carga_pendente()),
        }

    def erro_js(self, texto):
        """Um erro de JavaScript, para registros/interface-erros.txt."""

        _registrar_erro('javascript', texto)
        return True

    # ======================================================================
    # A LEITURA PELA REDE (albiondata-client)
    # ======================================================================

    def _iniciar_rede(self):
        """Liga o receptor e abre o cliente, se a leitura pela rede estiver ligada.

        O app chama ao abrir, numa thread: o cliente precisa estar rodando ANTES
        de voce trocar de zona no jogo, porque e assim que ele descobre em que
        mercado voce esta."""

        conf = ajustes.atuais()
        self._rede_msg = ''

        if not conf.get('rede_ativa'):
            escuta.parar_cliente()
            escuta.parar_servidor()
            return

        porta = conf.get('porta_rede') or escuta.PORTA_PADRAO

        ok, msg = escuta.iniciar_servidor(porta)

        if not ok:
            self._rede_msg = msg
            return

        ok, msg = escuta.iniciar_cliente(conf.get('cliente_dados') or '', porta)
        self._rede_msg = '' if ok else msg

    def _parar_rede(self):
        escuta.parar_cliente()
        escuta.parar_servidor()

    def _encerrar_rede(self):
        """Ao fechar o programa: fecha o receptor e DEIXA O CLIENTE RODANDO.

        O albiondata-client so manda preco depois de ver uma troca de mapa.
        Fechado junto com o bot, cada abertura pedia outra troca de mapa; vivo,
        ele continua sabendo onde voce esta, e o bot o adota ao abrir."""

        escuta.parar_servidor()

    def rede(self):
        """Como esta a leitura pela rede, para a interface mostrar."""

        conf = ajustes.atuais()
        s = escuta.situacao()

        s.update(ligada=bool(conf.get('rede_ativa')),
                 caminho=escuta.achar_cliente(conf.get('cliente_dados') or ''),
                 mensagem=self._rede_msg)

        return s

    def abrir_site_do_cliente(self):
        """A pagina de downloads do albiondata-client, no navegador."""

        try:
            os.startfile('https://github.com/ao-data/albiondata-client/releases')
            return True
        except OSError:
            return False

    def religar_rede(self):
        """Fecha e abre de novo o receptor e o cliente, com os ajustes atuais."""

        self._parar_rede()
        self._iniciar_rede()
        return self.rede()

    def escolher_cliente(self):
        """Abre o seletor de arquivo para achar o albiondata-client.exe."""

        if self._janela is None:
            return None

        try:
            import webview
            tipo = getattr(getattr(webview, 'FileDialog', None), 'OPEN', None)
            if tipo is None:
                tipo = webview.OPEN_DIALOG
            escolhido = self._janela.create_file_dialog(
                tipo, file_types=('Programa (*.exe)',))
        except Exception as e:
            _registrar_erro('escolher_cliente', e)
            return None

        return escolhido[0] if escolhido else None

    def grupos(self):
        return catalogo.grupos()

    # ======================================================================
    # PRECOS (o antigo Conferir)
    # ======================================================================

    def mercados(self):
        """Os sete mercados, com quantos precos e a idade do mais velho."""

        mercado.carregar()
        conf = ajustes.atuais()
        saida = []

        for nome in mercado.MERCADOS:
            quantos = mercado.quantidade(nome)
            idade = mercado.idade_mais_velha(nome) if quantos else None
            saida.append({
                'nome': nome,
                'quantos': quantos,
                'idade': idade,
                'tem_copia': mercado.tem_copia(nome),
                'negro': nome == mercado.MERCADO_NEGRO,
            })

        return {'mercados': saida,
                'escolhido': conf.get('ultimo_mercado') or None,
                'grupos': catalogo.grupos(),
                # o mercado de onde vem o trafego do jogo agora - quando a rede
                # sabe, a tela escolhe sozinha
                'pela_rede': escuta.local_atual(),
                'rede': self.rede()}

    def escolher_mercado(self, nome):
        """Lembra onde voce esta. Sem isto o Comecar nasce sem destino."""

        if nome not in mercado.MERCADOS:
            return False

        ajustes.definir('ultimo_mercado', nome)
        ajustes.salvar()
        return True

    def combinacoes_para_ler(self):
        """As 13 combinacoes e as que estao marcadas para a leitura de precos."""

        marcadas = ajustes.atuais().get('combinacoes_lidas')

        return {'rotulos': list(mercado.ROTULOS),
                'marcadas': (list(mercado.ROTULOS) if marcadas is None
                             else [r for r in mercado.ROTULOS if r in marcadas])}

    def marcar_combinacoes_para_ler(self, rotulos):
        """Guarda quais combinacoes a leitura percorre. Todas marcadas = sem filtro."""

        escolhidas = set(rotulos or [])
        validas = [r for r in mercado.ROTULOS if r in escolhidas]

        ajustes.definir('combinacoes_lidas',
                        None if len(validas) == len(mercado.ROTULOS) else validas)
        ajustes.salvar()

        return self.combinacoes_para_ler()

    def _combinacoes_para_ler(self):
        """combinacoes_de(item) do catalogo, so com as marcadas na tela.

        O catalogo ja tira o que tem quantidade zero; isto tira o que voce
        desmarcou na leitura - o que nao vai comprar hoje, sem mexer nas
        quantidades."""

        marcadas = ajustes.atuais().get('combinacoes_lidas')

        if marcadas is None:
            return catalogo.combinacoes_de

        marcadas = set(marcadas)

        def combinacoes(item, mapa=None):
            return [c for c in catalogo.combinacoes_de(item, mapa)
                    if mercado.rotulo(*c) in marcadas]

        return combinacoes

    def _itens_para_varrer(self, local, grupo, so_faltando):

        itens = catalogo.para_varrer(grupo or None)

        if so_faltando:
            itens = conferidor.falta_conferir(itens, local)

        # ITEM SEM NENHUMA COMBINACAO MARCADA NEM E ABERTO: abrir para nao ler
        # nada seria uma busca e um painel a toa por item
        combinacoes = self._combinacoes_para_ler()
        mapa = catalogo._mapa_de_grupos()

        return [i for i in itens if combinacoes(i, mapa)]

    def plano_varredura(self, local, grupo=None, so_faltando=False):
        """O que vai acontecer, antes de acontecer: itens, combinacoes, tempo."""

        if local not in mercado.MERCADOS:
            return {'erro': 'Escolha onde você está.'}

        itens = self._itens_para_varrer(local, grupo, so_faltando)
        conf = ajustes.atuais()

        # o que "apagar antes" tira: so os precos destes itens, e nao o mercado
        saida = {'local': local, 'itens': len(itens),
                 'tinha': mercado.quantidade(local, set(itens))}

        if not itens:
            aviso = ('Nenhuma combinação marcada para ler — marque alguma em '
                     '"Combinações".' if ajustes.atuais().get('combinacoes_lidas') == []
                     else 'Nada a ler com esses filtros — veja a tela Itens.')
            saida.update(combinacoes=0, minutos=0, aviso=aviso)
            return saida

        mapa = catalogo._mapa_de_grupos()
        combinacoes = self._combinacoes_para_ler()
        saida['combinacoes'] = sum(len(combinacoes(i, mapa)) for i in itens)
        # pela rede a leitura e mais rapida, e o tempo previsto acompanha
        saida['minutos'] = (saida['combinacoes']
                            * catalogo.segundos_por_combinacao(escuta.ativa()) / 60)
        saida['apagar'] = bool(conf['apagar_antes'] and not so_faltando)

        return saida

    def varrer(self, local, grupo=None, so_faltando=False, forcar=False):
        """Comeca a leitura dos precos no mercado onde voce esta."""

        plano = self.plano_varredura(local, grupo, so_faltando)

        if plano.get('erro') or not plano.get('combinacoes'):
            return {'ok': False, 'motivo': plano.get('erro') or plano.get('aviso')}

        conf = ajustes.atuais()
        itens = self._itens_para_varrer(local, grupo, so_faltando)
        no_negro = local == mercado.MERCADO_NEGRO
        combinacoes = self._combinacoes_para_ler()

        # A REDE CALADA NAO TRAVA MAIS A LEITURA. Ela e o normal logo depois de
        # abrir o jogo - ninguem abriu o mercado ainda - e o aviso que perguntava
        # "tentar mesmo assim?" aparecia toda vez, com a rede funcionando. Agora
        # o primeiro item testa a rede (conferidor.ler_item) e o Andamento diz o
        # resultado. Fica so a linha de quando o cliente nem esta de pe.
        aviso_rede = None

        if conf.get('rede_ativa') and not escuta.ligada():
            motivo = self._rede_msg or 'o albiondata-client nao esta rodando'
            aviso_rede = (f'ATENCAO: leitura pela rede ligada, mas {motivo} - a '
                          f'leitura vai pela tela (OCR).')

        def trabalho():
            if aviso_rede:
                comum.relatar(aviso_rede)
            if no_negro:
                mercado_negro.esquecer_calibragem()
            conferidor.varrer(local, itens, combinacoes=combinacoes,
                              apagar_antes=plano['apagar'],
                              repescar_depois=conf['repescar'],
                              amostras=conf['amostras'],
                              tela=mercado_negro.TELA if no_negro else None)

        # O JOGO SABE ONDE VOCE ESTA, e a rede conta. Um preco de Martlock
        # guardado como se fosse de Thetford estraga a conta das duas cidades, e
        # nada na tela denunciaria.
        extras = []
        pela_rede = escuta.local_atual()

        if pela_rede and pela_rede != local:
            extras.append(f'a rede diz que você está em {pela_rede}, e não em {local}')

        return self._rodar(trabalho, f'Lendo preços em {local}', forcar, extras)

    def restaurar_precos(self, local):
        """Devolve os precos que a ultima apagada tirou daquele mercado."""

        quantos = mercado.restaurar_copia(local)

        if quantos:
            mercado.salvar()

        return quantos

    def apagar_velhos(self):
        """Tira do banco o que foi lido ha mais de 24 horas."""

        saiu = mercado.apagar_velhos(24)
        mercado.salvar()
        return saiu

    # ======================================================================
    # COMPRAR
    # ======================================================================

    def calcular_compra(self, cidade='a melhor', margem=None, teto=None,
                        espacos=None):
        """A lista de compras. Campos vazios valem o que esta nos Ajustes."""

        mercado.carregar()
        conf = ajustes.atuais()

        margem = _numero(margem)
        margem = conf['margem'] if margem is None else margem / 100

        teto = _numero(teto, inteiro=True)
        espacos = _numero(espacos, inteiro=True)

        opcoes = dict(margem_minima=margem, taxa=conf['taxa'],
                      idade_maxima=conf['idade_maxima'], ordem_na_compra=True,
                      teto=teto or None, espacos=espacos or None,
                      por_qualidade=bool(conf.get('comprar_por_qualidade')))

        saida = {'cidades': list(mercado.ORIGENS), 'linhas': [], 'origem': None,
                 'resumo': None, 'aviso': None,
                 'qualidade': self._situacao_da_qualidade(conf)}

        do_catalogo = catalogo.para_calcular(so=conf.get('combinacoes_lidas'))

        if not do_catalogo:
            self._compra = None
            saida['aviso'] = {'texto': 'O catálogo está vazio.',
                              'acao': 'itens', 'rotulo': 'Escolher itens'}
            return saida

        if cidade in (None, '', 'a melhor'):
            melhor = lucro.melhor_origem(do_catalogo, **opcoes)

            if melhor is None:
                self._compra = None
                lidas = set(mercado.mercados_lidos()) & set(mercado.ORIGENS)
                saida['aviso'] = (
                    {'texto': 'Nenhuma cidade paga a margem mínima com os preços '
                              'lidos. Escolha uma cidade para ver o que ficou '
                              'de fora.'}
                    if lidas else
                    {'texto': 'Nenhuma cidade tem preço lido ainda.',
                     'acao': 'precos', 'rotulo': 'Ler preços'})
                return saida

            origem, linhas, resumo = melhor
        else:
            origem = cidade
            linhas, resumo = lucro.montar(do_catalogo, cidade, **opcoes)

        self._compra = (origem, linhas, margem, teto or 0)

        saida.update(origem=origem, linhas=linhas, resumo=resumo)

        if not linhas and not mercado.itens(origem):
            # cidade que nunca foi lida: a conta pula o que nao foi pesquisado,
            # e "nada paga a margem" seria uma conclusao sem dado nenhum
            saida['aviso'] = {'texto': f'Nenhum preço lido em {origem} ainda.',
                              'acao': 'precos', 'rotulo': 'Ler preços'}

        elif not linhas:
            saida['aviso'] = {'texto': f'Nada em {origem} paga a margem de '
                                       f'{margem * 100:.0f}%.'}

        return saida

    def _situacao_da_qualidade(self, conf):
        """Se a compra por qualidade esta ligada, e se ela pode comprar agora."""

        if not conf.get('comprar_por_qualidade'):
            return {'ligada': False}

        faltam = []

        if not coordenadas.calibrado('CMP_BARRA_QUAL', 'CMP_QUAL_TOPO'):
            faltam.append('o filtro de qualidade calibrado')

        if not escuta.ativa():
            faltam.append('a leitura pela rede recebendo')

        return {'ligada': True, 'pode_comprar': not faltam, 'faltam': faltam}

    def comprar(self, de_verdade=False, forcar=False):
        """Compra a ultima lista calculada."""

        if not self._compra or not self._compra[1]:
            return {'ok': False, 'motivo': 'Calcule a lista primeiro.'}

        origem, linhas, margem, teto = self._compra
        conf = ajustes.atuais()

        return self._rodar(
            lambda: comprador.comprar(origem, linhas, margem=margem,
                                      taxa=conf['taxa'], teto_de_prata=teto,
                                      de_verdade=de_verdade),
            ('Comprando em ' if de_verdade else 'Simulando compra em ') + origem,
            forcar)

    # ======================================================================
    # VENDER
    # ======================================================================

    def calcular_venda(self, margem=None, perto=None):
        """A carga a vender, com o caminho previsto para cada item."""

        mercado.carregar()
        conf = ajustes.atuais()
        taxa = conf['taxa']
        negro = mercado.MERCADO_NEGRO

        margem = _numero(margem)
        margem = conf['margem'] if margem is None else margem / 100

        perto = _numero(perto)
        perto = (vendedor.PERTO_DO_ALVO if perto is None
                 else max(0.5, min(1.5, perto / 100)))

        carga = vendedor.carga_pendente()
        do_dia = historico.do_dia()

        self._venda = (carga, margem, perto) if carga else None

        linhas = []
        pago_total = previsto_total = 0

        for e in carga:

            item, rot, pago, quantas = e['item'], e['combinacao'], e['pago'], e['unidades']
            qualidade = e['qualidade']

            # OS PRECOS DO ULTIMO CONFERIR, DA COMBINACAO COMPRADA: uma previsao.
            # No jogo a decisao e refeita com o livro do momento. Sem a
            # combinacao nao ha previsao - o maior pedido do item em qualquer
            # grau seria o de um T8 prevendo um T5.
            menor, pedido = (mercado.ler(negro, item, rot)[0],
                             mercado.ler_outro(negro, item, rot)) if rot else (None, None)

            # a unidade comprada por qualidade conta com os pedidos que ela atende
            if qualidade and rot:
                pedido = _maior([pedido] + [
                    v.get('pedido')
                    for q, v in mercado.ler_qualidades(negro, item, rot)[0].items()
                    if q <= qualidade])

            modo, preco, motivo = vendedor.decidir(pago, pedido, menor, margem,
                                                   taxa, perto)

            if not rot:
                motivo = 'sem a combinacao comprada, nao da para prever'

            # LIQUIDO, como a tela promete: a taxa de venda, e a de ordem quando
            # o caminho e a fila
            previsto = (int(lucro.receita_real(preco, taxa, modo == 'ordem') * quantas)
                        if modo else 0)
            pago_total += pago * quantas
            previsto_total += previsto

            linhas.append({'item': item, 'combinacao': rot, 'pago': pago,
                           'quantidade': quantas, 'qualidade': qualidade,
                           'alvo': vendedor.alvo(pago, margem, taxa),
                           'modo': modo, 'previsto': previsto, 'motivo': motivo})

        return {
            'linhas': linhas,
            'pago': pago_total,
            'previsto': previsto_total,
            'unidades': sum(e['unidades'] for e in carga),
            'horas': vendedor.HORAS_DA_CARGA,
            'do_dia': do_dia,
        }

    def vender_pelo_mercado(self, de_verdade=False, forcar=False):
        """Cria a ordem de cada pilha da lista "Sell from Inventory".

        SEM DEPENDER DA COMPRA: o preco e o menor da qualidade Normal no Mercado
        Negro, menos uma prata - ver republicar.py."""

        def vender():
            r = republicar.vender(de_verdade=de_verdade)
            if 'ordens' in r:
                self._venda_mochila = dict(r, quando=time.strftime('%d/%m %H:%M'))

        return self._rodar(
            vender,
            ('Vendendo pelo mercado' if de_verdade
             else 'Simulando a venda pelo mercado'),
            forcar)

    def ultima_venda_mochila(self):
        """O resumo da ultima venda pela mochila - o total a venda -, ou None."""

        return self._venda_mochila

    def vender(self, de_verdade=False, forcar=False):
        """Vende a carga do ultimo calculo no Mercado Negro."""

        if not self._venda:
            return {'ok': False, 'motivo': 'Não há carga para vender.'}

        carga, margem, perto = self._venda
        conf = ajustes.atuais()

        return self._rodar(
            lambda: vendedor.vender(carga, margem=margem, taxa=conf['taxa'],
                                    de_verdade=de_verdade, perto=perto),
            'Vendendo no Mercado Negro' if de_verdade
            else 'Simulando venda no Mercado Negro',
            forcar)

    # ======================================================================
    # ITENS
    # ======================================================================

    def itens_do_jogo(self):
        """Tudo que o bot sabe selecionar no menu, por categoria e familia."""

        arvore = []

        for nome, familias in categorias.TRES_NIVEIS.items():
            arvore.append({'nome': nome,
                           'familias': [{'nome': f, 'itens': list(i)}
                                        for f, i in familias]})

        for nome, itens in categorias.DOIS_NIVEIS.items():
            arvore.append({'nome': nome,
                           'familias': [{'nome': None, 'itens': list(itens)}]})

        return arvore

    def catalogo_atual(self):
        """Os grupos e itens escolhidos, para a tela Itens."""

        grupos = []

        for g in catalogo.grupos():
            grupos.append({
                'nome': g,
                'proprio': catalogo.grupo_tem_excecao(g),
                'itens': [{'nome': i, 'proprio': catalogo.tem_excecao(i)}
                          for i in catalogo.itens_de(g)],
            })

        return {
            'nome': catalogo.nome_atual(),
            'salvos': sorted(set(catalogo.salvos()) | {catalogo.nome_atual()}),
            'grupos': grupos,
            'resumo': self._resumo_do_catalogo(),
            'desfazer': catalogo.da_para_desfazer(),
            'rotulos': list(catalogo.TABELA_PADRAO),
        }

    def _resumo_do_catalogo(self):

        r = catalogo.resumo()
        r['minutos'] = r['combinacoes'] * catalogo.segundos_por_combinacao(escuta.ativa()) / 60
        return r

    def _mudou(self):
        """Grava o catalogo a cada mudanca e devolve o estado novo.

        SEM BOTAO SALVAR. Escolher cem itens leva tempo, e um "esqueci de
        salvar" jogava tudo fora. O desfazer cobre o arrependimento."""

        catalogo.salvar()
        return self.catalogo_atual()

    def acrescentar(self, itens, grupo):

        with self._trava:
            grupo = (grupo or '').strip() or catalogo.GRUPO_PADRAO
            avisos = []

            for item in itens or []:
                ok, motivo = catalogo.acrescentar(item, grupo)
                if not ok and 'ja esta' not in motivo:
                    avisos.append(motivo)

            return dict(self._mudou(), avisos=avisos)

    def remover(self, itens):

        with self._trava:
            catalogo.remover_varios(itens or [])
            return self._mudou()

    def desfazer(self):

        with self._trava:
            catalogo.desfazer()
            return self._mudou()

    def mover(self, itens, grupo):

        with self._trava:
            grupo = (grupo or '').strip()
            if grupo:
                catalogo.criar_grupo(grupo)
                for item in itens or []:
                    catalogo.mover(item, grupo)
            return self._mudou()

    def criar_grupo(self, nome):

        with self._trava:
            if not catalogo.criar_grupo(nome):
                return {'erro': 'Esse grupo já existe, ou o nome está vazio.'}
            return self._mudou()

    def renomear_grupo(self, antigo, novo):

        with self._trava:
            if not catalogo.renomear_grupo(antigo, novo):
                return {'erro': 'Já existe um grupo com esse nome, ou ele está vazio.'}
            return self._mudou()

    def apagar_grupo(self, nome, mover_para=None):
        """Apaga o grupo. Os itens vao para <mover_para>, ou saem do catalogo."""

        with self._trava:
            catalogo.apagar_grupo(nome, mover_para or None)
            return self._mudou()

    def quantidades(self, nivel='tabela', alvo=None):
        """As 13 quantidades daquele nivel, com o que e proprio e o que e herdado."""

        rotulos = list(catalogo.TABELA_PADRAO)
        tabela = catalogo.tabela()
        saida = []

        if nivel == 'item' and alvo:
            proprias = catalogo.excecoes_de(alvo)
            grupo = catalogo.grupo_de(alvo)
            for r in rotulos:
                herdado = catalogo.quantidade_do_grupo(grupo, r) if grupo else tabela.get(r, 0)
                saida.append({'rotulo': r, 'valor': catalogo.quantidade(alvo, r),
                              'proprio': r in proprias, 'herdado': herdado})

        elif nivel == 'grupo' and alvo:
            proprias = catalogo.excecoes_do_grupo(alvo)
            for r in rotulos:
                saida.append({'rotulo': r,
                              'valor': catalogo.quantidade_do_grupo(alvo, r),
                              'proprio': r in proprias,
                              'herdado': tabela.get(r, 0)})

        else:
            nivel, alvo = 'tabela', None
            for r in rotulos:
                saida.append({'rotulo': r, 'valor': tabela.get(r, 0),
                              'proprio': True, 'herdado': None})

        return {'nivel': nivel, 'alvo': alvo, 'quantidades': saida}

    def definir_quantidade(self, nivel, alvo, rotulo, valor):
        """Uma quantidade. <valor> None tira o ajuste proprio (volta a herdar)."""

        with self._trava:

            if valor is not None:
                valor = _numero(valor, inteiro=True)
                if valor is None:
                    return {'erro': 'Use um número inteiro.'}
                if valor > MAXIMO_POR_COMBINACAO:
                    return {'erro': f'O máximo é {MAXIMO_POR_COMBINACAO} por '
                                    f'combinação — acima disso quase sempre é um '
                                    f'dígito a mais.'}

            if nivel == 'item':
                catalogo.definir(alvo, rotulo, valor)
            elif nivel == 'grupo':
                catalogo.definir_no_grupo(alvo, rotulo, valor)
            elif valor is not None:
                catalogo.definir_tabela(rotulo, valor)

            self._mudou()
            return self.quantidades(nivel, alvo)

    def definir_todas(self, nivel, alvo, valor):
        """A mesma quantidade nas 13 combinacoes daquele nivel."""

        resposta = None

        for rotulo in catalogo.TABELA_PADRAO:
            resposta = self.definir_quantidade(nivel, alvo, rotulo, valor)
            if resposta.get('erro'):
                return resposta

        return resposta

    def em_lote(self, texto, quanto, itens=None):
        """'8.3, 7.2' = 0 nos itens escolhidos, ou na tabela se nenhum."""

        with self._trava:

            rotulos = catalogo.rotulos_validos(texto)

            if not rotulos:
                return {'erro': 'Nenhuma combinação reconhecida. Use algo como '
                                '"T8.3" ou "T7.2, T8.1".'}

            quanto = _numero(quanto, inteiro=True)

            if quanto is None or quanto > MAXIMO_POR_COMBINACAO:
                return {'erro': f'Quantidade entre 0 e {MAXIMO_POR_COMBINACAO}.'}

            catalogo.em_lote(rotulos, quanto, itens or None)

            return dict(self._mudou(), feito=f'{", ".join(rotulos)} = {quanto} em '
                        + (f'{len(itens)} itens' if itens else 'todos os itens'))

    @staticmethod
    def _carregar_catalogo():
        """O catalogo da ultima vez. Se ele sumiu do disco, o padrao."""

        nome = ajustes.atuais().get('catalogo') or 'padrao'

        if nome != 'padrao' and nome not in catalogo.salvos():
            nome = 'padrao'

        return catalogo.carregar(nome)

    @staticmethod
    def _lembrar_catalogo():
        """Guarda nos ajustes o catalogo em uso, para reabrir nele."""

        ajustes.definir('catalogo', catalogo.nome_atual())
        ajustes.salvar()

    def abrir_catalogo(self, nome):

        with self._trava:
            ok, erro = catalogo.carregar(nome)
            if ok:
                self._lembrar_catalogo()
            return self.catalogo_atual() if ok else {'erro': erro}

    def salvar_catalogo_como(self, nome):

        with self._trava:
            nome = (nome or '').strip()
            if not nome:
                return {'erro': 'Dê um nome ao catálogo.'}
            ok, erro = catalogo.salvar(nome)
            if ok:
                self._lembrar_catalogo()
            return self.catalogo_atual() if ok else {'erro': erro}

    # ======================================================================
    # HISTORICO
    # ======================================================================

    def historico(self, onde='', periodo='tudo'):
        """As operacoes filtradas, o resumo delas e os destaques."""

        try:
            todas = historico.ler()
        except Exception as e:
            return {'erro': f'Não deu para ler o histórico: {e}'}

        lugares = sorted({o['mercado'] for o in todas if o['mercado']})

        horas = PERIODOS.get(periodo)

        if horas == 'hoje':
            desde = vendedor._meia_noite()
        elif horas:
            desde = time.time() - horas * 3600
        else:
            desde = None

        linhas = [o for o in todas
                  if (not onde or o['mercado'] == onde)
                  and (desde is None or o['momento'] >= desde)]

        compras = [o for o in linhas if o['operacao'] == historico.COMPRA]
        vendas = [o for o in linhas if o['operacao'] == historico.VENDA]

        # A MESMA SOMA DO RESUMO DO DIA: so o que entrou de verdade, liquido de
        # taxa; ordem de venda criada fica a parte
        s = historico.somar(linhas)

        resumo = {
            'compras': s['compras'], 'vendas': s['vendas'],
            'unidades': s['unidades_compradas'],
            'gasto': s['gasto'], 'recebido': s['recebido'],
            'em_ordens': s['em_ordens'], 'saldo': s['saldo'],
            # SO EXISTE MARGEM DEPOIS DE VENDER: com a carga parada o saldo e
            # negativo por definicao, e "-100%" seria alarme falso
            'margem': (s['saldo'] / s['gasto']
                       if s['gasto'] and s['recebido'] else None),
        }

        destaques = {}

        if linhas:
            por_item = {}
            for o in linhas:
                por_item[o['item']] = por_item.get(o['item'], 0) + o['unidades']
            item, unidades = max(por_item.items(), key=lambda kv: kv[1])
            destaques['item'] = {'valor': item, 'legenda': f'{unidades} unidades'}

        if compras:
            por_cidade = {}
            for o in compras:
                por_cidade[o['mercado']] = por_cidade.get(o['mercado'], 0) + o['total']
            cidade, total = max(por_cidade.items(), key=lambda kv: kv[1])
            destaques['cidade'] = {'valor': cidade, 'legenda': total}

        if vendas:
            maior = max(vendas, key=lambda o: o['total'])
            destaques['venda'] = {'valor': maior['item'], 'legenda': maior['total']}

        # A MAIS RECENTE PRIMEIRO. O painel antigo invertia duas vezes e mostrava
        # as 400 mais ANTIGAS.
        recentes = list(reversed(linhas))[:MAXIMO_NO_HISTORICO]

        return {
            'lugares': lugares,
            'total': len(todas),
            'filtradas': len(linhas),
            'linhas': [{k: o.get(k) for k in ('quando', 'operacao', 'modo',
                                              'mercado', 'item', 'combinacao',
                                              'unidades', 'preco', 'total')}
                       for o in recentes],
            'resumo': resumo,
            'destaques': destaques,
        }

    def abrir_pasta(self):
        """Abre a pasta de registros no Explorer."""

        try:
            os.startfile(comum.pasta_registro())
            return True
        except OSError:
            return False

    # ======================================================================
    # AJUSTES
    # ======================================================================

    def ajustes_atuais(self):

        conf = ajustes.atuais()

        return {
            'valores': {k: conf.get(k) for k in ajustes.PADRAO},
            'taxa': conf['taxa'],
            'teclas': list(comum.TECLAS_POSSIVEIS),
            'taxas': {'sem_premium': lucro.TAXA_SEM_PREMIUM,
                      'com_premium': lucro.TAXA_COM_PREMIUM,
                      'ordem': lucro.TAXA_DE_ORDEM},
        }

    def salvar_ajustes(self, dados):
        """Confere tudo antes de gravar. Devolve {ok, erros: {campo: motivo}}.

        UM CAMPO RUIM NAO GRAVA NADA. Gravar metade deixaria a tela mostrando
        uma coisa e o arquivo guardando outra."""

        dados = dados or {}
        novos = {}
        erros = {}

        def faixa(chave, minimo, maximo, inteiro=False, divisor=1, vazio=False):

            texto = dados.get(chave)
            valor = _numero(texto, inteiro=inteiro)

            if valor is None:
                if vazio and str(texto or '').strip() == '':
                    novos[chave] = None
                    return
                erros[chave] = 'Use um número.'
                return

            if not minimo <= valor <= maximo:
                erros[chave] = f'Entre {minimo} e {maximo}.'
                return

            novos[chave] = valor / divisor if divisor != 1 else valor

        faixa('margem', 0, 100, divisor=100)
        faixa('idade_maxima', 0.5, 72)
        faixa('teto', 1, 10 ** 11, inteiro=True, vazio=True)
        faixa('espacos', 1, 999, inteiro=True, vazio=True)
        faixa('amostras', 0, 100, inteiro=True)
        faixa('ordem_a_partir_de', 1, 999, inteiro=True)
        faixa('na_hora_acima_de', 0, 100_000_000, inteiro=True)
        faixa('ms_clique', 10, 2000, inteiro=True)
        faixa('ms_escrita', 10, 2000, inteiro=True)
        faixa('ms_leitura', 50, 3000, inteiro=True)

        faixa('porta_rede', 1024, 65535, inteiro=True)

        for chave in ('premium', 'minimizar', 'focar_jogo', 'avisar_no_fim',
                      'faixa', 'avisos', 'apagar_antes', 'repescar', 'rede_ativa',
                      'comprar_por_qualidade'):
            novos[chave] = bool(dados.get(chave))

        caminho = str(dados.get('cliente_dados') or '').strip().strip('"')

        if caminho and not os.path.isfile(caminho):
            erros['cliente_dados'] = 'Arquivo não encontrado.'
        else:
            novos['cliente_dados'] = caminho

        for chave, validos in (('modo_de_compra', ('smart', 'ordem', 'na_hora')),
                               ('tema', ('escuro', 'claro', 'sistema'))):
            if dados.get(chave) in validos:
                novos[chave] = dados[chave]
            else:
                erros[chave] = 'Opção desconhecida.'

        teclas = {}

        for chave in ('tecla_pausa', 'tecla_parada', 'tecla_pular'):
            tecla = str(dados.get(chave) or '').strip().lower()
            if tecla not in comum.TECLAS_POSSIVEIS:
                erros[chave] = 'Tecla não suportada.'
            elif tecla in teclas.values():
                erros[chave] = 'Já usada em outra função.'
            teclas[chave] = tecla

        if erros:
            return {'ok': False, 'erros': erros}

        novos.update(teclas)

        da_rede = ('rede_ativa', 'cliente_dados', 'porta_rede')
        antes = {k: ajustes.atuais().get(k) for k in da_rede}

        for chave, valor in novos.items():
            ajustes.definir(chave, valor)

        ok, erro = ajustes.salvar()

        # mudou a rede: religa ja, sem precisar reabrir o programa
        if ok and any(antes[k] != ajustes.atuais().get(k) for k in da_rede):
            threading.Thread(target=self.religar_rede, daemon=True).start()

        return {'ok': ok, 'erros': {} if ok else {'_': erro}}

    def restaurar_ajustes(self):

        ajustes.restaurar()
        ajustes.salvar()
        return self.ajustes_atuais()

    # ======================================================================
    # CALIBRADOR
    # ======================================================================

    def calibrador_passos(self):
        """Os grupos de marcas, sem as contas dos derivados (essas ficam aqui)."""

        return [{'titulo': g['titulo'], 'preparo': g.get('preparo', ''),
                 'marcas': g['marcas']} for g in coordenadas.PASSOS]

    def abrir_calibrador(self):

        if self._rodando:
            return {'ok': False, 'motivo': 'Termine ou pare a operação antes.'}

        if self._abrir_janela:
            self._abrir_janela('calibrador')

        return {'ok': True}

    def capturar_tela(self):
        """Sai da frente, fotografa o jogo, e volta. Devolve a imagem em PNG.

        A IMAGEM CAPTURADA E EXATAMENTE O QUE O BOT VAI VER. Marcar sobre ela e
        marcar sobre a verdade - e da para ampliar, o que o jogo ao vivo nao da."""

        janelas = [j for j in self._janelas_visiveis()]

        for j in janelas:
            try:
                j.minimize()
            except Exception:
                pass

        comum.focar_jogo()
        time.sleep(0.6)

        try:
            import mss
            from PIL import Image

            with mss.mss() as tela:
                monitor = tela.monitors[1]
                bruta = tela.grab(monitor)
                imagem = Image.frombytes('RGB', bruta.size, bruta.bgra, 'raw', 'BGRX')

            dados = io.BytesIO()
            imagem.save(dados, 'PNG')
            erro = None

        except Exception as e:
            erro = str(e)

        for j in reversed(janelas):
            try:
                j.restore()
            except Exception:
                pass

        if erro:
            return {'erro': f'Não deu para capturar a tela: {erro}'}

        return {'imagem': 'data:image/png;base64,'
                          + base64.b64encode(dados.getvalue()).decode('ascii'),
                'largura': imagem.width, 'altura': imagem.height}

    def _janelas_visiveis(self):

        try:
            import webview
            return list(webview.windows)
        except Exception:
            return [self._janela] if self._janela else []

    def salvar_coordenadas(self, valores):
        """Calcula os derivados e grava o coordenadas.json."""

        valores = dict(valores or {})

        for grupo in coordenadas.PASSOS:
            for nome, conta in grupo.get('derivados', []):
                try:
                    valores[nome] = int(conta(valores))
                except Exception:
                    pass

        for nome, valor in list(valores.items()):
            if isinstance(valor, list):
                valores[nome] = tuple(valor)

        try:
            trocadas = coordenadas.salvar_perfil(valores)
        except Exception as e:
            return {'ok': False, 'motivo': f'Não deu para gravar: {e}'}

        coordenadas.carregar_perfil()
        comum.relatar(f'{len(trocadas)} coordenadas foram remarcadas.')

        return {'ok': True, 'trocadas': len(trocadas)}

    # ======================================================================
    # A OPERACAO
    # ======================================================================

    def parar(self):
        """O mesmo que o F12: para onde estiver, respeitando a secao critica."""

        comum.aborto_pedido.set()
        comum.pausado.clear()
        self._emitir('progresso', rotulo='parando...', feito=0, total=0)
        return True

    def sair(self):
        """Fecha o programa, parando a operacao que estiver rodando."""

        self._saindo = True
        comum.aborto_pedido.set()
        comum.pausado.clear()

        if self._sobreposicao is not None:
            try:
                self._sobreposicao.fechar()
            except Exception:
                pass

        if self._janela is not None:
            self._janela.destroy()

        return True

    def _rodar(self, funcao, rotulo, forcar=False, extras=()):
        """Poe <funcao> numa thread, com a saida indo para a interface.

        A ORDEM IMPORTA. As sobreposicoes nascem ANTES de o jogo vir para a
        frente, porque criar janela pode roubar o foco; e o jogo vem para a
        frente so depois do clique em Comecar, porque nesse instante a frente
        e, por definicao, desta janela."""

        with self._trava:

            if self._rodando:
                return {'ok': False, 'motivo': 'Já há uma operação em andamento.'}

            problemas = list(extras) + comum.verificar_ambiente(exigir_foco=False)

            if problemas and not forcar:
                return {'ok': False, 'problemas': problemas}

            conf = ajustes.atuais()

            comum.limpar_sinais()
            comum.zerar_contadores()
            comum.instalar_teclas()

            registro = _abrir_registro_da_operacao(rotulo)

            def destino(t):
                self._emitir('linha', texto=t, etiqueta=etiqueta(t))
                _anotar(registro, t)

            self._registro = registro
            comum.definir_destino(destino)
            comum.definir_progresso(lambda f, t, r: self._emitir(
                'progresso', feito=f, total=t, rotulo=r))
            comum.definir_aviso(lambda t, v, tom: self._emitir(
                'aviso', titulo=t, valor=v, tom=tom))
            comum.definir_placar(lambda v: self._emitir('placar', **v))

            self._rodando = rotulo

            if self._sobreposicao is not None:
                try:
                    self._sobreposicao.abrir(faixa=conf['faixa'],
                                             avisos=conf['avisos'])
                except Exception as e:
                    _registrar_erro('sobreposicao', e)

            if conf['focar_jogo'] and not comum.focar_jogo():
                self._limpar()
                return {'ok': False,
                        'motivo': 'Não consegui trazer a janela do Albion para '
                                  'frente. Abra o jogo em tela cheia e tente de novo.'}

            if conf['minimizar'] and self._janela is not None:
                try:
                    self._janela.minimize()
                except Exception:
                    pass

            self._emitir('inicio', rotulo=rotulo)

            def alvo():
                try:
                    funcao()
                except comum.Abortado:
                    comum.relatar('')
                    comum.relatar('>>> parado <<<')
                except Exception as e:
                    comum.relatar(f'ERRO: {e}')
                    _registrar_erro(rotulo, traceback.format_exc())
                finally:
                    self._terminou(rotulo)

            threading.Thread(target=alvo, daemon=True).start()

            return {'ok': True}

    def _limpar(self):

        comum.definir_destino(None)

        registro, self._registro = getattr(self, '_registro', None), None

        if registro is not None:
            try:
                registro.close()
            except Exception:
                pass
        comum.definir_progresso(None)
        comum.definir_aviso(None)
        comum.definir_placar(None)
        comum.parar_teclas()

        if self._sobreposicao is not None:
            try:
                self._sobreposicao.fechar()
            except Exception:
                pass

        self._rodando = None

    def _terminou(self, rotulo):

        self._limpar()

        if self._janela is not None:
            try:
                self._janela.restore()
            except Exception:
                pass

        if ajustes.atuais()['avisar_no_fim']:
            _avisar_que_terminou()

        self._emitir('fim', rotulo=rotulo)


def _abrir_registro_da_operacao(rotulo):
    """O andamento de toda operacao, em registros/operacoes, um arquivo por dia.

    A varredura ja guardava o dela; compra, venda e soma das ordens so existiam
    na tela - e uma compra que "so abre o painel e fecha" nao deixava rastro de
    por que. Devolve o arquivo aberto, ou None: o registro nunca derruba nada."""

    try:
        destino = comum.pasta_registro('operacoes')
        caminho = os.path.join(destino, f'{time.strftime("%Y-%m-%d")}.txt')
        arquivo = open(caminho, 'a', encoding='utf-8', buffering=1)
        arquivo.write(f'\n===== {time.strftime("%H:%M:%S")} - {rotulo} - '
                      f'{comum.VERSAO} =====\n')
        return arquivo

    except Exception:
        return None


def _anotar(arquivo, texto):

    if arquivo is None:
        return

    try:
        arquivo.write(f'{texto}'.rstrip() + '\n')
    except Exception:
        pass


def _maior(valores):
    validos = [v for v in valores if v]
    return max(validos) if validos else None


def _avisar_que_terminou():
    """Um apito e o botao piscando na barra de tarefas.

    NAO TRAZ A JANELA PARA FRENTE: se voce estiver no meio de outra coisa, uma
    janela pulando na sua frente e pior que um aviso discreto."""

    try:
        import winsound
        winsound.MessageBeep(winsound.MB_ICONASTERISK)
    except Exception:
        pass

    try:
        import ctypes
        import win32gui

        hwnd = win32gui.FindWindow(None, TITULO)

        if not hwnd:
            return

        class FLASHWINFO(ctypes.Structure):
            _fields_ = [('cbSize', ctypes.c_uint), ('hwnd', ctypes.c_void_p),
                        ('dwFlags', ctypes.c_uint), ('uCount', ctypes.c_uint),
                        ('dwTimeout', ctypes.c_uint)]

        info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 0x03 | 0x0C, 0, 0)
        ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))

    except Exception:
        pass
