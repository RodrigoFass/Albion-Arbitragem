################################
#                              #
#           CATALOGO           #
#                              #
################################

# O que voce escolheu negociar: quais itens, em que grupos, e quanto de cada
# combinacao de grau e encantamento.
#
# E o unico arquivo deste programa que responde "o que fazer" em vez de "como
# fazer". O Conferidor pergunta a ele o que varrer; a calculadora pergunta
# quantas unidades de cada linha; a compra pergunta onde parar.
#
#
# A QUANTIDADE TEM TRES NIVEIS, cada um por cima do anterior.
#
#     a TABELA vale para todos os itens: quanto comprar de cada T5.2, de cada
#     T6.0, e assim por diante.
#
#     o GRUPO vale para os itens dele. E o meio-termo, e e o caso comum: "as
#     armaduras eu quero 20, as armas 8". Sem ele voce repetiria o mesmo ajuste
#     quarenta e cinco vezes.
#
#     as EXCECOES sao por item: este item, nesta combinacao, tem outro numero.
#
# Um nivel so nao dava conta. Um numero por combinacao ignora que um item liquido
# aguenta vinte unidades e um travado nao aguenta duas; um numero por item ignora
# que o mesmo item e barato no T5 e caro no T8.
#
#
# A TABELA PADRAO NAO FOI INVENTADA AQUI. Ela e a que voce ja afinou no bot que
# funciona hoje - 20 unidades no T6.0, 8 no T6.2, 1 no T8.2. Comecar de numeros
# redondos jogaria fora esse ajuste.
#
#
# QUANTIDADE ZERO E UMA RESPOSTA. Nao e "sem valor definido": e "nao quero esta
# combinacao". O Conferidor pula essas na varredura, o que encurta o trabalho na
# proporcao exata do que voce nao pretende comprar.
#
# Antes de alterar: python -m pyflakes catalogo.py

import json
import os

import categorias
import comum
import mercado

#region Configuracao

ARQUIVO = os.path.join(comum.PASTA, 'catalogo.json')

# As 13 combinacoes, com a quantidade que voce ja usa hoje.
TABELA_PADRAO = {
    'T5.2': 6,  'T5.3': 1,
    'T6.0': 20, 'T6.1': 20, 'T6.2': 8, 'T6.3': 1,
    'T7.0': 20, 'T7.1': 8,  'T7.2': 1, 'T7.3': 1,
    'T8.0': 3,  'T8.1': 1,  'T8.2': 1,
}

# O grupo em que um item cai quando voce nao escolhe nenhum.
GRUPO_PADRAO = 'Sem grupo'

#endregion

#region Estado

# Um catalogo e: grupos de itens, uma tabela de quantidades, e as excecoes.
#
# Guardado num dicionario so, e nao em variaveis soltas, porque ele inteiro e o
# que vai para o disco - e o que a tela carrega e salva com outro nome.
_vazio = {'grupos': {}, 'tabela': dict(TABELA_PADRAO),
          'por_grupo': {}, 'excecoes': {}}

_catalogo = json.loads(json.dumps(_vazio))
_nome_atual = 'padrao'

#endregion

#region Grupos


def grupos():
    """Os nomes dos grupos, em ordem alfabetica."""

    return sorted(_catalogo['grupos'])


def criar_grupo(nome):
    """Cria um grupo vazio. False se ele ja existia."""

    nome = (nome or '').strip()

    if not nome or nome in _catalogo['grupos']:
        return False

    _catalogo['grupos'][nome] = []

    return True


def apagar_grupo(nome, mover_para=None):
    """Apaga um grupo. Os itens vao para <mover_para>, ou saem do catalogo.

    Apagar em silencio os itens junto seria a forma mais facil de perder meia
    hora de escolha por um clique - por isso o destino e explicito."""

    if nome not in _catalogo['grupos']:
        return False

    itens = _catalogo['grupos'].pop(nome)
    _catalogo['por_grupo'].pop(nome, None)

    if mover_para is not None:
        criar_grupo(mover_para)
        for item in itens:
            if item not in _catalogo['grupos'][mover_para]:
                _catalogo['grupos'][mover_para].append(item)
    else:
        for item in itens:
            _catalogo['excecoes'].pop(item, None)

    return True


def renomear_grupo(antigo, novo):
    novo = (novo or '').strip()

    if antigo not in _catalogo['grupos'] or not novo or novo in _catalogo['grupos']:
        return False

    _catalogo['grupos'][novo] = _catalogo['grupos'].pop(antigo)

    if antigo in _catalogo['por_grupo']:
        _catalogo['por_grupo'][novo] = _catalogo['por_grupo'].pop(antigo)

    return True

#endregion

#region Itens


def acrescentar(item, grupo=GRUPO_PADRAO):
    """Poe um item no catalogo. Devolve (ok, motivo).

    RECUSA ITEM SEM CAMINHO DE MENU. Um item que o bot nao consegue selecionar na
    tela nao e uma escolha ruim, e uma escolha impossivel - e descobrir isso na
    metade de uma varredura, item por item, e o pior momento."""

    item = (item or '').strip()

    if not item:
        return False, 'nome vazio'

    if not categorias.navegavel(item):
        return False, f'"{item}" nao tem caminho de menu conhecido'

    if item in todos():
        return False, f'"{item}" ja esta no catalogo'

    criar_grupo(grupo)
    _catalogo['grupos'][grupo].append(item)

    return True, ''


_desfazer = []


def remover(item):
    """Tira um item do catalogo, com as excecoes dele.

    GUARDA O QUE TIROU. Um item com treze quantidades afinadas some com um
    clique, e sem isto o unico caminho de volta seria refazer o ajuste na mao.
    Ver desfazer()."""

    return remover_varios([item]) == 1


def remover_varios(itens):
    """Remove uma leva de uma vez, desfeita por um unico desfazer()."""

    lote = []

    for item in itens:

        grupo = grupo_de(item)

        if grupo is None:
            continue

        _catalogo['grupos'][grupo].remove(item)
        lote.append((item, grupo, _catalogo['excecoes'].pop(item, None)))

    if lote:
        _desfazer.append(lote)

    return len(lote)


def da_para_desfazer():
    return bool(_desfazer)


def desfazer():
    """Devolve o ultimo lote removido, no grupo de onde saiu. Quantos voltaram.

    O grupo pode ter sido apagado no meio-tempo - ai ele renasce, porque a
    alternativa seria jogar o item num lugar que voce nao escolheu."""

    if not _desfazer:
        return 0

    lote = _desfazer.pop()

    for item, grupo, excecoes in lote:

        criar_grupo(grupo)

        if item not in _catalogo['grupos'][grupo]:
            _catalogo['grupos'][grupo].append(item)

        if excecoes:
            _catalogo['excecoes'][item] = excecoes

    return len(lote)


def mover(item, para):
    """Troca o item de grupo."""

    if item not in todos():
        return False

    for itens in _catalogo['grupos'].values():
        if item in itens:
            itens.remove(item)

    criar_grupo(para)
    _catalogo['grupos'][para].append(item)

    return True


def itens_de(grupo):
    return list(_catalogo['grupos'].get(grupo, []))


def _mapa_de_grupos():
    """{item: grupo}, feito de uma vez.

    Quem pergunta por um item so continua usando grupo_de. Quem pergunta por
    todos - a varredura, o resumo, a calculadora - passa a construir isto uma vez
    em vez de varrer os grupos inteiros a cada pergunta."""

    mapa = {}

    for nome, itens in _catalogo['grupos'].items():
        for item in itens:
            mapa.setdefault(item, nome)

    return mapa


def grupo_de(item):
    """Em que grupo o item esta, ou None."""

    for nome, itens in _catalogo['grupos'].items():
        if item in itens:
            return nome

    return None


def todos():
    """Todos os itens do catalogo, sem repetir, na ordem dos grupos.

    DICT E NAO LISTA para deduplicar. E a funcao mais chamada do modulo, e com
    `not in lista` ela custava o quadrado do tamanho do catalogo - dentro de
    lacos que ja iteravam sobre itens, virava o cubo. O dict preserva a ordem de
    insercao desde o 3.7, entao nao se perde nada."""

    vistos = {}

    for nome in grupos():
        for item in _catalogo['grupos'][nome]:
            vistos[item] = True

    return list(vistos)


def conjunto():
    """Os mesmos itens, para quem so precisa perguntar "ja tenho este?".

    Existe porque a pergunta era feita DENTRO de lacos, uma vez por item, e cada
    pergunta reconstruia a lista inteira."""

    return set(todos())

#endregion

#region Quantidades


def quantidade(item, rotulo):
    """Quantas unidades comprar daquele item naquela combinacao.

    A ORDEM E ITEM, GRUPO, TABELA - do mais especifico para o mais geral, e o
    primeiro que tiver resposta vence.

    Zero e resposta valida - quer dizer "nao quero esta combinacao" - e por isso
    a busca nao pode usar `or`, que trataria zero como ausencia e devolveria o
    nivel de cima, comprando o que voce acabou de dizer que nao queria."""

    return _quantidade(item, grupo_de(item), rotulo)


def _quantidade(item, grupo, rotulo):
    """A mesma resposta, com o grupo ja resolvido por quem chamou."""

    excecao = _catalogo['excecoes'].get(item, {})

    if rotulo in excecao:
        return int(excecao[rotulo])

    do_grupo = _catalogo['por_grupo'].get(grupo or '', {})

    if rotulo in do_grupo:
        return int(do_grupo[rotulo])

    return int(_catalogo['tabela'].get(rotulo, 0))


def definir_no_grupo(grupo, rotulo, quanto):
    """Uma quantidade para todos os itens daquele grupo.

    None apaga e devolve o grupo a tabela geral."""

    if grupo not in _catalogo['grupos']:
        return False

    if quanto is None:
        _catalogo['por_grupo'].get(grupo, {}).pop(rotulo, None)
        if not _catalogo['por_grupo'].get(grupo):
            _catalogo['por_grupo'].pop(grupo, None)
        return True

    _catalogo['por_grupo'].setdefault(grupo, {})[rotulo] = max(0, int(quanto))

    return True


def quantidade_do_grupo(grupo, rotulo):
    """O que vale para o grupo: o dele, ou o da tabela."""

    do_grupo = _catalogo['por_grupo'].get(grupo, {})

    if rotulo in do_grupo:
        return int(do_grupo[rotulo])

    return int(_catalogo['tabela'].get(rotulo, 0))


def excecoes_do_grupo(grupo):
    return dict(_catalogo['por_grupo'].get(grupo, {}))


def grupo_tem_excecao(grupo):
    return bool(_catalogo['por_grupo'].get(grupo))


def definir_tabela(rotulo, quanto):
    """Muda a quantidade daquela combinacao para TODOS os itens."""

    _catalogo['tabela'][rotulo] = max(0, int(quanto))


def definir_em_massa(rotulos, quanto):
    """A mesma quantidade em varias combinacoes de uma vez.

    E o "Bulk Amount Set": voce marca as combinacoes que quer e poe um numero
    so. Sem isso, ajustar treze linhas e treze edicoes."""

    for rotulo in rotulos:
        definir_tabela(rotulo, quanto)


def definir(item, rotulo, quanto):
    """Uma quantidade so para ESTE item nesta combinacao.

    Passar None apaga a excecao e devolve o item a tabela."""

    if item not in todos():
        return False

    if quanto is None:
        _catalogo['excecoes'].get(item, {}).pop(rotulo, None)
        if not _catalogo['excecoes'].get(item):
            _catalogo['excecoes'].pop(item, None)
        return True

    _catalogo['excecoes'].setdefault(item, {})[rotulo] = max(0, int(quanto))

    return True


def excecoes_de(item):
    return dict(_catalogo['excecoes'].get(item, {}))


def tem_excecao(item):
    return bool(_catalogo['excecoes'].get(item))


def tabela():
    return dict(_catalogo['tabela'])

#endregion

#region O que o resto do programa pergunta


# 'T6.0' -> (6, 0), pronto. A conversao acontece 1.573 vezes por resumo, e o
# conjunto de rotulos possiveis e fixo e pequeno.
_PARTES = {f'T{g}.{e}': (g, e) for g in range(1, 9) for e in range(0, 5)}


def combinacoes_de(item, mapa=None):
    """As (grau, ench) que valem a pena varrer para este item.

    Quantidade zero nao entra: varrer uma combinacao que voce nao pretende
    comprar e ler a tela para jogar o numero fora. Numa lista onde metade dos
    graus altos esta zerada, isso corta a varredura pela metade.

    <mapa> e o {item: grupo} de quem vai perguntar por muitos itens seguidos.
    Sem ele o grupo e redescoberto a cada combinacao, varrendo todos os grupos."""

    grupo = mapa.get(item) if mapa is not None else grupo_de(item)

    saida = []

    for rotulo in _catalogo['tabela']:

        partes = _PARTES.get(rotulo) or mercado.partes(rotulo)

        if partes is None:
            continue

        if _quantidade(item, grupo, rotulo) > 0:
            saida.append(partes)

    for rotulo in _catalogo['excecoes'].get(item, {}):

        partes = _PARTES.get(rotulo) or mercado.partes(rotulo)

        if partes and partes not in saida and _quantidade(item, grupo,
                                                          rotulo) > 0:
            saida.append(partes)

    return sorted(saida)


def em_lote(rotulos, quanto, itens=None):
    """Poe <quanto> nas combinacoes <rotulos> de varios itens. Quantas mudaram.

    E o "Bulk Remove/Add T.E" da tela de referencia, e ele resolve um problema
    real: decidir que nenhum item vale a pena no T8.3 e ter que abrir item por
    item para zerar. Com 121 itens isso e trabalho de tarde.

    <quanto> zero TIRA a combinacao da varredura sem apagar o item - varrer uma
    combinacao que voce nao pretende comprar e ler a tela para jogar o numero
    fora. <itens> None vale para o catalogo inteiro, e ai a mudanca vai para a
    TABELA GERAL em vez de virar 121 excecoes iguais."""

    if not rotulos:
        return 0

    quanto = max(0, int(quanto))

    if itens is None:
        for rotulo in rotulos:
            definir_tabela(rotulo, quanto)
        return len(rotulos)

    mudadas = 0

    for item in itens:
        for rotulo in rotulos:
            definir(item, rotulo, quanto)
            mudadas += 1

    return mudadas


def rotulos_validos(texto):
    """'8.3, 7.2' ou 'T8.3 T7.2' -> ['T8.3', 'T7.2']. Ignora o que nao existe.

    ACEITA O JEITO QUE A PESSOA DIGITA. Escrever a combinacao com ou sem o T, com
    virgula ou espaco, e a mesma intencao - e recusar por causa da pontuacao seria
    fazer o usuario adivinhar a forma."""

    saida = []

    for pedaco in str(texto).replace(',', ' ').replace(';', ' ').split():

        limpo = pedaco.strip().upper().lstrip('T')

        rotulo = 'T' + limpo

        if rotulo in _PARTES and rotulo not in saida:
            saida.append(rotulo)

    return saida


def para_varrer(grupo=None):
    """Os itens a varrer. Um grupo, ou o catalogo inteiro."""

    return itens_de(grupo) if grupo else todos()


def para_calcular(grupo=None):
    """As triplas (item, rotulo, quantidade) que a calculadora de lucro espera.

    E o encaixe entre o que voce escolheu e a conta que decide a compra: o
    lucro.montar() recebe isto e devolve a lista de compras."""

    linhas = []

    for item in para_varrer(grupo):
        for grau, ench in combinacoes_de(item):
            rotulo = mercado.rotulo(grau, ench)
            linhas.append((item, rotulo, quantidade(item, rotulo)))

    return linhas


# Quanto tempo uma combinacao leva para ser lida, em segundos.
#
# ESTIMATIVA, e nao medida: sao os dois cliques de filtro mais a espera da lista
# assentar mais o OCR. Ate a primeira varredura de verdade este numero e um
# palpite informado - mas um palpite que aparece na tela vale mais que nenhum
# numero, porque e ele que responde "esse catalogo cabe na minha tarde?".
SEGUNDOS_POR_COMBINACAO = 1.5


def minutos_de_varredura(grupo=None):
    """Quanto tempo levaria varrer isto, em minutos, num mercado."""

    combinacoes = sum(len(combinacoes_de(i)) for i in para_varrer(grupo))

    return combinacoes * SEGUNDOS_POR_COMBINACAO / 60


def resumo():
    """Numeros para a tela mostrar sem ter que contar sozinha.

    O MAPA DE GRUPOS E FEITO UMA VEZ E PASSADO ADIANTE. Sem ele, cada uma das
    1.573 consultas de quantidade redescobria em que grupo o item esta varrendo
    todos os grupos - era isso, e nao a soma, que fazia esta funcao custar 10 ms
    e responder pela metade do tempo de cada recarga da tela Itens."""

    mapa = _mapa_de_grupos()
    itens = todos()

    # UMA PASSADA SO. A versao anterior calculava as combinacoes de cada item
    # DUAS vezes - uma para contar, outra para somar unidades - e a segunda ainda
    # ia pela quantidade() publica, que redescobre o grupo varrendo todos.
    combinacoes = 0
    unidades = 0

    for item in itens:

        grupo = mapa.get(item)

        for grau, ench in combinacoes_de(item, mapa):
            combinacoes += 1
            unidades += _quantidade(item, grupo, mercado.rotulo(grau, ench))

    return {
        'grupos': len(_catalogo['grupos']),
        'itens': len(itens),
        'combinacoes': combinacoes,
        'unidades': unidades,
        'com_excecao': sum(1 for i in itens if tem_excecao(i)),
        'minutos': combinacoes * SEGUNDOS_POR_COMBINACAO / 60,
    }

#endregion

#region Vindo da planilha


def achar_planilha():
    """Onde esta a Tabela-BM.xlsx. None se nao houver."""

    aqui = os.path.dirname(os.path.abspath(__file__))

    for tentativa in (os.path.join(aqui, 'Tabela-BM.xlsx'),
                      os.path.join(os.path.dirname(aqui), 'mercado-negro',
                                   'Tabela-BM.xlsx')):
        if os.path.exists(tentativa):
            return tentativa

    return None


def importar_da_planilha(caminho=None, coluna=1):
    """Traz os itens da Tabela-BM.xlsx. Devolve (quantos, avisos).

    OS 121 ITENS SAO TRABALHO SEU, e as tres abas ja sao a sua organizacao - a
    divisao existe porque o inventario tem limite, e cada aba e uma viagem. Elas
    viram os grupos do catalogo, com o mesmo nome.
    
    Isto acontece UMA VEZ. Dali em diante o catalogo e dele mesmo: os grupos que
    voce criar aqui nao voltam para a planilha, e as abas que voce mexer la nao
    chegam aqui. Duas fontes de verdade para a mesma lista e como uma delas fica
    velha sem ninguem perceber.

    Itens sem caminho de menu ficam de fora, com aviso - um item que o bot nao
    consegue selecionar na tela nao pode entrar como se fosse negociavel."""

    import planilha

    caminho = caminho or achar_planilha()

    if caminho is None:
        return 0, ['a Tabela-BM.xlsx nao foi encontrada']

    planilha.ARQUIVO = caminho

    ok, erro = planilha.carregar(forcar=True)

    if not ok:
        return 0, [erro or 'nao foi possivel abrir a planilha']

    entraram = 0
    avisos = []

    for i, aba in enumerate(planilha.abas()):

        folha = planilha.folha(i)
        grupo = str(aba).strip() or GRUPO_PADRAO

        for linha in planilha.linhas_com_nome(folha, 29):

            nome = str(folha.cell(row=linha, column=coluna).value or '').strip()

            if not nome:
                continue

            pos, motivo = acrescentar(nome, grupo)

            if pos:
                entraram += 1
            elif 'ja esta' not in motivo:
                avisos.append(motivo)

    return entraram, avisos

#endregion

#region Disco


def _caminho(nome):
    seguro = ''.join(c if c.isalnum() or c in ' -_' else '_' for c in nome).strip()

    return os.path.join(comum.PASTA, f'catalogo-{seguro or "padrao"}.json')


def salvar(nome=None):
    """Grava o catalogo. Devolve (ok, mensagem).

    ESCRITA ATOMICA: escolher cem itens leva tempo, e um F12 no meio da gravacao
    deixaria um json truncado - que na proxima abertura vira catalogo vazio."""

    global _nome_atual

    nome = nome or _nome_atual
    caminho = _caminho(nome)
    temporario = caminho + '.tmp'

    try:
        with open(temporario, 'w', encoding='utf-8') as f:
            json.dump(_catalogo, f, ensure_ascii=False, indent=1, sort_keys=True)

        os.replace(temporario, caminho)

    except Exception as e:
        try:
            os.remove(temporario)
        except OSError:
            pass

        return False, f'nao foi possivel gravar {os.path.basename(caminho)}: {e}'

    _nome_atual = nome

    return True, ''


def carregar(nome=None):
    """Le um catalogo do disco. Devolve (ok, mensagem).

    Arquivo ausente nao e erro: no primeiro uso ele nao existe, e o catalogo
    nasce vazio com a tabela padrao."""

    global _catalogo, _nome_atual

    nome = nome or _nome_atual
    caminho = _caminho(nome)

    if not os.path.exists(caminho):
        _catalogo = json.loads(json.dumps(_vazio))
        _nome_atual = nome
        return True, ''

    try:
        with open(caminho, encoding='utf-8') as f:
            dados = json.load(f)

    except Exception as e:
        return False, f'nao foi possivel ler {os.path.basename(caminho)}: {e}'

    if not isinstance(dados, dict) or 'grupos' not in dados:
        return False, f'{os.path.basename(caminho)} nao tem o formato esperado'

    _catalogo = {
        'grupos': dados.get('grupos', {}),
        'tabela': dict(TABELA_PADRAO, **dados.get('tabela', {})),
        'por_grupo': dados.get('por_grupo', {}),
        'excecoes': dados.get('excecoes', {}),
    }

    _nome_atual = nome

    return True, ''


def salvos():
    """Os catalogos que existem no disco, pelo nome."""

    achados = []

    try:
        for arquivo in os.listdir(comum.PASTA):
            if arquivo.startswith('catalogo-') and arquivo.endswith('.json'):
                achados.append(arquivo[len('catalogo-'):-len('.json')])
    except OSError:
        pass

    return sorted(achados)


def nome_atual():
    return _nome_atual


def zerar():
    """Esvazia o catalogo em memoria. Nao toca no disco."""

    global _catalogo
    _catalogo = json.loads(json.dumps(_vazio))


def usar(dados):
    """Troca o catalogo inteiro. Existe para os testes, e so para eles."""

    global _catalogo
    _catalogo = dados

#endregion
