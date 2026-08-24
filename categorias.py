################################
#                              #
#         CATEGORIAS           #
#                              #
################################

# O caminho de menu que SELECIONA um item no mercado, em vez de procurar por ele.
#
# O mercado tem um menu em cascata:
#
#     Weapons  ->  Crossbow  ->  Crossbow
#                               Heavy Crossbow
#                               Light Crossbow
#                               ...
#
# Escolhido o item na ponta, A LISTA PASSA A CONTER SO ELE. Isso encerra um
# problema que este programa vinha combatendo por outros meios desde o comeco:
# descobrir, LENDO a tela, se a lista mostrava o item certo. O truque do "do" no
# fim do nome, a comparacao posicional de palavras, o item "A" que casava com o
# item "A ELEVADO" - tudo isso era jeito de adivinhar o que agora deixa de ser
# pergunta.
#
# E sai mais barato. Sem a duvida, ler uma linha custa um OCR de preco e nao dois
# - o de nome deixa de ser necessario. Numa lista de cinco linhas, e metade da
# leitura.
#
#
# A GEOMETRIA E A MESMA DE SEMPRE. Medida em vinte e sete capturas do menu
# aberto, uma por familia:
#
#     todos os niveis usam passo de 27 px, o mesmo dos dropdowns de grau e
#     encantamento - este jogo tem uma grade so;
#
#     um submenu abre com a PRIMEIRA entrada dele ("All") na mesma altura do item
#     que o abriu, 135 px a direita.
#
# Disso sai uma conta e nao uma tabela de coordenadas: a altura de qualquer item
# do menu e o indice dele vezes 27, somado a altura do pai.
#
# Entradas de duas linhas - "Gathering Equipment", "Double Bladed Staff",
# "Graveguard Helmet" - ocupam a MESMA fatia de 27 px, so com as duas linhas mais
# juntas. A grade nao quebra, e foi conferido nas capturas.
#
#
# NEM TODA CATEGORIA TEM TRES NIVEIS. Capes e Bags param no segundo: em Capes o
# proprio item ja esta ali ("Cape", "Demon", "Keeper"), e nao ha submenu para
# abrir. Tratar todo mundo como se fosse igual faria o bot esperar um menu que
# nunca vem.
#
#
# POSICAO CALCULADA, NOME CONFERIDO. A posicao diz onde clicar; antes de clicar,
# le-se o que esta la. O jogo acrescenta armas - so a familia Espada tem oito -
# e uma posicao decorada envelheceria em silencio, selecionando o vizinho do item
# certo. Calcular e barato, conferir e barato, e errado sai caro.
#
# Antes de alterar: python -m pyflakes categorias.py

#region Geometria do menu

# Passo entre entradas, em qualquer nivel.
MENU_PASSO = 27

# Quanto um submenu se desloca para a direita em relacao ao pai.
MENU_DESLOCAMENTO = 135

# x do centro de cada nivel.
MENU_X = (815, 950, 1085)

# y da PRIMEIRA entrada do primeiro nivel ("All"), com o menu aberto.
MENU_PRIMEIRA_Y = 297

# O botao que abre tudo.
MENU_BOTAO = {'x': 815, 'y': 268}

# Faixa de uma entrada, para ler o que esta sob o cursor antes de clicar.
# Estreita no x de proposito: o triangulo de submenu no canto direito vira lixo
# no OCR.
MENU_LARGURA = 120
MENU_ALTURA = 22


def posicao(indices):
    """Onde clicar, dados os indices de cada nivel. {'x':, 'y':}.

        posicao([1])        -> Weapons
        posicao([1, 2])     -> Weapons > Crossbow
        posicao([1, 2, 1])  -> Weapons > Crossbow > Crossbow
    """

    y = MENU_PRIMEIRA_Y

    for i in indices:
        y += i * MENU_PASSO

    return {'x': MENU_X[len(indices) - 1], 'y': y}


def regiao(indices):
    """A faixa de tela daquela entrada, para ler o nome antes de clicar."""

    p = posicao(indices)

    return (p['x'] - MENU_LARGURA // 2, p['y'] - MENU_ALTURA // 2,
            p['x'] + MENU_LARGURA // 2, p['y'] + MENU_ALTURA // 2)

#endregion

#region O primeiro nivel

# Conferido na tela: a lista completa, na ordem, com "All" em zero.
CATEGORIAS = [
    'All',
    'Weapons',
    'Chest Armor',
    'Head Armor',
    'Foot Armor',
    'Off-Hands',
    'Capes',
    'Bags',
    'Mount',
    'Consumable',
    'Gathering Equipment',
    'Crafting',
    'Artifact',
    'Farming',
    'Furniture',
    'Vanity',
    'Other',
]

#endregion

#region Categorias de tres niveis

# CONFERIDO ITEM POR ITEM nas capturas do menu, uma por familia. Cada lista esta
# na ordem em que aparece na tela, e o "All" que encabeca todas fica implicito -
# o indice de um item e a posicao dele aqui, mais um.
#
# A ORDEM DO JOGO NAO E A DA PLANILHA. Nas armaduras:
#
#     planilha:  Scholar, Cleric, Mage, Royal,  Druid
#     menu:      Scholar, Cleric, Mage, Druid,  Royal
#
# Royal e Druid trocados - e o mesmo entre Stalker e Royal no couro, e entre
# Graveguard e Royal na placa. Como a altura sai do indice, usar a ordem da
# planilha clicaria no vizinho e compraria outra coisa.
#
# Os artefatos ficam listados mesmo sem estarem na planilha. Nao custam nada
# aqui, e no dia em que um deles entrar na sua lista o caminho ja existe.
TRES_NIVEIS = {

    'Weapons': [
        ('Bow', ('Bow', 'Longbow', 'Warbow', 'Whispering Bow', 'Wailing Bow',
                 'Bow of Badon', 'Mistpiercer', 'Skystrider Bow')),
        ('Crossbow', ('Crossbow', 'Heavy Crossbow', 'Light Crossbow',
                      'Weeping Repeater', 'Boltcasters', 'Siegebow',
                      'Energy Shaper', 'Arclight Blasters')),
        ('Axe', ('Battleaxe', 'Greataxe', 'Halberd', 'Carrioncaller',
                 'Infernal Scythe', 'Bear Paws', 'Realmbreaker',
                 'Crystal Reaper')),
        ('Dagger', ('Dagger', 'Dagger Pair', 'Claws', 'Bloodletter',
                    'Demon Fang', 'Deathgivers', 'Bridled Fury',
                    'Twin Slayers')),
        ('Hammer', ('Hammer', 'Great Hammer', 'Polehammer', 'Tombhammer',
                    'Forge Hammers', 'Grovekeeper', 'Hand of Justice',
                    'Truebolt Hammer')),
        ('War Gloves', ('Brawler Gloves', 'Battle Bracers', 'Spiked Gauntlets',
                        'Ursine Maulers', 'Hellfire Hands',
                        'Ravenstrike Cestus', 'Fists of Avalon',
                        'Forcepulse Bracers')),
        ('Mace', ('Mace', 'Heavy Mace', 'Morning Star', 'Bedrock Mace',
                  'Incubus Mace', 'Camlann Mace', 'Oathkeepers',
                  'Dreadstorm Monarch')),
        ('Quarterstaff', ('Quarterstaff', 'Iron-clad Staff',
                          'Double Bladed Staff', 'Black Monk Staff',
                          'Soulscythe', 'Staff of Balance', 'Grailseeker',
                          'Phantom Twinblade')),
        ('Spear', ('Spear', 'Pike', 'Glaive', 'Heron Spear', 'Spirithunter',
                   'Trinity Spear', 'Daybreaker', 'Rift Glaive')),
        ('Sword', ('Broadsword', 'Claymore', 'Dual Swords', 'Clarent Blade',
                   'Carving Sword', 'Galatine Pair', 'Kingmaker',
                   'Infinity Blade')),
        ('Arcane Staff', ('Arcane Staff', 'Great Arcane Staff',
                          'Enigmatic Staff', 'Witchwork Staff', 'Occult Staff',
                          'Malevolent Locus', 'Evensong', 'Astral Staff')),
        ('Cursed Staff', ('Cursed Staff', 'Great Cursed Staff', 'Demonic Staff',
                          'Lifecurse Staff', 'Cursed Skull', 'Damnation Staff',
                          'Shadowcaller', 'Rotcaller Staff')),
        ('Fire Staff', ('Fire Staff', 'Great Fire Staff', 'Infernal Staff',
                        'Wildfire Staff', 'Brimstone Staff', 'Blazing Staff',
                        'Dawnsong', 'Flamewalker Staff')),
        ('Frost Staff', ('Frost Staff', 'Great Frost Staff', 'Glacial Staff',
                         'Hoarfrost Staff', 'Icicle Staff', 'Permafrost Prism',
                         'Chillhowl', 'Arctic Staff')),
        ('Holy Staff', ('Holy Staff', 'Great Holy Staff', 'Divine Staff',
                        'Lifetouch Staff', 'Fallen Staff', 'Redemption Staff',
                        'Hallowfall', 'Exalted Staff')),
        ('Nature Staff', ('Nature Staff', 'Great Nature Staff', 'Wild Staff',
                          'Druidic Staff', 'Blight Staff', 'Rampant Staff',
                          'Ironroot Staff', 'Forgebark Staff')),
        ('Shapeshifter Staff', ('Prowling Staff', 'Rootbound Staff',
                                'Primal Staff', 'Bloodmoon Staff',
                                'Hellspawn Staff', 'Earthrune Staff',
                                'Lightcaller', 'Stillgaze Staff')),
    ],

    'Chest Armor': [
        ('Cloth Robes', ('Scholar Robe', 'Cleric Robe', 'Mage Robe',
                         'Druid Robe', 'Royal Robe', 'Fiend Robe',
                         'Cultist Robe', 'Feyscale Robe', 'Robe of Purity')),
        ('Leather Jackets', ('Mercenary Jacket', 'Hunter Jacket',
                             'Assassin Jacket', 'Stalker Jacket',
                             'Royal Jacket', 'Hellion Jacket',
                             'Specter Jacket', 'Mistwalker Jacket',
                             'Jacket of Tenacity')),
        ('Plate Armor', ('Soldier Armor', 'Knight Armor', 'Guardian Armor',
                         'Graveguard Armor', 'Royal Armor', 'Demon Armor',
                         'Judicator Armor', 'Duskweaver Armor',
                         'Armor of Valor')),
    ],

    'Head Armor': [
        ('Cloth Cowl', ('Scholar Cowl', 'Cleric Cowl', 'Mage Cowl',
                        'Druid Cowl', 'Royal Cowl', 'Fiend Cowl',
                        'Cultist Cowl', 'Feyscale Hat', 'Cowl of Purity')),
        ('Leather Hood', ('Mercenary Hood', 'Hunter Hood', 'Assassin Hood',
                          'Stalker Hood', 'Royal Hood', 'Hellion Hood',
                          'Specter Hood', 'Mistwalker Hood',
                          'Hood of Tenacity')),
        ('Plate Helmet', ('Soldier Helmet', 'Knight Helmet', 'Guardian Helmet',
                          'Graveguard Helmet', 'Royal Helmet', 'Demon Helmet',
                          'Judicator Helmet', 'Duskweaver Helmet',
                          'Helmet of Valor')),
    ],

    'Foot Armor': [
        ('Cloth Sandals', ('Scholar Sandals', 'Cleric Sandals', 'Mage Sandals',
                           'Druid Sandals', 'Royal Sandals', 'Fiend Sandals',
                           'Cultist Sandals', 'Feyscale Sandals',
                           'Sandals of Purity')),
        ('Leather Shoes', ('Mercenary Shoes', 'Hunter Shoes', 'Assassin Shoes',
                           'Stalker Shoes', 'Royal Shoes', 'Hellion Shoes',
                           'Specter Shoes', 'Mistwalker Shoes',
                           'Shoes of Tenacity')),
        ('Plate Boots', ('Soldier Boots', 'Knight Boots', 'Guardian Boots',
                         'Graveguard Boots', 'Royal Boots', 'Demon Boots',
                         'Judicator Boots', 'Duskweaver Boots',
                         'Boots of Valor')),
        # o Foot Armor tem um "Other" no fim que as outras nao tem
        ('Other', ()),
    ],

    # As tres familias sao por ARQUETIPO, e nao por material.
    'Off-Hands': [
        ('Mage', ('Tome of Spells', 'Eye of Secrets', 'Muisak', 'Taproot',
                  'Celestial Censer', 'Timelocked Grimoire')),
        ('Hunter', ('Torch', 'Mistcaller', 'Leering Cane', 'Cryptcandle',
                    'Sacred Scepter', 'Blueflame Torch')),
        ('Warrior', ('Shield', 'Sarcophagus', 'Caitiff Shield', 'Facebreaker',
                     'Astral Aegis', 'Unbreakable Ward')),
    ],
}

#endregion

#region Categorias de dois niveis

# Aqui o item ESTA no segundo nivel, e nao ha submenu para abrir.
#
# Nas capas o menu escreve so a faccao - "Demon", "Keeper" - sem a palavra
# "Cape" que a planilha usa. Nas bolsas ele escreve no plural e por extenso.
# Ver NOME_NO_MENU.
DOIS_NIVEIS = {
    'Capes': ('Cape', 'Bridgewatch', 'Fort Sterling', 'Lymhurst', 'Martlock',
              'Thetford', 'Caerleon', 'Brecilien', 'Heretic', 'Undead',
              'Keeper', 'Morgana', 'Avalonian', 'Demon', 'Smuggler'),

    'Bags': ('Bags', 'Satchels of Insight'),
}

#endregion

#region Nomes

# A PLANILHA E O MENU DISCORDAM EM NOVE NOMES.
#
# Nao da para simplesmente corrigir a planilha: ela e sua, e as duas colunas de
# nome tem donos diferentes - a coluna A e como voce escreveu, e o menu e como o
# jogo escreveu. Traduzir de uma para a outra e trabalho deste modulo.
NOME_NO_MENU = {
    # duas palavras onde a planilha usa uma, e um "Stave" que virou "Staff"
    'Greathammer': 'Great Hammer',
    'Black Monk Stave': 'Black Monk Staff',

    # nas capas o menu poe so a faccao
    'Demon Cape': 'Demon',
    'Undead Cape': 'Undead',
    'Morgana Cape': 'Morgana',
    'Keeper Cape': 'Keeper',
    'Heretic Cape': 'Heretic',

    # e nas bolsas, o plural por extenso
    'Bag': 'Bags',
    'Satchel': 'Satchels of Insight',
}

#endregion

#region Consulta

_caminho = {}

for _cat, _subs in TRES_NIVEIS.items():
    for _sub, _itens in _subs:
        for _item in _itens:
            _caminho[_item] = (_cat, _sub)

for _cat, _itens in DOIS_NIVEIS.items():
    for _item in _itens:
        _caminho[_item] = (_cat, None)


def no_menu(item):
    """O nome do item como o MENU escreve. Pode diferir do da planilha."""

    return NOME_NO_MENU.get(item, item)


def caminho(item):
    """(categoria, subcategoria) do item, ou None se ele nao estiver mapeado.

    A subcategoria vem None quando a categoria so tem dois niveis - o item ja
    esta la. Isso e diferente de o proprio retorno ser None, que quer dizer "nao
    sei onde fica". Quem chama tem que separar os dois, senao um item novo na
    planilha vira uma navegacao para o lugar errado em vez de um aviso."""

    return _caminho.get(no_menu(item))


def indices(item):
    """Os indices de menu do item - dois ou tres numeros - ou None.

    O indice conta o "All" que encabeca toda lista como zero; por isso os +1.

    Dois numeros quando a categoria para no segundo nivel (Capes, Bags), tres
    quando ela desce ate o item. Quem navega olha o TAMANHO da lista para saber
    quantos submenus vai abrir."""

    alvo = no_menu(item)
    onde = _caminho.get(alvo)

    if onde is None:
        return None

    categoria, sub = onde

    if categoria not in CATEGORIAS:
        return None

    i1 = CATEGORIAS.index(categoria)

    if sub is None:
        return [i1, DOIS_NIVEIS[categoria].index(alvo) + 1]

    subs = TRES_NIVEIS[categoria]
    nomes = [s for s, _ in subs]
    itens = dict(subs)[sub]

    return [i1, nomes.index(sub) + 1, itens.index(alvo) + 1]


def rotulos(item):
    """Os NOMES que o bot vai ler para confirmar cada clique.

    A posicao diz onde clicar; isto diz o que tem que estar escrito la. O jogo
    acrescenta armas - so a familia Espada tem oito - e uma posicao decorada
    envelheceria em silencio, selecionando o vizinho do item certo."""

    onde = _caminho.get(no_menu(item))

    if onde is None:
        return None

    categoria, sub = onde

    return [categoria, no_menu(item)] if sub is None else \
           [categoria, sub, no_menu(item)]


def navegavel(item):
    return indices(item) is not None


def conhecido(item):
    return no_menu(item) in _caminho


def por_confirmar():
    """Itens que nao tem posicao conferida na tela. Vazio e o objetivo."""

    return sorted(i for i in _caminho if indices(i) is None)


def itens_mapeados():
    return sorted(_caminho)


# Itens cujo nome esta CONTIDO no nome de outro item.
#
# A busca por texto do jogo devolve tudo que contem o que voce digitou, e a
# lista sai em ordem alfabetica - digitar "Cursed Staff" traz o "Great Cursed
# Staff" junto, e digitar "Bow" traz "Crossbow", "Warbow" e mais seis. Para
# estes o texto nao basta, e a selecao tem de ser pelo menu.
#
# Sao 18 dos 252. Os outros 234 vao pela busca, que e bem mais rapida que tres
# passadas de mouse pelo menu em cascata.
_AMBIGUOS = None


def ambiguo(item):
    """True se o nome deste item aparece dentro do nome de outro."""

    global _AMBIGUOS

    if _AMBIGUOS is None:
        todos = itens_mapeados()
        _AMBIGUOS = {a for a in todos
                     if any(a != b and a.lower() in b.lower() for b in todos)}

    return no_menu(item) in _AMBIGUOS


def ambiguos():
    """Os itens que precisam do menu. Ordenados, para o log."""

    ambiguo('')          # forca o calculo

    return sorted(_AMBIGUOS)


def familias_de(categoria):
    """As subcategorias de uma categoria, na ordem do menu."""

    return [s for s, _ in TRES_NIVEIS.get(categoria, [])]

#endregion
