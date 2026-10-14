# Gera o recursos/marca.ico (icone do .exe) a partir do desenho da marca, o
# mesmo do interface/web/img/marca.svg.
#
#     python ferramentas/gerar_icone.py

import os

from PIL import Image, ImageDraw

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(os.path.dirname(AQUI), 'recursos', 'marca.ico')

LADO = 1024          # desenha grande e reduz: as bordas saem lisas
ESCALA = LADO / 64   # o svg tem 64 de lado

CLARO = (0x5A, 0xB0, 0xFF)
ESCURO = (0x0A, 0x6C, 0xFF)


def _p(*v):
    return [round(x * ESCALA) for x in v]


def desenhar():

    # o degrade na diagonal, de cima-esquerda para baixo-direita
    fundo = Image.new('RGB', (LADO, LADO))
    px = fundo.load()

    for y in range(LADO):
        for x in range(LADO):
            t = (x + y) / (2 * (LADO - 1))
            px[x, y] = tuple(round(a + (b - a) * t) for a, b in zip(CLARO, ESCURO))

    mascara = Image.new('L', (LADO, LADO), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((0, 0, LADO - 1, LADO - 1),
                                              radius=round(15 * ESCALA), fill=255)

    icone = Image.new('RGBA', (LADO, LADO), (0, 0, 0, 0))
    icone.paste(fundo, (0, 0), mascara)

    d = ImageDraw.Draw(icone)
    largura = round(6 * ESCALA)
    branco = (255, 255, 255, 255)

    d.line(_p(23, 41, 42, 22), fill=branco, width=largura)
    d.line(_p(28, 21, 43, 21), fill=branco, width=largura)
    d.line(_p(43, 21, 43, 36), fill=branco, width=largura)

    # pontas redondas, como o stroke-linecap do svg
    r = largura / 2
    for x, y in ((23, 41), (42, 22), (28, 21), (43, 21), (43, 36)):
        cx, cy = x * ESCALA, y * ESCALA
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=branco)

    cx, cy, raio = 19 * ESCALA, 45 * ESCALA, 6 * ESCALA
    d.ellipse((cx - raio, cy - raio, cx + raio, cy + raio), fill=branco)

    return icone


def main():

    icone = desenhar().resize((256, 256), Image.LANCZOS)
    icone.save(SAIDA, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64),
                             (128, 128), (256, 256)])
    print(f'gravado {SAIDA}')


if __name__ == '__main__':
    main()
