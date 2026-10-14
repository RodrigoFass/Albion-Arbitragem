################################
#                              #
#        MERCADO NEGRO         #
#                              #
################################

# Ler os precos do Mercado Negro, que funciona de um jeito diferente do mercado
# das cidades.
#
#     na CIDADE   o item e selecionado pelo menu de categoria, os filtros de
#                 grau e encantamento ficam na barra de cima, e o preco esta na
#                 primeira linha da lista.
#
#     no NEGRO    voce digita o nome, clica em "Vender" na primeira linha, e o
#                 painel que abre e que tem os dropdowns de grau e encantamento.
#                 O preco esta no livro de ofertas, dentro do painel.
#
# E o fluxo do bot_atualizar da v1, e ele foi mantido porque funciona: cinco
# meses de varredura passaram por ele.
#
#
# A ARMADILHA DO DROPDOWN DE GRAU. A lista de graus do painel NAO COMECA NO
# GRAU 1. Ela comeca no grau base do item - Espada Larga abre em Grau 1, Arco em
# Grau 2, Besta em Grau 3, Arco de Guerra em Grau 4 - e COM encantamento ela e
# truncada no Grau 4, porque item encantado so existe dali para cima.
#
# Ou seja: a mesma coordenada seleciona graus diferentes conforme o item e o
# encantamento. Ignorar isso nao da erro nenhum - da preco do grau errado
# gravado como se fosse do certo, que e a pior forma de estar quebrado.
#
# A v1 resolvia com uma coluna na planilha guardando o grau base de cada item.
# Aqui nao ha planilha, e sao 252 itens - entao o bot DESCOBRE sozinho: clica
# onde acha que deve, LE o rotulo do dropdown, e se o numero nao for o esperado
# corrige pela diferenca e clica de novo. Uma correcao basta, porque o erro e um
# deslocamento constante, e a partir dai o item esta calibrado.
#
#
# QUEM E AMBIGUO VAI PELO MENU. A busca do jogo devolve tudo que contem o que
# voce digitou: "Cursed Staff" traz o "Great Cursed Staff" junto. Sao 18 itens
# nessa situacao, e so eles pagam o preco de tres passadas de mouse pelo menu em
# cascata; os outros 234 vao pela busca, que e bem mais rapida.
#
# Antes de alterar: python -m pyflakes mercado_negro.py

import time

from motor import categorias
from motor import comum
from motor import coordenadas as cd
from motor import filtros
from motor import menu

#region Configuracao

# OS MESMOS TEMPOS DO bot_atualizar. Eles nao sao chute - sairam de meses de
# varredura, e cada um foi mexido por causa de um defeito concreto.
ESPERA_BUSCA = 2.00     # limite esperando a lista filtrar depois de digitar
ESPERA_PAINEL = 2.50    # limite esperando o painel de Pedido de Venda abrir
ESPERA_ROTULO = 0.20    # respiro antes de reler um rotulo ilegivel

# Pular a reselecao do grau quando ele nao mudou. O grau PERMANECE selecionado
# atraves das trocas de encantamento - isto vem do bot_atualizar, que rodou
# meses assim. Desligue para voltar a clicar o grau em toda combinacao.
PULAR_GRAU_REPETIDO = True

# Quantas vezes corrigir o grau antes de desistir da combinacao.
#
# Uma basta quando o erro e o deslocamento da lista. Duas cobrem o caso de a
# primeira leitura do rotulo ter saido errada.
CORRECOES_DE_GRAU = 2

SALVAR_FALHAS = True
PASTA_FALHAS = 'falhas_mercado_negro'

#endregion

#region A tela


def _deteccao(barra=None):
    """Faixa onde a primeira opcao aparece quando um dropdown DO PAINEL abre.

    O painel de Pedido de Venda tem os dropdowns bem mais abaixo que a barra de
    cima da cidade: a primeira opcao sai em y=423, contra y=300 la. Sem passar
    isto, a espera fica olhando um pedaco de tela que nunca muda - e a lista
    "nao abre" em toda troca de filtro."""

    x = (barra or cd.VND_BARRA_TIER)['x']

    return (x - cd.VND_DETECCAO_MEIA_LARGURA,
            cd.VND_DROPDOWN_TOPO - cd.VND_DETECCAO_MEIA_ALTURA,
            x + cd.VND_DETECCAO_MEIA_LARGURA,
            cd.VND_DROPDOWN_TOPO + cd.VND_DETECCAO_MEIA_ALTURA)


def _regiao_do_preco():
    """A regiao do PRIMEIRO preco de "Pedidos de venda".

    A COLUNA DE VENDA, e nao a de compra. E o preco por que o item esta sendo
    OFERTADO no Mercado Negro - o numero que interessa a arbitragem. A coluna
    de compra mostra o que alguem se dispoe a pagar, que e outro numero e
    costuma ser bem menor.

    A regiao vem de cd.PRECO_VENDA - a mesma constante calibrada a mao que o
    bot_atualizar usa - e nao da formula venda_preco(n), que deriva as linhas
    do livro por calculo e nunca foi conferida no jogo."""

    return cd.PRECO_VENDA


def ler_preco(anterior=None):
    """O melhor preco do livro. None se ninguem estiver comprando.

    <anterior> e o preco da combinacao passada. Exigir um valor diferente dele e
    o que impede a leitura de sair um passo atrasada: o painel demora a
    redesenhar, e ate redesenhar ele mostra o numero de antes."""

    return comum.ler_numero_novo(_regiao_do_preco(), anterior)


def livro_vazio():
    """True quando o jogo diz que nao ha oferta nenhuma para o item.

    "NO MOMENTO NINGUEM ESTA VENDENDO ESTE ITEM NO MERCADO" nao e falha de
    leitura - e o mercado respondendo que ali nao ha negocio. Confundir as duas
    faria o bot insistir numa tela que nunca vai ter numero.

    So consultado quando a leitura do preco volta vazia: e um OCR de TEXTO, bem
    mais caro que o de numero, e perguntar nas treze combinacoes de cada item
    seriam 1.573 leituras por varredura para responder algo que quase sempre e
    nao."""

    texto = comum.normalizar(comum.ler_texto(cd.LIVRO_AVISO_VAZIO))

    return 'ninguem' in texto or 'momento' in texto


def ler_grau():
    """O grau que o dropdown esta mostrando, lido do rotulo. None se ilegivel."""

    with comum.cronometro('leitura do grau'):
        texto = comum.ler_texto(cd.GRAU_ROTULO)

    digitos = ''.join(c for c in texto if c.isdigit())

    return int(digitos) if len(digitos) == 1 else None

#endregion

#region Abrir o item


def buscar(nome):
    """Digita o nome e espera a lista filtrar. True se ela mudou.

    Espera a lista MUDAR e so depois parar de mudar. Esperar apenas
    estabilidade nao resolve: logo depois de digitar, a lista ainda esta no
    estado anterior - e estado anterior tambem esta estavel. O clique em
    "Vender" abriria o painel do item que estava ali antes."""

    comum.clicar(cd.VND_RESET)
    comum.clicar(cd.VND_BUSCA)

    antes = comum.assinatura(cd.LINHA_ITEM)

    comum.digitar(nome)

    if comum.esperar_mudanca(cd.LINHA_ITEM, antes, ESPERA_BUSCA):
        comum.esperar_estavel(cd.LINHA_ITEM, ESPERA_BUSCA)
        return True

    return False


def abrir_painel():
    """Clica em Vender na primeira linha e espera o painel desenhar."""

    antes = comum.assinatura(_regiao_do_preco())

    comum.clicar(cd.VND_VENDER, espera=0)

    if comum.esperar_mudanca(_regiao_do_preco(), antes, ESPERA_PAINEL):
        comum.esperar_estavel(_regiao_do_preco(), ESPERA_PAINEL)
        return True

    # o painel pode ter aberto sem mudar aquele recorte - a leitura decide
    return comum.ler_numero(_regiao_do_preco()) is not None or livro_vazio()


def fechar_painel():
    comum.clicar(cd.VND_FECHAR)


# Se o item atual foi aberto pelo menu - e por isso deixou a categoria fixada.
_veio_do_menu = False


def abrir(item, nome_de_busca=None):
    """Deixa o painel de venda do <item> aberto. Devolve (ok, motivo).

    UM CAMINHO POR ITEM. Os 18 cujo nome cabe dentro do nome de outro vao pelo
    MENU, que desce ate o item e deixa a lista no que se quer; os 234 restantes
    vao pela busca, que custa um clique e uma digitacao contra tres passadas de
    mouse com leitura de rotulo em cada uma.

    Digitar por cima do menu seria trabalho e espera para nao mudar nada."""

    global _veio_do_menu

    _veio_do_menu = categorias.ambiguo(item)

    if _veio_do_menu:

        ok, motivo = menu.selecionar(item)

        if not ok:
            return False, motivo

        comum.contar('abertos_pelo_menu')

    else:

        if not buscar(nome_de_busca or categorias.no_menu(item)):
            comum.contar('busca_sem_efeito')

        comum.contar('abertos_pela_busca')

    if not abrir_painel():
        return False, 'o painel de venda nao abriu'

    return True, ''


def limpar_selecao():
    """Fecha o painel. E so isso.

    NADA DE BOTAO DE RESETAR AQUI. O da direita zera os filtros de grau e
    encantamento DA BARRA DE CIMA, e no Mercado Negro esses filtros nao sao
    usados: os dropdowns que interessam ficam dentro do painel de Pedido de
    Venda e vao embora com ele. Clicar ali era um clique por item sem efeito
    nenhum sobre a proxima leitura.

    A busca tambem nao precisa ser zerada aqui - o proximo item comeca clicando
    no reset da busca antes de digitar, que e a sequencia do bot_atualizar."""

    fechar_painel()

#endregion

#region O dropdown de grau, que se calibra sozinho

# Onde a lista de graus comeca, por item. Descoberto na primeira correcao e
# reaproveitado nas 12 combinacoes seguintes daquele item.
# O GRAU EM QUE A LISTA COMECA, item por item, vindo da tabela do bot_atualizar.
#
# Nao e detalhe: a mesma coordenada do dropdown seleciona graus DIFERENTES
# conforme o item. Espada Larga abre em Grau 1, Arco em 2, Besta em 3, Arco de
# Guerra em 4 - pedir o Grau 6 num item que comeca no 4 clicando a sexta linha
# seleciona o Grau 9. Nao da erro: da o preco de outro grau gravado no lugar do
# certo.
#
# Sao 121 dos 252. O resto se descobre sozinho, lendo o rotulo e corrigindo pela
# diferenca - o que funciona, mas custa um clique de dropdown a mais no primeiro
# item de cada nome. Ter a tabela dispensa isso onde ela existe, e e o mesmo
# numero que o bot_atualizar usava na coluna AE.
ARQUIVO_GRAUS = 'graus-base.json'

_grau_base = None


def graus_base():
    """A tabela, lida uma vez. Vazia se o arquivo nao estiver la."""

    global _grau_base

    if _grau_base is None:

        try:
            import json
            import os

            # a pasta do programa, e nao a deste arquivo: empacotado, o codigo
            # mora numa subpasta interna e o json fica ao lado do .exe
            caminho = os.path.join(comum.PASTA_RECURSOS, ARQUIVO_GRAUS)

            with open(caminho, encoding='utf-8') as f:
                _grau_base = {n: int(g) for n, g in json.load(f).items()}

        except Exception:
            _grau_base = {}

    return _grau_base


_inicio_conhecido = {}


def esquecer_calibragem():
    """Esquece o que foi APRENDIDO na tela. A tabela continua valendo.

    O que se aprendeu lendo rotulo vale para a sessao; o que veio da tabela vale
    sempre, e apagar seria jogar fora a informacao mais confiavel que existe
    aqui."""

    _inicio_conhecido.clear()


def _inicio(item, ench):
    """Em que grau a lista do dropdown comeca, para este item e encantamento.

    A chave inclui SE HA ENCANTAMENTO, e nao o encantamento em si: a lista e a
    mesma para 1, 2 e 3 - truncada no Grau 4 - e diferente para o 0, que comeca
    no grau base do item.

    Duas chaves e nao uma porque o que se aprende numa nao vale na outra:
    descobrir que a lista encantada comeca no 4 nao diz nada sobre onde comeca
    a lista sem encantamento, ja que 4 e o piso de todas."""

    if (item, ench >= 1) in _inicio_conhecido:
        return _inicio_conhecido[(item, ench >= 1)]

    # A TABELA PRIMEIRO. Com encantamento a lista e truncada no Grau 4, porque
    # item encantado so existe a partir dali - por isso o max().
    base = graus_base().get(item)

    if base is not None:
        return max(base, 4) if ench >= 1 else base

    # Sem tabela, o palpite mais barato: erra por deslocamento constante, e a
    # primeira leitura do rotulo corrige.
    return 4 if ench >= 1 else 1


def _posicao_do_grau(item, grau, ench):
    """A opcao do dropdown que corresponde aquele grau. None se nao existir."""

    indice = grau - _inicio(item, ench) + 1

    if indice < 1:
        return None

    return {'x': cd.VND_BARRA_TIER['x'], 'y': cd.opcao_venda(indice)}


def escolher_grau(item, grau, ench):
    """Seleciona o grau e CONFERE pelo rotulo, corrigindo se errar.

    Devolve 'ok', 'ilegivel' ou 'nao_conseguiu'.

    A correcao e o coracao deste modulo. Errar aqui nao da erro: da o preco de
    outro grau gravado no lugar do certo. Como o erro e um deslocamento
    constante - a lista comecou N graus acima do que se supunha - a diferenca
    entre o que se pediu e o que apareceu E a calibragem, e uma correcao basta.
    """

    for tentativa in range(1 + CORRECOES_DE_GRAU):

        alvo = _posicao_do_grau(item, grau, ench)

        if alvo is None:
            return 'nao_conseguiu'

        filtros.trocar(
            lambda: filtros.escolher(cd.VND_BARRA_TIER, alvo,
                                     _deteccao(cd.VND_BARRA_TIER),
                                     afastar=False),
            regiao=_regiao_do_preco())

        lido = ler_grau()

        if lido is None:
            time.sleep(ESPERA_ROTULO)
            lido = ler_grau()

        if lido is None:
            # ROTULO ILEGIVEL nao e evidencia de erro - so falta de evidencia.
            # Aceitar em silencio ja fez gravar preco de grau errado; descartar
            # ja esvaziou leituras boas. O certo e gravar e sinalizar.
            comum.contar('grau_ilegivel')
            return 'ilegivel'

        if lido == grau:
            return 'ok'

        # A DIFERENCA E A CALIBRAGEM, e o sinal importa.
        #
        # Clicou-se a opcao numero  i = grau - suposto + 1.
        # O jogo selecionou        lido = real + i - 1.
        # Logo                     real = suposto + (lido - grau).
        #
        # Pediu o 6 e apareceu o 9: a lista comeca TRES graus acima do suposto.
        # Com o sinal trocado a correcao anda para o lado errado e cada
        # tentativa afasta mais - foi o que o teste pegou.
        suposto = _inicio(item, ench)
        _inicio_conhecido[(item, ench >= 1)] = max(1, suposto + (lido - grau))

        # o que se aprende sem encantamento vale para a lista encantada, que e a
        # mesma truncada no 4 - e isso poupa a segunda correcao do item
        if ench == 0:
            _inicio_conhecido.setdefault(
                (item, True), max(_inicio_conhecido[(item, False)], 4))

        comum.contar('grau_corrigido')

    comum.contar('grau_contradiz')

    return 'nao_conseguiu'


def escolher_encantamento(ench):
    """O dropdown de encantamento. A lista dele sempre comeca no 0."""

    alvo = {'x': cd.VND_BARRA_ENCH['x'], 'y': cd.opcao_venda(ench + 1)}

    filtros.trocar(
        lambda: filtros.escolher(cd.VND_BARRA_ENCH, alvo, _deteccao(alvo),
                                 afastar=False),
        regiao=_regiao_do_preco())

#endregion

#region Varredura


class Tela:
    """O painel de Pedido de Venda, do ponto de vista de quem le um item.

    E o mesmo contrato da Cidade do conferidor: abrir, fechar, base, ler, vazio,
    encantamento, grau. O laco de leitura e um so para os dois mercados, e o que
    muda mora aqui - a regiao do preco, os dropdowns dentro do painel, e o grau
    que pode contradizer o rotulo.

    Com isto a repescagem e a auditoria passam a rodar NESTA tela quando a
    varredura e daqui. Antes elas chamavam a leitura da cidade direto: clicavam
    na barra de cima, que o Mercado Negro nao usa, e liam a coluna de compra em
    vez da de venda."""

    def __init__(self):
        self.regiao = cd.PRECO_VENDA

    def abrir(self, item):
        return abrir(item)

    def fechar(self):
        limpar_selecao()

    def base(self):
        return ler_preco()

    def ler(self, anterior):
        return ler_preco(anterior)

    def outro_preco(self):
        """O primeiro "pedido de compra", lido na mesma passada.

        E O NUMERO DA ESTRATEGIA DE VENDA: vender na hora casa com um pedido de
        compra existente, e entrar na fila e por uma ordem um pouco abaixo do
        vendedor mais barato. Sao colunas diferentes, e voltar depois so para
        pegar a segunda custaria a varredura inteira de novo.

        Custa um OCR de numero por combinacao lida - nao por combinacao
        percorrida."""

        return comum.ler_numero(cd.compra_preco(0))

    def vazio(self):
        return livro_vazio()

    def encantamento(self, ench):
        escolher_encantamento(ench)

    def grau(self, item, grau, ench):
        # O GRAU SO E CLICADO QUANDO MUDA - quem chama ja garante isso. Ele
        # permanece selecionado atraves das trocas de encantamento, e e assim
        # que o bot_atualizar rodou por meses.
        return escolher_grau(item, grau, ench) != 'nao_conseguiu'


# A leitura em si mora no conferidor, que recebe esta Tela e trata os dois
# mercados com o mesmo laco.
TELA = Tela()

#endregion
