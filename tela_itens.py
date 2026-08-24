################################
#                              #
#          TELA ITENS          #
#                              #
################################

# Dois paineis: a arvore do jogo a esquerda, o que voce escolheu a direita, e as
# quantidades presas embaixo.
#
#
# A ARVORE NAO PODE FECHAR AO ADICIONAR. Era o defeito que mais custava tempo:
# cada item acrescentado reconstruia os 252 nos com todos os galhos fechados, e
# para pegar o segundo item da mesma familia voce reabria Weapons e depois Sword.
# Dez itens de uma familia eram trinta cliques.
#
# A correcao tem duas partes. Os nos ganharam IDENTIDADE ESTAVEL - 'c:Weapons',
# 'f:Weapons/Sword', 'i:Broadsword' - e antes de reconstruir a tela anota quais
# estavam abertos, o que estava selecionado e onde estava a rolagem, devolvendo
# tudo depois. Sem id estavel isso seria impossivel: o Tk inventa um id novo a
# cada insercao, e o "no que estava aberto" some junto com ele.
#
#
# SELECAO MULTIPLA DOS DOIS LADOS. Montar 121 itens um a um sao 121 idas ao
# botao. Com Ctrl e Shift, uma familia inteira vai de uma vez - e selecionar a
# FAMILIA, e nao os itens dela, tambem funciona: o botao entao diz quantos vai
# levar.
#
#
# O GRUPO DE DESTINO E EXPLICITO. Antes ele era deduzido do que estivesse
# selecionado a direita, e quando nao havia nada os itens caiam em "Sem grupo" -
# em silencio. Voce escolhia vinte e descobria depois. Agora ele e uma lista ao
# lado do botao, e ela lembra a ultima escolha.
#
# Antes de alterar: python -m pyflakes tela_itens.py

import tkinter as tk
from tkinter import ttk

import catalogo
import categorias
import mercado
import visual
from visual import COR, ESPACO, ESPACO_M, ESPACO_G

COMBINACOES = mercado.ROTULOS

# Silencio, em ms, antes de a busca filtrar.
#
# Sem isto o filtro roda a cada tecla, e cada passada reconstroi 252 nos:
# digitar "broadsword" sao dez reconstrucoes para chegar num resultado so.
ESPERA_DA_BUSCA = 200

# Quanto tempo o recado de confirmacao fica na tela, em ms.
TEMPO_DO_RECADO = 4000

# Teto por combinacao.
#
# Nao e limite do jogo: e limite de digito a mais. Ninguem compra mil unidades de
# uma combinacao so, e "9999" digitado sem querer viraria uma ordem gigante muito
# depois, na tela de compra, longe de onde o erro foi cometido.
MAX_POR_COMBINACAO = 999


class Tela:

    def __init__(self, quadro, app):

        self.quadro = quadro
        self.app = app
        self.precisa_atualizar = True

        self.foco_item = None       # item selecionado a direita
        self.foco_grupo = None      # grupo selecionado a direita
        self.campos = {}
        self._busca_agendada = None
        self._recado_agendado = None
        self.quantidades_abertas = True

        self._montar()

    #region Montagem

    def _montar(self):

        visual.titulo_da_pagina(
            self.quadro, 'Itens',
            'o que negociar, em que grupo, e quanto comprar de cada combinação')

        self._montar_quantidades()

        corpo = tk.Frame(self.quadro, bg=COR['fundo'])
        corpo.pack(fill='both', expand=True, padx=ESPACO_G, pady=(ESPACO_M, 0))

        self._montar_disponiveis(corpo)
        self._montar_escolhidos(corpo)

        self._atalhos()

    def _painel(self, pai, titulo, **empacotar):
        """Um painel com cabecalho proprio. Devolve (dentro, cabecalho)."""

        caixa = tk.Frame(pai, bg=COR['fundo'])
        caixa.pack(**empacotar)

        cabecalho = tk.Frame(caixa, bg=COR['fundo'])
        cabecalho.pack(fill='x', pady=(0, ESPACO))

        visual.secao(cabecalho, titulo).pack(side='left')

        cartao = visual.Cartao(caixa, recheio=ESPACO)
        cartao.pack(fill='both', expand=True)

        return cartao.dentro, cabecalho

    def _busca(self, pai, variavel, dica, ao_mudar):
        """Campo de busca com dica por cima e botao de limpar."""

        linha = tk.Frame(pai, bg=COR['painel'])
        linha.pack(fill='x', pady=(0, ESPACO))

        entrada = visual.Entrada(linha, variavel, largura=26)
        entrada.pack(side='left', fill='x', expand=True)

        # A DICA E UM ROTULO POR CIMA do campo, e nao um texto dentro dele:
        # escrito dentro, ele viraria o valor da variavel e a arvore passaria a
        # procurar por "procure um item...".
        rotulo_dica = visual.rotulo(entrada.campo, dica, visual.FONTE_PEQUENA,
                                    cor='texto_fraco', fundo='painel_alto')
        rotulo_dica.place(x=2, rely=0.5, anchor='w')
        rotulo_dica.bind('<Button-1>', lambda _e: entrada.campo.focus_set())

        def mostrar_dica(*_):
            if variavel.get():
                rotulo_dica.place_forget()
            else:
                rotulo_dica.place(x=2, rely=0.5, anchor='w')

        variavel.trace_add('write', mostrar_dica)
        variavel.trace_add('write', lambda *_: ao_mudar())

        visual.Botao(linha, 'Limpar', lambda: variavel.set(''),
                     largura=6).pack(side='left', padx=(ESPACO, 0))

        return entrada

    def _montar_disponiveis(self, pai):

        dentro, cabecalho = self._painel(
            pai, 'Itens do jogo', side='left', fill='both', expand=True)

        visual.Botao(cabecalho, 'Trazer da planilha', self.importar,
                     largura=16, fundo_pai='fundo').pack(side='right')

        self.filtro = tk.StringVar()
        self.entrada = self._busca(dentro, self.filtro, 'procure um item...',
                                   self._busca_mudou)

        self.esconder = tk.BooleanVar(value=False)

        visual.Caixa(dentro, 'esconder os que já tenho', self.esconder,
                     ao_mudar=self._encher_arvore).pack(anchor='w',
                                                        pady=(0, ESPACO))

        self.arvore = self._arvore(dentro)
        self.arvore.bind('<Double-1>', lambda _e: self.acrescentar())
        self.arvore.bind('<<TreeviewSelect>>',
                         lambda _e: self._mudou_a_esquerda())

        rodape = tk.Frame(dentro, bg=COR['painel'])
        rodape.pack(fill='x', pady=(ESPACO, 0))

        # O DESTINO, EXPLICITO. Antes ele era deduzido do que estivesse
        # selecionado a direita, e o silencio custava caro.
        visual.rotulo(rodape, 'em', visual.FONTE_PEQUENA,
                      cor='texto_fraco').pack(side='left', padx=(0, ESPACO))

        self.destino = tk.StringVar(value=catalogo.GRUPO_PADRAO)
        self.lista_destino = visual.Lista(rodape, self.destino, [], largura=15)
        self.lista_destino.pack(side='left')

        self.acrescentar_botao = visual.Botao(
            rodape, 'Acrescentar →', self.acrescentar, tipo='destaque',
            largura=20)
        self.acrescentar_botao.pack(side='right')
        self.acrescentar_botao.habilitar(False)

    def _montar_escolhidos(self, pai):

        dentro, cabecalho = self._painel(
            pai, 'Escolhidos', side='left', fill='both', expand=True,
            padx=(ESPACO_M, 0))

        for texto, comando, largura, tipo in (
                ('Carregar', self.carregar, 9, ''),
                ('Salvar', self.salvar, 8, 'salvar'),
                ('Novo grupo', self.novo_grupo, 11, 'criar')):
            visual.Botao(cabecalho, texto, comando, largura=largura,
                         tipo=tipo,
                         fundo_pai='fundo').pack(side='right', padx=(ESPACO, 0))

        self.filtro_direita = tk.StringVar()
        self._busca(dentro, self.filtro_direita, 'procure entre os escolhidos...',
                    self._encher_escolhidos)

        self.escolhidos = self._arvore(dentro)
        self.escolhidos.bind('<<TreeviewSelect>>', self._mudou_selecao)

        # OS MARCADORES PRECISAM DE LEGENDA. Um losango ao lado do grupo e um
        # ponto ao lado do item querem dizer "tem quantidade propria", e nada na
        # tela dizia isso - descobria-se por tentativa, ou nao se descobria.
        visual.rotulo(dentro, '◆ grupo com quantidade própria     '
                              '● item com quantidade própria',
                      visual.FONTE_MINIMA, cor='texto_fraco').pack(
            anchor='w', pady=(ESPACO, 0))

        acoes = tk.Frame(dentro, bg=COR['painel'])
        acoes.pack(fill='x', pady=(ESPACO, 0))

        self.remover_botao = visual.Botao(acoes, '← Remover', self.remover,
                                          largura=18)
        self.remover_botao.pack(side='left')
        self.remover_botao.habilitar(False)

        self.desfazer_botao = visual.Botao(acoes, '↶ Desfazer', self.desfazer,
                                           largura=11)
        self.desfazer_botao.pack(side='left', padx=ESPACO)
        self.desfazer_botao.habilitar(False)

        # AS ACOES DE GRUPO FICAM SEMPRE NA TELA, apagadas quando nao servem.
        #
        # Antes elas apareciam so com um grupo selecionado. A ideia era poupar
        # leitura, e o efeito foi o contrario: quem nunca viu os botoes nao sabe
        # que renomear e excluir existem, e o unico jeito de descobrir e
        # selecionar um grupo por acaso. Um botao apagado ensina o que da para
        # fazer e como habilitar; um botao ausente nao ensina nada.
        #
        # E o lugar deles para de mudar. Uma fileira que some e volta empurra o
        # que esta embaixo a cada clique na arvore.
        self.acoes_de_grupo = tk.Frame(dentro, bg=COR['painel'])
        self.acoes_de_grupo.pack(fill='x', pady=(ESPACO, 0))

        grupo = self.acoes_de_grupo

        self.mover_botao = visual.Botao(grupo, 'Mudar de grupo',
                                        self.mudar_grupo, largura=13)
        self.mover_botao.pack(side='left')
        self.mover_botao.habilitar(False)

        self.renomear_botao = visual.Botao(grupo, 'Renomear', self.renomear,
                                           largura=10)
        self.renomear_botao.pack(side='left', padx=ESPACO)
        self.renomear_botao.habilitar(False)

        self.excluir_botao = visual.Botao(grupo, 'Excluir grupo',
                                          self.excluir_grupo, tipo='limpar',
                                          largura=12)
        self.excluir_botao.pack(side='left')
        self.excluir_botao.habilitar(False)

        self._montar_lote(dentro)

        self.recado = visual.rotulo(dentro, '', visual.FONTE_MINIMA, cor='ok')
        self.recado.pack(anchor='w', pady=(ESPACO, 0))

        # O QUE FAZER QUANDO NAO HA NADA. Catalogo zerado mostrava dois paineis
        # vazios e nenhuma pista de por onde comecar - e o primeiro uso do
        # programa e exatamente esse estado.
        self.vazio = visual.rotulo(
            dentro,
            'Nada escolhido ainda.\n\n'
            'Marque itens na árvore ao lado e clique em Acrescentar, ou '
            'traga tudo de uma vez com "Trazer da planilha".',
            visual.FONTE_PEQUENA, cor='texto_fraco')

    def _montar_lote(self, pai):
        """Acrescentar ou tirar uma combinacao de varios itens de uma vez.

        RESOLVE UM PROBLEMA REAL: decidir que nenhum item vale a pena no T8.3 e
        ter que abrir item por item para zerar. Com 121 itens isso e trabalho de
        tarde, e e a razao de a tela de referencia ter esta fileira."""

        linha = tk.Frame(pai, bg=COR['painel'])
        linha.pack(fill='x', pady=(ESPACO, 0))

        visual.rotulo(linha, 'em lote', visual.FONTE_PEQUENA,
                      cor='texto_fraco').pack(side='left', padx=(0, ESPACO))

        self.lote_combos = tk.StringVar()
        visual.Entrada(linha, self.lote_combos, largura=12).pack(side='left')

        visual.Botao(linha, 'Tirar', lambda: self._lote(0), largura=7,
                     tipo='limpar').pack(side='left', padx=ESPACO)

        self.lote_quanto = tk.StringVar()
        visual.Entrada(linha, self.lote_quanto, largura=5,
                       alinhamento='center').pack(side='left')

        visual.Botao(linha, 'Pôr', lambda: self._lote(None), largura=6,
                     tipo='criar').pack(side='left', padx=(ESPACO, 0))

        visual.rotulo(pai, 'ex.: "8.3" ou "8.2, 8.3" — vale para os itens '
                           'selecionados, ou para todos se não houver seleção',
                      visual.FONTE_MINIMA, cor='texto_fraco').pack(
            anchor='w', pady=(4, 0))

    def _lote(self, quanto):
        """Aplica a combinacao digitada. <quanto> None le do campo."""

        rotulos = catalogo.rotulos_validos(self.lote_combos.get())

        if not rotulos:
            visual.avisar(self.quadro, 'Qual combinação?',
                          'Digite a combinação, como "8.3" ou "8.2, 8.3".',
                          tipo='aviso')
            return

        if quanto is None:
            quanto = self._quantidade_valida(self.lote_quanto.get())

            if quanto is None:
                return

        itens, _ = self._selecao_direita()

        # SEM SELECAO VALE PARA TODOS, e ai a mudanca vai para a tabela geral em
        # vez de virar 121 excecoes iguais - que e o que faria a tela de
        # quantidades mentir depois, mostrando "exceção" onde ha regra.
        alvo = itens or None

        if alvo is None and not visual.perguntar(
                self.quadro,
                'Aplicar em todos?',
                f'Nada está selecionado, então {", ".join(rotulos)} '
                f'{"vai" if len(rotulos) == 1 else "vão"} para {quanto} em '
                f'TODOS os itens do catálogo.\n\nSelecione itens à direita '
                f'para aplicar só neles.',
                sim='Aplicar em todos'):
            return

        catalogo.em_lote(rotulos, quanto, alvo)

        self._recarregar(manter_selecao=True)

        onde = f'{len(itens)} itens' if itens else 'todos os itens'

        self._dizer(f'{", ".join(rotulos)} = {quanto} em {onde}')

    def _montar_quantidades(self):

        caixa = tk.Frame(self.quadro, bg=COR['fundo'])
        caixa.pack(side='bottom', fill='x', padx=ESPACO_G,
                   pady=(ESPACO_M, ESPACO_M))

        cabecalho = tk.Frame(caixa, bg=COR['fundo'], cursor='hand2')
        cabecalho.pack(fill='x', pady=(0, ESPACO))

        self.seta = visual.secao(cabecalho, '▾')
        self.seta.pack(side='left', padx=(0, 6))

        titulo = visual.secao(cabecalho, 'Quanto comprar de cada combinação')
        titulo.pack(side='left')

        for alvo in (cabecalho, self.seta, titulo):
            alvo.bind('<Button-1>', lambda _e: self.alternar_quantidades())

        self.resumo = visual.rotulo(cabecalho, '', visual.FONTE_PEQUENA,
                                    cor='texto_fraco', fundo='fundo')
        self.resumo.pack(side='right')

        self.cartao_qtd = visual.Cartao(caixa, recheio=ESPACO_M - 2)
        self.cartao_qtd.pack(fill='x')

        dentro = self.cartao_qtd.dentro

        self.explicacao = visual.rotulo(dentro, '', visual.FONTE_MINIMA,
                                        cor='texto_fraco')
        self.explicacao.pack(anchor='w', pady=(0, ESPACO_M - 4))

        grade = tk.Frame(dentro, bg=COR['painel'])
        grade.pack(fill='x')

        for i, combo in enumerate(COMBINACOES):

            coluna = tk.Frame(grade, bg=COR['painel'])
            coluna.grid(row=0, column=i, padx=(0 if i == 0 else 5, 0))

            visual.rotulo(coluna, combo, visual.FONTE_ROTULO,
                          cor='texto_fraco').pack()

            var = tk.StringVar()

            entrada = visual.Entrada(coluna, var, largura=4,
                                     alinhamento='center')
            entrada.pack(pady=(2, 0))

            entrada.campo.bind('<FocusOut>', lambda _e, c=combo: self._gravar(c))
            entrada.campo.bind('<Return>', lambda _e, c=combo: self._gravar(c))

            self.campos[combo] = var

        acoes = tk.Frame(dentro, bg=COR['painel'])
        acoes.pack(fill='x', pady=(ESPACO_M - 4, 0))

        visual.rotulo(acoes, 'todas de uma vez', visual.FONTE_PEQUENA,
                      cor='texto_fraco').pack(side='left', padx=(0, ESPACO))

        self.em_massa = tk.StringVar()
        visual.Entrada(acoes, self.em_massa, largura=5, alinhamento='center',
                       ao_confirmar=self.aplicar_em_massa).pack(side='left')

        visual.Botao(acoes, 'Aplicar', self.aplicar_em_massa,
                     largura=8).pack(side='left', padx=ESPACO)

        self.voltar_botao = visual.Botao(acoes, 'Voltar ao geral',
                                         self.tirar_excecao, largura=13)
        self.voltar_botao.pack(side='left')
        self.voltar_botao.habilitar(False)

        self.tempo = visual.rotulo(acoes, '', visual.FONTE_PEQUENA,
                                   cor='texto_fraco')
        self.tempo.pack(side='right')

    def _arvore(self, pai):

        moldura = tk.Frame(pai, bg=COR['painel'])
        moldura.pack(fill='both', expand=True)

        rolagem = ttk.Scrollbar(moldura, orient='vertical',
                                style='Fina.Vertical.TScrollbar')
        rolagem.pack(side='right', fill='y')

        # ALTURA NATURAL PEQUENA, de proposito. O Treeview nasce pedindo dez
        # linhas, e o pack respeita esse pedido antes de distribuir o que sobra
        # - com dois paineis e duas filas de botoes, os botoes eram empurrados
        # para fora da tela. Pedindo pouco, ele fica com o que sobrar, que e
        # exatamente o que 'expand' quer dizer.
        arvore = ttk.Treeview(moldura, style='Escuro.Treeview', show='tree',
                              height=5, selectmode='extended',
                              yscrollcommand=rolagem.set)
        arvore.pack(fill='both', expand=True)
        rolagem.config(command=arvore.yview)

        return arvore

    def _atalhos(self):
        """Enter acrescenta, Delete remove, Ctrl+F busca, Esc limpa."""

        self.arvore.bind('<Return>', lambda _e: self.acrescentar())
        self.escolhidos.bind('<Delete>', lambda _e: self.remover())

        # NAS ARVORES, E NAO NO QUADRO. Preso ao quadro, o Ctrl+Z pegava
        # tambem dentro de um campo de quantidade - onde ele quer dizer "desfaz o
        # que eu digitei", e desfazia a remocao de um item. O Escape idem: com o
        # foco na busca da direita, limpava a da esquerda.
        for alvo in (self.arvore, self.escolhidos):
            alvo.bind('<Control-f>',
                      lambda _e: self.entrada.campo.focus_set())
            alvo.bind('<Control-z>', lambda _e: self.desfazer())

        self.arvore.bind('<Escape>', lambda _e: self.filtro.set(''))
        self.escolhidos.bind('<Escape>',
                             lambda _e: self.filtro_direita.set(''))

    #endregion

    #region A arvore da esquerda

    def _busca_mudou(self):
        """Espera o silencio antes de filtrar.

        Sem isto o filtro roda a cada tecla, e cada passada reconstroi 252 nos.
        """

        if self._busca_agendada:
            self.quadro.after_cancel(self._busca_agendada)

        self._busca_agendada = self.quadro.after(ESPERA_DA_BUSCA,
                                                 self._encher_arvore)

    def _guardar_estado(self, arvore):
        """O que estava aberto, selecionado e onde estava a rolagem."""

        abertos = []

        def descer(no):
            for filho in arvore.get_children(no):
                if arvore.item(filho, 'open'):
                    abertos.append(filho)
                descer(filho)

        descer('')

        return abertos, list(arvore.selection()), arvore.yview()

    def _devolver_estado(self, arvore, estado):

        abertos, selecao, vista = estado

        for iid in abertos:
            if arvore.exists(iid):
                arvore.item(iid, open=True)

        validos = [i for i in selecao if arvore.exists(i)]

        if validos:
            arvore.selection_set(validos)
            arvore.focus(validos[0])

        if vista:
            arvore.yview_moveto(vista[0])

    def _encher_arvore(self):

        estado = self._guardar_estado(self.arvore)

        self.arvore.delete(*self.arvore.get_children())

        procurado = self.filtro.get().strip().lower()
        ja_tenho = catalogo.conjunto()
        esconder = self.esconder.get()

        abrir = bool(procurado)

        def cabe(item):
            if esconder and item in ja_tenho:
                return False
            return not procurado or procurado in item.lower()

        for categoria, familias in categorias.TRES_NIVEIS.items():

            no_cat = None
            dentro_cat = tenho_cat = 0

            for familia, itens in familias:

                visiveis = [i for i in itens if cabe(i)]

                if not visiveis:
                    continue

                if no_cat is None:
                    no_cat = self.arvore.insert('', 'end', iid=f'c:{categoria}',
                                                text=categoria, open=abrir)

                no_fam = self.arvore.insert(
                    no_cat, 'end', iid=f'f:{categoria}/{familia}',
                    text=familia, open=abrir)

                tenho_fam = 0

                for item in visiveis:
                    marcado = item in ja_tenho
                    tenho_fam += marcado
                    self.arvore.insert(no_fam, 'end', iid=f'i:{item}',
                                       text=item + ('   ✓' if marcado else ''))

                self.arvore.item(no_fam,
                                 text=f'{familia}   ({tenho_fam}/{len(visiveis)})')

                dentro_cat += len(visiveis)
                tenho_cat += tenho_fam

            if no_cat is not None:
                self.arvore.item(
                    no_cat, text=f'{categoria}   ({tenho_cat}/{dentro_cat})')

        for categoria, itens in categorias.DOIS_NIVEIS.items():

            visiveis = [i for i in itens if cabe(i)]

            if not visiveis:
                continue

            tenho = sum(1 for i in visiveis if i in ja_tenho)

            no_cat = self.arvore.insert(
                '', 'end', iid=f'c:{categoria}',
                text=f'{categoria}   ({tenho}/{len(visiveis)})', open=abrir)

            for item in visiveis:
                marcado = item in ja_tenho
                self.arvore.insert(no_cat, 'end', iid=f'i:{item}',
                                   text=item + ('   ✓' if marcado else ''))

        self._devolver_estado(self.arvore, estado)
        self._mudou_a_esquerda()

    def _itens_marcados(self):
        """Os itens sob a selecao da esquerda, com familias e categorias abertas.

        Selecionar a FAMILIA vale como selecionar os itens dela - e o que faz
        "acrescentar todas as espadas" ser um clique."""

        achados = []

        for iid in self.arvore.selection():

            if iid.startswith('i:'):
                achados.append(iid[2:])
                continue

            # categoria ou familia: leva os filhos
            for filho in self.arvore.get_children(iid):
                if filho.startswith('i:'):
                    achados.append(filho[2:])
                else:
                    achados += [n[2:] for n in self.arvore.get_children(filho)
                                if n.startswith('i:')]

        # UM CONJUNTO, E UMA VEZ SO. Antes o catalogo inteiro era reconstruido
        # DENTRO do laco, uma vez por item marcado, e a lista de vistos era
        # varrida linearmente - selecionar uma categoria com 130 itens custava
        # 11 ms, a cada tecla de seta na arvore.
        ja_tenho = catalogo.conjunto()

        vistos = {}

        for item in achados:
            if item not in ja_tenho:
                vistos[item] = True

        return list(vistos)

    def _mudou_a_esquerda(self):
        """O botao diz o que vai fazer com o que esta marcado."""

        novos = self._itens_marcados()
        marcados = self.arvore.selection()

        if not novos:
            if marcados:
                self.acrescentar_botao.trocar_texto('já estão no catálogo')
            else:
                self.acrescentar_botao.trocar_texto('Acrescentar →')
            self.acrescentar_botao.habilitar(False)
            return

        # CONTAGEM, E NAO NOME. O nome esta na arvore ao lado, selecionado e
        # visivel - repeti-lo no botao so serve para o texto variar de tamanho.
        self.acrescentar_botao.trocar_texto(
            f'Acrescentar {len(novos)} '
            f'{"item" if len(novos) == 1 else "itens"}  →')

        self.acrescentar_botao.habilitar(True)

    #endregion

    #region A arvore da direita

    def _encher_escolhidos(self):

        estado = self._guardar_estado(self.escolhidos)

        self.escolhidos.delete(*self.escolhidos.get_children())

        procurado = self.filtro_direita.get().strip().lower()

        for grupo in catalogo.grupos():

            itens = [i for i in catalogo.itens_de(grupo)
                     if not procurado or procurado in i.lower()]

            if procurado and not itens:
                continue

            marca = '   ◆' if catalogo.grupo_tem_excecao(grupo) else ''

            no = self.escolhidos.insert(
                '', 'end', iid=f'g:{grupo}',
                text=f'{grupo}   ({len(itens)}){marca}', open=True)

            for item in itens:
                excecao = '   ●' if catalogo.tem_excecao(item) else ''
                self.escolhidos.insert(no, 'end', iid=f'e:{item}',
                                       text=item + excecao)

        self._devolver_estado(self.escolhidos, estado)

    def _selecao_direita(self):
        """(itens, grupos) marcados a direita."""

        itens = []
        grupos = []

        for iid in self.escolhidos.selection():
            if iid.startswith('e:'):
                itens.append(iid[2:])
            elif iid.startswith('g:'):
                grupos.append(iid[2:])
                itens += catalogo.itens_de(iid[2:])

        return itens, grupos

    def _mudou_selecao(self, _evento=None):

        itens, grupos = self._selecao_direita()

        # o foco das quantidades: um item, ou um grupo, ou nada
        alvo = self.escolhidos.focus()

        self.foco_item = alvo[2:] if alvo.startswith('e:') else None
        self.foco_grupo = alvo[2:] if alvo.startswith('g:') else None

        if itens:
            self.remover_botao.trocar_texto(
                f'←  Remover {len(itens)} '
                f'{"item" if len(itens) == 1 else "itens"}')
        else:
            self.remover_botao.trocar_texto('← Remover')

        self.remover_botao.habilitar(bool(itens))
        self.mover_botao.habilitar(bool(itens))

        um_grupo = len(grupos) == 1

        self.renomear_botao.habilitar(um_grupo)
        self.excluir_botao.habilitar(um_grupo)

        self.excluir_botao.trocar_texto('Excluir grupo')

        self._mostrar_quantidades()

    #endregion

    #region Acrescentar e remover

    def acrescentar(self):

        novos = self._itens_marcados()

        if not novos:
            return

        grupo = self.destino.get() or catalogo.GRUPO_PADRAO
        entraram = 0

        for item in novos:
            if catalogo.acrescentar(item, grupo)[0]:
                entraram += 1

        self._recarregar(manter_selecao=True)

        if entraram:
            self._dizer(f'{entraram} '
                        f'{"item acrescentado" if entraram == 1 else "itens acrescentados"}'
                        f' em "{grupo}"')

    def remover(self):

        itens, _ = self._selecao_direita()

        if not itens:
            return

        # AVISAR ANTES DE PERDER AJUSTE. Um item com treze quantidades afinadas
        # some com um clique, e o unico caminho de volta seria refazer na mao.
        com_excecao = [i for i in itens if catalogo.tem_excecao(i)]

        if com_excecao:

            quantas = sum(len(catalogo.excecoes_de(i)) for i in com_excecao)

            if not visual.perguntar(
                    self.quadro, 'Remover mesmo?',
                    f'{len(com_excecao)} dos itens têm quantidade própria — '
                    f'{quantas} ajustes no total. Remover apaga esses ajustes.'
                    f'\n\nDá para desfazer logo em seguida.',
                    tipo='aviso', sim='Remover'):
                return

        saiu = catalogo.remover_varios(itens)

        self._recarregar()

        if saiu:
            self._dizer(f'{saiu} {"item removido" if saiu == 1 else "itens removidos"}'
                        f' — dá para desfazer')

    def desfazer(self):

        voltaram = catalogo.desfazer()

        if voltaram:
            self._recarregar()
            self._dizer(f'{voltaram} {"item devolvido" if voltaram == 1 else "itens devolvidos"}')

    def importar(self):

        caminho = catalogo.achar_planilha()

        if caminho is None:
            visual.avisar(self.quadro, 'Não achei a planilha',
                          'A Tabela-BM.xlsx não foi encontrada.', tipo='aviso')
            return

        if not visual.perguntar(
                self.quadro, 'Trazer da planilha?',
                'Os itens da coluna A viram o catálogo, e cada aba vira um '
                'grupo com o mesmo nome.\n\nQuem já estiver aqui não entra de '
                'novo, e nada é apagado.', sim='Trazer'):
            return

        quantos, avisos = catalogo.importar_da_planilha(caminho)

        self._recarregar()

        if avisos:
            visual.avisar(self.quadro, 'Trazido com ressalvas',
                          f'{quantos} itens entraram.\n\n'
                          + '\n'.join(avisos[:8]), tipo='aviso')
        else:
            self._dizer(f'{quantos} itens vieram da planilha'
                        if quantos else 'todos já estavam no catálogo')

    #endregion

    #region Grupos

    def novo_grupo(self):

        dados = visual.Formulario(
            self.quadro, 'Novo grupo',
            [{'chave': 'nome', 'rotulo': 'Nome do grupo', 'obrigatorio': True,
              'dica': 'Grupos existem porque o inventario tem limite: cada '
                      'grupo e uma viagem.'}]).resultado

        if not dados or not dados.get('nome'):
            return

        nome = dados['nome'].strip()

        # NOME REPETIDO NAO PODE FALHAR EM SILENCIO. criar_grupo devolve False
        # quando o grupo ja existe, e ignorar esse retorno fazia a tela recarregar
        # sem mudar nada - de onde a unica conclusao possivel e que o programa
        # travou. Aqui o grupo existente vira o destino, que e o que a pessoa
        # queria de qualquer forma.
        if not catalogo.criar_grupo(nome):
            self.destino.set(nome)
            self._recarregar()
            self._dizer(f'"{nome}" ja existia — passou a ser o destino')
            return

        self.destino.set(nome)
        self._recarregar()
        self._dizer(f'grupo "{nome}" criado')

    def renomear(self):

        _, grupos = self._selecao_direita()

        if len(grupos) != 1:
            return

        antigo = grupos[0]

        dados = visual.Formulario(
            self.quadro, f'Renomear "{antigo}"',
            [{'chave': 'nome', 'rotulo': 'Novo nome', 'obrigatorio': True,
              'padrao': antigo}]).resultado

        if not dados or not dados.get('nome'):
            return

        novo = dados['nome'].strip()

        if novo == antigo:
            return

        if not catalogo.renomear_grupo(antigo, novo):
            visual.avisar(
                self.quadro, 'Esse nome ja existe',
                f'Ja ha um grupo chamado "{novo}". Escolha outro nome, ou mova '
                f'os itens para la em vez de renomear.', tipo='aviso')
            return

        if self.destino.get() == antigo:
            self.destino.set(novo)

        self._recarregar()
        self._dizer(f'"{antigo}" agora se chama "{novo}"')

    def excluir_grupo(self):
        """Apaga um grupo, com destino explicito para os itens dele.

        APAGAR EM SILENCIO OS ITENS JUNTO seria a forma mais facil de perder
        meia hora de escolha por um clique - por isso a pergunta oferece as duas
        saidas, e nao so o sim."""

        _, grupos = self._selecao_direita()

        if len(grupos) != 1:
            return

        grupo = grupos[0]
        itens = catalogo.itens_de(grupo)
        outros = [g for g in catalogo.grupos() if g != grupo]

        if not itens:
            catalogo.apagar_grupo(grupo)
            self._recarregar()
            self._dizer(f'grupo "{grupo}" excluído')
            return

        campos = [{'chave': 'destino', 'rotulo': f'Os {len(itens)} itens vão para',
                   'valores': outros + ['— apagar junto —'],
                   'padrao': outros[0] if outros else '— apagar junto —',
                   'dica': 'Apagar leva também as quantidades próprias deles.'}]

        escolha = visual.Formulario(
            self.quadro, f'Excluir "{grupo}"', campos,
            explicacao=f'O grupo "{grupo}" tem {len(itens)} itens. Escolha o '
                       f'que fazer com eles antes de apagar o grupo.',
            confirmar='Excluir').resultado

        if not escolha:
            return

        destino = escolha.get('destino')

        catalogo.apagar_grupo(grupo,
                              mover_para=None if destino == '— apagar junto —'
                              else destino)

        if self.destino.get() == grupo:
            self.destino.set(catalogo.grupos()[0] if catalogo.grupos()
                             else catalogo.GRUPO_PADRAO)

        self._recarregar()
        self._dizer(f'grupo "{grupo}" excluído')

    def mudar_grupo(self):

        itens, _ = self._selecao_direita()

        if not itens:
            return

        destinos = catalogo.grupos()

        if len(destinos) < 2:
            visual.avisar(self.quadro, 'Só há um grupo',
                          'Crie outro grupo antes de mover.', tipo='aviso')
            return

        escolha = visual.Formulario(
            self.quadro,
            f'Mover {len(itens)} {"item" if len(itens) == 1 else "itens"}',
            [{'chave': 'grupo', 'rotulo': 'Para qual grupo',
              'valores': destinos, 'padrao': destinos[0]}]).resultado

        if not escolha or not escolha.get('grupo'):
            return

        for item in itens:
            catalogo.mover(item, escolha['grupo'])

        self._recarregar()
        self._dizer(f'{len(itens)} movidos para "{escolha["grupo"]}"')

    def salvar(self):

        dados = visual.Formulario(
            self.quadro, 'Salvar catalogo',
            [{'chave': 'nome', 'rotulo': 'Com que nome', 'obrigatorio': True,
              'padrao': catalogo.nome_atual(),
              'dica': 'Da para ter varios: um enxuto para dias de pouca prata, '
                      'um cheio para quando da.'}]).resultado

        if not dados or not dados.get('nome'):
            return

        nome = dados['nome'].strip()

        # O PADRAO DO CAMPO E O NOME ATUAL, entao o caminho de menor esforco e
        # justamente o que sobrescreve.
        if nome in catalogo.salvos() and nome != catalogo.nome_atual():
            if not visual.perguntar(
                    self.quadro, 'Ja existe um salvo com esse nome',
                    f'"{nome}" ja existe. Salvar por cima apaga o que estava '
                    f'la.', tipo='aviso', sim='Substituir'):
                return

        ok, erro = catalogo.salvar(nome)

        if ok:
            self._dizer(f'salvo como "{nome}"')
        else:
            visual.avisar(self.quadro, 'Não deu para salvar', erro,
                          tipo='perigo')

        self._recarregar()

    def carregar(self):

        salvos = catalogo.salvos()

        if not salvos:
            visual.avisar(self.quadro, 'Nada salvo ainda',
                          'Monte um catálogo e salve com um nome.', tipo='aviso')
            return

        # TROCAR O CATALOGO INTEIRO E A ACAO MAIS DESTRUTIVA DESTA TELA, e era
        # a unica sem confirmacao nem desfazer. Remover um item pergunta e da
        # para desfazer; substituir os 121 nao perguntava nada.
        quantos = len(catalogo.todos())

        if quantos and not visual.perguntar(
                self.quadro, 'Trocar o catalogo atual?',
                f'Os {quantos} itens que estao aqui agora saem para dar lugar '
                f'ao que voce carregar.\n\nSe ainda nao salvou este, salve '
                f'antes — nao ha como desfazer.',
                tipo='aviso', sim='Carregar'):
            return

        escolha = visual.Formulario(
            self.quadro, 'Carregar catalogo',
            [{'chave': 'nome', 'rotulo': 'Qual', 'valores': salvos,
              'padrao': salvos[0]}]).resultado

        if not escolha or not escolha.get('nome'):
            return

        ok, erro = catalogo.carregar(escolha['nome'])

        if not ok:
            visual.avisar(self.quadro, 'Não deu para ler', erro, tipo='perigo')

        self._recarregar()

    #endregion

    #region Quantidades

    def alternar_quantidades(self):

        self.quantidades_abertas = not self.quantidades_abertas

        if self.quantidades_abertas:
            self.cartao_qtd.pack(fill='x')
            self.seta.config(text='▾')
        else:
            self.cartao_qtd.pack_forget()
            self.seta.config(text='▸')

    def _nivel(self):
        """Sobre o que a faixa de quantidades esta agindo agora."""

        if self.foco_item:
            return 'item', self.foco_item

        if self.foco_grupo:
            return 'grupo', self.foco_grupo

        return 'tabela', None

    def _mostrar_quantidades(self):

        nivel, alvo = self._nivel()

        for combo, var in self.campos.items():

            if nivel == 'item':
                valor = catalogo.quantidade(alvo, combo)
            elif nivel == 'grupo':
                valor = catalogo.quantidade_do_grupo(alvo, combo)
            else:
                valor = catalogo.tabela().get(combo, 0)

            var.set(str(valor))

        if nivel == 'item':
            quantas = len(catalogo.excecoes_de(alvo))
            self.explicacao.config(
                text=f'Mostrando "{alvo}". O que você mudar vale só para ele — '
                     f'hoje tem {quantas} exceção(ões).', fg=COR['primario'])
            self.voltar_botao.habilitar(bool(quantas))
            self.voltar_botao.trocar_texto('Voltar ao grupo')

        elif nivel == 'grupo':
            quantas = len(catalogo.excecoes_do_grupo(alvo))
            self.explicacao.config(
                text=f'Mostrando o grupo "{alvo}". O que você mudar vale para '
                     f'os {len(catalogo.itens_de(alvo))} itens dele — hoje tem '
                     f'{quantas} exceção(ões).', fg=COR['primario'])
            self.voltar_botao.habilitar(bool(quantas))
            self.voltar_botao.trocar_texto('Voltar à tabela')

        else:
            self.explicacao.config(
                text='Estes números valem para TODOS os itens. Selecione um '
                     'grupo ou um item à direita para ajustar só ele.',
                fg=COR['texto_fraco'])
            self.voltar_botao.habilitar(False)
            self.voltar_botao.trocar_texto('Voltar ao geral')

    def _gravar(self, combo):

        quanto = self._quantidade_valida(self.campos[combo].get())

        if quanto is None:
            self._mostrar_quantidades()
            return

        nivel, alvo = self._nivel()

        # NADA A FAZER SE O NUMERO NAO MUDOU. O <FocusOut> dispara so de passar o
        # Tab pelo campo: percorrer as treze combinacoes eram treze reconstrucoes
        # das duas arvores - 252 nos cada - para gravar o mesmo valor de volta, e
        # a arvore piscava a cada tecla.
        if quanto == self._valor_atual(combo, nivel, alvo):
            return

        if nivel == 'item':
            catalogo.definir(alvo, combo, quanto)
        elif nivel == 'grupo':
            catalogo.definir_no_grupo(alvo, combo, quanto)
        else:
            catalogo.definir_tabela(combo, quanto)

        self._recarregar(manter_selecao=True)

    def _valor_atual(self, combo, nivel, alvo):
        """O que esta gravado hoje naquele nivel, para saber se mudou."""

        if nivel == 'item':
            return catalogo.quantidade(alvo, combo)

        if nivel == 'grupo':
            return catalogo.quantidade_do_grupo(alvo, combo)

        return catalogo.tabela().get(combo, 0)

    def _quantidade_valida(self, texto):
        """O numero digitado, ou None se nao servir. Avisa quando recusa.

        TETO DE PROPOSITO. isdigit() aceita 999999999, e um zero a mais num campo
        de quantidade vira ordem de compra gigante la na frente - o mesmo tipo de
        erro que o limite de prata existe para conter, e este campo nao tinha
        protecao nenhuma."""

        texto = (texto or '').strip()

        if not texto.isdigit():
            return None

        quanto = int(texto)

        if quanto > MAX_POR_COMBINACAO:
            visual.avisar(
                self.quadro, 'Quantidade alta demais',
                f'{quanto:,}'.replace(',', '.') + ' unidades de uma combinacao '
                f'so. O teto e {MAX_POR_COMBINACAO} — acima disso quase sempre '
                f'e um digito a mais sem querer.', tipo='aviso')
            return None

        return quanto

    def aplicar_em_massa(self):

        quanto = self._quantidade_valida(self.em_massa.get())

        if quanto is None:
            return

        nivel, alvo = self._nivel()

        for combo in COMBINACOES:
            if nivel == 'item':
                catalogo.definir(alvo, combo, quanto)
            elif nivel == 'grupo':
                catalogo.definir_no_grupo(alvo, combo, quanto)
            else:
                catalogo.definir_tabela(combo, quanto)

        self._recarregar(manter_selecao=True)

    def tirar_excecao(self):

        nivel, alvo = self._nivel()

        for combo in COMBINACOES:
            if nivel == 'item':
                catalogo.definir(alvo, combo, None)
            elif nivel == 'grupo':
                catalogo.definir_no_grupo(alvo, combo, None)

        self._recarregar(manter_selecao=True)

    #endregion

    #region Estado

    def _dizer(self, texto):
        """Um recado que some sozinho.

        Sem ele o clique em Acrescentar so faz a tela mudar um pouco, e nao ha
        como ter certeza de que valeu."""

        self.recado.config(text=texto)

        if self._recado_agendado:
            self.quadro.after_cancel(self._recado_agendado)

        self._recado_agendado = self.quadro.after(
            TEMPO_DO_RECADO, lambda: self.recado.config(text=''))

    def _recarregar(self, manter_selecao=False):

        guardado = self.escolhidos.selection() if manter_selecao else ()

        self._encher_arvore()
        self._encher_escolhidos()

        validos = [i for i in guardado if self.escolhidos.exists(i)]

        if validos:
            self.escolhidos.selection_set(validos)
            self.escolhidos.focus(validos[0])

        self._mudou_selecao()

        grupos = catalogo.grupos() or [catalogo.GRUPO_PADRAO]

        self.lista_destino.trocar_valores(grupos)

        if self.destino.get() not in grupos:
            self.destino.set(grupos[0])

        self.desfazer_botao.habilitar(catalogo.da_para_desfazer())

        if catalogo.todos():
            self.vazio.pack_forget()
        else:
            self.vazio.pack(anchor='w', pady=(ESPACO, 0))

        r = catalogo.resumo()

        self.resumo.config(
            text=f'{r["itens"]} itens · {r["combinacoes"]} combinações · '
                 f'{r["unidades"]:,} unidades'.replace(',', '.'))

        # O NUMERO QUE DECIDE. Nem itens nem combinacoes respondem "esse
        # catalogo cabe na minha tarde?" - o tempo responde.
        self.tempo.config(
            text=f'≈ {r["minutos"]:.0f} min de varredura, por mercado',
            fg=COR['aviso'] if r['minutos'] > 45 else COR['texto_fraco'])

        self.app.atualizar_rodape()

    def ao_mostrar(self):

        self.precisa_atualizar = False
        self._recarregar(manter_selecao=True)

    #endregion
