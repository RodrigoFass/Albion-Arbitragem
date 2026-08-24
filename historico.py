################################
#                              #
#          HISTORICO           #
#                              #
################################

# O que foi comprado e vendido, quando, a que preco.
#
#
# POR QUE ISTO EXISTE SEPARADO DO LOG.
#
# O log conta o que o bot FEZ - cliques, leituras, avisos - e serve para achar
# defeito. O historico conta o que ACONTECEU com a sua prata, e serve para
# responder uma pergunta que o log nao responde: o dia deu lucro?
#
# Sao formatos diferentes porque as perguntas sao diferentes. O log e texto para
# ler de cima a baixo uma vez; o historico e CSV, uma linha por operacao, para
# abrir na planilha e somar.
#
#
# O PRECO REGISTRADO E O QUE O JOGO COBROU, e nao o que a lista mostrava.
#
# Isto custou caro no programa antigo: o historico dizia 66.990, 66.990 e 66.991
# enquanto o jogo cobrava 66.990, 66.991 e 66.996. Cada leitura ficava uma oferta
# atrasada, e como a diferenca entre ofertas vizinhas e de poucas pratas, ela
# cabia na tolerancia e passava. O dinheiro estava certo; a contabilidade e que
# nao - e uma contabilidade errada e pior que nenhuma, porque parece certa.
#
# Por isso quem registra uma compra na hora passa o valor do DIALOGO.
#
#
# UMA LINHA POR OPERACAO, NUNCA REESCRITA. O arquivo so cresce, e cresce devagar:
# um dia intenso de operacao sao algumas centenas de linhas. Reescrever para
# "corrigir" uma linha antiga seria perder o unico registro que existe do que
# realmente aconteceu.
#
# Antes de alterar: python -m pyflakes historico.py

import csv
import os
import time

import comum

#region Configuracao

# JUNTO DOS OUTROS REGISTROS, e nao na raiz do programa.
#
# O comum ja apontava para registros/historico.csv, e a tela Painel lia de la.
# Gravar noutro lugar criava duas verdades sobre o mesmo assunto - e o sintoma
# foi imediato: o comprador escrevia num arquivo e o Painel mostrava o outro,
# vazio, sem nada denunciando.
ARQUIVO = comum.ARQUIVO_HISTORICO

# A ordem das colunas. Mudar isto quebra os arquivos ja gravados, entao coluna
# nova entra NO FIM - quem le por nome nao se importa, e quem abre na planilha ve
# a coluna nova vazia nas linhas velhas em vez de tudo deslocado.
COLUNAS = ['quando', 'operacao', 'mercado', 'item', 'combinacao', 'unidades',
           'preco', 'total', 'modo', 'observacao']

COMPRA = 'compra'
VENDA = 'venda'

#endregion

#region Gravar


def registrar(operacao, mercado, item, combinacao, unidades, preco,
              modo='', observacao='', quando=None):
    """Guarda uma operacao. Devolve (ok, erro).

    <preco> e por unidade e E O QUE O JOGO COBROU - ver o cabecalho.
    <modo> distingue 'na hora' de 'ordem', que tem taxas diferentes.

    NUNCA LEVANTA. Uma falha ao gravar o historico nao pode derrubar uma compra
    que ja aconteceu: a prata ja saiu, e perder o registro e ruim, mas abortar o
    laco no meio deixaria o resto da lista por comprar por causa de um arquivo."""

    linha = {
        'quando': time.strftime('%Y-%m-%d %H:%M:%S',
                                time.localtime(quando or time.time())),
        'operacao': operacao,
        'mercado': mercado or '',
        'item': item,
        'combinacao': combinacao or '',
        'unidades': int(unidades),
        'preco': int(preco),
        'total': int(preco) * int(unidades),
        'modo': modo,
        'observacao': observacao,
    }

    try:
        novo = not os.path.exists(ARQUIVO)

        with open(ARQUIVO, 'a', encoding='utf-8', newline='') as f:

            escritor = csv.DictWriter(f, fieldnames=COLUNAS)

            if novo:
                escritor.writeheader()

            escritor.writerow(linha)

    except Exception as e:
        comum.contar('historico_nao_gravou')
        return False, str(e)

    comum.contar('operacoes_registradas')

    return True, ''


def comprou(mercado, item, combinacao, unidades, preco, modo='', observacao=''):
    return registrar(COMPRA, mercado, item, combinacao, unidades, preco,
                     modo, observacao)


def vendeu(mercado, item, combinacao, unidades, preco, modo='', observacao=''):
    return registrar(VENDA, mercado, item, combinacao, unidades, preco,
                     modo, observacao)

#endregion

#region Ler


def ler(desde=None):
    """As operacoes gravadas, mais novas por ultimo. Lista de dicionarios.

    <desde> em segundos desde a epoca - so o que veio depois. Arquivo ausente
    devolve lista vazia: no primeiro uso ele nao existe mesmo."""

    if not os.path.exists(ARQUIVO):
        return []

    try:
        with open(ARQUIVO, encoding='utf-8', newline='') as f:
            linhas = list(csv.DictReader(f))

    except Exception:
        comum.contar('historico_nao_leu')
        return []

    saida = []

    for linha in linhas:

        for chave in ('unidades', 'preco', 'total'):
            try:
                linha[chave] = int(linha.get(chave) or 0)
            except (TypeError, ValueError):
                linha[chave] = 0

        linha['momento'] = _momento(linha.get('quando'))

        if desde is not None and linha['momento'] < desde:
            continue

        saida.append(linha)

    return saida


def _momento(texto):
    """O 'quando' de volta em segundos. 0 quando nao der para ler."""

    try:
        return time.mktime(time.strptime(texto, '%Y-%m-%d %H:%M:%S'))
    except (TypeError, ValueError):
        return 0.0


def resumo(desde=None):
    """Quanto entrou, quanto saiu e o que sobrou.

    O LUCRO AQUI E REALIZADO, e nao previsto. A tela de compra mostra o lucro que
    a lista PROMETE; este e o que de fato aconteceu, e a diferenca entre os dois
    e a unica medida honesta de quanto o bot acerta."""

    operacoes = ler(desde)

    gasto = sum(o['total'] for o in operacoes if o['operacao'] == COMPRA)
    recebido = sum(o['total'] for o in operacoes if o['operacao'] == VENDA)

    return {
        'operacoes': len(operacoes),
        'compras': sum(1 for o in operacoes if o['operacao'] == COMPRA),
        'vendas': sum(1 for o in operacoes if o['operacao'] == VENDA),
        'unidades_compradas': sum(o['unidades'] for o in operacoes
                                  if o['operacao'] == COMPRA),
        'gasto': gasto,
        'recebido': recebido,
        'saldo': recebido - gasto,
    }


def do_dia():
    """O resumo de hoje, da meia-noite para ca."""

    agora = time.localtime()

    meia_noite = time.mktime((agora.tm_year, agora.tm_mon, agora.tm_mday,
                              0, 0, 0, 0, 0, -1))

    return resumo(meia_noite)

#endregion
