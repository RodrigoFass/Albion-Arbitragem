################################
#                              #
#           TESTES             #
#            TELAS             #
#                              #
################################

# A interface de verdade, numa janela escondida: cada tela abre, desenha o que
# devia e nao solta erro de JavaScript.
#
# Os outros testes conferem a Api que as telas chamam; este confere as telas.
# Um erro de digitacao num .js nao quebra teste nenhum de Python - so aparece
# quando alguem abre aquela tela. Aqui ele aparece antes.
#
# Precos e historico de mentira, numa pasta temporaria: nunca nos seus arquivos.
#
#     python testes/testar_telas.py

import atexit
import os
import random
import shutil
import sys
import tempfile
import threading
import time

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)

_DADOS = tempfile.mkdtemp(prefix='albion-telas-')
os.environ['ALBION_DADOS'] = _DADOS
atexit.register(shutil.rmtree, _DADOS, True)

import webview                # noqa: E402

from motor import ajustes     # noqa: E402
from motor import catalogo    # noqa: E402
from motor import historico   # noqa: E402
from motor import mercado     # noqa: E402
from interface.ponte import Api   # noqa: E402

PASTA_WEB = os.path.join(RAIZ, 'interface', 'web')
ERROS_JS = os.path.join(_DADOS, 'registros', 'interface-erros.txt')

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


# --- dados de mentira ----------------------------------------------------------

random.seed(7)
catalogo.carregar()
_agora = time.time()

for _item, _rot, _ in catalogo.para_calcular()[:400]:
    _base = random.randint(5_000, 400_000)
    mercado.gravar('Thetford', _item, _rot, _base, quando=_agora - 600)
    mercado.gravar(mercado.MERCADO_NEGRO, _item, _rot, int(_base * random.uniform(1.0, 1.9)),
                   quando=_agora - 300, outro=int(_base * random.uniform(0.9, 1.6)))
mercado.salvar()

for _item, _rot, _pago, _vendido in (('Broadsword', 'T6.1', 120_000, 190_000),
                                     ('Claymore', 'T5.2', 80_000, 0)):
    historico.comprou('Thetford', _item, _rot, 3, _pago, 'na hora')
    if _vendido:
        historico.vendeu(mercado.MERCADO_NEGRO, _item, _rot, 2, _vendido, 'na hora')


# --- a janela -------------------------------------------------------------------

api = Api(None)

janela = webview.create_window('testar telas', os.path.join(PASTA_WEB, 'index.html'),
                               js_api=api, width=1280, height=860, hidden=True)
calibrador = webview.create_window('testar calibrador', os.path.join(PASTA_WEB, 'calibrador.html'),
                                   js_api=api, width=1280, height=860, hidden=True)
api._ligar(janela, lambda qual: None)


def js(codigo, espera=0.0):
    """Roda no app e devolve o resultado; <espera> da tempo da tela responder."""

    valor = janela.evaluate_js(codigo)
    if espera:
        time.sleep(espera)
    return valor


def quantos(seletor):
    return js(f'document.querySelectorAll({seletor!r}).length')


def visivel(seletor):
    """Quantos dos que casam estao na tela (nao escondidos)."""

    return js(f'[...document.querySelectorAll({seletor!r})].filter(e => e.offsetParent !== null).length')


def rodar():

    try:
        janela.events.loaded.wait(30)
        calibrador.events.loaded.wait(30)
        time.sleep(2)

        # ---------------------------------------------------------------------
        grupo('cada tela abre e desenha')

        for chave, titulo in (('operacao', 'Operação'), ('itens', 'Itens'),
                              ('royal', 'Craft Royal'),
                              ('historico', 'Histórico'), ('ajustes', 'Ajustes')):
            js(f"app.ir('{chave}')", 1.5)
            checar(f'{titulo}: o titulo', js("document.getElementById('titulo').textContent") == titulo)
            texto = js(f"app.montadas['{chave}'].textContent.trim().length") or 0
            checar(f'{titulo}: com conteudo', texto > 80, f'{texto} caracteres')

        # ---------------------------------------------------------------------
        grupo('Operacao: os tres passos')

        js("app.ir('operacao')", 1.0)
        checar('os sete mercados', visivel('.mercado') == 7, str(visivel('.mercado')))
        checar('a situacao da rede numa pilula', visivel('.pilula-rede') == 1)

        # as combinacoes da leitura: o botao abre as caixas, e desmarcar uma
        # muda o resumo do botao
        checar('as combinacoes comecam todas marcadas',
               (js("document.querySelector('.botao-combinacoes').textContent") or '').startswith('Todas'))
        js("document.querySelector('.botao-combinacoes').click()", 0.5)
        checar('o botao abre as 13 caixas', visivel('.combinacoes input[type=checkbox]') == 13,
               str(visivel('.combinacoes input[type=checkbox]')))
        js("document.querySelector('.combinacoes input[data-rotulo=\"T5.2\"]').click()", 1.0)
        checar('desmarcar uma muda o resumo', js("document.querySelector('.botao-combinacoes').textContent") == '12 de 13',
               str(js("document.querySelector('.botao-combinacoes').textContent")))
        checar('e fica guardado', 'T5.2' not in (api.combinacoes_para_ler()['marcadas']))
        api.marcar_combinacoes_para_ler(api.combinacoes_para_ler()['rotulos'])
        js("app.ir('operacao')", 1.0)

        js("document.querySelector('[data-passo=comprar]').click()", 2.0)
        linhas = visivel('[data-tela=operacao] .tabela tbody tr')
        checar('Comprar: a lista com os precos lidos', linhas > 0, f'{linhas} linhas')
        checar('Comprar: sem a coluna de qualidade, desligada',
               visivel('[data-tela=operacao] .tabela th[data-col=qualidade]') == 0)
        checar('Comprar: os campos com a unidade dentro',
               visivel('[data-tela=operacao] .com-unidade') >= 3)

        texto = js("[...document.querySelectorAll('[data-tela=operacao] .tabela tbody tr')]"
                   ".map(t => t.textContent).join(' ')") or ''
        checar('Comprar: a venda diz o caminho, na hora ou por ordem',
               '· na hora' in texto or '· ordem' in texto)

        js("document.querySelector('[data-passo=vender]').click()", 2.0)
        linhas = visivel('[data-tela=operacao] .tabela tbody tr')
        checar('Vender: a carga a vender', linhas > 0, f'{linhas} linhas')

        texto = js("[...document.querySelectorAll('[data-tela=operacao] .tabela tbody tr')]"
                   ".filter(t => t.offsetParent !== null).map(t => t.textContent).join(' ')") or ''
        checar('Vender: com a combinacao comprada', 'T5.2' in texto, texto[:120])

        # ---------------------------------------------------------------------
        grupo('Itens')

        js("app.ir('itens')", 1.5)
        checar('a grade de quantidades', visivel('.quantidades .entrada') == 13,
               str(visivel('.quantidades .entrada')))
        checar('o catalogo listado', visivel('.lista-arvore') == 2)

        # ---------------------------------------------------------------------
        grupo('Craft Royal')

        js("app.ir('royal')", 1.5)
        checar('os cinco campos de preco do Sigil', visivel('[data-tela=royal] .com-unidade') == 5,
               str(visivel('[data-tela=royal] .com-unidade')))
        checar('os dois botoes de leitura',
               visivel('[data-tela=royal] .botao') >= 2)

        # o Sigil digitado entra na conta e volta para o campo
        js("(() => { const i = document.querySelectorAll('[data-tela=royal] .com-unidade input')[2];"
           " i.value = '2150'; i.dispatchEvent(new Event('change')); })()", 1.5)
        checar('o Sigil T6 digitado fica guardado',
               any(s['grau'] == 6 and s['preco'] == 2150
                   for s in api.royal_estado(api.royal_estado()['cidade'])['sigils']))

        # ---------------------------------------------------------------------
        grupo('Historico')

        js("app.ir('historico')", 1.5)
        linhas = visivel('[data-tela=historico] .tabela tbody tr')
        checar('as operacoes', linhas == 3, f'{linhas} linhas')
        checar('os destaques numa fila', visivel('.grade-3 .destaque-lado') == 3)

        # ---------------------------------------------------------------------
        grupo('Ajustes: abas e salvar sozinho')

        js("app.ir('ajustes')", 1.5)

        for aba in ('geral', 'compra', 'leitura', 'avancado'):
            js(f"document.querySelector('.abas-ajustes [data-valor={aba}]').click()", 0.4)
            n = visivel('.pagina-ajustes .linha-ajuste')
            checar(f'a aba {aba} mostra os ajustes dela', n >= 2, f'{n} linhas')

        js("document.querySelector('.abas-ajustes [data-valor=compra]').click()", 0.4)

        # a margem e o primeiro numero da aba Compra
        js("""(() => {
            const c = document.querySelector('.pagina-ajustes[data-aba=compra] .com-unidade .entrada');
            c.value = '27'; c.dispatchEvent(new Event('change'));
        })()""", 1.5)
        ajustes.carregar(forcar=True)
        checar('mudar um numero grava sozinho', abs(ajustes.atuais()['margem'] - 0.27) < 1e-9,
               str(ajustes.atuais()['margem']))

        js("""(() => {
            const c = document.querySelectorAll('.pagina-ajustes[data-aba=compra] .com-unidade .entrada')[2];
            c.value = 'abc'; c.dispatchEvent(new Event('change'));
        })()""", 1.5)
        erro = js("[...document.querySelectorAll('.pagina-ajustes[data-aba=compra] .erro-campo')]"
                  ".map(e => e.textContent).join('')")
        ajustes.carregar(forcar=True)
        checar('numero invalido mostra o erro no campo', 'número' in (erro or ''), repr(erro))
        checar('e nao grava', ajustes.atuais()['teto'] is None, str(ajustes.atuais()['teto']))

        js("app.ir('ajustes', 'leitura')", 1.0)
        checar("app.ir('ajustes', 'leitura') abre na aba", js("document.querySelector("
               "'.abas-ajustes [aria-pressed=true]').dataset.valor") == 'leitura')

        # ---------------------------------------------------------------------
        grupo('Andamento e dialogo')

        js("app.gaveta(true); app.escrever('linha de teste'); app.escrever('um erro', 'erro')", 0.8)
        checar('o Andamento recebe linhas', quantos('#log > div') == 2)
        js("document.getElementById('log-limpar').click(); app.gaveta(false)", 0.5)
        checar('e limpa', quantos('#log > div') == 0)

        js("window._resposta = 'nada'; dialogo({ titulo: 'Teste?', sim: 'Sim' })"
           ".then(r => window._resposta = r)", 0.6)
        checar('o dialogo abre', visivel('.dialogo') == 1)
        js("document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))", 0.6)
        # cancelar devolve null; a caixa some depois de uma animacao, que numa
        # janela escondida nao anda - por isso confere a resposta, e nao a caixa
        checar('e o Esc cancela', js('window._resposta === null') is True,
               str(js('String(window._resposta)')))

        # ---------------------------------------------------------------------
        grupo('Calibrador')

        passos = calibrador.evaluate_js("document.querySelectorAll('#grupos button').length")
        # 10: o painel de republicar do bot antigo virou dois grupos - a
        # qualidade no painel de pedido de venda, e a lista de qualidades aberta
        checar('os grupos de marcas', passos == 10, str(passos))
        preparo = calibrador.evaluate_js("document.getElementById('preparo').textContent")
        checar('o preparo do grupo atual', (preparo or '').startswith('Antes de capturar: '), repr(preparo))

        # ---------------------------------------------------------------------
        grupo('nenhum erro de JavaScript')

        time.sleep(0.5)
        erros = open(ERROS_JS, encoding='utf-8').read() if os.path.exists(ERROS_JS) else ''
        checar('o registro de erros da interface ficou vazio', not erros.strip(), erros[-800:])

    except Exception as e:
        falhas.append(f'{grupo_atual}: o teste parou - {e!r}')
        print(f'  FALHA o teste parou - {e!r}')

    finally:
        for w in list(webview.windows):
            try:
                w.destroy()
            except Exception:
                pass


threading.Thread(target=rodar, daemon=True).start()
webview.start(http_server=True)

print(f'\n===== {ok} ok, {len(falhas)} falhas =====')

for f in falhas:
    print(f'  {f}')

raise SystemExit(1 if falhas else 0)
