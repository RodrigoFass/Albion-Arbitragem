################################
#                              #
#          CALIBRADOR          #
#                              #
################################

# Remarca as posicoes de clique e as regioes de leitura, sem editar codigo.
#
# POR QUE EXISTE. Tudo no programa assume o jogo em 1920x1080, em tela cheia, no
# monitor primario. Quem tem 2560x1440, um notebook em 1366x768, ou o jogo em
# janela, simplesmente nao conseguia usar o aplicativo - o selo do cabecalho
# detectava e avisava, oferecendo um diagnostico sem saida. E no dia em que a
# interface do jogo mudar de lugar, remarcar exigiria abrir o coordenadas.py.
#
# COMO FUNCIONA, e por que assim. O calibrador CAPTURA a tela do jogo e deixa
# voce marcar sobre a imagem parada, em vez de desenhar uma camada por cima do
# jogo ao vivo. Tres razoes:
#
#   Uma camada por cima cobre justamente o que se precisa ver, e deixar a camada
#   transparente o bastante para enxergar o jogo deixa a marcacao imprecisa.
#
#   Sobre uma imagem parada da para ampliar. A LUPA mostra os pixels em volta do
#   cursor a 10x, com a coordenada exata - e regiao de OCR se ganha ou se perde
#   por dois pixels: a regiao antiga do preco comecava um pixel abaixo do topo
#   dos digitos, e por isso o OCR lia 6 como 0.
#
#   A imagem capturada e EXATAMENTE o que o bot vai ver. Marcar sobre ela e
#   marcar sobre a verdade.
#
# O que sai daqui e um coordenadas.json ao lado do programa, que sobrescreve as
# constantes do coordenadas.py. O codigo nao muda, e desfazer e apagar o arquivo.
#
#
# NESTA VERSAO ELE E MAIS NECESSARIO AINDA, e por um motivo concreto: das
# coordenadas daqui, boa parte foi DERIVADA - calculada a partir de um print ou
# de outra coordenada - e nao medida na tela. Isso ja custou tres defeitos num
# dia so:
#
#   o recorte do preco comecava 6 px a direita de onde os numeros comecam, e o
#   "5" raspado de 540.000 saia lido como 9;
#
#   a espera do dropdown olhava a linha da barra da cidade dentro do painel do
#   Mercado Negro, e por isso gastava o limite inteiro em toda troca de filtro;
#
#   o ponto de descanso do cursor caiu em cima do filtro de Qualidade.
#
# Nenhum dos tres dava erro. Todos os tres davam numero errado, em silencio - e o
# unico jeito de achar foi olhar o PNG do que o bot capturou. Este calibrador e
# o caminho curto para isso.
#
# Antes de alterar: python -m pyflakes calibrador.py

import base64
import io
import tkinter as tk

from PIL import Image

import comum
import coordenadas as cd
from visual import (COR, FONTE, FONTE_MINIMA, FONTE_PEQUENA, FONTE_ROTULO,
                    Botao, avisar, espacado, perguntar, rotulo)

# Ampliacao da lupa e quantos pixels da tela ela mostra de lado.
LUPA_ZOOM = 10
LUPA_PIXELS = 15


class Calibrador(tk.Toplevel):

    def __init__(self, pai, ao_terminar=None):

        super().__init__(pai, bg=COR['fundo'])

        self._ao_terminar = ao_terminar
        self._valores = {}
        self._grupo = 0
        self._marca = 0

        self._captura = None       # PIL.Image da tela do jogo
        self._instrucao = ''
        self._ultimo_tamanho = None
        self._mostrada = None      # PhotoImage do que esta no canvas
        self._escala = 1.0
        self._arrasto = None

        self.title('Calibrar coordenadas - Albion BM')
        self.geometry('1280x860')
        self.minsize(1000, 700)

        try:
            self.transient(pai)
        except tk.TclError:
            pass

        self._montar()
        self._mostrar_grupo()

        self.protocol('WM_DELETE_WINDOW', self.fechar)

        self.lift()
        self.focus_force()

    # --- estrutura --------------------------------------------------------

    def _montar(self):

        topo = tk.Frame(self, bg=COR['fundo'], padx=22, pady=16)
        topo.pack(fill='x')

        esquerda = tk.Frame(topo, bg=COR['fundo'])
        esquerda.pack(side='left')

        self.titulo = rotulo(esquerda, '', fonte=('Segoe UI Semibold', 15),
                             fundo='fundo')
        self.titulo.pack(anchor='w')

        self.subtitulo = rotulo(esquerda, '', fonte=FONTE_PEQUENA,
                                cor='texto_medio', fundo='fundo', wraplength=760)
        self.subtitulo.pack(anchor='w', pady=(3, 0))

        self.contador = rotulo(topo, '', fonte=FONTE_PEQUENA, cor='texto_fraco',
                               fundo='fundo')
        self.contador.pack(side='right')

        tk.Frame(self, bg=COR['borda'], height=1).pack(fill='x')

        # --- rodape antes do corpo, para ele nao ser empurrado para fora ---
        self._montar_rodape()

        corpo = tk.Frame(self, bg=COR['fundo'], padx=22, pady=16)
        corpo.pack(fill='both', expand=True)

        self.tela = tk.Canvas(corpo, bg=COR['painel'], highlightthickness=1,
                              highlightbackground=COR['borda'], cursor='crosshair')
        self.tela.pack(side='left', fill='both', expand=True)

        self.tela.bind('<Motion>', self._mexeu)
        self.tela.bind('<Button-1>', self._apertou)
        self.tela.bind('<B1-Motion>', self._arrastando)
        self.tela.bind('<ButtonRelease-1>', self._soltou)

        # O canvas so tem tamanho depois de ser desenhado. Sem esperar por isto,
        # o texto de instrucao ia para o centro de uma area de 1x1 - ou seja,
        # para o canto - e a captura era reduzida para caber num tamanho errado.
        self.tela.bind('<Configure>', self._ao_redimensionar)

        # --- lupa ---
        lado = tk.Frame(corpo, bg=COR['fundo'], width=210)
        lado.pack(side='left', fill='y', padx=(16, 0))
        lado.pack_propagate(False)

        rotulo(lado, espacado('LUPA'), fonte=FONTE_ROTULO, cor='texto_fraco',
               fundo='fundo').pack(anchor='w')

        self.lupa = tk.Canvas(lado, width=196, height=196, bg=COR['painel'],
                              highlightthickness=1,
                              highlightbackground=COR['borda'])
        self.lupa.pack(pady=(8, 0))

        self.coordenada = rotulo(lado, '-', fonte=('Consolas', 10),
                                 cor='destaque', fundo='fundo')
        self.coordenada.pack(anchor='w', pady=(10, 0))

        self.dica = rotulo(lado, '', fonte=FONTE_MINIMA, cor='texto_fraco',
                           fundo='fundo', wraplength=196)
        self.dica.pack(anchor='w', pady=(12, 0))

    def _montar_rodape(self):

        tk.Frame(self, bg=COR['borda'], height=1).pack(side='bottom', fill='x')

        rodape = tk.Frame(self, bg=COR['fundo'], padx=22, pady=14)
        rodape.pack(side='bottom', fill='x')

        self.estado = rotulo(rodape, '', fonte=FONTE_PEQUENA, cor='texto_fraco',
                             fundo='fundo')
        self.estado.pack(side='left')

        Botao(rodape, 'Fechar', self.fechar, largura=10,
              fundo_pai='fundo').pack(side='right')

        self.botao_salvar = Botao(rodape, 'Gravar', self.gravar, tipo='destaque',
                                  largura=12, fundo_pai='fundo')
        self.botao_salvar.pack(side='right', padx=(10, 10))

        self.botao_proximo = Botao(rodape, 'Pular grupo', self.proximo_grupo,
                                   largura=12, fundo_pai='fundo')
        self.botao_proximo.pack(side='right')

        self.botao_refazer = Botao(rodape, 'Refazer marca', self.refazer,
                                   largura=13, fundo_pai='fundo')
        self.botao_refazer.pack(side='right', padx=(0, 10))

        self.botao_capturar = Botao(rodape, 'Capturar a tela', self.capturar,
                                    tipo='destaque', largura=16, fundo_pai='fundo')
        self.botao_capturar.pack(side='left', padx=(24, 0))

    # --- passos -----------------------------------------------------------

    def _grupo_atual(self):
        return cd.PASSOS[self._grupo] if self._grupo < len(cd.PASSOS) else None

    def _marca_atual(self):

        grupo = self._grupo_atual()

        if grupo is None or self._marca >= len(grupo['marcas']):
            return None

        return grupo['marcas'][self._marca]

    def _mostrar_grupo(self):

        grupo = self._grupo_atual()

        if grupo is None:
            self._terminou()
            return

        self.titulo.config(text=f'{self._grupo + 1}. {grupo["titulo"]}')
        self.subtitulo.config(text=grupo['preparo'])

        self._captura = None
        self.tela.delete('all')
        self._instrucao_na_tela('Deixe o jogo na tela descrita acima e clique '
                                'em "Capturar a tela".')

        self._atualizar_contador()
        self._atualizar_marca()

    def _ao_redimensionar(self, evento=None):
        """Redesenha o conteudo no tamanho novo do canvas."""

        # ignora as trocas minusculas, senao redesenhar dispara outro Configure
        tamanho = (self.tela.winfo_width(), self.tela.winfo_height())

        if tamanho == getattr(self, '_ultimo_tamanho', None):
            return

        self._ultimo_tamanho = tamanho

        if self._captura is not None:
            self._desenhar()
        else:
            self._instrucao_na_tela(self._instrucao)

    def _instrucao_na_tela(self, texto):

        self._instrucao = texto

        self.tela.delete('all')

        largura = self.tela.winfo_width()
        altura = self.tela.winfo_height()

        if largura < 50 or altura < 50:
            return   # ainda nao foi desenhado; o <Configure> chama de novo

        self.tela.create_text(largura // 2, altura // 2, text=texto,
                              fill=COR['texto_fraco'], font=FONTE,
                              width=largura - 120, justify='center')

    def _atualizar_contador(self):

        feitas = len([n for n in self._valores if not n.startswith('_')])

        self.contador.config(
            text=f'grupo {self._grupo + 1} de {len(cd.PASSOS)}   -   '
                 f'{feitas} marcas feitas')

    def _atualizar_marca(self):

        marca = self._marca_atual()

        if marca is None:
            self.estado.config(
                text='Grupo terminado. "Pular grupo" leva ao proximo.',
                fg=COR['ok'])
            self.dica.config(text='')
            return

        tipo = {'ponto': 'Clique em', 'regiao': 'Arraste um retangulo em volta de',
                'altura': 'Clique na altura de'}[marca['tipo']]

        self.estado.config(text=f'{tipo}: {marca["o_que"]}', fg=COR['destaque'])
        self.dica.config(text=marca.get('dica', ''))

    # --- captura ----------------------------------------------------------

    def capturar(self):
        """Some da tela, fotografa, e volta.

        withdraw() e nao iconify(): esta janela e transient da principal, e o Tk
        RECUSA minimizar uma transient - "can't iconify: it is a transient". A
        excecao morria dentro do callback do botao, entao clicar em Capturar nao
        fazia absolutamente nada, sem nenhum erro a vista.

        A janela principal tambem sai da frente. Ela fica atras desta, e o que
        precisa aparecer na foto e o jogo."""

        self._escondidas = []

        for janela in (self, self.master):
            try:
                if janela is not None and janela.winfo_viewable():
                    janela.withdraw()
                    self._escondidas.append(janela)
            except tk.TclError:
                pass

        self.update()

        # tempo para o Windows redesenhar o que estava atras
        self.after(500, self._capturar_de_fato)

    def _mostrar_de_volta(self):

        # ordem inversa: a principal primeiro, o calibrador por cima
        for janela in reversed(getattr(self, '_escondidas', [])):
            try:
                janela.deiconify()
            except tk.TclError:
                pass

        self._escondidas = []

        try:
            self.lift()
            self.focus_force()
        except tk.TclError:
            pass

    def _capturar_de_fato(self):

        erro = None

        try:
            largura = self.winfo_screenwidth()
            altura = self.winfo_screenheight()

            self._captura = comum.capturar((0, 0, largura, altura))

        except Exception as e:
            erro = e

        # a janela volta ACONTECA O QUE ACONTECER - deixa-la escondida por causa
        # de uma falha de captura seria perder o programa de vista
        self._mostrar_de_volta()

        if erro is not None:
            avisar(self, 'Captura', f'Nao deu para capturar a tela: {erro}',
                   tipo='perigo')
            return

        self._desenhar()
        self._atualizar_marca()

    def _desenhar(self):
        """Poe a captura no canvas, reduzida para caber."""

        if self._captura is None:
            return

        self.tela.update_idletasks()

        largura = max(self.tela.winfo_width() - 4, 200)
        altura = max(self.tela.winfo_height() - 4, 150)

        self._escala = min(largura / self._captura.width,
                           altura / self._captura.height, 1.0)

        vista = self._captura.resize(
            (max(1, int(self._captura.width * self._escala)),
             max(1, int(self._captura.height * self._escala))),
            Image.LANCZOS)

        dados = io.BytesIO()
        vista.save(dados, 'PNG')

        self._mostrada = tk.PhotoImage(data=base64.b64encode(dados.getvalue()))

        self.tela.delete('all')
        self.tela.create_image(0, 0, image=self._mostrada, anchor='nw')

        self._ultimo_tamanho = (self.tela.winfo_width(), self.tela.winfo_height())

        self._redesenhar_marcas()

    def _redesenhar_marcas(self):
        """Mostra o que ja foi marcado NESTE grupo, sobre a captura."""

        self.tela.delete('marca')

        grupo = self._grupo_atual()

        if grupo is None:
            return

        for m in grupo['marcas'][:self._marca]:

            valor = self._valores.get(m['nome'])

            if valor is None:
                continue

            if m['tipo'] == 'ponto':
                x, y = valor['x'] * self._escala, valor['y'] * self._escala
                self.tela.create_line(x - 9, y, x + 9, y, fill=COR['destaque'],
                                      width=1, tags='marca')
                self.tela.create_line(x, y - 9, x, y + 9, fill=COR['destaque'],
                                      width=1, tags='marca')

            elif m['tipo'] == 'regiao':
                x1, y1, x2, y2 = (v * self._escala for v in valor)
                self.tela.create_rectangle(x1, y1, x2, y2, outline=COR['destaque'],
                                           width=2, tags='marca')

            else:
                y = valor * self._escala
                self.tela.create_line(0, y, 4000, y, fill=COR['destaque'],
                                      width=1, dash=(4, 3), tags='marca')

    # --- mouse ------------------------------------------------------------

    def _na_tela(self, evento):
        """Coordenada na TELA REAL, a partir do ponto no canvas."""

        return (int(round(self.tela.canvasx(evento.x) / self._escala)),
                int(round(self.tela.canvasy(evento.y) / self._escala)))

    def _mexeu(self, evento):

        if self._captura is None:
            return

        x, y = self._na_tela(evento)

        self.coordenada.config(text=f'{x}, {y}')
        self._pintar_lupa(x, y)

    def _pintar_lupa(self, x, y):
        """Os pixels em volta do cursor, ampliados.

        Regiao de OCR se ganha ou se perde por dois pixels - sem lupa, marcar
        sobre uma imagem reduzida seria adivinhar."""

        meio = LUPA_PIXELS // 2

        caixa = (x - meio, y - meio, x + meio + 1, y + meio + 1)

        pedaco = self._captura.crop(caixa)
        pedaco = pedaco.resize((LUPA_PIXELS * LUPA_ZOOM, LUPA_PIXELS * LUPA_ZOOM),
                               Image.NEAREST)

        dados = io.BytesIO()
        pedaco.save(dados, 'PNG')

        self._lupa_img = tk.PhotoImage(data=base64.b64encode(dados.getvalue()))

        self.lupa.delete('all')
        self.lupa.create_image(0, 0, image=self._lupa_img, anchor='nw')

        centro = meio * LUPA_ZOOM

        self.lupa.create_rectangle(centro, centro, centro + LUPA_ZOOM,
                                   centro + LUPA_ZOOM, outline=COR['destaque'],
                                   width=2)

    def _apertou(self, evento):

        if self._captura is None or self._marca_atual() is None:
            return

        marca = self._marca_atual()

        if marca['tipo'] == 'regiao':
            self._arrasto = self._na_tela(evento)
            return

        x, y = self._na_tela(evento)

        self._guardar(marca, {'x': x, 'y': y} if marca['tipo'] == 'ponto' else y)

    def _arrastando(self, evento):

        if self._arrasto is None:
            return

        x1, y1 = self._arrasto
        x2, y2 = self._na_tela(evento)

        self.tela.delete('arrastando')
        self.tela.create_rectangle(
            x1 * self._escala, y1 * self._escala,
            x2 * self._escala, y2 * self._escala,
            outline=COR['destaque'], width=2, tags='arrastando')

        self.coordenada.config(text=f'{abs(x2-x1)} x {abs(y2-y1)} px')

    def _soltou(self, evento):

        if self._arrasto is None:
            return

        x1, y1 = self._arrasto
        x2, y2 = self._na_tela(evento)

        self._arrasto = None
        self.tela.delete('arrastando')

        if abs(x2 - x1) < 4 or abs(y2 - y1) < 4:
            self.estado.config(text='Retangulo pequeno demais - arraste de novo.',
                               fg=COR['aviso'])
            return

        self._guardar(self._marca_atual(),
                      (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))

    def _guardar(self, marca, valor):

        self._valores[marca['nome']] = valor

        self._marca += 1

        self._redesenhar_marcas()
        self._atualizar_contador()
        self._atualizar_marca()

        if self._marca_atual() is None:
            self._fechar_grupo()

    def _fechar_grupo(self):
        """Calcula os derivados do grupo e passa para o proximo."""

        grupo = self._grupo_atual()

        for nome, conta in grupo.get('derivados', []):
            try:
                self._valores[nome] = int(conta(self._valores))
            except Exception:
                pass

        self.estado.config(
            text=f'"{grupo["titulo"]}" pronto. Va para o proximo.', fg=COR['ok'])

    # --- navegacao --------------------------------------------------------

    def refazer(self):

        if self._marca > 0:
            self._marca -= 1
            marca = self._grupo_atual()['marcas'][self._marca]
            self._valores.pop(marca['nome'], None)
            self._redesenhar_marcas()
            self._atualizar_contador()
            self._atualizar_marca()

    def proximo_grupo(self):

        self._grupo += 1
        self._marca = 0
        self._mostrar_grupo()

    def _terminou(self):

        self.titulo.config(text='Marcacao terminada')
        self.subtitulo.config(
            text='Clique em Gravar para escrever o coordenadas.json. O que voce '
                 'nao marcou continua com o valor de fabrica.')
        self.tela.delete('all')
        self._instrucao_na_tela('Nada mais a marcar.')
        self.estado.config(text='', fg=COR['texto_fraco'])
        self._atualizar_contador()

    # --- saida ------------------------------------------------------------

    def gravar(self):

        feitas = {n: v for n, v in self._valores.items() if not n.startswith('_')}

        if not feitas:
            avisar(self, 'Gravar', 'Nada foi marcado ainda.', tipo='aviso')
            return

        if not perguntar(
                self, 'Gravar coordenadas',
                f'{len(feitas)} coordenadas serao gravadas em coordenadas.json, '
                f'ao lado do programa.\n\nO que voce nao marcou continua com o '
                f'valor de fabrica. Para desfazer tudo, apague esse arquivo.\n\n'
                f'DEPOIS DE GRAVAR, rode uma vez em Simular antes de usar '
                f'qualquer modo que mexa com prata: uma coordenada errada num bot '
                f'de compra e uma compra errada.',
                sim='Gravar', nao='Cancelar'):
            return

        try:
            trocadas = cd.salvar_perfil(self._valores)
        except Exception as e:
            avisar(self, 'Gravar', f'Nao deu para gravar: {e}', tipo='perigo')
            return

        # aplica ja, sem precisar reabrir o programa
        cd.carregar_perfil()

        avisar(self, 'Gravado',
               f'{len(trocadas)} coordenadas gravadas em coordenadas.json.\n\n'
               f'Ja valem na proxima execucao - cada bot recarrega as posicoes ao '
               f'comecar, entao nao precisa reabrir o programa.\n\n'
               f'Rode uma vez em Simular antes de qualquer modo que mexa com '
               f'prata.')

        if self._ao_terminar:
            self._ao_terminar(trocadas)

        self.destroy()

    def fechar(self):

        feitas = [n for n in self._valores if not n.startswith('_')]

        if feitas and not perguntar(
                self, 'Fechar',
                f'{len(feitas)} marcas ainda nao foram gravadas.\n\n'
                f'Fechar agora descarta tudo.',
                tipo='aviso', sim='Descartar', nao='Continuar'):
            return

        self.destroy()


def abrir(pai, ao_terminar=None):
    """Abre o calibrador, ou traz para frente o que ja estiver aberto."""

    for filho in pai.winfo_children():
        if isinstance(filho, Calibrador):
            filho.lift()
            filho.focus_force()
            return filho

    return Calibrador(pai, ao_terminar)
