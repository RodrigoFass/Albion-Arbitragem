################################
#                              #
#        TELA CONFERIR         #
#                              #
################################

# Ler os precos do mercado em que voce ESTA agora.
#
# UMA FILEIRA SO, E NAO DUAS. Antes esta tela tinha sete botoes em cima e sete
# cartoes embaixo, repetindo os mesmos sete nomes: um para escolher, outro para
# dizer quanto ja foi lido. Agora e um cartao por mercado, com a bandeira, o
# nome e o estado dentro - metade do espaco dizendo mais.
#
# A pergunta que ela faz primeiro - "onde voce esta?" - nao e burocracia. O
# programa nao tem como descobrir isso sozinho, e chutar seria pior que
# perguntar: um preco de Martlock guardado como se fosse de Thetford estraga a
# conta de lucro das duas cidades ao mesmo tempo, e nada na tela denunciaria.
#
# Antes de alterar: python -m pyflakes tela_conferir.py

import tkinter as tk

import ajustes
import catalogo
import conferidor
import mercado
import mercado_negro
import visual
from visual import COR, ESPACO, ESPACO_M, ESPACO_G


class Tela:

    def __init__(self, quadro, app):

        self.quadro = quadro
        self.app = app
        self.precisa_atualizar = True
        self.onde = None
        self.cartoes = {}

        self._montar()

    #region Montagem

    def _montar(self):

        visual.titulo_da_pagina(
            self.quadro, 'Conferir',
            'ler os preços do mercado em que você está — uma vez em Caerleon, '
            'uma na cidade')

        self._montar_acoes()
        self._montar_mercados()

    def _montar_mercados(self):

        caixa = tk.Frame(self.quadro, bg=COR['fundo'])
        caixa.pack(fill='both', expand=True, padx=ESPACO_G, pady=(ESPACO_M, 0))

        visual.secao(caixa, 'Onde você está agora').pack(anchor='w',
                                                         pady=(0, ESPACO))

        # OS SETE NUMA FILEIRA SO, como na tela de referencia.
        #
        # Duas fileiras de quatro parecem uma grade, e grade e coisa que se
        # varre com o olho procurando; uma fileira e uma ESCOLHA, e a pergunta
        # aqui e escolha - "onde voce esta agora?". Em 1.260 px cabem os sete
        # com folga.
        grade = tk.Frame(caixa, bg=COR['fundo'])
        grade.pack(fill='x')

        for coluna in range(len(mercado.MERCADOS)):
            grade.columnconfigure(coluna, weight=1, uniform='mercados')

        for n, nome in enumerate(mercado.MERCADOS):

            cartao = self._cartao_de_mercado(grade, nome)
            cartao.grid(row=0, column=n, sticky='ew',
                        padx=(0 if n == 0 else ESPACO // 2,
                              0 if n == len(mercado.MERCADOS) - 1
                              else ESPACO // 2))

    def _cartao_de_mercado(self, pai, nome):
        """Bandeira, nome e estado - tudo no mesmo lugar.

        ARREDONDADO COMO O RESTO DO PROGRAMA. Estes sete eram o unico componente
        de canto reto da interface: um Frame com 1 px de borda desenhado a mao,
        porque o Cartao nao sabia trocar de cor quando selecionado. Agora sabe."""

        cartao = visual.Cartao(pai, recheio=ESPACO + 2)
        cartao.config(cursor='hand2', takefocus=True)

        dentro = cartao.dentro

        linha = tk.Frame(dentro, bg=COR['painel'])
        linha.pack(fill='x')

        bandeira = visual.bandeira(nome, 24)

        if bandeira:
            icone = visual.rotulo(linha, '', ('Segoe UI', 12))
            icone.config(image=bandeira)
        else:
            # O MERCADO NEGRO NAO TEM ESTANDARTE NO JOGO. Um emoji ao lado de
            # seis bandeiras tem outro peso e outro alinhamento; um disco do
            # mesmo tamanho, na cor da marca, entra na fileira.
            icone = visual.Emblema(linha, lado=24)

        icone.pack(side='left')

        # SEM RETICENCIAS NO NOME DA CIDADE. Sete pastilhas numa fileira de
        # 1.260 px dao 165 px cada, e "Fort Sterling" em corpo 10 nao cabe - mas
        # o nome e a unica coisa que a pastilha PRECISA dizer.
        titulo = visual.rotulo(linha, nome, visual.FONTE_PEQUENA,
                               cor='texto_forte')
        titulo.pack(side='left', padx=(6, 0))

        estado = visual.rotulo(dentro, 'nunca lido', visual.FONTE_MINIMA,
                               cor='texto_fraco')
        estado.pack(anchor='w', pady=(2, 0))

        # A IDADE COMO BARRA, e nao so como texto. O estado geral dos sete
        # mercados passa a ser lido de relance, sem comparar numeros.
        barra = tk.Frame(dentro, bg=COR['painel'], height=3)
        barra.pack(fill='x', pady=(6, 0))
        barra.pack_propagate(False)

        self.cartoes[nome] = (cartao, icone, titulo, estado, barra)

        for alvo in (cartao, dentro, linha, icone, titulo, estado):
            alvo.bind('<Button-1>', lambda _e, n=nome: self.escolher(n))
            alvo.bind('<Enter>', lambda _e, n=nome: self._realcar(n, True))
            alvo.bind('<Leave>', lambda _e, n=nome: self._realcar(n, False))

        # DA PARA CHEGAR NELES SEM MOUSE. Sao a primeira decisao da tela, e ate
        # aqui a unica forma de tomar essa decisao era clicando.
        cartao.bind('<Return>', lambda _e, n=nome: self.escolher(n))
        cartao.bind('<space>', lambda _e, n=nome: self.escolher(n))
        cartao.bind('<FocusIn>', lambda _e, n=nome: self._realcar(n, True))
        cartao.bind('<FocusOut>', lambda _e, n=nome: self._realcar(n, False))

        return cartao

    def _realcar(self, nome, sobre):
        """A borda acende ao passar o mouse ou receber o foco.

        Um cartao clicavel que nao reage ao ponteiro nao parece clicavel."""

        if nome == self.onde:
            return

        try:
            self.cartoes[nome][0].pintar(borda='borda_clara' if sobre
                                         else 'borda')
        except tk.TclError:
            pass

    def _montar_acoes(self):

        caixa = tk.Frame(self.quadro, bg=COR['fundo'])
        caixa.pack(fill='x', padx=ESPACO_G, pady=(ESPACO_M, 0))

        cartao = visual.Cartao(caixa, recheio=ESPACO_M - 2)
        cartao.pack(fill='x')

        linha = tk.Frame(cartao.dentro, bg=COR['painel'])
        linha.pack(fill='x')

        visual.rotulo(linha, 'grupo', visual.FONTE_PEQUENA,
                      cor='texto_fraco').pack(side='left', padx=(0, ESPACO))

        self.grupo = tk.StringVar(value='todos')
        self.lista_grupo = visual.Lista(linha, self.grupo, ['todos'],
                                        ao_mudar=lambda _v: self._recalcular(),
                                        largura=22)
        self.lista_grupo.pack(side='left')

        # "CONTINUAR DE ONDE PAROU" E O NOME DA COISA. A informacao ja existia,
        # escondida atras de um rotulo que descreve o filtro em vez do uso: quem
        # parou no item 40 quer continuar, e nao "filtrar por falta".
        self.so_faltando = tk.BooleanVar(value=False)

        self.caixa_faltando = visual.Caixa(
            linha, 'continuar de onde parou', self.so_faltando,
            ao_mudar=self._recalcular)
        self.caixa_faltando.pack(side='left', padx=ESPACO_M)

        self.comecar = visual.Botao(linha, 'Começar', self.varrer,
                                    tipo='destaque', largura=12, emoji='▶')
        self.comecar.pack(side='right')
        self.comecar.habilitar(False)

        # AO LADO DO BOTAO, e nao no rodape do cartao. O motivo de ele estar
        # apagado precisa estar onde o olho ja esta - no botao que nao responde.
        self.tempo = visual.rotulo(linha, '', visual.FONTE_PEQUENA,
                                   cor='texto_fraco')
        self.tempo.pack(side='right', padx=ESPACO)

        visual.Botao(linha, 'Apagar antigos', self.apagar_velhos,
                     largura=14).pack(side='right', padx=ESPACO)

        # A VOLTA DA APAGADA. "Apagar antes de varrer" e o padrao e acontece no
        # primeiro segundo; parar no item cinco deixava o resto perdido. A copia
        # existe desde entao, e sem um botao ela nao serviria para nada.
        self.desfazer_botao = visual.Botao(linha, '↶ Trazer de volta',
                                           self.restaurar, largura=17)
        self.desfazer_botao.pack(side='right')
        self.desfazer_botao.habilitar(False)

        self.aviso = visual.rotulo(cartao.dentro,
                                   'Escolha abaixo onde você está.',
                                   visual.FONTE_PEQUENA, cor='texto_fraco')
        self.aviso.pack(anchor='w', pady=(ESPACO_M - 4, 0))

    #endregion

    #region Acoes

    def escolher(self, nome):

        self.onde = nome

        # LEMBRADO ENTRE SESSOES. Sem isto, toda abertura do programa comeca com
        # o botao Comecar apagado e sem dizer por que.
        ajustes.definir('ultimo_mercado', nome)
        ajustes.salvar()

        self._pintar()
        self._recalcular()
        self._atualizar_desfazer()

    def _atualizar_desfazer(self):

        self.desfazer_botao.habilitar(
            bool(self.onde) and mercado.tem_copia(self.onde))

    def _confirmar(self, itens, conf):
        """O resumo do que vai acontecer, antes de acontecer.

        E A ACAO MAIS CARA DO PROGRAMA e era a que menos perguntava: um clique
        apagava os precos daquele mercado, minimizava a janela e ocupava o
        computador por quarenta minutos."""

        mapa = catalogo._mapa_de_grupos()
        combinacoes = sum(len(catalogo.combinacoes_de(i, mapa)) for i in itens)
        minutos = combinacoes * catalogo.SEGUNDOS_POR_COMBINACAO / 60

        linhas = [f'{len(itens)} itens · {combinacoes} combinações · '
                  f'≈ {minutos:.0f} min em "{self.onde}".', '']

        apagar = conf['apagar_antes'] and not self.so_faltando.get()
        tinha = mercado.quantidade(self.onde)

        if apagar and tinha:
            linhas.append(f'Os {tinha} preços que já estão em "{self.onde}" '
                          f'serão apagados antes de começar. Uma cópia fica '
                          f'guardada, e dá para trazer de volta.')
            linhas.append('')

        linhas.append('Durante a varredura o jogo fica em primeiro plano e o '
                      'mouse é do bot. F11 pausa, F12 para.')

        return visual.perguntar(self.quadro, f'Conferir "{self.onde}"?',
                                '\n'.join(linhas), sim='Começar')

    def _pintar(self):

        for nome, pecas in self.cartoes.items():

            cartao, icone, titulo, estado, barra = pecas

            ligado = nome == self.onde

            cartao.pintar(fundo='primario_fundo' if ligado else 'painel',
                          borda='primario' if ligado else 'borda')

            titulo.config(fg=COR['texto_forte'] if ligado else COR['texto'])

            if isinstance(icone, visual.Emblema):
                icone.desenhar(cartao._fundo)

            barra.config(bg=self._cor_da_idade(nome, cartao._fundo))

    def _cor_da_idade(self, nome, fundo):
        """Verde para preco fresco, ambar para velho, vermelho para muito velho.

        Sem leitura nenhuma a barra some no fundo: nao ha idade para mostrar, e
        uma barra cinza ali seria ruido com aparencia de informacao."""

        if not mercado.quantidade(nome):
            return COR[fundo]

        idade = mercado.idade_mais_velha(nome)

        if idade is None:
            return COR[fundo]

        if idade > 24:
            return COR['perigo']

        if idade > 6:
            return COR['aviso']

        return COR['ok']

    def _recalcular(self):

        if not self.onde:
            return

        itens = self._itens()

        self.comecar.habilitar(bool(itens))

        if not itens:
            self.aviso.config(
                text='Nada a ler com esses filtros — veja a tela Itens.',
                fg=COR['aviso'])
            self.tempo.config(text='')
            return

        mapa = catalogo._mapa_de_grupos()
        combinacoes = sum(len(catalogo.combinacoes_de(i, mapa)) for i in itens)

        # O NUMERO QUE DECIDE. "121 itens" nao responde "isso cabe na minha
        # tarde?" - e esta e a tela onde se resolve comprometer quarenta minutos.
        # A tela Itens ja mostrava o tempo; aqui, onde ele importa mais, nao.
        minutos = combinacoes * catalogo.SEGUNDOS_POR_COMBINACAO / 60

        self.tempo.config(
            text=f'≈ {minutos:.0f} min',
            fg=COR['aviso'] if minutos > 45 else COR['texto_fraco'])

        if self.onde == mercado.MERCADO_NEGRO:
            como = 'busca + painel de venda; os 18 de nome ambíguo, pelo menu'
        else:
            como = 'busca; os 18 de nome ambíguo, pelo menu'

        self.aviso.config(
            text=f'{len(itens)} itens · {combinacoes} combinações em '
                 f'"{self.onde}"  ·  {como}',
            fg=COR['texto_fraco'])

    def _itens(self):

        grupo = self.grupo.get()
        itens = catalogo.para_varrer(None if grupo == 'todos' else grupo)

        if self.so_faltando.get() and self.onde:
            itens = conferidor.falta_conferir(itens, self.onde)

        return itens

    def varrer(self):

        if not self.onde:
            return

        itens = self._itens()

        if not itens:
            return

        conf = ajustes.atuais()

        if not self._confirmar(itens, conf):
            return

        # O MERCADO NEGRO TEM OUTRO FLUXO. Na cidade o item e selecionado pela
        # busca e os filtros ficam na barra de cima; la voce digita o nome, clica
        # em Vender, e os dropdowns estao dentro do painel que abre.
        no_negro = self.onde == mercado.MERCADO_NEGRO

        if no_negro:
            mercado_negro.esquecer_calibragem()

        self.app.rodar(
            lambda: conferidor.varrer(
                self.onde, itens,
                combinacoes=catalogo.combinacoes_de,
                apagar_antes=conf['apagar_antes'] and not self.so_faltando.get(),
                repescar_depois=conf['repescar'],
                amostras=conf['amostras'],
                tela=mercado_negro.TELA if no_negro else None),
            rotulo=f'conferindo {self.onde}',
            ao_terminar=self.app.avisar_telas)

    def restaurar(self):
        """Devolve os precos que a ultima apagada tirou daquele mercado."""

        if not self.onde:
            return

        quantos = mercado.restaurar_copia(self.onde)

        if not quantos:
            visual.avisar(self.quadro, 'Nao ha o que trazer de volta',
                          f'Nenhuma copia guardada de "{self.onde}".',
                          tipo='aviso')
            return

        mercado.salvar()

        self.app.escrever(f'{quantos} precos de "{self.onde}" voltaram.')
        self.app.avisar_telas()

    def apagar_velhos(self):

        if not visual.perguntar(
                self.quadro, 'Apagar preços antigos?',
                'Tira do banco tudo que foi lido há mais de 24 horas.\n\n'
                'Preço velho é pior que preço nenhum: sem ele a tela diz "sem '
                'dado" e você vai coletar; com ele a tela mostra um número, e '
                'número na tela parece verdade.',
                sim='Apagar'):
            return

        saiu = mercado.apagar_velhos(24)
        mercado.salvar()

        self.app.escrever(f'{saiu} preços com mais de 24 h foram apagados.')
        self.app.avisar_telas()

    #endregion

    def ao_mostrar(self):

        self.precisa_atualizar = False

        if self.onde is None:
            lembrado = ajustes.atuais().get('ultimo_mercado')
            if lembrado in mercado.MERCADOS:
                self.onde = lembrado

        # Sem custo por visita: o mercado.carregar() so vai ao disco na primeira
        # vez, e depois responde da memoria.
        mercado.carregar()

        self.lista_grupo.trocar_valores(['todos'] + catalogo.grupos())

        for nome, pecas in self.cartoes.items():

            estado = pecas[3]
            quantos = mercado.quantidade(nome)

            if not quantos:
                estado.config(text='nunca lido', fg=COR['texto_fraco'])
                continue

            idade = mercado.idade_mais_velha(nome)
            velho = idade is not None and idade > 6

            estado.config(
                text=f'{quantos} preços  ·  ' +
                     (f'{idade:.1f} h' if idade is not None else ''),
                fg=COR['aviso'] if velho else COR['ok'])

        self._pintar()
        self._recalcular()
        self._atualizar_desfazer()
