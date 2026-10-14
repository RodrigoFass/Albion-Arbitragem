################################
#                              #
#        SOBREPOSICAO          #
#                              #
################################

# A faixa no topo da tela e os cartoes no canto, POR CIMA DO JOGO, enquanto o
# bot roda.
#
# A janela do aplicativo passa a operacao inteira minimizada, e voce passa ela
# olhando para o jogo. Sem isto nao haveria sinal de vida nenhum - nem o item
# atual, nem o preco que acabou de ser lido, para conferir ao lado do numero que
# o jogo esta mostrando.
#
# A COR E A DOS CARTOES DO APLICATIVO, solida. Um vidro com o jogo desfocado
# atras chegou a existir, mas copiar o jogo varias vezes por segundo pesava.
#
# CADA CARTAO E UMA JANELA: cinco, num rodizio. O aviso novo vai para a janela
# mais antiga, que desce para o fim da pilha, e as outras deslizam uma posicao
# para cima.
#
# NAO ACEITAM CLIQUE E NAO PEGAM FOCO. Um clique aqui tiraria o foco do jogo, e a
# conferencia de foco que roda a cada item encerraria a operacao.
#
# NADA AQUI PODE TRAVAR O RESTO. Janela do WebView2 nasce em outra thread, e
# conversar com ela na hora errada trava as duas pontas - foi o que aconteceu ao
# mexer no estilo dela de dentro do evento de carregamento. Por isso: as janelas
# sao criadas uma de cada vez, o estilo e aplicado so depois de elas carregarem e
# numa thread que ninguem espera, toda mudanca de posicao e assincrona, e os
# eventos vao por uma fila propria. Se uma sobreposicao empacar, o bot e a
# janela principal nem notam.
#
# Antes de alterar: python -m pyflakes sobreposicao.py

import ctypes
import json
import os
import queue
import threading
import time

import win32api
import win32con


FAIXA = {'largura': 600, 'altura': 40, 'topo': 10}
CARTAO = {'largura': 310, 'altura': 44, 'vao': 6, 'margem': 16, 'quantos': 5}

# onde as janelas esperam, fora de qualquer monitor
FORA = -32000

# quanto abaixo do lugar o cartao novo nasce, e quanto tempo leva o deslize
ENTRADA = 14
DESLIZE = 0.16
QUADROS = 10

# a cor dos cartoes do aplicativo (--superficie do tema escuro, em estilo.css)
COR = '#2c2c2e'

TITULO_FAIXA = 'Albion Arbitragem - faixa'
TITULO_CARTAO = 'Albion Arbitragem - aviso {}'

# JANELA FORA DA TELA CONTINUA DESENHANDO. O WebView2 para de desenhar a janela
# que acha escondida, e o cartao que espera fora entraria vazio, desenhando so um
# quadro depois - outra piscada. Vale para o navegador inteiro, por isso fica
# aqui, antes de qualquer janela nascer.
_ARGUMENTOS = 'WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'
_SEM_OCLUSAO = '--disable-features=CalculateNativeWinOcclusion'

if _SEM_OCLUSAO not in os.environ.get(_ARGUMENTOS, ''):
    os.environ[_ARGUMENTOS] = (os.environ.get(_ARGUMENTOS, '') + ' ' + _SEM_OCLUSAO).strip()

# o que as posicoes mudam sem esperar a janela responder nem tirar o foco do jogo
_SEM_ESPERA = (win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | 0x4000)  # ASYNCWINDOWPOS


class Sobreposicao:

    def __init__(self, pasta_web):

        self._pasta = pasta_web
        self._faixa = None
        self._cartoes = []       # [(janela, hwnd)] - o hwnd chega depois de carregar
        self._ordem = []         # indices de _cartoes, do mais novo para o mais velho
        self._proximo = 0
        self._tela = None        # (x, y, largura, altura) da area util, em pixels reais
        self._trava = threading.RLock()
        self._js = threading.Lock()  # uma conversa com as paginas de cada vez
        self._fila = queue.Queue()

        threading.Thread(target=self._entregar, daemon=True).start()

    def abrir(self, faixa=True, avisos=True):

        import webview

        self.fechar()

        def criar(titulo, pagina, w, h):
            # NASCEM FORA DA TELA. Ao nascer a janela ainda tem o tamanho errado e
            # os cantos retos; so entra na tela depois de pronta.
            janela = webview.create_window(
                titulo, os.path.join(self._pasta, pagina), width=w, height=h,
                x=FORA, y=FORA, frameless=True, on_top=True, focus=False,
                resizable=False, easy_drag=False, min_size=(20, 20),
                background_color=COR)
            janela.events.loaded.wait(8)
            return janela

        # UMA DE CADA VEZ: a seguinte so nasce depois que a anterior carregou.
        # So volta depois de todas carregarem, porque ao carregar o Windows lhes
        # da o foco - mesmo com focus=False. Voltando antes, quem chamou poria o
        # jogo na frente e a sobreposicao o tiraria de la um instante depois.
        titulos = []

        with self._trava:

            if faixa:
                self._faixa = criar(TITULO_FAIXA, 'faixa.html', FAIXA['largura'],
                                    FAIXA['altura'])
                titulos.append(TITULO_FAIXA)

            if avisos:
                for n in range(CARTAO['quantos']):
                    titulo = TITULO_CARTAO.format(n + 1)
                    janela = criar(titulo, 'cartao.html', CARTAO['largura'],
                                   CARTAO['altura'])
                    self._cartoes.append([janela, None])
                    titulos.append(titulo)

        preparar = threading.Thread(target=self._preparar, args=(titulos,), daemon=True)
        preparar.start()
        preparar.join(3)

        time.sleep(0.3)

    def _preparar(self, titulos):
        """Cantos redondos, sem clique, e a faixa no seu lugar. Os cartoes
        esperam fora."""

        hwnds = {t: _achar(t) for t in titulos}

        # O TAMANHO E POSTO AQUI, em pixels reais: o que a janela sem moldura
        # recebe ao nascer sai mais baixo que o pedido.
        for titulo, hwnd in hwnds.items():
            if hwnd:
                _sem_entrada(hwnd)
                _cantos(hwnd)
                k = _escala(hwnd)
                medida = FAIXA if titulo == TITULO_FAIXA else CARTAO
                _redimensionar(hwnd, round(k * medida['largura']), round(k * medida['altura']))

        # o tamanho e os cantos sao pedidos sem esperar: da tempo de chegarem
        # antes de a faixa aparecer
        time.sleep(0.15)

        with self._trava:

            self._tela = _area_util()

            for n, cartao in enumerate(self._cartoes):
                cartao[1] = hwnds.get(TITULO_CARTAO.format(n + 1))

            faixa = hwnds.get(TITULO_FAIXA)

            if faixa:
                x, y, largura, _ = self._tela
                k = _escala(faixa)
                _mover(faixa, x + (largura - round(k * FAIXA['largura'])) // 2,
                       y + round(k * FAIXA['topo']))

    def eventos(self, lote):
        """Entrega o lote as sobreposicoes, sem esperar por elas."""

        if self._faixa is not None or self._cartoes:
            self._fila.put(lote)

    def _entregar(self):

        while True:

            lote = self._fila.get()

            with self._trava:
                faixa = self._faixa

            if faixa is not None:
                texto = json.dumps([e for e in lote if e.get('tipo') != 'aviso'],
                                   ensure_ascii=False)
                self._js_em(faixa, f'window.sobre && window.sobre.eventos({texto})')

            # num lote com treze avisos, so os ultimos cinco chegariam a aparecer
            avisos = [e for e in lote if e.get('tipo') == 'aviso']

            for aviso in avisos[-CARTAO['quantos']:]:
                self._cartao(aviso)

    def _cartao(self, aviso):
        """O aviso novo entra embaixo e os outros sobem uma posicao.

        A JANELA RECICLADA SAI DA TELA ANTES DE TROCAR DE TEXTO. Trocando onde
        estava, o cartao de cima mudava de conteudo a vista e so depois pulava
        para baixo - era a piscada."""

        with self._trava:

            if not self._cartoes or self._tela is None:
                return

            indice = self._proximo
            self._proximo = (indice + 1) % len(self._cartoes)
            janela, novo = self._cartoes[indice]

            if indice in self._ordem:
                self._ordem.remove(indice)
            self._ordem.insert(0, indice)

            pilha = [self._cartoes[i][1] for i in self._ordem]
            x, y, largura, altura = self._tela

        # ESPERANDO A JANELA SAIR DE VERDADE: pedida sem esperar, a saida chegava
        # depois do texto novo, e o cartao de cima mostrava o aviso novo por um
        # quadro antes de sumir. Mais um quadro para o Windows redesenhar a tela.
        if novo:
            _mover(novo, FORA, FORA, esperar=True)
            time.sleep(0.02)

        dados = json.dumps({'titulo': aviso.get('titulo'), 'valor': aviso.get('valor'),
                            'tom': aviso.get('tom')}, ensure_ascii=False)
        if not self._js_em(janela, f'window.sobre && window.sobre.mostrar({dados})'):
            return

        # um quadro para a pagina desenhar o texto novo antes de aparecer
        time.sleep(0.03)

        # DE BAIXO PARA CIMA: o mais novo fica no fim da pilha
        destinos = {}
        base = y + altura

        for posicao, hwnd in enumerate(pilha):
            if not hwnd:
                continue
            k = _escala(hwnd)
            w, h = round(k * CARTAO['largura']), round(k * CARTAO['altura'])
            base -= round(k * (CARTAO['margem'] if posicao == 0 else CARTAO['vao'])) + h
            destinos[hwnd] = (x + largura - w - round(k * CARTAO['margem']), base)

        # DE ONDE CADA UM SAI: os que ja estavam na tela, de onde estao; o novo,
        # um pouco abaixo do lugar dele, para subir junto com os outros
        origens = {}

        for hwnd, (dx, dy) in destinos.items():
            onde = _posicao(hwnd) if hwnd != novo else None
            if onde is None or onde[0] <= FORA // 2:
                onde = (dx, dy + round(_escala(hwnd) * ENTRADA))
            origens[hwnd] = onde

        _deslizar(origens, destinos)

    def _js_em(self, janela, codigo):
        with self._js:
            try:
                janela.evaluate_js(codigo)
                return True
            except Exception:
                return False

    def fechar(self):

        with self._trava:
            janelas = ([self._faixa] if self._faixa is not None else []) + \
                      [c[0] for c in self._cartoes]
            self._faixa = None
            self._cartoes = []
            self._ordem = []
            self._proximo = 0

        for janela in janelas:
            try:
                janela.destroy()
            except Exception:
                pass


#region Windows

# TUDO PELO CTYPES, E NAO PELO PYWIN32. O pywin32 segura o interpretador do
# Python enquanto a chamada espera a janela responder - e a janela, para
# responder, precisa do interpretador: as duas pontas ficavam esperando uma a
# outra para sempre. O ctypes solta o interpretador durante a chamada.
#
# UMA INSTANCIA PROPRIA E COM OS TIPOS DECLARADOS. Sem os tipos, o ctypes manda
# todo inteiro como 32 bits, e o HWND_TOPMOST (-1) chegava ao Windows como um
# numero qualquer: nenhuma janela saia do lugar. A instancia e propria porque o
# pywebview usa a windll.user32 com outros tipos.
from ctypes import wintypes as _w

_user32 = ctypes.WinDLL('user32', use_last_error=True)

_user32.FindWindowW.argtypes = [_w.LPCWSTR, _w.LPCWSTR]
_user32.FindWindowW.restype = _w.HWND
_user32.GetDpiForWindow.argtypes = [_w.HWND]
_user32.GetDpiForWindow.restype = _w.UINT
_user32.SetWindowPos.argtypes = [_w.HWND, _w.HWND, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, _w.UINT]
_user32.SetWindowPos.restype = _w.BOOL
_user32.GetWindowLongW.argtypes = [_w.HWND, ctypes.c_int]
_user32.GetWindowLongW.restype = _w.LONG
_user32.SetWindowLongW.argtypes = [_w.HWND, ctypes.c_int, _w.LONG]
_user32.SetWindowLongW.restype = _w.LONG
_user32.EnableWindow.argtypes = [_w.HWND, _w.BOOL]
_user32.EnableWindow.restype = _w.BOOL
_user32.GetWindowRect.argtypes = [_w.HWND, ctypes.POINTER(_w.RECT)]
_user32.GetWindowRect.restype = _w.BOOL

_dwmapi = ctypes.WinDLL('dwmapi')


def _achar(titulo):
    try:
        return _user32.FindWindowW(None, titulo) or None
    except Exception:
        return None


def _area_util():
    """A tela principal sem a barra de tarefas."""

    try:
        monitor = win32api.MonitorFromPoint((0, 0), win32con.MONITOR_DEFAULTTOPRIMARY)
        x1, y1, x2, y2 = win32api.GetMonitorInfo(monitor)['Work']
        return x1, y1, x2 - x1, y2 - y1
    except Exception:
        return 0, 0, win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)


def _escala(hwnd):
    try:
        return _user32.GetDpiForWindow(hwnd) / 96 or 1
    except Exception:
        return 1


def _redimensionar(hwnd, largura, altura):
    try:
        _user32.SetWindowPos(hwnd, 0, 0, 0, int(largura), int(altura),
                             (_SEM_ESPERA & ~win32con.SWP_NOSIZE) | win32con.SWP_NOMOVE
                             | win32con.SWP_NOZORDER)
    except Exception:
        pass


def _posicao(hwnd):
    """Onde a janela esta agora (x, y), ou None."""

    r = _w.RECT()
    if not _user32.GetWindowRect(hwnd, ctypes.byref(r)):
        return None
    return r.left, r.top


def _deslizar(origens, destinos):
    """Leva cada janela da origem ao destino em DESLIZE segundos, freando.

    A curva e a da mola amortecida da interface (sem passar do ponto): rapido no
    comeco e assentando devagar, como as listas do sistema."""

    inicio = time.monotonic()

    for quadro in range(1, QUADROS + 1):

        t = quadro / QUADROS
        anda = 1 - (1 - t) ** 3

        for hwnd, (dx, dy) in destinos.items():
            ox, oy = origens[hwnd]
            _mover(hwnd, round(ox + (dx - ox) * anda), round(oy + (dy - oy) * anda))

        espera = inicio + DESLIZE * t - time.monotonic()
        if espera > 0:
            time.sleep(espera)


def _mover(hwnd, x, y, esperar=False):
    """Muda a janela de lugar. <esperar> so volta depois de o Windows mudar -
    seguro porque o ctypes solta o interpretador enquanto espera."""

    flags = _SEM_ESPERA | win32con.SWP_SHOWWINDOW

    if esperar:
        flags &= ~0x4000   # sem o ASYNCWINDOWPOS

    try:
        _user32.SetWindowPos(hwnd, win32con.HWND_TOPMOST, int(x), int(y), 0, 0, flags)
    except Exception:
        pass


def _sem_entrada(hwnd):
    """Desabilita a janela para mouse e teclado, e tira da barra de tarefas."""

    try:
        estilo = _user32.GetWindowLongW(hwnd, win32con.GWL_EXSTYLE)
        estilo |= win32con.WS_EX_NOACTIVATE | win32con.WS_EX_TOOLWINDOW
        estilo &= ~win32con.WS_EX_APPWINDOW
        _user32.SetWindowLongW(hwnd, win32con.GWL_EXSTYLE, estilo)

        _user32.EnableWindow(hwnd, False)

    except Exception:
        pass


def _cantos(hwnd):
    """Cantos redondos e o fio da borda do Windows 11, no escuro.

    No Windows 10 nada disto existe e a chamada falha calada: ficam os cantos
    retos."""

    def atributo(qual, valor):
        v = ctypes.c_int(valor)
        _dwmapi.DwmSetWindowAttribute(hwnd, qual, ctypes.byref(v), ctypes.sizeof(v))

    try:
        atributo(20, 1)            # DWMWA_USE_IMMERSIVE_DARK_MODE
        atributo(33, 2)            # DWMWA_WINDOW_CORNER_PREFERENCE: redondo
        atributo(34, 0x003c3a3a)   # DWMWA_BORDER_COLOR: o --superficie-2 do app
    except Exception:
        pass

#endregion
