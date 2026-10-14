################################
#                              #
#         ARBITRAGEM           #
#                              #
################################

# A conta que decide o que comprar: cruza o preco de uma cidade com o preco do
# Mercado Negro e devolve a lista de compras, da melhor margem para a pior.
#
# E so aritmetica. Esta num arquivo proprio porque e a unica parte do negocio que
# da para conferir sem o jogo aberto - e conferivel e o que ela precisa ser, ja
# que e ela quem manda gastar prata.
#
#
# A TAXA. O bot que serviu de referencia mostra o lucro assim:
#
#     Assassin Jacket 5.0   compra 10.994   venda 18.444   67,76%
#
#     (18.444 - 10.994) / 10.994 = 0,6776
#
# Bate ao centesimo nas seis linhas da tela dele, e o total de custo bate ao
# silver com a soma de quantidade x preco. Nao ha imposto nenhum nessa conta.
#
# Isso importa na hora de copiar o numero dele: um minimo de 23% ali e 23% ANTES
# de qualquer taxa. Aquela linha de 67,76%, com as taxas que o jogo cobra de
# verdade, e assim:
#
#     sem Premium (8%), comprando por ordem (+2,5%)   50,6%
#     sem Premium (8%), comprando na hora             54,3%
#     com Premium (4%), comprando por ordem           57,1%
#     com Premium (4%), comprando na hora             61,1%
#
# Dezessete pontos entre o numero que ele mostra e o pior caso real. Um minimo de
# 23% bruto pode ser 8% liquido - que ainda paga, mas nao e o que estava escrito.
#
# Por isso as duas contas moram aqui e aparecem lado a lado. A bruta existe para
# voce comparar com o que ve por ai; a liquida e a que decide.
#
# Antes de alterar: python -m pyflakes arbitragem.py

from motor import mercado

#region Configuracao

# AS TAXAS, LIDAS DA PROPRIA TELA DO JOGO. Sobre um preco de 6.356 o Mercado
# Negro mostrava, em vermelho:
#
#     508  (8% Taxa)
#     159  (2.5% Taxa de ordem)
#     Total: 5.848
#
# 6.356 x 0,08 = 508,5 e 6.356 x 0,025 = 158,9. Sao esses dois numeros, e nao um
# so - e eles nao incidem sempre juntos.
#
# A de venda cai pela metade com Premium. O anuncio "pague 50% a menos de taxas"
# aparecendo na tela e o que denuncia uma conta sem.
TAXA_SEM_PREMIUM = 0.08
TAXA_COM_PREMIUM = 0.04

# A taxa de ordem e cobrada por CRIAR uma ordem, seja de compra ou de venda, e
# nao muda com Premium. Quem compra ou vende na hora nao paga.
TAXA_DE_ORDEM = 0.025

# O padrao e o caso caro. Errar para menos aqui faz o programa recomendar compras
# que nao pagam; errar para mais so deixa passar negocio magro.
TAXA_PADRAO = TAXA_SEM_PREMIUM

# Margem minima padrao, em fracao. 23% e o numero da tela de referencia - mas
# la ele e bruto, e aqui e liquido por padrao. Ver o cabecalho.
MARGEM_PADRAO = 0.23

# Idade maxima de um preco, em horas, para ele poder decidir uma compra.
#
# Preco de mercado nao envelhece como nome envelhece. Um preco de ontem nao esta
# "um pouco desatualizado": ele e de outro mercado, porque quem vendia vendeu e
# quem comprava comprou. Seis horas e o meio-termo entre exigir uma coleta nova
# a cada rodada e decidir sobre dado morto.
IDADE_MAXIMA_PADRAO = 6.0

#endregion

#region A conta


def bruto(compra, venda):
    """A margem sem imposto: (venda - compra) / compra.

    E a conta que os bots por ai mostram. Serve para comparar, nao para decidir.
    """

    if not compra:
        return 0.0

    return (venda - compra) / compra


def custo_real(compra, ordem_na_compra=True):
    """O que sai do bolso por uma unidade.

    Comprar POR ORDEM custa 2,5% a mais - e o Smart Buy compra por ordem, porque
    e assim que se leva 53 unidades num clique em vez de 53. A vantagem e de
    tempo, e ela tem preco; ignorar esse preco faria a lista prometer uma margem
    que a compra ja gastou."""

    return compra * (1 + TAXA_DE_ORDEM) if ordem_na_compra else compra


def receita_real(venda, taxa=TAXA_PADRAO, ordem_na_venda=False):
    """O que entra no bolso por uma unidade vendida.

    A taxa incide sobre a VENDA e nao sobre o lucro - descontar do lucro daria um
    numero otimista, e otimista aqui significa comprar coisa que nao paga.

    Vender na hora paga so a taxa de venda. Criar pedido de venda paga tambem os
    2,5% de ordem: 10,5% no total, sem Premium."""

    return venda * (1 - taxa - (TAXA_DE_ORDEM if ordem_na_venda else 0))


def liquido(compra, venda, taxa=TAXA_PADRAO,
            ordem_na_compra=True, ordem_na_venda=False):
    """A margem depois de todas as taxas."""

    custo = custo_real(compra, ordem_na_compra)

    if not custo:
        return 0.0

    return (receita_real(venda, taxa, ordem_na_venda) - custo) / custo


def venda_minima(compra, margem=MARGEM_PADRAO, taxa=TAXA_PADRAO,
                 ordem_na_compra=True, ordem_na_venda=False):
    """Por quanto e preciso vender para a margem sair. O inverso do preco_maximo.

    O preco_maximo responde "quanto posso pagar sabendo por quanto vendo"; este
    responde "por quanto preciso vender sabendo quanto paguei". Sao a mesma
    conta virada, e o vendedor precisa desta ponta: a prata ja saiu, e o que se
    decide agora e aceitar ou nao o que o mercado esta oferecendo.

    Vender POR ORDEM paga 2,5% a mais, entao o alvo sobe - e e por isso que a
    ordem e o caminho de quem pode esperar, e nao o de quem tem pressa."""

    custo = custo_real(compra, ordem_na_compra)

    sobra = 1 - taxa - (TAXA_DE_ORDEM if ordem_na_venda else 0)

    if sobra <= 0:
        return 0

    return int(custo * (1 + margem) / sobra + 0.999)


def linha(item, rot, compra, venda, quantidade, taxa=TAXA_PADRAO,
          ordem_na_compra=True, ordem_na_venda=False):
    """Uma linha da lista de compras, com as duas margens e os totais."""

    custo = custo_real(compra, ordem_na_compra)
    receita = receita_real(venda, taxa, ordem_na_venda)

    return {
        'item': item,
        'combinacao': rot,
        'compra': compra,
        'venda': venda,
        'quantidade': quantidade,
        'margem_bruta': bruto(compra, venda),
        'margem': liquido(compra, venda, taxa, ordem_na_compra, ordem_na_venda),
        'lucro_unitario': receita - custo,
        'custo': custo * quantidade,
        'receita': receita * quantidade,
        'lucro': (receita - custo) * quantidade,
        # o que voce ve na tela do jogo, sem taxa nenhuma - para conferir
        'custo_de_tabela': compra * quantidade,
        'receita_de_tabela': venda * quantidade,
    }

#endregion

#region A lista


# Quanto a mais de lucro por unidade uma qualidade maior precisa dar para tomar o
# lugar da Normal. A Normal gira mais rapido - e o pedido de qualidade alta e
# mais raro -, entao empate nao basta.
GANHO_MINIMO_DA_QUALIDADE = 0.15


def _linha_normal(item, rot, origem, destino, quantidade, taxa, idade_maxima,
                  ordem_na_compra, ordem_na_venda):
    """A linha de sempre: a oferta mais barata contra a venda Normal.

    Devolve (linha, None) ou (None, motivo): 'sem_compra', 'sem_venda', 'velho'."""

    preco_compra, idade_compra = mercado.ler(origem, item, rot)
    preco_venda, idade_venda = mercado.ler(destino, item, rot)

    if preco_compra is None:
        return None, 'sem_compra'

    if preco_venda is None:
        return None, 'sem_venda'

    if idade_maxima is not None and max(idade_compra, idade_venda) > idade_maxima:
        return None, 'velho'

    l = linha(item, rot, preco_compra, preco_venda, quantidade, taxa,
              ordem_na_compra, ordem_na_venda)
    l['qualidade'] = None

    return l, None


def _linha_de_qualidade(item, rot, origem, destino, quantidade, taxa,
                        idade_maxima):
    """A melhor qualidade acima da Normal para comprar, ou None.

    SO EXISTE COM OS PRECOS DA REDE: a tela mostra uma qualidade por vez, a rede
    traz as cinco. Comprar a qualidade Q custa a oferta mais barata dela na
    cidade; vende-la rende o maior pedido do Mercado Negro que ela atende - os
    de qualidade Q ou menor.

    Sempre NA HORA: uma ordem de compra pode ser preenchida por item Normal, e o
    negocio inteiro dependia da qualidade."""

    na_cidade, idade_c = mercado.ler_qualidades(origem, item, rot)
    no_negro, idade_n = mercado.ler_qualidades(destino, item, rot)

    if not na_cidade or not no_negro:
        return None

    if idade_maxima is not None and max(idade_c, idade_n) > idade_maxima:
        return None

    melhor = None

    for q in range(2, 6):

        compra = (na_cidade.get(q) or {}).get('oferta')

        pedidos = [v['pedido'] for k, v in no_negro.items()
                   if k <= q and v.get('pedido')]

        if not compra or not pedidos:
            continue

        l = linha(item, rot, compra, max(pedidos), quantidade, taxa,
                  ordem_na_compra=False, ordem_na_venda=False)
        l['qualidade'] = q

        if melhor is None or l['lucro_unitario'] > melhor['lucro_unitario']:
            melhor = l

    return melhor


def montar(catalogo, origem, destino=None, margem_minima=MARGEM_PADRAO,
           taxa=TAXA_PADRAO, idade_maxima=IDADE_MAXIMA_PADRAO,
           por_margem_bruta=False, teto=None,
           ordem_na_compra=True, ordem_na_venda=False, espacos=None,
           por_qualidade=False):
    """A lista de compras de uma cidade. Devolve (linhas, resumo).

    <catalogo> e uma sequencia de (item, rotulo, quantidade_maxima) - o que voce
    escolheu na tela de Itens. Cada tripla vira no maximo uma linha.

    Uma combinacao so entra se TIVER OS DOIS PRECOS e os dois forem recentes.
    Faltando um deles nao existe negocio para avaliar, e isso e diferente de um
    negocio ruim: o primeiro pede uma coleta, o segundo pede outro item. Por isso
    os descartes saem contados no resumo, separados por motivo - sem isso, uma
    lista vazia nao diz se voce tem que coletar de novo ou baixar a margem.

    <teto> corta a lista quando o custo acumulado passaria dele. As linhas vem
    ordenadas da melhor margem para a pior, entao o que fica de fora e sempre o
    pior negocio - e nao "o que sobrou depois que o dinheiro acabou".

    <espacos> e quantos espacos livres o inventario tem na viagem. Equipamento
    nao empilha - cada unidade ocupa um espaco - entao isto e um teto de
    UNIDADES. A linha que nao cabe inteira entra com o que cabe; dali em diante
    o resto fica de fora, sempre o pior negocio, como no teto de prata.
    """

    if destino is None:
        destino = mercado.DESTINO_PADRAO

    linhas = []
    sem_compra = 0
    sem_venda = 0
    velhos = 0
    abaixo = 0

    for item, rot, quantidade in catalogo:

        l, motivo = _linha_normal(item, rot, origem, destino, quantidade, taxa,
                                  idade_maxima, ordem_na_compra, ordem_na_venda)

        if l is not None and (l['margem_bruta'] if por_margem_bruta
                              else l['margem']) < margem_minima:
            l, motivo = None, 'abaixo'

        # A QUALIDADE SO ENTRA QUANDO PAGA BEM MAIS. Vender como Normal e o que
        # gira mais rapido; trocar isso por uma qualidade maior so vale com uma
        # folga clara de lucro por unidade.
        if por_qualidade:
            lq = _linha_de_qualidade(item, rot, origem, destino, quantidade, taxa,
                                     idade_maxima)

            if (lq is not None and lq['margem'] >= margem_minima
                    and (l is None or lq['lucro_unitario']
                         >= l['lucro_unitario'] * (1 + GANHO_MINIMO_DA_QUALIDADE))):
                linhas.append(lq)
                continue

        if l is None:
            if motivo == 'sem_compra':
                sem_compra += 1
            elif motivo == 'sem_venda':
                sem_venda += 1
            elif motivo == 'velho':
                velhos += 1
            else:
                abaixo += 1
            continue

        linhas.append(l)

    chave = 'margem_bruta' if por_margem_bruta else 'margem'
    linhas.sort(key=lambda l: l[chave], reverse=True)

    cortadas = 0

    if teto is not None:
        cabem = []
        acumulado = 0

        for l in linhas:
            if acumulado + l['custo'] > teto:
                cortadas += 1
                continue
            cabem.append(l)
            acumulado += l['custo']

        linhas = cabem

    sem_espaco = 0

    if espacos is not None:
        cabem = []
        livres = max(0, int(espacos))

        for l in linhas:
            if livres <= 0:
                sem_espaco += 1
                continue
            if l['quantidade'] > livres:
                qualidade = l.get('qualidade')
                l = linha(l['item'], l['combinacao'], l['compra'], l['venda'],
                          livres, taxa,
                          ordem_na_compra and not qualidade, ordem_na_venda)
                l['qualidade'] = qualidade
            cabem.append(l)
            livres -= l['quantidade']

        linhas = cabem

    resumo = {
        'origem': origem,
        'destino': destino,
        'linhas': len(linhas),
        'unidades': sum(l['quantidade'] for l in linhas),
        'custo': sum(l['custo'] for l in linhas),
        'receita': sum(l['receita'] for l in linhas),
        'custo_de_tabela': sum(l['custo_de_tabela'] for l in linhas),
        'receita_de_tabela': sum(l['receita_de_tabela'] for l in linhas),
        'lucro': sum(l['lucro'] for l in linhas),
        'sem_preco_de_compra': sem_compra,
        'sem_preco_de_venda': sem_venda,
        'precos_velhos': velhos,
        'abaixo_da_margem': abaixo,
        'cortadas_pelo_teto': cortadas,
        'sem_espaco': sem_espaco,
        'por_qualidade': sum(1 for l in linhas if l.get('qualidade')),
    }

    resumo['margem'] = (resumo['lucro'] / resumo['custo']) if resumo['custo'] else 0.0

    return linhas, resumo


def melhor_origem(catalogo, origens=None, **kw):
    """Roda montar() em cada cidade e devolve (cidade, linhas, resumo) da melhor.

    Qual cidade compensa hoje nao e uma pergunta de opiniao, e o lucro nao vive
    na cidade: vive na diferenca entre ela e o Mercado Negro naquele momento. Com
    as coletas na mao, a resposta e uma comparacao - e comparar seis numeros e
    mais barato que viajar ate a cidade errada.

    None quando NENHUMA cidade tem linha. Antes devolvia a primeira da lista
    mesmo vazia, e a tela mostrava "Martlock" como rota de uma cidade que nunca
    foi lida."""

    if origens is None:
        origens = mercado.ORIGENS

    melhor = None

    for cidade in origens:

        linhas, resumo = montar(catalogo, cidade, **kw)

        if not linhas:
            continue

        if melhor is None or resumo['lucro'] > melhor[2]['lucro']:
            melhor = (cidade, linhas, resumo)

    return melhor


def comparar(catalogo, origens=None, **kw):
    """O resumo de CADA cidade, da mais lucrativa para a menos.

    Serve para a tela de escolha: em vez de dizer so qual e a melhor, mostra o
    tamanho da diferenca - as vezes a segunda paga quase o mesmo e fica no
    caminho de onde voce ja esta."""

    if origens is None:
        origens = mercado.ORIGENS

    resumos = [montar(catalogo, cidade, **kw)[1] for cidade in origens]

    resumos.sort(key=lambda r: r['lucro'], reverse=True)

    return resumos

#endregion
