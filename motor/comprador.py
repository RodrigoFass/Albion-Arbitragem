################################
#                              #
#          COMPRADOR           #
#                              #
################################

# Percorre a lista de compras e compra. E o laco que faltava.
#
# O compra.py ja sabia planejar uma linha e criar uma ordem; o lucro.py ja sabia
# montar a lista. Entre os dois nao havia nada, e a tela dizia isso em voz alta:
# "a lista ja sai certa, mas o laco que percorre e compra ainda nao foi escrito".
#
#
# CADA LINHA E UMA DECISAO, E NAO UMA EXECUCAO.
#
# A lista da tela foi montada com precos LIDOS ANTES - minutos ou horas antes. O
# mercado nao esperou. Entao a linha nao diz "compre 8 a 66.990": ela diz "vale a
# pena ir olhar 8 unidades desta combinacao". Chegando la, o livro e lido de
# novo, o plano e refeito com o que existe AGORA, e so entao se decide.
#
# Foi assim que o programa antigo perdeu dinheiro: ele confiou na lista.
#
#
# TRES BARREIRAS ANTES DE CADA PRATA SAIR, da mais barata para a mais cara:
#
#     1. o livro relido        - a oferta ainda paga a margem?
#     2. o teto de gasto       - ainda ha prata reservada para esta viagem?
#     3. o dialogo do jogo     - o valor que ele VAI COBRAR ainda vale?
#
# A terceira e a unica que nao passa pela nossa aritmetica nem pelo nosso OCR
# duas vezes: e o proprio jogo dizendo o numero. Por isso ela e a ultima, e por
# isso ela pode reverter as outras duas.
#
#
# PARAR NO MEIO TEM QUE DEIXAR TUDO COERENTE. Cada compra e registrada no
# historico ASSIM QUE ACONTECE, e nao no fim: o F12 no item quarenta nao pode
# apagar as trinta e nove compras que ja custaram prata.
#
# Antes de alterar: python -m pyflakes comprador.py

import time

from motor import ajustes
from motor import comum
from motor import compra
from motor import coordenadas as cd
from motor import escuta
from motor import filtros
from motor import historico
from motor import lucro
from motor import mercado
from motor import menu
from motor.comum import relatar

#region Configuracao

# Itens seguidos com falha que fazem a compra parar.
#
# Comprar e diferente de varrer: varrendo, um item que falha custa uma leitura
# perdida; comprando, um item que falha pode ser a tela inteira em outro lugar -
# e o clique seguinte cai em cima de qualquer coisa que estiver ali.
MAX_ITENS_COM_ERRO_SEGUIDOS = 3

# Quanto do teto de gasto pode sobrar sem valer a pena continuar.
#
# Com 900 de prata restante nao ha o que comprar, e continuar a lista so gasta
# tempo abrindo item por item para descobrir isso uma vez por linha.
SOBRA_MINIMA = 1_000

#endregion

#region Uma linha


def _aceitar(linha, plano, gasto_ate_agora, teto_de_prata, margem, taxa):
    """Devolve a funcao que julga o preco REAL que o dialogo mostrar.

    Ela responde a pergunta certa: "este valor, que e o verdadeiro, ainda vale a
    compra?" - e nao "bate com o que eu li?". As duas contas sao as mesmas que
    decidiram a linha, agora sobre o numero certo."""

    def julgar(cobrado):

        teto_do_preco = compra.preco_maximo(
            linha['venda'], margem, taxa,
            ordem_na_venda=linha.get('venda_por_ordem', False))

        if cobrado > teto_do_preco:
            return False, (f'{comum.fmt(cobrado)} passa do teto de '
                           f'{comum.fmt(teto_do_preco)} que ainda paga a margem')

        if teto_de_prata and gasto_ate_agora + cobrado > teto_de_prata:
            return False, (f'{comum.fmt(cobrado)} estoura o limite de gasto '
                           f'({comum.fmt(teto_de_prata)})')

        return True, ''

    return julgar


def comprar_linha(linha, origem, margem, taxa, gasto_ate_agora=0,
                  teto_de_prata=None, de_verdade=True, sondar=False):
    """Compra uma combinacao. Devolve o resultado, sem levantar.

    O caminho e escolhido pelo Smart Buy: ordem quando ha volume e o item nao e
    caro, compra na hora no resto. Os dois passam pelas mesmas barreiras.

    <sondar> espera o livro pela rede mesmo sem pacote recente - o teste da rede
    na primeira linha. O resultado traz 'pela_rede' quando o livro foi pedido."""

    item = linha['item']
    rot = linha['combinacao']

    saida = {'item': item, 'combinacao': rot, 'unidades': 0, 'gasto': 0,
             'modo': '', 'motivo': ''}

    partes = mercado.partes(rot)

    if partes is None:
        saida['motivo'] = f'combinacao "{rot}" desconhecida'
        return saida

    # A LINHA POR QUALIDADE SO COMPRA COM AS DUAS GARANTIAS: o filtro de
    # qualidade medido no calibrador (a posicao de fabrica e palpite) e o livro
    # vindo da rede, que diz a qualidade de cada oferta. Sem elas, o clique
    # poderia comprar outra qualidade achando que e esta.
    qualidade = linha.get('qualidade')

    if qualidade:
        if not cd.calibrado('CMP_BARRA_QUAL', 'CMP_QUAL_TOPO'):
            saida['motivo'] = ('comprar por qualidade precisa do filtro de '
                               'qualidade calibrado (Ajustes > Calibrar)')
            return saida

        if not escuta.ativa():
            saida['motivo'] = 'comprar por qualidade precisa da leitura pela rede'
            return saida

    ok, motivo = menu.selecionar(item)

    if not ok:
        saida['motivo'] = motivo
        comum.contar('itens_sem_menu')
        return saida

    # A COMBINACAO DA LINHA, ANTES DE ABRIR O PAINEL. O menu deixa a lista com o
    # item em TODOS os graus e encantamentos, e o painel abre o primeiro da
    # lista. Sem os filtros, o livro lido - e a compra - seriam de uma
    # combinacao qualquer, julgada pelo preco de venda de outra: um T4.0 barato
    # parecendo negocio de ouro contra a venda de um T7.1.
    grau, ench = partes
    painel = False

    try:
        aplicados = [filtros.encantamento(ench)]

        # O LIVRO DE AGORA, e nao o da varredura. A lista foi montada com precos
        # de antes, e o mercado nao esperou. A marca vem ANTES DA ULTIMA TROCA DE
        # FILTRO: e ela que faz o jogo pedir as ofertas desta combinacao, e so
        # vale pacote que chegou depois dela.
        filtrado_em = escuta.marca()
        aplicados.append(filtros.grau(grau))

        if qualidade:
            filtrado_em = escuta.marca()
            aplicados.append(filtros.qualidade(qualidade))

        # FILTRO QUE NAO ENTROU E COMPRA DE OUTRA COMBINACAO: o livro na tela
        # seria o do grau de antes, julgado pela venda deste
        if filtros.NAO_APLICADO in aplicados:
            saida['motivo'] = 'o filtro de grau ou encantamento nao foi aplicado'
            comum.contar('linhas_sem_filtro')
            return saida

        # PELA REDE, SEM PAINEL. A lista filtrada ja fez o servidor mandar as
        # ofertas desta combinacao, exatas e com quantidade. Antes o bot abria o
        # painel do item clicando no NOME - posicao derivada, nunca medida - e
        # quando ele nao abria a linha parava ali, sem nunca chegar ao Buy.
        ofertas = escuta.ofertas(
            origem, item, rot, desde=filtrado_em, qualidade=qualidade or None,
            prazo=escuta.ESPERA_SONDA if sondar else escuta.ESPERA,
            mesmo_calado=sondar)

        saida['pela_rede'] = bool(ofertas)

        if ofertas:
            comum.contar('livros_pela_rede')

        elif qualidade:
            # so a rede diz a qualidade de cada oferta: sem o pacote, nao compra
            saida['motivo'] = 'o livro dessa qualidade nao chegou pela rede'
            return saida

        else:
            # SEM A REDE o livro sai da tela, e ele esta no painel do item
            if not compra.abrir_painel():
                saida['motivo'] = ('o painel do item nao abriu - e sem a leitura '
                                   'pela rede o livro so sai dele')
                comum.contar('itens_sem_painel')
                return saida

            painel = True
            ofertas = compra.ler_livro()

        if not ofertas:
            saida['motivo'] = ('ninguem vendendo' if compra.livro_vazio()
                               else 'nao deu para ler o livro')
            comum.contar('livros_vazios')
            return saida

        quanto = linha['quantidade']

        if teto_de_prata:
            sobra = max(0, teto_de_prata - gasto_ate_agora)
            quanto = min(quanto, _cabem(ofertas, sobra))

        conf = ajustes.atuais()

        travado = {'ordem': 'ordem', 'na_hora': 'na hora'}.get(
            conf.get('modo_de_compra'))

        # por qualidade, sempre na hora: uma ordem de compra seria preenchida
        # por qualquer qualidade, e o negocio dependia desta
        if qualidade:
            travado = 'na hora'

        plano, modo, motivo = compra.decidir(
            ofertas, linha['venda'], margem, quanto, taxa, travado,
            conf.get('ordem_a_partir_de'), conf.get('na_hora_acima_de'),
            ordem_na_venda=linha.get('venda_por_ordem', False))

        if plano is None:
            saida['motivo'] = motivo
            comum.contar('linhas_sem_plano')
            return saida

        # A ORDEM PRECISA DO PAINEL - e la que ficam o "Pedido de compra", a
        # quantidade e o preco. A compra na hora nao: ela sai da propria lista.
        # Sem o painel, a linha que ia por ordem e comprada na hora, unidade por
        # unidade e com o dialogo conferido - a ordem so poupava cliques.
        if modo == 'ordem' and not painel:

            if compra.abrir_painel():
                painel = True

            elif travado == 'ordem':
                saida['motivo'] = ('travado em ordem, e o painel do item nao '
                                   'abriu para criar a ordem')
                comum.contar('itens_sem_painel')
                return saida

            else:
                comum.contar('ordem_virou_na_hora')
                modo = 'na hora'

        saida['modo'] = modo

        if not de_verdade:
            saida['unidades'] = plano['unidades']
            saida['gasto'] = plano['custo']
            saida['motivo'] = 'simulacao'
            return saida

        if modo == 'ordem':
            _por_ordem(saida, plano, linha, origem)
        else:
            # A COMPRA NA HORA COMECA DA LISTA: o primeiro clique e o Buy da
            # linha da oferta. Com o painel do item aberto por cima, esse clique
            # caia no livro de ofertas do painel e nada acontecia.
            if painel:
                compra.fechar_painel()
                painel = False

            _na_hora(saida, plano, linha, origem, margem, taxa,
                     gasto_ate_agora, teto_de_prata)

    finally:
        if painel:
            compra.fechar_painel()
        # o jogo guarda o filtro: a linha seguinte nasceria nesta combinacao -
        # e a qualidade volta a "Todas" explicitamente, sem contar que o botao
        # de limpar tambem a zere
        if qualidade:
            filtros.qualidade(0)
        filtros.limpar()

    return saida


def _cabem(ofertas, sobra):
    """Quantas unidades cabem na prata que sobrou, da mais barata para a cara."""

    unidades = 0

    for preco, quantidade in sorted(ofertas):

        if preco <= 0:
            continue

        possiveis = int(sobra // preco)

        if possiveis <= 0:
            break

        leva = min(quantidade, possiveis)
        unidades += leva
        sobra -= leva * preco

    return unidades


def _por_ordem(saida, plano, linha, origem):
    """Uma ordem casa com todas as ofertas naquele preco de uma vez."""

    ok, motivo = compra.criar_ordem(plano)

    if not ok:
        saida['motivo'] = motivo
        return

    saida['unidades'] = plano['unidades']
    saida['gasto'] = plano['custo']

    # O CUSTO DA ORDEM E ESTIMADO, e o historico diz isso. O jogo cobra o preco
    # de quem vende, oferta por oferta, e nao ha dialogo mostrando o total - o
    # numero exato so apareceria no extrato do jogo. Registrar o preco medio
    # previsto e melhor que nao registrar, desde que fique marcado como previsto.
    historico.comprou(origem, linha['item'], linha['combinacao'],
                      plano['unidades'],
                      plano['custo'] // max(1, plano['unidades']),
                      modo='ordem', observacao='custo previsto')


def _na_hora(saida, plano, linha, origem, margem, taxa, gasto_ate_agora,
             teto_de_prata):
    """Tres cliques por unidade, com o dialogo conferido em cada uma."""

    gasto = 0
    levadas = 0

    for _ in range(plano['unidades']):

        if comum.deve_parar():
            saida['motivo'] = 'parado no meio'
            break

        julgar = _aceitar(linha, plano, gasto_ate_agora + gasto, teto_de_prata,
                          margem, taxa)

        situacao, pago, motivo = compra.comprar_uma(plano['preco'], julgar)

        if situacao == 'comprou':

            levadas += 1
            gasto += pago or 0

            historico.comprou(origem, linha['item'], linha['combinacao'], 1,
                              pago or 0, modo='na hora',
                              qualidade=linha.get('qualidade'))

            comum.avisar(f'{linha["item"]} {linha["combinacao"]}',
                         comum.fmt(pago), 'ok')

            continue

        # RECUSA NAO E FALHA, e nao adianta insistir: a proxima oferta da fila e
        # mais cara que esta, entao se esta ja nao paga, nenhuma abaixo dela paga.
        saida['motivo'] = motivo
        break

    saida['unidades'] = levadas
    saida['gasto'] = gasto

#endregion

#region A lista inteira


def comprar(origem, linhas=None, margem=None, taxa=None, teto_de_prata=None,
            de_verdade=True, destino=None):
    """Percorre a lista de compras e compra. Devolve o resumo.

    <linhas> pronta, ou None para montar aqui a partir do catalogo e dos precos.
    <teto_de_prata> None para sem limite.

    NAO LEVANTA POR LINHA. Um item que nao abre, um livro que nao le, uma ordem
    que a tela recusa - cada um custa uma linha, e a lista continua. So a
    sequencia de erros faz parar, porque ai o problema nao e a linha: e a tela."""

    conf = ajustes.atuais()

    margem = conf['margem'] if margem is None else margem
    taxa = conf['taxa'] if taxa is None else taxa
    teto_de_prata = conf.get('teto') if teto_de_prata is None else teto_de_prata

    if origem not in mercado.MERCADOS:
        return {'erro': f'"{origem}" nao e um mercado conhecido'}

    problemas = comum.sem_foco()

    if problemas:
        relatar('ABORTADO antes de tocar no mouse:')
        for p in problemas:
            relatar(f'  - {p}')
        return {'erro': 'jogo sem foco'}

    if linhas is None:
        from motor import catalogo as cat
        linhas, _ = lucro.montar(cat.para_calcular(), origem, destino,
                                 margem_minima=margem, taxa=taxa,
                                 teto=teto_de_prata)

    if not linhas:
        return {'erro': 'nao ha nada que pague a margem'}

    inicio = time.monotonic()

    # cliente de pe e calado: a primeira linha testa a rede
    sondar = escuta.ligada() and not escuta.ativa()

    gasto = 0
    previsto = 0
    unidades = 0
    feitas = 0
    com_erro = []
    erros_seguidos = 0

    relatar('')
    relatar(f'Comprando {len(linhas)} linhas em "{origem}"'
            + (f', ate {comum.fmt(teto_de_prata)} de prata'
               if teto_de_prata else ''))
    relatar('')

    for n, linha in enumerate(linhas, start=1):

        if comum.deve_parar():
            relatar('')
            relatar(f'>>> parado na linha {n} de {len(linhas)} <<<')
            break

        # F11 PARA ENTRE UMA LINHA E OUTRA, nunca no meio de uma: pausar com o
        # painel aberto e o dialogo na tela deixaria uma compra pela metade.
        if comum.pausado.is_set():

            _, pode_seguir = comum.aguardar_retomada(
                (f'parado antes da linha {n} de {len(linhas)}',
                 f'{comum.fmt(gasto)} gastos ate aqui'))

            if not pode_seguir:
                relatar('>>> encerrado durante a pausa <<<')
                break

        if comum.pular_pedido.is_set():
            comum.pular_pedido.clear()
            relatar('      PULADO a pedido')
            continue

        if not comum.jogo_em_foco():
            relatar('')
            relatar(f'PARANDO na linha {n} - o jogo saiu de primeiro plano.')
            break

        if teto_de_prata and teto_de_prata - gasto < SOBRA_MINIMA:
            relatar('')
            relatar(f'LIMITE DE GASTO alcancado: {comum.fmt(gasto)} de '
                    f'{comum.fmt(teto_de_prata)}.')
            break

        relatar(f'[{n}/{len(linhas)}] {linha["item"]} {linha["combinacao"]}  '
                f'ate {linha["quantidade"]}x, margem prevista '
                f'{linha["margem"] * 100:.0f}%')

        comum.progresso(n, len(linhas), f'{linha["item"]} {linha["combinacao"]}')

        try:
            r = comprar_linha(linha, origem, margem, taxa, gasto,
                              teto_de_prata, de_verdade, sondar=sondar)

            # o teste e um so por compra: a primeira linha que pediu o livro
            # diz se a rede responde, e o resto segue com o que ela disse
            if sondar and 'pela_rede' in r:
                sondar = False
                relatar('      a rede respondeu: livros pelos pacotes'
                        if r['pela_rede'] else escuta.AVISO_SEM_REDE)

        except comum.Abortado:
            relatar('')
            relatar(f'>>> F12 - parado em "{linha["item"]}" <<<')
            break

        except Exception as e:
            com_erro.append(linha['item'])
            erros_seguidos += 1
            relatar(f'      ERRO nesta linha - seguindo: {e}')

            if erros_seguidos >= MAX_ITENS_COM_ERRO_SEGUIDOS:
                relatar('')
                relatar(f'PARANDO: {MAX_ITENS_COM_ERRO_SEGUIDOS} linhas '
                        f'seguidas falharam. Confira a tela do jogo.')
                break

            continue

        erros_seguidos = 0

        if r['unidades']:
            feitas += 1
            unidades += r['unidades']
            gasto += r['gasto']
            # o lucro que a lista prometia para o que foi de fato comprado
            previsto += r['gasto'] * linha.get('margem', 0)
            comum.placar(gasto=gasto, previsto=int(previsto), unidades=unidades)
            relatar(f'      {r["unidades"]}x por {comum.fmt(r["gasto"])} '
                    f'({r["modo"]})')
        else:
            relatar(f'      nada: {r["motivo"]}')

    decorrido = time.monotonic() - inicio

    resumo = {
        'linhas': len(linhas),
        'linhas_compradas': feitas,
        'unidades': unidades,
        'gasto': gasto,
        'com_erro': com_erro,
        'minutos': decorrido / 60,
        'contadores': comum.contadores(),
    }

    _relatar_resumo(resumo, origem, teto_de_prata)

    return resumo


def _relatar_resumo(r, origem, teto_de_prata):

    relatar('')
    relatar(f'{r["linhas_compradas"]} de {r["linhas"]} linhas, '
            f'{r["unidades"]} unidades, {comum.fmt(r["gasto"])} de prata '
            f'em {r["minutos"]:.0f} min')

    if teto_de_prata:
        relatar(f'  limite: {comum.fmt(r["gasto"])} de '
                f'{comum.fmt(teto_de_prata)}')

    if r['com_erro']:
        relatar(f'  {len(r["com_erro"])} linhas com erro: '
                + ', '.join(r['com_erro'][:6]))

    do_dia = historico.do_dia()

    relatar(f'  hoje: {do_dia["compras"]} compras, '
            f'{comum.fmt(do_dia["gasto"])} gastos, '
            f'{comum.fmt(do_dia["recebido"])} recebidos')

#endregion
