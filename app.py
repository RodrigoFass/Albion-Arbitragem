################################
#                              #
#          APLICATIVO          #
#                              #
################################

# Abre a janela. A interface e HTML/CSS em web/, desenhada pelo WebView2 do
# Windows atraves do pywebview; tudo que ela pede ao programa passa pela Api da
# ponte.py.
#
#     python app.py
#
# Antes de alterar: python -m pyflakes app.py

import ctypes
import os
import subprocess
import sys
import threading


def _no_python_do_projeto():
    """Reabre o programa com o Python da .venv quando este nao tem as dependencias.

    O botao de rodar do editor usa o Python que estiver selecionado nele - o do
    sistema, muitas vezes -, e as bibliotecas estao instaladas na .venv do
    projeto. Sem isto, o programa morria com "No module named 'webview'"."""

    import importlib.util

    faltando = next((m for m in ('webview', 'mss', 'PIL', 'pynput', 'pytesseract',
                                 'win32api') if importlib.util.find_spec(m) is None),
                    None)

    if faltando is None:
        return

    raiz = os.path.dirname(os.path.abspath(__file__))
    da_venv = os.path.join(raiz, '.venv', 'Scripts', 'python.exe')

    if os.path.isfile(da_venv) and os.path.normcase(sys.executable) != os.path.normcase(da_venv):
        raise SystemExit(subprocess.call([da_venv, os.path.abspath(__file__)] + sys.argv[1:]))

    ctypes.windll.user32.MessageBoxW(
        None, f'Falta a biblioteca "{faltando}" neste Python ({sys.executable}).\n\n'
              f'Instale as dependencias na pasta do programa:\n'
              f'    python -m venv .venv\n'
              f'    .venv\\Scripts\\python -m pip install -r requirements.txt',
        'Albion Arbitragem', 0x10)
    raise SystemExit(1)


if not getattr(sys, 'frozen', False):
    _no_python_do_projeto()

import webview  # noqa: E402

from motor import comum  # noqa: E402
from interface.ponte import TITULO, Api  # noqa: E402
from interface.sobreposicao import Sobreposicao  # noqa: E402

PASTA_WEB = os.path.join(comum.PASTA, 'interface', 'web')

# Onde a janela guarda o que e dela (a ultima tela aberta, a lateral recolhida),
# junto com os outros dados de quem usa.
PASTA_NAVEGADOR = os.path.join(comum.PASTA_DADOS, 'navegador')


def _pagina(nome):
    return os.path.join(PASTA_WEB, nome)


def _limpar_cache_da_janela():
    """Joga fora o HTML, JS e CSS que a janela guardou da ultima vez.

    SEM ISTO, ATUALIZAR O PROGRAMA NAO MUDAVA A TELA: o WebView2 servia os
    arquivos antigos do cache e as telas novas simplesmente nao apareciam. Fica
    o que importa - a memoria da janela -, sai so o cache de arquivos."""

    import shutil

    for pedaco in (('EBWebView', 'Default', 'Cache'),
                   ('EBWebView', 'Default', 'Code Cache')):
        shutil.rmtree(os.path.join(PASTA_NAVEGADOR, *pedaco), ignore_errors=True)


def _avisar(texto):
    """Caixa do Windows - usada so antes de existir janela."""

    ctypes.windll.user32.MessageBoxW(None, texto, TITULO, 0x30)


def main():

    ok, mensagem = comum.travar('AlbionArbitragem')

    if not ok:
        _avisar(mensagem)
        return

    # o que versoes anteriores deixavam solto na raiz vai para dados/
    comum.migrar_dados_antigos()

    api = None

    try:
        api = Api(Sobreposicao(PASTA_WEB))

        janela = webview.create_window(
            TITULO, _pagina('index.html'), js_api=api, width=1280, height=840,
            min_size=(1060, 700), background_color='#1c1c1e')

        calibrador = []

        def abrir(qual):

            if qual != 'calibrador':
                return

            vivas = [j for j in calibrador if j in webview.windows]

            if vivas:
                vivas[0].restore()
                return

            calibrador[:] = [webview.create_window(
                f'{TITULO} - calibrar coordenadas', _pagina('calibrador.html'),
                js_api=api, width=1320, height=880, min_size=(1000, 700),
                background_color='#1c1c1e')]

        api._ligar(janela, abrir)

        # FECHAR NO MEIO DE UMA OPERACAO PERGUNTA ANTES. A pergunta e da
        # interface, que depois chama api.sair().
        def fechando():
            if api._rodando and not api._saindo:
                janela.evaluate_js('window.app && window.app.confirmarSaida()')
                return False
            return True

        janela.events.closing += fechando

        # A LEITURA PELA REDE LIGA JUNTO COM O APP, e nao so ao comecar uma
        # operacao: o albiondata-client descobre em que mercado voce esta quando
        # voce troca de zona, e precisa estar rodando antes disso.
        threading.Thread(target=api._iniciar_rede, daemon=True).start()

        _limpar_cache_da_janela()

        webview.start(http_server=True, private_mode=False,
                      storage_path=PASTA_NAVEGADOR)

    finally:
        if api is not None:
            api._encerrar_rede()
        comum.terminar_execucao()


if __name__ == '__main__':
    main()
