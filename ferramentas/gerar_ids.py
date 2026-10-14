# Gera o ids-dos-itens.json: o nome de cada item que o programa conhece ->
# o identificador que a API do Albion Online Data Project usa.
#
#     python ferramentas/gerar_ids.py [caminho/do/items.txt]
#
# Sem argumento, baixa o items.txt do ao-bin-dumps (a lista oficial extraida do
# jogo). O identificador guardado e o "tronco", sem grau nem encantamento:
# "Broadsword" -> "MAIN_SWORD", que vira T5_MAIN_SWORD@2 na hora de perguntar.
#
# Rodar de novo so quando o jogo acrescentar itens que voce queira negociar.

import json
import os
import re
import sys
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))

from motor import categorias  # noqa: E402
from motor import nomes       # noqa: E402

FONTE = ('https://raw.githubusercontent.com/ao-data/ao-bin-dumps/master/'
         'formatted/items.txt')

SAIDA = os.path.join(os.path.dirname(AQUI), 'recursos', 'ids-dos-itens.json')

# "  4233: T4_ARMOR_LEATHER_SET3   : Adept's Assassin Jacket"
LINHA = re.compile(r'^\s*\d+:\s*(T(\d)_[A-Z0-9_]+)\s*:\s*(.+?)\s*$')

# Onde o nome do jogo nao e o do menu nem o do catalogo.
GRAFIA_DO_JOGO = {
    'Bags': 'Bag',
    'Satchel': 'Satchel of Insight',
    'Satchels of Insight': 'Satchel of Insight',
    'Demon Fang': 'Demonfang',
}


def ler(caminho):

    if caminho:
        with open(caminho, encoding='utf-8') as f:
            return f.read().splitlines()

    with urllib.request.urlopen(FONTE, timeout=60) as r:
        return r.read().decode('utf-8').splitlines()


def main():

    por_nome = {}

    for linha in ler(sys.argv[1] if len(sys.argv) > 1 else None):

        achado = LINHA.match(linha)

        if not achado:
            continue

        identificador, grau, nome = achado.groups()
        prefixo = nomes.prefixo(int(grau))

        if not prefixo or not nome.startswith(prefixo + ' '):
            continue

        base = nome[len(prefixo) + 1:]
        tronco = identificador.split('_', 1)[1]

        # o primeiro que aparece e o certo: as variantes vem depois na lista
        por_nome.setdefault(base, tronco)

    mapa = {}
    faltando = []

    # os nomes do menu e os do catalogo, que as vezes diferem ("Greathammer" no
    # catalogo, "Great Hammer" no menu) - a API e perguntada pelos dois
    conhecidos = set(categorias.itens_mapeados()) | set(categorias.NOME_NO_MENU)

    for item in sorted(conhecidos):

        candidatos = [GRAFIA_DO_JOGO.get(item, item), categorias.no_menu(item),
                      item + ' Cape']

        for nome in candidatos:
            if nome in por_nome:
                mapa[item] = por_nome[nome]
                break
        else:
            faltando.append(item)

    with open(SAIDA, 'w', encoding='utf-8') as f:
        json.dump(mapa, f, ensure_ascii=False, indent=1, sort_keys=True)

    print(f'{len(mapa)} itens com identificador em {SAIDA}')

    if faltando:
        print(f'{len(faltando)} sem identificador: {", ".join(faltando)}')


if __name__ == '__main__':
    main()
