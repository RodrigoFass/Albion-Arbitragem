################################
#                              #
#           MERCADO            #
#                              #
################################

# As cidades e o banco de precos que o Conferidor enche.
#
# ATE AQUI O PROGRAMA SO CONHECIA UM MERCADO. O Mercado Negro era "o mercado", e
# o preco de um item era um numero so - uma coluna da planilha. A arbitragem
# entre cidades quebra as duas coisas: o mesmo item tem um preco em cada cidade,
# e o que decide a compra e a DIFERENCA entre dois deles.
#
# Por que um arquivo proprio, e nao mais colunas na Tabela-BM.xlsx: sao 7
# mercados x 13 combinacoes de grau e encantamento por item. Um item ocupa 91
# numeros. Uma aba de 121 itens ocupa 11.011 celulas, e isso multiplicado pelas
# abas nao cabe numa planilha que uma pessoa ainda precise conseguir ler. A
# planilha continua sendo o que ela e boa: o lugar onde VOCE edita margens e
# nomes. Isto aqui e o que a maquina enche e a maquina le.
#
# CADA PRECO CARREGA A HORA EM QUE FOI LIDO. Um preco de mercado nao envelhece
# como um nome envelhece: em duas horas ele ja e outro. A idade nao e enfeite de
# relatorio - e o que impede uma compra decidida sobre a leitura da semana
# passada, e por isso ela fica dentro do registro do preco, e nao numa coluna
# separada que alguem esquece de atualizar.
#
# Antes de alterar: python -m pyflakes mercado.py

import json
import os
import threading
import time

from motor import comum

# DUAS PONTAS GRAVAM AQUI AO MESMO TEMPO: a varredura e a escuta da rede, que
# recebe precos a qualquer momento. Sem a trava, gravar o json enquanto a outra
# ponta acrescenta um item da "dicionario mudou de tamanho" no meio da escrita.
_trava = threading.RLock()

#region Cidades

# Os seis mercados reais, Caerleon e o Mercado Negro.
#
# A ordem e a do mapa, nao a alfabetica: e como aparecem na tela de escolha, e
# quem opera pensa em rota, nao em dicionario.
CIDADES = (
    'Martlock',
    'Thetford',
    'Fort Sterling',
    'Lymhurst',
    'Bridgewatch',
    'Caerleon',
)

# O Mercado Negro fica em Caerleon, mas e um mercado a parte com precos
# proprios - por isso ele entra na lista como se fosse mais um lugar.
MERCADO_NEGRO = 'Mercado Negro'

MERCADOS = CIDADES + (MERCADO_NEGRO,)

# Onde se compra e onde se vende, no unico sentido que a rota tem hoje: comprar
# barato numa cidade real e vender no Mercado Negro. Deixado explicito porque a
# conta de lucro nao e simetrica - trocar as pontas nao da o negocio inverso, da
# um negocio que nao existe.
ORIGENS = CIDADES
DESTINO_PADRAO = MERCADO_NEGRO

#endregion

#region Banco de precos

ARQUIVO = os.path.join(comum.PASTA_DADOS, 'precos.json')

# Combinacoes de grau e encantamento, no mesmo formato que o resto do programa
# usa: 'T5.2' e o grau 5 com encantamento 2.
def rotulo(grau, ench):
    return f'T{grau}.{ench}'


# AS 13 COMBINACOES QUE VALEM A PENA, na ordem em que sao lidas.
#
# AQUI, E NAO EM CADA MODULO QUE PRECISA DELAS. Elas estavam repetidas no
# conferidor e na tela de Itens, e a ordem importa: e ela que agrupa por grau
# para o dropdown ser clicado o minimo possivel. Duas copias sao duas ordens que
# podem divergir sem ninguem perceber.
COMBINACOES = [
    (5, 2), (5, 3),
    (6, 0), (6, 1), (6, 2), (6, 3),
    (7, 0), (7, 1), (7, 2), (7, 3),
    (8, 0), (8, 1), (8, 2),
]

ROTULOS = [f'T{g}.{e}' for g, e in COMBINACOES]


def partes(rot):
    """'T5.2' -> (5, 2). None se nao for um rotulo valido."""

    if not rot.startswith('T') or '.' not in rot:
        return None

    grau, _, ench = rot[1:].partition('.')

    if not (grau.isdigit() and ench.isdigit()):
        return None

    return int(grau), int(ench)


_banco = {}
_carregado = False


def carregar(forcar=False):
    """Le o precos.json do disco. Devolve (ok, mensagem).

    Arquivo ausente NAO e erro: no primeiro uso ele nao existe mesmo, e o
    Conferidor e quem vai cria-lo. Tratar isso como falha faria o programa
    reclamar de algo que so o proprio uso resolve."""

    global _banco, _carregado

    if _carregado and not forcar:
        return True, ''

    _carregado = True

    if not os.path.exists(ARQUIVO):
        _banco = {}
        return True, ''

    try:
        with open(ARQUIVO, encoding='utf-8') as f:
            dados = json.load(f)

    except Exception as e:
        # Um json quebrado nao pode apagar o que ja foi coletado em silencio.
        # Sem o banco o programa ainda roda - so nao tem o que calcular.
        _banco = {}
        return False, f'nao foi possivel ler {os.path.basename(ARQUIVO)}: {e}'

    if not isinstance(dados, dict):
        _banco = {}
        return False, 'o precos.json nao tem o formato esperado'

    _banco = dados

    return True, ''


def salvar():
    """Grava o banco no disco. Devolve (ok, mensagem).

    ESCRITA ATOMICA, pelo mesmo motivo da planilha: uma varredura de uma cidade
    inteira leva minutos, e o F12 no meio da gravacao deixaria um json truncado
    - que na proxima abertura vira "formato inesperado" e todo o trabalho da
    coleta se perde. Escreve ao lado e troca de nome, que o sistema faz de uma
    vez so."""

    temporario = ARQUIVO + '.tmp'

    try:
        with _trava:
            texto = json.dumps(_banco, ensure_ascii=False, indent=1, sort_keys=True)

            with open(temporario, 'w', encoding='utf-8') as f:
                f.write(texto)

            os.replace(temporario, ARQUIVO)

    except Exception as e:
        try:
            os.remove(temporario)
        except OSError:
            pass

        return False, f'nao foi possivel gravar {os.path.basename(ARQUIVO)}: {e}'

    return True, ''


# Quantas ofertas do livro guardar por combinacao: bastam para a media de
# qualquer quantidade razoavel, e o arquivo nao incha.
OFERTAS_GUARDADAS = 30

# Ate quanto tempo atras o que a rede gravou num registro ainda e DESTA leitura.
RECENTE_DA_REDE = 120


def _ofertas_para_guardar(ofertas):
    """[[preco, quantidade]] das mais baratas, para o json."""

    return [[int(p), int(q)] for p, q in sorted(ofertas)[:OFERTAS_GUARDADAS]
            if p and q]


def gravar(mercado, item, rot, preco, quando=None, outro=None, ofertas=None):
    """Guarda um preco lido. <quando> em segundos desde a epoca.

    Sobrescreve o anterior de proposito: um preco velho do mesmo item na mesma
    cidade nao tem serventia nenhuma, e guardar historico aqui transformaria o
    arquivo num diario que ninguem le e que so cresce.

    <outro> e o preco da OUTRA COLUNA do livro, quando ela foi lida na mesma
    passada. No Mercado Negro sao "pedidos de venda" e "pedidos de compra": a
    varredura le o primeiro, e a estrategia de venda - vender na hora casando com
    um pedido de compra, ou entrar na fila com uma ordem - precisa do segundo.
    Voltar depois so para pega-lo custaria a varredura inteira de novo.

    Fica de fora do registro quando nao houver: um campo ausente e menor e mais
    honesto que um None gravado, e quem le ja trata a ausencia.

    <ofertas> e o livro de venda, [(preco, quantidade)] - e dele que sai a
    media que a lista de compras usa na cidade (ver lucro.media_das_ofertas).

    O QUE A REDE GRAVOU AGORA HA POUCO FICA. A varredura grava depois que o
    pacote ja entrou no registro, e substituir o registro inteiro apagava as
    cinco qualidades que so a rede traz - a compra por qualidade nunca achava
    linha para nada que tivesse sido varrido."""

    carregar()

    if preco is None:
        return

    agora = float(quando if quando is not None else time.time())

    registro = {'preco': int(preco), 'quando': agora}

    if outro is not None:
        registro['outro'] = int(outro)

    with _trava:
        combinacoes = _banco.setdefault(mercado, {}).setdefault(item, {})
        anterior = combinacoes.get(rot) or {}

        if (anterior.get('qualidades')
                and agora - anterior.get('quando', 0) <= RECENTE_DA_REDE):
            registro['qualidades'] = anterior['qualidades']

        if ofertas:
            registro['ofertas'] = _ofertas_para_guardar(ofertas)
        elif anterior.get('ofertas') and agora - anterior.get('quando', 0) <= RECENTE_DA_REDE:
            registro['ofertas'] = anterior['ofertas']

        combinacoes[rot] = registro


def atualizar(mercado, item, rot, preco=None, outro=None, qualidades=None,
              quando=None, ofertas=None):
    """Junta ao registro o que chegou, sem apagar o que nao veio.

    E O CAMINHO DA REDE. Um pacote pode trazer so as ofertas de venda, e o
    seguinte so os pedidos de compra; gravar() substituiria o registro inteiro e
    cada um apagaria o outro.

    <qualidades> e {qualidade: {'oferta': menor venda, 'pedido': maior compra}},
    o que a rede sabe de cada uma das cinco - a tela so mostra uma por vez."""

    carregar()

    with _trava:

        registro = _banco.setdefault(mercado, {}).setdefault(item, {}).setdefault(rot, {})

        if preco is not None:
            registro['preco'] = int(preco)

        if outro is not None:
            registro['outro'] = int(outro)

        if qualidades:
            atuais = registro.setdefault('qualidades', {})
            for q, valores in qualidades.items():
                atuais.setdefault(str(q), {}).update(
                    {k: int(v) for k, v in valores.items() if v is not None})

        if ofertas:
            registro['ofertas'] = _ofertas_para_guardar(ofertas)

        registro['quando'] = float(quando if quando is not None else time.time())


def ler(mercado, item, rot):
    """(preco, idade_em_horas) ou (None, None) se nao houver leitura."""

    carregar()

    registro = _banco.get(mercado, {}).get(item, {}).get(rot)

    if not registro or 'preco' not in registro:
        return None, None

    return registro['preco'], (time.time() - registro['quando']) / 3600


def ler_qualidades(mercado, item, rot):
    """{qualidade: {'oferta', 'pedido'}} e a idade em horas, ou ({}, None).

    So existe para o que chegou pela rede: a leitura da tela ve uma qualidade
    por vez."""

    carregar()

    registro = _banco.get(mercado, {}).get(item, {}).get(rot)

    if not registro or not registro.get('qualidades'):
        return {}, None

    return ({int(q): dict(v) for q, v in registro['qualidades'].items()},
            (time.time() - registro['quando']) / 3600)


def ler_ofertas(mercado, item, rot):
    """[(preco, quantidade)] do livro de venda guardado, mais barata primeiro, ou None."""

    carregar()

    registro = _banco.get(mercado, {}).get(item, {}).get(rot)

    if not registro or not registro.get('ofertas'):
        return None

    return [(int(p), int(q)) for p, q in registro['ofertas']]


def ler_outro(mercado, item, rot):
    """O preco da outra coluna do livro, ou None se nao foi lido."""

    carregar()

    registro = _banco.get(mercado, {}).get(item, {}).get(rot)

    return registro.get('outro') if registro else None


def combinacoes(mercado, item):
    """Os rotulos que ja foram lidos daquele item naquele mercado."""

    carregar()

    return sorted(_banco.get(mercado, {}).get(item, {}))


def itens(mercado):
    """Os itens que ja foram lidos naquele mercado."""

    carregar()

    return sorted(_banco.get(mercado, {}))


def mercados_lidos():
    """Os mercados que ja tem alguma leitura."""

    carregar()

    return [m for m in MERCADOS if _banco.get(m)]


def quantidade(mercado=None):
    """Quantos precos existem, no total ou num mercado."""

    carregar()

    alvos = [mercado] if mercado else list(_banco)

    return sum(len(c)
               for m in alvos
               for c in _banco.get(m, {}).values())


def idade_mais_velha(mercado):
    """Idade em horas do preco mais antigo daquele mercado, ou None.

    E o numero que responde "essa coleta ainda vale?" sem obrigar ninguem a
    olhar preco por preco."""

    carregar()

    agora = time.time()

    quandos = [r['quando']
               for c in _banco.get(mercado, {}).values()
               for r in c.values()]

    if not quandos:
        return None

    return (agora - min(quandos)) / 3600


def apagar_velhos(horas):
    """Remove precos com mais de <horas>. Devolve quantos sairam.

    O "Delete Old Data" existe porque preco velho e pior que preco nenhum: sem
    ele a tela mostra "sem dado" e voce vai coletar; com ele a tela mostra um
    numero, e numero na tela parece verdade."""

    carregar()

    limite = time.time() - horas * 3600
    saiu = 0

    with _trava:
        for mercado in list(_banco):
            for item in list(_banco[mercado]):

                for rot in list(_banco[mercado][item]):
                    if _banco[mercado][item][rot]['quando'] < limite:
                        del _banco[mercado][item][rot]
                        saiu += 1

                if not _banco[mercado][item]:
                    del _banco[mercado][item]

            if not _banco[mercado]:
                del _banco[mercado]

    return saiu


ARQUIVO_ANTERIOR = os.path.join(comum.PASTA_DADOS, 'precos-anterior.json')


def apagar_mercado(mercado):
    """Zera as leituras de um mercado, GUARDANDO COPIA. Devolve quantas sairam.

    A copia nao e zelo: "apagar antes de varrer" e o padrao, e apagar acontece no
    primeiro segundo da varredura. Parar no item cinco - por F12, por o jogo cair
    para tras, por qualquer coisa - deixava o mercado com cinco itens novos e os
    outros cento e dezesseis simplesmente perdidos, sem volta.

    UM ARQUIVO SO, sobrescrito a cada apagada. Nao e historico: e a rede embaixo
    da unica operacao do programa que destroi dado de propria iniciativa."""

    carregar()

    with _trava:
        n = quantidade(mercado)

        if n:
            _guardar_copia(mercado)

        _banco.pop(mercado, None)

    return n


def _guardar_copia(mercado):
    """Grava o que vai ser apagado em precos-anterior.json."""

    try:
        anterior = {}

        if os.path.exists(ARQUIVO_ANTERIOR):
            with open(ARQUIVO_ANTERIOR, encoding='utf-8') as f:
                lido = json.load(f)
                if isinstance(lido, dict):
                    anterior = lido

        anterior[mercado] = _banco.get(mercado, {})

        # A MESMA ESCRITA ATOMICA DO precos.json: gravar por cima e ser
        # interrompido no meio destruiria a copia justamente na hora em que ela
        # e a unica coisa que sobrou.
        temporario = ARQUIVO_ANTERIOR + '.tmp'

        with open(temporario, 'w', encoding='utf-8') as f:
            json.dump(anterior, f, ensure_ascii=False, indent=1, sort_keys=True)

        os.replace(temporario, ARQUIVO_ANTERIOR)

    except Exception:
        # A COPIA NAO PODE DERRUBAR A VARREDURA. Se ela falhar, o que se perde e
        # a rede - nao a coleta que estava para comecar.
        comum.contar('copia_de_precos_falhou')


def restaurar_copia(mercado):
    """Devolve ao banco o que a ultima apagada tirou. Quantos precos voltaram."""

    try:
        with open(ARQUIVO_ANTERIOR, encoding='utf-8') as f:
            anterior = json.load(f)

    except Exception:
        return 0

    guardado = anterior.get(mercado) if isinstance(anterior, dict) else None

    if not guardado:
        return 0

    carregar()

    _banco[mercado] = guardado

    return quantidade(mercado)


def tem_copia(mercado):
    """True se ha o que restaurar daquele mercado."""

    try:
        with open(ARQUIVO_ANTERIOR, encoding='utf-8') as f:
            anterior = json.load(f)

        return bool(anterior.get(mercado))

    except Exception:
        return False


def zerar():
    """Esvazia o banco em memoria. Nao toca no disco - use salvar() depois."""

    global _banco
    _banco = {}


def usar_banco(dados):
    """Troca o banco inteiro. Existe para os testes, e so para eles."""

    global _banco, _carregado
    _banco = dados
    _carregado = True

#endregion
