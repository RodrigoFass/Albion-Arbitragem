################################
#                              #
#          PLANILHA            #
#                              #
################################

# A Tabela-BM.xlsx, carregada UMA VEZ para o programa inteiro.
#
# Antes cada bot tinha os seus proprios `book` e `sheet`, carregados de forma
# independente. Alem do desperdicio de manter duas copias do mesmo arquivo na
# memoria, as duas podiam discordar: depois de uma varredura do Atualizar, o
# livro do Comprar continuava sendo o antigo ate alguem lembrar de recarregar - e
# decidir compra com preco anterior a varredura gasta prata em cima de dado
# velho. A correcao existia, mas dependia de lembrar dela em cada novo ponto de
# entrada.
#
# A recarga acontece quando o ARQUIVO MUDA no disco, nao a cada pedido: montar o
# painel de um bot chamava load_workbook na thread da interface, que ficava
# congelada enquanto isso. Comparar (mtime, tamanho) da a mesma garantia de
# frescor de graca.
#
# Antes de alterar: python -m pyflakes planilha.py

import os
import re
import shutil
import time

import openpyxl

import comum

ARQUIVO = os.path.join(comum.PASTA, 'Tabela-BM.xlsx')

PASTA_BACKUP = os.path.join(comum.PASTA, 'backups')
MAX_BACKUPS = 5

_estado = {
    'book': None,
    'assinatura': None,      # (mtime_ns, tamanho) do arquivo que esta na memoria
    'backup_da_execucao': False,
}


def _assinatura_do_arquivo():

    try:
        st = os.stat(ARQUIVO)
        return st.st_mtime_ns, st.st_size
    except OSError:
        return None


def carregar(forcar=False):
    """Carrega a planilha se ela mudou no disco. Devolve (ok, mensagem).

    Devolve erro em vez de levantar SystemExit: no app grafico isso derrubaria a
    janela inteira em vez de mostrar uma mensagem.

    data_only fica em False de proposito. E das FORMULAS que o bot Comprar extrai
    as margens, e com data_only=True viriam os valores em cache, que estao vazios
    depois de cada varredura do Atualizar - foram 494 de 494 na medicao, porque o
    openpyxl grava formula mas nao calcula o resultado."""

    if not os.path.isfile(ARQUIVO):
        _estado['book'] = None
        return False, (f'Planilha nao encontrada:\n{ARQUIVO}\n\n'
                       f'Ela precisa ficar na mesma pasta do programa.')

    agora = _assinatura_do_arquivo()

    if not forcar and _estado['book'] is not None and _estado['assinatura'] == agora:
        return True, ''

    try:
        book = openpyxl.load_workbook(ARQUIVO)
    except Exception as e:
        return False, (f'Nao foi possivel abrir {os.path.basename(ARQUIVO)}: {e}\n'
                       f'Se ela estiver corrompida, ha copias em backups/.')

    if not book.sheetnames:
        return False, f'A planilha {os.path.basename(ARQUIVO)} nao tem nenhuma aba.'

    _estado['book'] = book
    _estado['assinatura'] = agora

    return True, ''


def carregada():
    return _estado['book'] is not None


def livro():
    return _estado['book']


def abas():
    """Nomes das abas. Lista vazia se a planilha nao foi carregada."""

    book = _estado['book']

    return list(book.sheetnames) if book is not None else []


def folha(pagina):
    """A folha pelo indice (0-based) ou pelo nome."""

    book = _estado['book']

    if book is None:
        return None

    if isinstance(pagina, int):
        nomes = book.sheetnames
        if not (0 <= pagina < len(nomes)):
            return None
        return book[nomes[pagina]]

    return book[pagina]


def nome_da_aba(pagina):

    nomes = abas()

    return nomes[pagina] if 0 <= pagina < len(nomes) else ''

#region Gravacao


def novo_ciclo():
    """Marca o inicio de uma execucao. Chamar antes de cada varredura.

    Existe por causa de um bug de perda de dado: o backup era feito uma vez por
    PROCESSO. No terminal isso era correto, porque uma execucao do script era um
    processo. No aplicativo a janela fica aberta o dia todo, entao a segunda
    varredura em diante gravava por cima da planilha sem nenhuma copia recente -
    a que existia em backups/ era de antes da primeira."""

    _estado['backup_da_execucao'] = False


def _backup():
    """Copia a planilha uma vez por execucao, antes da primeira gravacao.

    O bot reescreve o arquivo a cada item. Sem uma copia intacta, um erro de
    logica que grave valores errados em massa nao tem volta."""

    if _estado['backup_da_execucao']:
        return

    _estado['backup_da_execucao'] = True

    try:
        os.makedirs(PASTA_BACKUP, exist_ok=True)

        destino = os.path.join(
            PASTA_BACKUP, f'Tabela-BM_{time.strftime("%Y%m%d-%H%M%S")}.xlsx')

        shutil.copy2(ARQUIVO, destino)

        # mantem apenas os MAX_BACKUPS mais recentes; o nome comeca com a data,
        # entao a ordem alfabetica e a cronologica
        antigos = sorted(f for f in os.listdir(PASTA_BACKUP) if f.endswith('.xlsx'))
        for f in antigos[:-MAX_BACKUPS]:
            os.remove(os.path.join(PASTA_BACKUP, f))

        comum.relatar(f'  backup da execucao: backups/{os.path.basename(destino)}')

    except Exception as e:
        comum.relatar(f'  AVISO: nao deu para fazer o backup da planilha ({e})')


def salvar():
    """Grava a planilha de forma atomica.

    Escreve num arquivo temporario e so entao troca pelo original com os.replace,
    que e atomico no mesmo volume. Uma interrupcao no meio da escrita deixa o
    original intacto, em vez de um .xlsx truncado.

    Enquanto grava, o F12 fica retido: o openpyxl escreve o .xlsx como um ZIP, e
    matar o processo no meio deixa o arquivo truncado. Como o bot grava a cada
    item, a janela de exposicao seria grande."""

    book = _estado['book']

    if book is None:
        raise RuntimeError('Planilha nao carregada - nada a gravar.')

    _backup()

    comum.secao_critica.set()

    temporario = ARQUIVO + '.tmp'

    try:
        with comum.cronometro('gravacao'):
            book.save(temporario)
            os.replace(temporario, ARQUIVO)

    except PermissionError as e:
        raise RuntimeError(
            f'Sem permissao para gravar a planilha ({e}). '
            f'Feche o {os.path.basename(ARQUIVO)} no Excel e rode de novo.') from e

    finally:
        if os.path.exists(temporario):
            try:
                os.remove(temporario)
            except OSError:
                pass
        comum.secao_critica.clear()

    # o que esta em memoria agora E o que esta no disco: sem atualizar a
    # assinatura, o proximo carregar() releria o arquivo que acabamos de escrever
    _estado['assinatura'] = _assinatura_do_arquivo()

#endregion

#region Leitura


def validar_colunas(folha, rotulos, primeira, bloco=''):
    """Confere os rotulos da linha 1 contra a ordem esperada. Devolve problemas.

    O bot Atualizar grava a combinacao i na coluna B+i, e o bot Comprar le a meta
    da coluna P+i para a MESMA combinacao i. Essa correspondencia e um contrato
    entre os dois que nada garantia: reordenar uma lista e nao a outra
    compararia o preco de um grau com a meta de outro, em silencio."""

    problemas = []

    for i, esperado in enumerate(rotulos):

        coluna = primeira + i
        rotulo = folha.cell(row=1, column=coluna).value
        lido = str(rotulo).replace(' ', '') if rotulo is not None else ''

        if lido != esperado:
            onde = f'coluna {coluna}' + (f' ({bloco})' if bloco else '')
            problemas.append(
                f'{onde}: planilha diz {rotulo!r}, o codigo espera {esperado}')

    return problemas


# --- Colunas -------------------------------------------------------------
# O layout da Tabela-BM.xlsx, num lugar so:
#
#   A       ITENS       nome em ingles, para voce ler
#   B..N    13 precos escaneados
#   O       vazio, separando os dois blocos
#   P..AB   13 formulas de meta
#   AC      ITENS       nome de BUSCA, em portugues
#   AD      T8/Name     nome alternativo do T8 (artefatos tem nome proprio)
#   AE      Tiers       grau em que a lista do dropdown comeca
#   AF      Atualizado  quando esta linha foi escaneada  <- acrescentado
#
# O nome de busca e em portugues e termina em "do" por um motivo pratico: o
# jogo ordena a busca alfabeticamente, e procurar "Broadsword" as vezes trazia
# outro item na frente. "Espada Larga do" nao tem esse problema.
COL_NOME_INGLES = 1
COL_PRECO       = 2
COL_META        = 16
COL_BUSCA       = 29
COL_NOME_T8     = 30
COL_TIER        = 31
COL_ATUALIZADO  = 32

ROTULO_ATUALIZADO = 'Atualizado'


def marcar_atualizada(folha, linha, quando=None):
    """Carimba a data em que esta linha foi escaneada.

    Uma celula preenchida nao dizia QUANDO foi preenchida, e comprar com base num
    preco de tres dias atras e decidir com dado velho - a meta saia com a mesma
    confianca para um preco de dez minutos e para um da semana passada.

    O carimbo e por LINHA e nao por celula. A varredura escaneia a linha inteira
    de uma vez, e treze colunas de data para treze de preco dobrariam a largura da
    planilha para responder a mesma pergunta. A repescagem, que preenche celulas
    soltas, tambem carimba - ali a data passa a valer pela celula mais recente, e
    e o lado seguro do erro: uma linha parece mais nova do que a parte mais velha
    dela, nunca mais velha do que e."""

    if folha.cell(row=1, column=COL_ATUALIZADO).value != ROTULO_ATUALIZADO:
        folha.cell(row=1, column=COL_ATUALIZADO).value = ROTULO_ATUALIZADO

    folha.cell(row=linha, column=COL_ATUALIZADO).value = (
        quando or time.strftime('%Y-%m-%d %H:%M'))


def _para_data(valor):
    """A data de uma celula, como struct_time. None se nao der para ler."""

    if valor is None:
        return None

    if hasattr(valor, 'timetuple'):
        return valor.timetuple()

    for formato in ('%Y-%m-%d %H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return time.strptime(str(valor).strip(), formato)
        except ValueError:
            continue

    return None


def idade_em_dias(folha, linha):
    """Ha quantos dias esta linha foi escaneada. None se nunca foi carimbada."""

    quando = _para_data(folha.cell(row=linha, column=COL_ATUALIZADO).value)

    if quando is None:
        return None

    return max(0.0, (time.time() - time.mktime(quando)) / 86400)


def idade_da_aba(folha, linhas):
    """(mais_nova, mais_velha, quantas_sem_data) em dias, para o resumo."""

    idades = []
    sem_data = 0

    for linha in linhas:
        dias = idade_em_dias(folha, linha)
        if dias is None:
            sem_data += 1
        else:
            idades.append(dias)

    if not idades:
        return None, None, sem_data

    return min(idades), max(idades), sem_data


def texto_de_idade(dias):
    """'ha 3 dias', 'hoje', '-'. Curto o bastante para caber numa coluna."""

    if dias is None:
        return '-'

    if dias < 1 / 24:
        return 'agora'

    if dias < 1:
        return f'ha {int(dias * 24)}h'

    if dias < 2:
        return 'ontem'

    return f'ha {int(dias)} dias'

#endregion

#region Itens


def formulas_de_meta(folha, linha_modelo=2):
    """As 13 formulas de meta de uma linha, com a linha trocada.

    Serve para uma linha NOVA nascer com as mesmas margens das outras. Sem isso,
    um item acrescentado ficaria sem meta nenhuma e o bot Comprar simplesmente o
    pularia - em silencio, porque "sem preco escaneado" e "sem formula" produzem
    o mesmo resultado la."""

    formulas = []

    for i in range(13):

        bruto = folha.cell(row=linha_modelo, column=COL_META + i).value

        if not isinstance(bruto, str) or not bruto.startswith('='):
            return None

        # troca so o numero da linha nas referencias de celula
        formulas.append(re.sub(r'(\$?[A-Z]{1,2}\$?)' + str(linha_modelo) + r'\b',
                               r'\g<1>' + '{linha}', bruto))

    return formulas


def acrescentar_item(pagina, nome_ingles, nome_busca, tier, nome_t8=''):
    """Cria uma linha nova no fim da aba. Devolve (ok, mensagem, linha).

    NAO grava em disco - quem chama decide quando salvar, e assim varias
    alteracoes viram uma gravacao so."""

    folha = folha_por(pagina)

    if folha is None:
        return False, 'Planilha nao carregada.', None

    nome_busca = (nome_busca or '').strip()
    nome_ingles = (nome_ingles or '').strip()

    if not nome_busca:
        return False, 'O nome de busca e obrigatorio - e por ele que o bot acha o item no jogo.', None

    try:
        tier = int(tier)
    except (TypeError, ValueError):
        return False, 'O tier tem que ser um numero de 1 a 8.', None

    if not 1 <= tier <= 8:
        return False, 'O tier tem que ser um numero de 1 a 8.', None

    linhas = linhas_com_nome(folha, COL_BUSCA)

    # o mesmo nome de busca duas vezes faria o bot escanear o mesmo item em duas
    # linhas, e a segunda sobrescreveria a primeira sem ninguem notar
    for linha in linhas:
        atual = folha.cell(row=linha, column=COL_BUSCA).value
        if str(atual).strip().lower() == nome_busca.lower():
            return False, (f'Ja existe um item com o nome de busca '
                           f'"{nome_busca}" na linha {linha}.'), None

    nova = (linhas[-1] + 1) if linhas else 2

    folha.cell(row=nova, column=COL_NOME_INGLES).value = nome_ingles or nome_busca
    folha.cell(row=nova, column=COL_BUSCA).value = nome_busca
    folha.cell(row=nova, column=COL_TIER).value = tier

    if (nome_t8 or '').strip():
        folha.cell(row=nova, column=COL_NOME_T8).value = nome_t8.strip()

    # as metas: copiadas da primeira linha da aba, com a referencia trocada
    modelo = linhas[0] if linhas else None
    formulas = formulas_de_meta(folha, modelo) if modelo else None

    if formulas is None:
        return False, ('Nao deu para copiar as formulas de meta da primeira linha '
                       'desta aba - o item foi criado sem meta, e o bot Comprar '
                       'vai pula-lo.'), nova

    for i, formula in enumerate(formulas):
        folha.cell(row=nova, column=COL_META + i).value = formula.format(linha=nova)

    return True, '', nova


def remover_item(pagina, linha):
    """Apaga a linha do item, empurrando as de baixo para cima.

    NAO grava em disco. Devolve (ok, mensagem)."""

    folha = folha_por(pagina)

    if folha is None:
        return False, 'Planilha nao carregada.'

    if folha.cell(row=linha, column=COL_BUSCA).value is None:
        return False, f'A linha {linha} nao tem item.'

    folha.delete_rows(linha, 1)

    # As metas referenciam a propria linha (=TRUNC(B7 - ...) na linha 7). O
    # delete_rows do openpyxl NAO corrige essas referencias, entao a partir da
    # linha removida cada formula passaria a apontar para a linha de baixo -
    # comprando com a meta do item errado. Reescrever resolve, e e barato.
    _reescrever_metas(folha)

    return True, ''


def _reescrever_metas(folha):
    """Refaz as 13 formulas de meta de cada linha, apontando para a propria."""

    linhas = linhas_com_nome(folha, COL_BUSCA)

    if not linhas:
        return

    formulas = formulas_de_meta(folha, linhas[0])

    if formulas is None:
        return

    for linha in linhas:
        for i, formula in enumerate(formulas):
            folha.cell(row=linha, column=COL_META + i).value = formula.format(
                linha=linha)


def criar_aba(nome, modelo=0):
    """Cria uma aba nova com os rotulos da linha 1 copiados de <modelo>.

    O inventario do jogo tem limite, e por isso a planilha e dividida em abas: uma
    varredura carrega no inventario os itens de UMA aba. Quando uma aba enche, a
    saida e uma aba nova - e ela precisa nascer com os mesmos rotulos, senao a
    validacao do contrato de colunas recusa a varredura."""

    book = _estado['book']

    if book is None:
        return False, 'Planilha nao carregada.', None

    nome = (nome or '').strip()

    if not nome:
        return False, 'A aba precisa de um nome.', None

    if nome in book.sheetnames:
        return False, f'Ja existe uma aba chamada "{nome}".', None

    origem = folha_por(modelo)

    if origem is None:
        return False, 'Aba modelo nao encontrada.', None

    nova = book.create_sheet(nome)

    for coluna in range(1, COL_ATUALIZADO + 1):
        nova.cell(row=1, column=coluna).value = origem.cell(row=1, column=coluna).value

    return True, '', book.sheetnames.index(nome)


def folha_por(pagina):
    """A folha pelo indice ou pelo nome. Apelido de folha(), para leitura."""

    return folha(pagina)


def linhas_com_nome(folha, coluna, ate_vazio=True):
    """Numeros das linhas que tem nome na <coluna>, a partir da 2.

    Ler tudo de uma vez, em vez de espiar a proxima linha dentro do laco, evita
    o TypeError que o script original dava ao chegar na primeira linha vazia."""

    linhas = []
    linha = 2

    while True:

        if folha.cell(row=linha, column=coluna).value is None:
            if ate_vazio:
                break
            linha += 1
            continue

        linhas.append(linha)
        linha += 1

    return linhas

#endregion
