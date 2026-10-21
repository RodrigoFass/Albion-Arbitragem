################################
#                              #
#           TESTES             #
#            PONTE             #
#                              #
################################

# O que a interface em HTML pede ao programa, testado sem janela e sem o jogo.
#
# A interface nao tem regra nenhuma: cada botao chama um metodo da Api da
# ponte.py. Testar a Api e testar o que cada tela faz - o que ela mostra, o que
# ela recusa, e o que ela grava.
#
#     python testes/testar_ponte.py

import atexit
import json
import os
import shutil
import sys
import tempfile
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# os testes gravam numa pasta temporaria, nunca nos seus arquivos
_DADOS = tempfile.mkdtemp(prefix='albion-ponte-')
os.environ['ALBION_DADOS'] = _DADOS
atexit.register(shutil.rmtree, _DADOS, True)

from motor import ajustes     # noqa: E402
from motor import catalogo    # noqa: E402
from motor import comum       # noqa: E402
from motor import historico   # noqa: E402
from motor import lucro       # noqa: E402
from motor import mercado     # noqa: E402
from interface import ponte       # noqa: E402

ok = 0
falhas = []
grupo_atual = ''


def grupo(nome):
    global grupo_atual
    grupo_atual = nome
    print(f'\n--- {nome}')


def checar(nome, condicao, detalhe=''):
    global ok

    if condicao:
        ok += 1
        print(f'  ok    {nome}')
    else:
        falhas.append(f'{grupo_atual}: {nome}' + (f'  ({detalhe})' if detalhe else ''))
        print(f'  FALHA {nome}' + (f'  ({detalhe})' if detalhe else ''))


def vira_json(valor):
    """Tudo que a Api devolve tem de atravessar para o JavaScript."""
    try:
        json.dumps(valor)
        return True
    except (TypeError, ValueError):
        return False


class JanelaFalsa:
    """Guarda o que a ponte mandaria para a janela."""

    def __init__(self):
        self.chamadas = []
        self.minimizada = False

    def evaluate_js(self, codigo):
        self.chamadas.append(codigo)

    def minimize(self):
        self.minimizada = True

    def restore(self):
        self.minimizada = False

    def eventos(self):
        saida = []
        for c in self.chamadas:
            if 'app.eventos(' in c:
                saida += json.loads(c[c.index('app.eventos(') + 12:-1])
        return saida


janela = JanelaFalsa()
api = ponte.Api(None)
api._ligar(janela)


# ============================================================
grupo('o estado que a casca mostra')

e = api.estado()

checar('o primeiro uso abre o catalogo inicial', e['catalogo']['itens'] == 121,
       str(e['catalogo']))

checar('sem operacao rodando', e['rodando'] is None)

checar('e o estado vira JSON', vira_json(e))

checar('a pasta de dados e a temporaria', comum.PASTA_DADOS == _DADOS)


# ============================================================
grupo('a tela Itens')

cat = api.catalogo_atual()

checar('tres grupos e treze rotulos', len(cat['grupos']) == 3 and len(cat['rotulos']) == 13)

r = api.criar_grupo('Viagem 4')
checar('cria um grupo', any(g['nome'] == 'Viagem 4' for g in r['grupos']))

checar('e recusa o mesmo nome de novo', 'erro' in api.criar_grupo('Viagem 4'))

r = api.acrescentar(['Bloodletter', 'Item Que Nao Existe'], 'Viagem 4')
checar('acrescenta o que existe', any(i['nome'] == 'Bloodletter' for g in r['grupos']
                                      for i in g['itens'] if g['nome'] == 'Viagem 4'))
checar('e avisa do que nao tem caminho de menu', r['avisos'] and 'Item Que Nao Existe' in r['avisos'][0],
       str(r['avisos']))

checar('cada mudanca ja fica gravada, sem botao salvar',
       os.path.exists(os.path.join(_DADOS, 'catalogo-padrao.json')))

r = api.mover(['Bloodletter'], 'Viagem 5')
checar('mover para um grupo novo cria o grupo',
       any(g['nome'] == 'Viagem 5' and g['itens'] for g in r['grupos']))

r = api.remover(['Bloodletter'])
checar('remove', not any(i['nome'] == 'Bloodletter' for g in r['grupos'] for i in g['itens']))
checar('e da para desfazer', r['desfazer'])

r = api.desfazer()
checar('desfazer devolve o item ao grupo de onde saiu',
       any(i['nome'] == 'Bloodletter' for g in r['grupos'] if g['nome'] == 'Viagem 5' for i in g['itens']))

r = api.renomear_grupo('Viagem 5', 'Lanças')
checar('renomeia', any(g['nome'] == 'Lanças' for g in r['grupos']))

r = api.apagar_grupo('Lanças', 'Viagem 4')
checar('apagar um grupo leva os itens para outro',
       any(i['nome'] == 'Bloodletter' for g in r['grupos'] if g['nome'] == 'Viagem 4' for i in g['itens']))

# --- quantidades em tres niveis -----------------------------------------
q = api.quantidades('item', 'Bloodletter')
checar('o item herda do grupo, que herda da tabela',
       all(not x['proprio'] for x in q['quantidades']))

q = api.definir_quantidade('item', 'Bloodletter', 'T6.0', '5')
t60 = next(x for x in q['quantidades'] if x['rotulo'] == 'T6.0')
checar('um valor proprio no item', t60['proprio'] and t60['valor'] == 5, str(t60))

checar('quantidade absurda e recusada, com motivo',
       'erro' in api.definir_quantidade('item', 'Bloodletter', 'T6.0', '99999'))

checar('texto nao vira quantidade', 'erro' in api.definir_quantidade('item', 'Bloodletter', 'T6.0', 'oito'))

q = api.definir_quantidade('item', 'Bloodletter', 'T6.0', None)
t60 = next(x for x in q['quantidades'] if x['rotulo'] == 'T6.0')
checar('apagar o valor proprio volta a herdar', not t60['proprio'], str(t60))

q = api.definir_todas('grupo', 'Viagem 4', '2')
checar('todas de uma vez, num grupo', all(x['valor'] == 2 for x in q['quantidades']))

checar('em lote recusa rotulo que nao existe', 'erro' in api.em_lote('9.9', '0'))

r = api.em_lote('8.3, 8.2', '0', ['Bloodletter'])
checar('em lote nos itens marcados',
       catalogo.quantidade('Bloodletter', 'T8.2') == 0 and 'Bloodletter' in [i['nome'] for g in r['grupos'] for i in g['itens']])

r = api.salvar_catalogo_como('Teste')
checar('salvar como troca o nome atual', r['nome'] == 'Teste' and 'Teste' in r['salvos'])

r = api.abrir_catalogo('padrao')
checar('e da para voltar ao outro', r['nome'] == 'padrao')

arvore = api.itens_do_jogo()
checar('a arvore do jogo traz as categorias', any(c['nome'] == 'Weapons' for c in arvore)
       and vira_json(arvore))


# ============================================================
grupo('a tela de compra')

agora = time.time()

for item in ('Broadsword', 'Claymore'):
    mercado.gravar('Thetford', item, 'T6.0', 10000, agora)
    mercado.gravar(mercado.MERCADO_NEGRO, item, 'T6.0', 20000, agora)

r = api.calcular_compra('Thetford', '23', '', '')
checar('a lista sai com as duas linhas', len(r['linhas']) == 2, str(len(r['linhas'])))
checar('e com o resumo', r['resumo']['lucro'] > 0)
checar('e vira JSON', vira_json(r))

r = api.calcular_compra('a melhor', '23,0', '', '')
checar('a melhor cidade e a que tem preco', r['origem'] == 'Thetford', str(r['origem']))

r = api.calcular_compra('Martlock', '23', '', '')
checar('cidade sem preco diz por que a lista esta vazia',
       not r['linhas'] and r['aviso'] and r['resumo']['sem_preco_de_compra'] > 0, str(r['aviso']))

r = api.calcular_compra('Thetford', '23', '', '15')
checar('os espacos do inventario limitam as unidades', r['resumo']['unidades'] == 15,
       str(r['resumo']['unidades']))

r = api.calcular_compra('Thetford', '500', '', '')
checar('margem impossivel esvazia a lista e explica', not r['linhas'] and r['aviso'])

api._compra = None
checar('comprar sem lista calculada e recusado', not api.comprar(False)['ok'])


# ============================================================
grupo('a tela de venda')

r = api.calcular_venda('', '')
checar('sem carga, nada para vender', r['linhas'] == [] and r['unidades'] == 0)

historico.comprou('Thetford', 'Broadsword', 'T6.0', 3, 10000, modo='ordem')

r = api.calcular_venda('23', '95')
checar('a carga vem do historico de hoje', r['unidades'] == 3, str(r))
checar('e cada linha diz o alvo', r['linhas'] and r['linhas'][0]['alvo'] > 10000)
checar('e vira JSON', vira_json(r))

# A PREVISAO E DA COMBINACAO COMPRADA. Antes ela pegava o maior pedido do item
# em qualquer grau - o do T8.0 prevendo a venda de um T6.0.
mercado.gravar(mercado.MERCADO_NEGRO, 'Broadsword', 'T6.0', 15000, outro=14800)
mercado.gravar(mercado.MERCADO_NEGRO, 'Broadsword', 'T8.0', 450000, outro=400000)

r = api.calcular_venda('23', '95')
l = r['linhas'][0] if r['linhas'] else {}
checar('a previsao usa os precos da combinacao comprada',
       l.get('combinacao') == 'T6.0' and l.get('modo') == 'na hora', str(l))
checar('e o previsto e liquido de taxa',
       l.get('previsto') == int(lucro.receita_real(14800, lucro.TAXA_SEM_PREMIUM) * 3),
       str(l))


# A VENDA PELO MERCADO NAO DEPENDE DA COMPRA, e passa pelo mesmo portao das
# outras operacoes - NUNCA com o ambiente de verdade, que com o jogo aberto
# comecaria a vender de fato
_verificar_real, _focar_real = comum.verificar_ambiente, comum.focar_jogo
comum.verificar_ambiente = lambda exigir_foco: ['jogo fechado (teste)']
comum.focar_jogo = lambda: False

try:
    r = api.vender_pelo_mercado(True)
finally:
    comum.verificar_ambiente, comum.focar_jogo = _verificar_real, _focar_real

checar('e passa pelo portao do jogo pronto, como as outras operacoes',
       r.get('problemas') == ['jogo fechado (teste)'] and api._rodando is None, str(r))


# ============================================================
grupo('o historico')

historico.vendeu(mercado.MERCADO_NEGRO, 'Broadsword', '', 1, 19000, modo='na hora')

r = api.historico('', 'tudo')
checar('as operacoes aparecem', r['filtradas'] == 2, str(r['filtradas']))
checar('a mais recente primeiro', r['linhas'][0]['operacao'] == 'venda', str(r['linhas'][0]))
checar('com o saldo das filtradas', r['resumo']['saldo'] == 19000 - 30000, str(r['resumo']))

r = api.historico('Thetford', 'hoje')
checar('o filtro de lugar vale', r['filtradas'] == 1 and r['resumo']['vendas'] == 0)
checar('e sem venda nao ha margem', r['resumo']['margem'] is None)

checar('os destaques dizem a cidade onde mais comprou',
       api.historico('', 'tudo')['destaques']['cidade']['valor'] == 'Thetford')

# ORDEM DE VENDA CRIADA NAO E PRATA RECEBIDA
historico.vendeu(mercado.MERCADO_NEGRO, 'Claymore', '', 2, 5000, modo='ordem',
                 liquido=8950)

r = api.historico('', 'tudo')
checar('a ordem de venda aparece em "em ordens", fora do saldo',
       r['resumo']['em_ordens'] == 8950 and r['resumo']['saldo'] == 19000 - 30000,
       str(r['resumo']))


# ============================================================
grupo('os ajustes')

a = api.ajustes_atuais()
checar('os valores atuais e as opcoes', 'margem' in a['valores'] and a['teclas'] and vira_json(a))

dados = dict(a['valores'])
dados.update(margem='abc', teto='', espacos='48')

r = api.salvar_ajustes(dados)
checar('campo invalido nao grava nada', not r['ok'] and 'margem' in r['erros'], str(r))
checar('e o valor antigo continua', ajustes.atuais()['margem'] == a['valores']['margem'])

dados.update(margem='25,5', tecla_pular='f12')
r = api.salvar_ajustes(dados)
checar('a mesma tecla em duas funcoes e recusada', not r['ok'] and 'tecla_pular' in r['erros'], str(r))

dados.update(tecla_pular='f2')
r = api.salvar_ajustes(dados)
checar('com tudo certo, grava', r['ok'], str(r))
checar('a margem vira fracao', abs(ajustes.atuais()['margem'] - 0.255) < 1e-9)
checar('teto vazio e sem teto', ajustes.atuais()['teto'] is None)
checar('e os espacos ficam', ajustes.atuais()['espacos'] == 48)
checar('no arquivo da pasta de dados', os.path.exists(os.path.join(_DADOS, 'ajustes.json')))

r = api.restaurar_ajustes()
checar('voltar ao padrao', abs(r['valores']['margem'] - ajustes.PADRAO['margem']) < 1e-9)


# ============================================================
grupo('a leitura de precos')

m = api.mercados()
checar('os sete mercados', len(m['mercados']) == 7 and vira_json(m))

checar('escolher o mercado fica lembrado',
       api.escolher_mercado('Thetford') and ajustes.atuais()['ultimo_mercado'] == 'Thetford')

checar('e mercado que nao existe nao', not api.escolher_mercado('Narnia'))

p = api.plano_varredura('Thetford', None, False)
checar('o plano conta as combinacoes do catalogo', p['combinacoes'] > 1500, str(p))

# AS COMBINACOES DA LEITURA: desmarcar pula aquela combinacao em todos os itens
c = api.combinacoes_para_ler()
checar('de fabrica, as 13 combinacoes estao marcadas',
       len(c['rotulos']) == 13 and c['marcadas'] == c['rotulos'] and vira_json(c), str(c))

c = api.marcar_combinacoes_para_ler(['T7.0', 'T6.0', 'T9.9'])
checar('marcar algumas guarda so essas, na ordem do jogo e sem rotulo invalido',
       c['marcadas'] == ['T6.0', 'T7.0'] and ajustes.atuais()['combinacoes_lidas'] == ['T6.0', 'T7.0'],
       str(c))

p2 = api.plano_varredura('Thetford', None, False)
_esperadas = sum(1 for i in catalogo.para_varrer(None) for g, e in catalogo.combinacoes_de(i)
                 if (g, e) in ((6, 0), (7, 0)))
checar('e o plano conta so as marcadas', p2['combinacoes'] == _esperadas and 0 < p2['combinacoes'] < p['combinacoes'],
       f"{p2['combinacoes']} de {p['combinacoes']}, esperadas {_esperadas}")

c = api.marcar_combinacoes_para_ler([])
p3 = api.plano_varredura('Thetford', None, False)
checar('nenhuma marcada: nada a ler, e o aviso diz por que',
       p3['combinacoes'] == 0 and 'Nenhuma combinação marcada' in (p3.get('aviso') or ''), str(p3))

c = api.marcar_combinacoes_para_ler(c['rotulos'])
checar('todas marcadas de novo e o mesmo que sem filtro',
       ajustes.atuais()['combinacoes_lidas'] is None
       and api.plano_varredura('Thetford', None, False)['combinacoes'] == p['combinacoes'])

# A REDE CALADA NAO TRAVA A LEITURA. Ela e o normal logo depois de abrir o jogo,
# e o aviso que perguntava "tentar mesmo assim?" aparecia toda vez. Agora o
# primeiro item testa a rede, e o Andamento diz o resultado.
#
# NUNCA COM O AMBIENTE DE VERDADE: com o jogo aberto na maquina, nada mais
# impedia a leitura de comecar - e ela comecava, clicando e digitando no jogo.
# O ambiente de mentira devolve um problema, e a leitura so devolve a lista.
_verificar_real, _focar_real = comum.verificar_ambiente, comum.focar_jogo
comum.verificar_ambiente = lambda exigir_foco: ['jogo fechado (teste)']
comum.focar_jogo = lambda: False

try:
    r = api.varrer('Thetford')
finally:
    comum.verificar_ambiente, comum.focar_jogo = _verificar_real, _focar_real

checar('a rede ligada e calada nao vira problema que trava a leitura',
       r.get('problemas') == ['jogo fechado (teste)'] and api._rodando is None, str(r))


# ============================================================
grupo('a operacao')

_verificar, _focar, _instalar = comum.verificar_ambiente, comum.focar_jogo, comum.instalar_teclas
comum.instalar_teclas = lambda: None

comum.verificar_ambiente = lambda exigir_foco: ['jogo fechado']

r = api._rodar(lambda: None, 'teste')
checar('com o jogo fora, devolve os problemas e nao comeca', r.get('problemas') == ['jogo fechado']
       and api._rodando is None, str(r))

comum.verificar_ambiente = lambda exigir_foco: []
comum.focar_jogo = lambda: True

feito = threading.Event()
janela.chamadas.clear()

r = api._rodar(lambda: (comum.relatar('linha do bot'), comum.progresso(1, 2, 'item'),
                        comum.placar(gasto=100), feito.set()), 'teste', forcar=False)
checar('com tudo certo, comeca', r == {'ok': True}, str(r))

feito.wait(3)
time.sleep(0.6)

eventos = janela.eventos()
tipos = [x['tipo'] for x in eventos]

checar('a interface recebe inicio, linha, progresso, placar e fim',
       all(t in tipos for t in ('inicio', 'linha', 'progresso', 'placar', 'fim')), str(tipos))

checar('em lote, e nao uma chamada por linha', len(janela.chamadas) < len(eventos),
       f'{len(janela.chamadas)} chamadas para {len(eventos)} eventos')

checar('a linha leva a cor certa', any(x.get('etiqueta') == 'erro' for x in eventos) is False
       and any(x.get('texto') == 'linha do bot' for x in eventos))

checar('e ao fim nada fica rodando', api._rodando is None)
checar('a janela volta do minimizado', not janela.minimizada)

checar('ERRO vira linha vermelha', ponte.etiqueta('ERRO: algo') == 'erro')
checar('ATENCAO vira amarela', ponte.etiqueta('ATENCAO x') == 'aviso')

comum.aborto_pedido.clear()
api.parar()
checar('Parar e o mesmo que o F12: aborta', comum.aborto_pedido.is_set())
comum.aborto_pedido.clear()

comum.verificar_ambiente, comum.focar_jogo, comum.instalar_teclas = _verificar, _focar, _instalar


# ============================================================
grupo('o calibrador')

passos = api.calibrador_passos()
checar('os passos atravessam para o JavaScript (sem as contas)', vira_json(passos) and len(passos) >= 8)

r = api.salvar_coordenadas({'CMP_TIER_TOPO': 300, '_CMP_SEGUNDA': 327,
                            'PRECO_COMPRA': [1, 2, 30, 40]})
with open(os.path.join(_DADOS, 'coordenadas.json'), encoding='utf-8') as f:
    gravado = json.load(f)

checar('grava na pasta de dados', r['ok'] and 'CMP_TIER_TOPO' in gravado, str(r))
checar('com o derivado calculado aqui', gravado.get('CMP_DROPDOWN_PASSO') == 27, str(gravado))
checar('e sem os auxiliares', '_CMP_SEGUNDA' not in gravado)


# ============================================================
print(f'\n===== {ok} ok, {len(falhas)} falhas =====')

for f in falhas:
    print(f'  {f}')

raise SystemExit(1 if falhas else 0)
