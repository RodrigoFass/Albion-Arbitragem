################################
#                              #
#         CRAFT ROYAL          #
#                              #
################################

# Vale a pena craftar um item Royal para vender NA HORA no Mercado Negro?
#
# A RECEITA, DOS DADOS DO JOGO (ao-bin-dumps, items.xml): um Royal e o item
# normal do mesmo slot e do mesmo grau e encantamento - qualquer um dos tres da
# linha - mais Royal Sigils do mesmo grau. Sem material bruto, sem prata e sem
# foco no craft, e sem retorno de recurso.
#
#     Royal Cowl / Robe / Sandals     Scholar, Cleric ou Mage
#     Royal Hood / Jacket / Shoes     Mercenary, Hunter ou Assassin
#     Royal Helmet / Armor / Boots    Soldier, Knight ou Guardian
#
#     Sigils     T4  T5  T6  T7  T8
#     cabeca/pe   2   4   8   8   8
#     peito       4   8  16  16  16
#
# A CONTA, POR COMBINACAO:
#
#     receita  = Buy Order do Mercado Negro x (1 - taxa de venda)
#                (vender NA HORA casa com o pedido de compra: sem os 2,5% da ordem)
#     custo    = o mais barato dos tres itens normais na cidade
#                + Sigils x preco do Sigil na cidade
#     lucro    = receita - custo
#
# OS PRECOS SAO OS DO BANCO DE SEMPRE. O Buy Order vem da leitura do Mercado
# Negro (o "outro" preco que ela ja guardava); o item normal, da leitura da
# cidade; o Sigil, da rede quando voce o abre no mercado, ou digitado na tela.
#
# Antes de alterar: python -m pyflakes motor/royal.py

from motor import mercado

#region As receitas

ROYAIS = {
    'Royal Cowl':    ('cabeca', ('Scholar Cowl', 'Cleric Cowl', 'Mage Cowl')),
    'Royal Robe':    ('peito',  ('Scholar Robe', 'Cleric Robe', 'Mage Robe')),
    'Royal Sandals': ('pe',     ('Scholar Sandals', 'Cleric Sandals', 'Mage Sandals')),
    'Royal Hood':    ('cabeca', ('Mercenary Hood', 'Hunter Hood', 'Assassin Hood')),
    'Royal Jacket':  ('peito',  ('Mercenary Jacket', 'Hunter Jacket', 'Assassin Jacket')),
    'Royal Shoes':   ('pe',     ('Mercenary Shoes', 'Hunter Shoes', 'Assassin Shoes')),
    'Royal Helmet':  ('cabeca', ('Soldier Helmet', 'Knight Helmet', 'Guardian Helmet')),
    'Royal Armor':   ('peito',  ('Soldier Armor', 'Knight Armor', 'Guardian Armor')),
    'Royal Boots':   ('pe',     ('Soldier Boots', 'Knight Boots', 'Guardian Boots')),
}

SIGILS_POR_GRAU = {
    'cabeca': {4: 2, 5: 4, 6: 8, 7: 8, 8: 8},
    'pe':     {4: 2, 5: 4, 6: 8, 7: 8, 8: 8},
    'peito':  {4: 4, 5: 8, 6: 16, 7: 16, 8: 16},
}

# O Sigil no banco de precos: um item so, com o grau na combinacao (T4.0...).
SIGIL = 'Royal Sigil'

# O identificador do Sigil no jogo, que a rede manda: QUESTITEM_TOKEN_ROYAL_T4.
TRONCO_DO_SIGIL = 'QUESTITEM_TOKEN_ROYAL'

GRAUS = (4, 5, 6, 7, 8)
ENCANTAMENTOS = (0, 1, 2, 3, 4)


def itens_normais():
    """Os 27 itens normais que entram nas receitas, sem repetir."""

    return sorted({n for _, normais in ROYAIS.values() for n in normais})


def combinacoes(marcadas=None):
    """As (grau, ench) dos Royal - todas, ou so as <marcadas> para ler."""

    todas = [(g, e) for g in GRAUS for e in ENCANTAMENTOS]

    if marcadas is None:
        return todas

    marcadas = set(marcadas)

    return [(g, e) for g, e in todas if mercado.rotulo(g, e) in marcadas]


def sigils(royal, grau):
    """Quantos Sigils a receita de <royal> pede no <grau>."""

    return SIGILS_POR_GRAU[ROYAIS[royal][0]][grau]

#endregion

#region A conta


def _mais_barato(cidade, normais, rot, idade_maxima):
    """(item, preco) do item normal mais barato na cidade, ou (None, motivo)."""

    precos = []

    for nome in normais:
        preco, idade = mercado.ler(cidade, nome, rot)
        if preco is None:
            continue
        if idade_maxima is not None and idade > idade_maxima:
            continue
        precos.append((preco, nome))

    if not precos:
        return None, None

    preco, nome = min(precos)

    return nome, preco


def preco_do_sigil(cidade, grau):
    """O preco de um Sigil daquele grau na cidade, ou None."""

    preco, _ = mercado.ler(cidade, SIGIL, mercado.rotulo(grau, 0))

    return preco


def calcular(cidade, taxa, marcadas=None, idade_maxima=None):
    """(linhas, faltas): a conta de cada Royal em cada combinacao.

    <linhas> so traz as combinacoes com os tres precos, da que mais lucra para
    a que menos. <faltas> conta o que ficou de fora e por que - sem Buy Order
    no Mercado Negro, sem item normal na cidade, sem preco de Sigil."""

    linhas = []
    faltas = {'sem_buy_order': 0, 'sem_item_normal': 0, 'sem_sigil': 0}

    for royal, (_, normais) in ROYAIS.items():
        for grau, ench in combinacoes(marcadas):

            rot = mercado.rotulo(grau, ench)
            buy_order = mercado.ler_outro(mercado.MERCADO_NEGRO, royal, rot)
            _, idade = mercado.ler(mercado.MERCADO_NEGRO, royal, rot)

            if not buy_order or (idade_maxima is not None and idade is not None
                                 and idade > idade_maxima):
                faltas['sem_buy_order'] += 1
                continue

            normal, preco_normal = _mais_barato(cidade, normais, rot, idade_maxima)

            if normal is None:
                faltas['sem_item_normal'] += 1
                continue

            preco_sigil = preco_do_sigil(cidade, grau)

            if not preco_sigil:
                faltas['sem_sigil'] += 1
                continue

            quantos = sigils(royal, grau)
            custo = preco_normal + quantos * preco_sigil
            receita = int(buy_order * (1 - taxa))
            lucro = receita - custo

            linhas.append({
                'royal': royal, 'combinacao': rot,
                'buy_order': buy_order, 'receita': receita,
                'normal': normal, 'preco_normal': preco_normal,
                'sigils': quantos, 'preco_sigil': preco_sigil,
                'custo': custo, 'lucro': lucro,
                'margem': lucro / custo if custo else 0.0,
            })

    linhas.sort(key=lambda l: l['lucro'], reverse=True)

    return linhas, faltas

#endregion
