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

import time

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


def ler_livro(linhas=LINHAS_DO_LIVRO):
    """Le "Pedidos de venda". Devolve [(preco, quantidade)], de baixo para cima.

    Para na primeira linha que nao der para ler: a lista e continua e ordenada,
    entao uma linha vazia quer dizer que o livro acabou. Insistir depois disso
    seria ler o fundo do painel.

    Quantidade ilegivel com preco legivel vira 1, e nao zero. Um vira uma compra
    a menos que a possivel; zero faria a linha inteira desaparecer da conta e a
    ordem nasceria pequena demais - e o erro que some e sempre pior."""

    ofertas = []

    for n in range(linhas):

        comum.checar_aborto()

        preco = comum.ler_numero(cd.venda_preco(n))

        if preco is None:
            break

        quantidade = comum.ler_numero(cd.venda_quantidade(n))

        if quantidade is None or quantidade < 1:
            comum.contar('quantidade_ilegivel')
            quantidade = 1

        ofertas.append((preco, int(quantidade)))

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

    Clica no NOME, e nao no botao Comprar: o botao compra uma unidade na hora, o
    nome abre o painel com o livro de ofertas e as quatro acoes."""

    antes = comum.assinatura(cd.venda_preco(0))

    comum.clicar(cd.PAINEL_ABRIR)

    if comum.esperar_mudanca(cd.venda_preco(0), antes, ESPERA_CAMPO):
        comum.esperar_estavel(cd.venda_preco(0), ESPERA_CAMPO,
                              intervalo=comum.SONDAGEM_LENTA)
        return True

    return comum.ler_numero(cd.venda_preco(0)) is not None


def fechar_painel():
    """Sai do painel pelo X."""

    comum.clicar(cd.PAINEL_FECHAR)


def criar_ordem(plano, tolerancia=0.01):
    """Cria o pedido de compra do <plano>. Devolve (ok, motivo).

    A ULTIMA BARREIRA E O "TOTAL" DA TELA. Antes de clicar em criar, o jogo ja
    escreveu quanto vai reservar - e esse numero e o unico que nao passou pelo
    nosso OCR duas vezes nem pela nossa aritmetica. Se ele nao bater com o
    previsto, alguma coisa entre o plano e a tela se perdeu: o campo pegou o
    numero errado, o item nao e o que se pensa, o preco tem outra casa.

    E a mesma licao que custou caro no bot antigo, onde o dialogo de confirmacao
    dizia um valor e a lista dizia outro. So que la a divergencia custava uma
    unidade; aqui custaria a ordem inteira."""

    comum.secao_critica.set()

    try:
        comum.clicar(cd.PAINEL_PEDIDO_DE_COMPRA)

        if not preencher(cd.PAINEL_QTD_BARRA, cd.PAINEL_QTD_VALOR,
                         plano['unidades']):
            return False, 'a quantidade nao entrou no campo'

        if not preencher(cd.PAINEL_PRECO_CAMPO, cd.PAINEL_PRECO_VALOR,
                         plano['preco']):
            return False, 'o preco nao entrou no campo'

        comum.esperar_estavel(cd.PAINEL_TOTAL, ESPERA_CAMPO,
                              intervalo=comum.SONDAGEM_LENTA)

        total = comum.ler_numero(cd.PAINEL_TOTAL)

        if total is None:
            comum.contar('total_ilegivel')
        else:
            previsto = plano['custo_maximo']

            if abs(total - previsto) > max(1, previsto * tolerancia):
                comum.contar('total_divergente')
                return False, (f'a tela reserva {comum.fmt(total)} e o plano '
                               f'previa {comum.fmt(previsto)}')

        comum.clicar(cd.PAINEL_CRIAR)

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


def _guardar_falha(nome, extras):

    if not SALVAR_FALHAS:
        return

    comum.salvar_diagnostico(PASTA_FALHAS,
                             time.strftime('%H%M%S') + '_' + nome,
                             regiao=cd.CMP_DIALOGO_COMPRA, extras=extras)

#endregion
