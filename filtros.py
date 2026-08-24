################################
#                              #
#            FILTROS           #
#                              #
################################

# Os dropdowns de grau e encantamento da barra de cima do mercado.
#
# Sao a MESMA barra no Mercado Negro e no mercado das cidades - conferido nas
# capturas das duas telas, e por isso as coordenadas daqui vieram prontas do
# programa que ja funciona.
#
# O que muda entre a versao antiga e esta e quem seleciona o item: la era a caixa
# de busca, aqui e o menu de categoria. Os filtros continuam sendo o que separa
# as 13 combinacoes de grau e encantamento dentro de um item so.
#
#
# TROCAR UM FILTRO E ESPERAR SAO A MESMA OPERACAO. Um clique que volta antes da
# lista redesenhar entrega a combinacao anterior para quem for ler em seguida, e
# a leitura sai um passo atrasada - o erro que contaminava sequencias inteiras no
# programa antigo. Por isso nao existe aqui uma funcao que so clica.
#
# Antes de alterar: python -m pyflakes filtros.py

import comum
import coordenadas as cd

#region Configuracao

# Limite esperando o dropdown abrir.
ESPERA_DROPDOWN = 1.50

# Limite esperando a lista de ofertas se redesenhar depois da troca.
#
# E LIMITE, NAO PAUSA: a espera acaba no instante em que o preco muda, e so vira
# tempo de verdade quando a troca demora. Aumentar nao deixa a varredura mais
# lenta no caso comum - so da mais chance ao caso ruim.
#
# 1,20 s veio do bot_atualizar, que trabalha no painel de Pedido de Venda. A
# LISTA DA CIDADE E MAIS PESADA que aquele painel: ela refiltra e redesenha
# linhas com icone e nome. Com 1,20 s a troca de grau nao chegava a tempo, a
# leitura pegava a combinacao anterior, e o preco do T4.2 era gravado como T5.2.
ESPERA_PRECO = 2.50

#endregion

#region Dropdowns


def _regiao_opcoes(barra):
    """Faixa onde a primeira opcao aparece quando o dropdown da CIDADE abre."""

    return (barra['x'] - cd.CMP_DETECCAO_MEIA_LARGURA,
            cd.CMP_DETECCAO_OPCAO_Y - cd.CMP_DETECCAO_MEIA_ALTURA,
            barra['x'] + cd.CMP_DETECCAO_MEIA_LARGURA,
            cd.CMP_DETECCAO_OPCAO_Y + cd.CMP_DETECCAO_MEIA_ALTURA)


def escolher(barra, opcao, deteccao=None, afastar=True):
    """Abre um dropdown e clica numa opcao, esperando a animacao de abertura.

    Sem essa espera o clique da opcao chega antes da lista existir na tela, e o
    filtro fica no valor anterior - lendo o preco de outra combinacao.

    <deteccao> E OBRIGATORIO FORA DA CIDADE. O padrao olha a linha y=300, onde
    a primeira opcao aparece na barra de cima da cidade. No painel do Mercado
    Negro ela aparece em y=423, e olhando para o lugar errado a espera NUNCA ve
    a lista abrir: gasta o limite inteiro em toda troca de filtro e depois
    clica as cegas, com a lista talvez ainda fechada - o clique cai no painel
    atras e o grau fica no valor anterior.

    Era isto que deixava o Mercado Negro lento E errando graus ao mesmo tempo.
    Um sintoma so, duas aparencias."""

    with comum.cronometro('dropdowns'):

        regiao = deteccao or _regiao_opcoes(barra)
        antes = comum.assinatura(regiao)

        comum.clicar(barra, espera=0)

        if comum.esperar_mudanca(regiao, antes, ESPERA_DROPDOWN):
            comum.esperar_estavel(regiao, ESPERA_DROPDOWN)
        else:
            comum.contar('dropdown_perdidos')

        aberto = comum.assinatura(regiao)

        comum.clicar(opcao, espera=0)

        # SO A CIDADE PRECISA AFASTAR O CURSOR. La a opcao do encantamento 3 fica
        # logo acima da primeira linha da lista, e o ponteiro - que o jogo desenha
        # e a captura pega junto - para em cima dos primeiros digitos do preco.
        #
        # No painel do Mercado Negro os dropdowns ficam em x=520 e x=665 e o preco
        # em x=1016; o cursor nao chega perto. Mover ali seria um movimento de
        # mouse e uma espera por combinacao sem nada em troca - e o bot_atualizar,
        # que rodou meses naquela tela, nunca moveu.
        if not afastar:
            return

        # ESPERA O CLIQUE SER CONSUMIDO ANTES DE TIRAR O CURSOR DALI.
        #
        # O jogo nao usa a posicao do ponteiro no instante do clique: ele le a
        # posicao ATUAL no quadro seguinte, e resolve o clique ali. Movendo o
        # cursor logo depois de soltar o botao, a opcao nunca era selecionada -
        # o clique caia onde o cursor tinha acabado de chegar, e o dropdown
        # ficava aberto com o filtro no valor de antes.
        #
        # A lista fechando E a confirmacao de que o clique chegou. Esperar por
        # ela nao custa nada quando funciona, e quando nao funciona vira um
        # contador em vez de um bot parado em frente a um menu aberto.
        if comum.esperar_mudanca(regiao, aberto, ESPERA_DROPDOWN):
            comum.apontar(cd.MOUSE_DESCANSO)
        else:
            comum.contar('opcao_sem_efeito')


def trocar(acao, regiao=None):
    """Executa uma troca de filtro e volta quando a tela tiver assentado.

    A base e confirmada estavel ANTES da troca. Sem isso, uma base capturada no
    meio de um redesenho faz a "mudanca" detectada ser a tela voltando ao valor
    antigo, e a leitura sai um passo atrasada.

    False quer dizer que a troca nao apareceu na tela no tempo limite. Nao e
    necessariamente erro - duas combinacoes vizinhas podem ter o mesmo preco, e
    ai nada muda mesmo - mas quem le em seguida precisa saber."""

    if regiao is None:
        regiao = cd.PRECO_COMPRA

    with comum.cronometro('espera do preco'):

        comum.esperar_estavel(regiao, ESPERA_PRECO, comum.LEITURAS_IGUAIS_PRECO)
        antes = comum.assinatura(regiao)

        acao()

        if comum.esperar_mudanca(regiao, antes, ESPERA_PRECO):
            # NO RITMO RAPIDO, como o bot_atualizar faz. A sondagem lenta -
            # 50 ms entre leituras, 8 leituras - poe 400 ms fixos em CADA troca
            # de filtro, e sao 26 por item. Ela existe para o bot de compra,
            # onde ler cedo demais custa dinheiro; aqui a mudanca ja foi
            # confirmada logo acima, e o que sobra e so confirmar que parou.
            comum.esperar_estavel(regiao, ESPERA_PRECO,
                                  comum.LEITURAS_IGUAIS_PRECO)
            return True

        comum.contar('filtros_sem_efeito')

        return False


def grau(valor):
    """Troca o filtro de grau. True se a tela reagiu."""

    return trocar(lambda: escolher(cd.CMP_BARRA_TIER, cd.tier_compra(valor)))


def encantamento(valor):
    """Troca o filtro de encantamento. True se a tela reagiu."""

    return trocar(lambda: escolher(cd.CMP_BARRA_ENCH, cd.ench_compra(valor)))


def limpar():
    """Devolve grau e encantamento a "Todos".

    O JOGO GUARDA O FILTRO ENTRE UM ITEM E OUTRO. Cada item termina na ultima
    combinacao da lista; sem zerar, o proximo nasce filtrado ali e a lista
    aparece vazia ou mostrando so aquela faixa - e as leituras seguintes saem de
    uma combinacao que nao e a que o programa pensa estar vendo."""

    antes = comum.assinatura(cd.CMP_LINHA_ITEM)

    comum.clicar(cd.CMP_LIMPAR_FILTROS, espera=0)

    if comum.esperar_mudanca(cd.CMP_LINHA_ITEM, antes, ESPERA_PRECO):
        comum.esperar_estavel(cd.CMP_LINHA_ITEM, ESPERA_PRECO)
    else:
        # ja estava sem filtro: nada muda na tela, e isso e normal
        comum.contar('filtros_ja_limpos')

#endregion
