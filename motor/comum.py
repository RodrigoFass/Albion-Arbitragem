################################
#                              #
#        INFRAESTRUTURA        #
#         COMPARTILHADA        #
#                              #
################################

# Tudo que os tres bots precisam em comum: trava de execucao, registro, parada de
# emergencia, checagem de ambiente, cliques, esperas adaptativas, OCR e o
# historico de operacoes.
#
# Por que existir: antes destas linhas viverem aqui, elas eram tres copias quase
# iguais. O custo apareceu na pratica - uma correcao de contadores foi aplicada
# num bot e nao nos outros dois, e a auditoria encontrou 8 contadores acumulando
# entre execucoes. Correcao em um lugar agora vale para os tres.
#
# A SAIDA NAO USA print DIRETO. Tudo passa por relatar(), que escreve num destino
# configuravel - terminal por padrao, painel da interface quando o app define
# outro. Isso e o que permite os bots rodarem dentro de uma janela grafica.
#
# DOIS SINAIS DE PARADA, e a diferenca e QUANDO param, nao o que acontece depois:
#
#   parada_pedida   termine a unidade de trabalho, grave, e devolva o controle
#   aborto_pedido   pare onde estiver, agora
#
# Os dois devolvem o controle com a janela do aplicativo aberta. Nenhum mata o
# processo. Antes eram um evento so, e o botao Parar - que promete "grava e a
# interface continua aberta" - passava pelo os._exit de dentro do salvar(),
# chamado ao fim de cada item: clicar em Parar fazia a janela sumir.
#
# Antes de alterar: python -m pyflakes comum.py

import csv
import os
import re
import sys
import threading
import time
from contextlib import contextmanager

import mss
import win32api
import win32con
import win32gui
import pytesseract
from PIL import Image, ImageOps
from pynput.keyboard import Controller, Key, Listener

# Sobe a cada mudanca que altere comportamento. Vai para o cabecalho de cada
# sessao de log e para o rodape da janela: sem isso, todo suporte a alguem que
# recebeu o pacote comeca por adivinhar qual build a pessoa tem.
VERSAO = '3.0.0'


def _pasta_do_programa():
    """A pasta do programa.

    Rodando pelo Python e a raiz do projeto (este arquivo mora em motor/).
    Empacotado com o PyInstaller e a pasta do .EXE - e nao a do __file__, que ali
    aponta para dentro do pacote, um diretorio que o Windows apaga depois."""

    if getattr(sys, 'frozen', False):
        return os.path.dirname(os.path.abspath(sys.executable))

    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


PASTA = _pasta_do_programa()

# O que vem COM o programa e nunca e gravado: o catalogo inicial, o mapa de ids
# da API, os graus base, o icone.
PASTA_RECURSOS = os.path.join(PASTA, 'recursos')

# OS DADOS DE QUEM USA: ajustes, precos, catalogos, coordenadas e registros, numa
# pasta so, separados do programa. ALBION_DADOS manda para outro lugar - e e
# assim que os testes rodam numa pasta temporaria. Antes eles gravavam precos de
# mentira no precos.json de verdade, e um teste que quebrasse no meio deixava os
# precos la.
PASTA_DADOS = os.environ.get('ALBION_DADOS') or os.path.join(PASTA, 'dados')

try:
    os.makedirs(PASTA_DADOS, exist_ok=True)
except OSError:
    pass

# O que ficava solto ao lado do programa nas versoes anteriores.
_DADOS_ANTIGOS = ('ajustes.json', 'precos.json', 'precos-anterior.json',
                  'coordenadas.json', 'registros')


def migrar_dados_antigos():
    """Leva para dados/ o que versoes anteriores gravavam na raiz. Quantos moveu.

    MOVE, nao copia, e nunca sobrescreve: se o arquivo ja existe em dados/, o
    antigo fica onde esta."""

    if os.path.abspath(PASTA_DADOS) == os.path.abspath(PASTA):
        return 0

    nomes = list(_DADOS_ANTIGOS)

    try:
        nomes += [n for n in os.listdir(PASTA)
                  if n.startswith('catalogo-') and n.endswith('.json')]
    except OSError:
        pass

    movidos = 0

    for nome in nomes:

        antigo = os.path.join(PASTA, nome)
        novo = os.path.join(PASTA_DADOS, nome)

        if os.path.exists(antigo) and not os.path.exists(novo):
            try:
                os.replace(antigo, novo)
                movidos += 1
            except OSError:
                pass

    return movidos

# Tudo que os bots GERAM vai para ca: logs, historico.csv e os PNGs de
# diagnostico do OCR.
PASTA_REGISTROS = os.path.join(PASTA_DADOS, 'registros')


def pasta_registro(nome='', criar=True):
    """Caminho dentro de registros/, criando a pasta se preciso.

    <criar> False para so montar o caminho - o resumo lista os PNGs ja gravados e
    nao deve criar a pasta so para descobrir que ela esta vazia."""

    destino = os.path.join(PASTA_REGISTROS, nome) if nome else PASTA_REGISTROS

    if criar:
        try:
            os.makedirs(destino, exist_ok=True)
        except OSError:
            return PASTA_DADOS   # sem conseguir criar, a raiz e melhor que perder o dado

    return destino


def pasta_gravavel(pasta=None):
    """True se da para escrever em <pasta>. Devolve (ok, motivo).

    Existe por causa do usuario que faz o obvio com o pacote: mover a pasta para
    C:\\Program Files. La a escrita exige elevacao, e o app falhava em silencio em
    tres lugares diferentes - preferencias engolidas, registros caindo na raiz,
    precos sem gravar. Descobrir isso na abertura e dizer com todas as letras e
    melhor que rodar meia hora e nao guardar nada."""

    destino = pasta or PASTA_DADOS
    teste = os.path.join(destino, '.teste_de_escrita')

    try:
        with open(teste, 'w', encoding='utf-8') as f:
            f.write('ok')
        os.remove(teste)
        return True, ''

    except OSError as e:
        return False, (
            f'Nao da para gravar em {destino} ({e.strerror or e}). '
            f'O programa precisa escrever os precos, os ajustes e os registros '
            f'ao lado dele. Mova a pasta para um lugar seu - a Area de Trabalho '
            f'ou Documentos, por exemplo - em vez de Arquivos de Programas.')

#region Configuracao compartilhada


def _achar_tesseract():
    """Caminho do tesseract.exe.

    Empacotado, procura primeiro o motor que veio junto, numa subpasta - e o que
    permite rodar em maquina que nunca instalou o Tesseract. Rodando pelo Python,
    NAO olha essa subpasta: um binario resolvido por caminho relativo dentro de
    uma pasta onde o navegador escreve (Downloads, por exemplo) seria executado
    so por ter o nome certo. Fora do pacote, so a instalacao do sistema serve.

    Devolve o caminho padrao mesmo quando nao acha nada: assim a checagem de
    ambiente reclama de um caminho que faz sentido para quem le a mensagem."""

    padrao = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

    candidatos = []

    if getattr(sys, 'frozen', False):
        candidatos.append(os.path.join(PASTA, 'tesseract', 'tesseract.exe'))

    candidatos += [padrao, r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe']

    for caminho in candidatos:
        if os.path.isfile(caminho):
            return caminho

    return padrao


TESSERACT = _achar_tesseract()

# --- Tempos ---------------------------------------------------------------
# Os scripts originais usavam sleep(0.3)+0.1+0.1 = 0.5s por clique, o que era 94%
# do tempo total. Aqui os cliques sao curtos e as esperas que importam sao
# adaptativas: o bot observa a tela mudar em vez de cronometrar.
#
# SE O JOGO COMECAR A PERDER CLIQUES, aumente ESPERA_CLIQUE primeiro.
ESPERA_MOUSE  = 0.05   # entre posicionar o cursor e apertar o botao
ESPERA_BOTAO  = 0.05   # entre apertar e soltar
ESPERA_CLIQUE = 0.12   # depois do clique, para a UI reagir

# Cada sondagem da tela custa ~17 ms na captura, o que ja da o ritmo do laco.
#
# NAO ADIANTA colocar um valor pequeno aqui achando que economiza CPU: a
# granularidade do timer do Windows e de ~15,6 ms, entao sleep(0.002) dorme 15 ms
# de verdade. Seria trocar 17 ms de captura por 32 ms de ciclo - a espera
# adaptativa inteira ficaria duas vezes mais lenta para poupar um nucleo.
SONDAGEM = 0.0

# Mas para DECLARAR A TELA PARADA o ritmo tem que ser outro, e este numero foi
# comprado caro. Sondando o mais rapido possivel, as 8 leituras iguais que o
# preco exige acontecem em ~50 ms - e 50 ms depois de um clique o jogo nem
# comecou a redesenhar a lista. "Estavel" virava "ninguem mexeu no ultimo
# piscar de olhos", e o bot lia a oferta anterior achando que era a proxima.
#
# Espacadas, as mesmas 8 leituras cobrem ~0,5 s de tela realmente parada.
#
# So onde a resposta importa: esperar_mudanca continua no ritmo rapido, porque
# ali quanto antes se percebe a mudanca, melhor.
SONDAGEM_LENTA = 0.05

# Quantas leituras identicas seguidas contam como "parou de mudar".
#
# 3 basta para animacao de dropdown, que e continua. Para o PRECO precisa de
# mais: a atualizacao da lista tem uma pausa no meio em que os pixels ficam
# parados com o numero ANTIGO na tela, e uma janela curta assentava nessa pausa,
# lendo o valor da combinacao anterior.
#
# Quantas leituras, porem, so vira tempo junto com o intervalo entre elas - ver
# SONDAGEM_LENTA acima.
LEITURAS_IGUAIS = 3
LEITURAS_IGUAIS_PRECO = 8

RETENTATIVA = 0.20       # base da espera crescente entre releituras
TENTATIVAS_VALOR = 5

SEGUNDOS_PARA_FOCAR = 5

# --- Ambiente -------------------------------------------------------------
# Tudo assume o jogo em tela cheia nesta resolucao, no monitor primario. Se
# qualquer premissa falhar, os cliques caem em outra janela.
RESOLUCAO_ESPERADA = (1920, 1080)
TITULO_JOGO = 'Albion Online Client'

# --- OCR ------------------------------------------------------------------
ESCALA_OCR = 4
CONFIG_OCR = '--psm 7 --oem 1 -c tessedit_char_whitelist=0123456789,'

# MARGEM BRANCA em volta da imagem antes de mandar para o tesseract.
#
# O tesseract usa a borda da captura para estimar a linha de base e a altura da
# fonte. Um recorte justo - que e o que uma coordenada calibrada a mao produz -
# nao lhe da nada disso, e ele decide a forma dos digitos com menos informacao.
# E ali que o 5 vira 9: os dois so diferem pela abertura no canto de cima, e
# essa e a primeira coisa que se perde quando a estimativa sai errada.
#
# Medido, nao suposto: numa bateria de 532 leituras com fundo em gradiente como
# o do jogo, a versao anterior errou 4 e esta errou 0. Custa 1 ms.
MARGEM_OCR = 12

# Abaixo deste tom um pixel conta como traco, e nao como fundo. Usado so para
# perceber que ha algo encostado na borda do recorte - nunca para decidir o que
# e traco na hora de ler, que medir provou ser pior que os meios-tons.
LIMIAR_TINTA = 110

# Abaixo disto a leitura vai para a escada de reserva, que exige duas variantes
# concordando. O tesseract devolve a confianca na MESMA chamada - perguntar nao
# custa OCR nenhum, e um numero que ele proprio marca como duvidoso e o unico
# aviso que existe antes do preco errado entrar no banco.
# 85, e nao 75: o 540.000 raspado que virou 940.000 voltou com 79. Um recorte
# bem enquadrado da 96 nesta fonte, entao a folga ate 85 e larga e nao custa
# nada; abaixo disso, a escada de reserva decide.
CONFIANCA_MINIMA = 85

# Escada de reserva, usada so quando a leitura principal nao devolve digito.
#
# O psm 7 faz analise de layout antes de reconhecer, e em algumas imagens essa
# etapa falha: o tesseract devolve '' ou ',' mesmo com o numero legivel. Como os
# precos do Mercado Negro sao estaveis, a mesma imagem se repete entre execucoes
# e a falha e deterministica. O psm 13 ("linha crua") pula a segmentacao e
# recupera todos os casos observados; mudar a escala tambem resolve.
#
# Exige DUAS variantes concordando: numero errado aqui vira decisao de compra ou
# preco de venda, e nesses casos celula vazia e melhor que numero duvidoso.
RESERVAS_OCR = [
    (4, '--psm 13 --oem 1 -c tessedit_char_whitelist=0123456789,'),
    (8, '--psm 7  --oem 1 -c tessedit_char_whitelist=0123456789,'),
    (2, '--psm 7  --oem 1 -c tessedit_char_whitelist=0123456789,'),
]
CONCORDANCIA_RESERVA = 2

# Faixa de sanidade: responde "isso e um numero plausivel?", nao define piso de
# preco. Fora dela a leitura e descartada.
PRECO_MIN = 100
PRECO_MAX = 500_000_000

MAX_LOG_BYTES = 2_000_000
MAX_HISTORICO_BYTES = 5_000_000

#endregion

#region Saida

# Mensagens emitidas antes de existir um destino de verdade.
#
# No executavel compilado com --windowed o sys.stdout e None, e print() falha.
# Sem esta fila, o aviso mais importante do arranque - "nao deu para criar a
# trava de execucao" - simplesmente desaparecia, justamente no caso em que ele
# explicaria por que duas instancias conseguiram abrir.
_pendentes = []
MAX_PENDENTES = 200


def _para_terminal(texto):

    if sys.stdout is None:
        if len(_pendentes) < MAX_PENDENTES:
            _pendentes.append(texto)
        return

    print(texto)


_destino = _para_terminal


def definir_destino(funcao):
    """Troca para onde relatar() escreve.

    O app grafico aponta para o painel de log; o terminal e o padrao. Sem isso os
    bots so funcionariam com um console anexado."""

    global _destino

    _destino = funcao if funcao is not None else _para_terminal

    if funcao is not None and _pendentes:
        # o que ficou sem destino durante o arranque chega agora, na ordem
        for texto in list(_pendentes):
            try:
                funcao(texto)
            except Exception:
                pass
        _pendentes.clear()


def relatar(texto=''):
    """Escreve uma linha de saida no destino atual."""

    try:
        _destino(texto)
    except Exception:
        # a saida nunca deve derrubar uma varredura
        try:
            _para_terminal(texto)
        except Exception:
            pass


def fmt(n):
    """12345 -> '12.345'. Aplicado so ao numero, nunca a frase inteira."""

    if n is None:
        return '-'

    return f'{n:,}'.replace(',', '.')

#endregion

#region Progresso

# Andamento estruturado, para a interface desenhar barra e faixa em vez de
# garimpar "[34/121]" no meio do texto do log.
_progresso = None


def definir_progresso(funcao):

    global _progresso

    _progresso = funcao


def progresso(feito=0, total=0, rotulo=''):
    """Informa o andamento. Ignorado quando ninguem esta ouvindo."""

    if _progresso is None:
        return

    try:
        _progresso(feito, total, rotulo)
    except Exception:
        pass


# Avisos curtos - um preco lido, uma compra fechada - para aparecerem POR CIMA
# DO JOGO, no canto de baixo.
#
# O log ja recebe tudo, mas o log esta na janela do aplicativo, que fica
# minimizada durante a varredura inteira. Enquanto o bot roda voce esta olhando
# para o jogo, e era exatamente ali que nao dava para conferir se o numero lido
# batia com o numero na tela. Descobrir uma leitura ruim so ao fim de quarenta
# minutos e descobrir tarde demais.
#
# CANAL SEPARADO DO LOG de proposito: no canto cabem cinco linhas, entao aqui so
# entra o que vale interromper o olho. Mandar o log inteiro para ca deixaria o
# canto rolando rapido demais para ser lido, que e o mesmo que nao mostrar nada.
_aviso = None


def definir_aviso(funcao):

    global _aviso

    _aviso = funcao


def avisar(titulo, valor=None, tom='primario'):
    """Um aviso de canto. Ignorado quando ninguem esta ouvindo."""

    if _aviso is None:
        return

    try:
        _aviso(titulo, valor, tom)
    except Exception:
        pass


# O PLACAR DA OPERACAO: a prata que ja saiu, o lucro que a compra promete, o que
# a venda ja trouxe. E o numero que se quer ver enquanto o bot roda, e no log ele
# fica enterrado entre as linhas de cada item.
_placar = None


def definir_placar(funcao):

    global _placar

    _placar = funcao


def placar(**valores):
    """Atualiza o placar. Ignorado quando ninguem esta ouvindo."""

    if _placar is None:
        return

    try:
        _placar(valores)
    except Exception:
        pass

#endregion

#region Contadores e cronometro

# Contadores por execucao, num dicionario em vez de globais por modulo.
#
# Motivo concreto: com `_contador = 0` no modulo, um `import` nao propaga
# reatribuicao - foi o que fez a correcao de reset valer para um bot e nao para
# os outros. Mutacao de dicionario atravessa modulos.
_contadores = {}

# Onde o tempo foi de fato. Compartilhado pelos tres bots: antes so o Atualizar
# media, e as decisoes de afinacao dos outros dois eram palpite.
_tempos = {}


def zerar_contadores():
    _contadores.clear()
    _tempos.clear()


def contar(chave, quantos=1):
    _contadores[chave] = _contadores.get(chave, 0) + quantos


def contador(chave):
    return _contadores.get(chave, 0)


def contadores():
    return dict(_contadores)


@contextmanager
def cronometro(chave):
    """Soma o tempo do bloco na chave. Use nos trechos que se quer afinar."""

    inicio = time.monotonic()

    try:
        yield
    finally:
        _tempos[chave] = _tempos.get(chave, 0.0) + (time.monotonic() - inicio)


def tempos():
    return dict(_tempos)

#endregion

#region Trava de execucao unica

ARQUIVO_TRAVA = os.path.join(PASTA_DADOS, '.bot_em_execucao')

# A autoridade e um mutex nomeado do Windows, valido para a sessao inteira do
# usuario. O arquivo continua existindo, mas so para dizer QUEM esta segurando.
#
# Duas razoes para ter trocado. A trava por PID nao cobria duas copias do
# programa extraidas em pastas diferentes - cada uma tinha o seu arquivo, as duas
# abriam, e acontecia exatamente o que a trava existe para impedir: dois
# programas disputando o mesmo cursor, um clicando na posicao que o outro acabou
# de definir, em botoes de confirmar compra. E o PID sobrevivente de um
# desligamento abrupto podia ser reciclado pelo Windows para outro processo, o
# que deixava o aplicativo permanentemente impedido de abrir, sem saida para quem
# nao sabe o que e um PID.
NOME_MUTEX = 'Local\\AlbionBM.execucao.unica'
_ERRO_JA_EXISTE = 183

_mutex = None


def _tomar_mutex():
    """True se este processo ficou com o mutex, False se outro tem, None se nao
    deu para saber."""

    global _mutex

    if _mutex is not None:
        return True

    try:
        import ctypes

        k32 = ctypes.WinDLL('kernel32', use_last_error=True)
        k32.CreateMutexW.restype = ctypes.c_void_p
        k32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]

        handle = k32.CreateMutexW(None, True, NOME_MUTEX)
        erro = ctypes.get_last_error()

        if not handle:
            return None

        if erro == _ERRO_JA_EXISTE:
            k32.CloseHandle(ctypes.c_void_p(handle))
            return False

        _mutex = handle
        return True

    except Exception:
        return None


def _soltar_mutex():

    global _mutex

    if _mutex is None:
        return

    try:
        import ctypes

        k32 = ctypes.windll.kernel32
        k32.ReleaseMutex(ctypes.c_void_p(_mutex))
        k32.CloseHandle(ctypes.c_void_p(_mutex))

    except Exception:
        pass

    _mutex = None


def _ler_trava():

    try:
        with open(ARQUIVO_TRAVA, encoding='utf-8') as f:
            partes = f.read().strip().split('|')

        return int(partes[0]), partes[1], partes[2]

    except Exception:
        return None


def _escrever_trava(nome):

    try:
        with open(ARQUIVO_TRAVA, 'w', encoding='utf-8') as f:
            f.write(f'{os.getpid()}|{nome}|{time.strftime("%H:%M:%S")}')
    except OSError as e:
        relatar(f'AVISO: nao deu para anotar a trava de execucao ({e})')


def dono_da_trava():
    """(nome, pid, horario) de quem esta segurando, ou None."""

    atual = _ler_trava()

    if atual is None:
        return None

    return atual[1], atual[0], atual[2]


def travar(nome):
    """Garante que so um bot rode por vez. Devolve (ok, mensagem).

    Os bots movem o mesmo cursor com SetCursorPos e clicam com mouse_event. Dois
    ao mesmo tempo intercalam esses comandos: o clique de um cai na posicao que o
    outro acabou de definir - em botoes de confirmar compra e venda."""

    tomou = _tomar_mutex()

    if tomou is False:

        atual = dono_da_trava()
        quem = (f'"{atual[0]}" (PID {atual[1]}, desde {atual[2]})'
                if atual else 'outra copia do programa')

        return False, (
            f'{quem} ja esta em execucao nesta sessao do Windows.\n\n'
            f'Os bots movem o mesmo cursor, entao dois ao mesmo tempo fazem os '
            f'cliques de um cair na posicao do outro.')

    if tomou is None:
        # sem mutex, resta o arquivo - e ele nao distingue PID reciclado, entao
        # so avisa em vez de impedir
        atual = dono_da_trava()

        if atual is not None and atual[1] != os.getpid():
            relatar(f'AVISO: existe uma trava de "{atual[0]}" (PID {atual[1]}, '
                    f'{atual[2]}) e nao deu para conferir se ainda vale.')

    _escrever_trava(nome)

    return True, ''


def destravar():
    """Solta a trava, se for desta execucao."""

    _soltar_mutex()

    atual = _ler_trava()

    if atual is not None and atual[0] != os.getpid():
        return

    try:
        os.remove(ARQUIVO_TRAVA)
    except OSError:
        pass

#endregion

#region Registro em arquivo


class _Tee:
    """Escreve na tela e no arquivo de log ao mesmo tempo."""

    def __init__(self, *destinos):
        self._destinos = destinos

    def write(self, texto):
        for d in self._destinos:
            try:
                d.write(texto)
            except Exception:
                pass
        return len(texto)

    def flush(self):
        for d in self._destinos:
            try:
                d.flush()
            except Exception:
                pass

    def isatty(self):
        return False


def abrir_log(nome_arquivo, redirecionar_stdout=True):
    """Liga o registro em arquivo. Devolve o arquivo aberto, ou None.

    Numa varredura de meia hora o resumo rola para fora do terminal. E nos bots
    que mexem com prata, o log e a unica forma de auditar depois quanto foi
    comprado ou vendido e a que preco.

    <redirecionar_stdout> False quando quem chama ja captura a saida - caso do
    app grafico, que recebe tudo por relatar()."""

    caminho = os.path.join(pasta_registro(), nome_arquivo)

    try:
        if os.path.exists(caminho) and os.path.getsize(caminho) > MAX_LOG_BYTES:
            os.replace(caminho, caminho + '.1')

        # buffering=1 (por linha) para o log sobreviver ao os._exit do F12
        log = open(caminho, 'a', encoding='utf-8', buffering=1)
        log.write(f'\n\n===== sessao {time.strftime("%Y-%m-%d %H:%M:%S")} '
                  f'- Albion BM {VERSAO} =====\n')

        if redirecionar_stdout and sys.__stdout__ is not None:
            sys.stdout = _Tee(sys.__stdout__, log)

        return log

    except Exception as e:
        relatar(f'AVISO: nao deu para abrir o log ({e}) - seguindo so na tela')
        return None


def fechar_log(log):

    if log is None:
        return

    try:
        if isinstance(sys.stdout, _Tee):
            sys.stdout = sys.__stdout__
        log.close()
    except Exception:
        pass

#endregion

#region Parada e pausa

# AS TRES TECLAS, E ELAS SAO TROCAVEIS.
#
# F11 e F12 sao o padrao daqui, mas nem todo teclado as tem livres: F11 e tela
# cheia em qualquer navegador, F12 abre o console. Quem joga com o navegador
# aberto atras precisa de outra combinacao, e ate aqui a unica saida era editar
# codigo.
#
# Os nomes vem do pynput e valem tanto para F1..F12 quanto para as teclas
# comuns; guardar o NOME e nao o objeto e o que deixa a escolha caber num JSON.
TECLAS_POSSIVEIS = ('f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9',
                    'f10', 'f11', 'f12', 'pause', 'insert', 'delete', 'home',
                    'end', 'page_up', 'page_down')

TECLA_PARADA = Key.f12
TECLA_PAUSA = Key.f11

# PULAR O ITEM ATUAL e seguir para o proximo.
#
# Existe para o item que trava a varredura sem falhar: o painel que nao abre, o
# menu que nao chega, a lista que nao filtra. Sem isto a unica saida e parar
# tudo e recomecar - perdendo o que ja foi lido, ou tendo que marcar "continuar
# de onde parou" e refazer a conta.
TECLA_PULAR = Key.f2

# Pedido de pular, atendido pelo laco no proximo ponto seguro.
pular_pedido = threading.Event()


def definir_teclas(pausa=None, parada=None, pular=None):
    """Troca as teclas por NOME. Devolve quantas foram trocadas.

    Nome invalido e ignorado em silencio de proposito: um ajuste salvo com uma
    tecla que a versao seguinte nao conhece nao pode impedir o programa de
    abrir."""

    global TECLA_PAUSA, TECLA_PARADA, TECLA_PULAR

    trocadas = 0

    for nome, atual in (('pausa', pausa), ('parada', parada), ('pular', pular)):

        if not atual:
            continue

        tecla = getattr(Key, str(atual).lower(), None)

        if tecla is None:
            continue

        if nome == 'pausa':
            TECLA_PAUSA = tecla
        elif nome == 'parada':
            TECLA_PARADA = tecla
        else:
            TECLA_PULAR = tecla

        trocadas += 1

    return trocadas


def nome_da_tecla(tecla):
    """'f11' a partir do objeto. Para a tela mostrar o que esta valendo."""

    return getattr(tecla, 'name', str(tecla)).replace('Key.', '')

# A pausa espera a unidade de trabalho atual terminar (um item, um ciclo). Nesse
# ponto o estado esta consistente e a retomada nao precisa desfazer nada.
pausado = threading.Event()

# PARADA EDUCADA: termine a unidade de trabalho, grave, e devolva o controle a
# quem chamou. E o botao Parar.
parada_pedida = threading.Event()

# ABORTO: pare ONDE ESTIVER, sem terminar o item. E o F12.
#
# A diferenca entre os dois e quando param, e nao o que acontece depois: os dois
# devolvem o controle com a janela aberta. O F12 nao fecha mais o programa - uma
# parada de emergencia que mata o aplicativo e uma parada que ninguem aperta com
# confianca, ainda mais quando o certo depois de um susto e olhar o log.
aborto_pedido = threading.Event()

# Nome antigo, mantido para nao quebrar quem importava daqui.
encerramento_pedido = aborto_pedido

# Trecho que nao pode ser interrompido no meio: gravar a planilha, confirmar uma
# compra ou uma venda. O F12 aguarda sair dele antes de encerrar.
secao_critica = threading.Event()

_listener = None


class Abortado(BaseException):
    """F12: larga o trabalho onde estiver e devolve o controle.

    Herda de BaseException e nao de Exception de proposito. Os bots tem
    `except Exception` em volta de cada item, para que um item problematico nao
    derrube uma varredura de meia hora - e um aborto pedido pelo usuario cairia
    nesse tratamento, seria registrado como "erro neste item" e a varredura
    seguiria para o proximo. Como KeyboardInterrupt, isto nao e um erro: e uma
    ordem."""


def deve_parar():
    """True quando o laco tem que terminar, por qualquer um dos dois motivos."""

    return parada_pedida.is_set() or aborto_pedido.is_set()


def checar_aborto():
    """Levanta Abortado se o F12 foi apertado. Chamar nos pontos de espera.

    NAO aborta dentro de uma secao critica. Gravar a planilha e um ZIP sendo
    escrito; confirmar uma compra sao dois cliques que precisam acontecer os
    dois. Sair no meio de qualquer um dos dois troca um susto por um estrago -
    entao ali a ordem espera o trecho terminar, que dura frações de segundo."""

    if aborto_pedido.is_set() and not secao_critica.is_set():
        raise Abortado()


def encerrar(codigo=1):
    """Mata o processo. So para o caso de o aborto nao ter sido obedecido.

    O F12 normal nao passa por aqui: ele levanta o Abortado e o programa segue
    aberto. Isto e a valvula do segundo F12, quando o primeiro nao surtiu efeito
    - se sobrasse nenhuma forma de matar um bot travado, a parada de emergencia
    deixaria de ser de emergencia."""

    try:
        if sys.stdout is not None:
            sys.stdout.flush()
        if sys.stderr is not None:
            sys.stderr.flush()
    except Exception:
        pass

    destravar()
    os._exit(codigo)


def _ao_teclar(tecla):

    if tecla == TECLA_PULAR:
        pular_pedido.set()
        relatar('>>> pular - seguindo para o proximo item <<<')
        return

    if tecla == TECLA_PAUSA:

        if pausado.is_set():
            pausado.clear()
            relatar('>>> F11 - retomando <<<')
        else:
            pausado.set()
            relatar('>>> F11 - pausa pedida, para ao terminar o item atual <<<')

        return

    if tecla != TECLA_PARADA:
        return

    # solta o botao do mouse, caso a parada caia entre o LEFTDOWN e o LEFTUP
    try:
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    except Exception:
        pass

    # SEGUNDO F12: o primeiro nao foi obedecido. Unico caminho que mata o
    # processo, e existe so para o bot que travou de um jeito que nenhuma
    # checagem alcanca.
    if aborto_pedido.is_set():
        relatar('>>> F12 de novo - o bot nao parou, encerrando o programa <<<')
        encerrar()
        return

    aborto_pedido.set()
    pausado.clear()       # abortar de dentro de uma pausa tem que funcionar

    if secao_critica.is_set():
        relatar('>>> F12 - parando assim que a operacao em andamento terminar <<<')
        return

    relatar('>>> F12 - parando agora <<<')


def instalar_teclas():
    """Liga F11 e F12. Idempotente.

    ARMAR SO ENQUANTO UM BOT RODA. F12 abre o DevTools no Chrome, no Edge e no
    Firefox; F11 e tela cheia em praticamente todo navegador. Com o listener
    ligado o tempo todo, apertar F12 em qualquer lugar do Windows encerrava o
    aplicativo na hora, via os._exit, com o app apenas aberto e ocioso."""

    global _listener

    if _listener is not None:
        return

    _listener = Listener(on_press=_ao_teclar)
    _listener.daemon = True
    _listener.start()


def parar_teclas():

    global _listener

    if _listener is None:
        return

    try:
        _listener.stop()
    except Exception:
        pass

    _listener = None


def teclas_ligadas():
    return _listener is not None


def limpar_sinais():
    """Zera pausa, parada e pulo. Chamar no inicio de cada execucao."""

    pular_pedido.clear()
    pausado.clear()
    parada_pedida.clear()
    aborto_pedido.clear()
    secao_critica.clear()


def aguardar_retomada(extras=()):
    """Bloqueia enquanto a pausa estiver ativa. Devolve (segundos, pode_seguir).

    Uma copia so, aqui. Havia tres quase identicas - uma por bot - divergindo no
    tipo de retorno, que e exatamente a duplicacao que este modulo existe para
    eliminar.

    Durante a pausa o usuario tipicamente alterna para outra janela, entao na
    retomada o foco e conferido de novo: seguir sem isso mandaria os cliques para
    o programa errado."""

    relatar('')
    relatar('  PAUSADO. F11 retoma, F12 para.')

    for linha in extras:
        relatar(f'  {linha}')

    relatar('')

    # NO CANTO TAMBEM. Quem aperta F11 esta olhando para o jogo, nao para a
    # janela do programa - que passa a varredura inteira minimizada. Um aviso que
    # so aparece no log e um aviso que nao chega.
    avisar('PAUSADO — F11 retoma', 'F12 para', 'aviso')

    inicio = time.monotonic()

    while pausado.is_set():

        checar_aborto()

        if deve_parar():
            return time.monotonic() - inicio, False

        time.sleep(0.2)

    pausa = time.monotonic() - inicio

    relatar(f'  retomando apos {pausa / 60:.1f} min de pausa')
    avisar('retomando', f'{pausa / 60:.1f} min parado', 'ok')

    problemas = sem_foco()

    if problemas:
        relatar('  ENCERRANDO - o jogo nao esta em primeiro plano:')
        for p in problemas:
            relatar(f'    - {p}')
        relatar('')
        return pausa, False

    return pausa, True

#endregion

#region Ciclo de vida de uma execucao


def iniciar_execucao(nome, arquivo_log=None, redirecionar_stdout=True, teclas=True):
    """Prepara uma execucao. Devolve (ok, mensagem, log).

    Junta o que todo ponto de entrada precisa fazer na mesma ordem: pegar a
    trava, zerar contadores e sinais da execucao anterior, ligar F11/F12 e abrir
    o log. Existe para o app e os tres bots nao repetirem isso quatro vezes,
    cada um esquecendo um passo diferente.

    <teclas> False para NAO armar F11 e F12 - o app grafico toma a trava quando
    abre a janela, mas so arma os atalhos quando um bot comeca de fato.

    Com <ok> False nao ha nada a liberar: a trava nao foi tomada."""

    ok, mensagem = travar(nome)

    if not ok:
        return False, mensagem, None

    zerar_contadores()
    limpar_sinais()

    if teclas:
        instalar_teclas()

    log = abrir_log(arquivo_log, redirecionar_stdout) if arquivo_log else None

    return True, '', log


def terminar_execucao(log=None):
    """Desfaz o iniciar_execucao. Seguro de chamar mais de uma vez."""

    parar_teclas()
    fechar_captura()
    fechar_log(log)
    destravar()

#endregion

#region Ambiente

# hwnd do jogo, guardado para a checagem barata de foco. Descobrir a janela custa
# um EnumWindows; comparar com a janela em primeiro plano custa microssegundos.
_hwnd_jogo = None


def janela_do_jogo():
    """(hwnd, rect) da janela do cliente do Albion, ou None."""

    global _hwnd_jogo

    achadas = []

    def visitar(hwnd, _):
        try:
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd) == TITULO_JOGO:
                achadas.append((hwnd, win32gui.GetWindowRect(hwnd)))
        except Exception:
            pass
        return True

    try:
        win32gui.EnumWindows(visitar, None)
    except Exception:
        return None

    if not achadas:
        _hwnd_jogo = None
        return None

    _hwnd_jogo = achadas[0][0]

    return achadas[0]


def jogo_em_foco():
    """True se o jogo esta em primeiro plano AGORA. Barato o bastante para o laco.

    Existe porque o foco so era conferido antes do laco e na volta de uma pausa.
    Uma varredura de 121 itens dura meia hora e passa por ~1.600 cliques sem
    reconferir para onde estao indo: se o jogo cai, se o Windows troca o foco por
    uma notificacao, ou se o usuario alterna de janela sem pausar, o bot segue
    digitando nomes de item dentro de outro programa - o que ja aconteceu uma vez
    neste projeto."""

    try:
        # janela_do_jogo() e quem atualiza o _hwnd_jogo; aqui so se le
        if _hwnd_jogo is None or not win32gui.IsWindow(_hwnd_jogo):
            if janela_do_jogo() is None:
                return False

        return _hwnd_jogo == win32gui.GetForegroundWindow()

    except Exception:
        # sem conseguir verificar, nao vale abortar uma varredura de meia hora
        return True


def verificar_ambiente(exigir_foco):
    """Confere as premissas das coordenadas. Devolve a lista de problemas.

    Comecar com o jogo fora de foco nao e so perda de tempo: os cliques e a
    digitacao vao para outro programa. Aconteceu de verdade numa das primeiras
    execucoes, quando o bot digitou nomes de item dentro de outra janela."""

    problemas = []

    largura = win32api.GetSystemMetrics(0)
    altura = win32api.GetSystemMetrics(1)

    if (largura, altura) != RESOLUCAO_ESPERADA:
        problemas.append(
            f'tela primaria e {largura}x{altura}, mas as coordenadas foram '
            f'medidas em {RESOLUCAO_ESPERADA[0]}x{RESOLUCAO_ESPERADA[1]}')

    if not os.path.isfile(TESSERACT):
        problemas.append(f'tesseract nao encontrado em {TESSERACT}')

    janela = janela_do_jogo()

    if janela is None:
        problemas.append(f'janela "{TITULO_JOGO}" nao encontrada - o jogo esta aberto?')

    else:
        hwnd, rect = janela

        if rect != (0, 0) + RESOLUCAO_ESPERADA:
            problemas.append(
                f'a janela do jogo esta em {rect}, e as coordenadas assumem '
                f'(0, 0, {RESOLUCAO_ESPERADA[0]}, {RESOLUCAO_ESPERADA[1]})')

        if exigir_foco and hwnd != win32gui.GetForegroundWindow():
            atual = win32gui.GetWindowText(win32gui.GetForegroundWindow())
            problemas.append(
                f'o jogo nao esta em primeiro plano (esta "{atual}") - '
                f'os cliques iriam para essa janela')

    return problemas


def sem_foco():
    """Apenas os problemas de foco, para abortar antes de tocar no mouse."""

    return [p for p in verificar_ambiente(exigir_foco=True) if 'primeiro plano' in p]


def focar_jogo():
    """Traz a janela do jogo para a frente. True se conseguiu.

    Usado pelo app grafico: apos o usuario clicar em iniciar, o foco esta na
    janela do app, e sem trazer o jogo para frente a varredura abortaria."""

    janela = janela_do_jogo()

    if janela is None:
        return False

    try:
        win32gui.SetForegroundWindow(janela[0])
        time.sleep(0.3)
        return janela[0] == win32gui.GetForegroundWindow()
    except Exception:
        return False

#endregion

#region Tela


def definir_velocidades(clique=None, escrita=None, leitura=None):
    """Troca as pausas fixas, em MILISSEGUNDOS. Ver o bloco de constantes.

    O bot de referencia expoe estes tres numeros na tela de configuracao, e faz
    sentido: eles sao o unico ajuste que compensa uma maquina lenta ou um ping
    alto sem mexer em mais nada. Fora da faixa o valor e ignorado - 0 ms de
    clique nao acelera coisa nenhuma e faz o jogo perder eventos."""

    global ESPERA_CLIQUE, ESPERA_MOUSE, LEITURAS_IGUAIS_PRECO

    if clique is not None and 10 <= clique <= 2000:
        ESPERA_CLIQUE = clique / 1000

    if escrita is not None and 10 <= escrita <= 2000:
        ESPERA_MOUSE = escrita / 1000

    # "Price Listen Duration" na tela deles: quanto tempo a regiao do preco
    # precisa ficar parada antes de valer. Aqui isso e um numero de LEITURAS
    # iguais, e nao um relogio - mas a grandeza que o usuario quer controlar e a
    # mesma, entao a conversao acontece aqui e nao na cabeca dele.
    if leitura is not None and 50 <= leitura <= 3000:
        LEITURAS_IGUAIS_PRECO = max(3, int(leitura / 1000 / SONDAGEM_LENTA))


def clicar(pos, espera=None):
    """Clique com o botao esquerdo em pos = {'x':..., 'y':...}.

    <espera> e a pausa depois do clique. Passe 0 quando a proxima coisa for uma
    espera adaptativa: ela ja sonda a tela imediatamente, e a pausa fixa em cima
    seria latencia pura."""

    if espera is None:
        espera = ESPERA_CLIQUE

    # o F12 e atendido ANTES de mexer no mouse, nunca entre o apertar e o soltar
    checar_aborto()

    win32api.SetCursorPos((pos['x'], pos['y']))
    time.sleep(ESPERA_MOUSE)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, pos['x'], pos['y'], 0, 0)
    time.sleep(ESPERA_BOTAO)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, pos['x'], pos['y'], 0, 0)

    if espera:
        time.sleep(espera)


def apontar(pos):
    """Poe o cursor em cima de <pos> SEM clicar.

    Existe por causa do menu em cascata do mercado: os submenus dele abrem com o
    mouse parado em cima do pai, e nao com clique. E a primeira interacao deste
    programa que nao e um clique.

    O cursor SALTA para o destino - o SetCursorPos nao varre o caminho. Isso aqui
    e uma sorte, e nao um detalhe: arrastando o ponteiro de "Weapons" ate o
    submenu dele, ele passaria por cima de "Chest Armor" no meio do caminho, e o
    menu trocaria de galho embaixo do bot."""

    checar_aborto()

    win32api.SetCursorPos((pos['x'], pos['y']))


def rolar(pos, cliques):
    """Gira a roda do mouse em cima de <pos>. <cliques> positivo desce a lista.

    Um evento por clique da roda, com folga entre eles: varios cliques num
    evento so, o jogo pode contar como um."""

    checar_aborto()

    win32api.SetCursorPos((pos['x'], pos['y']))
    time.sleep(ESPERA_MOUSE)

    for _ in range(abs(int(cliques))):
        checar_aborto()
        win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL, 0, 0,
                             -120 if cliques > 0 else 120, 0)
        time.sleep(ESPERA_MOUSE)


def arrastar(de, para, passos=10):
    """Segura o botao em <de>, leva o cursor ate <para> e solta.

    Em passos, e nao num salto: o jogo so arrasta o que viu o cursor percorrer.
    O botao e SEMPRE solto - um F12 no meio deixaria o mouse preso apertado."""

    checar_aborto()

    win32api.SetCursorPos((de['x'], de['y']))
    time.sleep(ESPERA_MOUSE)
    win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, de['x'], de['y'], 0, 0)

    try:
        time.sleep(ESPERA_BOTAO)

        for i in range(1, passos + 1):
            x = round(de['x'] + (para['x'] - de['x']) * i / passos)
            y = round(de['y'] + (para['y'] - de['y']) * i / passos)
            win32api.SetCursorPos((x, y))
            time.sleep(0.02)

        time.sleep(ESPERA_BOTAO)

    finally:
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, para['x'], para['y'], 0, 0)


_teclado = Controller()


def digitar(texto):
    """Digita <texto> onde estiver o foco."""

    checar_aborto()

    _teclado.type(str(texto))


def limpar_campo():
    """Seleciona tudo e apaga, no campo que estiver com o foco.

    Digitar num campo que ja tem numero CONCATENA em vez de substituir: pedir 899
    num campo que mostrava 54 daria 54899, e o jogo aceitaria - e a ordem sairia
    por um preco setenta vezes maior que o pretendido.

    Ctrl+A e Delete, e nao apagar tecla a tecla: o campo pode ter qualquer numero
    de digitos, e contar quantos apagar seria mais uma coisa para errar."""

    checar_aborto()

    with _teclado.pressed(Key.ctrl):
        _teclado.press('a')
        _teclado.release('a')

    _teclado.press(Key.delete)
    _teclado.release(Key.delete)


# Uma instancia de captura POR THREAD. O mss guarda um contexto de dispositivo do
# Windows e nao promete ser seguro entre threads - e aqui o objeto nascia na
# thread da interface e era usado na thread do bot.
_local = threading.local()


def _captura():

    sct = getattr(_local, 'sct', None)

    if sct is None:
        sct = mss.mss()
        _local.sct = sct

    return sct


def _tirar(regiao):
    """Captura crua de uma regiao (x1, y1, x2, y2)."""

    return _captura().grab({
        'left': regiao[0],
        'top': regiao[1],
        'width': regiao[2] - regiao[0],
        'height': regiao[3] - regiao[1],
    })


def assinatura(regiao):
    """Bytes crus de uma regiao da tela, para detectar que ela mudou.

    Usa mss e nao PIL.ImageGrab: 17 ms contra 35 ms por captura, e essa funcao
    roda muitas vezes por espera."""

    return bytes(_tirar(regiao).raw)


def capturar(regiao):
    """Imagem PIL de uma regiao, pelo mss.

    O ImageGrab.grab(regiao) do Pillow captura os 1920x1080 INTEIROS no Windows e
    so depois recorta - dois megapixels copiados para aproveitar mil e
    seiscentos. O mss recorta na origem. Os bytes resultantes sao os mesmos: BGRX
    convertido para RGB da os mesmos canais que o ImageGrab entrega."""

    tiro = _tirar(regiao)

    return Image.frombytes('RGB', tiro.size, tiro.bgra, 'raw', 'BGRX')


def fechar_captura():

    sct = getattr(_local, 'sct', None)

    if sct is None:
        return

    try:
        sct.close()
    except Exception:
        pass

    _local.sct = None


def esperar_mudanca(regiao, antes, limite):
    """Espera a regiao ficar diferente de <antes>. True se mudou."""

    fim = time.monotonic() + limite

    while time.monotonic() < fim:

        checar_aborto()

        if assinatura(regiao) != antes:
            return True

        time.sleep(SONDAGEM)

    return False


def parecido(a, b, tolerancia=0.03):
    """True quando duas assinaturas da mesma regiao mostram quase a mesma coisa.

    Igualdade byte a byte nao serve para perguntar "a tela VOLTOU a ser o que
    era": um pixel de antialiasing ou de brilho animado no fundo ja a derruba.
    Conta os bytes que mudaram de verdade (mais de 24 tons) e aceita ate
    <tolerancia> deles - uma lista de dropdown aberta muda bem mais que isso."""

    if len(a) != len(b) or not a:
        return a == b

    diferentes = sum(1 for x, y in zip(a, b) if abs(x - y) > 24)

    return diferentes / len(a) <= tolerancia


def esperar_parecido(regiao, alvo, limite, tolerancia=0.03):
    """Espera a regiao voltar a parecer com <alvo>. True se voltou."""

    fim = time.monotonic() + limite

    while True:

        checar_aborto()

        if parecido(assinatura(regiao), alvo, tolerancia):
            return True

        if time.monotonic() >= fim:
            return False

        time.sleep(SONDAGEM_LENTA)


def esperar_estavel(regiao, limite, exigidas=None, intervalo=None):
    """Espera a regiao parar de mudar, ou seja, a animacao terminar.

    <intervalo> e o espaco entre uma leitura e a seguinte. Ele e que transforma
    "N leituras iguais" em tempo de tela parada: no ritmo rapido as 8 leituras
    do preco cabem em 50 ms, que nao provam nada sobre uma lista que o jogo leva
    quase um segundo para redesenhar. Passe SONDAGEM_LENTA onde ler cedo demais
    custa dinheiro."""

    if exigidas is None:
        exigidas = LEITURAS_IGUAIS

    if intervalo is None:
        intervalo = SONDAGEM

    fim = time.monotonic() + limite
    anterior = assinatura(regiao)
    iguais = 0

    while time.monotonic() < fim:

        checar_aborto()

        time.sleep(intervalo)
        atual = assinatura(regiao)

        if atual == anterior:
            iguais += 1
            if iguais >= exigidas:
                return True
        else:
            iguais = 0
            anterior = atual

    return False


def contagem_para_focar(segundos=None):
    """Contagem para o usuario alternar para o jogo. Vai so para a tela.

    Usa \\r, entao nao passa por relatar(): no log viraria uma linha unica com
    todos os segundos emendados."""

    if segundos is None:
        segundos = SEGUNDOS_PARA_FOCAR

    for s in range(segundos, 0, -1):
        try:
            sys.__stdout__.write(f'  comecando em {s}...   \r')
            sys.__stdout__.flush()
        except Exception:
            pass
        time.sleep(1)

    try:
        sys.__stdout__.write(' ' * 30 + '\n')
        sys.__stdout__.flush()
    except Exception:
        pass

#endregion

#region OCR

_ultima_imagem = None
_ultimo_texto = ''


def numero_valido(texto):
    """Extrai o numero do texto do OCR, ou None se nao houver um plausivel."""

    digitos = ''.join(c for c in texto if c.isdigit())

    if not digitos:
        return None

    valor = int(digitos)

    if not (PRECO_MIN <= valor <= PRECO_MAX):
        return None

    return valor


# Um numero como o jogo escreve: 25.000, 25,000 ou 25000.
_NUMERO_ESCRITO = re.compile(r'\d{1,3}(?:[.,]\d{3})+|\d+')


def valor_do_dialogo(texto):
    """O preco de um dialogo de confirmacao de VENDA, ou None.

    NAO JUNTA OS DIGITOS DO TEXTO INTEIRO, como o numero_valido. "Quer vender 1
    unidades de ... por 25.000 de prata?" daria 125.000 - um valor MAIOR que o
    de verdade, e na venda maior e o lado perigoso: passa por cima do piso e
    vende barato. Aqui cada numero escrito vale por si, e fica o maior que for
    plausivel. Se o OCR partir o preco em dois, sai um numero MENOR, e o piso
    recusa - o lado seguro."""

    valores = [int(g.replace('.', '').replace(',', ''))
               for g in _NUMERO_ESCRITO.findall(texto or '')]

    valores = [v for v in valores if PRECO_MIN <= v <= PRECO_MAX]

    return max(valores) if valores else None


# O preco no texto do dialogo: entre o "for"/"por" e o "Silver"/"prata".
_PRECO_NO_DIALOGO = re.compile(
    r'\b(?:for|por)\s+(\d[\d.,\s]*?)\s*(?:silver|de\s+prata|prata)', re.IGNORECASE)


def preco_do_dialogo(texto):
    """O preco de um dialogo de confirmacao, de COMPRA ou de VENDA, ou None.

    "Buy 1 pieces of Grandmaster's Brawler Gloves for 255,988 Silver?" - o
    numero_valido juntava todos os digitos do texto e lia 1.255.988: o "1" da
    quantidade colado no preco. Na compra isso passava do teto, e o bot clicava
    em "No" em toda compra na hora.

    Aqui o preco e o que esta entre "for"/"por" e "Silver"/"prata", e so ele -
    espacos que o OCR enfie no meio do numero ("255, 988") nao o partem. Sem
    esse trecho no texto, vale o maior numero escrito (valor_do_dialogo)."""

    achado = _PRECO_NO_DIALOGO.search(texto or '')

    if achado:
        digitos = ''.join(c for c in achado.group(1) if c.isdigit())

        if digitos and PRECO_MIN <= int(digitos) <= PRECO_MAX:
            return int(digitos)

    return valor_do_dialogo(texto)


def tinta_na_borda(bruta):
    """True quando ha traco colado na primeira coluna do recorte.

    NAO CORTA NADA, E ISTO E O PONTO. A versao que cortava partia de uma
    suposicao errada - "recorte bem enquadrado tem fundo na primeira coluna" - e
    na tela do jogo os digitos ENCOSTAM na borda esquerda. O corte comia o
    primeiro digito da maioria dos precos, trocando um numero errado e raro por
    um numero errado, menor e frequente. Menor e pior: passa pela barreira de
    plausibilidade com mais facilidade e vira decisao de compra.

    O que sobrou e o aviso. Tinta na borda pode ser o icone da moeda invadindo o
    recorte ou o primeiro digito encostado - daqui nao da para distinguir os
    dois, e fingir que da foi o erro. Entao a leitura nao e descartada nem
    aceita sozinha: ela cai na escada de reserva, que exige duas variantes
    concordando, e o contador diz quantas vezes isso aconteceu.

    Se este contador vier alto, o recorte precisa de calibragem - e a imagem
    salva em falhas_conferidor mostra qual dos dois casos e."""

    cinza = ImageOps.autocontrast(bruta.convert('L'))

    _, altura = cinza.size
    pixels = cinza.load()

    return any(pixels[0, y] < LIMIAR_TINTA for y in range(altura))


def _preparar(bruta, escala=ESCALA_OCR):
    """A captura pronta para o tesseract: contraste esticado, ampliada, com folga.

    O AUTOCONTRAST vem antes de ampliar. O fundo da lista do jogo e um gradiente,
    entao o mesmo digito chega ao tesseract com um cinza no alto da caixa e outro
    embaixo; esticar a faixa de tons primeiro tira essa variacao do caminho.

    A AMPLIACAO CONTINUA SENDO LANCZOS. Chegar aqui com limiar e repeticao de
    pixel parece mais limpo e e muito pior - na mesma bateria de 532 leituras,
    75 erros contra nenhum. Os meios-tons da borda de um traco de 14 px sao
    informacao, e nao sujeira: e deles que o tesseract tira a forma."""

    cinza = ImageOps.autocontrast(bruta.convert('L'))

    grande = cinza.resize((cinza.width * escala, cinza.height * escala),
                          Image.LANCZOS)

    return ImageOps.expand(grande, border=MARGEM_OCR, fill=255)


def _reconhecer_com_confianca(img, config):
    """(texto, confianca) numa chamada so.

    O image_to_data devolve o mesmo reconhecimento do image_to_string mais a
    confianca de cada pedaco. Nao e uma segunda passada: e a mesma, pedindo a
    saida completa."""

    contar('ocr_chamadas')

    with cronometro('ocr'):
        dados = pytesseract.image_to_data(
            img, config=config, output_type=pytesseract.Output.DICT)

    partes = []
    confiancas = []

    for texto, conf in zip(dados['text'], dados['conf']):

        if not str(texto).strip():
            continue

        partes.append(str(texto).strip())

        try:
            confiancas.append(float(conf))
        except (TypeError, ValueError):
            pass

    return ' '.join(partes), (min(confiancas) if confiancas else 0.0)


def _reconhecer(img, config):
    """Uma chamada ao tesseract, cronometrada e contada.

    Cada chamada e um PROCESSO NOVO: o pytesseract grava a imagem num arquivo
    temporario, executa o tesseract.exe e le a saida. Sao 80 a 200 ms de custo
    fixo. Medir isso e o pre-requisito de qualquer decisao sobre trocar a ponte
    por uma que chame a libtesseract dentro do processo."""

    contar('ocr_chamadas')

    with cronometro('ocr'):
        return pytesseract.image_to_string(img, config=config)


def _ler_com_reservas(bruta):
    """Tenta as configuracoes de reserva na mesma captura.

    So aceita quando CONCORDANCIA_RESERVA variantes chegam ao mesmo numero."""

    votos = {}

    for escala, cfg in RESERVAS_OCR:

        img = _preparar(bruta, escala)
        valor = numero_valido(_reconhecer(img, cfg))

        if valor is None:
            continue

        votos[valor] = votos.get(valor, 0) + 1

        if votos[valor] >= CONCORDANCIA_RESERVA:
            contar('reservas_usadas')
            return valor

    if votos:
        # alguma variante leu algo, mas nenhuma dupla concordou
        contar('reservas_discordaram')

    return None


def ler_numero(regiao):
    """Le um numero de uma regiao da tela. None quando nao ha nada confiavel.

    None tambem significa, legitimamente, que nao ha valor ali - uma lista de
    ofertas vazia, por exemplo."""

    global _ultima_imagem, _ultimo_texto

    bruta = capturar(regiao)

    texto, confianca = _reconhecer_com_confianca(_preparar(bruta), CONFIG_OCR)

    if tinta_na_borda(bruta):
        # Algo esta colado na borda esquerda: ou o icone da moeda invadiu o
        # recorte, ou o primeiro digito esta encostado nela. Nao da para saber
        # qual - e por isso esta leitura nao vale sozinha.
        contar('borda_suja')
        confianca = min(confianca, CONFIANCA_MINIMA - 1)

    _ultima_imagem = bruta
    _ultimo_texto = texto

    valor = numero_valido(texto)

    # UM NUMERO QUE O PROPRIO TESSERACT MARCA COMO DUVIDOSO vale menos que
    # nenhum: ele nao levanta erro, nao parece errado no log, e vira decisao de
    # compra. Nesse caso a escada de reserva decide, e ela so aceita com duas
    # variantes concordando.
    if valor is not None and confianca >= CONFIANCA_MINIMA:
        return valor

    if valor is not None:
        contar('leituras_pouco_confiaveis')

    return _ler_com_reservas(bruta)


def ler_numero_novo(regiao, anterior):
    """Le insistindo enquanto vier vazio ou igual ao <anterior>. None se desistir.

    A espera por pixels nao basta: ao trocar um filtro a lista se redesenha, os
    bytes mudam, mas o numero exibido continua o antigo por alguns quadros.
    Comparar o VALOR e o unico sinal confiavel de que a troca chegou na tela.

    A espera entre tentativas e crescente: o caso comum resolve na primeira e
    custa pouco, e os teimosos ganham tempo de verdade.

    DESISTIR DEVOLVE VAZIO, E NAO O VALOR TEIMOSO. Esta linha era a fuga por onde
    o preco errado entrava: gastas as cinco tentativas, a versao anterior
    devolvia o numero mesmo ele continuando igual ao anterior - isto e, mesmo com
    a evidencia de que a tela NUNCA mudou.

    Foi o que gravou o preco do T4.2 na celula do T5.2. A troca de grau nao tinha
    chegado na lista dentro dos tres segundos de insistencia, e o que estava na
    tela era a combinacao de antes; o programa preferia entregar aquilo a admitir
    que nao viu.

    Vazio aqui nao e perda: a combinacao fica sem preco, a repescagem no fim da
    varredura tenta de novo com o mercado ainda aberto, e a tela mostra "sem
    dado" em vez de um numero que parece verdade. Um preco errado nao tem
    conserto depois - ele vira decisao de compra.

    O caso legitimo de duas combinacoes com o MESMO preco existe e cai aqui
    junto. E raro entre graus vizinhos, custa uma releitura na repescagem, e o
    lado errado desse acerto de contas e o que produz compra errada."""

    valor = ler_numero(regiao)
    tentativa = 0

    for _ in range(TENTATIVAS_VALOR):

        # vazio e "igual ao anterior" sao o mesmo sintoma - a tela nao terminou
        # de atualizar. Tratar so o segundo deixava o primeiro sair na hora.
        if valor is not None and valor != anterior:
            return valor

        checar_aborto()

        contar('leituras_refeitas')
        tentativa += 1
        time.sleep(RETENTATIVA * tentativa)
        valor = ler_numero(regiao)

    if valor is not None and valor == anterior:
        contar('tela_nao_trocou')
        return None

    return valor


def ultima_captura():
    """(imagem, texto) da ultima leitura, para diagnostico."""

    return _ultima_imagem, _ultimo_texto


# --- Leitura de texto -----------------------------------------------------
# Sem whitelist: aqui o alvo e o NOME de um item, nao um numero. Escala menor que
# a dos precos porque o texto e maior na tela e ampliar demais so custa tempo.
# psm 6 ("bloco de texto"), e NAO psm 7 ("uma linha so").
#
# O nome do item QUEBRA EM DUAS LINHAS na tela: "Cajado Amaldicoado do" em cima,
# "Adepto" embaixo. Com psm 7 o tesseract tenta ler as duas como uma linha unica
# e devolve lixo - do nome acima ele leu "age do 29d23h". Com psm 6 ele le as
# duas linhas, e o normalizar() junta tudo numa frase que bate certo.
CONFIG_TEXTO = '--psm 6 --oem 1'
ESCALA_TEXTO = 3

# Quantas palavras de sujeira o OCR pode inventar ANTES do nome do item.
DESLOCAMENTO_MAXIMO = 2


def ler_texto(regiao):
    """Le texto de uma regiao. String vazia quando nao sai nada.

    Usado para confirmar que a busca do jogo filtrou para o item pedido - o
    preco mudar nao prova nada sobre QUAL item esta na tela."""

    global _ultima_imagem, _ultimo_texto

    bruta = capturar(regiao)

    img = bruta.resize((bruta.width * ESCALA_TEXTO, bruta.height * ESCALA_TEXTO),
                       Image.LANCZOS)

    texto = _reconhecer(img.convert('L'), CONFIG_TEXTO)

    _ultima_imagem = bruta
    _ultimo_texto = texto

    return texto.strip()


def normalizar(texto):
    """Minusculas, sem acento, so letras e numeros.

    Comparar nome lido com nome buscado exige isto: o OCR erra acento com
    facilidade, e a planilha e o jogo nem sempre usam a mesma grafia."""

    import unicodedata

    sem_acento = unicodedata.normalize('NFKD', str(texto))
    sem_acento = ''.join(c for c in sem_acento if not unicodedata.combining(c))

    # Tudo que nao e letra ou numero vira ESPACO, e nao e apagado. O nome do item
    # quebra em duas linhas na tela, e apagar a quebra colava as duas palavras
    # vizinhas: "Cajado Amaldicoado do" mais "Adepto" virava "...doadepto", e a
    # comparacao palavra a palavra nao reconhecia mais o "do".
    limpo = ''.join(c if c.isalnum() else ' ' for c in sem_acento.lower())

    return ' '.join(limpo.split())


def parece_o_mesmo_item(lido, esperado, minimo=0.75):
    """True se o texto lido corresponde ao nome esperado.

    O NOME BUSCADO E UM PREFIXO DO NOME REAL. A planilha guarda "Espada Larga
    do" - truncado no "do" de proposito, porque a busca do jogo e alfabetica e o
    nome curto traz outro item na frente - enquanto a tela mostra "Espada Larga
    do Alvorecer". Entao a regra e casar o COMECO, e nao o texto inteiro.

    Nao exige igualdade: o OCR de um nome erra letras com frequencia, e exigir
    exatidao transformaria a conferencia num bloqueio permanente. Compara por
    semelhanca, deslizando uma janela do tamanho do nome buscado - assim um
    "T6" ou um icone lido como letra na frente do nome nao derrubam a
    comparacao.

    SOBREPOSICAO DE PALAVRAS NAO SERVE, e isto custou um teste para descobrir:
    por aquela regra "Maca do" casava com "Maca pesada do Vale", porque a unica
    palavra longa de "Maca do" aparece la dentro. Num bot que compra, aceitar o
    item errado e o erro que custa caro.

    Devolve None quando nao ha texto suficiente para julgar, que e diferente de
    False: ausencia de evidencia nao e evidencia de erro."""

    from difflib import SequenceMatcher

    palavras_lidas = normalizar(lido).split()
    palavras_alvo = normalizar(esperado).split()

    if (len(''.join(palavras_lidas)) < 3 or len(''.join(palavras_alvo)) < 3):
        return None

    # a tela mostra menos palavras do que o nome procurado tem: nao e ele
    if len(palavras_lidas) < len(palavras_alvo):
        return False

    def casa_a_partir_de(inicio):
        """Todas as palavras do alvo batem, em sequencia, a partir daqui?

        Palavra por palavra, NA POSICAO. Comparar o texto corrido nao serve, e
        este e o caso que derruba qualquer regra frouxa: "Cajado Amaldicoado
        do" e "Cajado Amaldicoado ELEVADO do" tem 90% dos caracteres em comum e
        sao itens diferentes, com precos diferentes. A palavra inserida no meio
        empurra tudo que vem depois, e so a comparacao posicional percebe.

        0.75 por palavra: "iarga" no lugar de "larga" - um L lido como i, o erro
        mais comum do OCR nesta fonte - da 0.80 e precisa passar. Ja "do" contra
        "de" da 0.50 e precisa falhar, porque nas palavras curtas uma letra e
        metade do sentido."""

        if inicio + len(palavras_alvo) > len(palavras_lidas):
            return False

        return all(
            SequenceMatcher(None, palavras_lidas[inicio + i], alvo).ratio() >= minimo
            for i, alvo in enumerate(palavras_alvo))

    # Ate DESLOCAMENTO_MAXIMO palavras de sujeira antes do nome. O recorte pega
    # so a coluna do nome, mas a borda de um icone pode virar uma letra solta - e
    # perder o item por causa de um "K" inventado seria uma pena.
    #
    # Isto NAO enfraquece a protecao do "Elevado": la a palavra a mais esta no
    # MEIO do nome, e nenhum deslocamento do inicio faz o resto se alinhar.
    return any(casa_a_partir_de(i) for i in range(DESLOCAMENTO_MAXIMO + 1))


def salvar_diagnostico(pasta, base, regiao=None, extras=None, escala=6, maximo=20):
    """Salva a imagem QUE FALHOU e o texto do OCR, para inspecao.

    Guarda a captura que o ler_numero usou, nao uma nova: a tela assenta em
    seguida e o PNG sairia legivel, fazendo a falha parecer inexplicavel - erro
    que custou tres diagnosticos errados antes de ser percebido."""

    if contador('diagnosticos') >= maximo:
        return None

    contar('diagnosticos')

    try:
        destino = pasta_registro(pasta)

        seguro = ''.join(c if c.isalnum() or c in ' -_.' else '_' for c in base).strip()
        caminho = os.path.join(destino, seguro)

        img = _ultima_imagem

        if img is None and regiao is not None:
            img = capturar(regiao)

        if img is not None:
            img.resize((img.width * escala, img.height * escala),
                       Image.LANCZOS).save(caminho + '.png')

        with open(caminho + '.txt', 'w', encoding='utf-8') as f:
            f.write(f'texto cru do OCR : {_ultimo_texto!r}\n')
            f.write(f'digitos          : '
                    f'{"".join(c for c in _ultimo_texto if c.isdigit())!r}\n')
            f.write(f'faixa aceita     : {PRECO_MIN} a {PRECO_MAX}\n')
            if regiao:
                f.write(f'regiao           : {regiao}\n')
            for linha in (extras or []):
                f.write(f'{linha}\n')

        return caminho + '.png'

    except Exception as e:
        relatar(f'   (nao deu para salvar o diagnostico: {e})')
        return None

#endregion

#region Historico de operacoes

ARQUIVO_HISTORICO = os.path.join(PASTA_REGISTROS, 'historico.csv')

COLUNAS_HISTORICO = [
    'quando', 'bot', 'modo', 'aba', 'item', 'combinacao',
    'preco_mercado', 'referencia', 'margem', 'quantidade',
]


def registrar_operacao(bot, modo, item, combinacao, preco_mercado,
                       referencia=None, aba='', quantidade=1):
    """Anota uma compra ou venda no historico.csv.

    Existe para responder uma pergunta que o log em texto nao responde: as
    margens da planilha realmente dao lucro? Os 13.000 do T5.2 e os 280.000 do
    T8.2 nunca foram medidos contra resultado real. Com um CSV da para cruzar
    preco pago, referencia e margem ao longo do tempo.

    Grava tambem no modo simulacao, com o modo na coluna - assim da para comparar
    o que o bot decidiria com o que ele fez.

    Nunca levanta: falhar em anotar nao pode interromper uma operacao."""

    try:
        pasta_registro()   # a pasta pode nao existir na primeira operacao da sessao

        # os logs rodavam em 2 MB e este arquivo nao tinha limite nenhum, apesar
        # de crescer a cada decisao inclusive em simulacao
        if (os.path.exists(ARQUIVO_HISTORICO)
                and os.path.getsize(ARQUIVO_HISTORICO) > MAX_HISTORICO_BYTES):
            os.replace(ARQUIVO_HISTORICO, ARQUIVO_HISTORICO + '.1')

        novo = not os.path.exists(ARQUIVO_HISTORICO)

        with open(ARQUIVO_HISTORICO, 'a', newline='', encoding='utf-8') as f:

            escritor = csv.writer(f, delimiter=';')

            if novo:
                escritor.writerow(COLUNAS_HISTORICO)

            margem = (referencia - preco_mercado
                      if referencia is not None and preco_mercado is not None else '')

            escritor.writerow([
                time.strftime('%Y-%m-%d %H:%M:%S'),
                bot,
                modo,
                aba,
                item,
                combinacao,
                preco_mercado if preco_mercado is not None else '',
                referencia if referencia is not None else '',
                margem,
                quantidade,
            ])

        return True

    except Exception as e:
        relatar(f'   (nao deu para anotar no historico: {e})')
        return False


# O rodape da janela pede este resumo na abertura e ao fim de cada execucao, e
# ele relia o arquivo inteiro toda vez. Guardar pelo par (mtime, tamanho) evita
# a releitura sem risco de mostrar numero velho.
_resumo_cache = {'chave': None, 'valor': (0, 0, 0, 0)}


def resumo_do_historico():
    """(linhas, compras, vendas, prata_gasta) do historico. Zeros se nao houver."""

    try:
        st = os.stat(ARQUIVO_HISTORICO)
    except OSError:
        return 0, 0, 0, 0

    chave = (st.st_mtime_ns, st.st_size)

    if _resumo_cache['chave'] == chave:
        return _resumo_cache['valor']

    linhas = compras = vendas = gasto = 0

    try:
        with open(ARQUIVO_HISTORICO, newline='', encoding='utf-8') as f:

            for reg in csv.DictReader(f, delimiter=';'):

                linhas += 1

                if reg.get('modo') != 'real':
                    continue

                try:
                    preco = int(reg.get('preco_mercado') or 0)
                    qtd = int(reg.get('quantidade') or 1)
                except ValueError:
                    continue

                if reg.get('bot') == 'Comprar':
                    compras += qtd
                    gasto += preco * qtd
                elif reg.get('bot') == 'Vender':
                    vendas += qtd

    except Exception:
        return 0, 0, 0, 0

    _resumo_cache['chave'] = chave
    _resumo_cache['valor'] = (linhas, compras, vendas, gasto)

    return linhas, compras, vendas, gasto

#endregion

# o caminho do tesseract vale para todo o processo
pytesseract.pytesseract.tesseract_cmd = TESSERACT

# Onde estao os dados do idioma, APENAS para a copia empacotada.
#
# Ela roda de uma pasta qualquer, e sem isto erra com "Failed loading language
# 'eng'" - que chega aqui como leitura vazia, indistinguivel de uma regiao sem
# numero na tela.
#
# A instalacao do sistema fica de fora de proposito: ela ja sabe onde procurar, e
# o significado desta variavel mudou entre o Tesseract 4 (a pasta ACIMA de
# tessdata) e o 5 (a propria tessdata). Defini-la para um caminho no formato
# errado quebraria uma instalacao que hoje funciona.
if TESSERACT.startswith(PASTA):

    _tessdata = os.path.join(os.path.dirname(TESSERACT), 'tessdata')

    if os.path.isdir(_tessdata):
        os.environ['TESSDATA_PREFIX'] = _tessdata
