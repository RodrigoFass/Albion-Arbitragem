################################
#                              #
#            MARCA             #
#                              #
################################

# O simbolo do aplicativo, e as cores que saem dele.
#
# A ARTE E UM ARQUIVO, o marca.ico ao lado. Ela nao e desenhada por codigo: e uma
# marca existente, com proporcao e forma proprias, e reconstrui-la em poligonos
# seria copiar de olho um desenho que ja existe pronto.
#
# O QUE E DERIVADO POR CODIGO e o resto: o icone do executavel, os tamanhos que a
# barra de tarefas pede e a versao pequena do cabecalho. Tudo sai do mesmo
# arquivo, entao trocar a marca e trocar um arquivo.
#
# UM DETALHE QUE DECIDE O DESENHO DO ICONE: o "A" da marca e BRANCO, e o fundo do
# arquivo e transparente. Sobre o escuro do aplicativo isso fica perfeito - mas no
# Explorer, que e claro, o A simplesmente some e sobra um B vermelho solto. Por
# isso o icone do .exe leva uma placa escura atras: nao e enfeite, e o que faz a
# marca continuar inteira em qualquer lugar onde o Windows a mostre.
#
# Antes de alterar: python -m pyflakes marca.py

import os
import sys

from PIL import Image, ImageDraw


def _achar_arte():
    """Onde esta o marca.ico.

    Empacotado, ele vai para dentro do pacote (sys._MEIPASS) e nao para a pasta
    do .exe - ao contrario da planilha, este arquivo e so leitura e nao tem por
    que ficar a vista do usuario."""

    candidatos = []

    if getattr(sys, 'frozen', False):
        candidatos.append(os.path.join(getattr(sys, '_MEIPASS', ''), 'marca.ico'))

    candidatos.append(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'marca.ico'))

    for caminho in candidatos:
        if caminho and os.path.isfile(caminho):
            return caminho

    return candidatos[-1]


ARQUIVO = _achar_arte()
PASTA = os.path.dirname(ARQUIVO)

# Tirados da propria arte, e nao escolhidos a parte: sao os pixels que ela usa.
VERMELHO = '#d12928'
BRANCO   = '#ffffff'

# Fundo da placa do icone. O mesmo tom do painel da janela, para o icone e o
# aplicativo parecerem a mesma coisa.
PLACA = (28, 31, 38, 255)

TAMANHOS_ICO = [256, 128, 64, 48, 32, 16]


def arte(lado=None):
    """A marca em RGBA, com fundo transparente. None devolve o tamanho original."""

    img = Image.open(ARQUIVO).convert('RGBA')

    if lado and lado != img.width:
        img = img.resize((lado, lado), Image.LANCZOS)

    return img


def com_placa(lado, fundo=PLACA, raio=0.18, margem=None):
    """A marca sobre uma placa escura de cantos arredondados.

    <margem> e a folga em volta, em fracao do lado. Ela DIMINUI nos tamanhos
    pequenos: a 16 px cada pixel decide se a marca e legivel ou um borrao, e a
    folga que da respiro ao icone grande ali e desperdicio."""

    if margem is None:
        margem = 0.14 if lado >= 64 else (0.09 if lado >= 32 else 0.04)

    img = Image.new('RGBA', (lado, lado), (0, 0, 0, 0))

    ImageDraw.Draw(img).rounded_rectangle(
        [0, 0, lado - 1, lado - 1], radius=max(2, round(lado * raio)), fill=fundo)

    dentro = max(1, round(lado * (1 - 2 * margem)))
    simbolo = arte(dentro)

    img.paste(simbolo, ((lado - dentro) // 2, (lado - dentro) // 2), simbolo)

    return img


def gerar_icone(destino, placa=True):
    """Grava o .ico com todos os tamanhos que o Windows escolhe conforme o lugar.

    Um .ico com um tamanho so faz o Windows reduzir o de 256 para 16, e a marca
    vira um borrao na barra de tarefas."""

    base = com_placa(256) if placa else arte(256)

    base.save(destino, sizes=[(t, t) for t in TAMANHOS_ICO])

    return destino
