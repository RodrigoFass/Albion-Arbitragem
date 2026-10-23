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

from motor import comum
from motor import coordenadas as cd

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

# Quantas vezes tentar a opcao quando a lista nao fecha depois do clique.
TENTATIVAS_DE_OPCAO = 3

# O que trocar() devolve quando o filtro NAO FOI APLICADO: a lista nao abriu, ou
# nao fechou nem depois de insistir. E diferente de False, que quer dizer
# "aplicou, mas o preco nao mudou" - e isso pode ser verdade.
NAO_APLICADO = 'nao aplicado'

#endregion

#region Dropdowns


def _regiao_opcoes(barra):
    """Faixa onde a primeira opcao aparece quando o dropdown da CIDADE abre."""

    return (barra['x'] - cd.CMP_DETECCAO_MEIA_LARGURA,
            cd.CMP_DETECCAO_OPCAO_Y - cd.CMP_DETECCAO_MEIA_ALTURA,
            barra['x'] + cd.CMP_DETECCAO_MEIA_LARGURA,
            cd.CMP_DETECCAO_OPCAO_Y + cd.CMP_DETECCAO_MEIA_ALTURA)


def _ate_a_opcao(regiao, opcao):
    """A faixa da lista aberta, da primeira opcao ate a que vai ser clicada."""

    x1, y1, x2, y2 = regiao

    return (min(x1, opcao['x'] - 40), y1, max(x2, opcao['x'] + 40),
            max(y2, opcao['y'] + 13))


def escolher(barra, opcao, deteccao=None, afastar=True):
    """Abre um dropdown e clica numa opcao. True se a escolha foi feita.

    Sem esperar a lista abrir, o clique da opcao chega antes dela existir na
    tela, e o filtro fica no valor anterior - lendo o preco de outra combinacao.

    NA CIDADE, A LISTA TEM DE FECHAR DE VERDADE ANTES DE ALGUEM LER O PRECO. O
    jogo ganhou a opcao "Enchantment 4", e com a lista de encantamento aberta
    ela fica exatamente em cima do preco da primeira oferta: todos os PNGs de
    borda em falhas_conferidor eram o mesmo "...chantment 4" no lugar do
    numero. A versao anterior dava a lista por fechada no primeiro quadro
    diferente depois do clique - e o primeiro quadro da animacao de fechar ja e
    diferente. Agora a faixa da primeira opcao tem de voltar a PARECER com o que
    era antes de abrir. Se nao voltar, um clique no vazio fecha a lista e a
    escolha e tentada de novo; esgotadas as tentativas, devolve False e quem
    chamou nao le preco nenhum.

    E A OPCAO SO E CLICADA COM A LISTA ABERTA. Ela fica em cima da primeira
    linha de ofertas, e um clique ali com a lista fechada cai na oferta.

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
        fechado = comum.assinatura(regiao)

        for _ in range(TENTATIVAS_DE_OPCAO):

            comum.clicar(barra, espera=0)

            abriu = comum.esperar_mudanca(regiao, fechado, ESPERA_DROPDOWN)

            if abriu:
                # A LISTA INTEIRA PARADA, ATE A OPCAO, NO RITMO LENTO. Tres
                # quadros iguais no ritmo rapido sao ~50 ms, menos que a
                # animacao da lista abrindo: so a primeira opcao parecia parada,
                # a lista ainda descia, e o clique no T5 caia no T4.
                comum.esperar_estavel(_ate_a_opcao(regiao, opcao), ESPERA_DROPDOWN,
                                      intervalo=comum.SONDAGEM_LENTA)
            else:
                comum.contar('dropdown_perdidos')

            # SO A CIDADE PRECISA AFASTAR O CURSOR. La a opcao do encantamento 3
            # fica logo acima da primeira linha da lista, e o ponteiro - que o
            # jogo desenha e a captura pega junto - para em cima dos primeiros
            # digitos do preco.
            #
            # No painel do Mercado Negro os dropdowns ficam em x=520 e x=665 e o
            # preco em x=1016; o cursor nao chega perto. Ali segue o fluxo do
            # bot_atualizar, que rodou meses naquela tela: clica e volta.
            if not afastar:
                comum.clicar(opcao, espera=0)
                return True

            if not abriu:
                continue

            aberto = comum.assinatura(regiao)

            comum.clicar(opcao, espera=0)

            # ESPERA O CLIQUE SER CONSUMIDO ANTES DE TIRAR O CURSOR DALI.
            #
            # O jogo nao usa a posicao do ponteiro no instante do clique: ele le
            # a posicao ATUAL no quadro seguinte, e resolve o clique ali. Movendo
            # o cursor logo depois de soltar o botao, a opcao nunca era
            # selecionada - o clique caia onde o cursor tinha acabado de chegar.
            #
            # So depois de o cursor sair e que da para conferir que a lista
            # fechou: a opcao "Todos" fica dentro da faixa de deteccao, e o
            # ponteiro em cima dela nunca deixaria a faixa voltar ao que era.
            if comum.esperar_mudanca(regiao, aberto, ESPERA_DROPDOWN):
                comum.apontar(cd.MOUSE_DESCANSO)

                if comum.esperar_parecido(regiao, fechado, ESPERA_DROPDOWN):
                    return True

            comum.contar('opcao_sem_efeito')

            # A LISTA FICOU ABERTA. Um clique no vazio fecha sem escolher nada -
            # o ponto de descanso e madeira desenhada, sem controle nenhum.
            comum.clicar(cd.MOUSE_DESCANSO, espera=0)
            comum.esperar_parecido(regiao, fechado, ESPERA_DROPDOWN)

        comum.contar('filtro_nao_aplicado')

        return False


def trocar(acao, regiao=None):
    """Executa uma troca de filtro e volta quando a tela tiver assentado.

    A base e confirmada estavel ANTES da troca. Sem isso, uma base capturada no
    meio de um redesenho faz a "mudanca" detectada ser a tela voltando ao valor
    antigo, e a leitura sai um passo atrasada.

    False quer dizer que a troca nao apareceu na tela no tempo limite. Nao e
    necessariamente erro - duas combinacoes vizinhas podem ter o mesmo preco, e
    ai nada muda mesmo - mas quem le em seguida precisa saber.

    NAO_APLICADO quer dizer que a escolha no dropdown falhou: o filtro continua
    o de antes, e ler o preco agora seria ler outra combinacao. Volta na hora,
    sem gastar a espera do preco com uma troca que nao aconteceu."""

    if regiao is None:
        regiao = cd.PRECO_COMPRA

    with comum.cronometro('espera do preco'):

        comum.esperar_estavel(regiao, ESPERA_PRECO, comum.LEITURAS_IGUAIS_PRECO)
        antes = comum.assinatura(regiao)

        if acao() is False:
            return NAO_APLICADO

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


def qualidade(valor):
    """Troca o filtro de qualidade. 0 e "Todas". True se a tela reagiu.

    So a compra por qualidade usa, e so com as duas posicoes calibradas - ver
    coordenadas.calibrado()."""

    return trocar(lambda: escolher(cd.CMP_BARRA_QUAL, cd.qualidade_compra(valor)))


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
