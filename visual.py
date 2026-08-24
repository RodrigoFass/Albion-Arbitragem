################################
#                              #
#           VISUAL             #
#                              #
################################

# A paleta e os widgets que as tres janelas do programa compartilham: a principal,
# o painel da planilha e o calibrador.
#
# Isto era tudo do app.py. Saiu de la quando a segunda janela apareceu: cada uma
# importando os widgets da outra viraria um ciclo de imports, e cada uma com a
# sua copia da paleta viraria tres tons de cinza ligeiramente diferentes.
#
# Antes de alterar: python -m pyflakes visual.py

import os
import tkinter as tk
from tkinter import ttk

import tema

#region Aparencia

# As cores vem do tema.py, e as duas paletas nascem da marca: vermelho e branco,
# porque o icone nao tem terceira cor.
#
# VERMELHO E DESTAQUE E PERIGO AO MESMO TEMPO. O botao que comeca e o botao que
# apaga ficariam iguais, e o lugar onde isso doeria e a tela em que se escolhe
# entre simular e gastar prata. A saida nao e mudar a cor - e mudar o PESO: o
# destaque e preenchido, o perigo e so contorno, e o perigo sempre passa por uma
# pergunta antes de acontecer.

# A PALETA E VIVA. O `from visual import COR` de dez arquivos guarda uma
# referencia ao MESMO dicionario - por isso trocar de tema atualiza o conteudo
# dele no lugar, e nao substitui o objeto. Reatribuir COR aqui deixaria todos os
# outros modulos apontando para as cores antigas.
COR = {}

_tema_atual = tema.ESCURO


def aplicar_tema(nome):
    """Troca a paleta. Devolve o nome do tema que ficou valendo.

    Os widgets JA DESENHADOS nao mudam sozinhos - o Tk nao observa nada. Quem
    chama e responsavel por remontar a janela; aqui so as cores trocam."""

    global _tema_atual

    _tema_atual = nome if nome in tema.TEMAS else tema.ESCURO

    COR.clear()
    COR.update(tema.cores(_tema_atual))

    return _tema_atual


def tema_atual():
    return _tema_atual


def escuro():
    return tema.escuro(_tema_atual)


aplicar_tema(tema.ESCURO)

FONTE         = ('Segoe UI', 10)
FONTE_TITULO  = ('Segoe UI Semibold', 15)
FONTE_TITULO_PAGINA = ('Segoe UI Semibold', 13)
FONTE_NUMERO  = ('Segoe UI Light', 22)
FONTE_SECAO   = ('Segoe UI Semibold', 10)
FONTE_PEQUENA = ('Segoe UI', 9)
FONTE_MINIMA  = ('Segoe UI', 8)
FONTE_ROTULO  = ('Segoe UI Semibold', 8)
FONTE_LOG     = ('Consolas', 9)

# Tom que um bot pede -> cor da paleta. Os bots falam em "fraco", "ok", "perigo";
# a paleta chama o primeiro de texto_fraco. Sem esta traducao o resumo do painel
# levantava KeyError e aparecia como ('fraco') em vermelho.
TOM = {
    'fraco': 'texto_fraco',
    'ok': 'ok',
    'aviso': 'aviso',
    'perigo': 'perigo',
    'texto': 'texto',
    'destaque': 'destaque',
}

# Teto de linhas do painel de andamento. Uma varredura de 121 itens com avisos
# passa de mil linhas, e o widget guardava tudo com as tags de cor: o consumo
# crescia durante a meia hora inteira e a rolagem ficava lenta justamente quando
# o usuario queria olhar. O log completo continua no arquivo.
MAX_LINHAS_LOG = 3000

#endregion

#region Widgets de apoio


def rotulo(pai, texto, fonte=FONTE, cor='texto', fundo='painel', **kw):

    return tk.Label(pai, text=texto, font=fonte, fg=COR[cor], bg=COR[fundo],
                    anchor='w', justify='left', **kw)


def encurtar(texto, cabe, fonte=FONTE):
    """O texto cortado com reticencias quando nao couber em <cabe> pixels.

    CORTAR, E NAO QUEBRAR EM DUAS LINHAS. Onde a altura e fixa - um botao, um
    cartao de aviso - a segunda linha nao aparece: ela vaza para fora da forma
    desenhada e fica por cima do que estiver embaixo."""

    try:
        from tkinter import font as _font
        medir = _font.Font(font=fonte).measure
    except Exception:
        largura_media = 8
        return (texto if len(texto) * largura_media <= cabe
                else texto[:max(3, cabe // largura_media - 1)] + '…')

    if medir(texto) <= cabe:
        return texto

    while texto and medir(texto + '…') > cabe:
        texto = texto[:-1]

    return texto.rstrip() + '…'


def espacado(texto):
    """Letra espacada, para os rotulos de secao.

    O Tk nao tem letter-spacing, e um rotulo em caixa alta sem respiro entre as
    letras fica compacto e pesado justamente onde ele deveria ser discreto. Um
    espaco fino entre os caracteres resolve com o que existe."""

    return ' '.join(texto)


#region A grade

# UMA GRADE DE 8. Todo espacamento, altura e raio sai daqui.
#
# Nao e purismo: numa tela com seis blocos, distancias que quase se repetem -
# 10, 12, 14 - fazem o olho procurar o alinhamento e nao achar. Tres valores que
# se repetem parecem de proposito; oito que quase batem parecem descuido.
ESPACO = 8
ESPACO_M = 16
ESPACO_G = 24

RAIO = 8

ALTURA_CONTROLE = 32
ALTURA_CABECALHO = 48
ALTURA_RODAPE = 28
LARGURA_LATERAL = 220
LARGURA_LATERAL_FECHADA = 52

#endregion

#region Desenho


def _contorno(x1, y1, x2, y2, raio):
    """Os pontos de um retangulo de cantos arredondados.

    Sao doze pontos e nao quatro: o create_polygon com smooth=True interpola
    curvas entre eles, e para o canto sair redondo e nao chanfrado ele precisa
    de tres pontos por quina - onde a reta acaba, a quina, e onde a proxima reta
    comeca."""

    raio = max(0, min(raio, (x2 - x1) // 2, (y2 - y1) // 2))

    return [
        x1 + raio, y1,  x2 - raio, y1,  x2, y1,
        x2, y1 + raio,  x2, y2 - raio,  x2, y2,
        x2 - raio, y2,  x1 + raio, y2,  x1, y2,
        x1, y2 - raio,  x1, y1 + raio,  x1, y1,
    ]


def arredondar(canvas, largura, altura, fundo, borda=None, raio=RAIO,
               espessura=1):
    """Desenha um retangulo arredondado ocupando o canvas inteiro."""

    canvas.delete('forma')

    if largura < 4 or altura < 4:
        return

    canvas.create_polygon(
        _contorno(espessura, espessura, largura - espessura, altura - espessura,
                  raio),
        smooth=True, splinesteps=24, tags='forma',
        fill=fundo, outline=borda or fundo, width=espessura)

    canvas.tag_lower('forma')


def estilos(estilo):
    """Ensina ao ttk as cores desta interface.

    O ttk nao herda cor de lugar nenhum: um Treeview ou um Scrollbar nascem com
    o tema do Windows - cinza claro - e num painel escuro isso grita mais que
    qualquer erro de alinhamento. Precisa do tema 'clam'."""

    estilo.configure('Fina.Vertical.TScrollbar',
                     background=COR['borda_clara'], troughcolor=COR['painel'],
                     bordercolor=COR['painel'], arrowcolor=COR['texto_fraco'],
                     relief='flat', borderwidth=0, arrowsize=12, width=10)

    estilo.map('Fina.Vertical.TScrollbar',
               background=[('active', COR['texto_fraco'])])

    estilo.configure('Fina.Horizontal.TScrollbar',
                     background=COR['borda_clara'], troughcolor=COR['painel'],
                     bordercolor=COR['painel'], arrowcolor=COR['texto_fraco'],
                     relief='flat', borderwidth=0, arrowsize=12)

    for nome, fundo in (('Escuro', 'painel'), ('Fundo', 'fundo')):

        estilo.configure(f'{nome}.Treeview',
                         background=COR[fundo], fieldbackground=COR[fundo],
                         foreground=COR['texto'], borderwidth=0, relief='flat',
                         rowheight=28, font=FONTE_PEQUENA)

        estilo.configure(f'{nome}.Treeview.Heading',
                         background=COR['painel_alto'],
                         foreground=COR['texto_fraco'],
                         relief='flat', borderwidth=0, padding=(8, 7),
                         font=FONTE_ROTULO)

        estilo.map(f'{nome}.Treeview.Heading',
                   background=[('active', COR['painel_alto'])])

        estilo.map(f'{nome}.Treeview',
                   background=[('selected', COR['primario_fundo'])],
                   foreground=[('selected', COR['texto_forte'])])

        # o tracejado de foco em volta da linha nao combina com nada
        estilo.layout(f'{nome}.Treeview',
                      [(f'{nome}.Treeview.treearea', {'sticky': 'nswe'})])


def titulo_da_pagina(pai, titulo, subtitulo=''):
    """O cabecalho de uma tela: nome na cor da marca, explicacao, risco."""

    caixa = tk.Frame(pai, bg=COR['fundo'])
    caixa.pack(fill='x', padx=ESPACO_G, pady=(ESPACO_M, 0))

    rotulo(caixa, titulo, FONTE_TITULO_PAGINA, cor='marca',
           fundo='fundo').pack(anchor='w')

    if subtitulo:
        rotulo(caixa, subtitulo, FONTE_PEQUENA, cor='texto_fraco',
               fundo='fundo').pack(anchor='w', pady=(2, 0))

    tk.Frame(caixa, bg=COR['borda'], height=1).pack(fill='x',
                                                    pady=(ESPACO_M, 0))

    return caixa


def secao(pai, texto, **kw):
    """Um titulo de bloco, acima do cartao a que ele se refere.

    FORA do cartao, e nao dentro. Uma barra de titulo dentro come 26 px de
    altura em cada bloco e repete o que o rotulo ja diria de graca."""

    return rotulo(pai, texto, FONTE_SECAO, cor='texto_forte', fundo='fundo',
                  **kw)

#endregion

#region Blocos


class Cartao(tk.Frame):
    """Um painel de cantos arredondados, sem barra de titulo.

    O Tk nao arredonda um Frame - ele so desenha retangulos. O jeito e desenhar
    a forma num Canvas atras e encaixar o conteudo DENTRO dela, recuado pelo
    raio. Como os dois tem a mesma cor, a uniao das duas formas e exatamente o
    retangulo arredondado, e os cantos quadrados do frame de dentro ficam
    escondidos sob a curva.

    O recuo nao e desperdicio: e a margem que o conteudo ia querer de qualquer
    jeito."""

    def __init__(self, pai, fundo='painel', fundo_pai='fundo', raio=RAIO,
                 recheio=ESPACO_M):

        super().__init__(pai, bg=COR[fundo_pai])

        self._fundo = fundo
        self._borda = 'borda'
        self._raio = raio

        self._forma = tk.Canvas(self, bg=COR[fundo_pai], highlightthickness=0,
                                bd=0)
        self._forma.place(x=0, y=0, relwidth=1, relheight=1)

        self.dentro = tk.Frame(self, bg=COR[fundo])
        self.dentro.pack(fill='both', expand=True, padx=recheio, pady=recheio)

        self.bind('<Configure>', self._redesenhar)

    def _redesenhar(self, _evento=None):

        arredondar(self._forma, self.winfo_width(), self.winfo_height(),
                   COR[self._fundo], COR[self._borda], self._raio)

    def pintar(self, fundo=None, borda=None):
        """Troca as cores da forma E do conteudo, de uma vez.

        Existe por causa dos cartoes que TEM ESTADO - selecionado, sob o mouse,
        com foco. Sem isto, quem quisesse um cartao selecionavel tinha de
        desenhar o proprio retangulo, e foi assim que os sete cartoes de mercado
        viraram o unico componente de canto reto do programa."""

        if fundo:
            self._fundo = fundo

        if borda:
            self._borda = borda

        self.dentro.config(bg=COR[self._fundo])

        for filho in self._todos(self.dentro):
            try:
                filho.config(bg=COR[self._fundo])
            except tk.TclError:
                pass

        self._redesenhar()

    def _todos(self, pai):

        for filho in pai.winfo_children():
            yield filho
            for neto in self._todos(filho):
                yield neto


class Numero(tk.Frame):
    """Icone, rotulo, numero grande e legenda - o cartao de indicador.

    A HIERARQUIA E O PONTO: o numero e a unica coisa em corpo grande, e por isso
    ele e o que se le primeiro de longe. O rotulo em maiuscula pequena diz do que
    ele e; a legenda embaixo diz o que ele significa, e so e lida por quem
    quiser."""

    def __init__(self, pai, rotulo_texto, dica='', emoji='', fundo='painel',
                 fundo_pai='fundo'):

        super().__init__(pai, bg=COR[fundo_pai])

        self._fundo = fundo

        self._forma = tk.Canvas(self, bg=COR[fundo_pai], highlightthickness=0,
                                bd=0)
        self._forma.place(x=0, y=0, relwidth=1, relheight=1)

        dentro = tk.Frame(self, bg=COR[fundo])
        dentro.pack(fill='both', expand=True, padx=ESPACO_M, pady=ESPACO_M - 2)

        topo = tk.Frame(dentro, bg=COR[fundo])
        topo.pack(fill='x')

        if emoji:
            rotulo(topo, emoji, ('Segoe UI Emoji', 11),
                   fundo=fundo).pack(side='left', padx=(0, 6))

        rotulo(topo, rotulo_texto.upper(), FONTE_ROTULO, cor='texto_fraco',
               fundo=fundo).pack(side='left')

        self.valor = rotulo(dentro, '—', FONTE_NUMERO, cor='texto_forte',
                            fundo=fundo)
        self.valor.pack(anchor='w', pady=(4, 0))

        self.dica = rotulo(dentro, dica, FONTE_MINIMA, cor='texto_fraco',
                           fundo=fundo)
        self.dica.pack(anchor='w')

        self.bind('<Configure>', self._redesenhar)

    def _redesenhar(self, _evento=None):
        arredondar(self._forma, self.winfo_width(), self.winfo_height(),
                   COR[self._fundo], COR['borda'], RAIO)

    def mostrar(self, valor, dica=None, cor='texto_forte'):

        self.valor.config(text=valor, fg=COR[cor])

        if dica is not None:
            self.dica.config(text=dica)

#endregion

PASTA_ICONES = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'cidades icones e pngs')

_cache_de_imagens = {}


def imagem(caminho, lado=28):
    """Carrega um PNG redimensionado, pronto para um Label. None se falhar.

    GUARDA A REFERENCIA num cache do modulo, e nao e frescura: o Tk nao segura o
    PhotoImage: se o unico dono for uma variavel local, o coletor de lixo o
    recolhe e a imagem some da tela sem erro nenhum. E o bug mais classico do
    tkinter, e o sintoma - um retangulo vazio onde havia uma figura - nao aponta
    para lugar nenhum."""

    chave = (caminho, lado)

    if chave in _cache_de_imagens:
        return _cache_de_imagens[chave]

    try:
        import base64
        import io

        from PIL import Image

        img = Image.open(caminho).convert('RGBA')
        img = img.resize((lado, lado), Image.LANCZOS)

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')

        foto = tk.PhotoImage(data=base64.b64encode(buffer.getvalue()))

    except Exception:
        foto = None

    _cache_de_imagens[chave] = foto

    return foto


def bandeira(cidade, lado=28):
    """O estandarte daquela cidade, ou None se nao houver arquivo."""

    arquivo = ('VANITY_WARBANNER_PRESENT_FW_'
               + cidade.upper().replace(' ', '') + '.png')

    caminho = os.path.join(PASTA_ICONES, arquivo)

    return imagem(caminho, lado) if os.path.exists(caminho) else None


class Emblema(tk.Canvas):
    """Um disco na cor da paleta com um simbolo no meio.

    Existe para o Mercado Negro, que nao tem estandarte no jogo. Ele ficava com
    um emoji ao lado de seis bandeiras de 30 px - outro peso, outro alinhamento,
    e a unica coisa da tela que nao parecia desenhada junto com o resto.

    Um disco do mesmo tamanho das bandeiras resolve sem inventar um brasao."""

    def __init__(self, pai, simbolo='◆', lado=30, cor='marca',
                 fundo='painel'):

        super().__init__(pai, width=lado, height=lado, bg=COR[fundo],
                         highlightthickness=0, bd=0)

        self._lado = lado
        self._simbolo = simbolo
        self._cor = cor

        self.desenhar(fundo)

    def desenhar(self, fundo=None):

        if fundo:
            self.config(bg=COR[fundo])

        self.delete('all')

        folga = 1
        lado = self._lado

        self.create_oval(folga, folga, lado - folga, lado - folga,
                         fill=COR['painel_alto'], outline=COR[self._cor],
                         width=1)

        self.create_text(lado / 2, lado / 2, text=self._simbolo,
                         font=('Segoe UI', int(lado * 0.42)),
                         fill=COR[self._cor])


class Marca(tk.Label):
    """O simbolo do aplicativo.

    Vem do marca.ico, e nao de um desenho refeito aqui. O PNG vai para o Tk em
    base64 - a alternativa seria gravar um arquivo temporario so para o tkinter
    poder abri-lo, ou depender do ImageTk, que nem toda instalacao do Pillow tem.

    A referencia da imagem fica guardada no proprio widget: sem isso o Python
    recolhe o objeto e o rotulo aparece vazio, que e o classico do PhotoImage."""

    def __init__(self, pai, lado=32, fundo='fundo'):

        import base64
        import io

        import marca

        dados = io.BytesIO()
        marca.arte(lado).save(dados, 'PNG')

        self._imagem = tk.PhotoImage(data=base64.b64encode(dados.getvalue()))

        super().__init__(pai, image=self._imagem, bg=COR[fundo], bd=0,
                         highlightthickness=0)


class Farol(tk.Canvas):
    """Bolinha de estado. Cor diz mais rapido que texto, e as duas juntas dizem
    melhor que qualquer uma sozinha."""

    def __init__(self, pai, fundo='fundo', lado=8):

        super().__init__(pai, width=lado, height=lado, bg=COR[fundo],
                         highlightthickness=0, bd=0)

        self._ponto = self.create_oval(0, 0, lado - 1, lado - 1,
                                       fill=COR['texto_fraco'], width=0)

    def acender(self, cor):
        self.itemconfig(self._ponto, fill=COR[cor])


class Botao(tk.Frame):
    """Botao desenhado a mao. PREENCHIDO nos tres tipos.

    O ttk.Button no Windows ignora cor de fundo, entao aqui e um Canvas: forma,
    texto e hover sao todos nossos.

    Os tres se distinguem por COR, e nao por peso:

        primario     azul     comeca alguma coisa
        secundario   cinza    faz algo sem consequencia
        perigo       vermelho gasta prata, apaga, nao tem volta

    Antes o primario e o perigo saiam do mesmo vermelho e a diferenca era
    preenchido contra contorno - o que funciona, mas pede que voce repare. Com o
    azul separado, os dois param de se parecer exatamente na tela onde isso
    importa."""

    ALTURA = ALTURA_CONTROLE

    def __init__(self, pai, texto, comando, tipo='normal', largura=14,
                 fundo_pai='painel', emoji=''):

        super().__init__(pai, bg=COR[fundo_pai])

        self._tipo = tipo
        self._comando = comando
        self._ativo = True
        self._texto = f'{emoji}  {texto}' if emoji else texto
        self._fundo_pai = fundo_pai
        self._sobre = False

        self._largura = max(72, largura * 8 + 20)

        self._canvas = tk.Canvas(self, width=self._largura,
                                 height=self.ALTURA,
                                 bg=COR[fundo_pai], highlightthickness=0, bd=0,
                                 cursor='hand2')
        self._canvas.pack()

        self._canvas.bind('<Button-1>', self._clicado)
        self._canvas.bind('<Enter>', self._entrou)
        self._canvas.bind('<Leave>', self._saiu)
        self._canvas.bind('<Configure>', lambda _e: self._pintar())

        self._pintar()

    def _encurtar(self, texto):
        """O texto cortado com reticencias se nao couber. LARGURA NAO MUDA.

        A largura e fixa de proposito. A versao anterior crescia para caber o
        texto, o que resolvia o corte e criava outro problema pior: selecionar
        um item de nome longo empurrava a coluna inteira, e a tela dancava a
        cada clique.

        Um botao que muda de tamanho conforme o que voce seleciona nao e um
        botao - e um elemento de layout instavel, e o olho perde o lugar."""

        return encurtar(texto, self._largura - 20, FONTE_SECAO)

    def _cores(self):
        """(fundo, texto, borda) para o estado atual."""

        if not self._ativo:
            return COR['painel_alto'], COR['texto_fraco'], COR['borda']

        if self._tipo == 'destaque':
            f = COR['primario_alto'] if self._sobre else COR['primario']
            return f, COR['sobre_primario'], f

        if self._tipo == 'perigo':
            f = COR['perigo_alto'] if self._sobre else COR['perigo']
            return f, COR['sobre_perigo'], f

        # AS TRES ACOES QUE TEM COR PROPRIA, e cada uma com um significado so:
        # azul salva, verde cria, rosa apaga. Um botao que apaga e um botao que
        # gasta prata nao podem ter a mesma cor, e ate aqui os dois eram
        # vermelhos.
        if self._tipo in ('salvar', 'criar', 'limpar'):
            f = COR[self._tipo + ('_alto' if self._sobre else '')]
            return f, '#FFFFFF', f

        f = COR['borda_clara'] if self._sobre else COR['painel_alto']
        return f, COR['texto_forte'] if self._sobre else COR['texto'], COR['borda']

    def _pintar(self):

        fundo, frente, borda = self._cores()

        largura = self._canvas.winfo_width() or int(self._canvas['width'])
        altura = self._canvas.winfo_height() or self.ALTURA

        self._canvas.config(bg=COR[self._fundo_pai])
        self._canvas.delete('texto')

        arredondar(self._canvas, largura, altura, fundo, borda, raio=6)

        self._canvas.create_text(largura / 2, altura / 2,
                                 text=self._encurtar(self._texto),
                                 font=FONTE_SECAO, fill=frente, tags='texto')

    def trocar_texto(self, texto):
        """Um botao que diz o que vai fazer COM O QUE ESTA SELECIONADO dispensa
        instrucao. "Acrescentar" pede que voce adivinhe o quê; "Acrescentar
        Broadsword" nao pede nada."""

        self._texto = texto
        self._pintar()

    def _clicado(self, _=None):
        if self._ativo:
            self._comando()

    def _entrou(self, _=None):
        self._sobre = True
        self._pintar()

    def _saiu(self, _=None):
        self._sobre = False
        self._pintar()

    def habilitar(self, ligado):
        self._ativo = bool(ligado)
        self._canvas.config(cursor='hand2' if ligado else 'arrow')
        self._pintar()


class Entrada(tk.Frame):
    """Um campo de texto com borda que acende no foco.

    O tk.Entry nao tem borda que se possa colorir de forma decente - o relief
    dele e um sulco desenhado pelo Windows. Aqui a borda e um Frame por fora, e
    trocar a cor dele e trocar a borda."""

    def __init__(self, pai, variavel, largura=12, fundo='painel',
                 alinhamento='left', ao_confirmar=None):

        super().__init__(pai, bg=COR['borda'], padx=1, pady=1)

        self.campo = tk.Entry(self, textvariable=variavel, width=largura,
                              justify=alinhamento, bg=COR['painel_alto'],
                              fg=COR['texto_forte'], relief='flat', bd=0,
                              insertbackground=COR['primario'], font=FONTE)

        self.campo.pack(fill='both', expand=True, ipady=5, ipadx=6)

        self.campo.bind('<FocusIn>', lambda _e: self.config(bg=COR['primario']))
        self.campo.bind('<FocusOut>', lambda _e: self.config(bg=COR['borda']))

        if ao_confirmar:
            self.campo.bind('<Return>', lambda _e: ao_confirmar())


class Campo(tk.Frame):
    """Uma linha de formulario: rotulo a esquerda, controle a direita.

    O ALINHAMENTO A DIREITA E O QUE FAZ A LISTA PARECER UMA LISTA. Com os campos
    encostados no fim, os valores formam uma coluna so, e comparar dois numeros
    vira olhar para baixo em vez de procurar."""

    def __init__(self, pai, rotulo_texto, variavel, unidade='', dica='',
                 largura=10, fundo='painel', ao_confirmar=None):

        super().__init__(pai, bg=COR[fundo])

        linha = tk.Frame(self, bg=COR[fundo])
        linha.pack(fill='x')

        rotulo(linha, rotulo_texto, FONTE, cor='texto',
               fundo=fundo).pack(side='left')

        if unidade:
            rotulo(linha, unidade, FONTE_PEQUENA, cor='texto_fraco',
                   fundo=fundo).pack(side='right', padx=(6, 0))

        self.entrada = Entrada(linha, variavel, largura, fundo,
                               alinhamento='center', ao_confirmar=ao_confirmar)
        self.entrada.pack(side='right')

        if dica:
            rotulo(self, dica, FONTE_MINIMA, cor='texto_fraco', fundo=fundo,
                   wraplength=560).pack(anchor='w', pady=(2, 0))


class Caixa(tk.Frame):
    """Caixa de selecao desenhada.

    O tk.Checkbutton usa o quadradinho do Windows - branco, com um risco azul do
    tema nativo - e num painel escuro ele e a coisa mais fora de lugar da tela.
    """

    LADO = 16

    def __init__(self, pai, texto, variavel, dica='', fundo='painel',
                 ao_mudar=None):

        super().__init__(pai, bg=COR[fundo])

        self._var = variavel
        self._fundo = fundo
        self._ao_mudar = ao_mudar

        linha = tk.Frame(self, bg=COR[fundo], cursor='hand2')
        linha.pack(fill='x')

        self._marca = tk.Canvas(linha, width=self.LADO, height=self.LADO,
                                bg=COR[fundo], highlightthickness=0, bd=0,
                                cursor='hand2')
        self._marca.pack(side='left', pady=2)

        self._rotulo = rotulo(linha, texto, FONTE, cor='texto', fundo=fundo)
        self._rotulo.pack(side='left', padx=(ESPACO, 0))

        for alvo in (linha, self._marca, self._rotulo):
            alvo.bind('<Button-1>', self._alternar)

        if dica:
            rotulo(self, dica, FONTE_MINIMA, cor='texto_fraco', fundo=fundo,
                   wraplength=580).pack(anchor='w', padx=(self.LADO + ESPACO, 0))

        self._pintar()

        try:
            variavel.trace_add('write', lambda *_: self._pintar())
        except AttributeError:
            pass

    def _alternar(self, _=None):
        self._var.set(not self._var.get())
        self._pintar()

        if self._ao_mudar:
            self._ao_mudar()

    def _pintar(self):

        ligada = bool(self._var.get())

        self._marca.delete('all')
        self._marca.config(bg=COR[self._fundo])

        arredondar(self._marca, self.LADO, self.LADO,
                   COR['primario'] if ligada else COR['painel_alto'],
                   COR['primario'] if ligada else COR['borda_clara'], raio=4)

        if ligada:
            self._marca.create_line(4, 8, 7, 11, 12, 5,
                                    fill=COR['sobre_primario'], width=2,
                                    capstyle='round', joinstyle='round')


class Lista(tk.Frame):
    """Lista suspensa propria.

    O tk.OptionMenu e um botao cinza do Windows com uma seta preta. Ele nao
    aceita cor de fundo de forma confiavel e e o componente que mais denuncia
    que a janela nao foi desenhada, e sim montada."""

    def __init__(self, pai, variavel, valores, ao_mudar=None, largura=16,
                 fundo='painel'):

        super().__init__(pai, bg=COR[fundo])

        self._var = variavel
        self._ao_mudar = ao_mudar
        self._fundo = fundo
        self._sobre = False

        largura_px = max(90, largura * 8)

        self._canvas = tk.Canvas(self, width=largura_px,
                                 height=ALTURA_CONTROLE, bg=COR[fundo],
                                 highlightthickness=0, bd=0, cursor='hand2')
        self._canvas.pack()

        self._menu = tk.Menu(self, tearoff=0, bg=COR['painel_alto'],
                             fg=COR['texto'], bd=0,
                             activebackground=COR['primario_fundo'],
                             activeforeground=COR['texto_forte'],
                             font=FONTE_PEQUENA, relief='flat')

        self.trocar_valores(valores)

        self._canvas.bind('<Button-1>', self._abrir)
        self._canvas.bind('<Enter>', lambda _e: self._pintar(True))
        self._canvas.bind('<Leave>', lambda _e: self._pintar(False))

        try:
            variavel.trace_add('write', lambda *_: self._pintar(self._sobre))
        except AttributeError:
            pass

        self._pintar()

    def trocar_valores(self, valores):

        self._menu.delete(0, 'end')

        for valor in valores:
            self._menu.add_command(
                label=str(valor),
                command=lambda v=valor: self._escolher(v))

        self._pintar(self._sobre)

    def _escolher(self, valor):
        self._var.set(valor)
        self._pintar(False)

        if self._ao_mudar:
            self._ao_mudar(valor)

    def _abrir(self, _=None):
        self._menu.tk_popup(self._canvas.winfo_rootx(),
                            self._canvas.winfo_rooty() + ALTURA_CONTROLE)

    def _pintar(self, sobre=False):

        self._sobre = sobre

        largura = self._canvas.winfo_width() or int(self._canvas['width'])
        altura = ALTURA_CONTROLE

        self._canvas.delete('conteudo')
        self._canvas.config(bg=COR[self._fundo])

        arredondar(self._canvas, largura, altura, COR['painel_alto'],
                   COR['primario'] if sobre else COR['borda'], raio=6)

        self._canvas.create_text(10, altura / 2, anchor='w',
                                 text=str(self._var.get()), font=FONTE,
                                 fill=COR['texto_forte'], tags='conteudo')

        x = largura - 14
        y = altura / 2 - 1

        self._canvas.create_polygon(x - 4, y - 1, x + 4, y - 1, x, y + 4,
                                    fill=COR['texto_fraco'], tags='conteudo')


class Tabela(tk.Frame):
    """Tabela com cabecalho, linhas numeradas e zebra.

    A NUMERACAO NAO E ENFEITE. Numa lista de duzentas linhas, "a linha 47" e a
    unica forma de duas pessoas - ou voce e o log - falarem da mesma linha.

    A zebra e discreta de proposito: forte demais, ela compete com o dado; sem
    ela, o olho perde a linha ao atravessar oito colunas."""

    def __init__(self, pai, colunas, fundo='painel', altura=12):

        super().__init__(pai, bg=COR[fundo])

        self._colunas = colunas

        rolagem = ttk.Scrollbar(self, orient='vertical',
                                style='Fina.Vertical.TScrollbar')
        rolagem.pack(side='right', fill='y')

        estilo = 'Escuro' if fundo == 'painel' else 'Fundo'

        self.arvore = ttk.Treeview(
            self, style=f'{estilo}.Treeview', show='tree headings',
            columns=[c[0] for c in colunas], height=altura,
            yscrollcommand=rolagem.set)

        self.arvore.heading('#0', text='')
        self.arvore.column('#0', width=44, minwidth=44, stretch=False,
                           anchor='e')

        for chave, titulo, largura, *resto in colunas:
            alinhamento = resto[0] if resto else 'w'
            self.arvore.heading(chave, text=titulo.upper())
            self.arvore.column(chave, width=largura, anchor=alinhamento)

        self.arvore.pack(fill='both', expand=True)
        rolagem.config(command=self.arvore.yview)

        self.arvore.tag_configure('par', background=COR[fundo])
        self.arvore.tag_configure(
            'impar', background=COR['painel_alto'] if fundo == 'painel'
            else COR['painel'])

    def limpar(self):
        self.arvore.delete(*self.arvore.get_children())

    def acrescentar(self, valores, iid=None):

        n = len(self.arvore.get_children())

        return self.arvore.insert(
            '', 'end', iid=iid, text=str(n + 1), values=valores,
            tags=('par' if n % 2 == 0 else 'impar',))

    def encher(self, linhas):
        self.limpar()
        for valores in linhas:
            self.acrescentar(valores)

    def selecionado(self):
        alvo = self.arvore.focus()
        return self.arvore.item(alvo, 'values') if alvo else None


class Dialogo(tk.Toplevel):
    """Caixa de dialogo no tema do aplicativo.

    O messagebox usa o tema do Windows: num app cuidadosamente escuro, a
    confirmacao do modo real - o momento mais importante da interface - aparecia
    como uma caixa cinza-claro de sistema. E o unico ponto em que o acabamento
    quebrava, e e justamente onde se pede a decisao mais seria."""

    def __init__(self, pai, titulo, texto, tipo='normal', botoes=('OK',),
                 padrao=0):

        super().__init__(pai, bg=COR['painel'])

        self.resultado = None

        self.title(titulo)
        self.resizable(False, False)
        self.configure(padx=1, pady=1)

        # transient() so quando o pai esta na tela. Com um pai oculto - o caso da
        # recusa de segunda instancia, em que a janela principal nem chega a
        # existir - o Windows nao desenha a caixa em lugar nenhum, e o processo
        # ficava preso num wait_window por uma janela invisivel.
        try:
            if pai is not None and pai.winfo_viewable():
                self.transient(pai)
        except tk.TclError:
            pass

        cor_borda = {'perigo': COR['perigo'], 'aviso': COR['aviso'],
                     'normal': COR['borda']}[tipo]

        self.configure(bg=cor_borda)

        corpo = tk.Frame(self, bg=COR['painel'], padx=26, pady=22)
        corpo.pack(fill='both', expand=True)

        rotulo(corpo, titulo, fonte=('Segoe UI Semibold', 13),
               cor='perigo' if tipo == 'perigo' else 'texto').pack(anchor='w')

        rotulo(corpo, texto, fonte=FONTE, cor='texto_fraco',
               wraplength=460).pack(anchor='w', pady=(12, 0))

        linha = tk.Frame(corpo, bg=COR['painel'])
        linha.pack(anchor='e', pady=(22, 0))

        for i, nome in enumerate(botoes):
            estilo = 'destaque' if i == padrao else 'normal'
            if tipo == 'perigo' and i == padrao:
                estilo = 'perigo'
            Botao(linha, nome, lambda n=nome: self._responder(n), tipo=estilo,
                  largura=max(10, len(nome) + 2)).pack(side='left', padx=(10, 0))

        self.protocol('WM_DELETE_WINDOW', lambda: self._responder(None))
        self.bind('<Escape>', lambda _: self._responder(None))

        self.update_idletasks()
        self._centralizar(pai)

        self.grab_set()
        self.lift()
        self.focus_force()
        self.wait_window(self)

    def _centralizar(self, pai):
        """No meio do pai, ou no meio da tela quando nao ha pai visivel."""

        try:
            if pai is not None and pai.winfo_viewable():
                base_x, base_y = pai.winfo_rootx(), pai.winfo_rooty()
                largura, altura = pai.winfo_width(), pai.winfo_height()
            else:
                base_x = base_y = 0
                largura = self.winfo_screenwidth()
                altura = self.winfo_screenheight()

            x = base_x + (largura - self.winfo_width()) // 2
            y = base_y + (altura - self.winfo_height()) // 3

            self.geometry(f'+{max(0, x)}+{max(0, y)}')

        except tk.TclError:
            pass

    def _responder(self, nome):
        self.resultado = nome
        self.destroy()


def perguntar(pai, titulo, texto, tipo='normal', sim='Continuar', nao='Cancelar'):
    """True se o usuario confirmou."""

    return Dialogo(pai, titulo, texto, tipo=tipo, botoes=(sim, nao)).resultado == sim


def avisar(pai, titulo, texto, tipo='normal'):

    Dialogo(pai, titulo, texto, tipo=tipo, botoes=('Entendi',))


class Abertura(tk.Toplevel):
    """A marca enquanto o programa carrega.

    Nao e so enfeite. Abrir a planilha, montar os tres paineis e resolver o
    caminho do Tesseract levam um tempo em que a tela fica vazia - e uma janela
    que demora sem dizer nada parece travada. Aqui a espera tem cara.

    Sem borda e sem barra de titulo: uma abertura com botao de fechar e minimizar
    e uma janela comum fingindo ser uma abertura."""

    LADO = 360
    ALTURA = 292
    TEMPO_MINIMO = 1400   # ms que ela fica na tela mesmo se tudo carregar antes

    def __init__(self, pai, versao=''):

        super().__init__(pai, bg=COR['destaque'])

        self.overrideredirect(True)

        try:
            self.attributes('-topmost', True)
            self.attributes('-alpha', 0.0)   # entra suave
        except tk.TclError:
            pass

        corpo = tk.Frame(self, bg=COR['painel'], padx=30, pady=30)
        corpo.pack(fill='both', expand=True, padx=1, pady=1)

        try:
            Marca(corpo, lado=88, fundo='painel').pack(pady=(6, 0))
        except Exception:
            pass   # sem a marca a abertura ainda serve para dizer que carrega

        rotulo(corpo, 'Albion BM', fonte=('Segoe UI Semibold', 17),
               fundo='painel').pack(pady=(18, 0))

        rotulo(corpo, 'Mercado Negro', fonte=FONTE_PEQUENA, cor='texto_fraco',
               fundo='painel').pack(pady=(2, 0))

        # A barra nao mede nada - nao ha o que medir num carregamento de um
        # segundo. Ela existe para a janela nao parecer congelada.
        self._trilho = tk.Canvas(corpo, width=140, height=2, bg=COR['borda'],
                                 highlightthickness=0)
        self._trilho.pack(pady=(22, 0))

        self._risco = self._trilho.create_rectangle(0, 0, 0, 2,
                                                    fill=COR['destaque'], width=0)

        if versao:
            rotulo(corpo, versao, fonte=FONTE_MINIMA, cor='texto_fraco',
                   fundo='painel').pack(pady=(14, 0))

        self.update_idletasks()

        x = (self.winfo_screenwidth() - self.LADO) // 2
        y = (self.winfo_screenheight() - self.ALTURA) // 2

        self.geometry(f'{self.LADO}x{self.ALTURA}+{x}+{y}')

        self._nascida = None
        self._passo = 0

        self._aparecer()
        self._andar()

    def _aparecer(self, quanto=0.0):

        try:
            self.attributes('-alpha', quanto)
        except tk.TclError:
            return

        if quanto < 1.0:
            self.after(16, lambda: self._aparecer(min(1.0, quanto + 0.12)))

    def _andar(self):
        """Enche a barrinha ao longo do tempo minimo."""

        self._passo += 1

        fracao = min(1.0, self._passo * 40 / self.TEMPO_MINIMO)

        try:
            self._trilho.coords(self._risco, 0, 0, 140 * fracao, 2)
        except tk.TclError:
            return

        if fracao < 1.0:
            self.after(40, self._andar)

    def fechar(self, quando_terminar=None):
        """Fecha respeitando o tempo minimo, e chama <quando_terminar> depois.

        Sem o minimo, num computador rapido a abertura pisca por 200 ms - o que
        e pior que nao ter abertura nenhuma."""

        if self._nascida is None:
            self._nascida = 0

        def sumir(quanto=1.0):
            try:
                self.attributes('-alpha', quanto)
            except tk.TclError:
                quanto = 0

            if quanto <= 0:
                try:
                    self.destroy()
                except tk.TclError:
                    pass
                if quando_terminar:
                    quando_terminar()
                return

            self.after(16, lambda: sumir(quanto - 0.14))

        self.after(self.TEMPO_MINIMO, sumir)


class Rolavel(tk.Frame):
    """Area que ganha barra de rolagem SO quando o conteudo nao cabe.

    O Tk nao tem isso pronto: um Frame simplesmente desenha os filhos para fora
    da area visivel e nao avisa ninguem. Era o que acontecia com a lateral - os
    tres cartoes, as ferramentas e as preferencias somavam mais que a altura da
    janela, e as ultimas opcoes ficavam cortadas sem nenhum sinal de que existiam.

    Ponha os filhos em <self.dentro>, e nao no proprio widget.

    A barra some quando nao e necessaria: uma barra sempre visivel numa lateral
    de 236 px come largura util e diz "tem mais coisa aqui" mesmo quando nao tem."""

    def __init__(self, pai, fundo='fundo', largura=None):

        super().__init__(pai, bg=COR[fundo])

        self._canvas = tk.Canvas(self, bg=COR[fundo], highlightthickness=0, bd=0)

        if largura:
            self._canvas.config(width=largura)

        self._barra = ttk.Scrollbar(self, orient='vertical', style='Fina.Vertical.TScrollbar',
                                    command=self._canvas.yview)

        self._canvas.config(yscrollcommand=self._barra.set)
        self._canvas.pack(side='left', fill='both', expand=True)

        self.dentro = tk.Frame(self._canvas, bg=COR[fundo])

        self._janela = self._canvas.create_window(0, 0, window=self.dentro,
                                                  anchor='nw')

        self.dentro.bind('<Configure>', self._conteudo_mudou)
        self._canvas.bind('<Configure>', self._area_mudou)

        # A roda do mouse so vale enquanto o cursor esta por cima. Ligada de
        # forma global o tempo todo, rolar a lista de um combobox rolaria a
        # lateral junto.
        self._canvas.bind('<Enter>', self._ligar_roda)
        self._canvas.bind('<Leave>', self._desligar_roda)

    def _conteudo_mudou(self, _=None):

        self._canvas.config(scrollregion=self._canvas.bbox('all'))
        self._ajustar_barra()

    def _area_mudou(self, evento):

        # o conteudo acompanha a largura da area, para o fill='x' dos filhos
        # funcionar como funcionaria num Frame comum
        self._canvas.itemconfig(self._janela, width=evento.width)
        self._ajustar_barra()

    def _ajustar_barra(self):

        precisa = self.dentro.winfo_reqheight() > self._canvas.winfo_height()

        if precisa and not self._barra.winfo_ismapped():
            self._barra.pack(side='right', fill='y')
        elif not precisa and self._barra.winfo_ismapped():
            self._barra.pack_forget()
            self._canvas.yview_moveto(0)

    def altura_do_conteudo(self):
        """Altura que o conteudo PEDE, e nao a que a area tem.

        O winfo_reqheight de um Rolavel devolve o tamanho padrao do Canvas, que
        nao tem relacao nenhuma com o que ha dentro. Quem precisa dimensionar a
        area em volta tem que perguntar ao conteudo."""

        return self.dentro.winfo_reqheight()

    def _ligar_roda(self, _=None):
        self._canvas.bind_all('<MouseWheel>', self._rodou)

    def _desligar_roda(self, _=None):
        self._canvas.unbind_all('<MouseWheel>')

    def _rodou(self, evento):

        if self.dentro.winfo_reqheight() <= self._canvas.winfo_height():
            return

        self._canvas.yview_scroll(-1 if evento.delta > 0 else 1, 'units')


class Formulario(tk.Toplevel):
    """Caixa com campos, no tema do aplicativo. Devolve um dicionario ou None.

    Cada campo e um dicionario: chave, rotulo, e opcionalmente dica, padrao,
    valores (vira lista suspensa) e obrigatorio."""

    def __init__(self, pai, titulo, campos, explicacao='', confirmar='Salvar'):

        super().__init__(pai, bg=COR['borda'])

        self.resultado = None
        self._campos = campos
        self._vars = {}

        self.title(titulo)
        self.resizable(False, False)
        self.configure(padx=1, pady=1)

        try:
            if pai is not None and pai.winfo_viewable():
                self.transient(pai)
        except tk.TclError:
            pass

        corpo = tk.Frame(self, bg=COR['painel'], padx=26, pady=22)
        corpo.pack(fill='both', expand=True)

        rotulo(corpo, titulo, fonte=('Segoe UI Semibold', 13)).pack(anchor='w')

        if explicacao:
            rotulo(corpo, explicacao, fonte=FONTE_PEQUENA, cor='texto_medio',
                   wraplength=480).pack(anchor='w', pady=(8, 0))

        tk.Frame(corpo, bg=COR['borda'], height=1).pack(fill='x', pady=(16, 0))

        grade = tk.Frame(corpo, bg=COR['painel'])
        grade.pack(fill='x', pady=(16, 0))

        for i, campo in enumerate(campos):

            rotulo(grade, campo['rotulo'], fonte=FONTE_PEQUENA,
                   cor='texto_medio').grid(row=i * 2, column=0, sticky='w',
                                           pady=(0 if i == 0 else 12, 4))

            var = tk.StringVar(value=str(campo.get('padrao', '')))
            self._vars[campo['chave']] = var

            if campo.get('valores'):
                entrada = ttk.Combobox(grade, values=list(campo['valores']),
                                       state='readonly', font=FONTE,
                                       textvariable=var, width=40)
            else:
                entrada = tk.Entry(grade, textvariable=var, font=FONTE, width=42,
                                   bg=COR['painel_alto'], fg=COR['texto'], bd=0,
                                   highlightthickness=1,
                                   highlightbackground=COR['borda_clara'],
                                   highlightcolor=COR['destaque'],
                                   insertbackground=COR['texto'])

            entrada.grid(row=i * 2 + 1, column=0, sticky='we', ipady=3)

            if i == 0:
                entrada.focus_set()

            if campo.get('dica'):
                rotulo(grade, campo['dica'], fonte=FONTE_MINIMA, cor='texto_fraco',
                       wraplength=420).grid(row=i * 2 + 1, column=1, sticky='w',
                                            padx=(14, 0))

        self._erro = rotulo(corpo, '', fonte=FONTE_PEQUENA, cor='perigo',
                            wraplength=480)
        self._erro.pack(anchor='w', pady=(14, 0))

        linha = tk.Frame(corpo, bg=COR['painel'])
        linha.pack(anchor='e', pady=(18, 0))

        Botao(linha, 'Cancelar', self._cancelar, largura=12).pack(side='left')
        Botao(linha, confirmar, self._confirmar, tipo='destaque',
              largura=12).pack(side='left', padx=(10, 0))

        self.bind('<Return>', lambda _: self._confirmar())
        self.bind('<Escape>', lambda _: self._cancelar())
        self.protocol('WM_DELETE_WINDOW', self._cancelar)

        self.update_idletasks()

        try:
            if pai is not None and pai.winfo_viewable():
                x = pai.winfo_rootx() + (pai.winfo_width() - self.winfo_width()) // 2
                y = pai.winfo_rooty() + (pai.winfo_height() - self.winfo_height()) // 3
                self.geometry(f'+{max(0, x)}+{max(0, y)}')
        except tk.TclError:
            pass

        self.grab_set()
        self.lift()
        self.focus_force()
        self.wait_window(self)

    def _confirmar(self):

        valores = {c: v.get().strip() for c, v in self._vars.items()}

        faltando = [c['rotulo'] for c in self._campos
                    if c.get('obrigatorio') and not valores.get(c['chave'])]

        if faltando:
            self._erro.config(text='Falta preencher: ' + ', '.join(faltando))
            return

        self.resultado = valores
        self.destroy()

    def _cancelar(self):
        self.resultado = None
        self.destroy()


class CartaoBot(tk.Frame):
    """Item da lateral: nome do bot, uma linha do que ele faz, e selecao."""

    def __init__(self, pai, modulo, ao_escolher):

        super().__init__(pai, bg=COR['painel'], padx=1, pady=1)

        self._chave = modulo.NOME.lower()
        self._ao_escolher = ao_escolher
        self._marcado = False

        self._dentro = tk.Frame(self, bg=COR['painel'], padx=13, pady=12)
        self._dentro.pack(fill='both', expand=True)

        topo = tk.Frame(self._dentro, bg=COR['painel'])
        topo.pack(fill='x')

        # O icone ganha uma pastilha propria. Solto ao lado do nome ele parecia
        # um caractere perdido; numa caixinha ele vira um simbolo.
        self._pastilha = tk.Frame(topo, bg=COR['painel_alto'], width=22, height=22)
        self._pastilha.pack(side='left', padx=(0, 10))
        self._pastilha.pack_propagate(False)

        self._icone = tk.Label(self._pastilha, text=modulo.ICONE,
                               font=('Segoe UI', 10), bg=COR['painel_alto'],
                               fg=COR['texto_fraco'])
        self._icone.pack(expand=True)

        self._nome = rotulo(topo, modulo.ROTULO, fonte=FONTE_SECAO)
        self._nome.pack(side='left')

        self._linha = rotulo(self._dentro, modulo.LINHA_RESUMO, fonte=FONTE_PEQUENA,
                             cor='texto_fraco', wraplength=200)
        self._linha.pack(anchor='w', pady=(5, 0))

        self._todos = (self, self._dentro, topo, self._nome, self._linha,
                       self._icone, self._pastilha)

        for alvo in self._todos:
            alvo.bind('<Button-1>', self._clicado)
            alvo.bind('<Enter>', self._entrou)
            alvo.bind('<Leave>', self._saiu)
            alvo.config(cursor='hand2')

    def _clicado(self, _=None):
        self._ao_escolher(self._chave)

    def _entrou(self, _=None):
        if not self._marcado:
            self._pintar(COR['borda'], COR['painel_alto'], COR['painel_topo'])

    def _saiu(self, _=None):
        if not self._marcado:
            self._pintar(COR['painel'], COR['painel'], COR['painel_alto'])

    def _pintar(self, borda, fundo, pastilha):

        self.config(bg=borda)

        for alvo in (self._dentro, self._nome, self._linha):
            alvo.config(bg=fundo)

        self._pastilha.config(bg=pastilha)
        self._icone.config(bg=pastilha)

        # o Frame do topo tambem, senao sobra uma faixa da cor antiga
        self._nome.master.config(bg=fundo)

    def marcar(self, ligado):

        self._marcado = ligado

        if ligado:
            self._pintar(COR['destaque'], COR['painel_alto'], COR['destaque_fundo'])
            self._nome.config(fg=COR['texto'])
            self._linha.config(fg=COR['texto_medio'])
            self._icone.config(fg=COR['destaque'])
        else:
            self._pintar(COR['painel'], COR['painel'], COR['painel_alto'])
            self._nome.config(fg=COR['texto_fraco'])
            self._linha.config(fg=COR['texto_fraco'])
            self._icone.config(fg=COR['texto_fraco'])


class Faixa(tk.Toplevel):
    """Faixa fina no topo da tela, visivel enquanto o bot roda.

    O comportamento padrao minimiza a janela e some. Durante os 32 minutos
    seguintes nao havia nenhum sinal de vida - nem progresso, nem item atual, nem
    aviso de erro - e a unica forma de saber era restaurar a janela, que tira o
    foco do jogo e faz o bot parar.

    NAO ACEITA CLIQUE, de proposito. Um botao aqui roubaria o foco do jogo, e a
    conferencia de foco que agora roda a cada item encerraria a varredura. O
    controle continua sendo F11 e F12, que funcionam com o jogo em primeiro
    plano."""

    ALTURA = 34

    def __init__(self, pai):

        super().__init__(pai, bg=COR['destaque'])

        self.overrideredirect(True)
        self.attributes('-topmost', True)

        try:
            self.attributes('-alpha', 0.92)
            self.attributes('-disabled', True)   # nao rouba foco do jogo
        except tk.TclError:
            pass

        corpo = tk.Frame(self, bg=COR['painel'], padx=16, pady=6)
        corpo.pack(fill='both', expand=True, padx=1, pady=1)

        self._titulo = rotulo(corpo, 'Albion BM', fonte=('Segoe UI Semibold', 9),
                              cor='destaque')
        self._titulo.pack(side='left')

        self._texto = rotulo(corpo, '', fonte=FONTE_PEQUENA, cor='texto')
        self._texto.pack(side='left', padx=(14, 0))

        self._teclas = rotulo(corpo, 'F11 pausa    F12 para na hora', fonte=FONTE_MINIMA,
                              cor='texto_fraco')
        self._teclas.pack(side='right')

        self._contador = rotulo(corpo, '', fonte=('Consolas', 9), cor='texto_fraco')
        self._contador.pack(side='right', padx=(0, 18))

        largura = min(760, self.winfo_screenwidth() - 40)
        x = (self.winfo_screenwidth() - largura) // 2

        self.geometry(f'{largura}x{self.ALTURA}+{x}+0')

    def atualizar(self, texto, contador='', tom='texto'):

        self._texto.config(text=texto[:70], fg=COR[tom])
        self._contador.config(text=contador)


class Avisos(tk.Toplevel):
    """Cartoes curtos empilhados no canto de baixo, por cima do jogo.

    CADA PRECO LIDO APARECE AQUI, na hora, ao lado do numero que o jogo esta
    mostrando. E a unica forma de conferir uma leitura enquanto ela acontece: a
    janela do aplicativo passa a varredura inteira minimizada, e o log so vai
    ser lido depois - quando os quarenta minutos de leitura ja passaram e o que
    saiu errado ja foi gravado.

    CANTO DE BAIXO, E NAO DO MEIO. Ali nao ha nada do jogo que se precise ver
    durante uma varredura, e o olho encontra o cartao sem procurar. O topo ja e
    da faixa de andamento.

    CINCO CARTOES, e o mais velho sai. Nao e economia de espaco: uma pilha que
    cresce vira parede, e parede se ignora. Cinco e o quanto se le de relance
    entre uma combinacao e outra.

    NAO ACEITA CLIQUE, como a faixa - um clique aqui tiraria o foco do jogo e a
    conferencia de foco encerraria a varredura."""

    LARGURA = 264
    ALTURA = 34
    VAO = 6
    QUANTOS = 5
    MARGEM = 18
    RODAPE = 56          # espaco da barra de tarefas e do relogio do jogo

    def __init__(self, pai):

        super().__init__(pai, bg=COR['fundo'])

        self.overrideredirect(True)

        try:
            self.attributes('-topmost', True)
            self.attributes('-alpha', 0.94)
            self.attributes('-disabled', True)
            self.attributes('-transparentcolor', COR['fundo'])
        except tk.TclError:
            pass

        self._cartoes = []

        self.geometry(f'{self.LARGURA}x1'
                      f'+{self.winfo_screenwidth()}+{self.winfo_screenheight()}')

    #region Fora

    def mostrar(self, titulo, valor=None, tom='primario'):
        """Poe mais um cartao embaixo da pilha."""

        while len(self._cartoes) >= self.QUANTOS:
            self._cartoes.pop(0).destroy()

        self._cartoes.append(self._cartao(titulo, valor, tom))
        self._arrumar()

    def limpar(self):

        for c in self._cartoes:
            c.destroy()

        self._cartoes = []
        self._arrumar()

    #endregion

    #region Dentro

    def _cartao(self, titulo, valor, tom):
        """Nome a esquerda, numero a direita, num retangulo arredondado.

        TUDO DESENHADO NO CANVAS, sem rotulos por cima. O cartao tem cantos
        curvos, e um Label e sempre retangular: encaixado dentro da curva ele
        deixaria quatro quinas da cor errada aparecendo justamente nos cantos."""

        tela = tk.Canvas(self, width=self.LARGURA, height=self.ALTURA,
                         bg=COR['fundo'], highlightthickness=0)

        arredondar(tela, self.LARGURA, self.ALTURA, COR['painel_alto'],
                   COR['borda'], raio=RAIO)

        cor = COR.get(TOM.get(tom, tom), COR['primario'])

        # O NUMERO PRIMEIRO, porque ele manda no espaco: e o que se veio
        # conferir, entao e o texto que nao pode ser cortado. O nome se acomoda
        # no que sobrar.
        fim = self.LARGURA - 14

        if valor is not None:

            numero = tela.create_text(
                fim, self.ALTURA / 2, text=str(valor), anchor='e',
                font=('Segoe UI Semibold', 10), fill=cor)

            fim = tela.bbox(numero)[0] - 10

        tela.create_text(14, self.ALTURA / 2, anchor='w',
                         text=encurtar(titulo, max(40, fim - 14),
                                       FONTE_PEQUENA),
                         font=FONTE_PEQUENA, fill=COR['texto'])

        return tela

    def _arrumar(self):
        """Empilha e reencosta a janela no canto de baixo.

        A JANELA E REDIMENSIONADA A CADA CARTAO, e nao criada no tamanho maximo:
        uma janela alta e quase toda vazia continua sendo uma janela por cima do
        jogo, e as bordas dela aparecem contra qualquer fundo claro."""

        for c in self._cartoes:
            c.pack_forget()

        for c in self._cartoes:
            c.pack(side='top', pady=(0, self.VAO))

        if not self._cartoes:
            self.geometry(f'{self.LARGURA}x1'
                          f'+{self.winfo_screenwidth()}'
                          f'+{self.winfo_screenheight()}')
            return

        altura = len(self._cartoes) * (self.ALTURA + self.VAO)

        x = self.winfo_screenwidth() - self.LARGURA - self.MARGEM
        y = self.winfo_screenheight() - self.RODAPE - altura

        self.geometry(f'{self.LARGURA}x{altura}+{x}+{max(0, y)}')

    #endregion

#endregion

