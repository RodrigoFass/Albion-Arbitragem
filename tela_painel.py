################################
#                              #
#         TELA PAINEL          #
#                              #
################################

# O que foi feito e quanto rendeu, lido do historico.csv.
#
# O ARRANJO E O DA REFERENCIA: quatro indicadores no topo, a tabela a esquerda e
# uma coluna de destaques a direita. Funciona porque as tres coisas respondem
# perguntas de escalas diferentes - o total, o detalhe, e o que se sobressai - e
# quem abre um painel quer as tres nessa ordem.
#
# NAO INVENTA DADO NENHUM. Soma o que ja estava gravado. Um painel que guardasse
# os proprios numeros teria duas versoes da mesma verdade, e uma delas ficaria
# velha - normalmente a que aparece na tela.
#
# Antes de alterar: python -m pyflakes tela_painel.py

import os
import time
import tkinter as tk

import comum
import historico
import visual
from visual import COR, ESPACO, ESPACO_M, ESPACO_G

# AS LARGURAS SOMAM MENOS QUE A COLUNA DA TABELA. Somando mais, as ultimas
# ficam fora da area visivel - e as ultimas aqui sao o preco e o total, que sao
# justamente o que se veio olhar.
# Os dois filtros da tela de referencia: "All Locations" e "All Time".
TODOS_OS_LUGARES = 'todos os lugares'

PERIODOS = (
    ('tudo', None),
    ('hoje', 24),
    ('7 dias', 24 * 7),
    ('30 dias', 24 * 30),
)

COLUNAS = (
    ('quando', 'quando',  115),
    ('bot',    'o que',    62),
    ('modo',   'modo',     62),
    ('aba',    'onde',    105),
    ('item',   'item',    140),
    ('comb',   't/e',      42),
    ('preco',  'preço',    80, 'e'),
    ('total',  'total',    90, 'e'),
)

MAXIMO_NA_TELA = 400


class Tela:

    def __init__(self, quadro, app):

        self.quadro = quadro
        self.app = app
        self.precisa_atualizar = True
        self.destaques = {}

        self.onde = tk.StringVar(value=TODOS_OS_LUGARES)
        self.periodo = tk.StringVar(value=PERIODOS[0][0])

        self._montar()

    #region Montagem

    def _montar(self):

        visual.titulo_da_pagina(self.quadro, 'Painel',
                                'o que já foi feito, somado do histórico')

        self._montar_indicadores()
        self._montar_filtros()
        self._montar_corpo()

    def _montar_indicadores(self):

        fila = tk.Frame(self.quadro, bg=COR['fundo'])
        fila.pack(fill='x', padx=ESPACO_G, pady=(ESPACO_M, 0))

        # OS QUATRO NUMEROS QUE RESPONDEM "VALEU A PENA?", na ordem em que a
        # pergunta se faz: quanto entrou, quanto sobrou, quanto se moveu, e a
        # que taxa. O "margem media contra a referencia" que ficava aqui era
        # conceito da versao antiga - a referencia era uma coluna da planilha, e
        # essa planilha nao decide mais nada.
        self.receita = visual.Numero(fila, 'recebido', 'todas as vendas', '💰')
        self.ganho = visual.Numero(fila, 'lucro', 'realizado, não previsto',
                                   '📈')
        self.comprados = visual.Numero(fila, 'unidades', 'compradas', '📦')
        self.margem = visual.Numero(fila, 'margem média', 'sobre o gasto', '📊')

        for i, cartao in enumerate((self.receita, self.ganho, self.comprados,
                                    self.margem)):
            cartao.pack(side='left', fill='x', expand=True,
                        padx=(0 if i == 0 else ESPACO // 2,
                              0 if i == 3 else ESPACO // 2))

    def _montar_filtros(self):
        """Onde e quando, como na tela de referencia.

        UM HISTORICO SEM FILTRO SO RESPONDE "quanto no total". As perguntas que
        se faz depois de uma semana operando sao outras - "Thetford ainda paga?",
        "hoje foi melhor que ontem?" - e nenhuma delas cabe num numero unico."""

        caixa = tk.Frame(self.quadro, bg=COR['fundo'])
        caixa.pack(fill='x', padx=ESPACO_G, pady=(ESPACO_M, 0))

        cartao = visual.Cartao(caixa, recheio=ESPACO_M - 4)
        cartao.pack(fill='x')

        linha = tk.Frame(cartao.dentro, bg=COR['painel'])
        linha.pack(fill='x')

        visual.rotulo(linha, 'onde', visual.FONTE_PEQUENA,
                      cor='texto_fraco').pack(side='left', padx=(0, ESPACO))

        self.lista_onde = visual.Lista(linha, self.onde, [TODOS_OS_LUGARES],
                                       ao_mudar=lambda _v: self.ao_mostrar(),
                                       largura=18)
        self.lista_onde.pack(side='left')

        visual.rotulo(linha, 'quando', visual.FONTE_PEQUENA,
                      cor='texto_fraco').pack(side='left',
                                              padx=(ESPACO_M, ESPACO))

        visual.Lista(linha, self.periodo, [p[0] for p in PERIODOS],
                     ao_mudar=lambda _v: self.ao_mostrar(),
                     largura=14).pack(side='left')

        self.contagem = visual.rotulo(linha, '', visual.FONTE_PEQUENA,
                                      cor='texto_fraco')
        self.contagem.pack(side='right')

    def _desde(self):
        """O instante a partir do qual contar, ou None para tudo."""

        horas = dict(PERIODOS).get(self.periodo.get())

        return None if horas is None else time.time() - horas * 3600

    def _montar_corpo(self):

        corpo = tk.Frame(self.quadro, bg=COR['fundo'])
        corpo.pack(fill='both', expand=True, padx=ESPACO_G,
                   pady=(ESPACO_M, ESPACO_M))

        # --- a coluna de destaques, a direita ---------------------------------
        lado = tk.Frame(corpo, bg=COR['fundo'], width=250)
        lado.pack(side='right', fill='y', padx=(ESPACO_M, 0))
        lado.pack_propagate(False)

        visual.secao(lado, 'Destaques').pack(anchor='w', pady=(0, ESPACO))

        # UMA COR POR DESTAQUE, numa barra na borda esquerda.
        #
        # Os tres cartoes tem o mesmo formato e dizem coisas diferentes: um conta
        # itens, outro soma prata, outro compara margens. Sem nada que os separe,
        # o olho le os tres como uma lista e para de distinguir qual e qual - com
        # a barra, cada um vira um lugar fixo que se reconhece de longe.
        for chave, titulo, cor in (('item', 'item mais negociado', 'aviso'),
                                   ('lugar', 'onde mais rendeu', 'info'),
                                   ('melhor', 'melhor margem', 'salvar')):

            fora = tk.Frame(lado, bg=COR[cor])
            fora.pack(fill='x', pady=(0, ESPACO))

            cartao = visual.Cartao(fora, recheio=ESPACO_M - 2)
            cartao.pack(fill='both', expand=True, padx=(3, 0))

            visual.rotulo(cartao.dentro, titulo.upper(), visual.FONTE_ROTULO,
                          cor='texto_fraco').pack(anchor='w')

            valor = visual.rotulo(cartao.dentro, '—', visual.FONTE,
                                  cor='texto_forte')
            valor.pack(anchor='w', pady=(4, 0))

            legenda = visual.rotulo(cartao.dentro, '', visual.FONTE_MINIMA,
                                    cor='texto_fraco')
            legenda.pack(anchor='w')

            self.destaques[chave] = (valor, legenda)

        # --- a tabela, a esquerda ---------------------------------------------
        esquerda = tk.Frame(corpo, bg=COR['fundo'])
        esquerda.pack(side='left', fill='both', expand=True)

        topo = tk.Frame(esquerda, bg=COR['fundo'])
        topo.pack(fill='x', pady=(0, ESPACO))

        visual.secao(topo, 'Histórico').pack(side='left')

        visual.Botao(topo, 'Abrir a pasta', self.abrir, largura=13,
                     fundo_pai='fundo').pack(side='right')

        cartao = visual.Cartao(esquerda, recheio=ESPACO)
        cartao.pack(fill='both', expand=True)

        self.tabela = visual.Tabela(cartao.dentro, COLUNAS)
        self.tabela.pack(fill='both', expand=True)

        self.nota = visual.rotulo(esquerda, '', visual.FONTE_MINIMA,
                                  cor='texto_fraco', fundo='fundo')
        self.nota.pack(anchor='w', pady=(ESPACO, 0))

    #endregion

    def abrir(self):
        try:
            os.startfile(comum.PASTA_REGISTROS)
        except Exception as e:
            visual.avisar(self.quadro, 'Não deu', str(e), tipo='aviso')

    def ao_mostrar(self):

        self.precisa_atualizar = False

        todas = self._ler()

        # OS FILTROS SAO DA TELA, e nao do arquivo: o historico continua inteiro,
        # e o que muda e a pergunta. Assim da para alternar entre "hoje" e "tudo"
        # sem reler o disco.
        self.lista_onde.trocar_valores(
            [TODOS_OS_LUGARES] + sorted({l['aba'] for l in todas if l['aba']}))

        if self.onde.get() not in ([TODOS_OS_LUGARES]
                                   + [l['aba'] for l in todas]):
            self.onde.set(TODOS_OS_LUGARES)

        desde = self._desde()
        onde = self.onde.get()

        linhas = [l for l in todas
                  if (onde == TODOS_OS_LUGARES or l['aba'] == onde)
                  and (desde is None or l['momento'] >= desde)]

        self.contagem.config(
            text=f'{len(linhas)} de {len(todas)} operações'
            if len(linhas) != len(todas) else f'{len(todas)} operações')

        self.tabela.limpar()

        if not linhas:

            for cartao in (self.receita, self.ganho, self.comprados,
                           self.margem):
                cartao.mostrar('—', cor='texto_fraco')

            for valor, legenda in self.destaques.values():
                valor.config(text='—', fg=COR['texto_fraco'])
                legenda.config(text='')

            self.nota.config(
                text='Nenhuma operação registrada ainda. O histórico enche '
                     'sozinho quando um bot roda.')
            return

        # as ultimas primeiro: numa lista longa o que interessa e o fim dela
        for linha in reversed(linhas[-MAXIMO_NA_TELA:]):
            self.tabela.acrescentar(linha['mostrar'])

        # O LUCRO AQUI E REALIZADO, e nao previsto. A tela de compra mostra o
        # que a lista PROMETE; este e o que aconteceu, e a diferenca entre os
        # dois e a unica medida honesta de quanto o bot acerta.
        r = self._somar(linhas)

        self.receita.mostrar(comum.fmt(r['recebido']),
                             f'{r["vendas"]} vendas')

        self.ganho.mostrar(comum.fmt(r['saldo']),
                           cor='ok' if r['saldo'] > 0 else
                           ('perigo' if r['saldo'] < 0 else 'texto_fraco'))

        self.comprados.mostrar(f'{r["unidades_compradas"]}',
                               f'{r["compras"]} compras')

        # SO EXISTE MARGEM DEPOIS DE VENDER. Com a carga ainda parada o saldo e
        # negativo por definicao, e mostrar "-100%" ali seria alarme falso.
        if r['gasto'] and r['recebido']:
            self.margem.mostrar(f'{r["saldo"] / r["gasto"] * 100:.1f}%',
                                cor='ok' if r['saldo'] > 0 else 'perigo')
        else:
            self.margem.mostrar('—', 'ainda sem venda', cor='texto_fraco')

        self._mostrar_destaques(linhas)

        self.nota.config(
            text=f'mostrando as {min(len(linhas), MAXIMO_NA_TELA)} mais '
                 f'recentes de {len(linhas)}')

    def _somar(self, linhas):
        """O resumo DAS LINHAS FILTRADAS, e nao do arquivo inteiro.

        Chamar historico.resumo() aqui somaria tudo e faria os indicadores
        ignorarem o filtro que a pessoa acabou de escolher - o tipo de tela que
        parece funcionar e mente."""

        gasto = sum(l['total'] for l in linhas
                    if l['operacao'] == historico.COMPRA)
        recebido = sum(l['total'] for l in linhas
                       if l['operacao'] == historico.VENDA)

        return {
            'compras': sum(1 for l in linhas
                           if l['operacao'] == historico.COMPRA),
            'vendas': sum(1 for l in linhas
                          if l['operacao'] == historico.VENDA),
            'unidades_compradas': sum(
                l['unidades'] for l in linhas
                if l['operacao'] == historico.COMPRA),
            'gasto': gasto,
            'recebido': recebido,
            'saldo': recebido - gasto,
        }

    def _mostrar_destaques(self, linhas):
        """Os tres que se sobressaem, cada um por um criterio diferente."""

        por_item = {}
        por_lugar = {}

        for l in linhas:
            por_item[l['item']] = por_item.get(l['item'], 0) + 1
            if l['preco']:
                por_lugar[l['aba']] = por_lugar.get(l['aba'], 0) + l['preco']

        if por_item:
            item, quantas = max(por_item.items(), key=lambda kv: kv[1])
            self._destaque('item', item, f'{quantas} operações')

        if por_lugar:
            lugar, total = max(por_lugar.items(), key=lambda kv: kv[1])
            self._destaque('lugar', lugar or '—', comum.fmt(int(total)))

        com_margem = [l for l in linhas if l['margem'] is not None]

        if com_margem:
            melhor = max(com_margem, key=lambda l: l['margem'])
            self._destaque('melhor', melhor['item'],
                           f'{melhor["margem"] * 100:.1f}%  ·  '
                           f'{melhor["combinacao"]}')

    def _destaque(self, chave, texto, legenda):
        valor, rodape = self.destaques[chave]
        valor.config(text=texto, fg=COR['texto_forte'])
        rodape.config(text=legenda)

    def _ler(self):
        """As operacoes, em linhas prontas para a tabela.

        PELO MODULO, E NAO PELO ARQUIVO. Ate aqui esta tela abria o CSV e
        interpretava as colunas por conta propria - uma segunda leitura do mesmo
        arquivo, com os nomes de coluna da versao antiga. Quando o formato mudou,
        ela continuou lendo o que nao existia mais e mostrando a tabela vazia,
        sem nada denunciando."""

        try:
            operacoes = historico.ler()

        except Exception as e:
            self.app.escrever(f'ERRO ao ler o histórico: {e}')
            return []

        linhas = []

        for o in operacoes:

            preco = o['preco'] or None

            linhas.append({
                'item': o['item'],
                'aba': o['mercado'],
                'combinacao': o['combinacao'],
                'preco': preco,
                'total': o['total'],
                'unidades': o['unidades'],
                'operacao': o['operacao'],
                'momento': o['momento'],
                'margem': None,
                'mostrar': (
                    o['quando'], o['operacao'], o['modo'], o['mercado'],
                    o['item'], o['combinacao'],
                    comum.fmt(preco) if preco else '',
                    comum.fmt(o['total']) if o['total'] else ''),
            })

        linhas.reverse()   # o mais recente primeiro

        return linhas

    def _numero(texto):
        try:
            return int(float(str(texto).replace('.', '').replace(',', '.')))
        except (TypeError, ValueError):
            return None
