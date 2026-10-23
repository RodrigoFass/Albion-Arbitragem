################################
#                              #
#            COMPRA            #
#                              #
################################

# Como comprar N unidades sem dar N vezes tres cliques.
#
# O jogo tem dois jeitos de comprar, e eles nao competem - servem para casos
# diferentes:
#
#     COMPRA NA HORA    pega uma oferta de venda que ja existe. Tres cliques por
#                       unidade, e o preco e o que estiver la.
#
#     PEDIDO DE COMPRA  cria uma ordem sua a um preco. Ela casa NA HORA com toda
#                       oferta de venda que estiver naquele preco ou abaixo - as
#                       53 unidades de uma vez, num clique. Custa 2,5% de taxa.
#
# O bot de referencia chama a escolha entre os dois de "Smart Buy", e as regras
# dele estao na tela de configuracao: ordem quando sao 8 ou mais unidades, compra
# na hora quando o item passa de 100.000 de prata. A logica e clara - varrer com
# ordem so compensa em volume, e em item caro nao vale arriscar taxa.
#
#
# O TAMANHO DA ORDEM SAI DO LIVRO DE OFERTAS, e nao de um chute.
#
# O painel do item mostra os "Pedidos de venda" com preco e quantidade: 895 x1,
# 898 x28, 898 x14, 899 x8. Somando os que ainda pagam, sai exatamente quantas
# unidades pedir - e a ordem casa inteira, sem sobrar nada.
#
# Isso importa mais do que parece. Uma ordem maior do que ha para vender NAO
# desaparece: ela fica de pe no mercado com a sua prata presa dentro, esperando
# alguem vender. Dimensionada pelo livro, ela nasce e morre no mesmo instante.
#
#
# O JOGO COBRA O PRECO DE QUEM ESTA VENDENDO, e nao o da minha ordem. Pedindo 899
# e havendo ofertas a 895 e 898, paga-se 895 e 898 - o meu preco e um TETO, e nao
# uma proposta. Conferido com quem opera a rota na mao.
#
# Por isso o plano traz dois numeros de custo:
#
#     custo         a soma real, oferta por oferta. E o que deve sair da conta.
#     custo_maximo  preco da ordem vezes as unidades. E o que o jogo RESERVA, e
#                   o numero que aparece no "Total" do painel - e por isso e ele
#                   que da para conferir na tela antes de clicar em criar.
#
# Antes de alterar: python -m pyflakes compra.py

import math
import os
import time

from PIL import Image, ImageOps

from motor import comum
from motor import coordenadas as cd
from motor import lucro

#region Configuracao

# As duas regras do Smart Buy, com os numeros da tela de referencia.
MINIMO_PARA_ORDEM = 8
CARO_DEMAIS_PARA_ORDEM = 100_000

# Palavras que provam que o dialogo de confirmacao esta mesmo na tela.
#
# "Quer comprar 1 unidades de <item> por <preco> de prata?" - sem achar nenhuma
# delas, o numero lido dali nao e o preco da compra, e sim o que estiver naquele
# pedaco da tela. Ja aconteceu de o recorte pegar uma linha da lista atras.
PALAVRAS_DO_DIALOGO = ('comprar', 'prata', 'unidades', 'buy', 'silver', 'units')

# Limites, em segundos.
ESPERA_DIALOGO = 2.00   # o dialogo aparecer depois dos dois cliques
ESPERA_COMPRA = 3.00    # a lista assentar depois da compra

# Conferir o dialogo antes de clicar em Sim. Desligar aqui e comprar as cegas.
VERIFICAR_DIALOGO = True

SALVAR_FALHAS = True
PASTA_FALHAS = 'falhas_compra'

# Quantas linhas do livro de ofertas dao para ler sem rolar.
LINHAS_DO_LIVRO = cd.LIVRO_LINHAS

#endregion

#region O preco que ainda paga


def preco_maximo(venda, margem, taxa=lucro.TAXA_PADRAO, por_ordem=True,
                 ordem_na_venda=False):
    """O maior preco de compra que ainda deixa <margem> de lucro.

    Sai de inverter a conta do lucro.liquido():

        (venda*(1-taxa) - custo) / custo  >=  margem
        custo <= venda*(1-taxa) / (1+margem)

    e custo = compra * (1 + taxa de ordem), quando se compra por ordem.

    <ordem_na_venda> e o caminho de venda da linha (lucro.melhor_venda): vender
    por ordem paga os 2,5% tambem na saida, e o teto desce junto.

    E o preco a pedir na ordem: ele varre tudo que paga e para exatamente onde
    para de pagar. Um silver acima e a ordem comeca a comprar prejuizo."""

    if venda <= 0:
        return 0

    teto = lucro.receita_real(venda, taxa, ordem_na_venda) / (1 + margem)

    if por_ordem:
        teto /= (1 + lucro.TAXA_DE_ORDEM)

    # trunca: arredondar para cima poe o ultimo silver do lado errado da conta
    return int(teto)

#endregion

#region O livro de ofertas


# A leitura dos numeros do livro: (limiar, modo do tesseract, ampliacao), sobre
# o recorte com o contraste esticado. Modo 7 e linha, 10 e caractere solto - o
# "1" da quantidade quase so sai nele. Vale o numero que juntar VOTOS_MINIMOS
# leituras; a votacao para quando um numero chega la, e o caso comum custa tres.
# Medido no print do painel do Master's Enigmatic Staff, com o texto mais claro
# (~75 de cinza) que nos prints de antes: sem esticar o contraste, o 118,499
# nao saia em limiar nenhum.
VARIANTES_DO_LIVRO = ((110, 7, 4), (150, 7, 4), (130, 10, 3), (110, 10, 4),
                      (170, 7, 4), (90, 7, 3), (150, 10, 4), (130, 7, 4))
VOTOS_MINIMOS = 3
CONFIG_DO_LIVRO = '--psm {} --oem 1 -c tessedit_char_whitelist=0123456789,'

# A LINHA DESTACADA: abrindo o painel pelo Buy, o jogo seleciona a oferta mais
# barata e pinta a linha de verde, com o numero amarelo - claro sobre escuro, o
# contrario das outras. Mediana de cinza abaixo disto e linha destacada, lida
# invertida. No print: 104 na destacada, 170 a 190 nas outras.
MEDIANA_DA_DESTACADA = 140

# Uma linha sem oferta e bege liso; com numero, o traco e o fundo distam mais
# de 70 tons de cinza (95 na destacada, mais de 100 nas outras).
CONTRASTE_MINIMO = 40


def _preparar_do_livro(img):
    cinza = img.convert('L')
    valores = sorted(cinza.getdata())

    if valores[len(valores) // 2] < MEDIANA_DA_DESTACADA:
        cinza = ImageOps.invert(cinza)

    return ImageOps.autocontrast(cinza)


def ler_inteiro(img, minimo, maximo):
    """O numero de um recorte, ou None quando os limiares nao concordam."""

    cinza = _preparar_do_livro(img)
    votos = {}
    prontas = {}

    for limiar, psm, escala in VARIANTES_DO_LIVRO:

        if (limiar, escala) not in prontas:
            preto = cinza.point(lambda v, limiar=limiar: 0 if v < limiar else 255)
            grande = preto.resize((preto.width * escala, preto.height * escala),
                                  Image.LANCZOS)
            prontas[(limiar, escala)] = ImageOps.expand(grande, border=20, fill=255)

        texto, _ = comum._reconhecer_com_confianca(prontas[(limiar, escala)],
                                                   CONFIG_DO_LIVRO.format(psm))
        digitos = ''.join(c for c in texto if c.isdigit())

        if digitos and minimo <= int(digitos) <= maximo:
            valor = int(digitos)
            votos[valor] = votos.get(valor, 0) + 1

            if votos[valor] >= VOTOS_MINIMOS:
                return valor

    # sem chegar la, nao vale: um numero errado aqui vira compra errada calada
    return None


def _recorte_do_livro(tela, regiao):
    x1, y1, x2, y2 = regiao
    bx, by = cd.LIVRO_VENDA[0], cd.LIVRO_VENDA[1]
    return tela.crop((x1 - bx, y1 - by, x2 - bx, y2 - by))


def _linha_vazia(img):
    """Bege liso, sem numero: a linha nao tem oferta, o livro acabou.

    PELO CONTRASTE, e nao por "sem traco escuro": a linha destacada tem o
    numero CLARO sobre fundo escuro, e passava por vazia - a compra esperava o
    livro chegar, nunca via, e fechava o painel sem comprar."""

    valores = img.convert('L').getdata()

    return max(valores) - min(valores) < CONTRASTE_MINIMO


# Limite esperando o livro chegar do servidor depois de o painel abrir.
ESPERA_LIVRO = 3.00


def _esperar_livro():
    """Espera a primeira oferta aparecer no livro. False se ele ficou vazio.

    O PAINEL ABRE ANTES DO LIVRO. As ofertas chegam do servidor um instante
    depois, e o painel fica com o livro em branco nesse meio tempo - parado, e
    portanto "estavel". Lendo ali, a primeira linha saia vazia, o livro era
    dado por acabado, e a compra registrava "nao deu para ler o livro" em
    todo item: abria o painel e fechava."""

    fim = time.monotonic() + ESPERA_LIVRO

    while time.monotonic() < fim:

        comum.checar_aborto()

        tela = comum.capturar(cd.LIVRO_VENDA)

        if not _linha_vazia(_recorte_do_livro(tela, cd.venda_preco_numero(0))):
            comum.esperar_estavel(cd.LIVRO_VENDA, ESPERA_CAMPO,
                                  intervalo=comum.SONDAGEM_LENTA)
            return True

        time.sleep(0.10)

    comum.contar('livro_nao_chegou')

    return False


# --- descer o livro ----------------------------------------------------------
#
# SO CABEM SEIS OFERTAS NA TELA, e no print do Enigmatic Staff eram seis de uma
# unidade: vinte unidades iam ate 139.986, bem abaixo da primeira tela. Sem
# descer, o pedido saia com seis.
#
# PELO CABO DA BARRA, ARRASTADO. A roda do mouse nao mexia o livro no jogo; o
# cabo da barrinha a direita dele, segurado e puxado, mexe.
#
# CADA TELA NOVA E ENCAIXADA NA ANTERIOR PELAS OFERTAS LIDAS, e nao pela imagem:
# a lista nao anda linha a linha (no print, as linhas desceram 3 px), e o
# degrade do fundo pesa mais que os digitos numa comparacao de pixels. O livro e
# ordenado pelo preco, entao a tela nova comeca por um pedaco do fim da anterior.

MAXIMO_DE_DESCIDAS = 20

# Quanto puxar o cabo, em pixels. Comeca curto; se a lista nao mexer, dobra; se
# pular mais que uma tela, volta e puxa a metade.
PASSO_DO_CABO = 8
PASSO_MAXIMO_DO_CABO = 48


def cabo_da_barra(coluna):
    """O y (dentro da captura) do meio do cabo da barra, ou None se nao ha barra.

    O cabo e cinza-azulado escuro (azul acima do vermelho); o trilho e bege e
    as setas das pontas sao laranja. Sem barra, o livro cabe inteiro na tela."""

    px = coluna.load()
    linhas = [y for y in range(coluna.height)
              if any(px[x, y][2] - px[x, y][0] >= 6 and max(px[x, y]) < 130
                     for x in range(coluna.width))]

    # o maior trecho continuo: o cursor do mouse perto da barra tambem tem pixel
    # escuro, mas solto
    trechos, atual = [], []

    for y in linhas:
        if atual and y - atual[-1] > 2:
            trechos.append(atual)
            atual = []
        atual.append(y)

    trechos.append(atual)
    maior = max(trechos, key=len)

    if len(maior) < 10:
        return None

    return (maior[0] + maior[-1]) // 2


def sobreposicao(lidas, novas):
    """Quantas das <novas> ja estavam no fim das <lidas>.

    O MAIOR ENCAIXE. Com ofertas iguais em sequencia (118.499 x1 duas vezes) mais
    de um encaixe serve; o maior conta menos ofertas novas - a ordem sai com
    menos unidades que podia, e nunca com mais."""

    for k in range(min(len(lidas), len(novas)), 0, -1):
        if lidas[-k:] == novas[:k]:
            return k

    return 0


def _ler_tela(tela):
    """([(preco, quantidade)] das linhas visiveis, True se achou o fim do livro)."""

    ofertas = []

    for n in range(LINHAS_DO_LIVRO):

        comum.checar_aborto()

        recorte = _recorte_do_livro(tela, cd.venda_preco_numero(n))
        preco = ler_inteiro(recorte, comum.PRECO_MIN, comum.PRECO_MAX)

        if preco is None:
            if _linha_vazia(recorte):
                return ofertas, True
            comum.contar('preco_do_livro_ilegivel')
            continue

        quantidade = ler_inteiro(
            _recorte_do_livro(tela, cd.venda_quantidade(n)), 1, 999_999)

        if quantidade is None:
            comum.contar('quantidade_ilegivel')
            quantidade = 1

        ofertas.append((preco, int(quantidade)))

    return ofertas, False


def _puxar_cabo(pixels):
    """Arrasta o cabo da barra <pixels> para baixo (negativo, para cima). False
    se nao ha barra."""

    centro = cabo_da_barra(comum.capturar(cd.LIVRO_BARRA))

    if centro is None:
        return False

    x = (cd.LIVRO_BARRA[0] + cd.LIVRO_BARRA[2]) // 2
    y = cd.LIVRO_BARRA[1] + centro

    comum.arrastar({'x': x, 'y': y}, {'x': x, 'y': y + pixels})

    # o cursor sai de cima do livro: a linha embaixo dele fica escurecida
    comum.apontar(cd.MOUSE_DESCANSO)
    comum.esperar_estavel(cd.LIVRO_VENDA, ESPERA_CAMPO,
                          intervalo=comum.SONDAGEM_LENTA)

    return True


def ler_livro(ate_unidades=None, ate_preco=None):
    """Le "Pedidos de venda". Devolve [(preco, quantidade)], de baixo para cima.

    DESCE O LIVRO ate juntar <ate_unidades> ou passar de <ate_preco> - o que a
    linha quer comprar e o mais caro que ainda paga a margem. Sem os dois, so a
    primeira tela.

    PELA LEITURA POR VOTACAO (ler_inteiro), uma captura por tela. A leitura de
    antes falhava de tres jeitos nos prints do jogo:

      - a quantidade passava pelo numero_valido, que recusa menos de 100 - e
        toda quantidade do livro (1, 2, 5) virava 1;
      - parava na primeira linha ilegivel, achando que o livro tinha acabado;
      - a primeira linha, destacada pelo Buy, passava por vazia.

    O livro acaba na primeira linha VAZIA. Linha com numero que nao deu para ler
    e pulada: a ordem sai com menos unidades que podia, e nunca com mais.

    Quantidade ilegivel com preco legivel vira 1, e nao zero. Um vira uma compra
    a menos que a possivel; zero faria a linha inteira desaparecer da conta e a
    ordem nasceria pequena demais - e o erro que some e sempre pior."""

    if not _esperar_livro():
        return []

    ofertas, fim = _ler_tela(comum.capturar(cd.LIVRO_VENDA))
    passo = PASSO_DO_CABO

    for _ in range(MAXIMO_DE_DESCIDAS):

        if fim or not ofertas or (ate_unidades is None and ate_preco is None):
            break

        if ate_unidades is not None and sum(q for _, q in ofertas) >= ate_unidades:
            break

        if ate_preco is not None and max(p for p, _ in ofertas) > ate_preco:
            break

        if not _puxar_cabo(passo):
            # sem barra: o livro cabe inteiro na tela, e ja foi lido
            break

        novas, fim = _ler_tela(comum.capturar(cd.LIVRO_VENDA))
        k = sobreposicao(ofertas, novas)

        if not novas[k:]:
            # A LISTA NAO MEXEU: o puxao foi curto, ou o livro acabou
            if passo >= PASSO_MAXIMO_DO_CABO:
                break
            passo *= 2
            continue

        if k == 0:
            # PULOU MAIS QUE UMA TELA: o que ficou entre as duas nao foi lido.
            # Volta e puxa a metade; sem como encolher mais, para com o que tem
            comum.contar('livro_rolou_demais')
            _puxar_cabo(-passo)
            if passo <= 1:
                break
            passo //= 2
            fim = False
            continue

        ofertas.extend(novas[k:])

    return ofertas


def livro_vazio():
    """True se o jogo estiver dizendo que ninguem esta comprando este item.

    "NO MOMENTO NINGUEM ESTA COMPRANDO ESTE ITEM NO MERCADO" nao e falha de
    leitura - e o mercado respondendo que ali nao ha negocio. Confundir as duas
    faria o bot insistir numa tela que nunca vai ter numero."""

    texto = comum.normalizar(comum.ler_texto(cd.LIVRO_AVISO_VAZIO))

    return 'ninguem' in texto or 'momento' in texto

#endregion

#region Preencher um campo

# Limite esperando um campo mostrar o que foi digitado.
ESPERA_CAMPO = 1.50

# Quantas vezes tentar preencher antes de desistir.
TENTATIVAS_DE_CAMPO = 3


def preencher(campo, regiao, valor):
    """Poe <valor> num campo e CONFERE lendo de volta. True se ficou la.

    Ler de volta nao e paranoia: um clique que erra o campo por dois pixels cai
    no de cima, e o numero vai para o lugar errado sem nada reclamar. Aqui isso
    seria uma ordem de compra com a quantidade no preco.

    Insiste algumas vezes porque o campo as vezes nao pega o foco no primeiro
    clique - e falhar por isso obrigaria a refazer a navegacao inteira."""

    alvo = str(int(valor))

    for _ in range(TENTATIVAS_DE_CAMPO):

        comum.checar_aborto()

        comum.clicar(campo)
        comum.limpar_campo()
        comum.digitar(alvo)

        lido = comum.ler_numero(regiao)

        if lido == int(valor):
            return True

        comum.contar('campos_refeitos')

    return False


# Leituras de um campo antes de redigitar, e o intervalo entre elas - meio
# piscar do cursor de texto.
LEITURAS_DO_CAMPO = 4
ESPERA_ENTRE_LEITURAS = 0.15

# A leitura de um numero do painel do item: (limiar, modo do tesseract,
# ampliacao). O fundo bege fica em ~184 de cinza e o traco em ~46; nos prints
# do jogo 130 e 150 acertaram todos, 110 quase todos. O modo palavra (8) e para
# o numero de um digito so - o preco 3 de um Scraps of Hide -, que o modo linha
# (7) perde. As ampliacoes 3 e 5 sao do 449999 de um Guardian Boots: limpo na
# tela, lido "4495999" pelas quatro primeiras, e certo nas outras duas.
VARIANTES_DO_CAMPO = ((130, 7, 4), (150, 7, 4), (110, 7, 4), (130, 8, 4),
                      (130, 7, 3), (130, 7, 5))
CONFIG_DO_CAMPO = '--psm {} --oem 1 -c tessedit_char_whitelist=0123456789'


def ler_campo_da_imagem(bruta):
    """Os numeros que uma captura de um campo do painel pode estar mostrando.

    O CAMPO EM EDICAO NAO E A LISTA. O numero e marrom sobre um bege em
    degrade, com o cursor de texto branco piscando colado no ultimo digito, e o
    preparo do ler_numero - feito para a lista - lia "83384" como "8338400" ou
    perdia o "1" de "126981" (dados/registros/falhas_venda_mochila). Aqui o
    traco escuro vira preto e todo o resto, cursor incluso, vira fundo.

    Devolve uma leitura por limiar: quem chama confere se ALGUMA bate com o que
    esperava. Um limiar errar para o numero exato que se esperava nao acontece
    por acaso - e por isso aqui nao ha a faixa do numero_valido, que recusa
    menos de 100: um Scraps of Hide custa 3."""

    cinza = bruta.convert('L')
    lidos = []
    prontas = {}

    for limiar, psm, escala in VARIANTES_DO_CAMPO:

        if (limiar, escala) not in prontas:
            preto = cinza.point(lambda v, limiar=limiar: 0 if v < limiar else 255)
            grande = preto.resize((preto.width * escala, preto.height * escala),
                                  Image.LANCZOS)
            prontas[(limiar, escala)] = ImageOps.expand(grande, border=20, fill=255)

        texto, _ = comum._reconhecer_com_confianca(prontas[(limiar, escala)],
                                                   CONFIG_DO_CAMPO.format(psm))
        digitos = ''.join(c for c in texto if c.isdigit())
        lidos.append(int(digitos) if digitos else None)

    return lidos


def ler_campo(regiao):
    """ler_campo_da_imagem() de uma regiao da tela, guardado para diagnostico."""

    bruta = comum.capturar(regiao)
    lidos = ler_campo_da_imagem(bruta)

    comum._ultima_imagem = bruta
    comum._ultimo_texto = ' / '.join(str(v) for v in lidos)

    return lidos


def preencher_conferindo(campo, regiao, valor):
    """Digita <valor> num campo do painel e CONFERE lendo de volta.

    Como o preencher(), mas pela leitura do campo em edicao, e lendo VARIAS
    VEZES antes de digitar de novo: o cursor de texto pisca dentro do numero, e
    um quadro com ele aceso pode sair com um digito a mais. Redigitar por causa
    disso so trocava um quadro ruim por outro."""

    for _ in range(TENTATIVAS_DE_CAMPO):

        comum.checar_aborto()

        comum.clicar(campo)
        comum.limpar_campo()
        comum.digitar(str(int(valor)))

        for _ in range(LEITURAS_DO_CAMPO):
            if int(valor) in ler_campo(regiao):
                return True
            time.sleep(ESPERA_ENTRE_LEITURAS)

        comum.contar('campos_refeitos')

    return False

#endregion

#region O plano


def planejar(ofertas, venda, margem, quantidade_maxima,
             taxa=lucro.TAXA_PADRAO, ordem_na_venda=False):
    """Quanto pedir e a que preco. Devolve o plano, ou None se nao vale.

    Percorre as ofertas da mais barata para a mais cara enquanto elas pagarem a
    margem, e para no teto de quantidade que voce escolheu no catalogo.

    O plano sai com o custo calculado PELO PIOR CASO - todas as unidades ao preco
    da ordem. Ver o cabecalho do modulo."""

    if not ofertas or quantidade_maxima <= 0:
        return None

    teto = preco_maximo(venda, margem, taxa, ordem_na_venda=ordem_na_venda)

    unidades = 0
    preco_da_ordem = 0
    deixadas = 0
    gasto = 0

    for preco, quantidade in sorted(ofertas):

        if preco > teto:
            deixadas += quantidade
            continue

        cabem = min(quantidade, quantidade_maxima - unidades)

        if cabem <= 0:
            deixadas += quantidade
            continue

        unidades += cabem

        # o RESTO desta linha tambem ficou para tras. Contar so as linhas puladas
        # inteiras dava um numero menor que a verdade, e este numero e o que
        # responde "vale a pena voltar aqui?" - subestimado, ele diz que nao
        deixadas += quantidade - cabem

        # o jogo cobra o preco de QUEM VENDE, e nao o da ordem
        gasto += preco * cabem

        preco_da_ordem = max(preco_da_ordem, preco)

    if not unidades:
        return None

    custo = int(gasto * (1 + lucro.TAXA_DE_ORDEM))
    reservado = int(preco_da_ordem * unidades * (1 + lucro.TAXA_DE_ORDEM))
    receita = int(lucro.receita_real(venda, taxa, ordem_na_venda) * unidades)

    return {
        'preco': preco_da_ordem,
        'unidades': unidades,
        'teto_de_preco': teto,
        'custo': custo,
        'custo_maximo': reservado,
        'receita': receita,
        'lucro': receita - custo,
        'margem': (receita - custo) / custo if custo else 0.0,
        'deixadas_para_tras': deixadas,
    }


def por_ordem(unidades, preco, modo=None, minimo=None, caro=None):
    """A regra do Smart Buy: vale a pena criar uma ordem para isto?

    Volume justifica a taxa de 2,5%; item caro nao. Sao as duas regras da tela
    de referencia, e elas se somam - basta uma dizer que nao.

    <modo> 'ordem' ou 'na hora' TRAVA a escolha. Existe para quando voce sabe
    algo que a regra nao sabe - numa rodada de itens caros, ordem nenhuma; num
    item que voce quer varrer inteiro, ordem sempre."""

    if modo == 'ordem':
        return True, 'travado em ordem'

    if modo == 'na hora':
        return False, 'travado em compra na hora'

    minimo = MINIMO_PARA_ORDEM if minimo is None else minimo
    caro = CARO_DEMAIS_PARA_ORDEM if caro is None else caro

    if preco >= caro:
        return False, f'{comum.fmt(preco)} por unidade - caro demais para ordem'

    if unidades < minimo:
        return False, f'{unidades} unidades - poucas para justificar a taxa'

    return True, ''


def decidir(ofertas, venda, margem, quantidade_maxima, taxa=lucro.TAXA_PADRAO,
            modo=None, minimo=None, caro=None, ordem_na_venda=False):
    """O plano completo: quanto, a que preco, e por qual dos dois caminhos.

    Devolve (plano, modo, motivo). <modo> e 'ordem' ou 'na hora'."""

    plano = planejar(ofertas, venda, margem, quantidade_maxima, taxa,
                     ordem_na_venda)

    if plano is None:
        return None, None, 'nenhuma oferta paga a margem'

    vale, motivo = por_ordem(plano['unidades'], plano['preco'], modo, minimo,
                             caro)

    return plano, ('ordem' if vale else 'na hora'), motivo

#endregion

#region Criar a ordem


def abrir_painel():
    """Abre o painel do primeiro item da lista. True se ele apareceu.

    PELO BOTAO "BUY" DA LINHA. Ele nao compra nada: abre o painel com o livro de
    ofertas e as quatro acoes - quem compra e o Buy DE DENTRO do painel. Antes o
    bot clicava no nome, numa posicao derivada e nunca medida; o Buy da linha e
    o primeiro clique da compra na hora, medido e calibrado."""

    antes = comum.assinatura(cd.venda_preco(0))

    comum.clicar(cd.CMP_COMPRAR_1)

    if comum.esperar_mudanca(cd.venda_preco(0), antes, ESPERA_CAMPO):
        comum.esperar_estavel(cd.venda_preco(0), ESPERA_CAMPO,
                              intervalo=comum.SONDAGEM_LENTA)
        return True

    return comum.ler_numero(cd.venda_preco(0)) is not None


def fechar_painel():
    """Sai do painel pelo X."""

    comum.clicar(cd.PAINEL_FECHAR)


def total_da_ordem(preco, unidades):
    """O "Total" que o painel mostra: o reservado mais a taxa de ordem.

    A taxa e arredondada PARA CIMA - 3 de prata x 1 mostra taxa 1 e Total 4."""

    valor = int(preco) * int(unidades)

    return valor + math.ceil(valor * lucro.TAXA_DE_ORDEM)


def conferir_total(previsto, tolerancia=0.01):
    """(ok, leituras): o Total da tela bate com o <previsto>?"""

    comum.esperar_estavel(cd.PAINEL_TOTAL_VALOR, ESPERA_CAMPO,
                          intervalo=comum.SONDAGEM_LENTA)

    folga = max(1, previsto * tolerancia)
    lidos = []

    for _ in range(LEITURAS_DO_CAMPO):
        lidos = ler_campo(cd.PAINEL_TOTAL_VALOR)

        if any(v is not None and abs(v - previsto) <= folga for v in lidos):
            return True, lidos

        time.sleep(ESPERA_ENTRE_LEITURAS)

    return False, lidos


def _botoes_do_dialogo(coluna):
    """O y do meio dos botoes Yes/No numa captura da coluna, ou None.

    O botao e azul-escuro com borda clara; o fundo do dialogo e cinza quase
    preto, e o painel atras e bege. Azul (b acima de r) e escuro so o botao e."""

    px = coluna.load()
    linhas = [y for y in range(coluna.height)
              if px[0, y][2] - px[0, y][0] >= 5 and max(px[0, y]) < 120]

    # o maior trecho continuo, tolerando falhas de 3 px (o texto do botao)
    melhor, inicio, fim = None, None, None

    for y in linhas + [None]:
        if inicio is not None and (y is None or y - fim > 3):
            if fim - inicio >= 15 and (melhor is None or fim - inicio > melhor[1] - melhor[0]):
                melhor = (inicio, fim)
            inicio = None
        if y is not None:
            if inicio is None:
                inicio = y
            fim = y

    return None if melhor is None else (melhor[0] + melhor[1]) // 2


def numeros_do_dialogo(texto):
    """Os numeros escritos no texto do dialogo, como inteiros: 853,811 -> 853811."""

    return {int(g.replace('.', '').replace(',', ''))
            for g in comum._NUMERO_ESCRITO.findall(texto or '')}


def confirmar_ordem(plano):
    """Responde a pergunta do jogo depois do Create Buy Order. (ok, motivo).

    O jogo nem sempre pergunta - com o aviso "YOU CANNOT EQUIP THIS ITEM", sim.
    Sem pergunta na tela, a ordem ja foi criada.

    SO CLICA EM YES SE O DIALOGO DISSER O QUE O PLANO PEDIU: o preco de cada
    unidade, e a quantidade ou o total. Qualquer outra coisa e No - o dialogo e
    o jogo dizendo o que vai fazer, e ele discordar e a ultima chance de parar."""

    x1, y1, _, _ = cd.DIALOGO_ORDEM_COLUNA
    fim = time.monotonic() + ESPERA_DIALOGO
    centro = None

    while time.monotonic() < fim:
        comum.checar_aborto()
        centro = _botoes_do_dialogo(comum.capturar(cd.DIALOGO_ORDEM_COLUNA))
        if centro is not None:
            break
        time.sleep(0.10)

    if centro is None:
        return True, ''

    y = y1 + centro

    comum.esperar_estavel(cd.DIALOGO_ORDEM_TEXTO, ESPERA_DIALOGO,
                          intervalo=comum.SONDAGEM_LENTA)
    texto = comum.ler_texto(cd.DIALOGO_ORDEM_TEXTO)
    numeros = numeros_do_dialogo(texto)

    total = total_da_ordem(plano['preco'], plano['unidades'])

    if int(plano['preco']) in numeros and (int(plano['unidades']) in numeros
                                           or total in numeros):
        comum.clicar({'x': cd.DIALOGO_ORDEM_SIM_X, 'y': y})
        comum.contar('ordens_confirmadas')
        return True, ''

    comum.clicar({'x': cd.DIALOGO_ORDEM_NAO_X, 'y': y})
    comum.contar('ordens_recusadas_no_dialogo')
    _guardar_falha('dialogo_ordem', [f'texto            : {texto!r}',
                                     f'previsto         : {plano["unidades"]} x {plano["preco"]} = {total}'],
                   regiao=cd.DIALOGO_ORDEM_TEXTO)

    return False, (f'o dialogo do jogo nao confirma {plano["unidades"]} x '
                   f'{comum.fmt(plano["preco"])} - respondido No')


def criar_ordem(plano, tolerancia=0.01):
    """Cria o pedido de compra do <plano>. Devolve (ok, motivo).

    A ULTIMA BARREIRA E O "TOTAL" DA TELA. Antes de clicar em criar, o jogo ja
    escreveu quanto vai reservar - e esse numero e o unico que nao passou pelo
    nosso OCR duas vezes nem pela nossa aritmetica. Se ele nao bater com o
    previsto, alguma coisa entre o plano e a tela se perdeu: o campo pegou o
    numero errado, o item nao e o que se pensa, o preco tem outra casa.

    E a mesma licao que custou caro no bot antigo, onde o dialogo de confirmacao
    dizia um valor e a lista dizia outro. So que la a divergencia custava uma
    unidade; aqui custaria a ordem inteira.

    E E O TOTAL QUE CONFERE A QUANTIDADE. Ela vai na bolha em cima da barra
    (o "1"), e a bolha anda com a barra: depois de digitar nao ha um lugar fixo
    para le-la de volta. Por isso, Total ilegivel agora impede a ordem - antes
    deixava passar, quando a quantidade era conferida no proprio campo."""

    comum.secao_critica.set()

    try:
        comum.clicar(cd.PAINEL_PEDIDO_DE_COMPRA)

        comum.clicar(cd.PAINEL_QTD_NUMERO)
        comum.limpar_campo()
        comum.digitar(str(int(plano['unidades'])))

        # o campo de preco e o mesmo do painel de venda do Mercado Negro
        if not preencher_conferindo(cd.PAINEL_PRECO_CAMPO, cd.VND_PRECO_VALOR,
                                    plano['preco']):
            _guardar_falha('preco', [f'digitado          : {plano["preco"]}'],
                           regiao=cd.VND_PRECO_VALOR)
            return False, 'o preco nao entrou no campo'

        previsto = total_da_ordem(plano['preco'], plano['unidades'])
        ok, lidos = conferir_total(previsto, tolerancia)

        if not ok:
            comum.contar('total_divergente')
            _guardar_falha('total', [f'previsto          : {previsto}'],
                           regiao=cd.PAINEL_TOTAL_VALOR)
            lido = next((v for v in lidos if v is not None), None)
            return False, (f'a tela reserva '
                           f'{comum.fmt(lido) if lido else "um Total ilegivel"} '
                           f'e o plano previa {comum.fmt(previsto)} - a quantidade '
                           f'ou o preco nao entrou')

        comum.clicar(cd.PAINEL_CRIAR)

        # o jogo pode perguntar antes de criar - e a ordem so existe com o Yes
        ok, motivo = confirmar_ordem(plano)

        if not ok:
            return False, motivo

    finally:
        comum.secao_critica.clear()

    comum.contar('ordens_criadas')

    return True, ''

#endregion


#region Comprar na hora


def conferir_dialogo(esperado, aceitar=None):
    """Le o preco do dialogo. Devolve (situacao, cobrado, motivo).

    O dialogo diz "Quer comprar 1 unidades de <item> por <preco> de prata?".
    Esse <preco> e o que o jogo vai debitar - nao o que estava na lista quando o
    bot leu, que pode ter mudado no meio do caminho, e nao o que o OCR achou que
    tinha lido. E A MELHOR FONTE DE VERDADE DO PROGRAMA INTEIRO: e o proprio
    jogo dizendo, em numero, quanto vai cobrar, antes de cobrar.

    Quatro situacoes:

      'ok'       compra. <cobrado> e o valor de verdade, e e ele que vai para o
                 historico - o da lista pode estar uma oferta atrasado.
      'revisto'  o dialogo mostrou OUTRO numero, e esse numero ainda vale a
                 compra. Compra, pelo valor dele.
      'recusar'  o numero de verdade nao vale a compra. Clica em Nao.
      'ausente'  nao ha dialogo na tela. Nada de clicar em Sim.

    A DIVERGENCIA NAO E MOTIVO PARA DESISTIR, e no bot antigo foi assim que
    comecou. De dez compras recusadas, oito eram leituras atrasadas da lista com
    o dialogo mostrando um preco que passava folgado - e o bot recusava, clicava
    tudo de novo e comprava o mesmo item um ciclo depois. Uma delas era melhor
    ainda: a lista dizia 328.761 e o jogo ia cobrar 260.708. Ele recusou duas
    vezes e abandonou a combinacao.

    Quando o dialogo discorda, a pergunta certa nao e "bate com o que eu li?" e
    sim "este valor, que e o verdadeiro, vale a compra?". Quem responde e o
    <aceitar>, que devolve (pode, motivo)."""

    if not VERIFICAR_DIALOGO:
        return 'ok', esperado, ''

    comum.esperar_estavel(cd.CMP_DIALOGO_COMPRA, ESPERA_DIALOGO,
                          intervalo=comum.SONDAGEM_LENTA)

    with comum.cronometro('conferencia do dialogo'):
        texto = comum.ler_texto(cd.CMP_DIALOGO_COMPRA)

    # PRIMEIRO: isto e mesmo a pergunta? Um numero lido de outra coisa qualquer
    # nao vira "quanto o jogo vai cobrar" so por estar dentro do recorte.
    palavras = comum.normalizar(texto)

    if not any(p in palavras for p in PALAVRAS_DO_DIALOGO):
        comum.contar('dialogo_ausente')
        _guardar_falha('dialogo_ausente', ['esperado: ' + str(esperado), texto])
        return 'ausente', None, 'o dialogo de confirmacao nao esta na tela'

    # O PRECO, E SO ELE: juntar todos os digitos colava o "1" de "Buy 1 pieces"
    # no preco, lia 1.255.988 no lugar de 255.988 e recusava toda compra
    cobrado = comum.preco_do_dialogo(texto)

    if cobrado is None:
        comum.contar('dialogo_ilegivel')
        _guardar_falha('dialogo_ilegivel', ['esperado: ' + str(esperado), texto])
        # ILEGIVEL NAO E DIVERGENTE. O dialogo esta la, o texto e o certo, e so o
        # numero nao saiu - recusar aqui jogaria fora uma compra boa por causa do
        # OCR. Segue com o valor previsto, que ja passou por duas leituras.
        return 'ok', esperado, ''

    if esperado is not None and cobrado == esperado:
        return 'ok', cobrado, ''

    if aceitar is None:
        return 'ok', cobrado, ''

    pode, motivo = aceitar(cobrado)

    if not pode:
        return 'recusar', cobrado, motivo

    return 'revisto', cobrado, (f'o jogo vai cobrar {comum.fmt(cobrado)} e a '
                                f'lista dizia {comum.fmt(esperado)} - segue')


def comprar_uma(esperado, aceitar=None):
    """Da os tres cliques de compra. Devolve (situacao, preco_pago, motivo).

      'comprou'       a tela confirmou. <preco_pago> e o que o jogo cobrou.
      'recusado'      o valor de verdade nao vale a compra - decisao, nao falha.
      'ausente'       os cliques nao produziram o dialogo. Falha.
      'nao_confirmou' clicou tudo e a oferta nao saiu da lista. Falha.

    SAO TRES CLIQUES: Comprar na linha da oferta abre o painel, Comprar dentro
    do painel pede a compra, e o Sim do dialogo confirma. So no terceiro a prata
    sai - e e entre o segundo e o terceiro que da para conferir o valor.

    A CONFIRMACAO OLHA A LINHA INTEIRA, e nao so o preco. Quem vende copia o
    preco de quem esta na frente, e duas ofertas seguidas com o mesmo valor sao
    comuns. Consumida a primeira, a regiao do preco fica pixel a pixel identica,
    e o bot concluia que a compra nao tinha acontecido - abandonando justamente
    as ofertas mais baratas. Na linha inteira sempre ha o que mudar: o tempo
    restante e a quantidade sao de cada oferta."""

    antes = comum.assinatura(cd.CMP_LINHA_OFERTA)

    comum.secao_critica.set()

    try:
        comum.clicar(cd.CMP_COMPRAR_1)   # 1. na linha da oferta, abre o painel
        comum.clicar(cd.CMP_COMPRAR_2)   # 2. dentro do painel, pede a compra

        situacao, cobrado, motivo = conferir_dialogo(esperado, aceitar)

        if situacao not in ('ok', 'revisto'):

            if situacao == 'recusar':
                comum.contar('dialogo_recusado')

            # O "Nao" fecha A PERGUNTA. O painel de compra continua aberto por
            # cima da lista, e daqui para a frente tudo que o bot ler e clicar
            # cai nele. Sair pelo X e parte de recusar.
            comum.clicar(cd.CMP_NAO_COMPRAR)
            comum.clicar(cd.CMP_FECHAR_PAINEL)

            return (('recusado' if situacao == 'recusar' else 'ausente'),
                    None, motivo)

        comum.clicar(cd.CMP_CONFIRMAR_SIM)

    finally:
        comum.secao_critica.clear()

    if not comum.esperar_mudanca(cd.CMP_LINHA_OFERTA, antes, ESPERA_COMPRA):
        comum.contar('compras_nao_confirmadas')
        return 'nao_confirmou', None, 'a tela nao confirmou'

    # A LISTA INTEIRA E QUE PRECISA ASSENTAR: a oferta comprada sai e as de
    # baixo sobem um lugar. E precisa assentar DE VERDADE - sondando o mais
    # rapido possivel, as oito leituras iguais acontecem em 50 ms, e 50 ms depois
    # do clique o jogo nem comecou a redesenhar. O bot lia a oferta que acabara
    # de comprar e clicava nela de novo.
    comum.esperar_estavel(cd.CMP_LINHA_OFERTA, ESPERA_COMPRA,
                          comum.LEITURAS_IGUAIS_PRECO, comum.SONDAGEM_LENTA)

    comum.contar('compras_na_hora')

    return 'comprou', (cobrado if cobrado is not None else esperado), motivo


# O painel do item e o livro ao lado, para o print de diagnostico.
TELA_DO_PAINEL = (420, 280, 1510, 790)

# Prints do painel por operacao - o bastante para entender, sem encher a pasta.
MAXIMO_DE_PRINTS_DO_PAINEL = 3


def guardar_tela_do_painel(nome):
    """Salva o painel inteiro como esta agora. Devolve o caminho, ou None.

    Nao e o salvar_diagnostico: aquele guarda o ultimo recorte do OCR, e aqui o
    que importa e a tela toda - onde o painel abriu e o que o livro mostra."""

    if not SALVAR_FALHAS or comum.contador('prints_do_painel') >= MAXIMO_DE_PRINTS_DO_PAINEL:
        return None

    comum.contar('prints_do_painel')

    try:
        seguro = ''.join(c if c.isalnum() or c in ' -_.' else '_' for c in nome).strip()
        caminho = os.path.join(comum.pasta_registro(PASTA_FALHAS),
                               f'{time.strftime("%H%M%S")}_painel_{seguro}.png')
        comum.capturar(TELA_DO_PAINEL).save(caminho)
        return caminho

    except Exception:
        return None


def _guardar_falha(nome, extras, regiao=None):

    if not SALVAR_FALHAS:
        return

    comum.salvar_diagnostico(PASTA_FALHAS,
                             time.strftime('%H%M%S') + '_' + nome,
                             regiao=regiao or cd.CMP_DIALOGO_COMPRA, extras=extras)

#endregion
