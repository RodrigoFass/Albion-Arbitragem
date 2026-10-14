################################
#                              #
#        IDENTIFICADORES       #
#                              #
################################

# O nome de cada item que o programa conhece -> o identificador que o jogo usa
# ("Broadsword", "T5.2" -> "T5_MAIN_SWORD@2"). E por ele que a leitura pela rede
# reconhece de que item e cada pacote.
#
# O mapa vem de recursos/ids-dos-itens.json, gerado por
# ferramentas/gerar_ids.py a partir dos dados do jogo.
#
# Antes de alterar: python -m pyflakes identificadores.py

import json
import os

from motor import comum
from motor import mercado

ARQUIVO_IDS = os.path.join(comum.PASTA_RECURSOS, 'ids-dos-itens.json')

_ids = None


def _carregar_ids():

    global _ids

    if _ids is None:
        try:
            with open(ARQUIVO_IDS, encoding='utf-8') as f:
                _ids = json.load(f)
        except (OSError, ValueError):
            _ids = {}

    return _ids


def ids():
    """{nome do item: tronco do identificador}, para quem precisa do mapa todo."""

    return dict(_carregar_ids())


def tronco(item):
    """'Broadsword' -> 'MAIN_SWORD'. None se o item nao tem id."""

    return _carregar_ids().get(item)


def identificador(item, rotulo):
    """'Broadsword', 'T5.2' -> 'T5_MAIN_SWORD@2'. None se o item nao tem id."""

    tronco = _carregar_ids().get(item)
    partes = mercado.partes(rotulo)

    if not tronco or partes is None:
        return None

    grau, ench = partes

    return f'T{grau}_{tronco}' + (f'@{ench}' if ench else '')
