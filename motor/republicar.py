################################
#                              #
#      VENDER PELO MERCADO     #
#                              #
################################

# Vender o que estiver na mochila sem depender do historico de compras.
#
# A VENDA DA CARGA (vendedor.py) SO CONHECE O QUE O BOT COMPROU: o alvo e o piso
# saem do preco pago. Item comprado a mao, comprado ha mais de dois dias, ou que
# voltou de uma ordem cancelada para ser recolocado com preco novo ficava sem
# saida - a aba Vender pedia para rodar a compra antes.
#
# Aqui o preco sai do mercado, e de mais nada. Para cada linha da lista "Sell
# from Inventory" do Mercado Negro - que e a mochila -, de cima para baixo:
#
#     1. clica em Sell na linha e escolhe "Sell Order" no painel;
#     2. se a qualidade nao for Normal, troca o filtro para Normal, le o menor
#        preco da fila e restaura o painel para a versao da mochila;
#     3. cria a ordem uma prata abaixo desse menor preco - na frente da fila.
#
# A quantidade ja vem no maximo, e a ordem leva a pilha inteira. Com a pilha
# vendida ela sai da lista, e a de baixo sobe para o mesmo lugar.
#
# O QUE A LISTA MOSTRAR E O QUE SERA VENDIDO: a mochila inteira, ou so o que a
# busca da tela filtrar. O equipamento vestido nao aparece nela.
#
# Antes de alterar: python -m pyflakes motor/republicar.py

import time

from motor import categorias
from motor import comum
from motor import compra
from motor import coordenadas as cd
from motor import filtros
from motor import historico
from motor import lucro
from motor import mercado
from motor import mercado_negro
from motor import nomes
from motor.comum import relatar

#region Configuracao

# Limites, em segundos.
ESPERA_PAINEL = 2.50
ESPERA_CRIAR = 2.50

# A imagem e o OCR do campo de preco que nao conferiu, em dados/registros.
PASTA_FALHAS = 'falhas_venda_mochila'

#endregion

#region A qualidade


def qualidade_mostrada():
    """O texto do filtro de qualidade do painel, normalizado ('good', 'normal')."""

    return comum.normalizar(comum.ler_texto(cd.VND_QUAL_ROTULO))


def _e_normal(texto):
    return 'normal' in texto


def _restaurar():
    """Volta o painel a versao do item que esta na mochila."""

    comum.clicar(cd.VND_RESTAURAR)
    comum.esperar_estavel(cd.PRECO_VENDA, ESPERA_PAINEL, intervalo=comum.SONDAGEM_LENTA)


def preco_de_referencia():
    """(preco, motivo): o menor preco de venda que a ordem vai bater.

    O DA QUALIDADE NORMAL. Com o item em outra qualidade, o filtro vai para
    Normal, o preco e lido, e o painel e restaurado - a ordem tem de ser da
    versao que esta na mochila. Sem ninguem vendendo Normal, vale o menor preco
    da propria qualidade.

    None quando nao ha preco nenhum, ou quando o painel nao voltou para a
    qualidade do item: criar a ordem ali seria vender outra versao.

    A TROCA E CONFERIDA PELA FILA, E NAO SO PELO ROTULO. O OCR do rotulo do
    filtro falhou no jogo: o filtro ia para Normal, o preco era lido, e o bot
    desistia por nao enxergar a palavra "Normal". A fila mudando e prova de
    que o filtro trocou; o rotulo fica como segunda prova."""

    proprio = comum.ler_numero(cd.PRECO_VENDA)

    rotulo = qualidade_mostrada()

    if _e_normal(rotulo):
        return proprio, '' if proprio else 'ninguem esta vendendo este item'

    troca = filtros.trocar(
        lambda: filtros.escolher(cd.VND_BARRA_QUAL, cd.VND_QUAL_NORMAL,
                                 mercado_negro._deteccao(cd.VND_BARRA_QUAL),
                                 afastar=False),
        regiao=cd.PRECO_VENDA)

    if troca is not True and not _e_normal(qualidade_mostrada()):
        # a fila nao mudou e o rotulo nao diz Normal: ou o filtro nao trocou,
        # ou a Normal tem o mesmo menor preco. Nos dois casos o preco da
        # propria qualidade e o que da para confirmar
        comum.contar('qualidade_nao_foi_para_normal')
        _restaurar()
        return proprio, '' if proprio else 'ninguem esta vendendo este item'

    # um numero DIFERENTE do da qualidade do item: o igual pode ser a tela que
    # ainda nao trocou
    normal = comum.ler_numero_novo(cd.PRECO_VENDA, proprio)

    _restaurar()

    if normal and proprio and normal != proprio:
        # a fila tem de sair do preco da Normal
        restaurado = comum.ler_numero_novo(cd.PRECO_VENDA, normal) is not None
    else:
        restaurado = not _e_normal(qualidade_mostrada())

    if not restaurado:
        comum.contar('painel_nao_restaurou')
        return None, 'o painel nao voltou para a qualidade do item'

    if normal:
        return normal, ''

    comum.contar('sem_normal_vendendo')

    return proprio, ('' if proprio else 'ninguem esta vendendo este item, '
                                        'nem na qualidade Normal')

#endregion

#region Uma pilha


def unidades_do_total(total, preco):
    """Quantas unidades a ordem leva, pelo "Total" do painel. (unidades, taxa).

    O painel nao mostra a quantidade num lugar que de para ler bem; o Total
    mostra preco x unidades menos a taxa de venda - 4% com Premium, 8% sem. A
    taxa que der o numero mais redondo e a do jogo."""

    if not total or not preco:
        return None, None

    melhores = []

    for taxa in (lucro.TAXA_COM_PREMIUM, lucro.TAXA_SEM_PREMIUM):
        bruto = total / (preco * (1 - taxa))
        unidades = round(bruto)
        if unidades >= 1:
            melhores.append((abs(bruto - unidades), unidades, taxa))

    if not melhores:
        return None, None

    _, unidades, taxa = min(melhores)

    return unidades, taxa


def quantidade_pelo_total(preco):
    """(unidades, taxa) lendo o Total do painel, ou (None, None).

    PELA LEITURA DO PAINEL (compra.ler_campo), e nao pelo ler_numero: com a
    moeda no recorte ele voltava vazio, e a ordem ia para o historico como
    "quantidade nao lida" - fora da soma do que esta a venda. Das leituras, vale
    a que der um numero INTEIRO de unidades: o Total e preco x unidades menos a
    taxa de venda, e uma leitura errada nao cai redonda por acaso."""

    comum.esperar_estavel(cd.PAINEL_TOTAL_VALOR, ESPERA_PAINEL,
                          intervalo=comum.SONDAGEM_LENTA)

    for _ in range(compra.LEITURAS_DO_CAMPO):

        for total in compra.ler_campo(cd.PAINEL_TOTAL_VALOR):
            unidades, taxa = unidades_do_total(total, preco)

            if unidades and abs(total - preco * unidades * (1 - taxa)) <= max(2, total * 0.001):
                return unidades, taxa

        time.sleep(compra.ESPERA_ENTRE_LEITURAS)

    comum.contar('quantidade_nao_lida')

    return None, None


def preencher_preco(preco):
    """Digita o preco no campo do painel e CONFERE lendo de volta.

    A leitura do campo em edicao e a mesma da compra - ver
    compra.preencher_conferindo."""

    return compra.preencher_conferindo(cd.PAINEL_PRECO_CAMPO, cd.VND_PRECO_VALOR,
                                       preco)


def listar_aberto(item, de_verdade=True):
    """Cria o pedido de venda do painel aberto. Devolve o resultado, sem levantar.

    {'ok', 'preco', 'unidades', 'motivo'}. <de_verdade> False faz tudo menos
    digitar o preco e criar a ordem."""

    saida = {'ok': False, 'preco': None, 'unidades': None, 'motivo': ''}

    comum.clicar(cd.BM_PEDIDO_DE_VENDA)
    comum.esperar_estavel(cd.PAINEL_PRECO_VALOR, ESPERA_PAINEL,
                          intervalo=comum.SONDAGEM_LENTA)

    base, motivo = preco_de_referencia()

    if not base or base <= lucro.ABAIXO_DO_MENOR:
        saida['motivo'] = motivo or 'sem preco para bater'
        return saida

    preco = base - lucro.ABAIXO_DO_MENOR
    saida['preco'] = preco

    if not de_verdade:
        saida.update(ok=True, motivo='simulacao')
        return saida

    comum.secao_critica.set()

    try:
        # O MESMO PREENCHIMENTO DA COMPRA: digita e CONFERE lendo de volta.
        # Ordem com o preco errado e o pior erro desta tela.
        if not preencher_preco(preco):
            _, lido = comum.ultima_captura()
            saida['motivo'] = f'o preco nao entrou no campo (lido {lido!r})'
            comum.salvar_diagnostico(PASTA_FALHAS,
                                     time.strftime('%H%M%S') + '_preco_' + item,
                                     extras=[f'digitado          : {preco}'])
            return saida

        unidades, taxa = quantidade_pelo_total(preco)

        comum.clicar(cd.PAINEL_CRIAR)

    finally:
        comum.secao_critica.clear()

    time.sleep(ESPERA_CRIAR / 5)

    # O QUE ESTA ORDEM RENDE: o bruto menos a taxa de venda (4% com Premium, 8%
    # sem - o Total do painel diz qual) e os 2,5% de criar a ordem
    liquido = (int(preco * unidades * (1 - taxa - lucro.TAXA_DE_ORDEM))
               if unidades else None)

    saida.update(ok=True, unidades=unidades, taxa=taxa,
                 bruto=preco * unidades if unidades else None, liquido=liquido)

    historico.vendeu(mercado.MERCADO_NEGRO, item, '', unidades or 1, preco,
                     modo=historico.ORDEM,
                     observacao=('pelo mercado: menor preco da Normal menos 1'
                                 + ('' if unidades else ' (quantidade nao lida)')),
                     liquido=liquido)

    comum.contar('ordens_pelo_mercado')
    comum.avisar(f'ordem de {item}', comum.fmt(preco))

    return saida

#endregion

#region A lista "Sell from Inventory"

# A lista do Mercado Negro na aba de vender JA E A MOCHILA. Procurar item por
# item do catalogo na busca era lento e nao tinha por que: aqui o bot clica no
# Sell de cada linha, de cima para baixo.
#
# A LINHA SO ANDA QUANDO NAO HOUVE ORDEM. Criada a ordem, a pilha sai da lista e
# a de baixo sobe para o mesmo lugar - entao a proxima e a mesma linha. Pilha que
# nao virou ordem (sem preco, qualidade que nao trocou) fica, e o bot passa para
# a linha de baixo.

LINHAS_VISIVEIS = 5

# Teto de ordens numa passada: uma ordem que nao saisse da lista sem o bot
# perceber o faria voltar na mesma linha para sempre.
MAXIMO_DE_ORDENS = 60


def _sell_da_linha(n):
    """O botao Sell da linha <n> da lista (0 = a primeira)."""

    return {'x': cd.VND_VENDER['x'], 'y': cd.VND_VENDER['y'] + n * cd.LISTA_PASSO}


def _nome_da_linha(n):
    """O nome escrito na linha <n>, para o historico."""

    x1, y1, x2, y2 = cd.LINHA_ITEM
    dy = n * cd.LISTA_PASSO

    return comum.ler_texto((x1, y1 + dy, x2, y2 + dy))


def abrir_linha(n):
    """Clica no Sell da linha <n> e espera o painel. False se nao ha item ali."""

    antes = comum.assinatura(cd.PRECO_VENDA)

    comum.clicar(_sell_da_linha(n), espera=0)

    if comum.esperar_mudanca(cd.PRECO_VENDA, antes, ESPERA_PAINEL):
        comum.esperar_estavel(cd.PRECO_VENDA, ESPERA_PAINEL)
        return True

    # o painel pode ter aberto sem mudar aquele recorte - a leitura decide
    return (comum.ler_numero(cd.PRECO_VENDA) is not None
            or mercado_negro.livro_vazio())


def item_da_linha(texto):
    """'Grandmaster's Hoarfrost Staff' -> 'Hoarfrost Staff', o nome do catalogo.

    E o nome que o historico usa, e e por ele que a venda abate a carga das
    compras do bot. Sem reconhecer o item, fica o texto lido."""

    # o recorte pega a borda do icone, e o OCR poe lixo em volta do nome:
    # "a | Grandmaster's Spiked Gauntlets" - o grau e procurado em qualquer lugar
    lido = comum.normalizar(texto)

    # o T8 com nome proprio: "Vendetta's Wrath" e o Great Fire Staff
    for (base, _), proprio in nomes.NOME_PROPRIO.items():
        if comum.normalizar(proprio) in lido:
            return base

    for prefixo in nomes.PREFIXO_INGLES.values():
        p = comum.normalizar(prefixo) + ' '
        if p in lido:
            lido = lido[lido.index(p) + len(p):]
            break

    do_menu = {menu: catalogo for catalogo, menu in categorias.NOME_NO_MENU.items()}

    # o mais comprido que casar com o comeco: "Bow" nao pode levar o "Bow of Badon"
    casam = [nome for nome in categorias.itens_mapeados()
             if lido == comum.normalizar(nome)
             or lido.startswith(comum.normalizar(nome) + ' ')]

    if casam:
        nome = max(casam, key=len)
        return do_menu.get(nome, nome)

    return (texto or '').strip() or 'item da mochila'


def vender(de_verdade=True):
    """Cria a ordem de cada pilha da lista "Sell from Inventory", de cima para baixo.

    O Mercado Negro tem de estar aberto na aba de vender. O que a lista mostrar e
    o que sera vendido - se houver texto na busca, so o que ela filtrar."""

    problemas = comum.sem_foco()

    if problemas:
        relatar('ABORTADO antes de tocar no mouse:')
        for p in problemas:
            relatar(f'  - {p}')
        return {'erro': 'jogo sem foco'}

    inicio = time.monotonic()
    ordens = 0
    puladas = 0
    linha = 0

    # O QUE FICOU A VENDA NESTA PASSADA: soma das ordens criadas, e quantas
    # ficaram fora da soma por nao ter a quantidade lida
    venda = {'unidades': 0, 'bruto': 0, 'liquido': 0, 'sem_quantidade': 0}

    relatar('')
    relatar('Vendendo a mochila pelo mercado: cada linha da lista, 1 prata '
            'abaixo do menor preco da Normal')
    relatar('')

    while ordens < MAXIMO_DE_ORDENS and linha < LINHAS_VISIVEIS:

        if comum.deve_parar():
            relatar('>>> parado <<<')
            break

        if comum.pausado.is_set():
            _, pode_seguir = comum.aguardar_retomada((f'{ordens} ordens criadas',))
            if not pode_seguir:
                break

        if comum.pular_pedido.is_set():
            comum.pular_pedido.clear()
            relatar('      PULADA a pedido')
            linha += 1
            continue

        if not comum.jogo_em_foco():
            relatar('PARANDO - o jogo saiu de primeiro plano.')
            break

        comum.progresso(ordens + puladas + 1, 0, f'linha {linha + 1} da lista')

        try:
            item = item_da_linha(_nome_da_linha(linha))

            if not abrir_linha(linha):
                # nao ha mais item ali: a lista acabou
                break

            try:
                r = listar_aberto(item, de_verdade)
            finally:
                mercado_negro.fechar_painel()

        except comum.Abortado:
            relatar('>>> F12 - parado <<<')
            break

        except Exception as erro:
            relatar(f'      ERRO na linha {linha + 1} - seguindo: {erro}')
            puladas += 1
            linha += 1
            continue

        if r['ok']:
            ordens += 1
            quantas = f'{r["unidades"]}x ' if r['unidades'] else ''
            relatar(f'{item}: {quantas}ordem a {comum.fmt(r["preco"])}'
                    + (f' = {comum.fmt(r["liquido"])} liquido' if r.get('liquido') else '')
                    + (' (simulacao)' if not de_verdade else ''))

            if r.get('liquido'):
                venda['unidades'] += r['unidades']
                venda['bruto'] += r['bruto']
                venda['liquido'] += r['liquido']
            elif de_verdade:
                venda['sem_quantidade'] += 1

            # de verdade, a pilha saiu e a de baixo subiu para esta linha;
            # simulando, nada sai - a proxima e a linha de baixo
            if not de_verdade:
                linha += 1
            continue

        relatar(f'{item}: nada - {r["motivo"]}')
        puladas += 1
        linha += 1

    return _resumo(ordens, puladas, inicio, venda, de_verdade)


def _resumo(ordens, puladas, inicio, venda=None, de_verdade=True):

    minutos = (time.monotonic() - inicio) / 60
    venda = venda or {'unidades': 0, 'bruto': 0, 'liquido': 0, 'sem_quantidade': 0}

    relatar('')
    relatar(f'{ordens} ordens criadas, {puladas} pilhas puladas, em {minutos:.0f} min')

    # O TOTAL A VENDA: o que as ordens desta passada rendem, ja sem a taxa de
    # venda e os 2,5% da ordem
    if venda['unidades']:
        relatar(f'A venda: {venda["unidades"]} unidades, {comum.fmt(venda["bruto"])} bruto, '
                f'{comum.fmt(venda["liquido"])} liquido (depois das taxas)')
        comum.avisar('Total à venda', comum.fmt(venda['liquido']))

    if venda['sem_quantidade']:
        relatar(f'  {venda["sem_quantidade"]} ordens sem a quantidade lida ficaram '
                'FORA do total')

    if not de_verdade:
        relatar('  Simulando, o preco nao e digitado - o total so sai na venda de verdade.')

    for chave, texto in (
        ('qualidade_nao_foi_para_normal',
         'itens em que nao deu para confirmar a troca para Normal - foram pelo '
         'preco da propria qualidade'),
        ('painel_nao_restaurou',
         'itens em que o painel nao voltou para a qualidade da mochila - nao '
         'viraram ordem'),
        ('campos_refeitos', 'vezes em que o preco foi digitado de novo'),
    ):
        if comum.contador(chave):
            relatar(f'  {comum.contador(chave)} {texto}')

    return {'ordens': ordens, 'puladas': puladas, 'minutos': minutos,
            'unidades': venda['unidades'], 'bruto': venda['bruto'],
            'liquido': venda['liquido'], 'sem_quantidade': venda['sem_quantidade'],
            'de_verdade': de_verdade, 'contadores': comum.contadores()}

#endregion
