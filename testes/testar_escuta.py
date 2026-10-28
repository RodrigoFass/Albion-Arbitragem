################################
#                              #
#           TESTES             #
#           ESCUTA             #
#                              #
################################

# A leitura pela rede, sem o jogo e sem o albiondata-client: os pacotes aqui tem
# o formato exato que o cliente manda (lib/market.go do projeto), e o receptor
# HTTP e o de verdade, ouvindo nesta maquina.
#
#     python testes/testar_escuta.py

import atexit
import json
import os
import shutil
import socket
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_DADOS = tempfile.mkdtemp(prefix='albion-escuta-')
os.environ['ALBION_DADOS'] = _DADOS
atexit.register(shutil.rmtree, _DADOS, True)

from motor import comum        # noqa: E402
from motor import comprador    # noqa: E402
from motor import conferidor   # noqa: E402
from motor import escuta       # noqa: E402
from motor import mercado      # noqa: E402

ok = 0
falhas = []
grupo_atual = ''


def grupo(nome):
    global grupo_atual
    grupo_atual = nome
    print(f'\n--- {nome}')


def checar(nome, condicao, detalhe=''):
    global ok

    if condicao:
        ok += 1
        print(f'  ok    {nome}')
    else:
        falhas.append(f'{grupo_atual}: {nome}' + (f'  ({detalhe})' if detalhe else ''))
        print(f'  FALHA {nome}' + (f'  ({detalhe})' if detalhe else ''))


def ordem(item_id, local, preco, quantidade=1, tipo='offer', qualidade=1, ench=0):
    """Uma ordem como o cliente manda: preco x 10.000."""

    return {'Id': int(time.time() * 1000) % 10 ** 9, 'ItemTypeId': item_id,
            'ItemGroupTypeId': item_id.split('@')[0], 'LocationId': local,
            'QualityLevel': qualidade, 'EnchantmentLevel': ench,
            'UnitPriceSilver': preco * 10_000, 'Amount': quantidade,
            'AuctionType': tipo, 'Expires': '2026-11-01T00:00:00'}


# ============================================================
grupo('o identificador e o mercado')

checar('o id vira tronco, grau e encantamento',
       escuta.decompor('T5_MAIN_SWORD@2') == ('MAIN_SWORD', 5, 2))

checar('sem @ e encantamento zero', escuta.decompor('T6_2H_CLAYMORE') == ('2H_CLAYMORE', 6, 0))

checar('recurso e o que nao for equipamento nao vira item',
       escuta.decompor('UNIQUE_HIDEOUT') is None)

checar('a cidade vem com zeros e casa pelo numero', escuta.local_de('0007') == 'Thetford')

checar('3003 e o Mercado Negro', escuta.local_de('3003') == mercado.MERCADO_NEGRO)

checar('e lugar que nao e mercado conhecido fica de fora', escuta.local_de('4300') is None)


# ============================================================
grupo('um pacote vira preco no banco')

mercado.usar_banco({})
escuta.esquecer()

n = escuta.receber({'Orders': [
    ordem('T6_MAIN_SWORD@1', '0007', 12000, 3),
    ordem('T6_MAIN_SWORD@1', '0007', 11500, 2, qualidade=2),
    ordem('T6_MAIN_SWORD@1', '0007', 13000, 5),
    ordem('UNIQUE_HIDEOUT', '0007', 999),
]})

checar('aproveita as ordens de equipamento', n == 3, str(n))

preco, idade = mercado.ler('Thetford', 'Broadsword', 'T6.1')

checar('o preco vem dividido por 10.000', preco == 11500, str(preco))
checar('na cidade vale a oferta mais barata de qualquer qualidade', preco == 11500)
checar('e o preco e novo', idade is not None and idade < 0.01)

q, _ = mercado.ler_qualidades('Thetford', 'Broadsword', 'T6.1')
checar('cada qualidade guarda a sua', q.get(1, {}).get('oferta') == 12000
       and q.get(2, {}).get('oferta') == 11500, str(q))

checar('na cidade o livro inteiro vai junto, com as quantidades, para a media',
       mercado.ler_ofertas('Thetford', 'Broadsword', 'T6.1')
       == [(11500, 2), (12000, 3), (13000, 5)],
       str(mercado.ler_ofertas('Thetford', 'Broadsword', 'T6.1')))

escuta.receber({'Orders': [
    ordem('T6_MAIN_SWORD@1', '3003', 30000, 1, 'offer'),
    ordem('T6_MAIN_SWORD@1', '3003', 25000, 4, 'request'),
    ordem('T6_MAIN_SWORD@1', '3003', 26000, 1, 'request'),
    ordem('T6_MAIN_SWORD@1', '3003', 40000, 1, 'request', qualidade=3),
]})

checar('no Mercado Negro o preco e a menor venda da qualidade Normal',
       mercado.ler(mercado.MERCADO_NEGRO, 'Broadsword', 'T6.1')[0] == 30000)
checar('e o outro e o maior pedido de compra da Normal',
       mercado.ler_outro(mercado.MERCADO_NEGRO, 'Broadsword', 'T6.1') == 26000)

q, _ = mercado.ler_qualidades(mercado.MERCADO_NEGRO, 'Broadsword', 'T6.1')
checar('o pedido da qualidade 3 fica guardado a parte', q.get(3, {}).get('pedido') == 40000, str(q))

# so os pedidos chegam: as ofertas de antes continuam
escuta.receber({'Orders': [ordem('T6_MAIN_SWORD@1', '3003', 27000, 1, 'request')]})
checar('um pacote so de pedidos nao apaga a venda', mercado.ler(
    mercado.MERCADO_NEGRO, 'Broadsword', 'T6.1')[0] == 30000)
checar('e cada pacote substitui aquele lado do livro (nao soma)',
       mercado.ler_outro(mercado.MERCADO_NEGRO, 'Broadsword', 'T6.1') == 27000)

checar('a rede conta como ativa depois de receber', escuta.ativa())
checar('e sabe de onde veio o ultimo pacote', escuta.local_atual() == mercado.MERCADO_NEGRO)

checar('nome que difere no menu tambem recebe (Greathammer)',
       escuta.receber({'Orders': [ordem('T5_2H_HAMMER', '0007', 9000)]}) == 1
       and mercado.ler('Thetford', 'Greathammer', 'T5.0')[0] == 9000)

# O ROYAL SIGIL FOGE DO PADRAO T4_...: o grau vem no fim do identificador. Sem
# isto, o Sigil aberto no mercado nao virava preco, e o craft Royal nao fechava
checar('o identificador do Royal Sigil e reconhecido',
       escuta.decompor('QUESTITEM_TOKEN_ROYAL_T6') == ('QUESTITEM_TOKEN_ROYAL', 6, 0),
       str(escuta.decompor('QUESTITEM_TOKEN_ROYAL_T6')))

escuta.receber({'Orders': [ordem('QUESTITEM_TOKEN_ROYAL_T6', '1002', 2100, 40),
                           ordem('QUESTITEM_TOKEN_ROYAL_T6', '1002', 2050, 12)]})

checar('e o Sigil aberto no mercado vira preco na cidade, no grau dele',
       mercado.ler('Lymhurst', 'Royal Sigil', 'T6.0')[0] == 2050,
       str(mercado.ler('Lymhurst', 'Royal Sigil', 'T6.0')))


# ============================================================
grupo('quem le espera o pacote certo')

# o numero do pacote: 0 aceita todos; a marca de agora, nenhum dos que ja chegaram
antes = 0
depois = escuta.marca()

checar('precos da combinacao, chegados depois do instante pedido',
       escuta.precos('Thetford', 'Broadsword', 'T6.1', desde=antes, prazo=0.1) == (11500, None))

checar('pacote de antes da troca de filtro nao serve',
       escuta.precos('Thetford', 'Broadsword', 'T6.1', desde=depois, prazo=0.1) is None)

checar('combinacao que nao chegou cai para o OCR',
       escuta.precos('Thetford', 'Broadsword', 'T7.0', desde=antes, prazo=0.1) is None)

checar('no Mercado Negro, a venda e o pedido da Normal',
       escuta.precos(mercado.MERCADO_NEGRO, 'Broadsword', 'T6.1', desde=antes, prazo=0.1)
       == (30000, 27000))

checar('o livro inteiro, do mais barato, com quantidades',
       escuta.ofertas('Thetford', 'Broadsword', 'T6.1', desde=antes, prazo=0.1)
       == [(11500, 2), (12000, 3), (13000, 5)])

checar('ou so de uma qualidade',
       escuta.ofertas('Thetford', 'Broadsword', 'T6.1', desde=antes, prazo=0.1, qualidade=1)
       == [(12000, 3), (13000, 5)])

checar('na venda, o ultimo livro do item aberto, de qualquer grau',
       escuta.ultimo_do_item(mercado.MERCADO_NEGRO, 'Broadsword', antes, prazo=0.1)
       == (27000, 30000))

_real_relatar = comum.relatar
comum.relatar = lambda *a, **k: None
try:
    for _ in range(escuta.FALTAS_PARA_CALAR - 1):
        escuta.faltou()
    _ainda = escuta.ativa()
    escuta.faltou()
    _calou = not escuta.ativa()
finally:
    comum.relatar = _real_relatar

checar('algumas faltas nao calam a rede', _ainda)
checar('muitas seguidas, sim: a leitura volta ao OCR', _calou)

escuta.esquecer()
inicio = time.monotonic()
checar('com a rede calada ninguem espera por ela',
       escuta.precos('Thetford', 'Broadsword', 'T6.1', desde=antes, prazo=2) is None
       and time.monotonic() - inicio < 0.2, f'{time.monotonic() - inicio:.2f} s')


# ============================================================
grupo('a varredura usa a rede e pula o OCR')


class TelaDeMentira:
    """Uma tela cujo OCR NAO pode ser chamado: a rede tem de bastar."""

    regiao = (0, 0, 1, 1)

    def __init__(self):
        self.ocr = 0
        self.g = None
        self.e = 0

    def abrir(self, item):
        return True, ''

    def fechar(self):
        pass

    def base(self):
        return None

    def ler(self, anterior):
        self.ocr += 1
        return None

    def vazio(self):
        return True

    def outro_preco(self):
        return None

    def _pedir(self):
        # cada troca de filtro: o jogo pede o livro ao servidor e o cliente repassa
        if self.g is not None:
            escuta.receber({'Orders': [ordem(
                f'T{self.g}_MAIN_SWORD' + (f'@{self.e}' if self.e else ''),
                '0007', 1000 * self.g + 100 * self.e, 2)]})

    def encantamento(self, ench):
        self.e = ench
        self._pedir()

    def grau(self, item, grau, ench):
        self.g = grau
        self._pedir()
        return True


mercado.usar_banco({})
escuta.receber({'Orders': [ordem('T4_MAIN_SWORD', '0007', 1)]})   # rede ativa

_tela = TelaDeMentira()
_real_situacao = conferidor._situacao
conferidor._situacao = lambda *a: None
_real_avisar = comum.avisar
comum.avisar = lambda *a, **k: None

try:
    _lidos = conferidor.ler_item('Thetford', 'Broadsword', [(6, 0), (6, 1), (7, 0)], _tela)
finally:
    conferidor._situacao = _real_situacao
    comum.avisar = _real_avisar

checar('as tres combinacoes saem da rede', [p for _, p, _ in _lidos] == [6000, 6100, 7000],
       str(_lidos))
checar('e o OCR nao foi chamado nenhuma vez', _tela.ocr == 0, str(_tela.ocr))


# ============================================================
grupo('a compra le o livro pela rede')

_antes_do_livro = escuta.marca()
escuta.receber({'Orders': [ordem('T6_MAIN_SWORD', '0007', 900, 4),
                           ordem('T6_MAIN_SWORD', '0007', 950, 6)]})

# o comprador pede exatamente isto depois de filtrar a lista - sem painel e
# sem OCR (ver comprador.comprar_linha)
_livro = escuta.ofertas('Thetford', 'Broadsword', 'T6.0', desde=_antes_do_livro)

checar('o livro de compra inteiro vem da rede, sem OCR', _livro == [(900, 4), (950, 6)], str(_livro))


# ============================================================
grupo('o teste da rede no primeiro item')

# CALADA NAO E QUEBRADA: sem pacote ha 10 minutos e so ninguem ter aberto o
# mercado. O teste espera o pacote mesmo assim.
_antes_do_teste = escuta.marca()
escuta.receber({'Orders': [ordem('T6_MAIN_SWORD', '0007', 880, 2)]})
escuta._estado['quando'] = None     # calada: nenhum pacote recente

checar('calada, a espera de sempre desiste na hora',
       escuta.ofertas('Thetford', 'Broadsword', 'T6.0', desde=_antes_do_teste,
                      prazo=0.2) is None)

checar('e o teste espera o pacote mesmo assim',
       escuta.ofertas('Thetford', 'Broadsword', 'T6.0', desde=_antes_do_teste,
                      prazo=0.2, mesmo_calado=True) == [(880, 2)])

checar('o mesmo vale para o preco da varredura',
       escuta.precos('Thetford', 'Broadsword', 'T6.0', desde=_antes_do_teste,
                     prazo=0.2, mesmo_calado=True) == (880, None))

checar('e o aviso de quando ela nao responde fala de ExitLag e VPN',
       'ExitLag' in escuta.AVISO_SEM_REDE and 'VPN' in escuta.AVISO_SEM_REDE)


# ============================================================
grupo('a venda le o pedido que a qualidade atende')

escuta.esquecer()
_t0 = escuta.marca()
escuta.receber({'Orders': [
    ordem('T7_MAIN_SWORD', '3003', 20_000, 2, 'request', qualidade=1),
    ordem('T7_MAIN_SWORD', '3003', 30_000, 1, 'request', qualidade=3),
    ordem('T7_MAIN_SWORD', '3003', 90_000, 1, 'request', qualidade=5),
    ordem('T7_MAIN_SWORD', '3003', 35_000, 1, 'offer', qualidade=3),
    ordem('T7_MAIN_SWORD', '3003', 24_000, 1, 'offer', qualidade=1),
]})

checar('a unidade Normal conta com o pedido da Normal',
       escuta.ultimo_do_item(mercado.MERCADO_NEGRO, 'Broadsword', _t0, prazo=0.1)
       == (20_000, 24_000))

checar('a de qualidade 3 conta com o maior pedido de qualidade 3 ou menor',
       escuta.ultimo_do_item(mercado.MERCADO_NEGRO, 'Broadsword', _t0, prazo=0.1,
                             qualidade=3) == (30_000, 35_000))


# ============================================================
grupo('a compra por qualidade')

from motor import compra       # noqa: E402
from motor import coordenadas as cd  # noqa: E402
from motor import filtros      # noqa: E402
from motor import historico    # noqa: E402
from motor import lucro        # noqa: E402
from motor import menu         # noqa: E402


class JogoDaCompra:
    """A tela de compra: registra os filtros e responde pela rede ao filtrar.

    Como a varredura: a lista filtrada faz o jogo pedir as ofertas daquela
    combinacao, e o pacote chega sem painel nenhum aberto."""

    def __init__(self, manda_livro=True):
        self.filtros = []
        self.manda_livro = manda_livro
        self.compradas = 0
        self.registros = []

    def qualidade(self, v):
        self.filtros.append(('qualidade', v))
        if v and self.manda_livro:
            escuta.receber({'Orders': [
                ordem('T6_MAIN_SWORD', '0007', 9_000, 5, qualidade=1),
                ordem('T6_MAIN_SWORD', '0007', 12_000, 2, qualidade=3),
            ]})

    def abrir_painel(self):
        self.filtros.append(('painel', None))
        return True

    def comprar_uma(self, esperado, aceitar=None):
        self.compradas += 1
        return 'comprou', esperado, ''


def _comprar(jogo, linha):
    reais = (menu.selecionar, filtros.grau, filtros.encantamento, filtros.qualidade,
             filtros.limpar, compra.abrir_painel, compra.fechar_painel,
             compra.comprar_uma, historico.registrar, comum.avisar)

    menu.selecionar = lambda item: (True, '')
    filtros.grau = lambda v: jogo.filtros.append(('grau', v))
    filtros.encantamento = lambda v: jogo.filtros.append(('ench', v))
    filtros.qualidade = jogo.qualidade
    filtros.limpar = lambda: jogo.filtros.append(('limpar', None))
    compra.abrir_painel = jogo.abrir_painel
    compra.fechar_painel = lambda: None
    compra.comprar_uma = jogo.comprar_uma
    historico.registrar = lambda *a, **k: (jogo.registros.append(k), (True, ''))[1]
    comum.avisar = lambda *a, **k: None

    try:
        return comprador.comprar_linha(linha, 'Thetford', 0.1, lucro.TAXA_PADRAO)
    finally:
        (menu.selecionar, filtros.grau, filtros.encantamento, filtros.qualidade,
         filtros.limpar, compra.abrir_painel, compra.fechar_painel,
         compra.comprar_uma, historico.registrar, comum.avisar) = reais


_linha_q = lucro.linha('Broadsword', 'T6.0', 12_000, 25_000, 2, ordem_na_compra=False)
_linha_q['qualidade'] = 3

escuta.receber({'Orders': [ordem('T4_MAIN_SWORD', '0007', 1)]})   # rede ativa
cd._calibrados.discard('CMP_BARRA_QUAL')

_jogo = JogoDaCompra()
_r = _comprar(_jogo, _linha_q)

checar('sem o filtro de qualidade calibrado, nao compra e diz por que',
       _r['unidades'] == 0 and 'calibrado' in _r['motivo'] and not _jogo.filtros, str(_r))

cd._calibrados.update({'CMP_BARRA_QUAL', 'CMP_QUAL_TOPO'})

_jogo = JogoDaCompra()
_r = _comprar(_jogo, _linha_q)

checar('calibrado e com a rede, compra as duas unidades', _r['unidades'] == 2, str(_r))
checar('sempre na hora', _r['modo'] == 'na hora', str(_r))
checar('com o livro chegando pela lista filtrada, sem abrir o painel',
       ('qualidade', 3) in _jogo.filtros and ('painel', None) not in _jogo.filtros,
       str(_jogo.filtros))
checar('e devolvido a "Todas" no fim, antes de limpar',
       _jogo.filtros[-2:] == [('qualidade', 0), ('limpar', None)], str(_jogo.filtros))
checar('e o historico guarda a qualidade de cada compra',
       [k.get('qualidade') for k in _jogo.registros] == [3, 3], str(_jogo.registros))

_jogo = JogoDaCompra(manda_livro=False)
_r = _comprar(_jogo, _linha_q)

checar('sem o livro da qualidade pela rede, nao compra no escuro',
       _r['unidades'] == 0 and 'rede' in _r['motivo'] and _jogo.compradas == 0, str(_r))

cd._calibrados.discard('CMP_BARRA_QUAL')
cd._calibrados.discard('CMP_QUAL_TOPO')


# ============================================================
grupo('o receptor HTTP, de verdade')

with socket.socket() as s:
    s.bind(('127.0.0.1', 0))
    _porta = s.getsockname()[1]

ok_srv, erro = escuta.iniciar_servidor(_porta)
checar('liga numa porta livre', ok_srv, erro)

escuta.esquecer()
mercado.usar_banco({})


def postar(topico, dados):
    pedido = urllib.request.Request(
        f'http://127.0.0.1:{_porta}/{topico}', data=json.dumps(dados).encode('utf-8'),
        headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(pedido, timeout=5) as r:
        return r.status


checar('o cliente recebe 200 pelas ordens',
       postar('marketorders.ingest', {'Orders': [ordem('T8_MAIN_SWORD@1', '4002', 500000)]}) == 200)

checar('e o preco ja esta no banco', mercado.ler('Fort Sterling', 'Broadsword', 'T8.1')[0] == 500000)

checar('outros topicos (historico, ouro) recebem 200 e sao ignorados',
       postar('goldprices.ingest', {'Prices': [1]}) == 200)

checar('a situacao diz que esta recebendo', escuta.situacao()['recebendo']
       and escuta.situacao()['local'] == 'Fort Sterling')

checar('o receptor so ouve esta maquina', escuta._servidor.server_address[0] == '127.0.0.1')

escuta.parar_servidor()
checar('e desliga', escuta._servidor is None)


# ============================================================
grupo('o cliente abre so para este computador')

# SEM PROCURAR NO COMPUTADOR DE VERDADE: com o cliente instalado, este teste
# o abria de fato - e o processo vivo atropelava os testes seguintes.
#
# E SEM ADOTAR O CLIENTE DE VERDADE: com o bot em uso, o albiondata-client dele
# esta rodando e mandando para a mesma porta. Adotado aqui, o parar_cliente() do
# teste o fecharia - e o mapa que ele ja conhecia se perderia.
_desta_porta_real = escuta.cliente_desta_porta
escuta.cliente_desta_porta = lambda porta=None: None

_achar_real = escuta.achar_cliente
escuta.achar_cliente = lambda configurado='': None

try:
    ok_nada, msg_nada = escuta.iniciar_cliente(r'C:\nao\existe\albiondata-client.exe')
finally:
    escuta.achar_cliente = _achar_real

checar('sem o programa instalado, diz o que fazer',
       not ok_nada and 'Instale' in msg_nada, msg_nada)

_chamado = {}


class ProcessoFalso:
    def __init__(self, argumentos, **k):
        _chamado['args'] = argumentos

    def poll(self):
        return None

    def terminate(self):
        _chamado['fechado'] = True

    def wait(self, t=None):
        return 0


_falso = os.path.join(_DADOS, 'albiondata-client.exe')
open(_falso, 'w').close()

_reais = (escuta.subprocess.Popen, escuta.cliente_aberto)
escuta.subprocess.Popen = ProcessoFalso
escuta.cliente_aberto = lambda: False

try:
    ok_cli, msg = escuta.iniciar_cliente(_falso, porta=8642)
    escuta.parar_cliente()
finally:
    escuta.subprocess.Popen, escuta.cliente_aberto = _reais

_args = ' '.join(_chamado.get('args', []))

checar('abre o cliente', ok_cli, msg)
checar('mandando para o endereco local', '-i http://127.0.0.1:8642' in _args, _args)
checar('e para nenhum servidor publico', 'albion-online-data.com' not in _args, _args)
checar('e o bot fecha o que abriu', _chamado.get('fechado'))

escuta.cliente_aberto = lambda: True
try:
    ok_cli, msg = escuta.iniciar_cliente(_falso)
finally:
    escuta.cliente_aberto = _reais[1]

checar('com outro cliente ja aberto, nao abre um segundo e explica', not ok_cli and 'Feche' in msg, msg)

# O CLIENTE QUE JA MANDA PARA ESTE BOT E ADOTADO: foi o bot que o deixou
# rodando ao fechar, e ele ainda sabe em que mapa voce esta.
_chamado.clear()
_mortos = []
_reais = (escuta.subprocess.Popen, escuta.cliente_aberto, escuta.subprocess.run)
escuta.subprocess.Popen = ProcessoFalso
escuta.cliente_aberto = lambda: True
escuta.cliente_desta_porta = lambda porta=None: 4242
escuta.subprocess.run = lambda args, **k: _mortos.append(args)

try:
    ok_cli, msg = escuta.iniciar_cliente(_falso, porta=8642)
    _situacao_adotado = escuta.situacao()['cliente']
    escuta.parar_cliente()
finally:
    escuta.subprocess.Popen, escuta.cliente_aberto, escuta.subprocess.run = _reais
    escuta.cliente_desta_porta = lambda porta=None: None

checar('o cliente que ja manda para este bot e reaproveitado, sem abrir outro',
       ok_cli and _situacao_adotado == 'rodando' and 'args' not in _chamado, msg)

checar('e desligar a rede fecha o adotado tambem',
       any('4242' in a for a in _mortos), str(_mortos))

# FECHAR O BOT NAO FECHA O CLIENTE
from interface import ponte as _ponte   # noqa: E402

_reais = (escuta.parar_cliente, escuta.parar_servidor)
_chamadas_fim = []
escuta.parar_cliente = lambda: _chamadas_fim.append('cliente')
escuta.parar_servidor = lambda: _chamadas_fim.append('servidor')

try:
    _ponte.Api._encerrar_rede(None)
finally:
    escuta.parar_cliente, escuta.parar_servidor = _reais

checar('ao fechar o bot, o receptor fecha e o cliente fica rodando',
       _chamadas_fim == ['servidor'], str(_chamadas_fim))

escuta.cliente_desta_porta = _desta_porta_real


# ============================================================
print(f'\n===== {ok} ok, {len(falhas)} falhas =====')

for f in falhas:
    print(f'  {f}')

raise SystemExit(1 if falhas else 0)
