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
# oferecendo, e a unica referencia honesta e o custo real daquela unidade. O
# historico ja grava esse custo real: a compra por ordem com os 2,5% dentro, a
# compra na hora sem taxa nenhuma. Somar a taxa de ordem de novo aqui punha o
# alvo 2,5% acima do que a lista tinha aprovado.
#
#
# NADA SAI ABAIXO DO PISO, NEM NA HORA. O piso e o "perto do alvo" da tela, e
# nunca menos que o custo. Ele e conferido no dialogo de CADA unidade: vendido o
# primeiro pedido de compra, a unidade seguinte casa com o pedido de baixo, que
# pode ser bem menor - e antes o bot vendia todas sem olhar.
#
# Antes de alterar: python -m pyflakes motor/vendedor.py

import time

from motor import ajustes
from motor import comum
from motor import coordenadas as cd
from motor import escuta
from motor import historico
from motor import lucro
from motor import mercado
from motor import mercado_negro
from motor.comum import relatar

#region Configuracao

# Quanto do alvo basta para vender na hora, em vez de entrar na fila.
#
# 0,95 quer dizer: recebendo 95% do que eu queria, pego agora. Os 5% sao o preco
# de nao ficar com a carga esperando - e uma carga parada nao rende nada.
PERTO_DO_ALVO = 0.95

# Quanto abaixo do vendedor mais barato entrar na fila. Uma prata - ver o lucro,
# que usa o mesmo numero para prever a venda por ordem.
ABAIXO_DO_MENOR = lucro.ABAIXO_DO_MENOR

# Quantas horas para tras a carga olha.
#
# A CARGA NAO ACABA A MEIA-NOITE. Antes ela comecava as 0h: quem comprava as
# 23h50 e chegava ao Mercado Negro as 0h10 encontrava a carga vazia. Dois dias
# cobrem a viagem com folga; mais que isso, o que sobrou quase sempre foi vendido
# a mao, fora do bot, e ficaria na carga para sempre.
HORAS_DA_CARGA = 48

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
    """Por quanto e preciso vender esta unidade. Ver lucro.venda_minima.

    <pago> e o custo real, como o historico grava - ver o cabecalho."""

    conf = ajustes.atuais()

    return lucro.venda_minima(
        pago,
        conf['margem'] if margem is None else margem,
        conf['taxa'] if taxa is None else taxa,
        ordem_na_compra=False,
        ordem_na_venda=por_ordem)


def piso(pago, margem=None, taxa=None, perto=PERTO_DO_ALVO):
    """O menor pedido de compra que ainda serve para vender NA HORA.

    E o "perto do alvo" da tela, mas nunca abaixo do custo: com o "perto" em 50%
    o alvo podia cair abaixo do que foi pago, e a tela promete que nada e vendido
    abaixo do custo."""

    return max(int(alvo(pago, margem, taxa) * perto + 0.999),
               alvo(pago, 0, taxa))


def decidir(pago, pedido_de_compra, menor_venda, margem=None, taxa=None,
            perto=PERTO_DO_ALVO):
    """Como vender esta unidade. Devolve (modo, preco, motivo).

    <modo> e 'na hora', 'ordem' ou None quando nao vale vender de jeito nenhum.

    A ORDEM DAS PERGUNTAS IMPORTA. Primeiro se pergunta se da para receber AGORA
    por um valor aceitavel - porque receber agora e melhor que receber talvez.
    So quando nao da e que se calcula a fila.

    PEDIDO ACIMA DA FILA E LEITURA ERRADA, como no lucro.melhor_venda: quem
    quisesse pagar mais que a oferta mais barata ja teria comprado dela."""

    if pedido_de_compra and menor_venda and pedido_de_compra > menor_venda:
        comum.contar('pedido_acima_da_fila')
        pedido_de_compra = None

    alvo_agora = alvo(pago, margem, taxa, por_ordem=False)

    if pedido_de_compra and pedido_de_compra >= piso(pago, margem, taxa, perto):
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


def _dialogo_confere(esperado, minimo=None, primeira=True):
    """(ok, recebido, motivo): o dialogo esta na tela e o valor dele serve?

    A MESMA LICAO DA COMPRA: o numero que o jogo mostra antes de confirmar e a
    unica fonte que nao passou pelo nosso OCR duas vezes nem pela nossa
    aritmetica. La ele evitou pagar caro; aqui evita vender barato - desde que
    alguem compare o numero com o <minimo>, o que antes ninguem fazia.

    DIALOGO ILEGIVEL SO PASSA NA PRIMEIRA UNIDADE. Ali o <esperado> acabou de
    ser lido do livro aberto. Da segunda em diante o pedido da frente pode ter
    acabado, e o numero que valeria e justamente o que nao deu para ler."""

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

    recebido = comum.preco_do_dialogo(texto)

    if recebido is None:
        comum.contar('dialogo_de_venda_ilegivel')

        if primeira:
            return True, esperado, ''

        _guardar_falha('dialogo_ilegivel', [texto])
        return False, None, ('o dialogo nao deu para ler, e o pedido da frente '
                             'pode ter acabado')

    if minimo and recebido < minimo:
        comum.contar('vendas_abaixo_do_piso')
        return False, recebido, (f'o jogo pagaria {comum.fmt(recebido)}, abaixo '
                                 f'do piso de {comum.fmt(minimo)}')

    return True, recebido, ''


def vender_na_hora(esperado, minimo=None, primeira=True):
    """Vender → Vender. Devolve (ok, recebido, motivo).

    SAO DOIS CLIQUES E UM DIALOGO, do mesmo jeito da compra: o primeiro abre a
    acao, o segundo pede a venda, e o dialogo diz quanto entra. Abaixo do
    <minimo>, o dialogo e recusado."""

    antes = comum.assinatura(cd.PRECO_VENDA)

    comum.secao_critica.set()

    try:
        comum.clicar(cd.BM_VENDER)

        ok, recebido, motivo = _dialogo_confere(esperado, minimo, primeira)

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
        from motor import compra

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
                de_verdade=True, perto=PERTO_DO_ALVO, qualidade=None,
                combinacao='', pago_se_incerto=None):
    """Vende uma combinacao no Mercado Negro. Devolve o resultado.

    <qualidade> so vem na unidade comprada por qualidade: ai o pedido que conta
    e o maior que ela atende, e nao o da Normal.

    <combinacao> e a da carga ('T5.2'). O painel abre o item que estiver no
    inventario, e o vendedor nao escolhe o grau; com a rede mandando, o pacote
    diz qual combinacao abriu, e se for outra nao vende - o custo que decidiria
    a venda e o desta, e nao o daquela.

    <pago_se_incerto> e o custo para decidir quando nao da para confirmar a
    combinacao aberta - ver custos_se_incerto()."""

    taxa = ajustes.atuais()['taxa'] if taxa is None else taxa

    saida = {'item': item, 'unidades': 0, 'recebido': 0, 'em_ordem': 0,
             'modo': '', 'motivo': ''}

    aberto_em = escuta.marca()

    ok, motivo = abrir(item)

    if not ok:
        saida['motivo'] = motivo
        comum.contar('itens_sem_painel')
        return saida

    try:
        # pela rede quando ela chega - o grau e o do item no inventario, e o
        # pacote do painel aberto e o mais recente daquele item
        rede = escuta.ultimo_do_item(mercado.MERCADO_NEGRO, item, aberto_em,
                                     qualidade=qualidade or 1)

        aberta = None

        if rede is not None and rede[1] is not None:

            aberta = escuta.combinacao_aberta(mercado.MERCADO_NEGRO, item,
                                              aberto_em)

            if combinacao and aberta and aberta != combinacao:
                comum.contar('painel_em_outra_combinacao')
                saida['motivo'] = (f'o painel abriu {aberta}, e a carga e '
                                   f'{combinacao}')
                return saida

            pedido, menor = rede
            comum.contar('livros_pela_rede')
        else:
            pedido, menor = ler_precos()

        # A COMBINACAO SO VAI PARA O HISTORICO QUANDO A REDE CONFIRMA qual foi.
        # Gravada no chute, a venda abateria a compra de outro grau na carga.
        confirmada = bool(combinacao) and aberta == combinacao

        if not confirmada and pago_se_incerto:
            pago = pago_se_incerto

        modo, preco, motivo = decidir(pago, pedido, menor, margem, taxa, perto)

        saida['modo'] = modo or ''
        saida['motivo'] = motivo

        if modo is None:
            comum.contar('vendas_sem_saida')
            return saida

        if not de_verdade:
            saida['unidades'] = unidades
            liquido = int(lucro.receita_real(preco, taxa, modo == 'ordem') * unidades)
            saida['em_ordem' if modo == 'ordem' else 'recebido'] = liquido
            return saida

        vendida = combinacao if confirmada else ''

        if modo == 'na hora':

            minimo = piso(pago, margem, taxa, perto)
            levadas = 0
            recebido = 0

            for _ in range(unidades):

                if comum.deve_parar():
                    break

                ok, entrou, motivo = vender_na_hora(preco, minimo,
                                                    primeira=not levadas)

                if not ok:
                    saida['motivo'] = motivo
                    break

                entrou = entrou or preco
                liquido = int(lucro.receita_real(entrou, taxa))

                levadas += 1
                recebido += liquido

                historico.vendeu(mercado.MERCADO_NEGRO, item, vendida, 1,
                                 entrou, modo='na hora', qualidade=qualidade,
                                 liquido=liquido)

                comum.avisar(f'vendeu {item}', comum.fmt(entrou), 'ok')

            saida['unidades'] = levadas
            saida['recebido'] = recebido

            return saida

        ok, motivo = criar_ordem(preco, unidades)

        if not ok:
            saida['motivo'] = motivo
            return saida

        # A ORDEM NAO E PRATA RECEBIDA: ela fica na fila e pode nunca vender.
        # Vai para o historico como ordem, e o saldo nao a conta.
        saida['unidades'] = unidades
        saida['em_ordem'] = int(lucro.receita_real(preco, taxa, True) * unidades)

        historico.vendeu(mercado.MERCADO_NEGRO, item, vendida, unidades, preco,
                         modo=historico.ORDEM,
                         observacao='ordem criada, ainda nao paga',
                         qualidade=qualidade, liquido=saida['em_ordem'])

        comum.avisar(f'ordem de {item}', comum.fmt(preco))

    finally:
        fechar()

    return saida


def custos_se_incerto(carga):
    """O custo que decide cada entrada quando o painel aberto nao e confirmado.

    E O PAGO DELA - menos quando o mesmo item esta na carga em mais de uma
    combinacao. Sem a rede dizendo qual grau o painel abriu, decidir a venda de
    um T8 com o custo de um T5 seria vender o T8 pelo preco do T5. Ai vale o
    custo do mais caro: o pior que acontece e o mais barato nao vender agora."""

    maior = {}
    combinacoes = {}

    for e in carga:
        maior[e['item']] = max(maior.get(e['item'], 0), e['pago'])
        combinacoes.setdefault(e['item'], set()).add(e['combinacao'])

    return [maior[e['item']] if len(combinacoes[e['item']]) > 1 else e['pago']
            for e in carga]


def vender(carga, margem=None, taxa=None, de_verdade=True, perto=PERTO_DO_ALVO):
    """Percorre a carga e vende. <carga> e a de carga_pendente().

    A CARGA VEM DO HISTORICO, e nao de um inventario lido da tela: o que se
    precisa saber de cada unidade e QUANTO ELA CUSTOU, e isso a tela do jogo nao
    mostra. Sem esse numero nao ha alvo, e sem alvo a decisao vira chute.

    <perto> e o "vender na hora a partir de X% do alvo" da tela. Antes ele so
    mudava a previsao da tabela: a venda de verdade usava sempre o padrao."""

    problemas = comum.sem_foco()

    if problemas:
        relatar('ABORTADO antes de tocar no mouse:')
        for p in problemas:
            relatar(f'  - {p}')
        return {'erro': 'jogo sem foco'}

    if not carga:
        return {'erro': 'nada para vender'}

    inicio = time.monotonic()

    incertos = custos_se_incerto(carga)

    unidades = 0
    recebido = 0
    em_ordens = 0
    feitas = 0
    com_erro = []

    relatar('')
    relatar(f'Vendendo {len(carga)} itens no {mercado.MERCADO_NEGRO}')
    relatar('')

    for n, e in enumerate(carga, start=1):

        item = e['item']

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

        relatar(f'[{n}/{len(carga)}] {item} {e["combinacao"]}  {e["unidades"]}x, '
                f'pagos {comum.fmt(e["pago"])} cada')

        comum.progresso(n, len(carga), f'vendendo {item}')

        try:
            r = vender_item(item, e['pago'], e['unidades'], margem, taxa,
                            de_verdade, perto, e['qualidade'],
                            combinacao=e['combinacao'],
                            pago_se_incerto=incertos[n - 1])

        except comum.Abortado:
            relatar(f'>>> F12 - parado em "{item}" <<<')
            break

        except Exception as erro:
            com_erro.append(item)
            relatar(f'      ERRO neste item - seguindo: {erro}')
            continue

        if r['unidades']:
            feitas += 1
            unidades += r['unidades']
            recebido += r['recebido']
            em_ordens += r['em_ordem']
            comum.placar(recebido=recebido, unidades=unidades)

            if r['modo'] == 'ordem':
                relatar(f'      {r["unidades"]}x em ordem, {comum.fmt(r["em_ordem"])} '
                        f'liquidos se vender - {r["motivo"]}')
            else:
                relatar(f'      {r["unidades"]}x por {comum.fmt(r["recebido"])} '
                        f'liquidos ({r["modo"]}) - {r["motivo"]}')
        else:
            relatar(f'      nada: {r["motivo"]}')

    resumo = {
        'itens': len(carga),
        'itens_vendidos': feitas,
        'unidades': unidades,
        'recebido': recebido,
        'em_ordens': em_ordens,
        'com_erro': com_erro,
        'minutos': (time.monotonic() - inicio) / 60,
        'contadores': comum.contadores(),
    }

    relatar('')
    relatar(f'{feitas} de {len(carga)} itens, {unidades} unidades, '
            f'{comum.fmt(recebido)} recebidos'
            + (f' e {comum.fmt(em_ordens)} em ordens' if em_ordens else '')
            + f' em {resumo["minutos"]:.0f} min')

    if comum.contador('vendas_abaixo_do_piso'):
        relatar(f'  {comum.contador("vendas_abaixo_do_piso")} vendas recusadas no '
                f'dialogo por pagarem abaixo do piso - o resto fica na carga')

    if comum.contador('painel_em_outra_combinacao'):
        relatar(f'  {comum.contador("painel_em_outra_combinacao")} itens em que o '
                f'painel abriu outra combinacao - nao vendidos')

    do_dia = historico.do_dia()

    relatar(f'  hoje: {comum.fmt(do_dia["gasto"])} gastos, '
            f'{comum.fmt(do_dia["recebido"])} recebidos, '
            f'saldo {comum.fmt(do_dia["saldo"])}')

    return resumo


def carga_pendente(horas=HORAS_DA_CARGA):
    """O que foi comprado nas ultimas <horas> e ainda nao foi vendido.

    Uma lista de {'item', 'combinacao', 'pago', 'unidades', 'qualidade'}, uma
    entrada por item, combinacao, preco e qualidade: duas compras iguais sao a
    mesma decisao de venda, e separa-las so faria abrir o painel duas vezes.

    A COMBINACAO VAI JUNTO. Sem ela, a previsao da venda usava o maior pedido do
    item em qualquer grau - o de um T8 para prever um T5.

    A UNIDADE COMPRADA POR QUALIDADE leva a qualidade junto. Ela foi comprada
    para um pedido daquela qualidade, e vende-la como Normal desfaria o negocio.

    CADA VENDA ABATE AS COMPRAS MAIS ANTIGAS do mesmo item, na ordem em que
    aconteceram: primeiro as da mesma qualidade, depois qualquer uma. So restringe
    a combinacao quando a venda sabe qual foi - as antigas gravavam vazio."""

    lotes = []

    for o in historico.ler(time.time() - horas * 3600):

        if o['operacao'] == historico.COMPRA:
            lotes.append({'item': o['item'], 'combinacao': o['combinacao'],
                          'pago': o['preco'], 'unidades': o['unidades'],
                          'qualidade': o['qualidade']})
            continue

        falta = o['unidades']

        for mesma_qualidade in (True, False):
            for lote in lotes:

                if falta <= 0:
                    break

                if (lote['item'] != o['item'] or lote['unidades'] <= 0
                        or (o['combinacao'] and lote['combinacao'] != o['combinacao'])
                        or (mesma_qualidade and lote['qualidade'] != o['qualidade'])):
                    continue

                abate = min(falta, lote['unidades'])
                lote['unidades'] -= abate
                falta -= abate

    carga = {}

    for lote in lotes:

        if lote['unidades'] <= 0:
            continue

        chave = (lote['item'], lote['combinacao'], lote['pago'],
                 lote['qualidade'] or 0)

        if chave in carga:
            carga[chave]['unidades'] += lote['unidades']
        else:
            carga[chave] = dict(lote)

    return [carga[k] for k in sorted(carga)]


def _meia_noite():

    agora = time.localtime()

    return time.mktime((agora.tm_year, agora.tm_mon, agora.tm_mday,
                        0, 0, 0, 0, 0, -1))

#endregion
