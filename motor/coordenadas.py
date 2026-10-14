################################
#                              #
#         COORDENADAS          #
#                              #
################################

# Todas as posicoes de clique e regioes de leitura, num lugar so.
#
# Antes elas viviam espalhadas pelos tres bots, e a regiao do preco aparecia DUAS
# VEZES com o mesmo valor - o comentario do bot_vender explicava que tinha sido
# copiada do bot_atualizar depois de uma correcao. Funcionou daquela vez. Na
# proxima, alguem atualizaria uma e esqueceria a outra, e o resultado seria um bot
# certo e o outro errado, que e a pior forma de estar quebrado.
#
# TUDO AQUI FOI MEDIDO EM 1920x1080, com o jogo em tela cheia no monitor
# primario. Em outra resolucao os cliques caem no lugar errado - o app confere e
# avisa antes de comecar.
#
# As posicoes de opcao de dropdown sao CALCULADAS, nao escritas a mao: as listas
# tem passo regular, e uma constante de passo se corrige numa linha enquanto oito
# numeros soltos exigem remedir oito.
#
# Um coordenadas.json ao lado do programa sobrescreve qualquer valor daqui. E o
# gancho por onde um calibrador entra depois, sem que nada mais precise mudar.

import json
import os

from motor import comum

RESOLUCAO_BASE = (1920, 1080)

ARQUIVO_PERFIL = os.path.join(comum.PASTA_DADOS, 'coordenadas.json')

#region Painel de Pedido de Venda

# Usado pelo bot Atualizar e pelo bot Vender.

# Primeiro preco da lista "Pedidos de venda".
# x: 1016 comeca depois do icone da moeda (termina em 1016) e vai ate 1100,
#    logo antes da coluna Quantidade (comeca em 1106) - cabe ate 4.699.982
# y: 362-381 com folga em volta do texto, que fica em 367-376.
#    o valor antigo comecava em 368 e cortava o topo dos digitos (6 lia como 0),
#    o que no Atualizar gravava numero errado na planilha e no Vender geraria uma
#    ORDEM DE VENDA a preco errado
PRECO_VENDA = (1016, 362, 1100, 381)

# Icone e nome do primeiro item da lista "Vender do Inventario". Serve para
# esperar a busca terminar de filtrar: se o clique em "Vender" chegar antes, ele
# abre o painel do item que ainda estava na primeira linha.
LINHA_ITEM = (585, 415, 950, 448)

# Apenas o digito do rotulo do dropdown de grau ("Grau 7" -> o "7").
# O recorte e justo de proposito: com mais folga a letra "u" de "Grau" entra no
# quadro e o OCR devolve "17" em vez de "7". Como o rotulo e alinhado a esquerda
# e sempre tem um digito so, a posicao e estavel.
GRAU_ROTULO = (494, 388, 508, 403)

# tela principal do Mercado Negro
VND_RESET   = {'x': 720,  'y': 270}
VND_BUSCA   = {'x': 640,  'y': 270}
VND_VENDER  = {'x': 1280, 'y': 435}   # botao "Vender" do primeiro item da lista

# painel de Pedido de Venda
VND_FECHAR   = {'x': 940, 'y': 315}
VND_BARRA_TIER = {'x': 520, 'y': 405}
VND_BARRA_ENCH = {'x': 665, 'y': 405}

# Os dois dropdowns tem o mesmo formato: a primeira opcao fica em y=423 e cada
# opcao seguinte 27 px abaixo. Medido com ampliacao de 5x no dropdown aberto.
VND_DROPDOWN_TOPO  = 423
VND_DROPDOWN_PASSO = 27

# Meia largura e meia altura da faixa usada para detectar a abertura do dropdown.
# 40 px de cada lado do centro cabem dentro das duas caixas (a de grau ocupa
# x 452-586, a de encantamento x 606-739); 11 px cobrem a altura de uma opcao,
# que tem passo de 27 px.
VND_DETECCAO_MEIA_LARGURA = 40
VND_DETECCAO_MEIA_ALTURA = 11

#endregion

#region Republicacao (bot Vender)

# O painel de venda do proprio item, diferente da lista de pedidos acima.
VER_VENDER_1 = {'x': 1275, 'y': 435}   # botao "Vender" do item
VER_VENDER_2 = {'x': 880,  'y': 735}   # CONFIRMAR a venda
VER_BUSCA    = {'x': 820,  'y': 400}
VER_NORMAL   = {'x': 820,  'y': 430}   # filtro de qualidade
VER_PRECO    = {'x': 655,  'y': 640}   # campo de preco
VER_DIMINUIR = {'x': 560,  'y': 640}   # botao de diminuir 1 de prata
VER_FECHAR   = {'x': 937,  'y': 310}   # fechar o painel

#endregion

#region Tela de COMPRA

# Filtros da tela principal do Mercado Negro, aba de compra. Diferentes das do
# painel de Pedido de Venda acima.
CMP_BUSCA   = {'x': 640,  'y': 270}
CMP_RESET   = {'x': 720,  'y': 270}
CMP_BARRA_TIER = {'x': 960,  'y': 270}
CMP_BARRA_ENCH = {'x': 1100, 'y': 270}

# Zera os filtros de grau e encantamento, devolvendo a lista a "Todos".
#
# O jogo GUARDA o filtro entre uma busca e outra. Sem este clique, o item
# seguinte nasce com o filtro em que o anterior terminou - o T8.2, que e a
# ultima combinacao da lista - e a lista aparece vazia ou mostrando so uma faixa.
CMP_LIMPAR_FILTROS = {'x': 1335, 'y': 270}

# COMPRAR SAO TRES CLIQUES, nesta ordem:
#
#   1. Comprar na linha da oferta   -> abre o painel de compra
#   2. Comprar dentro do painel     -> pede a compra
#   3. Sim no dialogo               -> confirma, e so agora a prata sai
#
# O terceiro faltava. E os dois primeiros estao certos como estao - nao troque
# um pelo outro achando que sao a mesma coisa.
CMP_COMPRAR_1 = {'x': 1275, 'y': 430}   # 1. na linha da oferta
CMP_COMPRAR_2 = {'x': 880,  'y': 735}   # 2. dentro do painel

# O "X" que FECHA o painel de compra (o que o clique 1 abriu).
#
# Recusar no dialogo fecha SO O DIALOGO - o painel continua na tela, por cima da
# lista. Dai em diante todo clique cai no painel e toda leitura le o painel: o
# preco da "proxima oferta" e o que estiver naquele pedaco do painel, os filtros
# nao trocam, e o bot segue achando que esta olhando a lista.
CMP_FECHAR_PAINEL = {'x': 937, 'y': 305}

# 3. O "Sim" do dialogo "Quer comprar 1 unidades de <item> por <preco>?".
# MEDIDO na tela.
CMP_CONFIRMAR_SIM = {'x': 860, 'y': 550}

# O "Nao" do mesmo dialogo, para RECUSAR a compra.
#
# DERIVADO da posicao do "Sim" e do print do dialogo, nao medido - vale conferir
# no calibrador. Se estiver errado, o dialogo fica aberto e a proxima compra
# falha em vez de sair errada, que e o lado seguro do erro.
CMP_NAO_COMPRAR = {'x': 1100, 'y': 550}

# O texto do dialogo: "Quer comprar 1 unidades de <item> por <preco> de prata?"
#
# ESTA E A MELHOR FONTE DE VERDADE DO PROGRAMA INTEIRO. Todo o resto e leitura
# de uma lista que pode ter mudado entre a leitura e o clique; aqui e o proprio
# jogo dizendo, em numero, quanto vai cobrar - antes de cobrar.
#
# DERIVADO tambem: o enquadramento saiu do print do dialogo somado a posicao
# medida do "Sim". Se o recorte estiver fora, o OCR nao le nada e a compra segue
# com um aviso no resumo - nunca o contrario.
CMP_DIALOGO_COMPRA = (780, 428, 1190, 495)

#region Painel do item (pedido de compra e livro de ofertas)

# Medido na tela "Espada Larga do Calouro" do mercado de Caerleon.
#
# ATENCAO: O PAINEL DO MERCADO NEGRO TEM MENOS OPCOES. La so existem "Vender" e
# "Pedido de Venda"; na cidade sao quatro, e cada uma empurra a de baixo 27 px.
# Usar a mesma coordenada nas duas telas clica na acao errada.
# Onde clicar na LISTA para abrir o painel de um item: em cima do nome, e nao no
# botao Comprar - o botao compra uma unidade, o nome abre o painel com o livro de
# ofertas e o pedido de compra.
#
# DERIVADO do enquadramento do nome, nao medido. Se estiver errado, o painel nao
# abre e a compra para dizendo isso - o lado seguro do erro.
PAINEL_ABRIR = {'x': 780, 'y': 430}

PAINEL_VENDER          = {'x': 562, 'y': 453}
PAINEL_COMPRAR         = {'x': 562, 'y': 481}
PAINEL_PEDIDO_DE_VENDA = {'x': 562, 'y': 508}
PAINEL_PEDIDO_DE_COMPRA = {'x': 562, 'y': 535}

# No Mercado Negro, so duas
BM_VENDER          = {'x': 562, 'y': 453}
BM_PEDIDO_DE_VENDA = {'x': 562, 'y': 481}

# Quantia: barra com menos de um lado e mais do outro.
PAINEL_QTD_MENOS = {'x': 562, 'y': 594}
PAINEL_QTD_MAIS  = {'x': 862, 'y': 594}
PAINEL_QTD_BARRA = {'x': 710, 'y': 594}
PAINEL_QTD_VALOR = (560, 562, 600, 585)

# Preco: mesma coisa, uma linha abaixo.
PAINEL_PRECO_MENOS = {'x': 566, 'y': 629}
PAINEL_PRECO_MAIS  = {'x': 858, 'y': 629}
PAINEL_PRECO_CAMPO = {'x': 640, 'y': 629}
PAINEL_PRECO_VALOR = (600, 618, 700, 642)

# "1 (2.5% Taxa de ordem)" e o "Total" logo abaixo.
PAINEL_TAXA  = (550, 648, 780, 672)
PAINEL_TOTAL = (550, 715, 720, 742)

PAINEL_CRIAR  = {'x': 881, 'y': 729}
PAINEL_FECHAR = {'x': 937, 'y': 305}

# --- O LIVRO DE OFERTAS ---------------------------------------------------
#
# Duas colunas, "Pedidos de venda" e "Pedidos de compra", com seis linhas
# visiveis e passo de 27 px - a mesma grade de todo o resto deste jogo.
#
# E daqui que sai o tamanho de uma ordem de compra: quantas unidades existem a
# um preco que ainda paga. Sem ler isto, a unica forma de saber seria comprando.
LIVRO_PRIMEIRA_Y = 371
LIVRO_PASSO = 27
LIVRO_LINHAS = 6


def venda_preco(n):
    """Preco da n-esima linha de "Pedidos de venda"."""

    y = LIVRO_PRIMEIRA_Y + n * LIVRO_PASSO

    return (1000, y - 11, 1095, y + 11)


def venda_quantidade(n):
    y = LIVRO_PRIMEIRA_Y + n * LIVRO_PASSO

    return (1100, y - 11, 1185, y + 11)


def compra_preco(n):
    """Preco da n-esima linha de "Pedidos de compra"."""

    y = LIVRO_PRIMEIRA_Y + n * LIVRO_PASSO

    return (1245, y - 11, 1340, y + 11)


def compra_quantidade(n):
    y = LIVRO_PRIMEIRA_Y + n * LIVRO_PASSO

    return (1370, y - 11, 1450, y + 11)


# Onde o jogo avisa que nao ha pedido de compra nenhum:
# "NO MOMENTO NINGUEM ESTA COMPRANDO ESTE ITEM NO MERCADO"
LIVRO_AVISO_VAZIO = (1240, 360, 1470, 420)

PRECO_MEDIO = (1370, 703, 1475, 728)

#endregion

#region Lista "Comprar do Mercado"

# A LISTA TEM CINCO LINHAS, com passo de 90 px - medido nas capturas do mercado
# de Caerleon. E a linha 1 cai exatamente em cima do que ja estava calibrado no
# Mercado Negro: e o mesmo componente, na mesma altura, nas duas telas.
#
# Por isso nao ha coordenada nova aqui embaixo, e sim uma constante de passo. As
# outras quatro linhas sao a primeira deslocada de 90, 180, 270 e 360.
LISTA_PASSO = 90
LISTA_LINHAS = 5


def linha_nome(n):
    """Regiao do nome da n-esima linha, contando do zero."""

    x1, y1, x2, y2 = CMP_LINHA_ITEM
    dy = n * LISTA_PASSO

    return (x1, y1 + dy, x2, y2 + dy)


def linha_preco(n):
    """Regiao do preco da n-esima linha."""

    x1, y1, x2, y2 = PRECO_COMPRA
    dy = n * LISTA_PASSO

    return (x1, y1 + dy, x2, y2 + dy)


def linha_botao(n):
    """O botao Comprar da n-esima linha."""

    return {'x': CMP_COMPRAR_1['x'], 'y': CMP_COMPRAR_1['y'] + n * LISTA_PASSO}


# A ORDENACAO DA LISTA. Fica em "Price - Lowest" - e o filtro que o video chama
# de "price filter, selecting lowest price is recommended".
#
# Nao e enfeite: com ele a oferta mais barata esta sempre na PRIMEIRA linha, e ai
# uma leitura basta para saber o preco de uma combinacao. Sem ele seria preciso
# ler as cinco e ainda assim nao haveria certeza, porque a mais barata poderia
# estar na pagina seguinte.
LISTA_ORDEM = {'x': 1180, 'y': 359}

# Paginacao, no rodape da lista.
LISTA_PAGINA_ANTERIOR = {'x': 927, 'y': 886}
LISTA_PAGINA_SEGUINTE = {'x': 990, 'y': 886}
LISTA_NUMERO_DA_PAGINA = (940, 872, 980, 900)

#endregion

# Preco da oferta mais barata, na aba de compra.
# MEDIDO EM CIMA DO QUE O BOT CAPTUROU, e nao estimado de um print.
#
# A borda esquerda estava em 1070 e os numeros comecam alguns pixels antes: os
# tres recortes guardados em testes/amostras mostram o primeiro digito faltando
# 1,3 a 2,5 px. Nao e detalhe estetico - o "5" de 540.000 raspado desse tanto e
# lido como 9, e o numero entra no banco como 940.000 com confianca 79. Foi este
# o defeito relatado como "le 5 como 9" e como "le 599.999 como 399.999".
#
# 1064 da 3,5 px de folga alem do pior caso medido, e continua bem a direita do
# icone da moeda - que nao aparece em nenhum dos tres recortes.
#
# A direita sobra de proposito: o numero mais longo visto ocupa 60 px dos 106.
PRECO_COMPRA = (1064, 412, 1170, 450)

# A LINHA INTEIRA da primeira oferta: icone, nome, tempo restante e preco.
#
# Serve para confirmar que uma compra aconteceu. Olhar so o preco NAO basta, e
# isto e comum: quem vende copia o preco de quem esta na frente, e a lista tem
# duas ofertas seguidas a 349.999. Consumida a primeira, a regiao do preco fica
# pixel a pixel identica - o bot concluia que a compra nao tinha acontecido,
# e duas dessas em sequencia faziam ele abandonar a combinacao.
#
# Na linha inteira sempre ha o que mudar: o tempo restante ("29 d 21 h" contra
# "29 d 22 h") e a quantidade no canto do icone sao de cada oferta.
CMP_LINHA_OFERTA = (595, 400, 1180, 460)

# Nome do item da oferta que esta sendo avaliada. Confirmar que a busca filtrou
# para o item certo exige olhar para ele - esperar so o preco mudar nao prova
# nada sobre QUAL item esta na tela.
#
# So a COLUNA DO NOME. A faixa anterior comecava em 600 e ia ate 1050, o que
# pegava o icone do item de um lado e o tempo de expiracao do outro - e o OCR
# devolvia 'age do 29d23h' no lugar de 'Cajado Amaldicoado do'. O icone vira
# letras inventadas e o "29d23h" entra no meio do nome.
CMP_LINHA_ITEM = (662, 405, 905, 455)

# As listas comecam com "Todos" e seguem com passo de 27 px:
#
#   grau:  Todos(300) G1(327) G2(354) ... G5(435) G6(462) G7(489) G8(516)
#   ench:  Todos(298) e0(325) e1(352) e2(379) e3(406)
#
# Antes estes oito valores eram constantes escritas a mao - 435, 465, 485, 515 e
# 325, 355, 375, 405 - cada uma errando de 0 a 4 px em relacao a grade. Cabiam na
# faixa de 27 px e por isso funcionavam, mas ninguem sabia de onde tinham vindo, e
# uma mudanca de uma linha na interface do jogo exigiria remedir as oito.
CMP_TIER_TOPO  = 300     # centro da opcao "Todos" do filtro de grau
CMP_ENCH_TOPO  = 298     # centro da opcao "Todos" do filtro de encantamento
CMP_DROPDOWN_PASSO = 27

# O FILTRO DE QUALIDADE da tela de compra.
#
# NAO FOI MEDIDO NUMA CAPTURA. Os numeros abaixo sao um palpite pela grade da
# barra - ele fica entre o encantamento (x=1100) e o botao de limpar (x=1335) - e
# por isso a compra por qualidade SO RODA DEPOIS DE CALIBRAR estas duas marcas:
# um clique na opcao errada compraria outra qualidade, gastando prata no item
# errado. Ver calibrado().
CMP_BARRA_QUAL = {'x': 1220, 'y': 270}
CMP_QUAL_TOPO = 300      # centro da opcao "Todas" do filtro de qualidade

# Os nomes do jogo em portugues, na ordem do filtro.
QUALIDADES = {1: 'Normal', 2: 'Bom', 3: 'Excepcional', 4: 'Excelente',
              5: 'Obra-prima'}

# A CAIXA "No offers found." QUE OCUPA O LUGAR DA LISTA.
#
# Quando o filtro nao casa com nada, o jogo troca a lista inteira por um quadro
# com esta frase no meio. Nao e um erro nem uma tela lenta: e a resposta, e ela
# chega na mesma hora.
#
# Sem ler este quadro, a unica evidencia disponivel era o preco vir vazio - que
# e o mesmo sintoma de "a tela ainda nao redesenhou". O bot entao gastava as
# cinco releituras com espera crescente, cerca de dois segundos, para concluir o
# que estava escrito na tela desde o primeiro quadro.
CMP_SEM_OFERTAS = (840, 450, 1060, 498)

# ONDE O CURSOR VAI DESCANSAR depois de clicar numa opcao de filtro.
#
# NAO E FRESCURA: o jogo desenha o proprio cursor, e a captura de tela o pega
# junto. A opcao "encantamento 3" fica em (1100, 406) e o preco em (1070, 412)
# ate (1170, 450) - a seta desce cerca de 20 px do ponto clicado e para em cima
# dos PRIMEIROS DIGITOS. Foi assim que 540.000 virou 40.000: o 5 estava debaixo
# do ponteiro.
#
# So o encantamento 3 alcanca a regiao, mas o cursor sai de la em todas as
# trocas - depender de qual opcao foi clicada seria guardar uma excecao que
# ninguem lembra ao mexer nas coordenadas.
#
# ESTE PONTO PRECISA SER VAZIO, E A LINHA DOS FILTROS NAO E.
#
# A primeira versao punha o cursor em (1240, 270) - "entre o encantamento e o
# botao de limpar". E o centro do filtro de QUALIDADE. Nao chegou a abrir nada
# porque passar o mouse nao abre dropdown, mas era um controle, e um clique
# perdido ali teria aberto uma lista por cima da tela toda.
#
# A faixa do titulo da janela do mercado, a direita do nome e a esquerda da
# moeda, e madeira desenhada: nao ha um so controle nela, e fica 200 px acima da
# primeira oferta - longe do balao de descricao que aparece ao parar em cima de
# um item.
MOUSE_DESCANSO = {'x': 1150, 'y': 212}

# Faixa usada para detectar a abertura de um dropdown de filtro: uma tira na
# altura da PRIMEIRA opcao. Fechado, ali esta o fundo do painel; aberto, a
# primeira opcao da lista - diferenca suficiente para saber que abriu.
CMP_DETECCAO_OPCAO_Y = 300
CMP_DETECCAO_MEIA_LARGURA = 40
CMP_DETECCAO_MEIA_ALTURA = 13

#endregion

#region Calculo


def opcao_venda(indice):
    """Centro da opcao <indice> (1 = primeira) de um dropdown do painel de venda."""

    return VND_DROPDOWN_TOPO + (indice - 1) * VND_DROPDOWN_PASSO


def tier_compra(grau):
    """Posicao do Grau <grau> no filtro da tela de compra.

    A lista comeca em "Todos", entao o Grau N e a opcao de indice N."""

    return {'x': CMP_BARRA_TIER['x'],
            'y': CMP_TIER_TOPO + grau * CMP_DROPDOWN_PASSO}


def ench_compra(ench):
    """Posicao do Encantamento <ench> no filtro da tela de compra.

    A lista comeca em "Todos", e o encantamento 0 e a opcao seguinte."""

    return {'x': CMP_BARRA_ENCH['x'],
            'y': CMP_ENCH_TOPO + (ench + 1) * CMP_DROPDOWN_PASSO}


def qualidade_compra(qualidade):
    """Posicao da qualidade no filtro da tela de compra. 0 e "Todas".

    A lista comeca em "Todas", e a Normal (1) e a opcao seguinte."""

    return {'x': CMP_BARRA_QUAL['x'],
            'y': CMP_QUAL_TOPO + qualidade * CMP_DROPDOWN_PASSO}

#endregion

#region Calibracao

# O que o calibrador pede, e em que tela do jogo cada coisa e marcada.
#
# Os grupos seguem a ordem em que se navega no jogo, e cada um diz o que deixar
# na tela ANTES de capturar. Marcar a caixa de um filtro e marcar as opcoes dele
# sao telas diferentes - a lista so existe com o dropdown aberto.
#
# Tipos de marca:
#   ponto    um clique          -> {'x': , 'y': }
#   regiao   um arrasto         -> (x1, y1, x2, y2)
#   altura   um clique, so o y  -> um numero
#
# Os <derivados> saem de contas sobre o que foi marcado. O passo do dropdown e o
# caso: marcar a primeira e a segunda opcao e mais facil e mais confiavel do que
# pedir "a distancia entre duas opcoes".

PASSOS = [
    {
        'titulo': 'Lista do Mercado Negro',
        'preparo': 'Abra o Mercado Negro na lista "Vender do inventário", com '
                   'algum item na primeira linha e sem nenhum painel aberto.',
        'marcas': [
            {'nome': 'VND_BUSCA', 'tipo': 'ponto',
             'o_que': 'o campo de busca',
             'dica': 'Onde o bot clica antes de digitar o nome do item.'},
            {'nome': 'VND_RESET', 'tipo': 'ponto',
             'o_que': 'o botão de limpar a busca',
             'dica': 'O X ao lado do campo. Sem ele os nomes se emendam entre '
                     'um item e o próximo.'},
            {'nome': 'VND_VENDER', 'tipo': 'ponto',
             'o_que': 'o botão "Vender" da primeira linha da lista',
             'dica': 'É sempre a primeira linha: depois da busca, é nela que o '
                     'item procurado aparece.'},
            {'nome': 'LINHA_ITEM', 'tipo': 'regiao',
             'o_que': 'o ícone e o nome do item da primeira linha',
             'dica': 'Arraste um retângulo em volta. O bot espera esta região '
                     'mudar para saber que a busca terminou de filtrar.'},
        ],
    },
    {
        'titulo': 'Painel de pedido de venda',
        'preparo': 'Clique em "Vender" num item para abrir o painel de pedido de '
                   'venda. Deixe-o aberto, sem nenhuma lista de opções aberta.',
        'marcas': [
            {'nome': 'PRECO_VENDA', 'tipo': 'regiao',
             'o_que': 'o primeiro preço da lista "Pedidos de venda"',
             'dica': 'Só o número, sem o ícone da moeda e sem encostar na coluna '
                     'de quantidade. Deixe uma folga em cima e embaixo: cortar o '
                     'topo dos dígitos faz o OCR ler 6 como 0.'},
            {'nome': 'GRAU_ROTULO', 'tipo': 'regiao',
             'o_que': 'só o número do rótulo do grau',
             'dica': 'Em "Grau 7", marque só o 7. Um recorte folgado deixa a '
                     'letra "u" entrar no quadro e o OCR devolve 17.'},
            {'nome': 'VND_BARRA_TIER', 'tipo': 'ponto',
             'o_que': 'a caixa do filtro de grau, fechada'},
            {'nome': 'VND_BARRA_ENCH', 'tipo': 'ponto',
             'o_que': 'a caixa do filtro de encantamento, fechada'},
            {'nome': 'VND_FECHAR', 'tipo': 'ponto',
             'o_que': 'o X que fecha o painel'},
        ],
    },
    {
        'titulo': 'Lista de graus aberta',
        'preparo': 'No painel de pedido de venda, clique no filtro de grau para '
                   'abrir a lista de opções. Deixe-a aberta.',
        'marcas': [
            {'nome': 'VND_DROPDOWN_TOPO', 'tipo': 'altura',
             'o_que': 'o centro da primeira opção da lista'},
            {'nome': '_VND_SEGUNDA', 'tipo': 'altura',
             'o_que': 'o centro da segunda opção',
             'dica': 'A distância entre as duas dá o passo, e com ele o bot '
                     'calcula a posição de qualquer opção da lista.'},
        ],
        'derivados': [
            ('VND_DROPDOWN_PASSO',
             lambda v: v['_VND_SEGUNDA'] - v['VND_DROPDOWN_TOPO']),
        ],
    },
    {
        'titulo': 'Painel de republicar a venda',
        'preparo': 'Deixe na tela o painel em que você republica um item à venda: '
                   'o que tem o campo de preço e o botão de diminuir.',
        'marcas': [
            {'nome': 'VER_VENDER_1', 'tipo': 'ponto',
             'o_que': 'o botão "Vender" do item'},
            {'nome': 'VER_BUSCA', 'tipo': 'ponto',
             'o_que': 'o campo de busca deste painel'},
            {'nome': 'VER_NORMAL', 'tipo': 'ponto',
             'o_que': 'o filtro de qualidade Normal',
             'dica': 'Normal é a qualidade mais barata, e portanto a que define '
                     'o preço a ser batido.'},
            {'nome': 'VER_PRECO', 'tipo': 'ponto',
             'o_que': 'o campo onde se digita o preço'},
            {'nome': 'VER_DIMINUIR', 'tipo': 'ponto',
             'o_que': 'o botão que diminui 1 de prata'},
            {'nome': 'VER_FECHAR', 'tipo': 'ponto',
             'o_que': 'o X que fecha este painel'},
            {'nome': 'VER_VENDER_2', 'tipo': 'ponto',
             'o_que': 'o botão que confirma a venda',
             'dica': 'Se ele só aparece depois de clicar em Vender, deixe a '
                     'confirmação aberta antes de capturar.'},
        ],
    },
    {
        'titulo': 'Tela de compra',
        'preparo': 'Vá para a aba de compra do mercado, com alguma oferta '
                   'na lista e os filtros fechados.',
        'marcas': [
            {'nome': 'CMP_BUSCA', 'tipo': 'ponto', 'o_que': 'o campo de busca'},
            {'nome': 'CMP_RESET', 'tipo': 'ponto',
             'o_que': 'o botão de limpar a busca'},
            {'nome': 'CMP_BARRA_TIER', 'tipo': 'ponto',
             'o_que': 'a caixa do filtro de grau, fechada'},
            {'nome': 'CMP_BARRA_ENCH', 'tipo': 'ponto',
             'o_que': 'a caixa do filtro de encantamento, fechada'},
            {'nome': 'CMP_SEM_OFERTAS', 'tipo': 'regiao',
             'o_que': 'a frase "No offers found." no meio da lista',
             'dica': 'Filtre por algo que não exista (um T8 com encantamento 4 '
                     'de um item raro) para o quadro aparecer. Enquadre só a '
                     'frase, sem a borda do quadro.'},
            {'nome': 'MOUSE_DESCANSO', 'tipo': 'ponto',
             'o_que': 'um lugar vazio na linha dos filtros',
             'dica': 'O cursor fica aqui enquanto o bot lê. O jogo desenha o '
                     'próprio ponteiro e a captura o pega junto: parado em cima '
                     'do preço, ele esconde um dígito. Não escolha nada que '
                     'abra balão ao passar o mouse.'},
            {'nome': 'CMP_LIMPAR_FILTROS', 'tipo': 'ponto',
             'o_que': 'o botão que zera os filtros de grau e encantamento',
             'dica': 'O jogo guarda o filtro entre buscas. Sem zerar, o item '
                     'seguinte nasce com o T8.2 do anterior e a lista aparece '
                     'vazia.'},
            {'nome': 'PRECO_COMPRA', 'tipo': 'regiao',
             'o_que': 'só o número do preço da oferta mais barata',
             'dica': 'Não inclua o ícone da moeda: com ele dentro, o OCR lê a '
                     'faixa como uma linha de texto e a lasca dourada vira um '
                     'dígito (foi assim que 599.999 virou 399.999). Deixe folga '
                     'em cima e embaixo: cortar o topo dos dígitos faz o 6 sair '
                     'como 0.'},
            {'nome': 'CMP_LINHA_ITEM', 'tipo': 'regiao',
             'o_que': 'o nome do item da oferta',
             'dica': 'O bot lê este nome para confirmar que a busca achou o item '
                     'certo: preço mudando não prova qual item está na tela.'},
            {'nome': 'CMP_COMPRAR_1', 'tipo': 'ponto',
             'o_que': 'o botão "Comprar" da oferta'},
            {'nome': 'CMP_LINHA_OFERTA', 'tipo': 'regiao',
             'o_que': 'a linha inteira da primeira oferta',
             'dica': 'Do ícone até o preço. É por ela que o bot sabe que uma '
                     'compra aconteceu: duas ofertas podem ter o mesmo preço, '
                     'mas não o mesmo tempo restante.'},
        ],
    },
    {
        'titulo': 'Painel de compra',
        'preparo': 'Na tela de compra, clique em "Comprar" na linha de uma '
                   'oferta. Abre um painel: deixe-o na tela, sem confirmar.',
        'marcas': [
            {'nome': 'CMP_COMPRAR_2', 'tipo': 'ponto',
             'o_que': 'o botão "Comprar" dentro deste painel',
             'dica': 'É o segundo dos três cliques. O primeiro abriu este '
                     'painel; este pede a compra; o terceiro confirma.'},
            {'nome': 'CMP_FECHAR_PAINEL', 'tipo': 'ponto',
             'o_que': 'o "X" que fecha este painel',
             'dica': 'Por ele o bot sai do painel quando recusa uma compra. '
                     'Sem isso o painel fica por cima da lista, e o resto da '
                     'leitura lê e clica no painel achando que é a lista.'},
        ],
    },
    {
        'titulo': 'Confirmação da compra',
        'preparo': 'Clique no "Comprar" do painel. Aparece a pergunta "Quer '
                   'comprar 1 unidades de ... por ... de prata?". Não responda '
                   'ainda: deixe-a na tela.',
        'marcas': [
            {'nome': 'CMP_DIALOGO_COMPRA', 'tipo': 'regiao',
             'o_que': 'a frase da pergunta, com o preço',
             'dica': 'Este número é o que o jogo vai cobrar: conferi-lo é a '
                     'última barreira antes do débito. Marque a frase inteira; '
                     'o preço é o maior número dela.'},
            {'nome': 'CMP_CONFIRMAR_SIM', 'tipo': 'ponto',
             'o_que': 'o botão Sim'},
            {'nome': 'CMP_NAO_COMPRAR', 'tipo': 'ponto',
             'o_que': 'o botão Não',
             'dica': 'É por ele que o bot recusa uma compra cujo valor na '
                     'pergunta não bate com o lido na lista. Depois de marcar, '
                     'clique nele no jogo para fechar sem comprar.'},
        ],
    },
    {
        'titulo': 'Filtros da tela de compra abertos',
        'preparo': 'Na tela de compra, abra o filtro de grau e marque as duas '
                   'primeiras opções. Depois abra o de encantamento para a '
                   'última marca.',
        'marcas': [
            {'nome': 'CMP_TIER_TOPO', 'tipo': 'altura',
             'o_que': 'o centro da primeira opção do filtro de grau',
             'dica': 'Normalmente é a opção "Todos".'},
            {'nome': '_CMP_SEGUNDA', 'tipo': 'altura',
             'o_que': 'o centro da segunda opção do filtro de grau'},
            {'nome': 'CMP_ENCH_TOPO', 'tipo': 'altura',
             'o_que': 'o centro da primeira opção do filtro de encantamento',
             'dica': 'Capture de novo, com este outro filtro aberto.'},
        ],
        'derivados': [
            ('CMP_DROPDOWN_PASSO',
             lambda v: v['_CMP_SEGUNDA'] - v['CMP_TIER_TOPO']),
        ],
    },
    {
        'titulo': 'Filtro de qualidade da tela de compra',
        'preparo': 'Só para comprar por qualidade. Na tela de compra, capture uma '
                   'vez com o filtro de qualidade fechado e outra com ele aberto.',
        'marcas': [
            {'nome': 'CMP_BARRA_QUAL', 'tipo': 'ponto',
             'o_que': 'o filtro de qualidade, fechado',
             'dica': 'A caixa ao lado da de encantamento. É onde o bot clica '
                     'para abrir.'},
            {'nome': 'CMP_QUAL_TOPO', 'tipo': 'altura',
             'o_que': 'o centro da primeira opção do filtro de qualidade',
             'dica': 'Com o filtro aberto. Normalmente é a opção "Todas".'},
        ],
    },
]


def total_de_marcas():

    return sum(len(g['marcas']) for g in PASSOS)


def salvar_perfil(valores, caminho=None):
    """Grava o coordenadas.json com o que foi remarcado. Devolve os nomes.

    Junta com o que ja estava no arquivo, em vez de substituir: calibrar so a
    tela de compra nao pode apagar a marcacao da tela de venda feita ontem.

    Os nomes que comecam com _ sao auxiliares - servem para calcular um derivado
    e nao existem como constante."""

    destino = caminho or ARQUIVO_PERFIL

    atual = {}

    if os.path.isfile(destino):
        try:
            with open(destino, encoding='utf-8') as f:
                lido = json.load(f)
            if isinstance(lido, dict):
                atual = lido
        except Exception:
            atual = {}

    guardar = {n: v for n, v in valores.items() if not n.startswith('_')}

    atual.update(guardar)

    with open(destino, 'w', encoding='utf-8') as f:
        json.dump(atual, f, indent=2, ensure_ascii=False)

    return sorted(guardar)

#endregion

#region Perfil


def carregar_perfil(caminho=None):
    """Sobrescreve as constantes deste modulo com um coordenadas.json, se houver.

    Devolve a lista de nomes trocados. Existe para que uma remedicao - por causa
    de uma mudanca na interface do jogo, ou de outra resolucao - nao exija editar
    codigo nem reempacotar o programa.

    So aceita nomes que ja existem aqui, e so tipos compativeis: um arquivo
    escrito a mao com um nome errado tem que falhar de forma visivel, nao criar
    uma constante nova que ninguem le."""

    destino = caminho or ARQUIVO_PERFIL

    if not os.path.isfile(destino):
        return []

    try:
        with open(destino, encoding='utf-8') as f:
            dados = json.load(f)
    except Exception as e:
        comum.relatar(f'AVISO: {os.path.basename(destino)} nao pode ser lido ({e}) '
                      f'- seguindo com as coordenadas de fabrica')
        return []

    if not isinstance(dados, dict):
        return []

    trocados = []
    globais = globals()

    for nome, valor in dados.items():

        if nome not in globais or nome.startswith('_'):
            comum.relatar(f'AVISO: {nome!r} nao e uma coordenada conhecida - ignorado')
            continue

        atual = globais[nome]

        if not isinstance(atual, (dict, tuple, list, int, float)):
            continue

        if isinstance(atual, dict):
            if not (isinstance(valor, dict) and {'x', 'y'} <= set(valor)):
                comum.relatar(f'AVISO: {nome!r} precisa de x e y - ignorado')
                continue
            globais[nome] = {'x': int(valor['x']), 'y': int(valor['y'])}

        elif isinstance(atual, tuple):
            if not (isinstance(valor, (list, tuple)) and len(valor) == len(atual)):
                comum.relatar(f'AVISO: {nome!r} precisa de {len(atual)} numeros - ignorado')
                continue
            globais[nome] = tuple(int(v) for v in valor)

        else:
            if not isinstance(valor, (int, float)):
                comum.relatar(f'AVISO: {nome!r} precisa de um numero - ignorado')
                continue
            globais[nome] = type(atual)(valor)

        trocados.append(nome)

    _calibrados.update(trocados)

    return trocados


# Os nomes que vieram do coordenadas.json - os que alguem MEDIU, e nao os de
# fabrica. E o que separa uma posicao conferida de um palpite.
_calibrados = set()


def calibrado(*nomes):
    """True se todas estas coordenadas foram marcadas no calibrador."""

    return all(n in _calibrados for n in nomes)

#endregion


# Aplicado na importacao: quem usa as constantes ja recebe os valores do perfil.
PERFIL_APLICADO = carregar_perfil()
