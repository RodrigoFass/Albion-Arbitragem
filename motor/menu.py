################################
#                              #
#             MENU             #
#                              #
################################

# Desce o menu em cascata do mercado ate selecionar um item.
#
#     Weapons  ->  Crossbow  ->  Crossbow
#
# Feito isso, A LISTA CONTEM SO AQUELE ITEM. E o que torna o resto do programa
# possivel: ler cinco linhas de uma vez so faz sentido se as cinco forem do mesmo
# item, e ate aqui a unica forma de saber isso era ler o nome de cada uma.
#
#
# CONFERE ANTES DE CLICAR, SEMPRE. A posicao de cada entrada e calculada - indice
# vezes 27 px - e a conta esta certa hoje. Mas o jogo acrescenta armas, e no dia
# em que uma entrar no meio de uma familia todas as de baixo descem uma linha. O
# clique continuaria acontecendo, no vizinho, e a compra sairia do item errado
# sem nada reclamar.
#
# Por isso cada passo le o que esta escrito no lugar antes de tocar nele. Calcular
# e barato, ler e barato, e errado sai caro.
#
#
# ESPERA PELO CONTEUDO, E NAO POR PIXEL. Um submenu aberto tem sempre "All" na
# primeira linha - e esse texto que prova que ele desenhou. Esperar os pixels
# mudarem daria falso positivo quando o submenu ja estivesse aberto de um item
# anterior, e falso negativo quando o novo fosse parecido com o velho.
#
# E a mesma licao do bot_comprar: pixel parado nao quer dizer tela pronta.
#
# Antes de alterar: python -m pyflakes menu.py

import time

from motor import categorias as cat
from motor import comum
from motor import coordenadas as cd
from motor.comum import relatar

#region Configuracao

# Limite esperando um nivel do menu desenhar.
#
# Generoso de proposito. Nao custa tempo quando o jogo esta rapido - quem espera
# volta assim que le o que procura - e custa so nos casos em que a alternativa
# era clicar numa lista que ainda nao existe.
ESPERA_MENU = 2.00

# Respiro entre uma leitura e a seguinte, enquanto insiste.
ESPERA_ENTRE_LEITURAS = 0.15

# A palavra que encabeca TODA lista deste menu. E ela que prova que um submenu
# terminou de desenhar.
PRIMEIRA_ENTRADA = 'All'

#endregion

#region Leitura


def _ler(indices):
    """O texto da entrada naquela posicao do menu."""

    with comum.cronometro('leitura do menu'):
        return comum.ler_texto(cat.regiao(indices))


def _esperar_texto(indices, esperado, limite=ESPERA_MENU):
    """Insiste ate a posicao mostrar <esperado>. 'ok', 'outro' ou 'ilegivel'.

    Tres resultados e nao dois, pela mesma razao de sempre neste programa: texto
    que CONTRADIZ o esperado e evidencia de que a posicao esta errada; texto que
    nao da para ler e ausencia de evidencia. Tratar os dois igual faria o bot
    parar de funcionar no dia em que o OCR piorasse um pouco."""

    fim = time.monotonic() + limite

    lido = ''
    so_ilegivel = True

    while True:

        comum.checar_aborto()

        lido = _ler(indices)
        igual = comum.parece_o_mesmo_item(lido, esperado)

        if igual:
            return 'ok'

        if igual is False:
            so_ilegivel = False

        if time.monotonic() >= fim:
            break

        time.sleep(ESPERA_ENTRE_LEITURAS)

    comum.contar('menu_ilegivel' if so_ilegivel else 'menu_fora_do_lugar')

    return 'ilegivel' if so_ilegivel else 'outro'

#endregion

#region Navegacao


def aberto():
    """True se o menu de categoria ja esta na tela."""

    return comum.parece_o_mesmo_item(_ler([0]), PRIMEIRA_ENTRADA) is True


def abrir():
    """Abre o menu de categoria. True se ele apareceu.

    Confere ANTES de clicar se ele ja nao estava aberto: com o menu na tela, o
    clique no botao FECHA - e a navegacao seguinte aconteceria em cima da lista,
    clicando em ofertas."""

    if aberto():
        return True

    comum.clicar(cat.MENU_BOTAO, espera=0)

    return _esperar_texto([0], PRIMEIRA_ENTRADA) == 'ok'


def fechar():
    """Fecha o menu de categoria, se ele estiver na tela.

    MENU QUE FALHOU NO MEIO FICAVA ABERTO, por cima da lista. Dali em diante os
    cliques do item seguinte - a busca, o filtro, o Comprar - caiam nas entradas
    do menu, e o bot se perdia no meio dos itens."""

    if aberto():
        comum.clicar(cat.MENU_BOTAO, espera=0)
        comum.contar('menu_fechado_na_falha')


def _limpar_busca():
    """Esvazia a caixa de busca e espera a lista voltar.

    A BUSCA DO ITEM ANTERIOR FICA NA CAIXA. O menu filtra a lista por cima dela:
    depois de "Hoarfrost Staff" pela busca, o menu de "Arcane Staff" mostrava o
    cruzamento dos dois - nada -, e o item era pulado. E o mesmo botao de limpar
    a busca nas duas telas, a da cidade e a do Mercado Negro."""

    comum.clicar(cd.CMP_RESET)
    comum.esperar_estavel(cd.CMP_LINHA_ITEM, ESPERA_MENU,
                          intervalo=comum.SONDAGEM_LENTA)


def _abrir_submenu(indices):
    """Passa o mouse no item e espera o submenu dele desenhar."""

    comum.apontar(cat.posicao(indices))

    # o "All" do filho fica na MESMA altura do pai, uma coluna a direita
    return _esperar_texto(indices + [0], PRIMEIRA_ENTRADA) == 'ok'


def selecionar(item):
    """Desce o menu ate <item> e clica nele. Devolve (ok, motivo).

    Depois disso a lista mostra so esse item, em todos os graus e encantamentos
    que existirem - os filtros de grau e encantamento continuam sendo o que
    separa as 13 combinacoes.

    NAO espera a lista filtrar: quem chama sabe o que vai ler em seguida e tem
    como esperar pelo conteudo certo. Esperar aqui seria esperar por algo
    generico, que e sempre a espera mais cara e a menos confiavel."""

    indices = cat.indices(item)
    rotulos = cat.rotulos(item)

    if indices is None:
        return False, f'"{item}" nao tem caminho de menu conhecido'

    _limpar_busca()

    if not abrir():
        return False, 'o menu de categoria nao abriu'

    ok, motivo = _descer(indices, rotulos)

    if not ok:
        fechar()

    return ok, motivo


def _descer(indices, rotulos):
    """Os niveis do menu, ja aberto, ate clicar no item. (ok, motivo)."""

    for nivel, esperado in enumerate(rotulos):

        alvo = indices[:nivel + 1]
        situacao = _esperar_texto(alvo, esperado)

        if situacao == 'outro':
            comum.contar('menu_desalinhado')
            return False, (f'no nivel {nivel + 1} a posicao de "{esperado}" '
                           f'mostra outra coisa - o jogo mudou a lista?')

        if situacao == 'ilegivel':
            # sem evidencia de erro. Segue, mas fica registrado: se isto virar
            # rotina, o recorte do menu e que esta errado, e nao o jogo
            comum.contar('menu_ilegivel_seguiu')

        ultimo = nivel == len(rotulos) - 1

        if ultimo:
            comum.clicar(cat.posicao(alvo))
            comum.contar('itens_selecionados')
            return True, ''

        if not _abrir_submenu(alvo):
            return False, f'o submenu de "{esperado}" nao abriu'

    return False, 'caminho de menu vazio'


def selecionar_ou_relatar(item):
    """selecionar() que escreve o motivo no log quando falha."""

    ok, motivo = selecionar(item)

    if not ok:
        relatar(f'      MENU: {motivo}')

    return ok

#endregion
