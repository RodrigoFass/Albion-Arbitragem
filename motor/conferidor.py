################################
#                              #
#          CONFERIDOR          #
#                              #
################################

# Enche o banco de precos: para cada item, le quanto custa cada combinacao de
# grau e encantamento NO MERCADO EM QUE VOCE ESTA, e guarda com a hora da
# leitura.
#
# E a primeira metade da arbitragem. A segunda - decidir o que comprar - e
# aritmetica em cima do que este modulo coletou, e vive no lucro.py.
#
# RODA DUAS VEZES POR ROTA, em lugares diferentes:
#
#     no Mercado Negro, em Caerleon   quanto ele PAGA por cada item
#     na cidade                       quanto custa COMPRAR cada item
#
# A mesma varredura nos dois: e o mesmo mercado, a mesma barra de filtros, a
# mesma lista. So muda o nome sob o qual os precos sao guardados.
#
#
# O ITEM E SELECIONADO PELO MENU, e nao pela busca. Isso muda mais do que
# parece: com a categoria fixada a lista contem so aquele item, e ai o preco da
# primeira linha e o preco daquele item, ponto. Nao ha o que conferir por
# leitura, e a duvida que atravessou o programa antigo inteiro - "sera que a
# lista esta mostrando o que eu pedi?" - deixa de existir.
#
#
# LE UMA LINHA SO, e de proposito. Com a lista ordenada por "Price - Lowest" a
# oferta mais barata esta sempre na primeira, e e ela que interessa: e o preco
# que a decisao de compra vai usar. Ler as cinco custaria cinco vezes mais OCR
# para responder a mesma pergunta.
#
# Antes de alterar: python -m pyflakes conferidor.py

import os
import random
import time
import traceback

from motor import categorias
from motor import comum
from motor import coordenadas as cd
from motor import escuta
from motor import filtros
from motor import menu
from motor import mercado
from motor.comum import relatar

#region Configuracao

# As 13 combinacoes de grau e encantamento que valem a pena, na ordem em que sao
# varridas: do mais fraco para o mais forte.
#
# A ordem importa duas vezes. A troca de filtro fica barata - encantamento anda
# dentro do mesmo grau - e a leitura fica conferivel: dentro de um item os
# precos crescem, e uma sequencia que quebra essa ordem denuncia leitura ruim
# sem precisar de outra fonte.
# Uma fonte so, no mercado.py - a ordem delas e o que agrupa por grau e faz o
# dropdown ser clicado o minimo possivel, e duas copias sao duas ordens.
COMBINACOES = mercado.COMBINACOES

# Itens seguidos com falha que fazem a varredura parar.
#
# Sem isto, com o mercado fechado ou a janela em outro lugar, o bot percorreria
# a lista inteira falhando um por um - minutos de cliques inuteis antes de o
# resumo dizer que todos deram erro.
MAX_ITENS_COM_ERRO_SEGUIDOS = 3

# --- Faixa de plausibilidade ----------------------------------------------
# Um preco lido e confrontado com o que JA HAVIA no banco para a mesma
# combinacao no mesmo mercado. Fora desta faixa a leitura e descartada, com
# registro e com PNG.
#
# A barreira existe por uma razao concreta, herdada do bot que gasta prata: se o
# OCR JUNTA digitos o numero cresce e a compra nao acontece - falha inofensiva.
# Se ele PERDE o digito da frente, acontece o contrario: 1.358.869 lido como
# 358.869 vira uma oportunidade que nao existe.
#
# A FAIXA E LARGA DE PROPOSITO, e isso tambem foi aprendido caro. Na v1 o piso
# esteve em 0,40 e bloqueou 33 de 39 leituras BOAS - precos de mercado se movem
# muito mais do que a intuicao diz. Aqui a comparacao e contra o mesmo mercado, o
# que e bem mais estavel que comparar dois mercados; ainda assim, largo.
FAIXA_MIN = 0.08
FAIXA_MAX = 2.50

SALVAR_FALHAS = True
PASTA_FALHAS = 'falhas_conferidor'




#endregion

#region Uma combinacao


# Quem esta sendo lido agora. Existe so para a amostra de borda sair com nome de
# item e combinacao em vez de um numero de relogio - um PNG anonimo nao diz em
# que tela ele foi tirado.
def _situacao(local, item, rotulo):

    ATUAL.onde, ATUAL.item, ATUAL.rotulo = local, item, rotulo


def _anotar(arquivo, texto):
    """Escreve no registro do mercado. Nunca levanta."""

    if arquivo is None:
        return

    try:
        arquivo.write(texto.rstrip() + chr(10))
    except Exception:
        pass


def _abrir_registro(local):
    """Um arquivo por mercado e por dia, dentro de registros/varreduras.

    Devolve o arquivo aberto, ou None. Falhar aqui nao pode derrubar a varredura:
    o registro e para depois, e a coleta e para agora."""

    try:
        destino = comum.pasta_registro('varreduras')

        seguro = ''.join(ch if ch.isalnum() else '-' for ch in local)
        nome = f'{time.strftime("%Y-%m-%d")}_{seguro}.txt'

        arquivo = open(os.path.join(destino, nome), 'a', encoding='utf-8')
        arquivo.write(chr(10) + f'===== {time.strftime("%H:%M:%S")} - {local}'
                      f' - {comum.VERSAO} ====={chr(10)}')

        return arquivo

    except Exception:
        comum.contar('registro_do_mercado_falhou')
        return None


def _fechar_registro(arquivo):

    if arquivo is None:
        return

    try:
        arquivo.close()
    except Exception:
        pass


def limpar_a_tela(local=None, tela=None):
    """Zera o que sobrou da ultima vez que alguem mexeu naquela tela.

    Chamada uma vez, no comeco da execucao. O jogo guarda o estado entre sessoes,
    e o que voce deixou ali nao tem como ser adivinhado - so desfeito.

    NO MERCADO NEGRO E SO A BUSCA. Os filtros de grau e encantamento da barra de
    cima nao sao usados naquela tela: os dropdowns que valem ficam dentro do
    painel de Pedido de Venda. Clicar no botao de resetar da direita ali seria um
    clique sem efeito sobre leitura nenhuma."""

    comum.clicar(cd.CMP_RESET)

    if local != mercado.MERCADO_NEGRO:
        filtros.limpar()


# Quantas amostras da borda guardar por execucao. Tres bastam para ver o
# enquadramento; uma por combinacao encheria a pasta com a mesma imagem.
AMOSTRAS_DE_BORDA = 3

def _amostrar_borda(local, item, rotulo, preco):
    """Guarda um PNG quando algo esta encostado na borda esquerda do recorte.

    E O UNICO JEITO DE SABER O QUE ESTA ENCOSTADO ALI. Pode ser o icone da moeda
    invadindo a regiao, ou o primeiro digito raspado pela borda - os dois
    estragam a leitura do mesmo jeito, e os dois se corrigem movendo a mesma
    coordenada, mas para lados OPOSTOS. Adivinhar qual foi como se troca uma
    leitura errada rara por uma errada frequente."""

    if not SALVAR_FALHAS or ATUAL.bordas_salvas >= AMOSTRAS_DE_BORDA:
        return

    ATUAL.bordas_salvas += 1

    comum.salvar_diagnostico(
        PASTA_FALHAS,
        f'{time.strftime("%H%M%S")}_{item}_{rotulo}_borda',
        regiao=cd.PRECO_COMPRA,
        extras=[f'mercado: {local}',
                f'leu: {preco}',
                'ha traco encostado na PRIMEIRA COLUNA do recorte.',
                'se for o icone da moeda, mova a borda esquerda de '
                'PRECO_COMPRA para a DIREITA.',
                'se for o primeiro digito, mova-a para a ESQUERDA.'])


def zerar_amostras():
    """Compatibilidade: zerar a execucao inteira e o que vale agora."""

    ATUAL.zerar()


def sem_ofertas():
    """True quando o jogo trocou a lista pelo quadro "No offers found.".

    E a RESPOSTA do mercado, nao uma falha: aquele filtro nao casa com nada.
    Confundir isso com uma tela lenta faz o bot esperar por um numero que nunca
    vai aparecer."""

    texto = comum.normalizar(comum.ler_texto(cd.CMP_SEM_OFERTAS))

    return 'no offers' in texto or 'nenhuma oferta' in texto


class _Execucao:
    """O que dura UMA varredura, e nada alem dela.

    Eram cinco variaveis de modulo com tres funcoes de zeramento espalhadas, e
    cada nova precisava ser lembrada no lugar certo. Uma esquecida vaza para a
    varredura seguinte - o contador de amostras vazando fazia a segunda execucao
    nao guardar diagnostico nenhum, em silencio.

    Um objeto so, zerado de uma vez: esquecer fica impossivel."""

    def __init__(self):
        self.zerar()

    def zerar(self):
        self.veio_do_menu = False
        self.sondar_rede = False     # testar a rede na proxima combinacao
        self.bordas_salvas = 0
        self.onde = ''
        self.item = ''
        self.rotulo = ''


ATUAL = _Execucao()

# Limite esperando a lista filtrar depois de digitar o nome.
#
# MAIOR QUE O DA TROCA DE FILTRO, e de proposito. Trocar um filtro redesenha as
# linhas; digitar um nome refaz a consulta inteira e a lista volta do servidor.
# E limite, nao pausa: acaba no instante em que a lista muda.
ESPERA_BUSCA = 3.50


def buscar(nome):
    """Digita o nome e espera a lista filtrar. True se ela mudou.

    A LISTA E CONFIRMADA PARADA ANTES DE TIRAR A BASE, e essa linha e a correcao
    do bug do "Travertine".
    
    Zerar a busca faz a lista voltar ao mercado inteiro - e o primeiro item dele
    em ordem alfabetica e uma pedra qualquer. Esse redesenho leva tempo. A versao
    anterior fotografava a lista no meio dele e digitava em seguida: a "mudanca"
    detectada era o redesenho do RESET terminando, nao a busca filtrando, e a
    espera dava por encerrada com a lista ainda sem filtro. O bot entao lia o
    preco da pedra achando que era o da espada.

    Depois disso a ordem de sempre: esperar a lista MUDAR e so entao parar de
    mudar. So estabilidade nao serve - logo depois de digitar a lista ainda esta
    no estado anterior, e estado anterior tambem esta estavel."""

    comum.clicar(cd.CMP_RESET)
    comum.clicar(cd.CMP_BUSCA)

    comum.esperar_estavel(cd.CMP_LINHA_ITEM, ESPERA_BUSCA,
                          intervalo=comum.SONDAGEM_LENTA)

    antes = comum.assinatura(cd.CMP_LINHA_ITEM)

    comum.digitar(nome)

    if comum.esperar_mudanca(cd.CMP_LINHA_ITEM, antes, ESPERA_BUSCA):
        comum.esperar_estavel(cd.CMP_LINHA_ITEM, ESPERA_BUSCA,
                              intervalo=comum.SONDAGEM_LENTA)
        return True

    comum.contar('busca_sem_efeito')

    return False


def abrir_item(item):
    """Deixa o <item> selecionado na lista. Devolve (ok, motivo).

    DUAS REGRAS, e cada item cai numa so:

      - Nome sem conflito: A BARRA DE PESQUISA. Digitar e um clique e uma
        digitacao; descer o menu em cascata sao tres passadas de mouse, cada uma
        com leitura de rotulo por OCR para confirmar que o ponteiro chegou onde
        devia. Sao 234 dos 252 itens.

      - Nome que cabe dentro de outro: O MENU, E SO ELE. A busca do jogo devolve
        tudo que CONTEM o que voce digitou - "Cursed Staff" traz o "Great Cursed
        Staff" junto, "Bow" traz Crossbow e Warbow - e o primeiro da lista pode
        ser o item errado. O menu desce ate o item, entao a lista ja fica no que
        se quer; digitar por cima seria trabalho e espera para nao mudar nada.
        Sao 18.

    O nome que aparece na primeira linha e conferido nos dois casos, mas so para
    CONTAR: ele depende de um OCR, e uma leitura ruim nao pode fazer uma
    varredura inteira voltar vazia."""

    ATUAL.veio_do_menu = categorias.ambiguo(item)

    nome = categorias.no_menu(item)

    if ATUAL.veio_do_menu:

        ok, motivo = menu.selecionar(item)

        if not ok:
            return False, motivo

        comum.contar('abertos_pelo_menu')

    else:
        buscar(nome)
        comum.contar('abertos_pela_busca')

    # CONFERE O QUE APARECEU. Preco mudando nao prova qual item esta na tela, e
    # quando a busca nao pega a lista continua mostrando o primeiro item do
    # mercado inteiro - uma pedra, um minerio, o que estiver em ordem alfabetica.
    #
    # AVISA, MAS NAO PULA. Ilegivel nao e contradicao, e mesmo a contradicao
    # depende de um recorte que pode estar fora do lugar: reprovando todos os
    # itens, a varredura voltaria vazia por causa da verificacao, e nao de um
    # defeito de leitura. O contador diz o que houve sem custar a coleta.
    lido = comum.ler_texto(cd.CMP_LINHA_ITEM)

    if comum.parece_o_mesmo_item(lido, nome) is False:
        comum.contar('item_diferente_na_lista')

    return True, ''


def ler_parado():
    """O preco que esta na tela agora, com a tela CONFIRMADA parada antes.

    Serve de base para a primeira combinacao de cada item. Ler sem esperar aqui
    devolveria o que sobrou do item anterior - a lista ainda esta redesenhando
    depois do menu - e uma base errada contamina a combinacao inteira."""

    comum.esperar_estavel(cd.PRECO_COMPRA, filtros.ESPERA_PRECO,
                          comum.LEITURAS_IGUAIS_PRECO, comum.SONDAGEM_LENTA)

    return comum.ler_numero(cd.PRECO_COMPRA)


def ler_combinacao(anterior=None):
    """Le o preco da primeira linha. Devolve o numero, ou None.

    <anterior> e o preco da combinacao passada. Exigir um valor DIFERENTE dele e
    o que impede a leitura de sair um passo atrasada: a lista demora para
    refiltrar, e ate refiltrar ela mostra o numero de antes. Esperar os pixels
    assentarem nao resolve - eles assentam com o valor velho na tela.

    TRES CAMINHOS, do mais barato para o mais caro:

      1. O numero veio e e diferente do anterior. E o caso comum, e custa uma
         leitura so - exatamente o que custava antes.
      2. Nao veio numero E a tela diz "No offers found.". Nao ha o que esperar:
         devolve vazio na hora, em vez de gastar as cinco releituras com espera
         crescente que existem para tela lenta.
      3. Qualquer outra coisa: insiste, que e o comportamento de sempre."""

    antes_da_borda = comum.contador('borda_suja')

    preco = comum.ler_numero(cd.PRECO_COMPRA)

    if comum.contador('borda_suja') > antes_da_borda:
        _amostrar_borda(ATUAL.onde, ATUAL.item, ATUAL.rotulo, preco)

    if preco is not None and preco != anterior:
        return preco

    if preco is None and sem_ofertas():
        comum.contar('sem_oferta_no_livro')
        return None

    return comum.ler_numero_novo(cd.PRECO_COMPRA, anterior)


def plausivel(novo, anterior):
    """(ok, motivo) do confronto com a leitura anterior do mesmo lugar.

    Sem leitura anterior nao ha o que confrontar, e isso NAO e motivo para
    recusar: e a primeira vez que se ve aquele item ali."""

    if anterior is None or novo is None:
        return True, ''

    if novo < anterior * FAIXA_MIN:
        return False, (f'{comum.fmt(novo)} e {novo / anterior * 100:.0f}% da '
                       f'leitura anterior ({comum.fmt(anterior)})')

    if novo > anterior * FAIXA_MAX:
        return False, (f'{comum.fmt(novo)} e {novo / anterior * 100:.0f}% da '
                       f'leitura anterior ({comum.fmt(anterior)})')

    return True, ''


def _combinacoes_de(item, escolhidas):
    """As combinacoes a varrer deste item.

    Aceita uma lista fixa ou uma FUNCAO. A funcao existe por causa do catalogo:
    la a quantidade e por item, entao as combinacoes que valem a pena tambem sao
    - um item com os graus 8 zerados tem dez, o vizinho tem treze. Uma lista so
    para todos varreria combinacao que voce ja disse que nao quer."""

    if escolhidas is None:
        return COMBINACOES

    if callable(escolhidas):
        return escolhidas(item)

    return escolhidas

#endregion

#region Um item

# COMO SE LE UM ITEM NAQUELA TELA.
#
# A cidade e o Mercado Negro tem o MESMO laco de leitura e telas diferentes. Ate
# aqui isso era resolvido com duas copias do laco - tres, contando a auditoria -
# e cada correcao precisava ser aplicada em todas. Nao foi: a auditoria ficou
# para tras nas tres correcoes de leitura desta semana, e a repescagem rodava o
# fluxo da cidade DENTRO do Mercado Negro.
#
# Agora o laco e um so e o que muda vira este objeto: como abrir o item, onde
# esta o preco, como trocar cada filtro, como o jogo diz que nao ha oferta.


class Cidade:
    """A lista de ofertas da tela de compra, com os filtros na barra de cima."""

    def __init__(self):
        self.regiao = cd.PRECO_COMPRA

    def abrir(self, item):
        return abrir_item(item)

    def fechar(self):
        # O item seguinte tem que comecar com os filtros zerados, senao ele nasce
        # na ultima combinacao deste. O botao tambem desfaz a categoria que o
        # menu fixou nos 18 de nome ambiguo.
        filtros.limpar()

    def base(self):
        return ler_parado()

    def ler(self, anterior):
        return ler_combinacao(anterior)

    def vazio(self):
        return sem_ofertas()

    def outro_preco(self):
        # A tela de compra da cidade tem uma coluna de preco so.
        return None

    def encantamento(self, ench):
        return filtros.encantamento(ench)

    def grau(self, item, grau, ench):
        # a lista que nao fechou e evidencia de que o grau nao e o pedido
        return filtros.grau(grau) != filtros.NAO_APLICADO


CIDADE = Cidade()


def _tela(tela):
    return tela if tela is not None else CIDADE


def ler_item(local, item, combinacoes, tela=None):
    """Le as combinacoes de um item e devolve [(rotulo, preco)].

    NAO GRAVA NADA. Quem grava e varrer_item; quem so compara e a auditoria. As
    duas precisam ler exatamente igual, e este e o unico jeito de garantir isso.

    <preco> None quer dizer que nao saiu numero - sem oferta, ou leitura que nao
    se confirmou. As duas coisas sao separadas pelos contadores."""

    tela = _tela(tela)

    lidos = []
    anterior = None
    grau_atual = None
    ench_atual = None

    try:
        for grau, ench in combinacoes:

            if comum.deve_parar():
                break

            # A PRIMEIRA COMBINACAO DO ITEM NAO TEM COM O QUE COMPARAR, e era por
            # ali que o preco do T4.2 entrava na celula do T5.2.
            #
            # Toda leitura daqui em diante se defende exigindo um numero
            # DIFERENTE do anterior. Na primeira o anterior e vazio, entao a
            # defesa nao existe: a leitura intermediaria entre a troca de
            # encantamento e a de grau saia na primeira olhada, e se saisse cedo
            # demais trazia o preco de ANTES da troca. Dai em diante tudo
            # desandava.
            # COM A REDE MANDANDO, o preco vem dela e a tela nao e lida: nem a
            # base, nem a leitura intermediaria entre dois filtros, que so
            # existem para ancorar o OCR.
            pela_rede = escuta.ativa()

            # O TESTE DA REDE. Cliente de pe e nenhum pacote recente e o normal
            # logo depois de abrir o jogo: ninguem abriu o mercado ainda. A
            # primeira combinacao espera o pacote mesmo assim; chegando, a
            # leitura inteira segue pela rede. Antes, isso virava um aviso que
            # travava a leitura toda vez - e a leitura ia pela tela mesmo com a
            # rede funcionando.
            sondando = not pela_rede and ATUAL.sondar_rede

            if sondando:
                pela_rede = True

            if anterior is None and not pela_rede:
                anterior = tela.base()

            # o instante da troca de filtro: so vale pacote da rede que chegou
            # DEPOIS dele - um anterior seria de outra combinacao ou de outra hora
            trocou_em = escuta.marca()

            rotulo = mercado.rotulo(grau, ench)

            if ench != ench_atual:

                # O ENCANTAMENTO VEM PRIMEIRO: no Mercado Negro ele define onde a
                # lista de graus comeca, entao a posicao do grau so pode ser
                # calculada depois dele estar posto.
                if tela.encantamento(ench) == filtros.NAO_APLICADO:
                    # A LISTA NAO FECHOU, ou nem abriu: na tela esta o texto do
                    # dropdown, ou o encantamento de antes. A combinacao fica sem
                    # preco - a repescagem do fim tenta de novo - e a seguinte
                    # repoe os dois filtros.
                    ench_atual = grau_atual = None
                    comum.contar('combinacoes_sem_filtro')
                    lidos.append((rotulo, None, None))
                    continue

                ench_atual = ench

                # QUANDO OS DOIS FILTROS MUDAM, a base tem de ser relida AQUI.
                # Entre uma troca e outra a tela mostra um TERCEIRO valor - o
                # grau velho com o encantamento novo - que nao e o da combinacao
                # anterior e por isso passaria pela comparacao como se fosse
                # novo. Foi o que fez 7.0 e 7.1 sairem defasados.
                #
                # ANCORADA NO ANTERIOR, como todas as outras: pedir "um numero
                # qualquer" aqui aceitaria de volta o preco que acabou de sair.
                if grau != grau_atual and not pela_rede:
                    anterior = tela.ler(anterior)

            if grau != grau_atual:

                if not tela.grau(item, grau, ench):
                    # o rotulo do grau contradisse de forma legivel: ha evidencia
                    # de que a selecao esta errada, e ler seria ler outro grau
                    grau_atual = None
                    comum.contar('combinacoes_sem_grau')
                    lidos.append((rotulo, None, None))
                    anterior = tela.base()
                    continue

                grau_atual = grau

            _situacao(local, item, rotulo)

            # PELA REDE, QUANDO ELA ESTA MANDANDO: o numero exato do servidor, sem
            # esperar a tela assentar nem rodar OCR.
            #
            # O PACOTE QUE NAO CHEGA NAO VIRA OCR AQUI. Sem a base e sem a leitura
            # intermediaria, o OCR leria sem ancora - e pegaria o valor de
            # transicao entre dois filtros. A combinacao fica sem preco, a
            # repescagem do fim tenta de novo, e varias faltas seguidas fazem a
            # escuta se dar por calada: dai em diante e OCR, com as ancoras.
            if pela_rede:
                rede = escuta.precos(
                    local, item, rotulo, desde=trocou_em,
                    prazo=escuta.ESPERA_SONDA if sondando else escuta.ESPERA,
                    mesmo_calado=sondando)

                # o teste e um so por leitura: falhou, o resto vai pela tela
                if sondando:
                    ATUAL.sondar_rede = False
                    relatar('      a rede respondeu: lendo pelos pacotes'
                            if rede is not None else escuta.AVISO_SEM_REDE)

                if rede is not None:
                    preco, outro = rede
                    anterior = preco
                    comum.contar('combinacoes_pela_rede')
                    lidos.append((rotulo, preco, outro))
                    comum.avisar(f'{item} {rotulo}', comum.fmt(preco))
                    continue

                escuta.faltou()
                comum.contar('combinacoes_sem_pacote')
                preco = None
            else:
                preco = tela.ler(anterior)

            # PERGUNTA SO QUANDO NAO VEIO NUMERO. O aviso de lista vazia e um OCR
            # de TEXTO, bem mais caro que o de numero, e faze-lo nas treze
            # combinacoes de cada item seriam 1.573 leituras por varredura para
            # responder algo que quase sempre e nao.
            if preco is None and tela.vazio():
                comum.contar('sem_oferta_no_livro')
                lidos.append((rotulo, None, None))
                continue

            # A BASE SO ANDA QUANDO HOUVE LEITURA. Zera-la a cada falha deixava a
            # combinacao SEGUINTE sem guarda nenhuma, e uma falha viraria duas.
            if preco is not None:
                anterior = preco

            # A SEGUNDA COLUNA, NA MESMA PASSADA. So quando houve leitura -
            # nao adianta ler a outra coluna de uma combinacao que nao existe.
            outro = tela.outro_preco() if preco is not None else None

            lidos.append((rotulo, preco, outro))

            # NA HORA EM QUE O NUMERO E LIDO, e nao no fim do item.
            #
            # O aviso existe para conferir a leitura AO LADO do numero que o jogo
            # esta mostrando. Depois que o item termina, a tela ja mudou treze
            # vezes e nao ha mais o que comparar - treze cartoes de uma vez sao
            # um resumo, e resumo o log ja da.
            if preco is not None:
                comum.avisar(f'{item} {rotulo}', comum.fmt(preco))

            if preco is None:
                _guardar_leitura_perdida(local, item, rotulo, tela)
                comum.contar('combinacoes_sem_oferta')

    finally:
        tela.fechar()

    return lidos


def varrer_item(local, item, combinacoes=None, relatos=None, tela=None):
    """Le todas as combinacoes de um item e grava. Devolve quantas gravou.

    Nao levanta excecao por item que nao existe no mercado: um item sem oferta
    nenhuma e informacao legitima, e nao falha. Ele simplesmente nao entra no
    banco, e a calculadora depois separa "nao tem preco" de "preco ruim"."""

    tela = _tela(tela)

    if relatos is None:
        relatos = []

    ok, motivo = tela.abrir(item)

    if not ok:
        relatos.append('      PULADO - ' + motivo)
        comum.contar('itens_sem_menu')
        return 0

    lidos = ler_item(local, item, _combinacoes_de(item, combinacoes), tela)

    gravados = 0

    for n, (rotulo, preco, outro) in enumerate(lidos):

        if preco is None:
            continue

        # A BARREIRA: confronta com o que ja havia aqui antes. Vale para os DOIS
        # mercados - o Mercado Negro e justamente onde um preco errado vira
        # compra errada, e era o unico caminho que gravava sem confronto.
        de_antes, _ = mercado.ler(local, item, rotulo)

        ok, motivo = plausivel(preco, de_antes)

        if not ok:
            comum.contar('precos_implausiveis')
            relatos.append('      ' + rotulo + ' DESCARTADO - ' + motivo)
            comum.avisar(item + ' ' + rotulo + '  descartado',
                         comum.fmt(preco), 'aviso')
            _guardar_implausivel(local, item, rotulo, preco, de_antes, motivo,
                                 tela)
            lidos[n] = (rotulo, None, None)
            continue

        # O AVISO DE CANTO JA SAIU, no instante da leitura. Aqui e a gravacao,
        # e ela acontece depois do item inteiro ter sido lido - avisar daqui
        # fazia os treze cartoes aparecerem de uma vez no fim, quando a tela do
        # jogo ja mudou treze vezes e nao ha mais o que conferir.
        mercado.gravar(local, item, rotulo, preco, outro=outro)
        gravados += 1

    # AS TREZE LEITURAS NUMA LINHA SO. O que se procura aqui nao e um numero
    # isolado - e a PROGRESSAO: dentro de um item o preco cresce com o grau e
    # com o encantamento, e uma sequencia que quebra essa ordem denuncia leitura
    # ruim sem precisar de outra fonte.
    if lidos:
        relatos.append('      ' + '  '.join(
            r + ' ' + (comum.fmt(p) if p else '-') for r, p, _ in lidos))

    return gravados


def _guardar_leitura_perdida(local, item, rotulo, tela):
    """PNG do recorte quando nao saiu numero e a tela nao disse que esta vazia.

    E o unico caso em que nao se sabe o que aconteceu. Sem a imagem, um relato de
    leitura falha vira adivinhacao sobre o enquadramento."""

    if not SALVAR_FALHAS or comum.contador('sem_oferta_no_livro'):
        return

    comum.salvar_diagnostico(
        PASTA_FALHAS,
        time.strftime('%H%M%S') + '_' + item + '_' + rotulo + '_nao_leu',
        regiao=tela.regiao,
        extras=['mercado: ' + str(local),
                'a regiao nao devolveu numero e a tela nao avisou que esta '
                'vazia',
                'confira o enquadramento do preco'])


def _guardar_implausivel(local, item, rotulo, preco, de_antes, motivo, tela):

    if not SALVAR_FALHAS:
        return

    comum.salvar_diagnostico(
        PASTA_FALHAS, time.strftime('%H%M%S') + '_' + item + '_' + rotulo,
        regiao=tela.regiao,
        extras=['mercado: ' + str(local), 'lido: ' + str(preco),
                'anterior: ' + str(de_antes), motivo])

#endregion

#region A varredura


def varrer(local, itens, combinacoes=None, salvar_a_cada=10,
           apagar_antes=False, repescar_depois=False, amostras=0, tela=None):
    """Percorre os itens no mercado atual. Devolve o resumo.

    <tela> diz COMO se le um item ali. O Mercado Negro tem outro fluxo - busca,
    clique em Vender, dropdowns dentro do painel - e passa o objeto dele aqui.
    A volta do laco e a mesma nos dois: foco, progresso, erro, gravacao.

    ELE VAI JUNTO PARA A REPESCAGEM E A AUDITORIA, e isso e a correcao de um
    defeito real: elas chamavam a leitura da cidade direto, entao toda varredura
    do Mercado Negro terminava clicando na barra de cima da cidade e lendo a
    regiao de preco errada.

    <local> e onde voce ESTA - a cidade ou o Mercado Negro. O programa nao tem
    como descobrir isso sozinho, e chutar seria pior que perguntar: um preco de
    Martlock guardado como se fosse de Thetford estraga a conta de lucro das duas
    cidades ao mesmo tempo, e nada na tela denunciaria.

    GRAVA NO DISCO DE TEMPO EM TEMPO, e nao so no fim. Uma varredura de 121 itens
    leva bastante, e um F12 no meio - ou a janela do jogo caindo - jogaria fora
    tudo que ja tinha sido lido."""

    if local not in mercado.MERCADOS:
        return {'erro': f'"{local}" nao e um mercado conhecido'}

    problemas = comum.sem_foco()

    if problemas:
        relatar('ABORTADO antes de tocar no mouse:')
        for p in problemas:
            relatar(f'  - {p}')
        return {'erro': 'jogo sem foco'}

    mercado.carregar()

    # APAGAR ANTES. Sem isto, parar no meio deixa o mercado com precos novos em
    # alguns itens e antigos nos demais, sem como distinguir - e a calculadora
    # trata os dois igual.
    if apagar_antes:
        saiu = mercado.apagar_mercado(local)
        if saiu:
            relatar(f'{saiu} precos anteriores de "{local}" foram apagados')

    # A TELA COMECA LIMPA. O jogo guarda busca, grau e encantamento de uma sessao
    # para a outra: se a ultima coisa que voce fez foi procurar um T8.3, a
    # varredura nasce dentro desse filtro. O primeiro item apareceria vazio - ou,
    # pior, mostrando outra coisa - e o bot gravaria isso sem nada na tela
    # denunciando.
    #
    # Um clique no comeco da execucao, e nao um por item: dentro do laco cada
    # item ja deixa a tela como o proximo precisa.
    limpar_a_tela(local, tela)
    ATUAL.zerar()

    # cliente de pe e calado: o primeiro item testa a rede - ver ler_item
    ATUAL.sondar_rede = escuta.ligada() and not escuta.ativa()

    inicio = time.monotonic()
    total = 0
    com_erro = []
    erros_seguidos = 0
    varridos = 0

    relatar('')
    relatar(f'Conferindo {len(itens)} itens em "{local}"')
    relatar('')

    # UM ARQUIVO POR MERCADO E POR DIA. O log da sessao mistura tudo o que foi
    # feito desde que o programa abriu; para comparar duas passadas do mesmo
    # mercado - que e como se descobre erro UNIFORME de leitura - e preciso poder
    # olhar uma de cada vez.
    registro = _abrir_registro(local)

    for n, item in enumerate(itens, start=1):

        if comum.deve_parar():
            relatar('')
            relatar(f'>>> parado no item {n} de {len(itens)} <<<')
            break

        # F11 PARA AQUI, ENTRE UM ITEM E OUTRO.
        #
        # A tecla ja ligava o sinal e escrevia no log desde sempre, e NINGUEM
        # esperava por ele: o bot seguia clicando, e o unico efeito de apertar
        # F11 era uma linha dizendo que ia pausar.
        #
        # Entre itens, e nao no meio de um: pausar com o painel de venda aberto e
        # um filtro pela metade deixaria a tela num estado que a retomada teria
        # de adivinhar.
        if comum.pausado.is_set():

            _, pode_seguir = comum.aguardar_retomada(
                (f'parado antes do item {n} de {len(itens)}',
                 f'{total} precos ja gravados'))

            if not pode_seguir:
                relatar('')
                relatar('>>> encerrado durante a pausa <<<')
                break

        # PULAR O ITEM ATUAL, a pedido. Existe para o item que trava a
        # varredura sem falhar - o painel que nao abre, a lista que nao filtra.
        # Sem isto a unica saida era parar tudo.
        if comum.pular_pedido.is_set():
            comum.pular_pedido.clear()
            relatar('      PULADO a pedido')
            continue

        # O FOCO E CONFERIDO A CADA ITEM. Se o jogo cair para tras no item 30, os
        # seguintes clicariam e leriam dentro de outra janela - e o banco de
        # precos encheria de numeros lidos de qualquer coisa.
        if not comum.jogo_em_foco():
            relatar('')
            relatar(f'PARANDO no item {n} - o jogo saiu de primeiro plano.')
            break

        decorrido = time.monotonic() - inicio
        eta = (f'~{(decorrido / (n - 1)) * (len(itens) - n + 1) / 60:.0f} min restantes'
               if n > 1 else 'calculando...')

        relatar(f'[{n}/{len(itens)}] {item}  {eta}')
        comum.progresso(n, len(itens), f'{local} - {item}')

        relatos = []

        try:
            gravados = varrer_item(local, item, combinacoes, relatos, tela)

        except comum.Abortado:
            relatar('')
            relatar(f'>>> F12 - parado no meio de "{item}" <<<')
            break

        except Exception:
            com_erro.append(item)
            erros_seguidos += 1
            relatar('      ERRO neste item - seguindo para o proximo:')
            for l in traceback.format_exc().strip().splitlines()[-3:]:
                relatar(f'        {l}')

            if erros_seguidos >= MAX_ITENS_COM_ERRO_SEGUIDOS:
                relatar('')
                relatar(f'PARANDO: {MAX_ITENS_COM_ERRO_SEGUIDOS} itens seguidos '
                        f'falharam. Confira a tela do jogo e as coordenadas.')
                break

            continue

        erros_seguidos = 0
        total += gravados
        varridos += 1

        for r in relatos:
            relatar(r)
            _anotar(registro, r)

        _anotar(registro, f'[{n}/{len(itens)}] {item}')

        if salvar_a_cada and varridos % salvar_a_cada == 0:
            mercado.salvar()

        # A LIMPEZA ENTRE ITENS AGORA E DA TELA, nao do laco: cada mercado
        # sabe o que precisa desfazer. Na cidade e o botao de resetar - filtros
        # e categoria; no Mercado Negro e fechar o painel, e mais nada.

    if repescar_depois and not comum.deve_parar():
        try:
            repescar(local, itens, combinacoes, tela=tela)
        except comum.Abortado:
            pass

    if amostras and not comum.deve_parar():
        try:
            auditar(local, itens, amostras, combinacoes, tela=tela)
        except comum.Abortado:
            pass

    _fechar_registro(registro)

    gravou, erro_ao_salvar = mercado.salvar()

    minutos = (time.monotonic() - inicio) / 60

    resumo = {
        'local': local,
        'itens': varridos,
        'precos': total,
        'minutos': minutos,
        'com_erro': com_erro,
        'salvou': gravou,
    }

    _resumo(resumo, erro_ao_salvar)

    return resumo


def _resumo(r, erro_ao_salvar):
    """O relatorio de uma varredura."""

    relatar('')
    relatar(f'"{r["local"]}" - {r["minutos"]:.1f} min')
    relatar(f'  {r["itens"]} itens varridos, {r["precos"]} precos gravados')

    if not r['salvou']:
        relatar(f'  ATENCAO: nao foi possivel gravar o banco - {erro_ao_salvar}')

    idade = mercado.idade_mais_velha(r['local'])

    if idade is not None:
        relatar(f'  o preco mais velho deste mercado tem {idade:.1f} h')

    relatar(f'  o banco tem {mercado.quantidade()} precos, '
            f'de {len(mercado.mercados_lidos())} mercados')

    for chave, texto in (
        ('abertos_pelo_menu',
         'itens abertos pelo menu por terem nome ambiguo (o resto foi por busca)'),
        ('grau_corrigido',
         'vezes em que o dropdown de grau comecou em outro lugar e foi corrigido'),
        ('grau_ilegivel',
         'graus gravados sem conferir o rotulo - se for muito, o recorte esta '
         'errado'),
        ('grau_contradiz',
         'combinacoes PULADAS porque o dropdown insistia em outro grau'),
        ('sem_oferta_no_livro',
         'combinacoes em que o jogo avisou que ninguem esta vendendo aquilo'),
        ('tela_nao_trocou',
         'combinacoes DESCARTADAS porque a lista nao trocou a tempo - o preco '
         'que estava ali era o da combinacao anterior; a repescagem tenta de '
         'novo'),
        ('borda_suja',
         'leituras com algo colado na borda esquerda do recorte - quase sempre '
         'o icone da moeda dentro da regiao do preco'),
        ('leituras_pouco_confiaveis',
         'numeros que o proprio OCR marcou como duvidosos e foram conferidos '
         'de novo - se for muito, o recorte do preco esta apertado'),
        ('opcao_sem_efeito',
         'cliques em opcao de filtro que nao fecharam a lista - se for muito, '
         'as coordenadas do dropdown sairam do lugar'),
        ('combinacoes_sem_filtro',
         'combinacoes SEM PRECO porque o filtro nao foi aplicado nem insistindo '
         '- se for muito, calibre o dropdown em Ajustes > Leitura > Calibrar'),
        ('itens_sem_painel',
         'itens cujo painel de venda nao abriu'),
        ('itens_sem_menu',
         'itens PULADOS porque o menu nao chegou neles - o jogo mudou a lista?'),
        ('item_diferente_na_lista',
         'itens em que o nome da primeira linha nao bateu com o procurado - se '
         'for perto do total, a busca nao esta filtrando'),
        ('busca_sem_efeito',
         'buscas em que a lista nao reagiu ao nome digitado'),
        ('abertos_pela_busca',
         'itens achados digitando o nome, que e o caminho normal'),
        ('abertos_pelo_menu',
         'itens achados descendo o menu - so os de nome que cabe dentro de '
         'outro precisam disso'),
        ('combinacoes_sem_oferta',
         'combinacoes sem oferta nenhuma (normal nos graus altos)'),
        ('precos_implausiveis',
         'leituras DESCARTADAS por estarem longe demais da anterior - ha um PNG '
         'de cada uma em ' + PASTA_FALHAS + '/'),
        ('menu_fora_do_lugar',
         'vezes em que uma entrada do menu mostrava outra coisa'),
        ('menu_ilegivel_seguiu',
         'entradas de menu que nao deram para ler - se for muito, o recorte e '
         'que esta errado'),
        ('filtros_sem_efeito',
         'trocas de filtro que nao apareceram na tela a tempo'),
        ('dropdown_perdidos',
         'dropdowns que nao abriram no tempo limite'),
        ('leituras_refeitas',
         'leituras vieram vazias ou repetidas e foram refeitas'),
        ('reservas_usadas',
         'leituras recuperadas pela escada de reserva do OCR'),
    ):
        if comum.contador(chave):
            relatar(f'  {comum.contador(chave)} {texto}')

    if r['com_erro']:
        relatar(f'  {len(r["com_erro"])} itens deram erro: '
                f'{", ".join(r["com_erro"])}')

    tempos = comum.tempos()

    if tempos and r['minutos'] > 0:
        total_s = r['minutos'] * 60
        relatar('')
        for chave, seg in sorted(tempos.items(), key=lambda kv: -kv[1]):
            relatar(f'    {chave:22} {seg:6.1f}s  ({seg / total_s * 100:4.1f}%)')

    relatar('')


def repescar(local, itens, combinacoes=None, relatar_cada=True, tela=None):
    """Rele as combinacoes que voltaram sem preco. Devolve quantas recuperou.

    VALE A PENA NA HORA, e nao depois: os itens ainda estao a sua frente, o
    mercado esta aberto e o jogo ja esta aquecido. O que faltou costuma ser
    lentidao da tela, e nao ausencia de oferta - e uma segunda passada custa
    segundos onde voltar ate la custaria a viagem inteira."""

    faltando = []

    for item in itens:
        for grau, ench in _combinacoes_de(item, combinacoes):
            rotulo = mercado.rotulo(grau, ench)
            if mercado.ler(local, item, rotulo)[0] is None:
                faltando.append((item, grau, ench))

    if not faltando:
        return 0

    relatar('')
    relatar(f'Repescando {len(faltando)} combinacoes que voltaram vazias')

    recuperadas = 0
    por_item = {}

    for item, grau, ench in faltando:
        por_item.setdefault(item, []).append((grau, ench))

    for n, (item, combos) in enumerate(sorted(por_item.items()), start=1):

        if comum.deve_parar():
            break

        comum.progresso(n, len(por_item), f'repescando {item}')

        antes = mercado.quantidade(local)

        try:
            varrer_item(local, item, combinacoes=combos, tela=tela)
        except comum.Abortado:
            raise
        except Exception:
            continue

        ganhou = mercado.quantidade(local) - antes
        recuperadas += ganhou

        if ganhou and relatar_cada:
            relatar(f'      {item}: recuperou {ganhou}')

    relatar(f'  {recuperadas} de {len(faltando)} recuperadas')

    return recuperadas


def auditar(local, itens, quantas=8, combinacoes=None, tela=None):
    """Rele combinacoes SORTEADAS e compara com o que ficou gravado.

    POR QUE ISTO EXISTE. As outras conferencias pegam leitura fora de ordem, mas
    nao pegam erro UNIFORME: se a varredura inteira leu um digito a menos, os
    precos continuam crescendo direitinho de grau em grau e nada acusa. A unica
    forma de saber e ler de novo e comparar - e conferir 1.573 celulas a mao
    ninguem faz.

    O SORTEIO E AGRUPADO POR ITEM: reler 8 combinacoes de 3 itens custa 3
    navegacoes de menu, e nao 8."""

    if quantas <= 0:
        return {'conferidas': 0, 'divergentes': 0}

    candidatas = [
        (item, grau, ench)
        for item in itens
        for grau, ench in _combinacoes_de(item, combinacoes)
        if mercado.ler(local, item, mercado.rotulo(grau, ench))[0] is not None
    ]

    if not candidatas:
        return {'conferidas': 0, 'divergentes': 0, 'erro': 'nada gravado'}

    sorteadas = random.sample(candidatas, min(quantas, len(candidatas)))

    por_item = {}

    for item, grau, ench in sorteadas:
        por_item.setdefault(item, []).append((grau, ench))

    relatar('')
    relatar(f'Conferindo {len(sorteadas)} combinacoes sorteadas, '
            f'em {len(por_item)} itens')

    conferidas = 0
    divergentes = []

    for n, (item, combos) in enumerate(sorted(por_item.items()), start=1):

        if comum.deve_parar():
            break

        comum.progresso(n, len(por_item), f'conferindo {item}')

        gravados = {mercado.rotulo(g, e):
                    mercado.ler(local, item, mercado.rotulo(g, e))[0]
                    for g, e in combos}

        # PELA MESMA PORTA E COM O MESMO LACO DA VARREDURA.
        #
        # Antes daqui saia uma terceira copia do laco de leitura, com o menu
        # cravado e as coordenadas da cidade. Ela nao recebeu nenhuma das tres
        # correcoes de leitura desta semana, e no Mercado Negro lia a regiao
        # errada - o que produzia divergencia falsa justamente na conferencia
        # que existe para achar divergencia.
        ok, _ = _tela(tela).abrir(item)

        if not ok:
            continue

        for rotulo, lido, _ in ler_item(local, item, sorted(combos), tela):

            gravado = gravados.get(rotulo)

            conferidas += 1

            if lido != gravado:
                divergentes.append((item, rotulo, gravado, lido))

    relatar(f'  {conferidas} conferidas, {len(divergentes)} divergentes')

    for item, rotulo, gravado, lido in divergentes:
        relatar(f'      {item} {rotulo}: gravado {comum.fmt(gravado)}, '
                f'relido {comum.fmt(lido) if lido else "nada"}')

    if divergentes:
        relatar('')
        relatar('  DIVERGENCIA NAO E NECESSARIAMENTE ERRO: entre a varredura e')
        relatar('  agora, alguem pode ter comprado ou posto uma oferta. Mas se')
        relatar('  varias divergirem PARA O MESMO LADO, e leitura.')

    return {'conferidas': conferidas, 'divergentes': len(divergentes),
            'lista': divergentes}


def falta_conferir(itens, local, idade_maxima=None):
    """Os itens que ainda nao tem preco recente naquele mercado.

    Serve para retomar uma varredura interrompida sem repetir o que ja foi lido -
    e para a tela poder dizer "faltam 40" em vez de "rode tudo de novo"."""

    if idade_maxima is None:
        idade_maxima = 6.0

    faltando = []

    for item in itens:

        recentes = 0

        for grau, ench in COMBINACOES:
            preco, idade = mercado.ler(local, item, mercado.rotulo(grau, ench))
            if preco is not None and idade is not None and idade <= idade_maxima:
                recentes += 1

        if not recentes:
            faltando.append(item)

    return faltando

#endregion
