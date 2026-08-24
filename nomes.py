################################
#                              #
#            NOMES             #
#                              #
################################

# Como o nome de um item aparece na tela, e o que digitar para acha-lo.
#
# O JOGO PODE ESTAR EM DOIS IDIOMAS, e eles nao sao a mesma coisa com palavras
# diferentes - eles colocam o grau em lugares diferentes da frase:
#
#     portugues:   Espada Larga do Mestre
#     ingles:      Master's Broadsword
#
# Depois, contra antes. Toda a estrategia de busca vem disso.
#
#
# POR QUE EXISTIA O TRUQUE DO "do". A coluna AC guarda "Espada Larga do" - o nome
# sem o grau, terminado na preposicao. A razao esta registrada assim: buscar em
# ingles as vezes trazia outro item na frente, porque a lista sai em ordem
# alfabetica. O "do" no fim funcionava como marca de fim de nome.
#
# So que ele resolve pela metade. Com o grau DEPOIS, "Espada Larga do" nunca
# consegue ser um nome inteiro - sempre falta a ultima palavra, e o que estiver
# ali fica por conferir. Foi assim que "Cajado Amaldicoado do" chegou perto de
# casar com "Cajado Amaldicoado Elevado do", o problema que voce mesmo levantou.
#
#
# O QUE O INGLES DA DE GRACA. Com o grau na frente, o nome completo existe:
#
#     Expert's Cursed Staff          e     Expert's Great Cursed Staff
#
# Sao duas frases que divergem na SEGUNDA palavra. A comparacao posicional que ja
# esta no comum.parece_o_mesmo_item separa as duas na hora - e nao por pouco.
# Nao ha versao dessa frase em que uma seja o comeco da outra.
#
# Por isso a estrategia muda com o idioma:
#
#     digita       o nome base, sem grau ("Broadsword") - uma busca por item,
#                  como hoje, e os filtros de grau e encantamento fazem o resto
#
#     confere      o nome COMPLETO daquele grau ("Master's Broadsword") - a
#                  precisao mora aqui, e nao na caixa de busca
#
# Antes de alterar: python -m pyflakes nomes.py

#region Idioma

PORTUGUES = 'portugues'
INGLES = 'ingles'

IDIOMAS = (PORTUGUES, INGLES)

ROTULO_IDIOMA = {
    PORTUGUES: 'Português',
    INGLES: 'English',
}

# O padrao continua sendo o portugues: e o idioma em que a coluna AC foi escrita,
# e trocar sozinho quebraria os tres bots que ja funcionam.
_idioma = PORTUGUES


def idioma():
    return _idioma


def usar_idioma(novo):
    """Troca o idioma. Devolve o que ficou valendo.

    Silenciosamente ignorar um valor invalido seria pior que recusar: o bot
    seguiria buscando no idioma errado e reportando "item nao encontrado" nos
    121 itens, sem nada apontando para a causa."""

    global _idioma

    if novo in IDIOMAS:
        _idioma = novo

    return _idioma

#endregion

#region Graus

# Confirmado no wiki do jogo e nas telas: o grau e uma palavra, e ela e a mesma
# para todo item.
PREFIXO_INGLES = {
    1: "Beginner's",
    2: "Novice's",
    3: "Journeyman's",
    4: "Adept's",
    5: "Expert's",
    6: "Master's",
    7: "Grandmaster's",
    8: "Elder's",
}

# Em portugues o grau vira um complemento no fim. Estes quatro saem das telas do
# proprio jogo - "Espada Larga do Calouro" com Grau 1, "Arco do Adepto" com
# Grau 4, "Espada Larga do Mestre" no registro de uma compra T6.
#
# Os outros quatro NAO ESTAO AQUI de proposito. Nenhum bot precisa deles: em
# portugues quem busca e a coluna AC, que ja vem pronta da planilha, e quem
# confere aceita o complemento sem le-lo. Escrever de palpite o que ninguem usa
# seria plantar um erro para alguem encontrar daqui a seis meses.
SUFIXO_PORTUGUES = {
    1: 'do Calouro',
    4: 'do Adepto',
    5: 'do Perito',
    6: 'do Mestre',
}

#endregion

#region Composicao


def prefixo(grau):
    """"Master's" para o grau 6. String vazia se o grau nao for conhecido."""

    return PREFIXO_INGLES.get(grau, '')


def completo(base, grau):
    """O nome como ele aparece na tela do jogo, em ingles.

    'Broadsword' + 6 -> "Master's Broadsword"
    """

    p = prefixo(grau)

    return f'{p} {base}'.strip() if p else base


def termo(base_ingles, busca_portugues, ling=None):
    """O que digitar na caixa de busca.

    Em ingles e o nome BASE, sem grau: uma busca por item, e os filtros de grau e
    encantamento percorrem as 13 combinacoes sem redigitar nada. Digitar o nome
    completo obrigaria a uma busca nova a cada combinacao - treze buscas por item
    em vez de uma, e a busca e a parte lenta.

    Em portugues e a coluna AC como ela esta."""

    if (ling or _idioma) == INGLES:
        return (base_ingles or '').strip()

    return (busca_portugues or '').strip()


def na_tela(base_ingles, busca_portugues, grau, ling=None):
    """O nome que se espera LER na linha, para conferir que e o item certo.

    Aqui mora a precisao. Em ingles devolve o nome completo daquele grau, que e
    uma frase inteira e nao o comeco de uma; em portugues devolve o que a coluna
    AC tem, e o complemento de grau que vier depois fica por conferir - e o
    melhor que da para fazer com o grau no fim da frase."""

    if (ling or _idioma) == INGLES:
        return completo((base_ingles or '').strip(), grau)

    return (busca_portugues or '').strip()

#endregion
