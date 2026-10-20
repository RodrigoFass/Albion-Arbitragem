################################
#                              #
#           TESTES             #
#         ARBITRAGEM           #
#                              #
################################

# O que da para conferir SEM O JOGO ABERTO, nesta metade do programa.
#
# Aqui a coisa mais valiosa nao e o codigo, e o DADO: os 252 caminhos de menu, a
# ordem em que o jogo lista cada familia, os nove nomes que a planilha escreve de
# um jeito e o jogo de outro. Nada disso da erro de sintaxe quando esta errado -
# da uma compra do item vizinho.
#
# Por isso metade destas conferencias e contra evidencia externa: as posicoes
# medidas em capturas do menu, os totais publicados por outro programa, a lista
# de itens da sua propria planilha. Um teste que so confere o codigo contra ele
# mesmo passaria com o mapa inteiro errado.
#
#     python testes/testar.py

import atexit
import json
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# OS TESTES GRAVAM NUMA PASTA TEMPORARIA, definida antes de qualquer import do
# programa: e na importacao que cada modulo monta o caminho do seu arquivo. Antes
# eles gravavam no precos.json de verdade, e um teste que quebrasse no meio
# deixava precos de mentira para o app mostrar.
_DADOS = tempfile.mkdtemp(prefix='albion-testes-')
os.environ['ALBION_DADOS'] = _DADOS
atexit.register(shutil.rmtree, _DADOS, True)

from motor import comum          # noqa: E402
from motor import coordenadas as cd   # noqa: E402
from motor import mercado        # noqa: E402
from motor import lucro          # noqa: E402
from motor import nomes          # noqa: E402
from motor import categorias     # noqa: E402
from motor import menu           # noqa: E402
from motor import filtros        # noqa: E402
from motor import conferidor     # noqa: E402
from motor import mercado_negro  # noqa: E402
from motor import catalogo       # noqa: E402
from motor import compra         # noqa: E402

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


# ============================================================
grupo('a conta da lucro, conferida contra um caso real')

# Estas seis linhas sao a tela de compra do bot que serviu de referencia, com os
# numeros que ele mostrou. Elas estao aqui porque um numero publicado por outro
# programa e a unica forma de conferir a nossa conta sem o jogo aberto - e a
# conta e quem manda gastar prata.
#
# E ela revelou uma coisa: a margem dele NAO desconta imposto. Bate ao centesimo
# nas seis linhas e o custo bate ao silver, sem taxa nenhuma. Copiar o "minimo de
# 23%" dele sem saber disso seria comprar com 17,5% de margem achando que sao 23.

REFERENCIA = [
    #  combinacao  qtd    compra   venda   margem que ele mostrou
    ('T5.0', 100,  10994,  18444, 0.6776),
    ('T4.1',  80,   6991,   9666, 0.3826),
    ('T6.1',  30,  77898, 104980, 0.3477),
    ('T4.0', 100,   4994,   6722, 0.3460),
    ('T6.2',  10, 269993, 338484, 0.2537),
    ('T6.0',  80,  49871,  61662, 0.2364),
]

_banco_real = mercado._banco
_agora = time.time()

mercado.usar_banco({})

# A "venda" dele e o que ele RECEBE vendendo na hora: o pedido de compra do
# Mercado Negro. Gravada nas duas colunas, a lista escolhe vender na hora por
# ela - ver lucro.melhor_venda.
for _rot, _q, _c, _v, _m in REFERENCIA:
    mercado.gravar('Thetford', 'Assassin Jacket', _rot, _c, _agora)
    mercado.gravar(mercado.MERCADO_NEGRO, 'Assassin Jacket', _rot, _v, _agora,
                   outro=_v)

CATALOGO = [('Assassin Jacket', r, q) for r, q, _, _, _ in REFERENCIA]

linhas_bruto, resumo_bruto = lucro.montar(
    CATALOGO, 'Thetford', margem_minima=0.23, por_margem_bruta=True)

checar('as seis linhas entram', len(linhas_bruto) == 6, str(len(linhas_bruto)))

for _rot, _q, _c, _v, _m in REFERENCIA:
    _l = next(l for l in linhas_bruto if l['combinacao'] == _rot)
    checar(f'a margem bruta de {_rot} bate com a dele',
           abs(_l['margem_bruta'] - _m) < 0.0001,
           f"{_l['margem_bruta']*100:.2f}% contra {_m*100:.2f}%")

# de TABELA: o que aparece na tela do jogo, antes de qualquer taxa. E o que ele
# soma, e e por isso que os numeros dele batem com estes e nao com os nossos.
checar('o custo de tabela bate ao silver',
       resumo_bruto['custo_de_tabela'] == 11184630,
       f"{resumo_bruto['custo_de_tabela']} contra 11184630")

checar('a receita de tabela bate ao silver',
       resumo_bruto['receita_de_tabela'] == 14757080,
       f"{resumo_bruto['receita_de_tabela']} contra 14757080")

# e o nosso custo e MAIOR que o de tabela, porque comprar por ordem custa 2,5%
checar('comprar por ordem custa mais que o preco de tabela',
       resumo_bruto['custo'] > resumo_bruto['custo_de_tabela'])

checar('e comprar na hora custa exatamente o preco de tabela',
       lucro.custo_real(1000, ordem_na_compra=False) == 1000)

# as quatro combinacoes de taxa, todas abaixo da bruta
_bruta = lucro.bruto(10994, 18444)
for _taxa, _nome in ((lucro.TAXA_SEM_PREMIUM, 'sem Premium'),
                     (lucro.TAXA_COM_PREMIUM, 'com Premium')):
    for _ordem in (True, False):
        checar(f'{_nome}, ordem={_ordem}: a margem real fica abaixo da bruta',
               lucro.liquido(10994, 18444, _taxa,
                                  ordem_na_compra=_ordem) < _bruta)

checar('com Premium sobra mais que sem',
       lucro.liquido(10994, 18444, lucro.TAXA_COM_PREMIUM)
       > lucro.liquido(10994, 18444, lucro.TAXA_SEM_PREMIUM))

checar('pedido de venda custa a taxa de ordem a mais que vender na hora',
       lucro.receita_real(1000, 0.08, ordem_na_venda=True)
       == lucro.receita_real(1000, 0.08) - 1000 * lucro.TAXA_DE_ORDEM)

# o padrao tem que ser o caso CARO: errar para menos recomenda compra que nao paga
checar('o padrao e a taxa sem Premium',
       lucro.TAXA_PADRAO == lucro.TAXA_SEM_PREMIUM)

# ... e a nossa, que desconta, e sempre menor
linhas_liq, resumo_liq = lucro.montar(CATALOGO, 'Thetford', margem_minima=0.0)

checar('a margem liquida e sempre menor que a bruta',
       all(l['margem'] < l['margem_bruta'] for l in linhas_liq))

checar('e o lucro liquido tambem',
       resumo_liq['lucro']
       < resumo_bruto['receita_de_tabela'] - resumo_bruto['custo_de_tabela'])

# a taxa incide sobre a VENDA, nao sobre o lucro. Descontar do lucro daria um
# numero otimista, e otimista aqui significa comprar coisa que nao paga.
checar('a taxa sai da venda, e nao do lucro',
       abs(lucro.liquido(100, 200, 0.10, ordem_na_compra=False)
           - (200 * 0.9 - 100) / 100) < 1e-9)

# ordem: sempre da melhor margem para a pior, para o teto cortar o pior negocio
checar('a lista vem ordenada pela margem',
       [l['combinacao'] for l in linhas_bruto] == [r for r, _, _, _, _ in REFERENCIA])

_, resumo_teto = lucro.montar(CATALOGO, 'Thetford', margem_minima=0.0,
                                   teto=3_000_000)

checar('o teto corta, e corta o pior negocio',
       resumo_teto['custo'] <= 3_000_000 and resumo_teto['cortadas_pelo_teto'] > 0,
       str(resumo_teto['custo']))

# equipamento nao empilha: cada unidade e um espaco do inventario
_linhas_esp, _resumo_esp = lucro.montar(CATALOGO, 'Thetford', margem_minima=0.0,
                                        espacos=150)

checar('os espacos do inventario limitam as unidades',
       _resumo_esp['unidades'] == 150, str(_resumo_esp['unidades']))

checar('a linha que nao cabe inteira entra com o que cabe',
       _linhas_esp[-1]['quantidade'] < dict(
           (r, q) for r, q, _, _, _ in REFERENCIA)[_linhas_esp[-1]['combinacao']],
       str(_linhas_esp[-1]))

checar('e o resto fica de fora, contado',
       _resumo_esp['sem_espaco'] == len(linhas_bruto) - len(_linhas_esp),
       f'{_resumo_esp["sem_espaco"]} contra {len(linhas_bruto) - len(_linhas_esp)}')

checar('a linha aparada tem o custo da quantidade aparada',
       _linhas_esp[-1]['custo'] == lucro.custo_real(
           _linhas_esp[-1]['compra']) * _linhas_esp[-1]['quantidade'])

checar('sem espacos definidos nada muda',
       lucro.montar(CATALOGO, 'Thetford', margem_minima=0.0)[1]['sem_espaco'] == 0)

# --- a qualidade: so quando paga BEM mais que a Normal -----------------------
# Os precos de cada qualidade so existem pela rede. Aqui o Mercado Negro tem um
# pedido de qualidade 3 (Excepcional) pagando quase o dobro do da Normal.
_banco_q = mercado._banco
mercado.usar_banco({})
mercado.gravar('Thetford', 'Claymore', 'T6.0', 10_000, _agora)
mercado.atualizar('Thetford', 'Claymore', 'T6.0',
                  qualidades={1: {'oferta': 10_000}, 3: {'oferta': 12_000}})
mercado.gravar(mercado.MERCADO_NEGRO, 'Claymore', 'T6.0', 14_000, _agora, outro=13_000)
mercado.atualizar(mercado.MERCADO_NEGRO, 'Claymore', 'T6.0',
                  qualidades={1: {'pedido': 13_000}, 3: {'pedido': 25_000}})

_cat_q = [('Claymore', 'T6.0', 5)]

_sem_q, _ = lucro.montar(_cat_q, 'Thetford', margem_minima=0.0)
checar('desligada, a linha e a Normal de sempre', _sem_q and _sem_q[0]['qualidade'] is None,
       str(_sem_q))

_com_q, _res_q = lucro.montar(_cat_q, 'Thetford', margem_minima=0.0, por_qualidade=True)
checar('ligada, a qualidade que paga bem mais toma o lugar', _com_q and _com_q[0]['qualidade'] == 3,
       str(_com_q))
checar('comprando a oferta da propria qualidade', _com_q[0]['compra'] == 12_000)
checar('e vendendo no maior pedido que ela atende', _com_q[0]['venda'] == 25_000)
checar('sempre na hora: o custo e o preco da oferta, sem a taxa da ordem',
       _com_q[0]['custo'] == 12_000 * 5)
checar('e o resumo conta as linhas de qualidade', _res_q['por_qualidade'] == 1)

# um pedido de qualidade so um pouco melhor nao vale trocar a Normal
mercado.atualizar(mercado.MERCADO_NEGRO, 'Claymore', 'T6.0', qualidades={3: {'pedido': 15_500}})
_pouco, _ = lucro.montar(_cat_q, 'Thetford', margem_minima=0.0, por_qualidade=True)
checar('ganho pequeno fica na Normal, que gira mais rapido',
       _pouco and _pouco[0]['qualidade'] is None, str(_pouco))

# o pedido de qualidade MAIOR que a do item nao serve para ele
mercado.atualizar(mercado.MERCADO_NEGRO, 'Claymore', 'T6.0',
                  qualidades={3: {'pedido': 0}, 5: {'pedido': 90_000}})
mercado._banco[mercado.MERCADO_NEGRO]['Claymore']['T6.0']['qualidades'].pop('3')
_acima, _ = lucro.montar(_cat_q, 'Thetford', margem_minima=0.0, por_qualidade=True)
checar('pedido de qualidade acima da do item nao conta',
       _acima and _acima[0]['qualidade'] is None, str(_acima))

mercado.usar_banco(_banco_q)

# faltar preco e diferente de negocio ruim: um pede coleta, o outro pede item
_, resumo_falta = lucro.montar(
    [('Item Que Nao Existe', 'T5.0', 10)], 'Thetford', margem_minima=0.0)

checar('sem preco na cidade, conta como falta de coleta',
       resumo_falta['sem_preco_de_compra'] == 1)

mercado.gravar('Thetford', 'So Na Cidade', 'T5.0', 1000, _agora)
_, resumo_meio = lucro.montar([('So Na Cidade', 'T5.0', 10)], 'Thetford',
                                   margem_minima=0.0)

checar('sem preco no Mercado Negro, idem',
       resumo_meio['sem_preco_de_venda'] == 1)

# preco velho nao decide compra
mercado.gravar('Thetford', 'Velho', 'T5.0', 1000, _agora - 48 * 3600)
mercado.gravar(mercado.MERCADO_NEGRO, 'Velho', 'T5.0', 5000, _agora - 48 * 3600)
_, resumo_velho = lucro.montar([('Velho', 'T5.0', 10)], 'Thetford',
                                    margem_minima=0.0, idade_maxima=6.0)

checar('preco velho nao vira compra', resumo_velho['linhas'] == 0)
checar('e sai contado como velho, nao como margem ruim',
       resumo_velho['precos_velhos'] == 1)

# a melhor cidade e uma comparacao, nao uma opiniao
mercado.gravar('Martlock', 'Assassin Jacket', 'T5.0', 5000, _agora)
_cidade, _, _ = lucro.melhor_origem(
    [('Assassin Jacket', 'T5.0', 100)], margem_minima=0.0)

checar('escolhe a cidade onde o mesmo item sai mais barato',
       _cidade == 'Martlock', _cidade)

# sem linha em cidade nenhuma nao ha "melhor" - antes saia a primeira da lista
checar('nenhuma cidade com linha da None, e nao a primeira da lista',
       lucro.melhor_origem([('Item que ninguem leu', 'T5.0', 100)],
                           margem_minima=0.0) is None)

checar('comparar() devolve uma linha por cidade',
       len(lucro.comparar([('Assassin Jacket', 'T5.0', 100)],
                               margem_minima=0.0)) == len(mercado.ORIGENS))

mercado.usar_banco(_banco_real)


# ============================================================
grupo('o nome do item nos dois idiomas')

# O jogo poe o grau em lugares diferentes da frase:
#
#     portugues:   Espada Larga do Mestre     (depois)
#     ingles:      Master's Broadsword        (antes)
#
# E disso vem toda a estrategia de busca.

checar('os oito graus tem prefixo em ingles',
       set(nomes.PREFIXO_INGLES) == set(range(1, 9)))

checar('e sao os do jogo',
       nomes.prefixo(4) == "Adept's" and nomes.prefixo(5) == "Expert's"
       and nomes.prefixo(6) == "Master's" and nomes.prefixo(8) == "Elder's")

checar('grau desconhecido nao inventa prefixo', nomes.prefixo(99) == '')

checar('e nesse caso o nome sai sem enfeite',
       nomes.completo('Broadsword', 99) == 'Broadsword')

checar('o nome completo e prefixo + base',
       nomes.completo('Broadsword', 6) == "Master's Broadsword")

# ESTE E O CASO QUE CUSTOU CARO. Um item "A" e um item "A ELEVADO" - em ingles,
# Cursed Staff e Great Cursed Staff. Antes da comparacao posicional, tres de
# quatro leituras casavam com o item errado.
_PT = ('Cajado Amaldicoado do', 'Cajado Amaldicoado Elevado do')
_EN = ('Cursed Staff', 'Great Cursed Staff')

for _ling, _certo, _intruso in (
        (nomes.PORTUGUES, _PT[0], _PT[1]),
        (nomes.INGLES, nomes.completo(_EN[0], 5), nomes.completo(_EN[1], 5))):

    checar(f'{_ling}: o item certo casa consigo mesmo',
           comum.parece_o_mesmo_item(_certo, _certo) is True)

    checar(f'{_ling}: o "elevado" NAO passa pelo simples',
           comum.parece_o_mesmo_item(_intruso, _certo) is False,
           f'{_intruso!r} contra {_certo!r}')

# em ingles as duas frases divergem na SEGUNDA palavra, e nenhuma e o comeco da
# outra - o que em portugues nao da para garantir, porque o grau vem depois
checar('em ingles nenhum dos dois nomes comeca com o outro',
       not nomes.completo(_EN[1], 5).startswith(nomes.completo(_EN[0], 5)))

# --- o que se digita contra o que se confere -------------------------------
checar('em ingles digita a base, sem grau',
       nomes.termo('Broadsword', 'Espada Larga do', nomes.INGLES) == 'Broadsword')

checar('uma busca so serve para os 13 graus e encantamentos',
       len({nomes.termo('Broadsword', 'Espada Larga do', nomes.INGLES)
            for _g in range(1, 9)}) == 1)

checar('mas confere o nome completo de CADA grau',
       len({nomes.na_tela('Broadsword', 'Espada Larga do', _g, nomes.INGLES)
            for _g in range(1, 9)}) == 8)

checar('em portugues nada muda: busca e conferencia sao a coluna AC',
       nomes.termo('Broadsword', 'Espada Larga do', nomes.PORTUGUES)
       == nomes.na_tela('Broadsword', 'Espada Larga do', 6, nomes.PORTUGUES)
       == 'Espada Larga do')

# --- a troca de idioma ------------------------------------------------------
checar('o padrao continua sendo o portugues, para nao quebrar os tres bots',
       nomes.idioma() == nomes.PORTUGUES)

_antes = nomes.idioma()
checar('trocar para ingles vale', nomes.usar_idioma(nomes.INGLES) == nomes.INGLES)
checar('e um idioma inventado nao passa',
       nomes.usar_idioma('klingon') == nomes.INGLES)
nomes.usar_idioma(_antes)

checar('e volta', nomes.idioma() == nomes.PORTUGUES)

# so os quatro sufixos que sairam de telas do jogo. Palpite aqui vira erro que
# alguem encontra daqui a seis meses.
checar('so os sufixos em portugues que foram vistos na tela',
       set(nomes.SUFIXO_PORTUGUES) == {1, 4, 5, 6})

checar('e os que estao batem com as telas',
       nomes.SUFIXO_PORTUGUES[4] == 'do Adepto'
       and nomes.SUFIXO_PORTUGUES[6] == 'do Mestre')


# ============================================================
grupo('o caminho de menu de cada item')

# Escolher o item no menu em cascata faz a lista conter SO ele - e ai nao ha o
# que confundir. E o fim de um problema que o programa vinha combatendo por
# leitura desde o comeco: o "do" no fim do nome, a comparacao posicional, o item
# "A" casando com o item "A ELEVADO".
#
# Este grupo confere o mapa contra o CATALOGO QUE VEM COM O PROGRAMA - os 121
# itens que voce negocia. Um item dele sem rota aqui e uma navegacao que vai
# parar no meio.
with open(catalogo.ARQUIVO_INICIAL, encoding='utf-8') as _f:
    _do_inicial = [n for itens in json.load(_f)['grupos'].values() for n in itens]

_sem_rota = [n for n in _do_inicial if not categorias.navegavel(n)]

checar('todo item do catalogo inicial da para navegar no menu', not _sem_rota,
       f'{len(_sem_rota)} sem rota: {", ".join(_sem_rota[:6])}')

checar('o catalogo inicial tem os 121 itens de sempre', len(_do_inicial) == 121,
       str(len(_do_inicial)))

checar('nao sobrou nada por confirmar', not categorias.por_confirmar(),
       ", ".join(categorias.por_confirmar()[:6]))

# --- a geometria, conferida contra as capturas ------------------------------
# Cada uma destas foi medida numa captura do menu aberto. Sao a prova de que a
# conta "indice x 27" descreve a tela, e nao so a si mesma.
for _item, _esperado in (
        ('Crossbow',    [(815, 324), (950, 378), (1085, 405)]),
        ('Broadsword',  [(815, 324), (950, 594), (1085, 621)]),
        ('Royal Cowl',  [(815, 378), (950, 405), (1085, 540)]),
        ('Shield',      [(815, 432), (950, 513), (1085, 540)]),
        ('Demon Cape',  [(815, 459), (950, 837)]),
        ('Satchel',     [(815, 486), (950, 540)])):

    _ind = categorias.indices(_item)
    _saiu = [(categorias.posicao(_ind[:n + 1])['x'],
              categorias.posicao(_ind[:n + 1])['y']) for n in range(len(_ind))]

    checar(f'a posicao de {_item} bate com a captura', _saiu == _esperado,
           f'{_saiu} contra {_esperado}')

checar('o passo do menu e o mesmo dos outros dropdowns do jogo',
       categorias.MENU_PASSO == cd.CMP_DROPDOWN_PASSO,
       f'{categorias.MENU_PASSO} contra {cd.CMP_DROPDOWN_PASSO}')

checar('cada nivel se desloca do anterior por uma distancia so',
       categorias.MENU_X[1] - categorias.MENU_X[0]
       == categorias.MENU_X[2] - categorias.MENU_X[1]
       == categorias.MENU_DESLOCAMENTO)

checar('a faixa de leitura cabe dentro de uma entrada',
       categorias.MENU_ALTURA < categorias.MENU_PASSO)

# --- dois niveis nao e a mesma coisa que tres -------------------------------
# Capes e Bags param no segundo nivel: o item ja esta la, e nao ha submenu para
# abrir. Tratar todo mundo como tres faria o bot esperar um menu que nunca vem.
checar('Capes e Bags param no segundo nivel',
       len(categorias.indices('Demon Cape')) == 2
       and len(categorias.indices('Bag')) == 2)

checar('e o resto desce ate o terceiro',
       len(categorias.indices('Broadsword')) == 3
       and len(categorias.indices('Shield')) == 3)

checar('os rotulos a conferir acompanham o numero de niveis',
       len(categorias.rotulos('Demon Cape')) == 2
       and len(categorias.rotulos('Broadsword')) == 3)

checar('e o ultimo rotulo e o nome do item no menu',
       categorias.rotulos('Greathammer')[-1] == 'Great Hammer'
       and categorias.rotulos('Satchel')[-1] == 'Satchels of Insight')

# --- os nomes que a planilha escreve diferente do jogo ----------------------
for _da_planilha_nome, _no_jogo in categorias.NOME_NO_MENU.items():
    checar(f'{_da_planilha_nome} e "{_no_jogo}" no menu',
           categorias.no_menu(_da_planilha_nome) == _no_jogo
           and categorias.navegavel(_da_planilha_nome))

checar('e um nome que nao precisa de traducao passa direto',
       categorias.no_menu('Broadsword') == 'Broadsword')

# --- A ORDEM DO MENU NAO E A DA PLANILHA -----------------------------------
# Nas armaduras a planilha traz Royal antes de Druid, e o jogo traz o contrario.
# Usar a ordem da planilha clicaria um lugar acima e compraria outra coisa.
_cowls = dict(categorias.TRES_NIVEIS['Head Armor'])['Cloth Cowl']

checar('no menu, Druid vem antes de Royal',
       _cowls.index('Druid Cowl') < _cowls.index('Royal Cowl'),
       str(_cowls))

checar('e a diferenca vale uma linha inteira de menu',
       categorias.indices('Royal Cowl')[-1]
       - categorias.indices('Druid Cowl')[-1] == 1)

# --- item desconhecido nao vira navegacao plausivel -------------------------
checar('item que nao existe nao tem rota',
       categorias.indices('Espada de Teste') is None
       and categorias.caminho('Espada de Teste') is None
       and categorias.rotulos('Espada de Teste') is None)

checar('o mapa cobre bem mais que a planilha, por causa dos artefatos',
       len(categorias.itens_mapeados()) > 200,
       str(len(categorias.itens_mapeados())))


# ============================================================
grupo('os sete mercados')

checar('as seis cidades reais mais Caerleon', len(mercado.CIDADES) == 6,
       str(mercado.CIDADES))

checar('o Mercado Negro entra como mercado a parte',
       mercado.MERCADO_NEGRO in mercado.MERCADOS
       and mercado.MERCADO_NEGRO not in mercado.CIDADES)

checar('nao se compra no proprio Mercado Negro para vender nele',
       mercado.MERCADO_NEGRO not in mercado.ORIGENS)

checar('o rotulo e o mesmo formato do resto do programa',
       mercado.rotulo(5, 2) == 'T5.2' and mercado.partes('T5.2') == (5, 2))

checar('rotulo invalido nao vira combinacao',
       mercado.partes('Assassin') is None and mercado.partes('T5') is None)

checar('o banco de precos fica na pasta de dados',
       os.path.dirname(mercado.ARQUIVO) == comum.PASTA_DADOS)

checar('e os testes rodam numa pasta temporaria, longe dos seus arquivos',
       comum.PASTA_DADOS == _DADOS and comum.PASTA_DADOS != comum.PASTA)



# ============================================================
grupo('descer o menu ate o item')

# Um menu de mentira que responde como o do jogo: o primeiro nivel fica visivel
# quando ele abre, e cada submenu so aparece depois que o mouse para em cima do
# pai. As posicoes saem das MESMAS funcoes que o bot usa - o que se testa aqui e
# a navegacao (a ordem dos passos, a conferencia antes de clicar, o que acontece
# quando algo nao bate), e nao a geometria, que ja foi conferida contra as
# capturas la em cima.


class Menu:
    """A tela do menu, do ponto de vista de quem le e clica nela."""

    def __init__(self):
        self.aberto = False
        self.sob_o_mouse = []
        self.cliques = []
        self.deslocar = {}      # familia -> quantas linhas o jogo empurrou

    def _visivel(self):
        """{regiao: (texto, caminho)} do que estaria na tela agora.

        O CAMINHO VEM JUNTO de proposito. A posicao sozinha nao identifica um
        item: [0, 3] e [1, 2] caem no mesmo pixel, porque a altura e a soma dos
        indices. No jogo isso nao e problema - so um caminho fica visivel de cada
        vez - mas so da para saber qual olhando o estado do menu, e nao a
        coordenada."""

        tela = {}

        if not self.aberto:
            return tela

        for i, nome in enumerate(categorias.CATEGORIAS):
            tela[categorias.regiao([i])] = (nome, [i])

        if len(self.sob_o_mouse) >= 1:
            i1 = self.sob_o_mouse[0]
            cat1 = categorias.CATEGORIAS[i1]

            if cat1 in categorias.TRES_NIVEIS:
                nomes = ['All'] + [s for s, _ in categorias.TRES_NIVEIS[cat1]]
            elif cat1 in categorias.DOIS_NIVEIS:
                nomes = ['All'] + list(categorias.DOIS_NIVEIS[cat1])
            else:
                nomes = ['All']

            for i, nome in enumerate(nomes):
                tela[categorias.regiao([i1, i])] = (nome, [i1, i])

        if len(self.sob_o_mouse) >= 2:
            i1, i2 = self.sob_o_mouse[:2]
            subs = categorias.TRES_NIVEIS.get(categorias.CATEGORIAS[i1], [])

            if 1 <= i2 <= len(subs):
                familia, itens = subs[i2 - 1]
                itens = ['Arma Nova'] * self.deslocar.get(familia, 0) + list(itens)

                for i, nome in enumerate(['All'] + itens):
                    tela[categorias.regiao([i1, i2, i])] = (nome, [i1, i2, i])

        return tela

    def ler(self, regiao):
        return self._visivel().get(tuple(regiao), ('', None))[0]

    def _caminho_em(self, pos):
        """Que caminho VISIVEL fica exatamente nessa posicao."""

        for regiao, (_, caminho) in self._visivel().items():
            centro = ((regiao[0] + regiao[2]) // 2, (regiao[1] + regiao[3]) // 2)
            if centro == (pos['x'], pos['y']):
                return caminho

        return None

    def apontar(self, pos):
        caminho = self._caminho_em(pos)

        if caminho:
            self.sob_o_mouse = caminho

    def clicar(self, pos, espera=None):
        if (pos['x'], pos['y']) == (categorias.MENU_BOTAO['x'],
                                    categorias.MENU_BOTAO['y']):
            self.aberto = not self.aberto
            self.sob_o_mouse = []
            return

        self.cliques.append((pos['x'], pos['y']))


def _com_menu(tela, acao):
    """Roda <acao> com a tela de mentira no lugar da de verdade."""

    reais = (comum.ler_texto, comum.clicar, comum.apontar)

    comum.ler_texto = tela.ler
    comum.clicar = tela.clicar
    comum.apontar = tela.apontar

    try:
        return acao()
    finally:
        comum.ler_texto, comum.clicar, comum.apontar = reais
        comum.zerar_contadores()


# --- o caminho feliz --------------------------------------------------------
_tela = Menu()
_res, _motivo = _com_menu(_tela, lambda: menu.selecionar('Crossbow'))

checar('chega no item', _res, _motivo)

checar('e clica UMA vez, no lugar certo', _tela.cliques == [(1085, 405)],
       str(_tela.cliques))

checar('o menu ficou aberto no caminho certo', _tela.sob_o_mouse == [1, 2],
       str(_tela.sob_o_mouse))

# --- dois niveis so ---------------------------------------------------------
_tela = Menu()
_res, _motivo = _com_menu(_tela, lambda: menu.selecionar('Demon Cape'))

checar('capa desce so dois niveis', _res, _motivo)

checar('e o clique cai no segundo', _tela.cliques == [(950, 837)],
       str(_tela.cliques))

# --- o menu ja aberto -------------------------------------------------------
# Com o menu na tela, clicar no botao FECHA. A navegacao seguinte aconteceria em
# cima da lista de ofertas, clicando em "Comprar".
_tela = Menu()
_tela.aberto = True
_res, _motivo = _com_menu(_tela, lambda: menu.selecionar('Broadsword'))

checar('menu ja aberto nao e fechado por engano', _res, _motivo)

checar('e nada de estranho foi clicado', _tela.cliques == [(1085, 621)],
       str(_tela.cliques))

# --- O QUE ESTE MODULO EXISTE PARA PEGAR ------------------------------------
# O jogo acrescenta uma arma no meio da familia. Todas as de baixo descem uma
# linha, a posicao calculada continua sendo clicavel, e o clique cai no vizinho.
# Sem conferir por leitura, isso compraria o item errado em silencio - e o
# silencio e o que faz esse tipo de erro sobreviver a varreduras inteiras.
_tela = Menu()
_tela.deslocar = {'Crossbow': 1}
_res, _motivo = _com_menu(_tela, lambda: menu.selecionar('Crossbow'))

checar('uma arma nova no meio da familia NAO passa batido', not _res, _motivo)

checar('e o motivo aponta o nivel', 'nivel 3' in _motivo, _motivo)

checar('e nada foi clicado', not _tela.cliques, str(_tela.cliques))

# --- item sem caminho -------------------------------------------------------
_tela = Menu()
_res, _motivo = _com_menu(_tela, lambda: menu.selecionar('Espada de Teste'))

checar('item desconhecido nao vira navegacao', not _res)

checar('e diz por que', 'caminho de menu' in _motivo, _motivo)

checar('sem tocar no mouse', not _tela.cliques and not _tela.aberto)

# --- o menu que nao abre ----------------------------------------------------


class MenuTravado(Menu):
    def clicar(self, pos, espera=None):
        pass


_tela = MenuTravado()
_res, _motivo = _com_menu(_tela, lambda: menu.selecionar('Broadsword'))

checar('menu que nao abre para a navegacao', not _res)

checar('e diz isso', 'nao abriu' in _motivo, _motivo)

# --- o submenu que nao abre -------------------------------------------------


class SubmenuTravado(Menu):
    def apontar(self, pos):
        pass


_tela = SubmenuTravado()
_tela.aberto = True
_res, _motivo = _com_menu(_tela, lambda: menu.selecionar('Broadsword'))

checar('submenu que nao abre para a navegacao', not _res)

checar('e diz de qual submenu se trata', 'Weapons' in _motivo, _motivo)

checar('e nao clica no escuro', not _tela.cliques, str(_tela.cliques))

# --- os 121 itens do catalogo inicial, um por um ----------------------------
_nao_navegaram = []

for _nome in _do_inicial:
    _t = Menu()
    if not _com_menu(_t, lambda n=_nome: menu.selecionar(n))[0]:
        _nao_navegaram.append(_nome)

checar('os 121 itens do catalogo inicial descem o menu inteiro',
       not _nao_navegaram,
       f'{len(_nao_navegaram)}: {", ".join(_nao_navegaram[:5])}')


# ============================================================
grupo('a varredura que enche o banco de precos')

# O Conferidor roda duas vezes por rota: no Mercado Negro para saber quanto ele
# PAGA, e na cidade para saber quanto custa COMPRAR. E a mesma varredura nos
# dois; so muda o nome sob o qual os precos sao guardados.


class Mercado:
    """O jogo, do ponto de vista do Conferidor."""

    def __init__(self, tabela=None):
        # {(item, grau, ench): preco} - o que o mercado tem
        self.tabela = tabela or {}
        self.item = None
        self.grau = None
        self.ench = None
        self.trocas = []
        self.limpezas = 0
        self.itens_sem_menu = set()
        self.buscados = []
        self.pelo_menu = []

    def selecionar(self, item):
        if item in self.itens_sem_menu:
            return False, f'"{item}" nao tem caminho de menu conhecido'
        self.item = item
        self.grau = self.ench = None
        self.pelo_menu.append(item)
        return True, ''

    def digitar(self, texto):
        """A busca do jogo: o que foi digitado passa a ser o item da lista."""

        self.buscados.append(texto)
        self.item = texto
        self.grau = self.ench = None

    def grau_para(self, valor):
        self.grau = valor
        self.trocas.append(('grau', valor))
        return True

    def ench_para(self, valor):
        self.ench = valor
        self.trocas.append(('ench', valor))
        return True

    def limpar(self):
        self.limpezas += 1
        self.grau = self.ench = None

    def numero(self, regiao):
        """Uma olhada, sem insistir - o que comum.ler_numero faz."""

        return self.tabela.get((self.item, self.grau, self.ench))

    def ler(self, regiao, anterior=None):
        """Insiste por um valor diferente do anterior - o ler_numero_novo."""

        return self.tabela.get((self.item, self.grau, self.ench))

    def texto(self, regiao):
        """Duas regioes de texto na tela, e elas dizem coisas diferentes."""

        if regiao == cd.CMP_LINHA_ITEM:
            return self.item or ''

        return ('' if self.numero(regiao) is not None
                else 'No offers found.')


def _com_mercado(jogo, acao):
    """Roda <acao> com o jogo de mentira no lugar do de verdade."""

    reais = (menu.selecionar, filtros.grau, filtros.encantamento, filtros.limpar,
             comum.ler_numero_novo, comum.ler_numero, comum.ler_texto,
             comum.clicar, comum.digitar, comum.assinatura,
             comum.esperar_mudanca, comum.esperar_estavel,
             comum.jogo_em_foco, comum.sem_foco,
             comum.relatar, comum.progresso)

    menu.selecionar = jogo.selecionar
    filtros.grau = jogo.grau_para
    filtros.encantamento = jogo.ench_para
    filtros.limpar = jogo.limpar
    comum.ler_numero_novo = jogo.ler
    comum.ler_numero = jogo.numero
    comum.ler_texto = jogo.texto
    comum.clicar = lambda p, espera=None: None
    comum.digitar = jogo.digitar
    comum.assinatura = lambda r: b''
    comum.esperar_mudanca = lambda *a, **k: True
    comum.esperar_estavel = lambda *a, **k: True
    comum.jogo_em_foco = lambda: True
    comum.sem_foco = lambda: []
    comum.relatar = lambda *a, **k: None
    comum.progresso = lambda *a, **k: None

    conferidor.menu = menu
    conferidor.filtros = filtros
    conferidor.comum = comum

    try:
        return acao()
    finally:
        (menu.selecionar, filtros.grau, filtros.encantamento, filtros.limpar,
         comum.ler_numero_novo, comum.ler_numero, comum.ler_texto,
         comum.clicar, comum.digitar, comum.assinatura,
         comum.esperar_mudanca, comum.esperar_estavel,
         comum.jogo_em_foco, comum.sem_foco,
         comum.relatar, comum.progresso) = reais
        comum.zerar_contadores()


# um item com preco em todas as 13, crescendo com grau e encantamento
_TABELA = {('Broadsword', g, e): 1000 * g + 100 * e
           for g, e in conferidor.COMBINACOES}

_banco_real = mercado._banco
mercado.usar_banco({})

_jogo = Mercado(_TABELA)
_gravados = _com_mercado(
    _jogo, lambda: conferidor.varrer_item('Thetford', 'Broadsword'))

checar('grava as 13 combinacoes', _gravados == 13, str(_gravados))

checar('e elas estao no banco, com os precos certos',
       all(mercado.ler('Thetford', 'Broadsword', mercado.rotulo(g, e))[0]
           == 1000 * g + 100 * e for g, e in conferidor.COMBINACOES))

checar('cada preco carrega a idade',
       mercado.ler('Thetford', 'Broadsword', 'T6.0')[1] is not None)

# --- o filtro so e tocado quando o valor MUDA ------------------------------
# Sao 13 combinacoes em 4 graus e 4 encantamentos. Clicar nos dois a cada volta
# seriam 26 trocas de filtro por item; so nas mudancas, sao 17. Numa varredura
# de 121 itens a diferenca e de mais de mil dropdowns abertos a toa.
checar('nao troca filtro que ja esta no valor certo',
       len(_jogo.trocas) < 2 * len(conferidor.COMBINACOES),
       f'{len(_jogo.trocas)} trocas para {len(conferidor.COMBINACOES)} combinacoes')

# --- a tela que vai um passo atras ------------------------------------------
# ESTE E O DEFEITO QUE APARECEU NO 7.0 E NO 7.1, e ele nao e falta de espera.
#
# Ir de T6.3 para T7.0 muda OS DOIS filtros. Entre uma troca e outra a tela passa
# por T6.0 - um TERCEIRO preco, que nao e o da combinacao anterior e por isso
# escapa da regra "nao aceite o valor de antes". T6.0 era gravado como T7.0, e
# a combinacao seguinte herdava a base errada: por isso o 7.1 saia junto.


class TelaAtrasada(Mercado):
    """O jogo com a lista sempre um redesenho atras do filtro.

    Modela o pior caso real: cada troca de filtro entra numa fila, e quem le
    logo depois pega o estado ANTERIOR. So insistir por um numero diferente do
    que estava comprovadamente na tela desfaz o atraso."""

    def __init__(self, tabela=None):
        super().__init__(tabela)
        self.fila = [(None, None, None)]
        self.serviu_atrasado = 0

    def grau_para(self, valor):
        super().grau_para(valor)
        self.fila.append((self.item, self.grau, self.ench))
        return True

    def ench_para(self, valor):
        super().ench_para(valor)
        self.fila.append((self.item, self.grau, self.ench))
        return True

    def numero(self, regiao):
        """Uma olhada so. Devolve o que a tela mostra AGORA - que e o estado
        anterior enquanto a fila nao esvazia - e avanca um passo.

        Separar isto do ler() e o que torna o teste honesto: o comum.ler_numero
        de verdade nao insiste, e o ler_numero_novo insiste comparando. Fundir os
        dois no mesmo mentiroso escondia justamente o passo em que o defeito
        acontecia."""

        estado = self.fila[0]

        if len(self.fila) > 1:
            self.fila.pop(0)
            self.serviu_atrasado += 1

        return self.tabela.get(estado)

    def texto(self, regiao):

        if regiao == cd.CMP_LINHA_ITEM:
            return self.item or ''

        return ('' if self.tabela.get(self.fila[0]) is not None
                else 'No offers found.')

    def ler(self, regiao, anterior=None):

        # cada leitura consome um passo da fila; a ultima e o estado de verdade
        for _ in range(len(self.fila)):

            estado = self.fila[0]
            valor = self.tabela.get(estado)

            if len(self.fila) > 1:
                self.fila.pop(0)
                self.serviu_atrasado += 1

            if valor != anterior:
                return valor

        return self.tabela.get((self.item, self.grau, self.ench))


mercado.usar_banco({})

_atrasado = TelaAtrasada(_TABELA)
_com_mercado(_atrasado,
             lambda: conferidor.varrer_item('Thetford', 'Broadsword'))

checar('a tela de mentira serviu mesmo valores atrasados',
       _atrasado.serviu_atrasado > 0, str(_atrasado.serviu_atrasado))

_errados = [(mercado.rotulo(g, e), mercado.ler('Thetford', 'Broadsword',
                                               mercado.rotulo(g, e))[0])
            for g, e in conferidor.COMBINACOES
            if mercado.ler('Thetford', 'Broadsword',
                           mercado.rotulo(g, e))[0] != 1000 * g + 100 * e]

checar('mesmo com a tela atrasada, nenhum preco sai defasado',
       not _errados, str(_errados))

checar('e o 7.0 - onde os dois filtros mudam - traz o preco DELE',
       mercado.ler('Thetford', 'Broadsword', 'T7.0')[0] == 7000,
       str(mercado.ler('Thetford', 'Broadsword', 'T7.0')[0]))

checar('assim como o 7.1, que herdava a base errada do 7.0',
       mercado.ler('Thetford', 'Broadsword', 'T7.1')[0] == 7100,
       str(mercado.ler('Thetford', 'Broadsword', 'T7.1')[0]))

mercado.usar_banco({})

# --- a primeira combinacao do item -----------------------------------------
# O T5.2 E A PRIMEIRA DA LISTA, e era por isso que so ele saia errado.
#
# Toda leitura se defende exigindo um numero DIFERENTE do anterior. Na primeira o
# anterior e vazio e a defesa nao existe. O bot chega ao item com os filtros em
# "todos", troca o encantamento, e a leitura intermediaria sai na primeira
# olhada: se sair antes da troca chegar na lista, ela traz o preco de TODOS OS
# GRAUS - que e o do grau mais barato, o T4.
#
# Dai a base esta errada, e o preco que chega em seguida - encantamento certo,
# grau ainda em "todos" - e diferente dela e passa como se fosse o da combinacao.
# O preco do T4.2 entrava na celula do T5.2.


class TelaAtrasadaComTodos(TelaAtrasada):
    """A tela atrasada, agora com os precos do estado "todos os graus".

    Sao eles que o bot ve enquanto o filtro de grau ainda nao pegou - e sao eles
    que entravam no lugar do preco certo."""

    def selecionar(self, item):
        ok, motivo = super().selecionar(item)
        self.fila = [(item, None, None)]
        return ok, motivo


_COM_TODOS = dict(_TABELA)
_COM_TODOS[('Broadsword', None, None)] = 4000    # todos os graus, todos os ench
_COM_TODOS[('Broadsword', None, 2)] = 4200       # todos os graus, encantamento 2

mercado.usar_banco({})

_primeira = TelaAtrasadaComTodos(_COM_TODOS)
_com_mercado(_primeira,
             lambda: conferidor.varrer_item('Thetford', 'Broadsword'))

_t52 = mercado.ler('Thetford', 'Broadsword', 'T5.2')[0]

checar('a primeira combinacao traz o preco DELA', _t52 == 5200, str(_t52))

checar('e nao o preco de "todos os graus" com o encantamento certo',
       _t52 != 4200, 'esse e o preco do T4.2, que era o que entrava ali')

checar('nem o de todos os graus e todos os encantamentos',
       _t52 != 4000, str(_t52))

checar('e as outras doze continuam certas',
       all(mercado.ler('Thetford', 'Broadsword', mercado.rotulo(g, e))[0]
           == 1000 * g + 100 * e
           for g, e in conferidor.COMBINACOES))

mercado.usar_banco({})


# --- o F11 ----------------------------------------------------------------
# A TECLA LIGAVA O SINAL E NINGUEM ESPERAVA POR ELE. O comum tinha o evento, o
# aguardar_retomada e ate a mensagem de log - e nenhum modulo consultava. O unico
# efeito de apertar F11 era uma linha dizendo que ia pausar.

checar('a varredura espera a pausa antes de cada item',
       'comum.pausado.is_set()' in open(conferidor.__file__, encoding='utf-8').read())

checar('e usa o aguardar_retomada em vez de um laco proprio',
       'aguardar_retomada' in open(conferidor.__file__, encoding='utf-8').read())

_avisos_pausa = []
comum.definir_aviso(lambda t, v, tom: _avisos_pausa.append((t, tom)))

_reais_pausa = (comum.relatar, comum.sem_foco)
comum.relatar = lambda *a, **k: None
comum.sem_foco = lambda: []

try:
    comum.pausado.clear()
    _tempo, _pode = comum.aguardar_retomada(('teste',))
finally:
    (comum.relatar, comum.sem_foco) = _reais_pausa
    comum.definir_aviso(None)

checar('sem pausa ativa, retomar e imediato e libera a sequencia',
       _pode and _tempo < 1, f'{_pode}, {_tempo:.2f}s')

# QUEM APERTA F11 ESTA OLHANDO PARA O JOGO, e a janela do programa passa a
# varredura inteira minimizada. Aviso que so vai para o log nao chega.
checar('a pausa avisa no canto, e nao so no log',
       any('PAUSADO' in t for t, _ in _avisos_pausa), str(_avisos_pausa))

checar('e a retomada tambem', any(t == 'retomando' for t, _ in _avisos_pausa),
       str(_avisos_pausa))

comum.zerar_contadores()


# --- as duas colunas numa passada so ---------------------------------------
# A varredura le a coluna de venda. A estrategia de venda - vender na hora
# casando com um pedido de compra, ou entrar na fila com uma ordem - precisa da
# de compra. Voltar depois so para pega-la custaria a varredura inteira de novo.
mercado.usar_banco({})

mercado.gravar('Caerleon Mercado Negro', 'Broadsword', 'T6.0', 100000,
               outro=64000)
mercado.gravar('Caerleon Mercado Negro', 'Broadsword', 'T6.1', 200000)

checar('o preco principal continua sendo o de sempre',
       mercado.ler('Caerleon Mercado Negro', 'Broadsword', 'T6.0')[0] == 100000)

checar('e a outra coluna fica guardada junto',
       mercado.ler_outro('Caerleon Mercado Negro', 'Broadsword',
                         'T6.0') == 64000)

# CAMPO AUSENTE, E NAO None GRAVADO: menor no arquivo, e quem le ja trata a
# ausencia. Ha 1.573 registros por mercado.
checar('quem nao tem a segunda coluna nao ganha campo vazio',
       mercado.ler_outro('Caerleon Mercado Negro', 'Broadsword',
                         'T6.1') is None)

checar('e o arquivo nao carrega chave a toa',
       'outro' not in mercado._banco['Caerleon Mercado Negro']['Broadsword']['T6.1'])

mercado.usar_banco({})


# --- uma fonte so para as combinacoes --------------------------------------
# A ORDEM DELAS E O QUE AGRUPA POR GRAU e faz o dropdown ser clicado o minimo
# possivel. Duas copias sao duas ordens que podem divergir sem ninguem perceber.
checar('conferidor e mercado falam da mesma lista',
       conferidor.COMBINACOES is mercado.COMBINACOES)

# a tela Itens mostra as combinacoes na ordem da tabela do catalogo
checar('e a tabela do catalogo usa os rotulos dessa mesma lista',
       list(catalogo.TABELA_PADRAO)
       == [mercado.rotulo(g, e) for g, e in mercado.COMBINACOES])

checar('sao treze, do mais fraco para o mais forte',
       len(mercado.COMBINACOES) == 13
       and mercado.COMBINACOES == sorted(mercado.COMBINACOES))

# --- o estado de UMA execucao ---------------------------------------------
# Eram cinco variaveis de modulo com tres funcoes de zeramento espalhadas. Uma
# esquecida vaza para a varredura seguinte: o contador de amostras vazando fazia
# a segunda execucao nao guardar diagnostico nenhum, em silencio.
conferidor.ATUAL.bordas_salvas = 3
conferidor.ATUAL.veio_do_menu = True
conferidor.ATUAL.item = 'Broadsword'

conferidor.ATUAL.zerar()

checar('zerar a execucao limpa tudo de uma vez',
       conferidor.ATUAL.bordas_salvas == 0
       and not conferidor.ATUAL.veio_do_menu
       and conferidor.ATUAL.item == '')

checar('e nao sobrou estado solto de execucao no modulo',
       not any(l.startswith(('_bordas_salvas', '_onde_estou', '_item_atual',
                             '_rotulo_atual', '_veio_do_menu'))
               for l in open(conferidor.__file__, encoding='utf-8')))


# --- o custo das perguntas mais repetidas ----------------------------------
# Nada aqui muda comportamento: sao as tres funcoes que a tela Itens chama a cada
# tecla, e que faziam trabalho quadratico sem precisar.

_banco_perf = mercado._banco
_cat_perf = catalogo.exportar() if hasattr(catalogo, 'exportar') else None

checar('todos() nao repete item', len(catalogo.todos())
       == len(set(catalogo.todos())))

checar('e conjunto() responde a mesma coisa',
       catalogo.conjunto() == set(catalogo.todos()))

# UM MAPA, E NAO UMA VARREDURA POR PERGUNTA. grupo_de percorre todos os grupos
# a cada chamada, e ela era feita 1.573 vezes por resumo().
_mapa = catalogo._mapa_de_grupos()

checar('o mapa de grupos concorda com grupo_de, item a item',
       all(_mapa.get(i) == catalogo.grupo_de(i) for i in catalogo.todos()),
       'se divergirem, a quantidade sai do grupo errado')

# O resumo passou a somar numa passada so; o numero tem de continuar o mesmo.
_r = catalogo.resumo()

checar('o resumo soma as unidades de todas as combinacoes',
       _r['unidades'] == sum(
           catalogo.quantidade(i, mercado.rotulo(g, e))
           for i in catalogo.todos()
           for g, e in catalogo.combinacoes_de(i)),
       str(_r['unidades']))

checar('e conta as combinacoes do mesmo jeito',
       _r['combinacoes'] == sum(len(catalogo.combinacoes_de(i))
                                for i in catalogo.todos()))

# A tabela de rotulos e um atalho, nao uma segunda verdade.
checar('a conversao de rotulo bate com a do mercado',
       all(catalogo._PARTES[r] == mercado.partes(r)
           for r in catalogo._PARTES))

mercado.usar_banco(_banco_perf)


# --- a copia do que vai ser apagado ----------------------------------------
# "APAGAR ANTES DE VARRER" E O PADRAO, e apagar acontece no primeiro segundo. Um
# F12 no item cinco deixava o mercado com cinco itens novos e cento e dezesseis
# perdidos - e os ajustes prometiam um backup que nao existia.

import os as _os2

_arquivo_copia = mercado.ARQUIVO_ANTERIOR
mercado.ARQUIVO_ANTERIOR = _os2.path.join(
    _os2.path.dirname(_os2.path.abspath(mercado.__file__)), '_copia_de_teste.json')

try:
    if _os2.path.exists(mercado.ARQUIVO_ANTERIOR):
        _os2.remove(mercado.ARQUIVO_ANTERIOR)

    mercado.usar_banco({})
    mercado.gravar('Thetford', 'Broadsword', 'T6.0', 6000)
    mercado.gravar('Thetford', 'Broadsword', 'T6.1', 6100)

    _tinha = mercado.quantidade('Thetford')
    _saiu = mercado.apagar_mercado('Thetford')

    checar('apagar devolve quantos precos sairam', _saiu == _tinha == 2,
           f'{_saiu} de {_tinha}')

    checar('e o mercado fica mesmo vazio',
           mercado.quantidade('Thetford') == 0)

    checar('mas ha copia do que foi apagado',
           mercado.tem_copia('Thetford'))

    _voltaram = mercado.restaurar_copia('Thetford')

    checar('e ela traz os precos de volta', _voltaram == 2, str(_voltaram))

    checar('com os valores certos',
           mercado.ler('Thetford', 'Broadsword', 'T6.0')[0] == 6000
           and mercado.ler('Thetford', 'Broadsword', 'T6.1')[0] == 6100)

    # A COPIA NAO PODE DERRUBAR A VARREDURA. Se o disco recusar, o que se perde e
    # a rede - nao a coleta que estava para comecar.
    mercado.ARQUIVO_ANTERIOR = _os2.path.join('Z:', 'nao', 'existe', 'x.json')
    mercado.usar_banco({})
    mercado.gravar('Martlock', 'Claymore', 'T6.0', 1000)

    checar('copia que falha nao levanta excecao',
           mercado.apagar_mercado('Martlock') == 1)

    checar('e fica contada, para o resumo mostrar',
           comum.contador('copia_de_precos_falhou') == 1,
           str(comum.contador('copia_de_precos_falhou')))

finally:
    for _p in (mercado.ARQUIVO_ANTERIOR,
               _os2.path.join(_os2.path.dirname(_os2.path.abspath(mercado.__file__)),
                              '_copia_de_teste.json')):
        try:
            _os2.remove(_p)
        except OSError:
            pass
    mercado.ARQUIVO_ANTERIOR = _arquivo_copia
    mercado.usar_banco({})
    comum.zerar_contadores()


# --- a repescagem e a auditoria no mercado certo ----------------------------
# ELAS CHAMAVAM A LEITURA DA CIDADE DIRETO. Com repescar e amostras ligados por
# padrao, toda varredura do Mercado Negro terminava clicando na barra de cima da
# cidade - que aquela tela nao usa - e lendo a coluna de compra em vez da de
# venda. O laco de leitura tinha tres copias, e essa era a que ficou para tras
# em todas as correcoes.


class TelaDeMentira:
    """Uma tela qualquer, so para ver por onde a leitura passou."""

    def __init__(self, tabela):
        self.tabela = tabela
        self.regiao = (0, 0, 1, 1)
        self.abertos = []
        self.fechou = 0
        self.item = None
        self.g = None
        self.e = None

    def abrir(self, item):
        self.item = item
        self.abertos.append(item)
        return True, ''

    def fechar(self):
        self.fechou += 1

    def base(self):
        return self.tabela.get((self.item, self.g, self.e))

    def ler(self, anterior):
        return self.tabela.get((self.item, self.g, self.e))

    def vazio(self):
        return True

    def outro_preco(self):
        return None

    def encantamento(self, ench):
        self.e = ench

    def grau(self, item, grau, ench):
        self.g = grau
        return True

mercado.usar_banco({})

_outra = TelaDeMentira({('Broadsword', g, e): 1000 * g + 100 * e
                        for g, e in conferidor.COMBINACOES})

_reais_tela = (comum.jogo_em_foco, comum.sem_foco, comum.relatar,
               comum.progresso, comum.clicar)
comum.jogo_em_foco = lambda: True
comum.sem_foco = lambda: []
comum.relatar = lambda *a, **k: None
comum.progresso = lambda *a, **k: None
comum.clicar = lambda p, espera=None: None

try:
    conferidor.varrer_item('Caerleon Mercado Negro', 'Broadsword', None, [],
                           _outra)
    # tira uma combinacao do banco para a repescagem ter o que buscar
    mercado.usar_banco({k: v for k, v in mercado._banco.items()})
    _antes_abertos = len(_outra.abertos)
    conferidor.repescar('Caerleon Mercado Negro', ['Broadsword'], None,
                        tela=_outra)
    conferidor.auditar('Caerleon Mercado Negro', ['Broadsword'], 3, None,
                       tela=_outra)
finally:
    (comum.jogo_em_foco, comum.sem_foco, comum.relatar,
     comum.progresso, comum.clicar) = _reais_tela
    comum.zerar_contadores()

checar('a auditoria abre o item pela tela que recebeu',
       len(_outra.abertos) > _antes_abertos, str(_outra.abertos))

checar('e nao sobra nenhuma chamada ao menu da cidade dentro dela',
       'menu.selecionar' not in
       open(conferidor.__file__, encoding='utf-8').read()
       .split('def auditar')[1].split('def falta_conferir')[0])

checar('nem ao filtro da barra de cima',
       'filtros.' not in open(conferidor.__file__, encoding='utf-8').read()
       .split('def auditar')[1].split('def falta_conferir')[0])

checar('a repescagem tambem passa a tela adiante',
       'tela=tela' in open(conferidor.__file__, encoding='utf-8').read()
       .split('if repescar_depois')[1][:200])

mercado.usar_banco({})


# --- a tela que nao trocou ------------------------------------------------
# ESTA ERA A FUGA POR ONDE O PRECO ERRADO ENTRAVA. Gastas as cinco tentativas, o
# ler_numero_novo devolvia o numero mesmo ele continuando IGUAL ao anterior -
# isto e, mesmo com a evidencia de que a tela nunca mudou.
#
# Foi o que gravou o preco do T4.2 na celula do T5.2: a troca de grau nao chegava
# na lista dentro do tempo de insistencia, e o programa preferia entregar o que
# estava na tela a admitir que nao viu.

_teimoso = []
_real_ler = comum.ler_numero
comum.ler_numero = lambda regiao: 42000

try:
    _r = comum.ler_numero_novo((0, 0, 1, 1), 42000)
    _contado = comum.contador('tela_nao_trocou')
finally:
    comum.ler_numero = _real_ler

checar('valor que nunca muda nao e entregue como leitura',
       _r is None, str(_r))

checar('e a desistencia fica contada, para o resumo mostrar',
       _contado == 1, str(_contado))

comum.zerar_contadores()

# O caso legitimo continua passando na primeira: valor diferente, sem espera.
comum.ler_numero = lambda regiao: 43000
try:
    _r = comum.ler_numero_novo((0, 0, 1, 1), 42000)
finally:
    comum.ler_numero = _real_ler

checar('valor novo sai na hora, sem insistir', _r == 43000, str(_r))

comum.zerar_contadores()

# E VAZIO NAO PODE ZERAR A GUARDA. Com anterior=None a combinacao seguinte
# aceitaria qualquer coisa que estivesse na tela - uma falha viraria duas.
_jogo_falho = Mercado(dict(_TABELA))
del _jogo_falho.tabela[('Broadsword', 5, 2)]

mercado.usar_banco({})
_com_mercado(_jogo_falho,
             lambda: conferidor.varrer_item('Thetford', 'Broadsword'))

checar('a combinacao que falhou fica sem preco',
       mercado.ler('Thetford', 'Broadsword', 'T5.2')[0] is None)

checar('e a seguinte continua saindo certa',
       mercado.ler('Thetford', 'Broadsword', 'T5.3')[0] == 5300,
       str(mercado.ler('Thetford', 'Broadsword', 'T5.3')[0]))

mercado.usar_banco({})


# --- a tela que diz que nao ha oferta nenhuma -------------------------------
# Quando o filtro nao casa com nada, o jogo troca a lista por um quadro escrito
# "No offers found.". Isso e a RESPOSTA, e chega no primeiro quadro. Sem le-la, a
# unica evidencia era o preco vir vazio - mesmo sintoma de tela lenta - e o bot
# gastava as cinco releituras com espera crescente para concluir o que ja estava
# escrito na tela.


class ListaVazia(Mercado):
    """O jogo sem oferta nenhuma para o filtro atual."""

    def __init__(self):
        super().__init__({})
        self.insistencias = 0

    def ler(self, regiao, anterior=None):
        self.insistencias += 1
        return None


_vazio = ListaVazia()
_vazio.item = 'Broadsword'

# o contador e lido DE DENTRO: _com_mercado zera os contadores ao sair
_r, _contado = _com_mercado(
    _vazio, lambda: (conferidor.ler_combinacao(1000),
                     comum.contador('sem_oferta_no_livro')))

checar('lista vazia devolve vazio', _r is None, str(_r))

checar('e SEM gastar as releituras de tela lenta',
       _vazio.insistencias == 0, f'{_vazio.insistencias} insistencias')

checar('contando de que foi o mercado que respondeu, e nao o OCR que falhou',
       _contado == 1, str(_contado))

# E o contrario tem de continuar valendo: sem o quadro na tela, um preco que nao
# veio ainda e tela lenta, e insistir e a coisa certa a fazer.
_lento = ListaVazia()
_lento.item = 'Broadsword'
_lento.texto = lambda regiao: ''

_com_mercado(_lento, lambda: conferidor.ler_combinacao(1000))

checar('sem o quadro, continua insistindo como antes',
       _lento.insistencias == 1, str(_lento.insistencias))

comum.zerar_contadores()


# --- os recortes que o BOT tirou -------------------------------------------
# Tres capturas de uma varredura de verdade, guardadas em testes/amostras. Nao
# sao desenhos meus: e a fonte do jogo, o fundo do jogo e o enquadramento que a
# coordenada produzia.
#
# Elas provam o defeito e a causa. O "5" de 540.000 raspado em 2,5 px e lido como
# 9 - o numero entra no banco como 940.000, com confianca 79, sem nada na tela
# denunciando. Era isto que aparecia como "le 5 como 9" e "le 599.999 como
# 399.999": nunca foi o OCR, era a borda esquerda da regiao alguns pixels a
# direita de onde os numeros comecam.

import glob as _glob
import os as _os
from PIL import Image as _Img2, ImageOps as _Ops2

_PASTA_AMOSTRAS = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                                'amostras')

_amostras = sorted(_glob.glob(_os.path.join(_PASTA_AMOSTRAS, '*borda.png')))

# A suite nao pode ficar verde porque as amostras sumiram - foi assim que um
# teste de planilha passou meses sem conferir nada.
checar('as tres amostras de tela estao no lugar',
       len(_amostras) == 3, f'{len(_amostras)} em {_PASTA_AMOSTRAS}')


def _falta_do_primeiro_digito(caminho):
    """Quantos pixels de tela faltam do primeiro digito daquele recorte."""

    g = _Ops2.autocontrast(_Img2.open(caminho).convert('L'))
    largura, altura = g.size
    px = g.load()

    com_tinta = [any(px[x, y] < comum.LIMIAR_TINTA for y in range(altura))
                 for x in range(largura)]

    grupos, x = [], 0

    while x < largura:
        if com_tinta[x]:
            inicio = x
            while x < largura and com_tinta[x]:
                x += 1
            grupos.append(x - inicio)
        else:
            x += 1

    digitos = [g for g in grupos if g > 20]        # virgulas ficam de fora

    return (max(digitos[1:]) - digitos[0]) / 6     # o PNG e salvo em 6x


_faltas = [_falta_do_primeiro_digito(a) for a in _amostras]

checar('em todas elas o primeiro digito esta raspado',
       all(f > 1 for f in _faltas), str([round(f, 1) for f in _faltas]))

checar('e o pior caso perde 2,5 px',
       2 < max(_faltas) < 3, f'{max(_faltas):.1f} px')

# A CORRECAO E A COORDENADA, e nao mais uma variante de OCR. A folga tem de
# cobrir o pior caso medido com sobra.
_folga = 1070 - cd.PRECO_COMPRA[0]

checar('a borda esquerda foi movida para cobrir isso',
       _folga > max(_faltas) + 1, f'{_folga} px de folga para {max(_faltas):.1f}')

checar('sem invadir onde fica o icone da moeda',
       cd.PRECO_COMPRA[0] >= 1060, str(cd.PRECO_COMPRA))

# E o detector precisa acusar os tres, senao o aviso em execucao nao serve.
checar('e o aviso de borda dispara nos tres recortes',
       all(comum.tinta_na_borda(_Img2.open(a).convert('RGB'))
           for a in _amostras))


# --- algo colado na borda esquerda do recorte do preco ---------------------
# A celula do preco na lista e "moeda + numero", e uma lasca do icone dentro do
# recorte estraga a leitura: com o psm 7 o tesseract le a faixa como UMA LINHA DE
# TEXTO, e como so digitos sao permitidos a lasca e forcada a virar um digito.
# Foi assim que 599.999 virou 399.999.
#
# CORTAR A LASCA PARECIA A CORRECAO E NAO ERA. Ela partia de "recorte bem
# enquadrado tem fundo na primeira coluna", e na tela do jogo os digitos ENCOSTAM
# na borda esquerda: o corte comia o primeiro digito da maioria dos precos.
# Trocou um numero errado e raro por um numero errado, MENOR e frequente - e
# menor e pior, porque passa pela barreira de plausibilidade e vira compra.

from PIL import Image as _Img, ImageDraw as _Dr


def _celula(encostado):
    """A celula do preco. <encostado> poe um traco colado na borda esquerda."""

    img = _Img.new('RGB', (100, 38), (233, 208, 170))
    d = _Dr.Draw(img)

    if encostado:
        d.ellipse([-7, 13, 6, 26], fill=(214, 170, 66), outline=(120, 88, 30))

    d.rectangle([16, 14, 24, 26], fill=(60, 40, 20))
    d.rectangle([30, 14, 38, 26], fill=(60, 40, 20))

    return img


checar('borda limpa nao levanta nada',
       not comum.tinta_na_borda(_celula(False)))

checar('e traco encostado na borda e percebido',
       comum.tinta_na_borda(_celula(True)))

# O QUE ELE FAZ E AVISAR, NAO CORTAR. Daqui nao da para saber se o que encosta na
# borda e o icone ou o primeiro digito, e fingir que da foi exatamente o erro.
_antes = comum._preparar(_celula(True)).size
_depois = comum._preparar(_celula(False)).size

checar('a imagem entregue ao OCR tem o mesmo tamanho nos dois casos',
       _antes == _depois, f'{_antes} contra {_depois}')

# E QUANDO ACONTECE, O BOT GUARDA A IMAGEM. Uma leitura errada relatada de
# memoria - "leu 399.999 em vez de 599.999" - nao diz se o que encosta na borda e
# o icone ou o digito, e a coordenada se move para lados OPOSTOS nos dois casos.
_salvas = []
_real_salvar = comum.salvar_diagnostico
comum.salvar_diagnostico = lambda pasta, nome, **kw: _salvas.append(nome)

conferidor.zerar_amostras()

for _ in range(10):
    conferidor._amostrar_borda('Thetford', 'Broadsword', 'T7.1', 399999)

comum.salvar_diagnostico = _real_salvar

checar('a borda suja vira PNG, com item e combinacao no nome',
       _salvas and 'Broadsword' in _salvas[0] and 'T7.1' in _salvas[0],
       str(_salvas[:1]))

# Tres bastam para ver o enquadramento; uma por combinacao encheria a pasta com
# 1.573 copias da mesma imagem.
checar('mas nao mais que tres por execucao',
       len(_salvas) == conferidor.AMOSTRAS_DE_BORDA, str(len(_salvas)))

conferidor.zerar_amostras()


checar('nenhum pixel e descartado por causa da borda',
       'crop' not in open(comum.__file__, encoding='utf-8').read()
       .split('def tinta_na_borda')[1].split('def _preparar')[0])


# --- o cursor nao pode ficar em cima do numero -----------------------------
# O jogo desenha o proprio ponteiro, e a captura de tela o pega junto. A opcao
# "encantamento 3" fica logo acima da primeira linha da lista, e a seta desce o
# bastante para cobrir os primeiros digitos: 540.000 foi lido como 40.000.

_x1, _y1, _x2, _y2 = cd.PRECO_COMPRA
_op = cd.ench_compra(3)

checar('a opcao do encantamento 3 cai mesmo em cima do preco',
       _x1 <= _op['x'] <= _x2 and abs(_op['y'] - _y1) < 25,
       f'opcao {_op}, preco {cd.PRECO_COMPRA}')

_d = cd.MOUSE_DESCANSO

checar('e o ponto de descanso fica FORA da regiao do preco',
       not (_x1 <= _d['x'] <= _x2 and _y1 <= _d['y'] <= _y2), str(_d))

checar('bem acima da lista, longe de qualquer balao de item',
       _d['y'] < _y1 - 100, f"y={_d['y']}, lista comeca em {_y1}")


checar('e nao em cima de outro filtro da barra',
       not any(abs(_d['x'] - b['x']) < 70 and abs(_d['y'] - b['y']) < 15
               for b in (cd.CMP_BUSCA, cd.CMP_RESET, cd.CMP_BARRA_TIER,
                         cd.CMP_BARRA_ENCH, cd.CMP_LIMPAR_FILTROS)),
       str(_d))


class Ponteiro:
    """O ponteiro e a lista, na ordem em que o jogo os ve."""

    def __init__(self, clique_fecha=True):
        self.onde = None
        self.clique_fecha = clique_fecha
        self.acoes = []

    def clicar(self, pos, espera=None):
        self.onde = (pos['x'], pos['y'])
        self.acoes.append(('clique', self.onde))

    def apontar(self, pos):
        self.onde = (pos['x'], pos['y'])
        self.acoes.append(('mover', self.onde))

    def esperar_mudanca(self, regiao, antes, limite):
        # a segunda chamada e a espera da lista FECHAR depois do clique
        return self.clique_fecha or len(
            [a for a in self.acoes if a[0] == 'clique']) < 2


def _com_ponteiro(pt, acao):

    reais = (comum.clicar, comum.apontar, comum.assinatura,
             comum.esperar_mudanca, comum.esperar_estavel)

    comum.clicar = pt.clicar
    comum.apontar = pt.apontar
    comum.assinatura = lambda r: b''
    comum.esperar_mudanca = pt.esperar_mudanca
    comum.esperar_estavel = lambda *a, **k: True

    try:
        return acao()
    finally:
        (comum.clicar, comum.apontar, comum.assinatura,
         comum.esperar_mudanca, comum.esperar_estavel) = reais


_pt = Ponteiro()
_com_ponteiro(_pt, lambda: filtros.escolher(cd.CMP_BARRA_ENCH,
                                            cd.ench_compra(3)))
comum.zerar_contadores()

checar('toda troca de filtro leva o cursor para la',
       _pt.onde == (_d['x'], _d['y']), str(_pt.onde))

# O JOGO NAO USA A POSICAO DO PONTEIRO NO INSTANTE DO CLIQUE - ele le a posicao
# atual no quadro seguinte e resolve o clique ali. Tirar o cursor logo depois de
# soltar o botao fazia a opcao nunca ser selecionada: o clique caia onde o cursor
# tinha acabado de chegar, e o bot ficava parado em frente ao menu aberto.
_ordem = [a[0] for a in _pt.acoes]

checar('o cursor so sai depois do clique na opcao',
       _ordem[-1] == 'mover' and _ordem[-2] == 'clique', str(_pt.acoes))

# E a lista fechando e a prova de que o clique chegou. Sem ela, o cursor fica.
_pt = Ponteiro(clique_fecha=False)
_com_ponteiro(_pt, lambda: filtros.escolher(cd.CMP_BARRA_ENCH,
                                            cd.ench_compra(3)))

checar('opcao que nao fez a lista fechar vira contador',
       comum.contador('opcao_sem_efeito') == 1,
       str(comum.contador('opcao_sem_efeito')))

comum.zerar_contadores()


checar('a ordem e do mais fraco para o mais forte',
       conferidor.COMBINACOES == sorted(conferidor.COMBINACOES),
       str(conferidor.COMBINACOES[:3]))

# --- combinacao sem oferta nao e falha -------------------------------------
# Um item que ninguem esta vendendo no grau 8 e informacao legitima. Ele nao
# entra no banco, e a calculadora depois separa "nao tem preco" de "preco ruim".
mercado.usar_banco({})

_parcial = dict(_TABELA)
del _parcial[('Broadsword', 8, 2)]
del _parcial[('Broadsword', 8, 1)]

_jogo = Mercado(_parcial)
_gravados = _com_mercado(
    _jogo, lambda: conferidor.varrer_item('Thetford', 'Broadsword'))

checar('as sem oferta simplesmente nao entram', _gravados == 11, str(_gravados))

checar('e o que entrou continua certo',
       mercado.ler('Thetford', 'Broadsword', 'T8.0')[0] == 8000)

checar('e o que faltou continua faltando',
       mercado.ler('Thetford', 'Broadsword', 'T8.2')[0] is None)

# --- como o item chega na tela: busca por padrao, menu na excecao ----------
# DIGITAR O NOME E UM CLIQUE E UMA DIGITACAO; descer o menu em cascata sao tres
# passadas de mouse, cada uma com leitura de rotulo para confirmar que o ponteiro
# chegou onde devia. A busca so nao serve para os 18 nomes que cabem dentro de
# outro - "Cursed Staff" traz o "Great Cursed Staff" junto - porque ali o
# primeiro da lista pode ser o item errado, e ler o preco dele seria gravar o
# preco de outra coisa sem nada na tela denunciando.
mercado.usar_banco({})

_jogo = Mercado(_TABELA)
_com_mercado(_jogo, lambda: conferidor.varrer_item('Thetford', 'Broadsword'))

checar('item de nome sem conflito vai pela BUSCA',
       _jogo.buscados == ['Broadsword'] and not _jogo.pelo_menu,
       f'buscados={_jogo.buscados}, menu={_jogo.pelo_menu}')

_jogo = Mercado({('Cursed Staff', g, e): 1000 * g + 100 * e
                 for g, e in conferidor.COMBINACOES})
_com_mercado(_jogo, lambda: conferidor.varrer_item('Thetford', 'Cursed Staff'))

checar('e o de nome ambiguo vai SO pelo menu',
       _jogo.pelo_menu == ['Cursed Staff'] and not _jogo.buscados,
       f'buscados={_jogo.buscados}, menu={_jogo.pelo_menu}')

# O menu desce ate o item, entao a lista ja fica no que se quer. Digitar por cima
# seria uma digitacao e uma espera de lista para nao mudar nada.
checar('um caminho por item, nunca os dois',
       not (_jogo.pelo_menu and _jogo.buscados))

checar('sao 18 assim entre os 252, o resto vai pela busca',
       len(categorias.ambiguos()) == 18, str(len(categorias.ambiguos())))

# --- o "Travertine": a base tirada no meio do redesenho ---------------------
# Zerar a busca faz a lista voltar ao mercado inteiro, e o primeiro item dele em
# ordem alfabetica e uma pedra qualquer. Esse redesenho leva tempo.
#
# Fotografando a lista NO MEIO dele e digitando em seguida, a "mudanca" detectada
# e o redesenho do reset terminando - nao a busca filtrando - e a espera termina
# com a lista ainda sem filtro. O bot lia o preco da pedra achando que era o da
# espada, e o log dizia: a busca trouxe "Travertine".

_ordem = []
_reais_busca = (comum.clicar, comum.digitar, comum.assinatura,
                comum.esperar_mudanca, comum.esperar_estavel)

comum.clicar = lambda p, espera=None: _ordem.append('clique')
comum.digitar = lambda texto: _ordem.append('digita')
comum.assinatura = lambda r: _ordem.append('foto') or b''
comum.esperar_estavel = lambda *a, **k: _ordem.append('espera parar') or True
comum.esperar_mudanca = lambda *a, **k: _ordem.append('espera mudar') or True

try:
    conferidor.buscar('Broadsword')
finally:
    (comum.clicar, comum.digitar, comum.assinatura,
     comum.esperar_mudanca, comum.esperar_estavel) = _reais_busca
    comum.zerar_contadores()

checar('a lista e confirmada PARADA antes da foto que serve de base',
       _ordem.index('espera parar') < _ordem.index('foto'), str(_ordem))

checar('a foto vem antes de digitar', _ordem.index('foto')
       < _ordem.index('digita'), str(_ordem))

checar('e so depois de digitar se espera a lista mudar',
       _ordem.index('digita') < _ordem.index('espera mudar'), str(_ordem))

# E ELA TEM MAIS TEMPO QUE UMA TROCA DE FILTRO. Trocar um filtro redesenha as
# linhas; digitar um nome refaz a consulta e a lista volta do servidor.
checar('a busca espera mais que a troca de filtro',
       conferidor.ESPERA_BUSCA > filtros.ESPERA_PRECO,
       f'{conferidor.ESPERA_BUSCA} contra {filtros.ESPERA_PRECO}')


# --- a busca que traz outro item --------------------------------------------
# PRECO MUDANDO NAO PROVA QUAL ITEM ESTA NA TELA, e por isso a conferencia do
# nome existe. Mas ela AVISA, e nao pula: depende de um OCR num recorte que
# nunca foi conferido no jogo, e um recorte fora do lugar reprovaria todos os
# itens - a varredura inteira voltaria vazia por causa da verificacao, e nao de
# um defeito de leitura.
mercado.usar_banco({})

_enganado = Mercado({('Claymore', g, e): 1000 * g + 100 * e
                     for g, e in conferidor.COMBINACOES})
_enganado.digitar = lambda texto: _enganado.buscados.append(texto)
_enganado.item = 'Claymore'      # a lista nao reage ao que foi digitado

_contado = _com_mercado(
    _enganado,
    lambda: (conferidor.varrer_item('Thetford', 'Broadsword'),
             comum.contador('item_diferente_na_lista'))[1])

checar('nome que nao bate com o procurado vira contador', _contado == 1,
       str(_contado))

checar('e a varredura segue assim mesmo, que e o que foi pedido',
       _enganado.trocas, 'os filtros continuam sendo percorridos')

checar('sem chamar o menu para um item que nao tem conflito de nome',
       not _enganado.pelo_menu, str(_enganado.pelo_menu))

mercado.usar_banco({})

# --- item que o menu nao alcanca -------------------------------------------
mercado.usar_banco({})

_jogo = Mercado({('Cursed Staff', g, e): 1000 * g + 100 * e
                 for g, e in conferidor.COMBINACOES})
_jogo.itens_sem_menu = {'Cursed Staff'}
_relatos = []
_gravados = _com_mercado(
    _jogo,
    lambda: conferidor.varrer_item('Thetford', 'Cursed Staff', None, _relatos))

checar('item sem menu nao grava nada', _gravados == 0)

checar('e nao mexe em filtro nenhum', not _jogo.trocas, str(_jogo.trocas))

checar('e diz por que no relato',
       _relatos and 'PULADO' in _relatos[0], str(_relatos))

# --- a varredura inteira ----------------------------------------------------
mercado.usar_banco({})

_TRES = {}
for _it in ('Broadsword', 'Claymore', 'Dual Swords'):
    for _g, _e in conferidor.COMBINACOES:
        _TRES[(_it, _g, _e)] = 1000 * _g + 100 * _e

_jogo = Mercado(_TRES)
_salvo = []
_salvar_real = mercado.salvar
mercado.salvar = lambda: (_salvo.append(1), (True, ''))[1]

try:
    _res = _com_mercado(_jogo, lambda: conferidor.varrer(
        'Thetford', ['Broadsword', 'Claymore', 'Dual Swords'], salvar_a_cada=2))
finally:
    mercado.salvar = _salvar_real

checar('varre os tres itens', _res['itens'] == 3, str(_res))

checar('e grava 39 precos', _res['precos'] == 39, str(_res['precos']))

# Tres itens, mais UMA no comeco da execucao: o jogo guarda busca e filtros
# entre sessoes, e o que sobrou da ultima vez que a pessoa mexeu ali so pode ser
# desfeito, nunca adivinhado.
checar('zera os filtros entre um item e outro, e uma vez no comeco',
       _jogo.limpezas == 4, str(_jogo.limpezas))

# NO MERCADO NEGRO, NAO. Os filtros da barra de cima nao sao usados naquela tela
# - os dropdowns que valem ficam dentro do painel de Pedido de Venda - e o botao
# de resetar da direita nao tem efeito sobre leitura nenhuma ali.
_jogo_bm = Mercado(_TABELA)
_com_mercado(_jogo_bm,
             lambda: conferidor.limpar_a_tela(mercado.MERCADO_NEGRO))

checar('no Mercado Negro o arranque nao toca no botao de resetar',
       _jogo_bm.limpezas == 0, str(_jogo_bm.limpezas))

_jogo_cidade = Mercado(_TABELA)
_com_mercado(_jogo_cidade, lambda: conferidor.limpar_a_tela('Thetford'))

checar('mas na cidade continua tocando', _jogo_cidade.limpezas == 1,
       str(_jogo_cidade.limpezas))

# grava no meio do caminho: um F12 aos 60 itens nao pode jogar fora os 60
checar('salva no disco durante a varredura, e nao so no fim', len(_salvo) >= 2,
       f'{len(_salvo)} gravacoes')

# --- mercado que nao existe -------------------------------------------------
# Um preco de Martlock guardado como se fosse de Thetford estraga a conta das
# duas cidades ao mesmo tempo, e nada na tela denunciaria.
_res = _com_mercado(_jogo, lambda: conferidor.varrer('Atlantida', ['Broadsword']))

checar('recusa mercado desconhecido', 'erro' in _res, str(_res))

checar('e diz qual era o nome errado', 'Atlantida' in _res['erro'], _res['erro'])

# --- retomar de onde parou --------------------------------------------------
mercado.usar_banco({})

for _g, _e in conferidor.COMBINACOES:
    mercado.gravar('Thetford', 'Broadsword', mercado.rotulo(_g, _e), 1000)

_faltam = conferidor.falta_conferir(['Broadsword', 'Claymore'], 'Thetford')

checar('quem ja tem preco recente nao precisa ser relido',
       _faltam == ['Claymore'], str(_faltam))

# preco velho conta como se nao existisse
mercado.usar_banco({})
mercado.gravar('Thetford', 'Broadsword', 'T6.0', 1000,
               time.time() - 48 * 3600)

# O CATALOGO DECIDE AS COMBINACOES, E ELAS MUDAM POR ITEM: um item com os graus
# 8 zerados tem dez, o vizinho tem treze. Por isso o conferidor aceita uma funcao
# no lugar de uma lista - com uma lista so, ele varreria o que voce ja disse que
# nao quer.
_banco_antes_cat = mercado._banco
mercado.usar_banco({})

_jogo = Mercado(_TABELA)
_com_mercado(_jogo, lambda: conferidor.varrer_item(
    'Thetford', 'Broadsword',
    combinacoes=lambda _i: [(6, 0), (6, 1)]))

checar('o conferidor aceita uma funcao por item',
       len(mercado.combinacoes('Thetford', 'Broadsword')) == 2,
       str(mercado.combinacoes('Thetford', 'Broadsword')))

mercado.usar_banco({})
_jogo = Mercado(_TABELA)
_com_mercado(_jogo, lambda: conferidor.varrer_item(
    'Thetford', 'Broadsword', combinacoes=[(7, 0)]))

checar('e continua aceitando uma lista fixa',
       mercado.combinacoes('Thetford', 'Broadsword') == ['T7.0'],
       str(mercado.combinacoes('Thetford', 'Broadsword')))

mercado.usar_banco(_banco_antes_cat)

checar('preco velho nao dispensa a releitura',
       conferidor.falta_conferir(['Broadsword'], 'Thetford') == ['Broadsword'])

mercado.usar_banco(_banco_real)


# ============================================================
grupo('o catalogo: o que negociar e quanto de cada')

# E o unico modulo que responde "o que fazer" em vez de "como fazer". O
# Conferidor pergunta a ele o que varrer, a calculadora quantas unidades de cada
# linha, a compra onde parar.

catalogo.zerar()

checar('a tabela padrao e a que ja foi afinada no bot de hoje',
       catalogo.TABELA_PADRAO['T6.0'] == 20
       and catalogo.TABELA_PADRAO['T6.2'] == 8
       and catalogo.TABELA_PADRAO['T8.2'] == 1,
       str(catalogo.TABELA_PADRAO))

checar('e cobre as 13 combinacoes', len(catalogo.TABELA_PADRAO) == 13)

# --- escolher itens ---------------------------------------------------------
checar('acrescenta um item', catalogo.acrescentar('Broadsword', 'Melee')[0])

checar('e ele fica no grupo pedido',
       catalogo.itens_de('Melee') == ['Broadsword'])

checar('o mesmo item nao entra duas vezes',
       not catalogo.acrescentar('Broadsword', 'Melee')[0])

# UM ITEM QUE O BOT NAO CONSEGUE SELECIONAR NA TELA nao e uma escolha ruim, e uma
# escolha impossivel - e descobrir isso na metade de uma varredura, item por
# item, e o pior momento possivel.
_ok, _motivo = catalogo.acrescentar('Espada de Teste')

checar('recusa item sem caminho de menu', not _ok)

checar('e diz por que', 'caminho de menu' in _motivo, _motivo)

catalogo.acrescentar('Claymore', 'Melee')
catalogo.acrescentar('Cursed Staff', 'Magia')

checar('grupos separam os itens',
       catalogo.grupos() == ['Magia', 'Melee'], str(catalogo.grupos()))

checar('e o catalogo inteiro tem os tres', len(catalogo.todos()) == 3)

checar('da para saber em que grupo um item esta',
       catalogo.grupo_de('Cursed Staff') == 'Magia')

checar('e trocar de grupo',
       catalogo.mover('Cursed Staff', 'Melee')
       and catalogo.grupo_de('Cursed Staff') == 'Melee')

# --- apagar grupo sem perder os itens sem querer ---------------------------
catalogo.criar_grupo('Temporario')
catalogo.mover('Cursed Staff', 'Temporario')

checar('apagar grupo pode levar os itens para outro',
       catalogo.apagar_grupo('Temporario', mover_para='Melee')
       and catalogo.grupo_de('Cursed Staff') == 'Melee')

checar('e apagar sem destino tira os itens do catalogo',
       catalogo.apagar_grupo('Melee') and catalogo.todos() == [])

# --- OS DOIS NIVEIS DE QUANTIDADE ------------------------------------------
# A tabela vale para todos os itens; a excecao e deste item nesta combinacao. Um
# nivel so nao dava conta: um numero por combinacao ignora que um item liquido
# aguenta vinte unidades e um travado nao aguenta duas; um numero por item
# ignora que o mesmo item e barato no T5 e caro no T8.
catalogo.zerar()
catalogo.acrescentar('Broadsword', 'Melee')
catalogo.acrescentar('Claymore', 'Melee')

checar('sem excecao, vale a tabela',
       catalogo.quantidade('Claymore', 'T6.0') == 20)

catalogo.definir('Broadsword', 'T6.0', 50)

checar('a excecao do item vence a tabela',
       catalogo.quantidade('Broadsword', 'T6.0') == 50)

checar('e nao contamina o vizinho',
       catalogo.quantidade('Claymore', 'T6.0') == 20)

checar('nem as outras combinacoes do mesmo item',
       catalogo.quantidade('Broadsword', 'T6.1') == 20)

checar('apagar a excecao devolve o item a tabela',
       catalogo.definir('Broadsword', 'T6.0', None)
       and catalogo.quantidade('Broadsword', 'T6.0') == 20
       and not catalogo.tem_excecao('Broadsword'))

# ZERO E UMA RESPOSTA, e nao "sem valor definido". Procurar a excecao com `or`
# trataria zero como ausencia e devolveria a tabela - comprando o que voce
# acabou de dizer que nao queria.
catalogo.definir('Broadsword', 'T8.2', 0)

checar('zero na excecao vale zero, e nao a tabela',
       catalogo.quantidade('Broadsword', 'T8.2') == 0,
       str(catalogo.quantidade('Broadsword', 'T8.2')))

checar('e a combinacao sai da varredura',
       (8, 2) not in catalogo.combinacoes_de('Broadsword'))

checar('mas continua valendo para os outros itens',
       (8, 2) in catalogo.combinacoes_de('Claymore'))

# --- mudar muitas de uma vez ------------------------------------------------
# Sem isso, ajustar treze linhas sao treze edicoes.
catalogo.definir_em_massa(['T8.0', 'T8.1', 'T8.2'], 0)

checar('o ajuste em massa vale para todos os itens',
       len(catalogo.combinacoes_de('Claymore')) == 10,
       str(len(catalogo.combinacoes_de('Claymore'))))

checar('e encurta a varredura na proporcao exata do que voce nao quer',
       all(g != 8 for g, _ in catalogo.combinacoes_de('Claymore')))

catalogo.definir_em_massa(['T8.0', 'T8.1', 'T8.2'], 3)

checar('e da para desfazer', len(catalogo.combinacoes_de('Claymore')) == 13)

# --- o encaixe com a calculadora de lucro ----------------------------------
# E aqui que o catalogo encontra a conta: para_calcular() devolve exatamente o
# que o lucro.montar() espera receber.
catalogo.zerar()
catalogo.acrescentar('Assassin Jacket', 'Couro')
catalogo.definir('Assassin Jacket', 'T6.0', 80)

_banco_antes = mercado._banco
mercado.usar_banco({})

_agora = time.time()
mercado.gravar('Thetford', 'Assassin Jacket', 'T6.0', 49871, _agora)
mercado.gravar(mercado.MERCADO_NEGRO, 'Assassin Jacket', 'T6.0', 61662, _agora,
               outro=61662)

_linhas, _resumo = lucro.montar(catalogo.para_calcular(), 'Thetford',
                                margem_minima=0.0)

checar('a lista de compras sai do catalogo mais o banco de precos',
       len(_linhas) == 1, str(len(_linhas)))

checar('e a quantidade e a que voce escolheu',
       _linhas[0]['quantidade'] == 80, str(_linhas[0]['quantidade']))

checar('com o preco de compra e de venda de cada mercado',
       _linhas[0]['compra'] == 49871 and _linhas[0]['venda'] == 61662)

mercado.usar_banco(_banco_antes)

# --- ida e volta ao disco ---------------------------------------------------
catalogo.zerar()
catalogo.acrescentar('Broadsword', 'Melee')
catalogo.definir('Broadsword', 'T6.0', 42)
catalogo.definir_tabela('T5.2', 9)

_gravou, _erro = catalogo.salvar('teste-automatico')

checar('grava no disco', _gravou, _erro)

catalogo.zerar()

checar('e depois de zerar nao sobra nada', catalogo.todos() == [])

_leu, _erro = catalogo.carregar('teste-automatico')

checar('le de volta', _leu, _erro)

checar('com os itens', catalogo.todos() == ['Broadsword'])

checar('com a excecao', catalogo.quantidade('Broadsword', 'T6.0') == 42)

checar('e com a tabela alterada', catalogo.tabela()['T5.2'] == 9)

checar('o catalogo salvo aparece na lista',
       'teste-automatico' in catalogo.salvos(), str(catalogo.salvos()))

# um catalogo que nunca existiu nasce vazio, e isso nao e erro
_leu, _erro = catalogo.carregar('nunca-existiu-mesmo')

checar('catalogo inexistente nasce vazio, sem reclamar', _leu and not _erro)

checar('e com a tabela padrao inteira',
       catalogo.tabela() == catalogo.TABELA_PADRAO)

try:
    os.remove(catalogo._caminho('teste-automatico'))
except OSError:
    pass

catalogo.zerar()


# ============================================================
grupo('o catalogo inicial vem com o programa')

# Os 121 itens em tres grupos - cada grupo e uma viagem, porque o inventario tem
# limite. Nada disso deve ser redigitado no primeiro uso.

_ok_cat, _erro_cat = catalogo.carregar('padrao')

checar('o primeiro uso abre o catalogo inicial', _ok_cat, _erro_cat)

checar('com os 121 itens', len(catalogo.todos()) == 121,
       str(len(catalogo.todos())))

checar('em tres grupos',
       catalogo.grupos() == ['Armors', 'Mage  Off Hand  Cape-Bag',
                             'Melee  Ranged'],
       str(catalogo.grupos()))

checar('com os itens de cada um',
       len(catalogo.itens_de('Armors')) == 45
       and len(catalogo.itens_de('Melee  Ranged')) == 38)

checar('todo item dele da para navegar no menu',
       all(categorias.navegavel(i) for i in catalogo.todos()))

# o inicial e dado do programa: salvar cria o seu, na pasta de dados
_inicial_antes = os.path.getmtime(catalogo.ARQUIVO_INICIAL)
catalogo.salvar()

checar('salvar grava na pasta de dados',
       os.path.exists(os.path.join(_DADOS, 'catalogo-padrao.json')))

checar('e nao mexe no catalogo inicial',
       os.path.getmtime(catalogo.ARQUIVO_INICIAL) == _inicial_antes)

# --- o tamanho do trabalho, em numero ---------------------------------------
# Isto nao e um teste de correcao, e um teste de EXPECTATIVA: se um dia esta
# conta mudar de ordem de grandeza, alguem tem que ver antes de descobrir com o
# jogo aberto.
_r = catalogo.resumo()

checar('sao ~1.573 combinacoes para varrer por mercado',
       1500 < _r['combinacoes'] < 1650, str(_r['combinacoes']))

checar('e 11.011 unidades no teto de compra',
       _r['unidades'] == 11011, str(_r['unidades']))

catalogo.zerar()


# ============================================================
grupo('comprar por ordem, sem dar N vezes tres cliques')

# Um pedido de compra casa NA HORA com toda oferta de venda naquele preco ou
# abaixo: 53 unidades num clique, em vez de 53 vezes tres. Custa 2,5% de taxa.

# --- O PRECO MAXIMO E O INVERSO EXATO DA CONTA DE LUCRO --------------------
# Um silver de erro aqui nao erra uma compra: erra todas as unidades da ordem de
# uma vez. Por isso a conferencia e por propriedade, e nao por exemplo - vale
# para qualquer preco e qualquer margem, e nao so para os que alguem lembrou.
_erros = []

for _venda in (1000, 18444, 61662, 338484, 2_500_000):
    for _margem in (0.05, 0.23, 0.5, 1.0):

        _teto = compra.preco_maximo(_venda, _margem)

        if _teto <= 0:
            continue

        # no teto ainda paga...
        if lucro.liquido(_teto, _venda) < _margem:
            _erros.append(f'{_venda}/{_margem}: {_teto} nao paga')

        # ...e um silver acima ja nao paga
        if lucro.liquido(_teto + 1, _venda) >= _margem:
            _erros.append(f'{_venda}/{_margem}: {_teto + 1} ainda paga')

checar('o teto de preco e exato ao silver, em toda faixa', not _erros,
       '; '.join(_erros[:3]))

checar('venda zero nao vira teto positivo', compra.preco_maximo(0, 0.23) == 0)

checar('margem maior aperta o teto',
       compra.preco_maximo(10000, 0.5) < compra.preco_maximo(10000, 0.23))

checar('e a taxa de ordem tambem',
       compra.preco_maximo(10000, 0.23, por_ordem=True)
       < compra.preco_maximo(10000, 0.23, por_ordem=False))

# --- o livro de ofertas de uma captura de verdade ---------------------------
# "Espada Larga do Calouro", mercado de Caerleon: 895 x1, 898 x28, 898 x14,
# 898 x1, 898 x1, 899 x8. Sao 53 unidades.
LIVRO = [(895, 1), (898, 28), (898, 14), (898, 1), (898, 1), (899, 8)]

_plano = compra.planejar(LIVRO, 1400, 0.23, 100)

checar('a ordem e dimensionada pelo livro', _plano['unidades'] == 53,
       str(_plano['unidades']))

# UMA ORDEM MAIOR DO QUE HA PARA VENDER NAO DESAPARECE: ela fica de pe no
# mercado com a sua prata presa dentro, esperando alguem vender.
checar('e nunca maior do que ha para comprar',
       _plano['unidades'] <= sum(q for _, q in LIVRO))

checar('o preco pedido cobre a oferta mais cara que ainda paga',
       _plano['preco'] == 899, str(_plano['preco']))

checar('e fica abaixo do teto', _plano['preco'] <= _plano['teto_de_preco'])

# --- o teto de quantidade do catalogo manda ---------------------------------
_plano = compra.planejar(LIVRO, 1400, 0.23, 20)

checar('nao compra mais do que voce pediu', _plano['unidades'] == 20)

checar('e conta as que ficaram para tras',
       _plano['deixadas_para_tras'] == 33, str(_plano['deixadas_para_tras']))

# --- oferta cara fica de fora ----------------------------------------------
_plano = compra.planejar([(898, 10), (99999, 50)], 1400, 0.23, 100)

checar('oferta acima do teto nao entra na ordem', _plano['unidades'] == 10)

checar('e o preco da ordem nao sobe por causa dela', _plano['preco'] == 898)

# --- quando nao vale ---------------------------------------------------------
checar('livro vazio nao vira plano',
       compra.planejar([], 1400, 0.23, 100) is None)

checar('teto de quantidade zero nao vira plano',
       compra.planejar(LIVRO, 1400, 0.23, 0) is None)

checar('nenhuma oferta abaixo do teto nao vira plano',
       compra.planejar([(5000, 10)], 1400, 0.23, 100) is None)

# --- OS DOIS CUSTOS ---------------------------------------------------------
# O jogo cobra o preco de QUEM ESTA VENDENDO, e nao o da minha ordem: pedindo 899
# e havendo ofertas a 895 e 898, paga-se 895 e 898. O meu preco e um teto.
#
# Dai os dois numeros. O "custo" e o que deve sair da conta; o "custo_maximo" e o
# que o jogo RESERVA - e e ele que aparece no Total do painel, o unico numero da
# tela que da para conferir antes de clicar em criar.
_plano = compra.planejar(LIVRO, 1400, 0.23, 100)
_soma_das_ofertas = sum(p * q for p, q in LIVRO)

checar('o custo e a soma das ofertas, oferta por oferta',
       _plano['custo'] == int(_soma_das_ofertas * (1 + lucro.TAXA_DE_ORDEM)),
       f'{_plano["custo"]} contra {_soma_das_ofertas}')

checar('o reservado usa o preco da ordem para todas',
       _plano['custo_maximo'] == int(899 * 53 * (1 + lucro.TAXA_DE_ORDEM)),
       str(_plano['custo_maximo']))

checar('e reservar nunca e menos que gastar',
       _plano['custo_maximo'] >= _plano['custo'])

checar('os dois incluem a taxa de ordem',
       _plano['custo'] > _soma_das_ofertas)

# com todas as ofertas ao mesmo preco os dois numeros se encontram
_igual = compra.planejar([(900, 10)], 1400, 0.23, 100)

checar('sem dispersao de preco, gastar e reservar coincidem',
       _igual['custo'] == _igual['custo_maximo'])

# --- as duas regras do Smart Buy --------------------------------------------
checar('volume justifica a ordem', compra.por_ordem(20, 900)[0])

checar('poucas unidades nao', not compra.por_ordem(3, 900)[0])

checar('e item caro tambem nao',
       not compra.por_ordem(50, compra.CARO_DEMAIS_PARA_ORDEM)[0])

checar('basta uma das duas dizer que nao',
       not compra.por_ordem(3, 999_999)[0])

_p, _modo, _ = compra.decidir(LIVRO, 1400, 0.23, 100)
checar('53 unidades baratas vao por ordem', _modo == 'ordem')

_p, _modo, _motivo = compra.decidir(LIVRO, 1400, 0.23, 5)
checar('5 unidades vao na hora', _modo == 'na hora')
checar('e o motivo diz por que', 'poucas' in _motivo, _motivo)

_p, _modo, _motivo = compra.decidir([(120000, 30)], 200000, 0.23, 30)
checar('item caro vai na hora mesmo em volume', _modo == 'na hora')
checar('e o motivo e o preco', 'caro' in _motivo, _motivo)

# --- ler o livro na tela -----------------------------------------------------


class Livro:
    """As seis linhas do painel, do ponto de vista de quem le."""

    def __init__(self, linhas):
        self.linhas = linhas

    def numero(self, regiao):
        for n in range(cd.LIVRO_LINHAS):
            if tuple(regiao) == cd.venda_preco(n):
                return self.linhas[n][0] if n < len(self.linhas) else None
            if tuple(regiao) == cd.venda_quantidade(n):
                return self.linhas[n][1] if n < len(self.linhas) else None
        return None


def _com_livro(livro, acao):
    real = comum.ler_numero
    comum.ler_numero = livro.numero
    try:
        return acao()
    finally:
        comum.ler_numero = real
        comum.zerar_contadores()


_lido = _com_livro(Livro(LIVRO), compra.ler_livro)

checar('le as seis linhas do painel', _lido == LIVRO, str(_lido))

# a lista e continua e ordenada: linha vazia quer dizer que o livro acabou, e
# insistir depois disso seria ler o fundo do painel
_lido = _com_livro(Livro(LIVRO[:2]), compra.ler_livro)

checar('para na primeira linha vazia', _lido == LIVRO[:2], str(_lido))

checar('livro totalmente vazio devolve lista vazia',
       _com_livro(Livro([]), compra.ler_livro) == [])

# QUANTIDADE ILEGIVEL VIRA 1, E NAO ZERO. Um vira uma compra a menos que a
# possivel; zero faria a linha sumir da conta e a ordem nasceria pequena demais.
_lido = _com_livro(Livro([(898, None), (899, 5)]), compra.ler_livro)

checar('quantidade ilegivel conta como uma, e nao como nenhuma',
       _lido == [(898, 1), (899, 5)], str(_lido))


# ============================================================
grupo('criar a ordem na tela')


class Painel:
    """O painel do item, do ponto de vista de quem preenche e clica nele."""

    def __init__(self, total_na_tela=None):
        self.campos = {}
        self.foco = None
        self.cliques = []
        self.total_na_tela = total_na_tela
        self.erra_o_campo = False
        self.total_ilegivel = False

    def clicar(self, pos, espera=None):
        self.cliques.append((pos['x'], pos['y']))

        for nome, campo in (('qtd', cd.PAINEL_QTD_BARRA),
                            ('preco', cd.PAINEL_PRECO_CAMPO)):
            if (pos['x'], pos['y']) == (campo['x'], campo['y']):
                # o clique que erra por dois pixels cai no campo de cima
                erra = self.erra_o_campo and nome == 'qtd'
                self.foco = 'preco' if erra else nome
                return

        self.foco = None

    def limpar(self):
        if self.foco:
            self.campos[self.foco] = ''

    def digitar(self, texto):
        if self.foco:
            self.campos[self.foco] = self.campos.get(self.foco, '') + str(texto)

    def numero(self, regiao):
        alvo = tuple(regiao)

        if alvo == cd.PAINEL_QTD_VALOR:
            return int(self.campos['qtd']) if self.campos.get('qtd') else None

        if alvo == cd.PAINEL_PRECO_VALOR:
            return int(self.campos['preco']) if self.campos.get('preco') else None

        if alvo == cd.PAINEL_TOTAL:
            if self.total_ilegivel:
                return None
            if self.total_na_tela is not None:
                return self.total_na_tela
            qtd = int(self.campos.get('qtd') or 0)
            preco = int(self.campos.get('preco') or 0)
            return int(qtd * preco * (1 + lucro.TAXA_DE_ORDEM)) or None

        return None


def _com_painel(painel, acao):
    reais = (comum.clicar, comum.digitar, comum.limpar_campo, comum.ler_numero,
             comum.esperar_estavel, comum.assinatura, comum.esperar_mudanca)

    comum.clicar = painel.clicar
    comum.digitar = painel.digitar
    comum.limpar_campo = painel.limpar
    comum.ler_numero = painel.numero
    comum.esperar_estavel = lambda *a, **k: True
    comum.esperar_mudanca = lambda *a, **k: True
    comum.assinatura = lambda r: b''

    try:
        return acao()
    finally:
        (comum.clicar, comum.digitar, comum.limpar_campo, comum.ler_numero,
         comum.esperar_estavel, comum.assinatura, comum.esperar_mudanca) = reais
        comum.zerar_contadores()


_PLANO = compra.planejar(LIVRO, 1400, 0.23, 100)

_p = Painel()
_res, _motivo = _com_painel(_p, lambda: compra.criar_ordem(_PLANO))

checar('cria a ordem', _res, _motivo)

checar('escolhe "Pedido de Compra" antes de preencher',
       _p.cliques[0] == (cd.PAINEL_PEDIDO_DE_COMPRA['x'],
                         cd.PAINEL_PEDIDO_DE_COMPRA['y']), str(_p.cliques[:2]))

checar('a quantidade e o preco vao para os campos certos',
       _p.campos['qtd'] == '53' and _p.campos['preco'] == '899',
       str(_p.campos))

checar('e o clique em criar e o ultimo',
       _p.cliques[-1] == (cd.PAINEL_CRIAR['x'], cd.PAINEL_CRIAR['y']),
       str(_p.cliques[-1]))

# DIGITAR NUM CAMPO QUE JA TEM NUMERO CONCATENA. Pedir 899 num campo que mostrava
# 54 daria 54899, e o jogo aceitaria - uma ordem setenta vezes maior.
_p = Painel()
_p.campos = {'qtd': '1', 'preco': '54'}
_com_painel(_p, lambda: compra.criar_ordem(_PLANO))

checar('o campo e limpo antes de receber o numero',
       _p.campos['preco'] == '899', str(_p.campos))

# --- A ULTIMA BARREIRA: o Total da tela ------------------------------------
# E o unico numero que nao passou pelo nosso OCR duas vezes nem pela nossa
# aritmetica. No bot antigo a mesma divergencia custava uma unidade; aqui
# custaria a ordem inteira.
_p = Painel(total_na_tela=999_999)
_res, _motivo = _com_painel(_p, lambda: compra.criar_ordem(_PLANO))

checar('Total divergente na tela impede a ordem', not _res)

checar('e o motivo diz os dois numeros',
       '999.999' in _motivo and comum.fmt(_PLANO['custo_maximo']) in _motivo,
       _motivo)

checar('e nao clica em criar',
       (cd.PAINEL_CRIAR['x'], cd.PAINEL_CRIAR['y']) not in _p.cliques,
       str(_p.cliques))

# ausencia de evidencia nao e evidencia de erro: recorte fora do lugar nao pode
# travar a compra inteira
_p = Painel()
_p.total_ilegivel = True
_res, _ = _com_painel(_p, lambda: compra.criar_ordem(_PLANO))

checar('Total ilegivel deixa criar, e fica registrado', _res)

# --- o clique que erra o campo ---------------------------------------------
# Dois pixels acima e a quantidade vai para o preco. Ler de volta e o que separa
# isso de uma ordem com a quantidade no lugar do preco.
_p = Painel()
_p.erra_o_campo = True
_res, _motivo = _com_painel(_p, lambda: compra.criar_ordem(_PLANO))

checar('clique que erra o campo nao vira ordem', not _res)

checar('e diz qual campo falhou', 'quantidade' in _motivo, _motivo)


# ============================================================
grupo('as quantidades em tres niveis')

# Item, grupo, tabela - do mais especifico para o mais geral, e o primeiro que
# tiver resposta vence. O nivel do meio e o caso comum: "as armaduras eu quero
# 20, as armas 8". Sem ele voce repetiria o mesmo ajuste quarenta e cinco vezes.

catalogo.zerar()
catalogo.acrescentar('Broadsword', 'Armas')
catalogo.acrescentar('Claymore', 'Armas')
catalogo.acrescentar('Knight Armor', 'Armaduras')

checar('sem nada por cima, vale a tabela',
       catalogo.quantidade('Broadsword', 'T6.0') == 20)

catalogo.definir_no_grupo('Armas', 'T6.0', 8)

checar('o grupo vence a tabela',
       catalogo.quantidade('Broadsword', 'T6.0') == 8)

checar('e vale para todos os itens dele',
       catalogo.quantidade('Claymore', 'T6.0') == 8)

checar('sem contaminar o outro grupo',
       catalogo.quantidade('Knight Armor', 'T6.0') == 20)

checar('nem as outras combinacoes do mesmo grupo',
       catalogo.quantidade('Broadsword', 'T6.1') == 20)

catalogo.definir('Broadsword', 'T6.0', 50)

checar('a excecao do item vence o grupo',
       catalogo.quantidade('Broadsword', 'T6.0') == 50)

checar('e o vizinho de grupo segue no valor do grupo',
       catalogo.quantidade('Claymore', 'T6.0') == 8)

catalogo.definir('Broadsword', 'T6.0', None)

checar('tirar a excecao do item devolve ao GRUPO, e nao a tabela',
       catalogo.quantidade('Broadsword', 'T6.0') == 8)

catalogo.definir_no_grupo('Armas', 'T6.0', None)

checar('e tirar a do grupo devolve a tabela',
       catalogo.quantidade('Broadsword', 'T6.0') == 20)

# ZERO E RESPOSTA em todos os niveis. Procurar com `or` trataria zero como
# ausencia e subiria um nivel - comprando o que voce acabou de recusar.
catalogo.definir_no_grupo('Armas', 'T8.2', 0)

checar('zero no grupo vale zero, e nao a tabela',
       catalogo.quantidade('Broadsword', 'T8.2') == 0)

checar('e a combinacao sai da varredura daquele grupo',
       (8, 2) not in catalogo.combinacoes_de('Broadsword')
       and (8, 2) in catalogo.combinacoes_de('Knight Armor'))

# --- o grupo carrega as quantidades dele --------------------------------------
catalogo.definir_no_grupo('Armas', 'T7.0', 3)

checar('renomear o grupo leva as quantidades junto',
       catalogo.renomear_grupo('Armas', 'Armas brancas')
       and catalogo.quantidade_do_grupo('Armas brancas', 'T7.0') == 3)

checar('e apagar o grupo leva junto',
       catalogo.apagar_grupo('Armas brancas', mover_para='Armaduras')
       and not catalogo.grupo_tem_excecao('Armas brancas'))

checar('os itens foram para o destino',
       catalogo.grupo_de('Broadsword') == 'Armaduras')


# ============================================================
grupo('desfazer a remocao')

# Um item com treze quantidades afinadas some com um clique, e sem isto o unico
# caminho de volta seria refazer o ajuste na mao.

catalogo.zerar()
catalogo.acrescentar('Broadsword', 'Armas')
catalogo.acrescentar('Claymore', 'Armas')
catalogo.definir('Broadsword', 'T6.0', 42)

checar('nao ha o que desfazer no comeco', not catalogo.da_para_desfazer())

catalogo.remover('Broadsword')

checar('removeu', catalogo.todos() == ['Claymore'])
checar('e da para desfazer', catalogo.da_para_desfazer())

checar('desfazer devolve um', catalogo.desfazer() == 1)
checar('no grupo de onde saiu', catalogo.grupo_de('Broadsword') == 'Armas')
checar('COM as quantidades que tinha',
       catalogo.quantidade('Broadsword', 'T6.0') == 42)

# um lote inteiro se desfaz de uma vez, e nao item por item
catalogo.remover_varios(['Broadsword', 'Claymore'])

checar('o lote sai junto', catalogo.todos() == [])
checar('e volta junto', catalogo.desfazer() == 2)
checar('com os dois no lugar', len(catalogo.todos()) == 2)

# o grupo pode ter sumido no meio-tempo
catalogo.remover_varios(['Broadsword'])
catalogo.apagar_grupo('Armas')

checar('grupo apagado depois da remocao', 'Armas' not in catalogo.grupos())

catalogo.desfazer()

checar('o grupo renasce para receber o item de volta',
       catalogo.grupo_de('Broadsword') == 'Armas',
       'jogar o item num grupo que voce nao escolheu seria pior')


# ============================================================
grupo('quanto tempo a varredura vai levar')

# Nem itens nem combinacoes respondem "esse catalogo cabe na minha tarde?" - o
# tempo responde, e e ele que aparece na tela na hora de escolher.

catalogo.zerar()
catalogo.carregar('padrao')

_r = catalogo.resumo()

checar('o resumo traz os minutos', 'minutos' in _r)

checar('e eles batem com as combinacoes',
       abs(_r['minutos']
           - _r['combinacoes'] * catalogo.SEGUNDOS_POR_COMBINACAO / 60) < 0.01)

checar('o catalogo cheio da algo entre meia hora e uma hora',
       30 < _r['minutos'] < 60, f'{_r["minutos"]:.0f} min')

_antes = catalogo.minutos_de_varredura()
catalogo.definir_em_massa(['T8.0', 'T8.1', 'T8.2'], 0)

checar('zerar combinacoes encurta a varredura',
       catalogo.minutos_de_varredura() < _antes,
       f'{catalogo.minutos_de_varredura():.0f} contra {_antes:.0f} min')

checar('e da para perguntar por grupo',
       catalogo.minutos_de_varredura('Armors')
       < catalogo.minutos_de_varredura())

catalogo.zerar()


# ============================================================
grupo('o Mercado Negro: o dropdown que se calibra sozinho')

# A lista de graus do painel NAO COMECA NO GRAU 1 - ela comeca no grau base do
# item, e com encantamento e truncada no Grau 4. A mesma coordenada seleciona
# graus diferentes conforme o item.
#
# Ignorar isso nao da erro: da o preco de um grau gravado como se fosse de
# outro. A v1 resolvia com uma coluna na planilha; aqui sao 252 itens e nao ha
# planilha, entao o bot descobre lendo o rotulo e corrigindo pela diferenca.


class Painel:
    """O painel de venda, com um dropdown que comeca onde o item manda."""

    def __init__(self, base, rotulo_ilegivel=False):
        self.base = base                  # o grau em que a lista COMECA
        self.ench = 0
        self.grau = None
        self.rotulo_ilegivel = rotulo_ilegivel
        self.cliques = 0
        self.deteccoes = []
        self.afastou = []

    def _inicio(self):
        return max(self.base, 4) if self.ench >= 1 else self.base

    def escolher(self, barra, opcao, deteccao=None, afastar=True):
        """Traduz a coordenada clicada no grau que o jogo realmente seleciona."""

        self.cliques += 1
        self.deteccoes.append(deteccao)
        self.afastou.append(afastar)

        indice = (opcao['y'] - cd.VND_DROPDOWN_TOPO) // cd.VND_DROPDOWN_PASSO + 1

        if barra['x'] == cd.VND_BARRA_ENCH['x']:
            self.ench = indice - 1
            self.grau = None
            return

        self.grau = self._inicio() + indice - 1

    def ler_grau(self):
        return None if self.rotulo_ilegivel else self.grau


def _com_painel(painel, acao):

    reais = (mercado_negro.filtros.trocar, mercado_negro.filtros.escolher,
             mercado_negro.ler_grau, comum.esperar_estavel, comum.assinatura,
             comum.esperar_mudanca)

    mercado_negro.filtros.trocar = lambda acao_, regiao=None: acao_() or True
    mercado_negro.filtros.escolher = painel.escolher
    mercado_negro.ler_grau = painel.ler_grau
    comum.esperar_estavel = lambda *a, **k: True
    comum.esperar_mudanca = lambda *a, **k: True
    comum.assinatura = lambda r: b''

    try:
        return acao()
    finally:
        (mercado_negro.filtros.trocar, mercado_negro.filtros.escolher,
         mercado_negro.ler_grau, comum.esperar_estavel, comum.assinatura,
         comum.esperar_mudanca) = reais
        comum.zerar_contadores()


# --- um item cuja lista comeca no grau 1: o palpite ja esta certo -----------
mercado_negro.esquecer_calibragem()
_p = Painel(base=1)

_r = _com_painel(_p, lambda: mercado_negro.escolher_grau('Broadsword', 6, 0))

checar('item de base 1 acerta de primeira', _r == 'ok', _r)
checar('e num clique so', _p.cliques == 1, str(_p.cliques))
checar('com o grau certo selecionado', _p.grau == 6, str(_p.grau))

# --- um item FORA DA TABELA cuja lista comeca no grau 4 ---------------------
# ESTE E O CASO QUE DESTRUIRIA A VARREDURA EM SILENCIO. Pedindo o Grau 6 num
# item que comeca no 4, a coordenada do "sexto da lista" seleciona o Grau 9 -
# que nao existe - ou, pior, um grau qualquer que existe e nao e o pedido.
#
# Os 121 itens da tabela nunca chegam aqui: para eles o primeiro clique ja
# acerta. Sao os outros 131 que dependem desta correcao.
mercado_negro.esquecer_calibragem()
_p = Painel(base=4)

_fora = 'Bloodletter'

checar('o item usado aqui esta mesmo fora da tabela',
       _fora not in mercado_negro.graus_base())

_r = _com_painel(_p, lambda: mercado_negro.escolher_grau(_fora, 6, 0))

checar('item de base 4 tambem termina no grau certo', _r == 'ok', _r)
checar('e o grau selecionado e mesmo o 6', _p.grau == 6, str(_p.grau))
checar('depois de UMA correcao', _p.cliques == 2, f'{_p.cliques} cliques')

checar('a calibragem fica guardada para as proximas combinacoes',
       mercado_negro._inicio(_fora, 0) == 4,
       str(mercado_negro._inicio(_fora, 0)))

_p.cliques = 0
_r = _com_painel(_p, lambda: mercado_negro.escolher_grau(_fora, 8, 0))

checar('a combinacao seguinte ja acerta de primeira',
       _r == 'ok' and _p.cliques == 1, f'{_r}, {_p.cliques} cliques')

# --- com encantamento a lista e truncada no grau 4 -------------------------
mercado_negro.esquecer_calibragem()
_p = Painel(base=1)
_p.ench = 2

_r = _com_painel(_p, lambda: mercado_negro.escolher_grau('Broadsword', 6, 2))

checar('com encantamento, a lista comeca no 4 e o bot sabe disso',
       _r == 'ok' and _p.grau == 6, f'{_r}, grau {_p.grau}')

checar('e sem encantamento ela volta ao grau base',
       mercado_negro._inicio('Broadsword', 0)
       < mercado_negro._inicio('Broadsword', 2))

# --- grau que nao existe naquela lista -------------------------------------
mercado_negro.esquecer_calibragem()
mercado_negro._inicio_conhecido[('Warbow', False)] = 4

checar('grau abaixo do inicio da lista nao vira coordenada',
       mercado_negro._posicao_do_grau('Warbow', 3, 0) is None,
       'clicar ali cairia fora da lista, sem erro nenhum')

# --- rotulo ilegivel nao e evidencia de erro -------------------------------
# Aceitar em silencio ja fez gravar preco de grau errado; descartar ja esvaziou
# leituras boas. O certo e gravar e sinalizar.
mercado_negro.esquecer_calibragem()
_p = Painel(base=1, rotulo_ilegivel=True)

_r = _com_painel(_p, lambda: mercado_negro.escolher_grau('Broadsword', 6, 0))

checar('rotulo ilegivel devolve "ilegivel", e nao erro', _r == 'ilegivel', _r)

# O CURSOR NAO SE MEXE NESTA TELA. Afastar o ponteiro existe por causa da cidade,
# onde a opcao do encantamento 3 para em cima dos primeiros digitos do preco. No
# painel de Pedido de Venda os dropdowns ficam em x=520 e x=665 e o preco em
# x=1016 - o cursor nao chega perto, e mover seria um movimento de mouse e uma
# espera por combinacao sem nada em troca.
mercado_negro.esquecer_calibragem()
_p = Painel(base=1)
_com_painel(_p, lambda: mercado_negro.escolher_grau('Broadsword', 6, 0))
_com_painel(_p, lambda: mercado_negro.escolher_encantamento(2))

checar('no painel do Mercado Negro o cursor fica onde clicou',
       _p.afastou and not any(_p.afastou), str(_p.afastou))

# A ESPERA PRECISA OLHAR PARA A LINHA DO PAINEL, e nao para a da cidade.
#
# O padrao de filtros.escolher olha y=300, onde a primeira opcao aparece na barra
# de cima da cidade. No painel de Pedido de Venda ela sai em y=423. Olhando o
# lugar errado a espera nunca ve a lista abrir: gasta o limite inteiro em CADA
# troca de filtro - 26 por item - e depois clica as cegas, com a lista talvez
# ainda fechada. Era um sintoma so aparecendo como dois: lentidao e grau errado.
mercado_negro.esquecer_calibragem()
_p = Painel(base=1)
_com_painel(_p, lambda: mercado_negro.escolher_grau('Broadsword', 6, 0))

_dt = _p.deteccoes[0]

checar('a espera do dropdown olha a linha do PAINEL',
       _dt is not None and _dt[1] < cd.VND_DROPDOWN_TOPO < _dt[3], str(_dt))

checar('e nao a linha da barra da cidade',
       not (_dt[1] < cd.CMP_DETECCAO_OPCAO_Y < _dt[3]), str(_dt))

# --- o grau base vem da tabela, para os itens que estao nela ---------------
# A mesma coordenada seleciona graus DIFERENTES conforme o item. Pedir o Grau 6
# num item que comeca no 4 clicando a sexta linha seleciona o Grau 9.
mercado_negro.esquecer_calibragem()

checar('a tabela de graus base tem os 121 itens do bot_atualizar',
       len(mercado_negro.graus_base()) == 121,
       str(len(mercado_negro.graus_base())))

checar('Espada Larga abre no Grau 1',
       mercado_negro._inicio('Broadsword', 0) == 1,
       str(mercado_negro._inicio('Broadsword', 0)))

checar('Arco no Grau 2, Besta no 3, Arco de Guerra no 4',
       (mercado_negro._inicio('Bow', 0),
        mercado_negro._inicio('Crossbow', 0),
        mercado_negro._inicio('Warbow', 0)) == (2, 3, 4),
       str((mercado_negro._inicio('Bow', 0),
            mercado_negro._inicio('Crossbow', 0),
            mercado_negro._inicio('Warbow', 0))))

checar('e com encantamento todos comecam no 4, que e o piso',
       all(mercado_negro._inicio(n, 2) == 4
           for n in ('Broadsword', 'Bow', 'Crossbow', 'Warbow')))

# SEM UMA CORRECAO SEQUER: a tabela ja diz onde a lista comeca, entao o primeiro
# clique acerta. Antes disto o Arco de Guerra precisava errar uma vez para
# aprender - e o que errava era um preco gravado no grau errado.
_p = Painel(base=4)
_r = _com_painel(_p, lambda: mercado_negro.escolher_grau('Warbow', 6, 0))

checar('item de base 4 da tabela acerta de primeira',
       _r == 'ok' and _p.grau == 6 and _p.cliques == 1,
       f'{_r}, grau {_p.grau}, {_p.cliques} cliques')

# Fora da tabela o bot continua se virando sozinho.
checar('item fora da tabela cai no palpite, e a calibragem corrige',
       'Bloodletter' not in mercado_negro.graus_base()
       and mercado_negro._inicio('Bloodletter', 0) == 1)


# ============================================================
grupo('o Mercado Negro: busca ou menu')

# A busca do jogo devolve tudo que contem o que voce digitou. "Cursed Staff"
# traz o "Great Cursed Staff" junto; "Bow" traz Crossbow, Warbow e mais seis.

checar('sao 18 itens ambiguos entre os 252',
       len(categorias.ambiguos()) == 18, str(len(categorias.ambiguos())))

checar('o simples e ambiguo, o composto nao',
       categorias.ambiguo('Cursed Staff')
       and not categorias.ambiguo('Great Cursed Staff'))

checar('e "Bow" tambem, por causa de Crossbow e Warbow',
       categorias.ambiguo('Bow') and not categorias.ambiguo('Warbow'))

checar('a maioria vai pela busca, que e mais rapida',
       len(categorias.ambiguos()) < len(categorias.itens_mapeados()) / 10)


class Tela:
    """A tela do Mercado Negro, do ponto de vista de quem abre um item."""

    def __init__(self):
        self.digitado = None
        self.pelo_menu = None
        self.cliques = []

    def clicar(self, pos, espera=None):
        self.cliques.append((pos['x'], pos['y']))

    def digitar(self, texto):
        self.digitado = texto

    def selecionar(self, item):
        self.pelo_menu = item
        return True, ''


def _com_tela(tela, acao):

    reais = (comum.clicar, comum.digitar, mercado_negro.menu.selecionar,
             comum.esperar_mudanca, comum.esperar_estavel, comum.assinatura)

    comum.clicar = tela.clicar
    comum.digitar = tela.digitar
    mercado_negro.menu.selecionar = tela.selecionar
    comum.esperar_mudanca = lambda *a, **k: True
    comum.esperar_estavel = lambda *a, **k: True
    comum.assinatura = lambda r: b''

    try:
        return acao()
    finally:
        (comum.clicar, comum.digitar, mercado_negro.menu.selecionar,
         comum.esperar_mudanca, comum.esperar_estavel, comum.assinatura) = reais
        comum.zerar_contadores()


_t = Tela()
_com_tela(_t, lambda: mercado_negro.abrir('Broadsword'))

checar('item sem ambiguidade vai pela busca',
       _t.digitado == 'Broadsword' and _t.pelo_menu is None)

checar('e clica em Vender na primeira linha',
       (cd.VND_VENDER['x'], cd.VND_VENDER['y']) in _t.cliques, str(_t.cliques))

_t = Tela()
_com_tela(_t, lambda: mercado_negro.abrir('Cursed Staff'))

checar('item ambiguo vai pelo MENU', _t.pelo_menu == 'Cursed Staff')

# O menu desce ate o item; digitar por cima seria trabalho e espera a toa.
checar('e nao digita nada', _t.digitado is None, str(_t.digitado))

checar('mas clica em Vender do mesmo jeito',
       (cd.VND_VENDER['x'], cd.VND_VENDER['y']) in _t.cliques)

# TERMINAR UM ITEM E FECHAR O PAINEL, E MAIS NADA.
#
# A busca nao precisa ser zerada aqui: o proximo item comeca clicando no reset da
# busca antes de digitar, que e a sequencia do bot_atualizar.
#
# E o botao de resetar da direita nao tem o que fazer nesta tela. Ele zera os
# filtros de grau e encantamento DA BARRA DE CIMA, e no Mercado Negro esses
# filtros nao sao usados - os dropdowns que interessam ficam dentro do painel de
# Pedido de Venda e vao embora junto com ele.
for _item in ('Cursed Staff', 'Broadsword'):

    _t = Tela()
    _com_tela(_t, lambda i=_item: (mercado_negro.abrir(i),
                                   mercado_negro.limpar_selecao()))

    checar(f'terminar "{_item}" fecha o painel',
           (cd.VND_FECHAR['x'], cd.VND_FECHAR['y']) in _t.cliques,
           str(_t.cliques))

    checar(f'e nao toca no botao de resetar da direita ({_item})',
           (cd.CMP_LIMPAR_FILTROS['x'], cd.CMP_LIMPAR_FILTROS['y'])
           not in _t.cliques, str(_t.cliques))

mercado_negro.esquecer_calibragem()


# ============================================================
grupo('o gargalo do Mercado Negro')

# A lista de graus do painel so muda de comeco ao cruzar a fronteira entre "sem
# encantamento" e "encantado". Entre 1, 2 e 3 ela e a mesma.
#
# Zerar o grau a cada troca de encantamento fazia o bot reabrir o dropdown treze
# vezes por item em vez de sete - 726 operacoes de dropdown a mais numa varredura
# de 121 itens, cada uma com abertura, animacao, clique e espera do preco
# assentar. Era o que fazia esta tela ser visivelmente mais lenta que a da
# cidade.


class PainelContado:
    """O painel, contando quantas vezes cada dropdown e aberto."""

    def __init__(self, base=1):
        self.base = base
        self.ench = 0
        self.grau = None
        self.trocas_de_grau = 0
        self.trocas_de_ench = 0
        self.afastou = []
        self.leituras_do_rotulo = 0
        self.leituras_do_aviso = 0

    def _inicio(self):
        return max(self.base, 4) if self.ench >= 1 else self.base

    def escolher(self, barra, opcao, deteccao=None, afastar=True):

        self.afastou.append(afastar)

        indice = (opcao['y'] - cd.VND_DROPDOWN_TOPO) // cd.VND_DROPDOWN_PASSO + 1

        if barra['x'] == cd.VND_BARRA_ENCH['x']:
            self.trocas_de_ench += 1
            self.ench = indice - 1
            return

        self.trocas_de_grau += 1
        self.grau = self._inicio() + indice - 1

    def ler_grau(self):
        self.leituras_do_rotulo += 1
        return self.grau

    def livro_vazio(self):
        self.leituras_do_aviso += 1
        return False


def _com_painel_contado(painel, acao):

    reais = (mercado_negro.filtros.trocar, mercado_negro.filtros.escolher,
             mercado_negro.ler_grau, mercado_negro.livro_vazio,
             mercado_negro.abrir, mercado_negro.limpar_selecao,
             mercado_negro.ler_preco, comum.esperar_estavel, comum.assinatura,
             comum.esperar_mudanca)

    mercado_negro.filtros.trocar = lambda a, regiao=None: a() or True
    mercado_negro.filtros.escolher = painel.escolher
    mercado_negro.ler_grau = painel.ler_grau
    mercado_negro.livro_vazio = painel.livro_vazio
    mercado_negro.abrir = lambda i, n=None: (True, '')
    mercado_negro.limpar_selecao = lambda: None
    mercado_negro.ler_preco = lambda anterior=None: 1000 * (painel.grau or 1)
    comum.esperar_estavel = lambda *a, **k: True
    comum.esperar_mudanca = lambda *a, **k: True
    comum.assinatura = lambda r: b''

    try:
        return acao()
    finally:
        (mercado_negro.filtros.trocar, mercado_negro.filtros.escolher,
         mercado_negro.ler_grau, mercado_negro.livro_vazio,
         mercado_negro.abrir, mercado_negro.limpar_selecao,
         mercado_negro.ler_preco, comum.esperar_estavel, comum.assinatura,
         comum.esperar_mudanca) = reais
        comum.zerar_contadores()


_banco_gargalo = mercado._banco
mercado.usar_banco({})
mercado_negro.esquecer_calibragem()

_p = PainelContado(base=1)
_relatos = []

_com_painel_contado(_p, lambda: conferidor.varrer_item(
    mercado.MERCADO_NEGRO, 'Broadsword', conferidor.COMBINACOES, _relatos,
    mercado_negro.TELA))

checar('as 13 combinacoes sao lidas', len(mercado.combinacoes(
    mercado.MERCADO_NEGRO, 'Broadsword')) == 13,
    str(len(mercado.combinacoes(mercado.MERCADO_NEGRO, 'Broadsword'))))

# 4 graus distintos, mais 3 reselecoes ao cruzar a fronteira do encantamento
checar('o dropdown de grau abre 7 vezes, e nao 13',
       _p.trocas_de_grau <= 7, f'{_p.trocas_de_grau} aberturas')

checar('o de encantamento abre 13, que e o minimo',
       _p.trocas_de_ench == 13, str(_p.trocas_de_ench))

# O AVISO DE "NINGUEM COMPRANDO" e um OCR de TEXTO, bem mais caro que o de
# numero. Fazia-lo nas treze combinacoes eram 1.573 leituras por varredura para
# responder uma pergunta que so importa quando a leitura de preco falha.
checar('o aviso do livro nao e lido quando ha preco',
       _p.leituras_do_aviso == 0, f'{_p.leituras_do_aviso} leituras')

# --- e o log traz o que foi lido -------------------------------------------
checar('o relato traz uma linha com as leituras',
       len(_relatos) == 1, str(len(_relatos)))

checar('com as treze combinacoes nela',
       all(r in _relatos[0] for r in ('T5.2', 'T6.0', 'T8.2')), _relatos[0])

checar('e com os precos, para conferir de relance',
       '5.000' in _relatos[0] and '8.000' in _relatos[0], _relatos[0])


# ============================================================
grupo('o laco que percorre a lista e compra')

# ERA A PECA QUE FALTAVA. O compra.py sabia planejar uma linha e criar uma ordem;
# o lucro.py sabia montar a lista. Entre os dois nao havia nada, e a tela dizia
# isso em voz alta.

from motor import comprador
from motor import historico


class Loja:
    """O jogo, do ponto de vista de quem compra.

    Guarda o livro de ofertas de cada item e vai consumindo as ofertas conforme
    o bot compra - que e o que a tela do jogo faz."""

    def __init__(self, livros, dialogo_mente=None):
        self.livros = livros          # {item: [(preco, quantidade), ...]}
        self.item = None
        self.dialogo_mente = dialogo_mente or {}
        self.compradas = []
        self.ordens = []
        self.painel_aberto = 0
        self.filtros = []          # (filtro, valor) na ordem em que foram postos

    def selecionar(self, item):
        self.item = item
        self.filtros.append(('item', item))
        return (True, '') if item in self.livros else (False, 'sem menu')

    def grau(self, valor):
        self.filtros.append(('grau', valor))
        return True

    def encantamento(self, valor):
        self.filtros.append(('ench', valor))
        return True

    def limpar_filtros(self):
        self.filtros.append(('limpar', None))

    def abrir_painel(self):
        self.painel_aberto += 1
        self.filtros.append(('painel', None))
        return True

    def fechar_painel(self):
        pass

    def ler_livro(self, linhas=None):
        return list(self.livros.get(self.item, []))

    def livro_vazio(self):
        return not self.livros.get(self.item)

    def criar_ordem(self, plano, tolerancia=0.01):
        self.ordens.append((self.item, plano['unidades'], plano['preco']))
        return True, ''

    def comprar_uma(self, esperado, aceitar=None):
        """Consome a oferta mais barata. O dialogo pode mostrar outro numero."""

        ofertas = sorted(self.livros.get(self.item, []))

        if not ofertas:
            return 'ausente', None, 'nada na lista'

        preco, quantidade = ofertas[0]

        cobrado = self.dialogo_mente.get(self.item, preco)

        if aceitar is not None:
            pode, motivo = aceitar(cobrado)
            if not pode:
                return 'recusado', None, motivo

        if quantidade <= 1:
            self.livros[self.item] = ofertas[1:]
        else:
            self.livros[self.item] = [(preco, quantidade - 1)] + ofertas[1:]

        self.compradas.append((self.item, cobrado))

        return 'comprou', cobrado, ''


def _com_loja(loja, acao):

    reais = (menu.selecionar, compra.abrir_painel, compra.fechar_painel,
             compra.ler_livro, compra.livro_vazio, compra.criar_ordem,
             compra.comprar_uma, comum.jogo_em_foco, comum.sem_foco,
             comum.relatar, comum.progresso, historico.registrar,
             filtros.grau, filtros.encantamento, filtros.limpar)

    filtros.grau = loja.grau
    filtros.encantamento = loja.encantamento
    filtros.limpar = loja.limpar_filtros
    menu.selecionar = loja.selecionar
    compra.abrir_painel = loja.abrir_painel
    compra.fechar_painel = loja.fechar_painel
    compra.ler_livro = loja.ler_livro
    compra.livro_vazio = loja.livro_vazio
    compra.criar_ordem = loja.criar_ordem
    compra.comprar_uma = loja.comprar_uma
    comum.jogo_em_foco = lambda: True
    comum.sem_foco = lambda: []
    comum.relatar = lambda *a, **k: None
    comum.progresso = lambda *a, **k: None

    registrados = []
    historico.registrar = lambda *a, **k: (registrados.append((a, k)), (True, ''))[1]

    comprador.menu = menu
    comprador.compra = compra
    comprador.historico = historico

    try:
        return acao(), registrados
    finally:
        (menu.selecionar, compra.abrir_painel, compra.fechar_painel,
         compra.ler_livro, compra.livro_vazio, compra.criar_ordem,
         compra.comprar_uma, comum.jogo_em_foco, comum.sem_foco,
         comum.relatar, comum.progresso, historico.registrar,
         filtros.grau, filtros.encantamento, filtros.limpar) = reais
        comum.zerar_contadores()


def _linha(item, rot, compra_, venda, quantidade):
    return lucro.linha(item, rot, compra_, venda, quantidade)


# --- o caminho da ordem: volume e item barato ------------------------------
# Uma ordem casa NA HORA com todas as ofertas naquele preco ou abaixo - as
# unidades de uma vez, num clique. Custa 2,5% de taxa, e por isso so vale em
# volume.
_loja = Loja({'Broadsword': [(900, 10)]})

_r, _reg = _com_loja(_loja, lambda: comprador.comprar_linha(
    _linha('Broadsword', 'T6.0', 900, 2000, 10), 'Thetford', 0.2,
    lucro.TAXA_PADRAO))

checar('dez unidades baratas vao por ORDEM', _r['modo'] == 'ordem', str(_r))

checar('e a ordem e criada uma vez so', len(_loja.ordens) == 1,
       str(_loja.ordens))

checar('com as dez unidades', _loja.ordens[0][1] == 10, str(_loja.ordens))

checar('e a compra entra no historico', len(_reg) == 1, str(_reg))

# A COMBINACAO DA LINHA E POSTA ANTES DE ABRIR O PAINEL. O menu deixa a lista
# com todos os graus do item, e o painel abre o primeiro: sem os filtros, a
# compra seria de uma combinacao qualquer, julgada pela venda de outra.
_ordem_filtros = [f for f, _ in _loja.filtros]

checar('a compra poe o encantamento e o grau da linha antes de abrir o painel',
       _ordem_filtros[:4] == ['item', 'ench', 'grau', 'painel']
       and ('ench', 0) in _loja.filtros and ('grau', 6) in _loja.filtros,
       str(_loja.filtros))

checar('e limpa os filtros no fim, para a linha seguinte nao nascer nesta',
       _ordem_filtros[-1] == 'limpar', str(_loja.filtros))


# --- o caminho da compra na hora: poucas unidades --------------------------
_loja = Loja({'Broadsword': [(900, 3)]})

_r, _reg = _com_loja(_loja, lambda: comprador.comprar_linha(
    _linha('Broadsword', 'T6.0', 900, 2000, 3), 'Thetford', 0.2,
    lucro.TAXA_PADRAO))

checar('tres unidades vao NA HORA', _r['modo'] == 'na hora', str(_r))

checar('e sao tres cliques de compra, um por unidade',
       len(_loja.compradas) == 3, str(_loja.compradas))

checar('cada uma registrada separadamente', len(_reg) == 3, str(len(_reg)))

checar('e nenhuma ordem foi criada', not _loja.ordens)


# --- O DIALOGO MANDA MAIS QUE A LISTA --------------------------------------
# O preco registrado tem de ser o que o JOGO COBROU. No programa antigo o
# historico dizia 66.990 tres vezes enquanto o jogo cobrava 66.990, 66.991 e
# 66.996: cada leitura ficava uma oferta atrasada, cabia na tolerancia, e
# passava. O dinheiro estava certo; a contabilidade e que nao.
_loja = Loja({'Broadsword': [(900, 2)]}, dialogo_mente={'Broadsword': 950})

_r, _reg = _com_loja(_loja, lambda: comprador.comprar_linha(
    _linha('Broadsword', 'T6.0', 900, 2000, 2), 'Thetford', 0.2,
    lucro.TAXA_PADRAO))

checar('o gasto sai do dialogo, e nao da lista',
       _r['gasto'] == 950 * 2, str(_r['gasto']))

checar('e o historico grava o valor cobrado',
       all(a[5] == 950 for a, _ in _reg), str(_reg))


# --- e o dialogo pode RECUSAR ----------------------------------------------
# O jogo vai cobrar um valor que nao paga mais a margem: nao compra, e nao
# adianta insistir - a proxima oferta da fila e mais cara que esta.
_loja = Loja({'Broadsword': [(900, 5)]}, dialogo_mente={'Broadsword': 1900})

_r, _reg = _com_loja(_loja, lambda: comprador.comprar_linha(
    _linha('Broadsword', 'T6.0', 900, 2000, 5), 'Thetford', 0.2,
    lucro.TAXA_PADRAO))

checar('preco real que nao paga a margem nao e comprado',
       _r['unidades'] == 0, str(_r))

checar('e nada vai para o historico', not _reg, str(_reg))

checar('a recusa diz o motivo, com o numero',
       'teto' in _r['motivo'] or 'passa' in _r['motivo'], _r['motivo'])


# --- O TETO DE PRATA -------------------------------------------------------
# O limite de gasto da v1 que faltava aqui. Ele corta a QUANTIDADE antes de
# comprar, e volta a ser conferido no dialogo de cada unidade.
_loja = Loja({'Broadsword': [(1000, 10)]})

_r, _reg = _com_loja(_loja, lambda: comprador.comprar_linha(
    _linha('Broadsword', 'T6.0', 1000, 3000, 10), 'Thetford', 0.2,
    lucro.TAXA_PADRAO, gasto_ate_agora=0, teto_de_prata=3500))

checar('o teto de prata corta a quantidade', _r['unidades'] <= 3,
       f'{_r["unidades"]} unidades com teto de 3.500')

checar('sem estourar o limite', _r['gasto'] <= 3500, str(_r['gasto']))


# --- item que nao abre nao derruba a linha ---------------------------------
_loja = Loja({})

_r, _reg = _com_loja(_loja, lambda: comprador.comprar_linha(
    _linha('Fantasma', 'T6.0', 900, 2000, 3), 'Thetford', 0.2,
    lucro.TAXA_PADRAO))

checar('item sem menu nao compra nada', _r['unidades'] == 0)

checar('e diz por que', bool(_r['motivo']), str(_r))


# --- a lista inteira -------------------------------------------------------
_loja = Loja({'Broadsword': [(900, 10)], 'Claymore': [(800, 10)]})

_lista = [_linha('Broadsword', 'T6.0', 900, 2000, 10),
          _linha('Claymore', 'T6.0', 800, 2000, 10)]

(_res, _reg) = _com_loja(_loja, lambda: comprador.comprar(
    'Thetford', _lista, margem=0.2, taxa=lucro.TAXA_PADRAO,
    teto_de_prata=None))

checar('as duas linhas sao compradas', _res['linhas_compradas'] == 2,
       str(_res))

checar('com as vinte unidades', _res['unidades'] == 20, str(_res['unidades']))

checar('e o resumo traz o gasto', _res['gasto'] > 0, str(_res['gasto']))


# --- simular nao gasta prata -----------------------------------------------
_loja = Loja({'Broadsword': [(900, 10)]})

(_res, _reg) = _com_loja(_loja, lambda: comprador.comprar(
    'Thetford', [_linha('Broadsword', 'T6.0', 900, 2000, 10)],
    margem=0.2, taxa=lucro.TAXA_PADRAO, de_verdade=False))

checar('simulacao calcula as unidades', _res['unidades'] == 10, str(_res))

checar('mas nao cria ordem nem clica em comprar',
       not _loja.ordens and not _loja.compradas)

checar('e nao grava nada no historico', not _reg, str(_reg))


# --- mercado que nao existe ------------------------------------------------
checar('mercado desconhecido devolve erro em vez de clicar',
       'erro' in comprador.comprar('Narnia', []),
       str(comprador.comprar('Narnia', [])))


# ============================================================
grupo('o calibrador')

# BOA PARTE DAS COORDENADAS DAQUI FOI DERIVADA de um print, e nao medida na tela.
# Num dia so isso custou tres defeitos - recorte do preco raspando o primeiro
# digito, deteccao do dropdown olhando a linha errada, ponto de descanso em cima
# de um filtro - e nenhum deles deu erro: os tres deram numero errado em
# silencio. O calibrador e o caminho curto para achar isso.

from interface import ponte as _ponte   # noqa: E402

_marcas = [m for g in cd.PASSOS for m in g['marcas']]

checar('o calibrador tem grupos para todas as telas',
       len(cd.PASSOS) >= 8, str(len(cd.PASSOS)))

# TODA MARCA TEM DE APONTAR PARA UMA CONSTANTE QUE EXISTE. Uma marca orfa e uma
# coordenada que o usuario remarca e o bot ignora - o pior tipo de conserto.
_orfas = [m['nome'] for m in _marcas
          if not m['nome'].startswith('_') and not hasattr(cd, m['nome'])]

checar('e nenhuma marca aponta para constante que nao existe',
       not _orfas, str(_orfas))

checar('cada marca diz o que marcar', all(m.get('o_que') for m in _marcas),
       str([m['nome'] for m in _marcas if not m.get('o_que')]))

checar('e cada grupo diz como preparar a tela do jogo',
       all(g.get('preparo') for g in cd.PASSOS),
       str([g['titulo'] for g in cd.PASSOS if not g.get('preparo')]))

# AS COORDENADAS QUE JA DERAM DEFEITO ESTAO LA, e com a dica que explica o erro.
_nomes = {m['nome'] for m in _marcas}

checar('o recorte do preco esta calibravel', 'PRECO_COMPRA' in _nomes)

checar('e a dica dele avisa do icone da moeda',
       any('moeda' in (m.get('dica') or '') for m in _marcas))

checar('o ponto de descanso do cursor tambem', 'MOUSE_DESCANSO' in _nomes)

checar('e o quadro de "sem ofertas"', 'CMP_SEM_OFERTAS' in _nomes)

# GRAVAR TEM DE SER DESFAZIVEL. O que sai daqui e um arquivo ao lado do
# programa; apagar o arquivo devolve o padrao, sem editar codigo.
checar('o perfil grava e carrega por arquivo',
       hasattr(cd, 'salvar_perfil') and hasattr(cd, 'carregar_perfil'))

checar('e a interface abre o calibrador e le os passos pela ponte',
       hasattr(_ponte.Api, 'abrir_calibrador')
       and hasattr(_ponte.Api, 'calibrador_passos')
       and hasattr(_ponte.Api, 'salvar_coordenadas'))


# ============================================================
grupo('vender no Mercado Negro')

# DUAS SAIDAS, e a escolha e entre tempo e prata: casar com um pedido de compra
# que ja existe (a prata entra agora) ou entrar na fila uma prata abaixo do
# vendedor mais barato (rende mais, e pode nao vender nunca).

from motor import vendedor

# --- o alvo sai do que foi pago -------------------------------------------
# A prata ja saiu. O que se decide e aceitar ou nao o que o mercado oferece, e a
# unica referencia honesta e o custo real daquela unidade.
_alvo = lucro.venda_minima(1000, 0.20, 0.08)

checar('o alvo devolve a margem pedida',
       abs(lucro.liquido(1000, _alvo, 0.08) - 0.20) < 0.01,
       f'alvo {_alvo}, margem {lucro.liquido(1000, _alvo, 0.08) * 100:.1f}%')

checar('e o alvo por ordem e maior, porque a ordem custa 2,5% a mais',
       lucro.venda_minima(1000, 0.20, 0.08, ordem_na_venda=True) > _alvo)

checar('o preco_maximo e o inverso disto',
       abs(compra.preco_maximo(_alvo, 0.20, 0.08) - 1000) <= 2,
       str(compra.preco_maximo(_alvo, 0.20, 0.08)))

# --- pedido de compra perto do alvo: vende agora ---------------------------
# RECEBER AGORA E MELHOR QUE RECEBER TALVEZ. Exigir o alvo exato faria o bot
# recusar 99% e ficar com a carga na mao esperando uma ordem que talvez nunca
# case - trocando prata garantida por prata possivel.
_modo, _preco, _motivo = vendedor.decidir(1000, 1300, 1500, 0.20, 0.08)

checar('97% do alvo ja vende na hora', _modo == 'na hora', f'{_modo} {_motivo}')

checar('pelo preco de quem esta comprando', _preco == 1300, str(_preco))

# --- longe do alvo: entra na fila -----------------------------------------
_modo, _preco, _motivo = vendedor.decidir(1000, 1000, 1500, 0.20, 0.08)

checar('75% do alvo nao vende na hora', _modo == 'ordem', f'{_modo} {_motivo}')

# UMA PRATA ABAIXO, e nao mais. A lista do jogo ordena por preco, e uma unidade
# abaixo poe a oferta na frente de todas daquele preco. Baixar mais e dar
# desconto para ninguem.
checar('a ordem entra uma prata abaixo do menor vendedor',
       _preco == 1499, str(_preco))

# --- sem pedido de compra nenhum ------------------------------------------
_modo, _preco, _ = vendedor.decidir(1000, None, 1500, 0.20, 0.08)

checar('sem pedido de compra, so resta a fila', _modo == 'ordem', str(_modo))

# --- a fila abaixo do custo: nao vende ------------------------------------
# ENTRAR NA FILA ABAIXO DO CUSTO E TROCAR PRATA POR PRATA MENOR. Nao ha pressa
# que justifique: a carga nao estraga, e o mercado muda.
_modo, _preco, _motivo = vendedor.decidir(1000, 900, 1100, 0.20, 0.08)

checar('fila abaixo do alvo nao vira ordem', _modo is None, f'{_modo} {_motivo}')

# 1.341 = 1.000 x 1,20 / (1 - 8% - 2,5%). O pago ja e o custo real - a taxa de
# ordem da compra, quando houve, foi gravada dentro dele -, e soma-la de novo
# punha o alvo em 1.375.
checar('e o motivo diz os dois numeros',
       '1.100' in _motivo and '1.341' in _motivo, _motivo)

# --- nem pedido de compra nem fila ----------------------------------------
_modo, _, _motivo = vendedor.decidir(1000, None, None, 0.20, 0.08)

checar('sem os dois lados do livro, nao ha o que decidir', _modo is None)


# --- a carga do dia sai do historico --------------------------------------
# O QUE SE PRECISA SABER DE CADA UNIDADE E QUANTO ELA CUSTOU, e isso a tela do
# jogo nao mostra. Sem esse numero nao ha alvo, e sem alvo a decisao vira chute.
from motor import historico as _hist

_arquivo_real = _hist.ARQUIVO
_hist.ARQUIVO = os.path.join(_DADOS, '_hist_de_teste.csv')

try:
    if os.path.exists(_hist.ARQUIVO):
        os.remove(_hist.ARQUIVO)

    _hist.comprou('Thetford', 'Broadsword', 'T6.0', 5, 1000, 'ordem')
    _hist.comprou('Thetford', 'Claymore', 'T6.0', 3, 2000, 'na hora')
    _hist.vendeu('Caerleon Mercado Negro', 'Broadsword', '', 2, 1500, 'na hora')

    _carga = vendedor.carga_pendente()

    checar('a carga traz o que foi comprado e nao vendido',
           {e['item']: e['unidades'] for e in _carga} == {'Broadsword': 3,
                                                         'Claymore': 3},
           str(_carga))

    checar('com o preco pago de cada um',
           {e['item']: e['pago'] for e in _carga} == {'Broadsword': 1000,
                                                     'Claymore': 2000},
           str(_carga))

    checar('e a combinacao comprada', {e['combinacao'] for e in _carga} == {'T6.0'},
           str(_carga))

    _hist.vendeu('Caerleon Mercado Negro', 'Broadsword', '', 3, 1500, 'na hora')
    _hist.vendeu('Caerleon Mercado Negro', 'Claymore', '', 3, 2600, 'ordem')

    checar('e some da carga quando tudo foi vendido',
           vendedor.carga_pendente() == [], str(vendedor.carga_pendente()))

    # A UNIDADE COMPRADA POR QUALIDADE leva a qualidade junto; o resto e vendido
    # como Normal. Num arquivo a parte: o resumo do dia, logo abaixo, conta o de
    # cima.
    _hist_principal = _hist.ARQUIVO
    _hist.ARQUIVO = os.path.join(_DADOS, '_hist_qualidade.csv')

    _hist.comprou('Thetford', 'Bow', 'T7.0', 2, 50_000, 'na hora', qualidade=3)
    _hist.comprou('Thetford', 'Bow', 'T7.0', 1, 40_000, 'na hora')

    _carga_q = vendedor.carga_pendente()

    checar('a carga separa a unidade de qualidade da Normal',
           [(e['pago'], e['unidades'], e['qualidade']) for e in _carga_q]
           == [(40_000, 1, None), (50_000, 2, 3)], str(_carga_q))

    checar('o historico guarda e devolve a qualidade',
           [o['qualidade'] for o in _hist.ler() if o['item'] == 'Bow'] == [3, None])

    _hist.vendeu('Caerleon Mercado Negro', 'Bow', '', 3, 60_000, 'na hora')

    # O ARQUIVO DE ANTES DA COLUNA NOVA: o cabecalho e reescrito uma vez, e as
    # linhas antigas ficam
    with open(_hist.ARQUIVO, 'w', encoding='utf-8', newline='') as _f:
        _f.write('quando,operacao,mercado,item,combinacao,unidades,preco,total,'
                 'modo,observacao\r\n'
                 f'{time.strftime("%Y-%m-%d %H:%M:%S")},compra,Thetford,Spear,T6.0,'
                 f'1,700,700,na hora,\r\n')

    _hist.comprou('Thetford', 'Pike', 'T6.0', 1, 900, 'na hora', qualidade=2)

    _lidas = {o['item']: o['qualidade'] for o in _hist.ler()}

    checar('o historico antigo ganha a coluna sem perder linha',
           _lidas == {'Spear': None, 'Pike': 2}, str(_lidas))

    with open(_hist.ARQUIVO, encoding='utf-8') as _f:
        checar('e o cabecalho fica com as colunas novas no fim',
               _f.readline().strip() == ','.join(_hist.COLUNAS))

    _hist.ARQUIVO = _hist_principal

    # O LUCRO AQUI E REALIZADO, e nao previsto - e a diferenca entre os dois e a
    # unica medida honesta de quanto o bot acerta. A ordem de venda do Claymore
    # so foi criada: fica em "em ordens", fora do recebido.
    _r = _hist.do_dia()

    checar('o resumo do dia soma as duas pontas',
           _r['gasto'] == 5 * 1000 + 3 * 2000
           and _r['recebido'] == 2 * 1500 + 3 * 1500,
           str(_r))

    checar('e a ordem de venda criada fica a parte, sem contar como recebida',
           _r['em_ordens'] == 3 * 2600, str(_r))

    checar('e o saldo e a diferenca',
           _r['saldo'] == _r['recebido'] - _r['gasto'], str(_r))

finally:
    try:
        os.remove(_hist.ARQUIVO)
    except OSError:
        pass
    _hist.ARQUIVO = _arquivo_real
    comum.zerar_contadores()


# ============================================================
grupo('a venda que a lista promete e a que o vendedor faz')

# A LISTA E O VENDEDOR TEM DE FAZER A MESMA CONTA. A lista usava o menor pedido
# de venda do Mercado Negro com a taxa de quem vende na hora - um caminho que nao
# existe -, e o vendedor recusava vender por ordem o que ela aprovou entre 23% e
# ~26%. Na hora, vendia toda a carga sem conferir o valor de cada unidade.

from motor import escuta as _escuta   # noqa: E402

# --- o caminho da venda ----------------------------------------------------
checar('so com a fila, vende por ordem uma prata abaixo dela',
       lucro.melhor_venda(2000, None) == (1999, True), str(lucro.melhor_venda(2000, None)))

checar('com o pedido de compra perto da fila, vende na hora pelo pedido',
       lucro.melhor_venda(2000, 1990) == (1990, False), str(lucro.melhor_venda(2000, 1990)))

checar('com o pedido longe da fila, a ordem rende mais',
       lucro.melhor_venda(2000, 1000) == (1999, True), str(lucro.melhor_venda(2000, 1000)))

# 81.270.374 contra uma fila de 1.659.971: lido assim por OCR, nos precos reais
checar('pedido acima da fila e leitura errada, e fica de fora',
       lucro.melhor_venda(1_659_971, 81_270_374) == (1_659_970, True))

checar('so com o pedido, vende na hora', lucro.melhor_venda(None, 1500) == (1500, False))

checar('sem nenhum dos dois, nao ha venda', lucro.melhor_venda(None, None) == (None, None))

# --- a lista usa o caminho de verdade ---------------------------------------
_banco_venda = mercado._banco
mercado.usar_banco({})
_agora_v = time.time()


def _precos(item, compra_, fila, pedido=None):
    mercado.gravar('Thetford', item, 'T6.0', compra_, _agora_v)
    mercado.gravar(mercado.MERCADO_NEGRO, item, 'T6.0', fila, _agora_v, outro=pedido)


try:
    # O CASO DOS PRECOS REAIS: pedido de compra num quarto da fila
    _precos('Knight Helmet', 29_471, 116_349, 30_312)

    _l, _ = lucro.montar([('Knight Helmet', 'T6.0', 5)], 'Thetford', margem_minima=0.0)

    checar('com o pedido baixo, a linha vende pela fila, por ordem',
           _l and _l[0]['venda'] == 116_348 and _l[0]['venda_por_ordem'], str(_l))

    checar('e a margem desconta os 2,5% da ordem de venda',
           _l and abs(_l[0]['margem']
                      - lucro.liquido(29_471, 116_348, ordem_na_venda=True)) < 1e-9
           and _l[0]['margem'] < lucro.liquido(29_471, 116_349))

    # 1.000 por ordem custa 1.025; com a fila em 1.422 a venda por ordem rende
    # 24%. Antes a lista aprovava e o vendedor, com os mesmos precos, recusava.
    _precos('Broadsword', 1000, 1422)

    _l, _ = lucro.montar([('Broadsword', 'T6.0', 5)], 'Thetford', margem_minima=0.23)

    checar('a lista aprova a venda por ordem com 24%',
           len(_l) == 1 and 0.23 <= _l[0]['margem'] < 0.25, str(_l))

    # o historico grava o custo da compra por ordem com a taxa dentro
    _pago_v = int(_l[0]['custo'] / _l[0]['quantidade']) if _l else 0
    _modo, _preco, _motivo = vendedor.decidir(_pago_v, None, 1422, 0.23, lucro.TAXA_PADRAO)

    checar('e o vendedor, com os mesmos precos, vende pelo mesmo caminho',
           _modo == 'ordem' and _preco == 1421, f'{_modo} {_preco} {_motivo}')

    _precos('Claymore', 1000, 1500, 1480)

    _l, _ = lucro.montar([('Claymore', 'T6.0', 5)], 'Thetford', margem_minima=0.23)

    checar('com o pedido perto da fila, a lista conta a venda na hora',
           _l and not _l[0]['venda_por_ordem'] and _l[0]['venda'] == 1480, str(_l))

    _modo, _preco, _ = vendedor.decidir(1025, 1480, 1500, 0.23, lucro.TAXA_PADRAO)

    checar('e o vendedor vende na hora pelo mesmo pedido',
           _modo == 'na hora' and _preco == 1480, f'{_modo} {_preco}')

    _l, _ = lucro.montar([('Claymore', 'T6.0', 50)], 'Thetford', margem_minima=0.0,
                         espacos=10)

    checar('cortada pelos espacos, a linha guarda o caminho da venda',
           _l and _l[0]['quantidade'] == 10 and not _l[0]['venda_por_ordem'], str(_l))

finally:
    mercado.usar_banco(_banco_venda)

# --- o teto de compra segue o caminho da venda -----------------------------
checar('vender por ordem baixa o teto de compra',
       compra.preco_maximo(10000, 0.23, ordem_na_venda=True)
       < compra.preco_maximo(10000, 0.23))

_hora = compra.planejar([(1000, 10), (1080, 10)], 1500, 0.23, 100)
_ordem = compra.planejar([(1000, 10), (1080, 10)], 1500, 0.23, 100, ordem_na_venda=True)

checar('e o plano compra menos quando a venda e por ordem',
       _hora['unidades'] == 20 and _ordem['unidades'] == 10,
       f'{_hora["unidades"]} contra {_ordem["unidades"]}')

# o dialogo cobra 1.470: paga a margem vendendo na hora (teto 1.495), mas nao
# vendendo por ordem (teto 1.455)
_linha_ordem = _linha('Broadsword', 'T6.0', 900, 2000, 2)
_linha_ordem['venda_por_ordem'] = True

_r, _reg = _com_loja(Loja({'Broadsword': [(900, 2)]}, dialogo_mente={'Broadsword': 1470}),
                     lambda: comprador.comprar_linha(_linha_ordem, 'Thetford', 0.2,
                                                     lucro.TAXA_PADRAO))

checar('o dialogo da compra e julgado pelo caminho da venda da linha',
       _r['unidades'] == 0 and not _reg, str(_r))

_r, _ = _com_loja(Loja({'Broadsword': [(900, 2)]}, dialogo_mente={'Broadsword': 1470}),
                  lambda: comprador.comprar_linha(_linha('Broadsword', 'T6.0', 900, 2000, 2),
                                                  'Thetford', 0.2, lucro.TAXA_PADRAO))

checar('e o mesmo valor passa quando a venda e na hora', _r['unidades'] == 2, str(_r))

# --- o piso ----------------------------------------------------------------
checar('com o "perto" padrao, o piso e 95% do alvo',
       vendedor.piso(1000, 0.20, 0.08)
       == int(vendedor.alvo(1000, 0.20, 0.08) * 0.95 + 0.999))

_piso_baixo = vendedor.piso(1000, 0.20, 0.08, perto=0.5)

checar('e nunca fica abaixo do custo, nem com o "perto" em 50%',
       lucro.receita_real(_piso_baixo, 0.08) >= 1000, str(_piso_baixo))

_modo, _preco, _ = vendedor.decidir(1000, 5000, 1500, 0.20, 0.08)

checar('pedido acima da fila nao vira venda na hora',
       _modo == 'ordem' and _preco == 1499, f'{_modo} {_preco}')

# --- o numero do dialogo ---------------------------------------------------
checar('o valor do dialogo nao junta o "1 unidades" ao preco',
       comum.valor_do_dialogo('Quer vender 1 unidades de Espada Larga por 25.000 '
                              'de prata?') == 25000)

checar('com virgula de milhar tambem',
       comum.valor_do_dialogo('Do you want to sell 1 Broadsword for 1,234,567 '
                              'silver?') == 1_234_567)

checar('sem preco legivel, nada',
       comum.valor_do_dialogo('Quer vender 1 unidades de Espada por de prata?') is None)

checar('preco partido pelo OCR sai menor, e nao maior',
       (comum.valor_do_dialogo('por 125 000 de prata') or 0) < 125_000)

# --- vender na hora, unidade por unidade ----------------------------------


def _dialogo(valor):
    return f'Quer vender 1 unidades de Espada Larga por {valor} de prata?'


def _vender_com(pedido, fila, dialogos, rede=None, aberta=None, **kw):
    """vender_item contra um Mercado Negro de mentira. (saida, cliques, vendas)."""

    reais = (vendedor.abrir, vendedor.fechar, vendedor.ler_precos,
             vendedor.criar_ordem, _escuta.ultimo_do_item, _escuta.combinacao_aberta,
             comum.clicar, comum.assinatura, comum.esperar_mudanca,
             comum.esperar_estavel, comum.ler_texto, comum.salvar_diagnostico,
             _hist.ARQUIVO)

    cliques = []
    fila_de_dialogos = list(dialogos)

    vendedor.abrir = lambda item, nome=None: (True, '')
    vendedor.fechar = lambda: None
    vendedor.ler_precos = lambda: (pedido, fila)
    vendedor.criar_ordem = lambda preco, unidades: (True, '')
    _escuta.ultimo_do_item = lambda *a, **k: rede
    _escuta.combinacao_aberta = lambda *a, **k: aberta
    comum.clicar = lambda pos, espera=None: cliques.append(pos)
    comum.assinatura = lambda regiao: b''
    comum.esperar_mudanca = lambda *a, **k: True
    comum.esperar_estavel = lambda *a, **k: True
    comum.ler_texto = lambda regiao: fila_de_dialogos.pop(0) if fila_de_dialogos else ''
    comum.salvar_diagnostico = lambda *a, **k: None

    _hist.ARQUIVO = os.path.join(_DADOS, '_hist_venda.csv')

    if os.path.exists(_hist.ARQUIVO):
        os.remove(_hist.ARQUIVO)

    try:
        saida = vendedor.vender_item(kw.pop('item', 'Broadsword'), kw.pop('pago', 1000),
                                     kw.pop('unidades', 3), 0.20, 0.08, **kw)
        vendas = _hist.ler()

    finally:
        (vendedor.abrir, vendedor.fechar, vendedor.ler_precos,
         vendedor.criar_ordem, _escuta.ultimo_do_item, _escuta.combinacao_aberta,
         comum.clicar, comum.assinatura, comum.esperar_mudanca,
         comum.esperar_estavel, comum.ler_texto, comum.salvar_diagnostico,
         _hist.ARQUIVO) = reais

    return saida, cliques, vendas


# pago 1.000 com 20% e 8%: alvo 1.305, piso 1.240. O primeiro pedido paga 1.300;
# vendido ele, o segundo paga 1.290, e o terceiro so 1.100.
_s, _cl, _vendas = _vender_com(1300, 1500, [_dialogo('1.300'), _dialogo('1.290'),
                                             _dialogo('1.100')], combinacao='T5.2')

checar('vende enquanto o dialogo paga o piso, e para no que nao paga',
       _s['unidades'] == 2 and 'piso' in _s['motivo'], str(_s))

checar('o dialogo abaixo do piso e recusado no jogo',
       _cl.count(cd.CMP_CONFIRMAR_SIM) == 2 and _cl.count(cd.CMP_NAO_COMPRAR) == 1,
       str(_cl))

checar('o recebido e o historico sao liquidos de taxa',
       _s['recebido'] == int(1300 * 0.92) + int(1290 * 0.92)
       and [v['liquido'] for v in _vendas] == [int(1300 * 0.92), int(1290 * 0.92)],
       f'{_s} {[v["liquido"] for v in _vendas]}')

checar('e sem a rede confirmar o grau, a venda vai sem combinacao',
       [v['combinacao'] for v in _vendas] == ['', ''], str(_vendas))

_s, _, _ = _vender_com(1300, 1500, [_dialogo('1.300'), _dialogo('???')], unidades=3)

checar('dialogo ilegivel depois da primeira unidade para a venda',
       _s['unidades'] == 1, str(_s))

_s, _, _vendas = _vender_com(1300, 1500, [_dialogo('???'), _dialogo('1.300')], unidades=2)

checar('na primeira unidade vale o pedido que acabou de ser lido',
       _s['unidades'] == 2 and _vendas[0]['preco'] == 1300, str(_s))

_s, _cl, _ = _vender_com(1300, 1500, [_dialogo('1.300')], rede=(1300, 1500),
                         aberta='T8.0', combinacao='T5.2')

checar('com a rede dizendo que o painel abriu outra combinacao, nao vende',
       _s['unidades'] == 0 and 'T8.0' in _s['motivo'] and not _cl, str(_s))

_s, _, _vendas = _vender_com(1300, 1500, [_dialogo('1.300')], rede=(1300, 1500),
                             aberta='T5.2', combinacao='T5.2', unidades=1)

checar('com a rede confirmando, a venda grava a combinacao',
       _s['unidades'] == 1 and _vendas[0]['combinacao'] == 'T5.2', str(_vendas))

_s, _cl, _ = _vender_com(1300, 1500, [_dialogo('1.300')], combinacao='T5.2',
                         pago_se_incerto=5000)

checar('sem confirmar o grau, decide pelo custo do mais caro da carga',
       _s['unidades'] == 0 and not _cl, str(_s))

_s, _, _vendas = _vender_com(None, 1500, [], unidades=2)

checar('a ordem de venda nao conta como recebida',
       _s['modo'] == 'ordem' and _s['recebido'] == 0
       and _s['em_ordem'] == int(1499 * (1 - 0.08 - lucro.TAXA_DE_ORDEM) * 2), str(_s))

checar('e vai para o historico como ordem, com o liquido previsto',
       _vendas and _vendas[0]['modo'] == _hist.ORDEM
       and _vendas[0]['liquido'] == _s['em_ordem'], str(_vendas))

# --- a carga --------------------------------------------------------------
_arquivo_real = _hist.ARQUIVO
_hist.ARQUIVO = os.path.join(_DADOS, '_hist_carga.csv')

try:
    if os.path.exists(_hist.ARQUIVO):
        os.remove(_hist.ARQUIVO)

    _agora_v = time.time()
    _negro = mercado.MERCADO_NEGRO

    _hist.registrar(_hist.COMPRA, 'Thetford', 'Broadsword', 'T5.2', 2, 1000,
                    'na hora', quando=_agora_v - 50 * 3600)
    _hist.registrar(_hist.COMPRA, 'Thetford', 'Broadsword', 'T5.2', 3, 1100,
                    'na hora', quando=_agora_v - 30 * 3600)
    _hist.registrar(_hist.COMPRA, 'Thetford', 'Broadsword', 'T8.0', 1, 30_000,
                    'ordem', quando=_agora_v - 60)

    _c = vendedor.carga_pendente()

    checar('a carga atravessa a meia-noite: a compra de 30 h atras continua nela',
           any(e['pago'] == 1100 and e['unidades'] == 3 for e in _c), str(_c))

    checar('e a de mais de 48 h fica de fora', not any(e['pago'] == 1000 for e in _c))

    _hist.vendeu(_negro, 'Broadsword', 'T8.0', 1, 40_000, 'na hora')

    _c = vendedor.carga_pendente()

    checar('a venda que sabe a combinacao abate a compra dela',
           [(e['combinacao'], e['unidades']) for e in _c] == [('T5.2', 3)], str(_c))

    _hist.vendeu(_negro, 'Broadsword', '', 2, 1500, 'na hora')

    checar('a que nao sabe abate a mais antiga do item',
           [(e['combinacao'], e['unidades']) for e in vendedor.carga_pendente()]
           == [('T5.2', 1)])

    _dois_graus = [
        {'item': 'Broadsword', 'combinacao': 'T5.2', 'pago': 1000, 'unidades': 2, 'qualidade': None},
        {'item': 'Broadsword', 'combinacao': 'T8.0', 'pago': 30_000, 'unidades': 1, 'qualidade': None},
        {'item': 'Claymore', 'combinacao': 'T6.0', 'pago': 2000, 'unidades': 1, 'qualidade': None},
    ]

    checar('sem confirmar o grau, o item em duas combinacoes decide pelo mais caro',
           vendedor.custos_se_incerto(_dois_graus) == [30_000, 30_000, 2000])

finally:
    try:
        os.remove(_hist.ARQUIVO)
    except OSError:
        pass
    _hist.ARQUIVO = _arquivo_real

# --- o saldo ----------------------------------------------------------------
_s = _hist.somar([
    {'operacao': 'compra', 'total': 2000, 'unidades': 2, 'modo': 'na hora', 'liquido': None},
    {'operacao': 'venda', 'total': 3000, 'unidades': 2, 'modo': 'na hora', 'liquido': 2760},
    {'operacao': 'venda', 'total': 1000, 'unidades': 1, 'modo': 'ordem', 'liquido': 895},
    {'operacao': 'venda', 'total': 500, 'unidades': 1, 'modo': 'na hora', 'liquido': None},
])

checar('o recebido e liquido de taxa, e a linha antiga entra pelo total',
       _s['recebido'] == 2760 + 500, str(_s))

checar('a ordem de venda fica em "em ordens", fora do saldo',
       _s['em_ordens'] == 895 and _s['saldo'] == 2760 + 500 - 2000, str(_s))

comum.zerar_contadores()


# ============================================================
grupo('os avisos do canto de baixo')

# O log so vai ser lido depois - a janela passa a varredura inteira minimizada.
# Sem estes cartoes nao ha como conferir uma leitura ENQUANTO ela acontece, ao
# lado do numero que o jogo esta mostrando.

_avisos = []

comum.definir_aviso(lambda t, v, tom: _avisos.append((t, v, tom)))

mercado.usar_banco({})
mercado_negro.esquecer_calibragem()

_com_painel_contado(PainelContado(base=1), lambda: conferidor.varrer_item(
    mercado.MERCADO_NEGRO, 'Broadsword', conferidor.COMBINACOES, [],
    mercado_negro.TELA))

comum.definir_aviso(None)

checar('cada combinacao lida vira um aviso',
       len(_avisos) == 13, f'{len(_avisos)} avisos')

checar('com o nome do item e a combinacao no titulo',
       _avisos[0][0].startswith('Broadsword T'), _avisos[0][0])

checar('e o preco formatado, do jeito que se le na tela do jogo',
       _avisos[0][1] == '5.000', str(_avisos[0][1]))

# Ninguem ouvindo e o caso normal: o bot tambem roda pela linha de comando.
comum.avisar('sem ninguem ouvindo', '1')

checar('avisar sem destino nao levanta nada', True)


def _ouvinte_quebrado(*_a):
    raise RuntimeError('a janelinha morreu')


comum.definir_aviso(_ouvinte_quebrado)
comum.avisar('x', '1')
comum.definir_aviso(None)

# A janelinha vive por cima de um jogo em tela cheia, que pode trocar de
# resolucao a qualquer momento. Se ela morrer, a varredura continua.
checar('e um aviso que falha nao derruba a varredura', True)

mercado.usar_banco(_banco_gargalo)
mercado_negro.esquecer_calibragem()

# --- item cuja lista comeca no 4: continua acertando -----------------------
mercado.usar_banco({})
mercado_negro.esquecer_calibragem()

_p = PainelContado(base=4)
_relatos = []

_com_painel_contado(_p, lambda: conferidor.varrer_item(
    mercado.MERCADO_NEGRO, 'Warbow', conferidor.COMBINACOES, _relatos,
    mercado_negro.TELA))

checar('item de base 4 tambem le as 13',
       len(mercado.combinacoes(mercado.MERCADO_NEGRO, 'Warbow')) == 13)

checar('e o preco gravado corresponde ao grau certo',
       mercado.ler(mercado.MERCADO_NEGRO, 'Warbow', 'T6.0')[0] == 6000,
       str(mercado.ler(mercado.MERCADO_NEGRO, 'Warbow', 'T6.0')[0]))

checar('sem estourar as aberturas de dropdown',
       _p.trocas_de_grau <= 9, f'{_p.trocas_de_grau} aberturas')

mercado.usar_banco(_banco_gargalo)
mercado_negro.esquecer_calibragem()


# ============================================================
grupo('os identificadores: de que item e cada pacote da rede')

from motor import identificadores   # noqa: E402

checar('o nome vira o identificador do jogo',
       identificadores.identificador('Broadsword', 'T5.2') == 'T5_MAIN_SWORD@2'
       and identificadores.identificador('Broadsword', 'T6.0') == 'T6_MAIN_SWORD')

checar('item sem identificador fica sem',
       identificadores.identificador('Espada de Teste', 'T5.0') is None)

with open(identificadores.ARQUIVO_IDS, encoding='utf-8') as _f:
    _ids_jogo = json.load(_f)

checar('todo item do catalogo inicial tem identificador',
       all(i in _ids_jogo for i in _do_inicial),
       str([i for i in _do_inicial if i not in _ids_jogo][:5]))

# ============================================================
print(f'\n===== {ok} ok, {len(falhas)} falhas =====')

for f in falhas:
    print(f'  {f}')

raise SystemExit(1 if falhas else 0)
