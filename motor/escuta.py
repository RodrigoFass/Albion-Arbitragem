################################
#                              #
#            ESCUTA            #
#                              #
################################

# Os precos que o albiondata-client captura da rede, recebidos aqui.
#
# QUANDO O JOGO ABRE UM ITEM NO MERCADO, o servidor manda o livro de ofertas
# inteiro: cada ordem com item, grau, encantamento, qualidade, preco e
# quantidade. O albiondata-client (o mesmo programa do Albion Online Data
# Project) le esse trafego e repassa para um endereco - aqui, so para este
# computador, nunca para o projeto publico. O bot continua clicando para abrir
# cada item, porque o servidor so manda o que o jogo pede; o que muda e que o
# numero chega EXATO, sem print e sem OCR. O OCR fica de reserva.
#
# O QUE ISSO RESOLVE:
#   - o preco lido errado pelo OCR (o 5 que vira 9, o digito raspado);
#   - o grau errado: o identificador do item traz grau e encantamento;
#   - a profundidade do livro: todas as ofertas, com quantidade;
#   - a qualidade: as cinco chegam juntas, a tela mostra uma por vez.
#
# QUALQUER PRECO QUE CHEGA E GRAVADO, mesmo com o bot parado. Abrir um item na
# mao no mercado tambem atualiza o banco.
#
# O cliente manda: POST http://127.0.0.1:<porta>/marketorders.ingest
#   {"Orders": [{"ItemTypeId": "T5_MAIN_SWORD@2", "LocationId": "0007",
#                "QualityLevel": 1, "EnchantmentLevel": 2,
#                "UnitPriceSilver": 1234560000, "Amount": 3,
#                "AuctionType": "offer", ...}]}
# O preco vem multiplicado por 10.000 - o proprio projeto divide, com o
# comentario "albion seems to be multiplying every price by 10000".
#
# Antes de alterar: python -m pyflakes motor/escuta.py

import json
import os
import re
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from motor import comum
from motor import mercado
from motor import identificadores

PORTA_PADRAO = 8642
ESCALA_DO_PRECO = 10_000

# O codigo do mercado na rede. A cidade vem com zeros a esquerda ("0007"), por
# isso a comparacao e pelo numero.
LOCAIS = {
    7: 'Thetford',
    1002: 'Lymhurst',
    2004: 'Bridgewatch',
    3005: 'Caerleon',
    3008: 'Martlock',
    4002: 'Fort Sterling',
    3003: mercado.MERCADO_NEGRO,
}

# Quanto esperar o pacote de uma combinacao depois de trocar o filtro, antes de
# cair para o OCR. A resposta do servidor costuma chegar em menos de meio
# segundo; o cliente ainda junta e envia.
ESPERA = 1.5

# Sem pacote nenhum ha este tempo, a rede conta como desligada e ninguem espera
# por ela - a leitura vai direto para o OCR, sem perder tempo por combinacao.
SILENCIO = 600

# Quanto esperar no TESTE DA REDE: o primeiro item de uma leitura ou de uma
# compra com o cliente de pe e nenhum pacote recente. Calada nao quer dizer
# quebrada - so que ninguem abriu o mercado nos ultimos minutos.
ESPERA_SONDA = 3.0

# O que o Andamento diz quando o teste da rede falha. EXITLAG E VPN PRIMEIRO:
# foi o que impediu a leitura pela rede numa maquina por dias, com o cliente
# aberto e o aviso pedindo uma troca de mapa que nao resolvia nada.
AVISO_SEM_REDE = ('ATENCAO: a rede nao respondeu no primeiro item - seguindo pela '
                  'tela (OCR). ExitLag, VPN ou outro programa que desvia o '
                  'trafego do jogo impedem a leitura pela rede; feche-o e reabra '
                  'o jogo. Se o albiondata-client acabou de abrir, troque de mapa.')

# Onde o instalador do albiondata-client costuma pôr o programa.
CAMINHOS_COMUNS = (
    r'C:\Program Files\Albion Data Client\albiondata-client.exe',
    r'C:\Program Files (x86)\Albion Data Client\albiondata-client.exe',
    os.path.expandvars(r'%LOCALAPPDATA%\Programs\Albion Data Client\albiondata-client.exe'),
)

NOME_DO_CLIENTE = 'albiondata-client.exe'

ID_DO_ITEM = re.compile(r'^T(\d)_([A-Z0-9_]+?)(?:@(\d))?$')

#region O que chegou

_trava = threading.RLock()

# (local, tronco, grau, ench, qualidade) -> {'ofertas': [...], 'pedidos': [...],
#                                            'quando_ofertas': t, 'quando_pedidos': t,
#                                            'seq': numero do pacote}
_livros = {}

_estado = {'quando': None, 'local': None, 'pacotes': 0, 'ordens': 0}

# O NUMERO DO ULTIMO PACOTE. Quem espera um livro anota este numero ANTES de
# clicar, e so aceita pacote de numero maior. O relogio nao serve para isso: no
# Windows ele anda em saltos de ~15 ms, e o pacote da linha anterior podia ter o
# mesmo horario do clique da linha seguinte.
_seq = [0]


def marca():
    """O numero do ultimo pacote - anote antes de clicar, passe como <desde>."""

    return _seq[0]


_nomes = None


def _nomes_por_tronco():
    """{tronco: [nomes]} - o mapa de identificadores, ao contrario."""

    global _nomes

    if _nomes is None:
        _nomes = {}
        for nome, tronco in identificadores.ids().items():
            _nomes.setdefault(tronco, []).append(nome)

    return _nomes


def decompor(item_id, ench=None):
    """'T5_MAIN_SWORD@2' -> ('MAIN_SWORD', 5, 2). None se nao for equipamento."""

    achado = ID_DO_ITEM.match(item_id or '')

    if not achado:
        return None

    grau, tronco, arroba = achado.groups()

    encantamento = int(arroba) if arroba else int(ench or 0)

    return tronco, int(grau), encantamento


def local_de(codigo):
    """'0007' -> 'Thetford'. None para o que nao e mercado conhecido."""

    try:
        return LOCAIS.get(int(str(codigo)))
    except (TypeError, ValueError):
        return None


def receber(dados, agora=None):
    """Processa um pacote do cliente. Devolve quantas ordens aproveitou."""

    agora = agora or time.time()
    ordens = (dados or {}).get('Orders') or []

    grupos = {}

    for o in ordens:

        local = local_de(o.get('LocationId'))
        partes = decompor(o.get('ItemTypeId'), o.get('EnchantmentLevel'))
        tipo = {'offer': 'ofertas', 'request': 'pedidos'}.get(
            str(o.get('AuctionType', '')).lower())

        if local is None or partes is None or tipo is None:
            continue

        try:
            preco = int(o.get('UnitPriceSilver') or 0) // ESCALA_DO_PRECO
            quantidade = int(o.get('Amount') or 0)
            qualidade = int(o.get('QualityLevel') or 1)
        except (TypeError, ValueError):
            continue

        if preco <= 0 or quantidade <= 0:
            continue

        tronco, grau, ench = partes
        chave = (local, tronco, grau, ench, qualidade)

        grupos.setdefault((chave, tipo), []).append((preco, quantidade))

    if not grupos:
        return 0

    tocados = set()

    with _trava:

        # CADA PACOTE E UMA FOTO daquele lado do livro: substitui o que havia, e
        # nao soma. Ordem que sumiu do livro (comprada, cancelada) some daqui.
        for (chave, tipo), lista in grupos.items():
            livro = _livros.setdefault(chave, {})
            livro[tipo] = sorted(lista, reverse=(tipo == 'pedidos'))
            livro['quando_' + tipo] = agora
            livro['seq'] = _seq[0] + 1
            tocados.add(chave[:4])

        _seq[0] += 1
        _estado['quando'] = agora
        _estado['pacotes'] += 1
        _estado['ordens'] += sum(len(v) for v in grupos.values())
        _estado['local'] = next(iter(grupos))[0][0]

    for local, tronco, grau, ench in tocados:
        _gravar_no_banco(local, tronco, grau, ench, agora)

    _pedir_gravacao()

    return sum(len(v) for v in grupos.values())


def _melhor(livro, tipo):
    lista = livro.get(tipo) or []
    return lista[0][0] if lista else None


def _gravar_no_banco(local, tronco, grau, ench, agora):
    """Leva para o precos.json o que a tela teria lido - e o que ela nao le.

    NA CIDADE o preco e a oferta mais barata de qualquer qualidade: e o que a
    lista de compra mostra no topo. NO MERCADO NEGRO a varredura le a qualidade
    Normal, e o banco guarda o mesmo: a menor venda e o maior pedido dela. As
    cinco qualidades vao a parte, para a compra por qualidade."""

    with _trava:
        livros = {q: dict(l) for (lo, t, g, e, q), l in _livros.items()
                  if (lo, t, g, e) == (local, tronco, grau, ench)}

    qualidades = {q: {'oferta': _melhor(l, 'ofertas'), 'pedido': _melhor(l, 'pedidos')}
                  for q, l in livros.items()}

    livro = None

    if local == mercado.MERCADO_NEGRO:
        normal = qualidades.get(1, {})
        preco, outro = normal.get('oferta'), normal.get('pedido')
    else:
        ofertas = [v['oferta'] for v in qualidades.values() if v['oferta']]
        preco, outro = (min(ofertas) if ofertas else None), None

        # NA CIDADE, O LIVRO INTEIRO: e dele que sai a media que a lista de
        # compras usa (lucro.media_das_ofertas)
        livro = sorted(o for l in livros.values() for o in (l.get('ofertas') or []))

    rot = mercado.rotulo(grau, ench)

    for nome in _nomes_por_tronco().get(tronco, []):
        mercado.atualizar(local, nome, rot, preco=preco, outro=outro,
                          qualidades=qualidades, quando=agora, ofertas=livro)

#endregion

#region Quem le

def ativa():
    """True se a rede esta mandando precos - e vale a pena esperar por ela."""

    return (_estado['quando'] is not None
            and time.time() - _estado['quando'] < SILENCIO)


def ligada():
    """True se o receptor e o cliente estao de pe: PODE chegar preco.

    Diferente de ativa(), que diz se chegou ha pouco. Ligada e calada e o normal
    logo depois de abrir o jogo - e e quando vale testar a rede no primeiro
    item em vez de desistir dela."""

    return _servidor is not None and _cliente_situacao == 'rodando'


# Pacotes esperados que nao chegaram, seguidos. Passando disto a escuta se da por
# calada - o cliente caiu, o jogo trocou de mercado - e a leitura volta ao OCR
# ate o proximo pacote chegar.
FALTAS_PARA_CALAR = 6

_faltas = 0


def faltou():
    """Um pacote esperado nao chegou."""

    global _faltas

    _faltas += 1

    if _faltas >= FALTAS_PARA_CALAR:
        _faltas = 0
        _estado['quando'] = None
        comum.relatar(f'ATENCAO: {FALTAS_PARA_CALAR} combinacoes seguidas sem '
                      f'pacote da rede - seguindo pelo OCR')


def _chegou():
    global _faltas
    _faltas = 0


def situacao():
    """O que a interface mostra sobre a rede."""

    quando = _estado['quando']

    return {
        'servidor': _servidor is not None,
        'porta': _porta,
        'recebendo': ativa(),
        'ha_segundos': None if quando is None else round(time.time() - quando),
        'local': _estado['local'],
        'pacotes': _estado['pacotes'],
        'ordens': _estado['ordens'],
        'cliente': _cliente_situacao,
    }


def local_atual(recente=120):
    """O mercado de onde veio o ultimo pacote, se ele for recente."""

    quando = _estado['quando']

    if quando is None or time.time() - quando > recente:
        return None

    return _estado['local']


def _livros_do_item(local, item, rot, desde):
    """Os livros daquele item e combinacao, por qualidade, chegados depois de <desde>."""

    ident = identificadores.identificador(item, rot)
    partes = decompor(ident) if ident else None

    if partes is None:
        return {}

    tronco, grau, ench = partes

    with _trava:
        return {q: dict(l) for (lo, t, g, e, q), l in _livros.items()
                if (lo, t, g, e) == (local, tronco, grau, ench)
                and l.get('seq', 0) > desde}


def _esperar(funcao, prazo, mesmo_calado=False):
    """Chama <funcao> ate ela devolver algo, ou o prazo acabar.

    <mesmo_calado> espera mesmo sem pacote recente: e o teste da rede."""

    if not ativa() and not mesmo_calado:
        return None

    fim = time.monotonic() + prazo

    while True:

        resposta = funcao()

        if resposta:
            return resposta

        if time.monotonic() >= fim:
            return None

        comum.checar_aborto()
        time.sleep(0.05)


def precos(local, item, rot, desde, prazo=ESPERA, mesmo_calado=False):
    """(preco, outro) de uma combinacao pela rede, ou None para cair no OCR.

    O MESMO PAR QUE A TELA DARIA: na cidade, a oferta mais barata; no Mercado
    Negro, a menor venda e o maior pedido da qualidade Normal."""

    def tentar():
        livros = _livros_do_item(local, item, rot, desde)

        if not livros:
            return None

        if local == mercado.MERCADO_NEGRO:
            normal = livros.get(1, {})
            venda = _melhor(normal, 'ofertas')
            return (venda, _melhor(normal, 'pedidos')) if venda else None

        ofertas = [_melhor(l, 'ofertas') for l in livros.values()]
        ofertas = [o for o in ofertas if o]
        return (min(ofertas), None) if ofertas else None

    resposta = _esperar(tentar, prazo, mesmo_calado)

    if resposta:
        _chegou()

    return resposta


def ofertas(local, item, rot, desde, prazo=ESPERA, qualidade=None,
            mesmo_calado=False):
    """O livro de venda inteiro, [(preco, quantidade)] do mais barato, ou None.

    <qualidade> None junta todas - e o que a lista de compra sem filtro mostra."""

    def tentar():
        livros = _livros_do_item(local, item, rot, desde)
        juntas = []

        for q, l in livros.items():
            if qualidade is None or q == qualidade:
                juntas += l.get('ofertas') or []

        return sorted(juntas) if juntas else None

    return _esperar(tentar, prazo, mesmo_calado)


def ultimo_do_item(local, item, desde, prazo=ESPERA, qualidade=1):
    """(pedido, menor_venda) do item aberto, de qualquer grau, chegado depois de <desde>.

    E o caso do Mercado Negro na venda: o painel abre o item que esta NO
    INVENTARIO, e o grau e o dele - quem chama nao sabe qual e.

    O PEDIDO E O MAIOR QUE O ITEM ATENDE: os de qualidade <qualidade> ou menor.
    A venda e a menor oferta da propria qualidade."""

    def tentar():
        painel = _painel(local, item, desde)

        if painel is None:
            return None

        _, dela = painel

        pedidos = [_melhor(l, 'pedidos') for q, l in dela.items() if q <= qualidade]
        pedidos = [p for p in pedidos if p]

        return (max(pedidos) if pedidos else None,
                _melhor(dela.get(qualidade, {}), 'ofertas'))

    return _esperar(tentar, prazo)


def _painel(local, item, desde):
    """((grau, ench), {qualidade: livro}) do item aberto, ou None.

    A combinacao do painel aberto e a do pacote mais recente do item."""

    troncos = {identificadores.tronco(item)} - {None}

    with _trava:
        recentes = [(l.get('seq', 0), (g, e), q, l)
                    for (lo, t, g, e, q), l in _livros.items()
                    if lo == local and t in troncos
                    and l.get('seq', 0) > desde]

    if not recentes:
        return None

    _, combinacao, _, _ = max(recentes, key=lambda a: a[0])

    return combinacao, {q: l for _, c, q, l in recentes if c == combinacao}


def combinacao_aberta(local, item, desde):
    """'T5.2' do item aberto no painel, pelo pacote mais recente, ou None.

    Nao espera: serve para conferir, depois que ultimo_do_item ja viu o pacote,
    se o painel abriu a combinacao que se pretendia vender."""

    painel = _painel(local, item, desde)

    return mercado.rotulo(*painel[0]) if painel else None


def esquecer():
    """Joga fora os livros em memoria. Existe para os testes."""

    with _trava:
        _livros.clear()
        _estado.update(quando=None, local=None, pacotes=0, ordens=0)

#endregion

#region Gravar no disco sem atrapalhar

_gravar = threading.Event()


def _pedir_gravacao():
    _gravar.set()


def _gravador():
    """Grava o precos.json pouco depois de os pacotes pararem de chegar."""

    while True:
        _gravar.wait()
        time.sleep(2)
        _gravar.clear()
        mercado.salvar()

#endregion

#region O receptor

_servidor = None
_porta = None


class _Receptor(BaseHTTPRequestHandler):

    def do_POST(self):

        tamanho = int(self.headers.get('Content-Length') or 0)
        corpo = self.rfile.read(tamanho) if tamanho else b''

        if self.path.strip('/').startswith('marketorders'):
            try:
                receber(json.loads(corpo.decode('utf-8')))
            except Exception:
                comum.contar('pacotes_ilegiveis')

        # 200 SEMPRE: o cliente so considera entregue com 200, e reenviar o que
        # nao interessa aqui (historicos, ouro) seria trafego a toa
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')

    def log_message(self, *args):
        pass


def iniciar_servidor(porta=PORTA_PADRAO):
    """Liga o receptor em 127.0.0.1. Devolve (ok, mensagem). Idempotente."""

    global _servidor, _porta

    if _servidor is not None:
        return True, ''

    try:
        _servidor = ThreadingHTTPServer(('127.0.0.1', int(porta)), _Receptor)
    except OSError as e:
        return False, f'a porta {porta} esta ocupada ({e.strerror or e})'

    _porta = int(porta)

    threading.Thread(target=_servidor.serve_forever, daemon=True).start()
    threading.Thread(target=_gravador, daemon=True).start()

    return True, ''


def parar_servidor():

    global _servidor

    if _servidor is not None:
        try:
            _servidor.shutdown()
            _servidor.server_close()
        except Exception:
            pass
        _servidor = None

    # o que chegou e ainda nao foi para o disco
    if _estado['pacotes']:
        mercado.salvar()

#endregion

#region O cliente

_processo = None
_cliente_situacao = 'desligado'


def achar_cliente(configurado=''):
    """O albiondata-client.exe: o configurado, ou onde o instalador poe."""

    for caminho in (configurado,) + CAMINHOS_COMUNS:
        if caminho and os.path.isfile(caminho):
            return caminho

    return None


def cliente_aberto():
    """True se ha um albiondata-client rodando nesta maquina (nosso ou nao)."""

    try:
        saida = subprocess.run(
            ['tasklist', '/FI', f'IMAGENAME eq {NOME_DO_CLIENTE}', '/FO', 'CSV', '/NH'],
            capture_output=True, text=True, timeout=10,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout
    except Exception:
        return False

    return NOME_DO_CLIENTE.lower() in saida.lower()


def _destino(porta=None):
    """O endereco para onde o cliente deste bot manda os precos."""

    return f'http://127.0.0.1:{porta or _porta or PORTA_PADRAO}'


def cliente_desta_porta(porta=None):
    """O PID de um albiondata-client que ja manda para este bot, ou None.

    E O CLIENTE QUE O BOT DEIXOU RODANDO da ultima vez - ver iniciar_cliente.
    Reconhecido pela linha de comando, que traz o endereco local."""

    destino = _destino(porta)

    try:
        saida = subprocess.run(
            ['powershell', '-NoProfile', '-Command',
             f"Get-CimInstance Win32_Process -Filter \"Name='{NOME_DO_CLIENTE}'\" | "
             "ForEach-Object { \"$($_.ProcessId)|$($_.CommandLine)\" }"],
            capture_output=True, text=True, timeout=20,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).stdout
    except Exception:
        return None

    for linha in saida.splitlines():
        pid, _, comando = linha.partition('|')
        if destino in comando and pid.strip().isdigit():
            return int(pid)

    return None


# O cliente que ja estava rodando, mandando para este bot, quando o bot abriu.
_adotado = None


def iniciar_cliente(configurado='', porta=None):
    """Abre o albiondata-client mandando os precos SO para este bot.

    -i troca o destino publico pelo endereco local: nada sai do computador. O
    projeto publico nao recebe nada desta maquina.

    O CLIENTE QUE JA MANDA PARA ESTE BOT E REAPROVEITADO. O albiondata-client so
    manda preco depois de ver uma troca de mapa no jogo - e ali que ele descobre
    onde voce esta. Fechado junto com o bot e aberto de novo com ele, cada
    abertura do bot pedia outra troca de mapa, e ate la a leitura caia no OCR.
    Por isso o bot deixa o cliente rodando ao fechar (ver ponte._encerrar_rede)
    e o adota ao abrir.

    Devolve (ok, mensagem)."""

    global _processo, _adotado, _cliente_situacao

    if _processo is not None and _processo.poll() is None:
        _cliente_situacao = 'rodando'
        return True, ''

    caminho = achar_cliente(configurado)

    if caminho is None:
        _cliente_situacao = 'nao_encontrado'
        return False, ('albiondata-client nao encontrado. Instale pelo site do '
                       'projeto e informe o caminho em Ajustes.')

    _adotado = cliente_desta_porta(porta)

    if _adotado is not None:
        _cliente_situacao = 'rodando'
        return True, ''

    if cliente_aberto():
        _cliente_situacao = 'outro_aberto'
        return False, ('Ja ha um albiondata-client aberto, com as opcoes dele. '
                       'Feche-o para o bot abrir um que manda os precos so para '
                       'este computador.')

    argumentos = [caminho, '-i', _destino(porta), '-minimize']

    try:
        _processo = subprocess.Popen(
            argumentos, cwd=os.path.dirname(caminho),
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

    except OSError as e:
        _processo = None
        _cliente_situacao = 'erro'

        if getattr(e, 'winerror', None) == 740:
            return False, ('O albiondata-client pede para rodar como '
                           'administrador. Abra o bot como administrador, ou '
                           'abra o cliente a mao com: ' + ' '.join(argumentos[1:]))

        return False, f'nao foi possivel abrir o albiondata-client: {e}'

    _cliente_situacao = 'rodando'

    return True, ''


def parar_cliente():
    """Fecha o cliente - so o deste bot: o que ele abriu ou o que ele adotou.

    E para desligar a leitura pela rede ou trocar a porta. Fechar o bot NAO
    passa por aqui: o cliente fica rodando para nao perder o mapa."""

    global _processo, _adotado, _cliente_situacao

    if _processo is not None and _processo.poll() is None:
        try:
            _processo.terminate()
            _processo.wait(5)
        except Exception:
            pass

    if _adotado is not None:
        try:
            subprocess.run(['taskkill', '/PID', str(_adotado), '/F'],
                           capture_output=True, timeout=10,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except Exception:
            pass

    _processo = None
    _adotado = None
    _cliente_situacao = 'desligado'

#endregion
