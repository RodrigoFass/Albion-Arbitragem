################################
#                              #
#         TELA AJUSTES         #
#                              #
################################

# Tudo que muda o comportamento sem mexer no codigo.
#
# DIVIDIDA POR QUEM RESPONDE A PERGUNTA, e nao por tipo de campo. "Quanto de
# taxa" e uma pergunta sobre o jogo; "minimizar ao comecar" e sobre o seu
# monitor; "apagar antes de varrer" e sobre o que voce quer que aconteca com o
# dado. Sao tres assuntos, e misturar os tres numa lista de doze campos faria
# procurar um deles custar ler os doze.
#
# Antes de alterar: python -m pyflakes tela_ajustes.py

import tkinter as tk

import ajustes
import comum
import lucro
import tema
import visual
from visual import COR, ESPACO, ESPACO_M, ESPACO_G

CAIXAS_JANELA = (
    ('minimizar', 'Minimizar ao começar',
     'Desmarque para acompanhar o log em outro monitor.'),
    ('focar_jogo', 'Trazer o jogo para frente',
     'Sem isso, alterne para o jogo antes de clicar — o clique deixa esta '
     'janela na frente, e a varredura clicaria aqui dentro.'),
    ('avisar_no_fim', 'Avisar quando terminar',
     'Um apito e o botão da barra de tarefas piscando. Não traz a janela para '
     'frente: isso seria pior que um aviso discreto.'),
    ('faixa', 'Faixa de andamento',
     'Uma tira no topo da tela com o item atual, por cima do jogo. Não aceita '
     'clique, para não tirar o foco do jogo.'),
    ('avisos', 'Avisos no canto de baixo',
     'Cada preço lido aparece num cartão sobre o jogo, ao lado do número que o '
     'jogo está mostrando. É o único jeito de conferir uma leitura enquanto '
     'ela acontece — o log só vai ser lido depois.'),
)

# O rotulo da tela e a chave guardada. Guardar o rotulo faria a preferencia
# depender do idioma da interface.
ROTULO_DO_MODO = {
    'smart': 'automático (Smart Buy)',
    'ordem': 'sempre por ordem',
    'na_hora': 'sempre na hora',
}

MODO_DO_ROTULO = {v: k for k, v in ROTULO_DO_MODO.items()}

CAIXAS_VARREDURA = (
    ('apagar_antes', 'Apagar os preços do mercado antes de varrer',
     'Sem isso, parar no meio deixa o mercado com preços novos em alguns itens '
     'e antigos nos demais, sem como distinguir — e a calculadora trata os '
     'dois igual.'),
    ('repescar', 'Repescar o que faltar, ao terminar',
     'Relê as combinações que voltaram vazias. Vale na hora: o mercado ainda '
     'está aberto e o que faltou costuma ser lentidão da tela, não ausência de '
     'oferta.'),
)


class Tela:

    def __init__(self, quadro, app):

        self.quadro = quadro
        self.app = app
        self.precisa_atualizar = True

        self.premium = tk.BooleanVar()
        self.margem = tk.StringVar()
        self.idade = tk.StringVar()
        self.teto = tk.StringVar()
        self.amostras = tk.StringVar()

        self.modo_de_compra = tk.StringVar()
        self.ordem_a_partir_de = tk.StringVar()
        self.na_hora_acima_de = tk.StringVar()

        self.tecla_pausa = tk.StringVar()
        self.tecla_parada = tk.StringVar()
        self.tecla_pular = tk.StringVar()

        self.ms_clique = tk.StringVar()
        self.ms_escrita = tk.StringVar()
        self.ms_leitura = tk.StringVar()
        self.tema = tk.StringVar(value=tema.ROTULO[visual.tema_atual()])

        self.caixas = {chave: tk.BooleanVar()
                       for chave, _, _ in CAIXAS_JANELA + CAIXAS_VARREDURA}

        self._montar()

    #region Montagem

    def _montar(self):

        visual.titulo_da_pagina(self.quadro, 'Ajustes',
                                'o que muda o comportamento sem mexer no código')

        rolavel = visual.Rolavel(self.quadro)
        rolavel.pack(fill='both', expand=True, padx=ESPACO_G,
                     pady=(ESPACO_M, 0))

        corpo = rolavel.dentro

        self._montar_conta(corpo)
        self._montar_compra(corpo)
        self._montar_teclas(corpo)
        self._montar_velocidade(corpo)
        self._montar_bloco(corpo, 'A janela', CAIXAS_JANELA)
        self._montar_varredura(corpo)
        self._montar_aparencia(corpo)
        self._montar_taxas(corpo)
        self._montar_acoes(corpo)

    def _cartao(self, pai, titulo):

        visual.secao(pai, titulo).pack(anchor='w', pady=(0, ESPACO))

        cartao = visual.Cartao(pai)
        cartao.pack(fill='x', pady=(0, ESPACO_G))

        return cartao.dentro

    def _linha_de_campo(self, pai, rotulo, variavel, dica='', largura=10,
                        valores=None):
        """Um rotulo a esquerda e o controle a direita, como na referencia."""

        linha = tk.Frame(pai, bg=COR['painel'])
        linha.pack(fill='x', pady=(0, ESPACO))

        visual.rotulo(linha, rotulo, visual.FONTE_PEQUENA,
                      cor='texto').pack(side='left')

        if valores is not None:
            visual.Lista(linha, variavel, valores,
                         largura=largura).pack(side='right')
        else:
            visual.Entrada(linha, variavel, largura=largura,
                           alinhamento='center').pack(side='right')

        if dica:
            visual.rotulo(pai, dica, visual.FONTE_MINIMA,
                          cor='texto_fraco').pack(anchor='w',
                                                  pady=(0, ESPACO_M - 4))

        return linha

    def _montar_compra(self, pai):
        """As tres regras que decidem COMO comprar.

        Estavam cravadas em compra.py como constantes. Sao exatamente os tres
        campos da tela de referencia, e a razao de existirem na tela e a mesma:
        eles dependem de quanta prata voce tem hoje e do que esta na lista, e nao
        de uma verdade do jogo."""

        dentro = self._cartao(pai, 'Como comprar')

        self._linha_de_campo(
            dentro, 'Modo de compra', self.modo_de_compra,
            'O automático escolhe por linha e acerta quase sempre. As travas '
            'existem para quando você sabe algo que a regra não sabe.',
            largura=22,
            valores=['automático (Smart Buy)', 'sempre por ordem',
                     'sempre na hora'])

        self._linha_de_campo(
            dentro, 'Usar ordem a partir de (unidades)',
            self.ordem_a_partir_de,
            'Uma ordem casa com todas as ofertas daquele preço de uma vez — '
            'em volume, a taxa de 2,5% se paga em cliques poupados.')

        self._linha_de_campo(
            dentro, 'Comprar na hora acima de (prata/unidade)',
            self.na_hora_acima_de,
            'Em item caro, 2,5% é dinheiro de verdade — e ali são poucas '
            'unidades mesmo.')

    def _montar_teclas(self, pai):

        dentro = self._cartao(pai, 'Teclas')

        possiveis = [t.upper() for t in comum.TECLAS_POSSIVEIS]

        self._linha_de_campo(dentro, 'Pausar e retomar', self.tecla_pausa,
                             largura=10, valores=possiveis)

        self._linha_de_campo(dentro, 'Pular o item atual', self.tecla_pular,
                             'Para o item que trava a varredura sem falhar: o '
                             'painel que não abre, a lista que não filtra.',
                             largura=10, valores=possiveis)

        self._linha_de_campo(dentro, 'Parar agora', self.tecla_parada,
                             'F11 é tela cheia em qualquer navegador e F12 abre '
                             'o console — quem joga com o navegador atrás '
                             'precisa de outra combinação.',
                             largura=10, valores=possiveis)

    def _montar_velocidade(self, pai):

        dentro = self._cartao(pai, 'Velocidade')

        self._linha_de_campo(dentro, 'Pausa depois do clique (ms)',
                             self.ms_clique)

        self._linha_de_campo(dentro, 'Pausa ao mover o mouse (ms)',
                             self.ms_escrita)

        self._linha_de_campo(
            dentro, 'Tempo de preço parado (ms)', self.ms_leitura,
            'Quanto a região do preço precisa ficar sem mudar antes da leitura '
            'valer. Aumente numa máquina lenta ou com ping alto; abaixar '
            'demais faz o bot ler a combinação anterior.')

    def _montar_conta(self, pai):

        dentro = self._cartao(pai, 'A conta')

        visual.Caixa(dentro, 'Esta conta tem Premium', self.premium,
                     ao_mudar=self._mostrar_taxa).pack(anchor='w')

        self.nota_taxa = visual.rotulo(dentro, '', visual.FONTE_MINIMA,
                                       cor='texto_fraco')
        self.nota_taxa.pack(anchor='w', padx=24, pady=(2, ESPACO_M))

        visual.Campo(dentro, 'Margem mínima', self.margem, '%',
                     'Abaixo disso a linha nem entra na lista. É a margem '
                     'LÍQUIDA — já descontadas a taxa de venda e a de ordem.',
                     largura=6).pack(fill='x', pady=(0, ESPACO_M))

        visual.Campo(dentro, 'Teto de gasto por rodada', self.teto, 'prata',
                     'Vazio = sem teto. A lista vem da melhor margem para a '
                     'pior, então o que fica de fora é sempre o pior negócio — '
                     'e não "o que sobrou quando o dinheiro acabou".',
                     largura=12).pack(fill='x', pady=(0, ESPACO_M))

        visual.Campo(dentro, 'Idade máxima do preço', self.idade, 'h',
                     'Preço de mercado não envelhece como nome envelhece: em '
                     'duas horas ele já é outro. Mais velho que isto não '
                     'decide compra.', largura=6).pack(fill='x')

    def _montar_bloco(self, pai, titulo, caixas):

        dentro = self._cartao(pai, titulo)

        for n, (chave, texto, dica) in enumerate(caixas):
            visual.Caixa(dentro, texto, self.caixas[chave], dica).pack(
                fill='x', pady=(0, ESPACO_M if n < len(caixas) - 1 else 0))

        return dentro

    def _montar_varredura(self, pai):

        dentro = self._montar_bloco(pai, 'A varredura', CAIXAS_VARREDURA)

        visual.Campo(dentro, 'Conferir N combinações sorteadas no fim',
                     self.amostras, 'zero desliga',
                     'Relê algumas e compara com o gravado. É a única forma de '
                     'pegar erro SISTEMÁTICO de leitura: se a varredura inteira '
                     'leu um dígito a menos, os preços continuam crescendo '
                     'direitinho e nenhuma outra checagem acusa.',
                     largura=5).pack(fill='x', pady=(ESPACO_M, 0))

    def _montar_aparencia(self, pai):

        dentro = self._cartao(pai, 'Aparência')

        linha = tk.Frame(dentro, bg=COR['painel'])
        linha.pack(fill='x')

        visual.rotulo(linha, 'Tema', visual.FONTE, cor='texto').pack(side='left')

        visual.Lista(linha, self.tema,
                     [tema.ROTULO[n] for n in tema.TEMAS],
                     ao_mudar=self.trocar_tema, largura=12).pack(side='right')

        visual.rotulo(
            dentro,
            'O fundo é #282C34 e a lateral #21252B. O vermelho da marca fica '
            'na identidade e no perigo; o azul começa as coisas.',
            visual.FONTE_MINIMA, cor='texto_fraco',
            wraplength=560).pack(anchor='w', pady=(6, 0))

    def _montar_taxas(self, pai):

        dentro = self._cartao(pai, 'As taxas do jogo, para conferência')

        texto = (
            f'venda sem Premium   {lucro.TAXA_SEM_PREMIUM * 100:.0f}%\n'
            f'venda com Premium   {lucro.TAXA_COM_PREMIUM * 100:.0f}%\n'
            f'criar uma ordem     {lucro.TAXA_DE_ORDEM * 100:.1f}%   '
            f'(não muda com Premium)')

        visual.rotulo(dentro, texto, visual.FONTE_LOG,
                      cor='texto').pack(anchor='w')

        visual.rotulo(
            dentro,
            'Lidas da própria tela do Mercado Negro: sobre um preço de 6.356 '
            'ele mostrava 508 de taxa e 159 de taxa de ordem.',
            visual.FONTE_MINIMA, cor='texto_fraco',
            wraplength=560).pack(anchor='w', pady=(ESPACO, 0))

    def _montar_acoes(self, pai):

        acoes = tk.Frame(pai, bg=COR['fundo'])
        acoes.pack(fill='x', pady=(0, ESPACO_G))

        visual.Botao(acoes, 'Salvar', self.salvar, tipo='salvar', largura=11,
                     fundo_pai='fundo').pack(side='left')

        visual.Botao(acoes, 'Voltar ao padrão', self.restaurar, largura=15,
                     fundo_pai='fundo').pack(side='left', padx=ESPACO)

        # CALIBRAR FICA AQUI, e nao escondido num menu. Boa parte das
        # coordenadas deste programa foi DERIVADA de um print, e nao medida na
        # tela - e um recorte seis pixels fora ja fez o "5" de 540.000 ser lido
        # como 9, sem erro nenhum aparecer. Quem descobre isso precisa achar o
        # remedio no mesmo lugar onde procurou o problema.
        visual.Botao(acoes, 'Calibrar coordenadas', self.calibrar, largura=20,
                     fundo_pai='fundo').pack(side='left')

        self.recado = visual.rotulo(acoes, '', visual.FONTE_PEQUENA, cor='ok',
                                    fundo='fundo')
        self.recado.pack(side='left', padx=ESPACO_M)

    def _mostrar_taxa(self):

        taxa = (lucro.TAXA_COM_PREMIUM if self.premium.get()
                else lucro.TAXA_SEM_PREMIUM)

        self.nota_taxa.config(
            text=f'a taxa de venda passa a ser {taxa * 100:.0f}%')

    #endregion

    #region Acoes

    def trocar_tema(self, rotulo_escolhido):
        """Troca a paleta e remonta a janela.

        O Tk nao observa nada: um widget desenhado com a cor antiga fica com ela
        para sempre. Trocar de tema de verdade e reconstruir."""

        for nome in tema.TEMAS:
            if tema.ROTULO[nome] == rotulo_escolhido:
                self.app.remontar(nome)
                return

    def salvar(self):

        try:
            margem = float(self.margem.get().replace(',', '.')) / 100
            idade = float(self.idade.get().replace(',', '.'))
            amostras = int(self.amostras.get() or 0)
        except ValueError:
            self.recado.config(text='número inválido', fg=COR['perigo'])
            return

        teto = self.teto.get().strip().replace('.', '').replace(',', '')

        ajustes.definir('premium', self.premium.get())
        ajustes.definir('margem', margem)
        ajustes.definir('idade_maxima', idade)
        ajustes.definir('amostras', max(0, amostras))
        ajustes.definir('teto', int(teto) if teto.isdigit() else None)

        for chave, var in self.caixas.items():
            ajustes.definir(chave, var.get())

        ajustes.definir('modo_de_compra',
                        MODO_DO_ROTULO.get(self.modo_de_compra.get(), 'smart'))

        for chave, var, minimo, maximo in (
                ('ordem_a_partir_de', self.ordem_a_partir_de, 1, 999),
                ('na_hora_acima_de', self.na_hora_acima_de, 0, 100_000_000),
                ('ms_clique', self.ms_clique, 10, 2000),
                ('ms_escrita', self.ms_escrita, 10, 2000),
                ('ms_leitura', self.ms_leitura, 50, 3000)):

            texto = var.get().strip().replace('.', '')

            # VALOR FORA DA FAIXA E IGNORADO, e nao salvo torto. 0 ms de clique
            # nao acelera nada e faz o jogo perder eventos.
            if texto.isdigit() and minimo <= int(texto) <= maximo:
                ajustes.definir(chave, int(texto))

        for chave, var in (('tecla_pausa', self.tecla_pausa),
                           ('tecla_parada', self.tecla_parada),
                           ('tecla_pular', self.tecla_pular)):
            ajustes.definir(chave, var.get().strip().lower())

        ok, erro = ajustes.salvar()

        self.recado.config(text='salvo' if ok else erro,
                           fg=COR['ok'] if ok else COR['perigo'])

        self.app.avisar_telas()

    def calibrar(self):
        """Abre o calibrador sobre uma captura da tela do jogo."""

        if self.app.rodando:
            visual.avisar(self.quadro, 'Calibrar',
                          'Termine ou pare a operacao antes de calibrar.',
                          tipo='aviso')
            return

        import calibrador

        calibrador.abrir(self.quadro.winfo_toplevel(),
                         ao_terminar=self._coordenadas_mudaram)

    def _coordenadas_mudaram(self, trocadas):

        if not trocadas:
            return

        self.recado.config(
            text=f'{trocadas} coordenadas remarcadas', fg=COR['ok'])

        self.app.escrever(f'{trocadas} coordenadas foram remarcadas.')

    def restaurar(self):

        ajustes.restaurar()
        self.ao_mostrar()
        self.recado.config(text='voltou ao padrão', fg=COR['texto_fraco'])

    #endregion

    def ao_mostrar(self):

        self.precisa_atualizar = False

        atual = ajustes.atuais()

        self.premium.set(atual['premium'])
        self.margem.set(f'{atual["margem"] * 100:.0f}')
        self.idade.set(f'{atual["idade_maxima"]:.0f}')
        self.teto.set(str(atual['teto']) if atual.get('teto') else '')
        self.amostras.set(str(atual.get('amostras', 0)))

        self.modo_de_compra.set(ROTULO_DO_MODO.get(
            atual.get('modo_de_compra', 'smart'), ROTULO_DO_MODO['smart']))
        self.ordem_a_partir_de.set(str(atual.get('ordem_a_partir_de', 8)))
        self.na_hora_acima_de.set(str(atual.get('na_hora_acima_de', 100000)))

        self.tecla_pausa.set(str(atual.get('tecla_pausa', 'f11')).upper())
        self.tecla_parada.set(str(atual.get('tecla_parada', 'f12')).upper())
        self.tecla_pular.set(str(atual.get('tecla_pular', 'f2')).upper())

        self.ms_clique.set(str(atual.get('ms_clique', 120)))
        self.ms_escrita.set(str(atual.get('ms_escrita', 50)))
        self.ms_leitura.set(str(atual.get('ms_leitura', 400)))
        self.tema.set(tema.ROTULO[visual.tema_atual()])

        for chave, var in self.caixas.items():
            var.set(bool(atual.get(chave, True)))

        self._mostrar_taxa()
        self.recado.config(text='')
