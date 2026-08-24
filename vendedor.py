################################
#                              #
#           VENDEDOR           #
#                              #
################################

# Vender no Mercado Negro o que foi comprado na cidade.
#
#
# DUAS SAIDAS, E A ESCOLHA E ENTRE TEMPO E PRATA:
#
#     NA HORA        casa com um pedido de compra que ja existe. A prata entra
#                    no mesmo instante, pelo preco de quem esta comprando.
#
#     PEDIDO DE VENDA  entra na fila por um preco seu, uma prata abaixo do
#                    vendedor mais barato. Rende mais e paga 2,5% de taxa a
#                    mais - e pode nao vender nunca.
#
# A regra e a que voce descreveu: se o pedido de compra ja esta PERTO do alvo,
# vende na hora e acabou; se nao esta, entra na fila.
#
#
# "PERTO" E UMA TOLERANCIA, E NAO UM SINAL DE IGUAL.
#
# Exigir o alvo exato faria o bot recusar 99% do alvo e ficar com a carga na mao
# esperando uma ordem que talvez nunca case - trocando prata garantida por prata
# possivel, que e o contrario do que se quer com carga parada. A tolerancia diz
# quanto de margem se aceita perder para receber agora.
#
#
# O ALVO SAI DO QUE FOI PAGO, e nao de uma tabela.
#
# A prata ja saiu. O que se decide aqui e aceitar ou nao o que o mercado esta
# oferecendo, e a unica referencia honesta e o custo real daquela unidade - com
# a taxa de ordem da compra ja embutida, porque ela tambem ja foi paga.
#
# Antes de alterar: python -m pyflakes vendedor.py

import time

import ajustes
import comum
import coordenadas as cd
import historico
import lucro
import mercado
import mercado_negro
from comum import relatar

#region Configuracao

# Quanto do alvo basta para vender na hora, em vez de entrar na fila.
#
# 0,95 quer dizer: recebendo 95% do que eu queria, pego agora. Os 5% sao o preco
# de nao ficar com a carga esperando - e uma carga parada nao rende nada.
PERTO_DO_ALVO = 0.95

# Quanto abaixo do vendedor mais barato entrar na fila.
#
# UMA PRATA. Nao e simbolico: a lista do jogo ordena por preco, e uma unidade
# abaixo poe a sua oferta na frente de todas as outras daquele preco. Baixar
# mais que isso e dar desconto para ninguem.
ABAIXO_DO_MENOR = 1

# Limites, em segundos.
ESPERA_PAINEL = 2.50
ESPERA_CAMPO = 1.50
ESPERA_VENDA = 2.50

# Palavras que provam que o dialogo de confirmacao da venda esta na tela.
PALAVRAS_DO_DIALOGO = ('vender', 'prata', 'unidades', 'sell', 'silver', 'units')

VERIFICAR_DIALOGO = True

SALVAR_FALHAS = True
PASTA_FALHAS = 'falhas_venda'

#endregion

#region A decisao


def alvo(pago, margem=None, taxa=None, por_ordem=False):
    """Por quanto e preciso vender esta unidade. Ver lucro.venda_minima."""

    conf = ajustes.atuais()

    return lucro.venda_minima(
        pago,
        conf['margem'] if margem is None else margem,
        conf['taxa'] if taxa is None else taxa,
        ordem_na_compra=True,
        ordem_na_venda=por_ordem)


def decidir(pago, pedido_de_compra, menor_venda, margem=None, taxa=None,
            perto=PERTO_DO_ALVO):
    """Como vender esta unidade. Devolve (modo, preco, motivo).

    <modo> e 'na hora', 'ordem' ou None quando nao vale vender de jeito nenhum.

    A ORDEM DAS PERGUNTAS IMPORTA. Primeiro se pergunta se da para receber AGORA
    por um valor aceitavel - porque receber agora e melhor que receber talvez.
    So quando nao da e que se calcula a fila."""

    alvo_agora = alvo(pago, margem, taxa, por_ordem=False)

    if pedido_de_compra and pedido_de_compra >= alvo_agora * perto:
        return 'na hora', pedido_de_compra, (
            f'{comum.fmt(pedido_de_compra)} e '
            f'{pedido_de_compra / alvo_agora * 100:.0f}% do alvo de '
            f'{comum.fmt(alvo_agora)}')

    if not menor_venda:
        return None, None, 'ninguem vendendo e nenhum pedido de compra serve'

    preco = menor_venda - ABAIXO_DO_MENOR
    alvo_fila = alvo(pago, margem, taxa, por_ordem=True)

    # ENTRAR NA FILA ABAIXO DO CUSTO E TROCAR PRATA POR PRATA MENOR. Nao ha
    # pressa que justifique isso: a carga nao estraga, e o mercado muda.
    if preco < alvo_fila:
        return None, preco, (
            f'a fila comeca em {comum.fmt(menor_venda)} e o alvo por ordem e '
            f'{comum.fmt(alvo_fila)} - nao paga')

    return 'ordem', preco, (f'uma prata abaixo de {comum.fmt(menor_venda)}')

#endregion

#region A tela


def abrir(item, nome_de_busca=None):
    """Deixa o painel do item aberto no Mercado Negro. (ok, motivo)."""

    return mercado_negro.abrir(item, nome_de_busca)


def fechar():
    mercado_negro.fechar_painel()


def ler_precos():
    """(pedido_de_compra, menor_venda) do livro aberto.

    OS DOIS DE UMA VEZ, porque a decisao precisa dos dois: um diz por quanto da
    para vender AGORA, o outro diz onde a fila comeca."""

    menor_venda = comum.ler_numero(cd.PRECO_VENDA)
    pedido = comum.ler_numero(cd.compra_preco(0))

    return pedido, menor_venda


def _dialogo_confere(esperado):
    """True quando o dialogo esta na tela e o valor dele ainda serve.

    A MESMA LICAO DA COMPRA: o numero que o jogo mostra antes de confirmar e a
    unica fonte que nao passou pelo nosso OCR duas vezes nem pela nossa
    aritmetica. La ele evitou pagar caro; aqui evita vender barato."""

    if not VERIFICAR_DIALOGO:
        return True, esperado, ''

    comum.esperar_estavel(cd.CMP_DIALOGO_COMPRA, ESPERA_CAMPO,
                          intervalo=comum.SONDAGEM_LENTA)

    texto = comum.ler_texto(cd.CMP_DIALOGO_COMPRA)
    palavras = comum.normalizar(texto)

    if not any(p in palavras for p in PALAVRAS_DO_DIALOGO):
        comum.contar('dialogo_de_venda_ausente')
        _guardar_falha('dialogo_ausente', [texto])
        return False, None, 'o dialogo de confirmacao nao esta na tela'

    recebido = comum.numero_valido(texto)

    if recebido is None:
        comum.contar('dialogo_de_venda_ilegivel')
        return True, esperado, ''

    return True, recebido, ''


def vender_na_hora(esperado):
    """Vender → Vender. Devolve (ok, recebido, motivo).

    SAO DOIS CLIQUES E UM DIALOGO, do mesmo jeito da compra: o primeiro abre a
    acao, o segundo pede a venda, e o dialogo diz quanto entra."""

    antes = comum.assinatura(cd.PRECO_VENDA)

    comum.secao_critica.set()

    try:
        comum.clicar(cd.BM_VENDER)

        ok, recebido, motivo = _dialogo_confere(esperado)

        if not ok:
            comum.clicar(cd.CMP_NAO_COMPRAR)
            return False, None, motivo

        comum.clicar(cd.CMP_CONFIRMAR_SIM)

    finally:
        comum.secao_critica.clear()

    if not comum.esperar_mudanca(cd.PRECO_VENDA, antes, ESPERA_VENDA):
        comum.contar('vendas_nao_confirmadas')
        return False, None, 'a tela nao confirmou'

    comum.esperar_estavel(cd.PRECO_VENDA, ESPERA_VENDA,
                          comum.LEITURAS_IGUAIS_PRECO, comum.SONDAGEM_LENTA)

    comum.contar('vendas_na_hora')

    return True, recebido, ''


def criar_ordem(preco, unidades):
    """Pedido de Venda a <preco>. Devolve (ok, motivo)."""

    comum.secao_critica.set()

    try:
        comum.clicar(cd.BM_PEDIDO_DE_VENDA)

        # O MESMO PREENCHIMENTO DA COMPRA, e pela mesma razao: digitar num campo
        # que ja tem numero CONCATENA em vez de substituir.
        import compra

        if not compra.preencher(cd.PAINEL_QTD_BARRA, cd.PAINEL_QTD_VALOR,
                                unidades):
            return False, 'a quantidade nao entrou no campo'

        if not compra.preencher(cd.PAINEL_PRECO_CAMPO, cd.PAINEL_PRECO_VALOR,
                                preco):
            return False, 'o preco nao entrou no campo'

        comum.clicar(cd.PAINEL_CRIAR)

    finally:
        comum.secao_critica.clear()

    comum.contar('ordens_de_venda_criadas')

    return True, ''


def _guardar_falha(nome, extras):

    if not SALVAR_FALHAS:
        return

    comum.salvar_diagnostico(PASTA_FALHAS,
                             time.strftime('%H%M%S') + '_' + nome,
                             regiao=cd.CMP_DIALOGO_COMPRA, extras=extras)

#endregion

#region A carga inteira


def vender_item(item, pago, unidades, margem=None, taxa=None,
                de_verdade=True):
    """Vende uma combinacao no Mercado Negro. Devolve o resultado."""

    saida = {'item': item, 'unidades': 0, 'recebido': 0, 'modo': '',
             'motivo': ''}

    ok, motivo = abrir(item)

    if not ok:
        saida['motivo'] = motivo
        comum.contar('itens_sem_painel')
        return saida

    try:
        pedido, menor = ler_precos()

        modo, preco, motivo = decidir(pago, pedido, menor, margem, taxa)

        saida['modo'] = modo or ''
        saida['motivo'] = motivo

        if modo is None:
            comum.contar('vendas_sem_saida')
            return saida

        if not de_verdade:
            saida['unidades'] = unidades
            saida['recebido'] = (preco or 0) * unidades
            return saida

        if modo == 'na hora':

            levadas = 0
            recebido = 0

            for _ in range(unidades):

                if comum.deve_parar():
                    break

                ok, entrou, motivo = vender_na_hora(preco)

                if not ok:
                    saida['motivo'] = motivo
                    break

                levadas += 1
                recebido += entrou or preco

                historico.vendeu(mercado.MERCADO_NEGRO, item, '', 1,
                                 entrou or preco, modo='na hora')

                comum.avisar(f'vendeu {item}', comum.fmt(entrou or preco), 'ok')

            saida['unidades'] = levadas
            saida['recebido'] = recebido

            return saida

        ok, motivo = criar_ordem(preco, unidades)

        if not ok:
            saida['motivo'] = motivo
            return saida

        saida['unidades'] = unidades
        saida['recebido'] = preco * unidades

        historico.vendeu(mercado.MERCADO_NEGRO, item, '', unidades, preco,
                         modo='ordem', observacao='ordem criada, ainda nao paga')

        comum.avisar(f'ordem de {item}', comum.fmt(preco))

    finally:
        fechar()

    return saida


def vender(carga, margem=None, taxa=None, de_verdade=True):
    """Percorre a carga e vende. <carga> e uma lista de (item, pago, unidades).

    A CARGA VEM DO HISTORICO, e nao de um inventario lido da tela: o que se
    precisa saber de cada unidade e QUANTO ELA CUSTOU, e isso a tela do jogo nao
    mostra. Sem esse numero nao ha alvo, e sem alvo a decisao vira chute."""

    problemas = comum.sem_foco()

    if problemas:
        relatar('ABORTADO antes de tocar no mouse:')
        for p in problemas:
            relatar(f'  - {p}')
        return {'erro': 'jogo sem foco'}

    if not carga:
        return {'erro': 'nada para vender'}

    inicio = time.monotonic()

    unidades = 0
    recebido = 0
    feitas = 0
    com_erro = []

    relatar('')
    relatar(f'Vendendo {len(carga)} itens no {mercado.MERCADO_NEGRO}')
    relatar('')

    for n, (item, pago, quantas) in enumerate(carga, start=1):

        if comum.deve_parar():
            relatar(f'>>> parado no item {n} de {len(carga)} <<<')
            break

        if comum.pausado.is_set():

            _, pode_seguir = comum.aguardar_retomada(
                (f'parado antes do item {n} de {len(carga)}',
                 f'{comum.fmt(recebido)} recebidos ate aqui'))

            if not pode_seguir:
                break

        if comum.pular_pedido.is_set():
            comum.pular_pedido.clear()
            relatar('      PULADO a pedido')
            continue

        if not comum.jogo_em_foco():
            relatar(f'PARANDO no item {n} - o jogo saiu de primeiro plano.')
            break

        relatar(f'[{n}/{len(carga)}] {item}  {quantas}x, pagos '
                f'{comum.fmt(pago)} cada')

        comum.progresso(n, len(carga), f'vendendo {item}')

        try:
            r = vender_item(item, pago, quantas, margem, taxa, de_verdade)

        except comum.Abortado:
            relatar(f'>>> F12 - parado em "{item}" <<<')
            break

        except Exception as e:
            com_erro.append(item)
            relatar(f'      ERRO neste item - seguindo: {e}')
            continue

        if r['unidades']:
            feitas += 1
            unidades += r['unidades']
            recebido += r['recebido']
            relatar(f'      {r["unidades"]}x por {comum.fmt(r["recebido"])} '
                    f'({r["modo"]}) - {r["motivo"]}')
        else:
            relatar(f'      nada: {r["motivo"]}')

    resumo = {
        'itens': len(carga),
        'itens_vendidos': feitas,
        'unidades': unidades,
        'recebido': recebido,
        'com_erro': com_erro,
        'minutos': (time.monotonic() - inicio) / 60,
        'contadores': comum.contadores(),
    }

    relatar('')
    relatar(f'{feitas} de {len(carga)} itens, {unidades} unidades, '
            f'{comum.fmt(recebido)} recebidos em {resumo["minutos"]:.0f} min')

    do_dia = historico.do_dia()

    relatar(f'  hoje: {comum.fmt(do_dia["gasto"])} gastos, '
            f'{comum.fmt(do_dia["recebido"])} recebidos, '
            f'saldo {comum.fmt(do_dia["saldo"])}')

    return resumo


def carga_do_dia():
    """O que foi comprado hoje e ainda nao foi vendido: [(item, pago, quantas)].

    AGRUPADO POR ITEM E PRECO. Duas compras do mesmo item ao mesmo preco sao a
    mesma decisao de venda; separa-las so faria abrir o painel duas vezes."""

    compras = {}
    vendas = {}

    for o in historico.ler(_meia_noite()):

        chave = (o['item'], o['preco'])

        if o['operacao'] == historico.COMPRA:
            compras[chave] = compras.get(chave, 0) + o['unidades']
        else:
            vendas[o['item']] = vendas.get(o['item'], 0) + o['unidades']

    carga = []

    for (item, pago), quantas in sorted(compras.items()):

        ja_vendidas = vendas.get(item, 0)
        sobram = quantas - min(quantas, ja_vendidas)

        vendas[item] = max(0, ja_vendidas - quantas)

        if sobram > 0:
            carga.append((item, pago, sobram))

    return carga


def _meia_noite():

    agora = time.localtime()

    return time.mktime((agora.tm_year, agora.tm_mon, agora.tm_mday,
                        0, 0, 0, 0, 0, -1))

#endregion
