################################
#                              #
#           AJUSTES            #
#                              #
################################

# As preferencias: taxa, margem, idade maxima de um preco e os limites de tempo.
#
# Ficam num arquivo proprio, e nao no catalogo, porque respondem a perguntas
# diferentes. O catalogo e O QUE negociar - muda quando o mercado muda de humor.
# Isto aqui e COMO operar - muda quando voce assina Premium, ou quando o jogo
# comeca a responder mais devagar.
#
# A TAXA E A UNICA QUE MUDA SOZINHA NA VIDA REAL: com Premium ela cai pela
# metade. Por isso ela e um campo, e nao uma constante - e por isso o padrao e o
# caso caro. Errar para menos faz o programa recomendar compras que nao pagam;
# errar para mais so deixa passar negocio magro.
#
# Antes de alterar: python -m pyflakes ajustes.py

import json
import os

import comum
import lucro

ARQUIVO = os.path.join(comum.PASTA, 'ajustes.json')

PADRAO = {
    'premium': False,
    'margem': lucro.MARGEM_PADRAO,
    'idade_maxima': lucro.IDADE_MAXIMA_PADRAO,

    # TETO DE GASTO POR RODADA, em prata. None = sem teto.
    #
    # Sem ele o unico limite e a quantidade do catalogo: 11.011 unidades, que
    # com os precos de hoje passam de um bilhao. O freio seria o F12 - e F12 e
    # freio de emergencia, nao de projeto.
    #
    # Nao ha valor padrao porque um numero sugerido aqui seria adivinhacao sobre
    # quanta prata voce tem naquele momento.
    'teto': None,

    # --- como a janela se comporta ----------------------------------------
    # Sair da frente enquanto trabalha. Desmarque para acompanhar o log em outro
    # monitor.
    'minimizar': True,

    # Trazer o jogo para frente ao comecar. Sem isto, alterne para ele na mao
    # antes de clicar - e o clique de "comecar" deixa esta janela na frente, o
    # que faria a varredura clicar aqui dentro.
    'focar_jogo': True,

    # Um apito e o botao da barra de tarefas piscando quando termina. Uma
    # varredura leva dezenas de minutos: tempo de sair de perto.
    'avisar_no_fim': True,

    # Uma tira no topo da tela com o item atual, por cima do jogo. Nao aceita
    # clique, para nao tirar o foco do jogo.
    'faixa': True,

    # Cartoes no canto de baixo com cada preco lido, por cima do jogo. Servem
    # para conferir a leitura ao lado do numero que o jogo mostra, na hora - a
    # janela do aplicativo passa a varredura inteira minimizada.
    'avisos': True,

    # --- como a varredura se comporta -------------------------------------
    # Apagar os precos daquele mercado antes de varrer.
    #
    # Sem isso, parar no meio deixa o mercado com precos novos em alguns itens e
    # antigos nos demais, sem como distinguir - e a calculadora trata os dois
    # igual. O que ja estava la vai para precos-anterior.json antes de sumir, e
    # a tela Conferir tem um botao para trazer de volta.
    'apagar_antes': True,

    # Reler, ao terminar, as combinacoes que voltaram sem preco.
    #
    # Vale a pena na hora: os itens ainda estao a sua frente, o mercado esta
    # aberto, e o que faltou costuma ser lentidao da tela e nao ausencia de
    # oferta. Depois voce teria que voltar ate la.
    'repescar': True,

    # Reler N combinacoes SORTEADAS no fim e comparar com o que ficou gravado.
    #
    # E a unica forma de pegar erro SISTEMATICO de leitura. Se a varredura
    # inteira leu um digito a menos, os precos continuam crescendo direitinho e
    # nenhuma checagem de consistencia acusa - so reler e comparar. Zero desliga.
    'amostras': 8,

    # Onde voce estava da ultima vez que conferiu.
    #
    # Nao e conveniencia: sem isto o botao Comecar nasce apagado toda abertura do
    # programa, sem dizer por que, e a resposta - "escolha uma cidade" - fica num
    # texto embaixo. Lembrar transforma a tela em "confirme onde voce esta".
    'ultimo_mercado': '',

    # --- como o bot compra ------------------------------------------------
    # SMART BUY, SO ORDEM, OU SO NA HORA.
    #
    # O automatico escolhe por linha e acerta quase sempre. As duas travas
    # existem para quando voce sabe algo que a regra nao sabe: numa rodada de
    # itens caros, ordem nenhuma; num item que voce quer varrer inteiro, ordem
    # sempre.
    'modo_de_compra': 'smart',

    # As duas regras do Smart Buy, com os numeros da tela de referencia.
    #
    # ORDEM quando ha volume: ela casa com todas as ofertas naquele preco de uma
    # vez, e a taxa de 2,5% se paga em cliques poupados. NA HORA quando o item e
    # caro: ali 2,5% e dinheiro de verdade, e sao poucas unidades mesmo.
    'ordem_a_partir_de': 8,
    'na_hora_acima_de': 100_000,

    # --- teclas -----------------------------------------------------------
    # F11 e tela cheia em qualquer navegador e F12 abre o console. Quem joga com
    # o navegador atras precisa de outra combinacao.
    'tecla_pausa': 'f11',
    'tecla_parada': 'f12',
    'tecla_pular': 'f2',

    # --- velocidade, em milissegundos -------------------------------------
    # Os tres numeros que compensam uma maquina lenta ou um ping alto sem mexer
    # em mais nada. Sao os mesmos tres da tela de referencia.
    'ms_clique': 120,
    'ms_escrita': 50,
    'ms_leitura': 400,

    # Escuro ou claro. As duas paletas saem da marca.
    'tema': 'escuro',
}

_ajustes = dict(PADRAO)
_carregado = False


def aplicar():
    """Leva as preferencias para os modulos que dependem delas.

    AS TECLAS E AS VELOCIDADES NAO SAO SO DADO: elas vivem em constantes do
    comum, e sem esta ponte uma preferencia salva ficaria bonita no JSON e sem
    efeito nenhum. O carregar ja faz isso; esta funcao existe para quem SALVOU e
    quer o efeito agora, sem reabrir o programa."""

    comum.definir_teclas(_ajustes.get('tecla_pausa'),
                         _ajustes.get('tecla_parada'),
                         _ajustes.get('tecla_pular'))

    comum.definir_velocidades(_ajustes.get('ms_clique'),
                              _ajustes.get('ms_escrita'),
                              _ajustes.get('ms_leitura'))


def atuais():
    """As preferencias, com a taxa ja resolvida a partir do Premium."""

    carregar()

    saida = dict(_ajustes)

    saida['taxa'] = (lucro.TAXA_COM_PREMIUM if _ajustes['premium']
                     else lucro.TAXA_SEM_PREMIUM)

    return saida


def definir(chave, valor):

    carregar()

    if chave in PADRAO:
        _ajustes[chave] = valor


def carregar(forcar=False):
    """Le do disco. Arquivo ausente nao e erro - vale o padrao."""

    global _ajustes, _carregado

    if _carregado and not forcar:
        return True, ''

    _carregado = True

    if not os.path.exists(ARQUIVO):
        _ajustes = dict(PADRAO)
        return True, ''

    try:
        with open(ARQUIVO, encoding='utf-8') as f:
            dados = json.load(f)
    except Exception as e:
        _ajustes = dict(PADRAO)
        return False, f'nao foi possivel ler os ajustes: {e}'

    _ajustes = dict(PADRAO)

    for chave in PADRAO:
        if chave in dados:
            _ajustes[chave] = dados[chave]

    # As teclas e as velocidades vivem em constantes do comum; sem esta ponte a
    # preferencia lida do disco nao teria efeito nenhum.
    comum.definir_teclas(_ajustes.get('tecla_pausa'),
                         _ajustes.get('tecla_parada'),
                         _ajustes.get('tecla_pular'))

    comum.definir_velocidades(_ajustes.get('ms_clique'),
                              _ajustes.get('ms_escrita'),
                              _ajustes.get('ms_leitura'))

    return True, ''


def salvar():

    temporario = ARQUIVO + '.tmp'

    try:
        with open(temporario, 'w', encoding='utf-8') as f:
            json.dump(_ajustes, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(temporario, ARQUIVO)

        # AS TECLAS E AS VELOCIDADES VALEM NA HORA. Guardar sem aplicar deixaria
        # a preferencia bonita no arquivo e sem efeito ate reabrir o programa -
        # e quem acabou de trocar a tecla de parada vai testar em seguida.
        aplicar()
    except Exception as e:
        try:
            os.remove(temporario)
        except OSError:
            pass
        return False, f'nao foi possivel gravar os ajustes: {e}'

    return True, ''


def restaurar():
    global _ajustes
    _ajustes = dict(PADRAO)
