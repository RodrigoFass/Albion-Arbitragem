################################
#                              #
#          APLICATIVO          #
#                              #
################################

# A casca: cabecalho, lateral, area de conteudo, barra de operacao e rodape.
# As cinco telas vivem em arquivos proprios e so recebem daqui um lugar para
# desenhar e um jeito de rodar coisa demorada sem congelar a interface.
#
#
# O ARRANJO. Quatro faixas horizontais fixas e uma que aparece:
#
#     cabecalho    48 px   marca, nome, e as acoes que valem em qualquer tela
#     operacao     36 px   SO ENQUANTO ALGO RODA - progresso, item atual, parar
#     corpo               lateral + tela
#     rodape       28 px   estado, sem nenhum controle
#
# A BARRA DE OPERACAO E O QUE MUDOU MAIS. Antes o botao Parar e a barra de
# progresso moravam no rodape o tempo todo, apagados 99% do tempo - um controle
# morto ocupando lugar permanente. Agora a faixa nasce quando um bot comeca e
# some quando ele termina, e enquanto existe ela e a coisa mais visivel da tela,
# que e exatamente o que ela deveria ser.
#
#
# NADA QUE TOCA NO JOGO RODA NA THREAD DA INTERFACE. Uma varredura leva dezenas
# de minutos; feita aqui, a janela ficaria branca e o Windows a marcaria como
# travada - e o F12 nao seria atendido, porque quem atende e o mesmo laco que
# estaria ocupado.
#
# Por isso o rodar() poe a funcao numa thread e liga a saida do comum.relatar()
# numa fila. O log so e escrito pela thread da interface, drenando essa fila: o
# Tk nao e seguro entre threads, e escrever no Text de fora trava a janela de
# formas que so aparecem depois de meia hora rodando.
#
#     python app.py
#
# Antes de alterar: python -m pyflakes app.py

import queue
import threading
import tkinter as tk
from tkinter import ttk

import ajustes
import catalogo
import comum
import mercado
import visual
from visual import COR

import tela_painel
import tela_itens
import tela_conferir
import tela_comprar
import tela_vender
import tela_ajustes

TITULO = 'Albion Arbitragem'

TELAS = (
    ('painel',   '📊', 'Painel',   tela_painel),
    ('itens',    '📦', 'Itens',    tela_itens),
    ('conferir', '🔍', 'Conferir', tela_conferir),
    ('comprar',  '🛒', 'Comprar',  tela_comprar),
    ('vender',   '🏷️', 'Vender',   tela_vender),
    ('ajustes',  '⚙️', 'Ajustes',  tela_ajustes),
)

ALTURA_OPERACAO = 38


class Aplicativo:

    def __init__(self, raiz):

        # O QUE FOI SALVO TEM QUE VOLTAR. Sem isto o catalogo nasce vazio a cada
        # abertura, e a hora de descobrir isso e depois de escolher cem itens.
        self._erro_ao_abrir = None

        for carregar, nome in ((catalogo.carregar, 'catalogo'),
                               (ajustes.carregar, 'ajustes'),
                               (mercado.carregar, 'precos')):
            ok, erro = carregar()
            if not ok:
                self._erro_ao_abrir = f'{nome}: {erro}'

        visual.aplicar_tema(ajustes.atuais().get('tema', 'escuro'))

        self.raiz = raiz
        self.fila = queue.Queue()
        self.rodando = None
        self.faixa = None
        self.avisos = None
        self.telas = {}
        self.botoes = {}
        self.atual = None
        self.lateral_aberta = True

        self._montar_janela()
        self._montar_cabecalho()
        self._montar_rodape()
        self._montar_operacao()
        self._montar_corpo()

        for chave, _, _, modulo in TELAS:
            quadro = tk.Frame(self.area, bg=COR['fundo'])
            self.telas[chave] = modulo.Tela(quadro, self)

        self.trocar('itens')

        self._drenagem = self.raiz.after(80, self._drenar)
        self.raiz.after(120, self.atualizar_rodape)

        if self._erro_ao_abrir:
            self.escrever(f'ATENCAO ao abrir - {self._erro_ao_abrir}')

    #region Janela

    def _montar_janela(self):

        self.raiz.title(TITULO)
        self.raiz.configure(bg=COR['fundo'])
        self.raiz.minsize(1060, 700)
        self.raiz.geometry('1260x820')

        estilo = ttk.Style()

        try:
            estilo.theme_use('clam')
        except tk.TclError:
            pass

        visual.estilos(estilo)

        self.raiz.protocol('WM_DELETE_WINDOW', self.fechar)

    def _montar_cabecalho(self):
        """A faixa de cima: marca a esquerda, titulo da janela, atalhos.

        A MARCA OCUPA A LARGURA DA LATERAL, e nao um canto qualquer. Assim ela
        fica alinhada com a coluna de navegacao que comeca logo abaixo, e as duas
        leem como uma peca so - que e o que faz a tela do bot de referencia
        parecer montada, e nao empilhada."""

        topo = tk.Frame(self.raiz, bg=COR['rodape'],
                        height=visual.ALTURA_CABECALHO)
        topo.pack(fill='x')
        topo.pack_propagate(False)

        marca = tk.Frame(topo, bg=COR['rodape'],
                         width=visual.LARGURA_LATERAL)
        marca.pack(side='left', fill='y')
        marca.pack_propagate(False)

        visual.Marca(marca, lado=28, fundo='rodape').pack(
            side='left', padx=(visual.ESPACO_M, 10))

        letras = tk.Frame(marca, bg=COR['rodape'])
        letras.pack(side='left', anchor='w')

        visual.rotulo(letras, 'Albion', ('Segoe UI Semibold', 13),
                      cor='texto_forte', fundo='rodape').pack(anchor='w')

        visual.rotulo(letras, 'arbitragem que se paga', visual.FONTE_MINIMA,
                      cor='texto_fraco', fundo='rodape').pack(anchor='w')

        visual.rotulo(topo, TITULO, visual.FONTE, cor='texto',
                      fundo='rodape').pack(side='left', padx=visual.ESPACO_M)

        self.log_botao = visual.Botao(topo, 'Andamento', self.alternar_log,
                                      largura=12, fundo_pai='rodape',
                                      emoji='>_')
        self.log_botao.pack(side='right', padx=visual.ESPACO_M)

    def _montar_operacao(self):
        """A faixa que so existe enquanto algo roda."""

        self.operacao = tk.Frame(self.raiz, bg=COR['primario_fundo'],
                                 height=ALTURA_OPERACAO)
        self.operacao.pack_propagate(False)

        self.barra = tk.Canvas(self.operacao, height=3,
                               bg=COR['primario_fundo'], highlightthickness=0,
                               bd=0)
        self.barra.pack(side='bottom', fill='x')

        self.andamento = visual.rotulo(self.operacao, '', visual.FONTE_PEQUENA,
                                       cor='texto_forte',
                                       fundo='primario_fundo')
        self.andamento.pack(side='left', padx=visual.ESPACO_G)

        self.parar_botao = visual.Botao(self.operacao, 'Parar (F12)',
                                        self.parar, tipo='perigo', largura=12,
                                        fundo_pai='primario_fundo')
        self.parar_botao.pack(side='right', padx=visual.ESPACO_M, pady=3)
        self.parar_botao.habilitar(False)

    def _montar_rodape(self):

        pe = tk.Frame(self.raiz, bg=COR['rodape'], height=visual.ALTURA_RODAPE)
        pe.pack(side='bottom', fill='x')
        pe.pack_propagate(False)

        self.estado = visual.rotulo(pe, '', visual.FONTE_MINIMA,
                                    cor='texto_fraco', fundo='rodape')
        self.estado.pack(side='left', padx=visual.ESPACO_M)

        visual.rotulo(pe, f'v{comum.VERSAO}', visual.FONTE_MINIMA,
                      cor='texto_fraco', fundo='rodape').pack(
                          side='right', padx=visual.ESPACO_M)

        visual.rotulo(pe, 'Rodrigo', visual.FONTE_MINIMA, cor='texto_fraco',
                      fundo='rodape').pack(side='right')

    def _montar_corpo(self):

        corpo = tk.Frame(self.raiz, bg=COR['fundo'])
        corpo.pack(fill='both', expand=True)

        self._montar_lateral(corpo)

        direita = tk.Frame(corpo, bg=COR['fundo'])
        direita.pack(side='left', fill='both', expand=True)

        self.divisa = tk.PanedWindow(direita, orient='vertical',
                                     bg=COR['fundo'], sashwidth=4,
                                     sashrelief='flat', bd=0)
        self.divisa.pack(fill='both', expand=True)

        self.area = tk.Frame(self.divisa, bg=COR['fundo'])
        self.divisa.add(self.area, minsize=320, stretch='always')

        self._montar_log()

    def _montar_lateral(self, pai):

        self.lateral = tk.Frame(pai, bg=COR['rodape'],
                                width=visual.LARGURA_LATERAL)
        self.lateral.pack(side='left', fill='y')
        self.lateral.pack_propagate(False)

        recolher = tk.Frame(self.lateral, bg=COR['rodape'], cursor='hand2')
        recolher.pack(fill='x', pady=(ESPACO := visual.ESPACO, 0))

        self.recolher_icone = visual.rotulo(recolher, '☰',
                                            ('Segoe UI', 12),
                                            cor='texto_fraco', fundo='rodape')
        self.recolher_icone.pack(side='left', padx=(18, 0), pady=ESPACO)

        self.recolher_texto = visual.rotulo(recolher, 'Recolher',
                                            visual.FONTE_PEQUENA,
                                            cor='texto_fraco', fundo='rodape')
        self.recolher_texto.pack(side='left', padx=10)

        for alvo in (recolher, self.recolher_icone, self.recolher_texto):
            alvo.bind('<Button-1>', lambda _e: self.alternar_lateral())

        tk.Frame(self.lateral, bg=COR['borda'], height=1).pack(
            fill='x', pady=(ESPACO, ESPACO))

        for chave, emoji, nome, _ in TELAS:

            linha = tk.Frame(self.lateral, bg=COR['rodape'], cursor='hand2')
            linha.pack(fill='x')

            faixa = tk.Frame(linha, bg=COR['rodape'], width=3)
            faixa.pack(side='left', fill='y')

            icone = visual.rotulo(linha, emoji, ('Segoe UI Emoji', 13),
                                  fundo='rodape')
            icone.pack(side='left', padx=(15, 0), pady=11)

            titulo = visual.rotulo(linha, nome, visual.FONTE, cor='texto',
                                   fundo='rodape')
            titulo.pack(side='left', padx=10)

            self.botoes[chave] = (linha, faixa, icone, titulo)

            for alvo in (linha, icone, titulo):
                alvo.bind('<Button-1>', lambda _e, c=chave: self.trocar(c))

    def alternar_lateral(self):
        """Recolhe a lateral para so os icones.

        Numa tela de 1260 px, 220 deles em nomes que voce ja decorou sao 220 px
        que a tabela de compras nao tem."""

        self.lateral_aberta = not self.lateral_aberta

        largura = (visual.LARGURA_LATERAL if self.lateral_aberta
                   else visual.LARGURA_LATERAL_FECHADA)

        self.lateral.config(width=largura)

        for _, _, _, titulo in self.botoes.values():
            if self.lateral_aberta:
                titulo.pack(side='left', padx=10)
            else:
                titulo.pack_forget()

        if self.lateral_aberta:
            self.recolher_texto.pack(side='left', padx=10)
        else:
            self.recolher_texto.pack_forget()

    #endregion

    #region Log

    def _montar_log(self):

        caixa = tk.Frame(self.divisa, bg=COR['painel'])
        self.caixa_log = caixa
        self.log_visivel = False
        self.log_novo = 0

        barra = tk.Frame(caixa, bg=COR['painel_alto'], height=28)
        barra.pack(fill='x')
        barra.pack_propagate(False)

        visual.rotulo(barra, 'ANDAMENTO', visual.FONTE_ROTULO,
                      cor='texto_fraco', fundo='painel_alto').pack(
                          side='left', padx=visual.ESPACO_M)

        visual.Botao(barra, 'Fechar', self.alternar_log, largura=7,
                     fundo_pai='painel_alto').pack(side='right', padx=6, pady=1)

        visual.Botao(barra, 'Limpar', self.limpar_log, largura=7,
                     fundo_pai='painel_alto').pack(side='right', pady=1)

        moldura = tk.Frame(caixa, bg=COR['painel'])
        moldura.pack(fill='both', expand=True)

        rolagem = ttk.Scrollbar(moldura, orient='vertical',
                                style='Fina.Vertical.TScrollbar')
        rolagem.pack(side='right', fill='y')

        self.log = tk.Text(moldura, bg=COR['painel'], fg=COR['texto'],
                           font=visual.FONTE_LOG, bd=0, highlightthickness=0,
                           wrap='none', state='disabled',
                           yscrollcommand=rolagem.set)
        self.log.pack(fill='both', expand=True, padx=(visual.ESPACO_M, 0),
                      pady=6)
        rolagem.config(command=self.log.yview)

        for nome, cor in (('ok', 'ok'), ('aviso', 'aviso'), ('erro', 'perigo'),
                          ('forte', 'texto_forte'), ('fraco', 'texto_fraco')):
            self.log.tag_config(nome, foreground=COR[cor])

    def alternar_log(self):

        if self.log_visivel:
            self.divisa.forget(self.caixa_log)
            self.log_visivel = False
        else:
            self.divisa.add(self.caixa_log, minsize=120, stretch='never')
            self.log_visivel = True
            self.log_novo = 0
            self.raiz.after(30, self._ajustar_divisor)

        self._pintar_botao_do_log()

    def _ajustar_divisor(self):

        altura = self.divisa.winfo_height()

        if altura > 300:
            try:
                self.divisa.sash_place(0, 0, altura - 190)
            except tk.TclError:
                pass

    def _pintar_botao_do_log(self):
        """O botao avisa que ha coisa nova la dentro.

        Sem isso, esconder o log esconde tambem que alguma coisa aconteceu - e o
        aviso mais importante do programa e justamente o que voce nao esperava.
        """

        if self.log_novo and not self.log_visivel:
            self.log_botao.trocar_texto(f'>_  Andamento ({self.log_novo})')
        else:
            self.log_botao.trocar_texto('>_  Andamento')

    def escrever(self, texto=''):

        if not self.log_visivel:
            self.log_novo += 1
            self._pintar_botao_do_log()

        etiqueta = ''
        limpo = texto.strip()

        if limpo.startswith(('ERRO', 'ABORTADO', 'PARANDO', 'RECUSADO')):
            etiqueta = 'erro'
        elif limpo.startswith(('ATENCAO', 'PULADO', '>>>', 'SEM ',
                               'DESCARTADO')):
            etiqueta = 'aviso'
        elif limpo.startswith('['):
            etiqueta = 'forte'
        elif texto.startswith('  '):
            etiqueta = 'fraco'

        self.log.config(state='normal')
        self.log.insert('end', texto + '\n', etiqueta)
        self.log.see('end')
        self.log.config(state='disabled')

    def limpar_log(self):
        self.log.config(state='normal')
        self.log.delete('1.0', 'end')
        self.log.config(state='disabled')
        self.log_novo = 0
        self._pintar_botao_do_log()

    #endregion

    #region Telas

    def trocar(self, chave):

        for c, (linha, faixa, icone, titulo) in self.botoes.items():

            ligado = c == chave
            fundo = COR['painel'] if ligado else COR['rodape']

            linha.config(bg=fundo)
            icone.config(bg=fundo)
            titulo.config(bg=fundo,
                          fg=COR['texto_forte'] if ligado else COR['texto'])
            faixa.config(bg=COR['marca'] if ligado else COR['rodape'])

        for tela in self.telas.values():
            tela.quadro.pack_forget()

        self.atual = chave
        tela = self.telas[chave]
        tela.quadro.pack(fill='both', expand=True)
        tela.ao_mostrar()

    def avisar_telas(self):
        """Diz a todas as telas que o catalogo ou os precos mudaram."""

        for chave, tela in self.telas.items():
            if chave != self.atual:
                tela.precisa_atualizar = True
            else:
                tela.ao_mostrar()

        self.atualizar_rodape()

    def atualizar_rodape(self):
        """O estado do programa em uma linha, sem nenhum controle."""

        try:
            r = catalogo.resumo()
            precos = mercado.quantidade()
            lidos = len(mercado.mercados_lidos())

            self.estado.config(
                text=f'catálogo "{catalogo.nome_atual()}"  ·  {r["itens"]} itens '
                     f'em {r["grupos"]} grupos  ·  {precos} preços de '
                     f'{lidos} mercado(s)')
        except Exception:
            self.estado.config(text='')

    #endregion

    #region Rodar coisa demorada

    def rodar(self, funcao, rotulo='', ao_terminar=None, exigir_jogo=True):
        """Poe <funcao> numa thread, com a saida indo para o log."""

        if self.rodando:
            visual.avisar(self.raiz, 'Um de cada vez',
                          'Já há uma operação em andamento. Espere ela '
                          'terminar, ou pare com F12.', tipo='aviso')
            return False

        if exigir_jogo and not self._preparar_o_jogo():
            return False

        comum.limpar_sinais()
        comum.zerar_contadores()
        comum.instalar_teclas()

        comum.definir_destino(self._do_bot)
        comum.definir_progresso(self._progresso_do_bot)
        comum.definir_aviso(self._aviso_do_bot)

        if ajustes.atuais()['faixa']:
            try:
                self.faixa = visual.Faixa(self.raiz)
            except Exception:
                self.faixa = None

        if ajustes.atuais()['avisos']:
            try:
                self.avisos = visual.Avisos(self.raiz)
            except Exception:
                self.avisos = None

        self.rodando = rotulo or 'operacao'
        self.andamento.config(text=rotulo or 'rodando...')
        self.operacao.pack(fill='x', after=self.raiz.winfo_children()[0])
        self.parar_botao.habilitar(True)

        def alvo():
            try:
                funcao()
            except comum.Abortado:
                comum.relatar('')
                comum.relatar('>>> parado <<<')
            except Exception as e:
                comum.relatar(f'ERRO: {e}')
            finally:
                self.fila.put(('fim', ao_terminar))

        threading.Thread(target=alvo, daemon=True).start()

        return True

    def _preparar_o_jogo(self):
        """Confere o ambiente e TRAZ O JOGO PARA FRENTE. True se da para comecar.

        Aqui morava um problema que so aparece usando: para clicar em "Começar",
        esta janela precisa estar na frente - e nesse instante o jogo, por
        definicao, nao esta. Exigir o jogo em primeiro plano ANTES do clique e
        pedir uma coisa impossivel.

        Entao a ordem se inverte: confere o que da para conferir com o app na
        frente e so DEPOIS pede o foco para o jogo."""

        problemas = comum.verificar_ambiente(exigir_foco=False)

        if problemas:

            texto = '\n'.join(f'- {p}' for p in problemas)

            if not visual.perguntar(
                    self.raiz, 'O jogo não está pronto',
                    f'{texto}\n\nQuer tentar mesmo assim?',
                    tipo='aviso', sim='Tentar'):
                return False

        if ajustes.atuais()['focar_jogo'] and not comum.focar_jogo():
            visual.avisar(
                self.raiz, 'Não achei o jogo',
                'Não consegui trazer a janela do Albion para frente.\n\n'
                'Abra o jogo em tela cheia e tente de novo.', tipo='aviso')
            return False

        if ajustes.atuais()['minimizar']:
            self.raiz.iconify()

        return True

    def parar(self):
        comum.parada_pedida.set()
        self.andamento.config(text='parando ao terminar o item...')

    def _do_bot(self, texto):
        self.fila.put(('linha', texto))

    def _progresso_do_bot(self, feito, total, rotulo):
        self.fila.put(('progresso', (feito, total, rotulo)))

    def _aviso_do_bot(self, titulo, valor, tom):
        self.fila.put(('aviso', (titulo, valor, tom)))

    def _drenar(self):
        """Tira da fila o que a thread do bot deixou. Roda na thread da tela."""

        try:
            while True:

                tipo, dado = self.fila.get_nowait()

                if tipo == 'linha':
                    self.escrever(dado)
                elif tipo == 'progresso':
                    self._pintar(*dado)
                elif tipo == 'aviso':
                    self._avisar_no_canto(*dado)
                elif tipo == 'fim':
                    self._terminou(dado)

        except queue.Empty:
            pass

        self._drenagem = self.raiz.after(80, self._drenar)

    def _avisar_no_canto(self, titulo, valor, tom):
        """Mais um cartao no canto de baixo, por cima do jogo.

        UM ERRO AQUI NAO PODE DERRUBAR A VARREDURA. Se a janelinha de aviso
        morrer - e ela vive por cima de um jogo em tela cheia, que a qualquer
        momento pode ser trocado de resolucao - o bot continua, sem ela."""

        if self.avisos is None:
            return

        try:
            self.avisos.mostrar(titulo, valor, tom)
        except Exception:
            self.avisos = None

    def _terminou(self, ao_terminar):

        comum.definir_destino(None)
        comum.definir_progresso(None)
        comum.definir_aviso(None)
        comum.parar_teclas()

        for canto in ('faixa', 'avisos'):

            janela = getattr(self, canto)

            if janela is not None:
                try:
                    janela.destroy()
                except Exception:
                    pass
                setattr(self, canto, None)

        self.rodando = None
        self.operacao.pack_forget()
        self.parar_botao.habilitar(False)
        self.barra.delete('all')

        try:
            self.raiz.deiconify()
            self.raiz.lift()
        except tk.TclError:
            pass

        if ajustes.atuais()['avisar_no_fim']:
            self._avisar_que_terminou()

        if ao_terminar:
            try:
                ao_terminar()
            except Exception as e:
                self.escrever(f'ERRO ao atualizar a tela: {e}')

        self.atualizar_rodape()

    def _pintar(self, feito, total, rotulo):

        self.andamento.config(
            text=f'{rotulo}      {feito} de {total}' if total else rotulo)

        self.barra.delete('all')

        if not total:
            return

        largura = self.barra.winfo_width() or 1
        self.barra.create_rectangle(0, 0, largura * feito / total, 3,
                                    fill=COR['primario'], width=0)

        if self.faixa is not None:
            try:
                self.faixa.atualizar(rotulo, f'{feito}/{total}')
            except Exception:
                self.faixa = None

    def _avisar_que_terminou(self):
        """Um apito e o botao piscando na barra de tarefas.

        NAO traz a janela para frente: se voce estiver no meio de outra coisa,
        uma janela pulando na sua frente e pior que um aviso discreto."""

        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception:
            pass

        try:
            import ctypes

            class FLASHWINFO(ctypes.Structure):
                _fields_ = [('cbSize', ctypes.c_uint),
                            ('hwnd', ctypes.c_void_p),
                            ('dwFlags', ctypes.c_uint),
                            ('uCount', ctypes.c_uint),
                            ('dwTimeout', ctypes.c_uint)]

            hwnd = ctypes.windll.user32.GetParent(self.raiz.winfo_id())

            info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, 0x03 | 0x0C, 0, 0)

            ctypes.windll.user32.FlashWindowEx(ctypes.byref(info))

        except Exception:
            pass

    #endregion

    def remontar(self, nome_do_tema):
        """Troca a paleta e reconstroi a janela inteira.

        O Tk nao observa nada: um widget desenhado com a cor antiga fica com ela
        para sempre, e nao existe "repintar tudo". Trocar de tema de verdade e
        construir de novo - o que so e barato porque a janela nasce de codigo, e
        nada aqui guarda estado que nao esteja no disco."""

        if self.rodando:
            visual.avisar(self.raiz, 'Agora não',
                          'Espere a operação terminar para trocar de tema.',
                          tipo='aviso')
            return

        ajustes.definir('tema', nome_do_tema)

        visual.aplicar_tema(nome_do_tema)
        visual.estilos(ttk.Style())

        if getattr(self, '_drenagem', None):
            try:
                self.raiz.after_cancel(self._drenagem)
            except Exception:
                pass

        for filho in self.raiz.winfo_children():
            filho.destroy()

        volta_para = self.atual

        self.__init__(self.raiz)
        self.trocar(volta_para)

    def fechar(self):

        if self.rodando:
            if not visual.perguntar(self.raiz, 'Sair agora?',
                                    'Há uma operação em andamento. Sair vai '
                                    'interrompê-la.', tipo='perigo',
                                    sim='Sair'):
                return
            comum.parada_pedida.set()

        self.raiz.destroy()


def main():

    raiz = tk.Tk()
    raiz.withdraw()

    ok, mensagem = comum.travar('AlbionArbitragem')

    if not ok:
        visual.avisar(raiz, 'Já está aberto', mensagem, tipo='aviso')
        return

    try:
        abertura = visual.Abertura(raiz)

        Aplicativo(raiz)

        abertura.fechar(lambda: raiz.deiconify())

        raiz.mainloop()

    finally:
        comum.terminar_execucao()


if __name__ == '__main__':
    main()
