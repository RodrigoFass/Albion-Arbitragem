################################
#                              #
#           TESTES             #
#          INTERFACE           #
#                              #
################################

# A interface, montada de verdade e sem o jogo aberto.
#
# NAO E TESTE DE APARENCIA. E teste de que ela ABRE - as cinco telas montam, a
# troca entre elas funciona, e o estado salvo volta. Uma janela que nao sobe e o
# unico defeito que impede de descobrir qualquer outro, e ele nao aparece em
# nenhum teste de logica.
#
# Roda com uma janela escondida (withdraw): nada pisca na tela de quem estiver
# usando o computador, e o Tk desenha tudo do mesmo jeito.
#
#     python testes/testar_interface.py

import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import ajustes     # noqa: E402
import catalogo     # noqa: E402
import mercado      # noqa: E402
import visual       # noqa: E402

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


raiz = tk.Tk()
raiz.withdraw()

# um catalogo de mentira, para as telas terem o que mostrar sem tocar no seu
_catalogo_real = catalogo._catalogo
_banco_real = mercado._banco

catalogo.zerar()
catalogo.acrescentar('Broadsword', 'Teste')
catalogo.acrescentar('Assassin Jacket', 'Teste')
mercado.usar_banco({})

import app as aplicativo   # noqa: E402


# ============================================================
grupo('a janela sobe')

try:
    programa = aplicativo.Aplicativo(raiz)
    raiz.update_idletasks()
    montou = True
    erro = ''
except Exception as e:
    programa = None
    montou = False
    erro = str(e)

checar('o aplicativo monta', montou, erro)

if montou:

    # AS SEIS TELAS SAO A OPERACAO INTEIRA, na ordem em que se usa: escolher o
    # que negociar, ler os precos, comprar, vender.
    checar('com as seis telas', len(programa.telas) == 6,
           str(list(programa.telas)))

    checar('e vender e uma delas - o modulo existia sem porta de entrada',
           'vender' in programa.telas, str(list(programa.telas)))

    checar('e nenhuma delas rodando nada', programa.rodando is None)


# ============================================================
grupo('as cinco telas desenham')

if montou:

    for chave in ('painel', 'itens', 'conferir', 'comprar', 'ajustes'):

        try:
            programa.trocar(chave)
            raiz.update_idletasks()
            deu = True
            motivo = ''
        except Exception as e:
            deu = False
            motivo = str(e)

        checar(f'{chave} monta e aparece', deu, motivo)

    checar('e a ultima trocada e a que fica', programa.atual == 'ajustes')

    # trocar de tela e ida e volta: um estado que so se monta uma vez quebraria
    # na segunda visita, e essa e a visita que o usuario faz o dia inteiro
    for _ in range(3):
        for chave in programa.telas:
            programa.trocar(chave)
            raiz.update_idletasks()

    checar('e aguentam ser trocadas varias vezes', True)


# ============================================================
grupo('o log recebe o que vem da thread do bot')

if montou:

    programa.limpar_log()
    programa._do_bot('linha de teste')
    programa._drenar_uma_vez() if hasattr(programa, '_drenar_uma_vez') else None
    raiz.update()

    # o drenar roda sozinho a cada 80 ms; damos um empurrao
    raiz.after(1, lambda: None)
    raiz.update()

    checar('a fila aceita linha sem estourar', True)

    programa.escrever('ERRO de mentira')
    programa.escrever('  linha recuada')
    raiz.update_idletasks()

    conteudo = programa.log.get('1.0', 'end')

    checar('o log guarda o que foi escrito', 'ERRO de mentira' in conteudo)


# ============================================================
grupo('as pecas visuais novas')

for nome in ('estilos', 'titulo_da_pagina', 'Cartao', 'Numero'):
    checar(f'visual.{nome} existe', hasattr(visual, nome))

if montou:

    caixa = tk.Frame(raiz)
    numero = visual.Numero(caixa, 'teste', 'dica')
    numero.mostrar('123', 'outra dica', cor='ok')
    raiz.update_idletasks()

    checar('o Numero troca de valor', numero.valor.cget('text') == '123')
    checar('e de dica', numero.dica.cget('text') == 'outra dica')


# ============================================================
grupo('nada roda sem o usuario mandar')

if montou:

    # A INTERFACE NAO PODE COMECAR NADA SOZINHA. Uma tela que dispara uma
    # varredura ao ser aberta gastaria prata por um clique de navegacao.
    for chave in programa.telas:
        programa.trocar(chave)
        raiz.update_idletasks()

    checar('abrir as telas nao dispara operacao nenhuma',
           programa.rodando is None)

    checar('e o botao de parar fica apagado',
           not programa.parar_botao._ativo)

    # --- as acoes de grupo, sem nada selecionado --------------------------
    # UM BOTAO APAGADO ENSINA que a acao existe e faz procurar como habilita-la.
    # Um botao ausente nao ensina nada: quem nunca viu "Renomear" nao sabe que da
    # para renomear, e o unico jeito de descobrir e selecionar um grupo por
    # acaso. Some-se a isso que a fileira sumindo e voltando empurra o que esta
    # embaixo a cada clique na arvore.
    programa.trocar('itens')
    raiz.update_idletasks()

    _itens = programa.telas['itens']

    # winfo_ismapped() nao serve aqui: a janela do teste nunca e mostrada, entao
    # nada esta mapeado. O que se quer saber e se o gerenciador de layout ainda
    # tem o quadro - que e exatamente o que o pack_forget tira.
    checar('as acoes de grupo ficam na tela sem nada selecionado',
           bool(_itens.acoes_de_grupo.winfo_manager()),
           repr(_itens.acoes_de_grupo.winfo_manager()))

    checar('so que apagadas, porque nao ha grupo para renomear ou excluir',
           not _itens.renomear_botao._ativo and not _itens.excluir_botao._ativo)

    checar('e "Mudar de grupo" tambem, que precisa de itens escolhidos',
           not _itens.mover_botao._ativo)

    # --- o teto de quantidade ---------------------------------------------
    # isdigit() aceita 999999999, e um zero a mais aqui vira ordem de compra
    # gigante la na frente, longe de onde o erro foi cometido.
    _avisos = []
    _real_avisar = visual.avisar
    visual.avisar = lambda *a, **k: _avisos.append(a[1] if len(a) > 1 else '')

    try:
        _ok = _itens._quantidade_valida('8')
        _alto = _itens._quantidade_valida('999999')
        _vazio = _itens._quantidade_valida('')
        _letra = _itens._quantidade_valida('oito')
    finally:
        visual.avisar = _real_avisar

    checar('quantidade normal passa', _ok == 8, str(_ok))

    checar('quantidade absurda e recusada', _alto is None, str(_alto))

    checar('e a recusa avisa, em vez de sumir com o numero',
           len(_avisos) == 1, str(_avisos))

    checar('campo vazio e texto nao viram quantidade',
           _vazio is None and _letra is None)

    checar('e nada disso avisa - so o teto', len(_avisos) == 1)

    # --- Ctrl+Z e Escape saem do quadro -----------------------------------
    # Presos ao quadro, pegavam tambem dentro de um campo de quantidade, onde
    # Ctrl+Z quer dizer "desfaz o que eu digitei" e desfazia a remocao de um
    # item.
    checar('Ctrl+Z nao fica preso ao quadro da pagina',
           '<Control-z>' not in _itens.quadro.bind())

    # o Tk normaliza o nome do evento: '<Escape>' vira '<Key-Escape>'
    _tem_esc = lambda w: any('Escape' in e for e in w.bind())

    # --- a tela Conferir --------------------------------------------------
    programa.trocar('conferir')
    raiz.update_idletasks()

    _conf = programa.telas['conferir']

    # O NUMERO QUE DECIDE. "121 itens" nao responde "isso cabe na minha tarde?",
    # e esta e a tela onde se resolve comprometer quarenta minutos.
    _conf.escolher('Thetford')
    raiz.update_idletasks()

    checar('a tela Conferir mostra o tempo estimado',
           'min' in _conf.tempo.cget('text'), repr(_conf.tempo.cget('text')))

    checar('e ele fica ao lado do botao Comecar, e nao no rodape',
           _conf.tempo.master is _conf.comecar.master)

    # LEMBRADO ENTRE SESSOES: sem isto o botao Comecar nasce apagado toda
    # abertura, sem dizer por que.
    checar('escolher o mercado grava a escolha',
           ajustes.atuais().get('ultimo_mercado') == 'Thetford',
           str(ajustes.atuais().get('ultimo_mercado')))

    # DA PARA CHEGAR NOS CARTOES SEM MOUSE.
    _cartao = _conf.cartoes['Thetford'][0]

    checar('os cartoes de mercado aceitam foco de teclado',
           bool(_cartao.cget('takefocus')))

    checar('e respondem a Enter e espaco',
           any('Return' in e for e in _cartao.bind())
           and any('space' in e for e in _cartao.bind()),
           str(_cartao.bind()))

    checar('com realce ao passar o mouse',
           any('Enter' in e for e in _cartao.bind()))

    programa.trocar('itens')
    raiz.update_idletasks()

    checar('e o Escape de cada busca limpa a busca dela',
           _tem_esc(_itens.escolhidos) and _tem_esc(_itens.arvore),
           f'{_itens.arvore.bind()} / {_itens.escolhidos.bind()}')


catalogo.usar(_catalogo_real)
mercado.usar_banco(_banco_real)

try:
    raiz.destroy()
except tk.TclError:
    pass


# ============================================================
print(f'\n===== {ok} ok, {len(falhas)} falhas =====')

for f in falhas:
    print(f'  {f}')

raise SystemExit(1 if falhas else 0)
