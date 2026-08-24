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

import ajustes
import comum
import compra
import historico
import lucro
import mercado
import menu
from comum import relatar

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

        teto_do_preco = compra.preco_maximo(linha['venda'], margem, taxa)

        if cobrado > teto_do_preco:
            return False, (f'{comum.fmt(cobrado)} passa do teto de '
                           f'{comum.fmt(teto_do_preco)} que ainda paga a margem')

        if teto_de_prata and gasto_ate_agora + cobrado > teto_de_prata:
            return False, (f'{comum.fmt(cobrado)} estoura o limite de gasto '
                           f'({comum.fmt(teto_de_prata)})')

        return True, ''

    return julgar


def comprar_linha(linha, origem, margem, taxa, gasto_ate_agora=0,
                  teto_de_prata=None, de_verdade=True):
    """Compra uma combinacao. Devolve o resultado, sem levantar.

    O caminho e escolhido pelo Smart Buy: ordem quando ha volume e o item nao e
    caro, compra na hora no resto. Os dois passam pelas mesmas barreiras."""

    item = linha['item']
    rot = linha['combinacao']

    saida = {'item': item, 'combinacao': rot, 'unidades': 0, 'gasto': 0,
             'modo': '', 'motivo': ''}

    ok, motivo = menu.selecionar(item)

    if not ok:
        saida['motivo'] = motivo
        comum.contar('itens_sem_menu')
        return saida

    # O LIVRO DE AGORA, e nao o da varredura. A lista foi montada com precos de
    # antes, e o mercado nao esperou.
    if not compra.abrir_painel():
        saida['motivo'] = 'o painel do item nao abriu'
        comum.contar('itens_sem_painel')
        return saida

    try:
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

        plano, modo, motivo = compra.decidir(
            ofertas, linha['venda'], margem, quanto, taxa, travado,
            conf.get('ordem_a_partir_de'), conf.get('na_hora_acima_de'))

        if plano is None:
            saida['motivo'] = motivo
            comum.contar('linhas_sem_plano')
            return saida

        saida['modo'] = modo

        if not de_verdade:
            saida['unidades'] = plano['unidades']
            saida['gasto'] = plano['custo']
            saida['motivo'] = 'simulacao'
            return saida

        if modo == 'ordem':
            _por_ordem(saida, plano, linha, origem)
        else:
            _na_hora(saida, plano, linha, origem, margem, taxa,
                     gasto_ate_agora, teto_de_prata)

    finally:
        compra.fechar_painel()

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
                              pago or 0, modo='na hora')

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
        import catalogo as cat
        linhas, _ = lucro.montar(cat.para_calcular(), origem, destino,
                                 margem_minima=margem, taxa=taxa,
                                 teto=teto_de_prata)

    if not linhas:
        return {'erro': 'nao ha nada que pague a margem'}

    inicio = time.monotonic()

    gasto = 0
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
                              teto_de_prata, de_verdade)

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
