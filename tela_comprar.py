################################
#                              #
#         TELA COMPRAR         #
#                              #
################################

# Cruza o que voce leu nos dois mercados e mostra a lista de compras.
#
# O RESUMO VEM ANTES DA TABELA, como na referencia. Quem abre esta tela quer
# saber se a viagem vale antes de ler linha por linha - e se nao valer, as
# duzentas linhas nao precisavam ter sido lidas.
#
# DUAS MARGENS, LADO A LADO. A bruta e a que os bots por ai mostram; a real
# desconta a taxa de venda e a de ordem. Sao dezessete pontos de diferenca no
# pior caso, e a bruta so esta aqui para voce poder comparar com o que ve por ai.
#
# Antes de alterar: python -m pyflakes tela_comprar.py

import tkinter as tk

import ajustes
import catalogo
import comprador
import comum
import lucro
import mercado
import visual
from visual import COR, ESPACO, ESPACO_M, ESPACO_G

COLUNAS = (
    ('item',   'item',        180),
    ('combo',  't/e',          50),
    ('qtd',    'quant.',       60, 'e'),
    ('compra', 'compra',       90, 'e'),
    ('venda',  'venda',        90, 'e'),
    ('bruta',  'margem bruta', 95, 'e'),
    ('margem', 'margem real',  95, 'e'),
    ('lucro',  'lucro',       100, 'e'),
)


class Tela:

    def __init__(self, quadro, app):

        self.quadro = quadro
        self.app = app
        self.precisa_atualizar = True
        self.linhas = []
        self.origem = None

        self._montar()

    #region Montagem

    def _montar(self):

        visual.titulo_da_pagina(
            self.quadro, 'Comprar',
            'cruzar os preços das duas pontas e comprar o que paga a margem')

        self._montar_barra()
        self._montar_resumo()
        self._montar_tabela()

    def _montar_barra(self):

        caixa = tk.Frame(self.quadro, bg=COR['fundo'])
        caixa.pack(fill='x', padx=ESPACO_G, pady=(ESPACO_M, 0))

        cartao = visual.Cartao(caixa, recheio=ESPACO_M - 2)
        cartao.pack(fill='x')

        linha = tk.Frame(cartao.dentro, bg=COR['painel'])
        linha.pack(fill='x')

        visual.rotulo(linha, 'comprar em', visual.FONTE_PEQUENA,
                      cor='texto_fraco').pack(side='left', padx=(0, ESPACO))

        self.cidade = tk.StringVar(value='a melhor')
        visual.Lista(linha, self.cidade,
                     ['a melhor'] + list(mercado.ORIGENS),
                     ao_mudar=lambda _v: self.calcular(),
                     largura=17).pack(side='left')

        visual.rotulo(linha, 'margem mín.', visual.FONTE_PEQUENA,
                      cor='texto_fraco').pack(side='left',
                                              padx=(ESPACO_M, ESPACO))

        self.margem = tk.StringVar()
        visual.Entrada(linha, self.margem, largura=5, alinhamento='center',
                       ao_confirmar=self.calcular).pack(side='left')

        visual.rotulo(linha, '%', visual.FONTE_PEQUENA,
                      cor='texto_fraco').pack(side='left', padx=(4, 0))

        visual.rotulo(linha, 'teto', visual.FONTE_PEQUENA,
                      cor='texto_fraco').pack(side='left',
                                              padx=(ESPACO_M, ESPACO))

        self.teto = tk.StringVar()
        visual.Entrada(linha, self.teto, largura=10, alinhamento='center',
                       ao_confirmar=self.calcular).pack(side='left')

        visual.Botao(linha, 'Calcular', self.calcular, largura=10).pack(
            side='left', padx=ESPACO_M)

        self.comprar_botao = visual.Botao(linha, 'Comprar de verdade',
                                          lambda: self.comprar(True),
                                          tipo='perigo', largura=17)
        self.comprar_botao.pack(side='right')
        self.comprar_botao.habilitar(False)

        self.simular = visual.Botao(linha, 'Simular', lambda: self.comprar(False),
                                    largura=10)
        self.simular.pack(side='right', padx=ESPACO)
        self.simular.habilitar(False)

    def _montar_resumo(self):

        caixa = tk.Frame(self.quadro, bg=COR['fundo'])
        caixa.pack(fill='x', padx=ESPACO_G, pady=(ESPACO_M, 0))

        self.rota = visual.Numero(caixa, 'rota', '', '🗺️')
        self.custo = visual.Numero(caixa, 'custo', 'o que sai', '💸')
        self.receita = visual.Numero(caixa, 'venda', 'já com a taxa', '🏷️')
        self.ganho = visual.Numero(caixa, 'lucro', 'o que fica', '💰')

        for i, cartao in enumerate((self.rota, self.custo, self.receita,
                                    self.ganho)):
            cartao.pack(side='left', fill='x', expand=True,
                        padx=(0 if i == 0 else ESPACO // 2,
                              0 if i == 3 else ESPACO // 2))

    def _montar_tabela(self):

        caixa = tk.Frame(self.quadro, bg=COR['fundo'])
        caixa.pack(fill='both', expand=True, padx=ESPACO_G,
                   pady=(ESPACO_M, ESPACO_M))

        visual.secao(caixa, 'Lista de compras').pack(anchor='w',
                                                     pady=(0, ESPACO))

        cartao = visual.Cartao(caixa, recheio=ESPACO)
        cartao.pack(fill='both', expand=True)

        self.tabela = visual.Tabela(cartao.dentro, COLUNAS)
        self.tabela.pack(fill='both', expand=True)

        self.nota = visual.rotulo(caixa, '', visual.FONTE_MINIMA,
                                  cor='texto_fraco', fundo='fundo')
        self.nota.pack(anchor='w', pady=(ESPACO, 0))

    #endregion

    #region Calcular

    def calcular(self):

        mercado.carregar()

        conf = ajustes.atuais()

        opcoes = dict(margem_minima=self._margem(), taxa=conf['taxa'],
                      idade_maxima=conf['idade_maxima'],
                      ordem_na_compra=True, teto=self._teto())

        do_catalogo = catalogo.para_calcular()

        if not do_catalogo:
            self._vazio('O catálogo está vazio — vá em Itens.')
            return

        escolha = self.cidade.get()

        if escolha == 'a melhor':
            melhor = lucro.melhor_origem(do_catalogo, **opcoes)
            if melhor is None:
                self._vazio('Nenhuma cidade tem preço lido.')
                return
            self.origem, self.linhas, resumo = melhor
        else:
            self.origem = escolha
            self.linhas, resumo = lucro.montar(do_catalogo, escolha, **opcoes)

        self._mostrar(resumo)

    def _teto(self):
        """O teto digitado, ou o dos ajustes, ou nenhum.

        Vazio quer dizer SEM TETO, e nao zero: zero seria um teto que corta
        tudo."""

        texto = self.teto.get().strip().replace('.', '').replace(',', '')

        if texto.isdigit():
            return int(texto)

        return ajustes.atuais().get('teto')

    def _margem(self):

        texto = self.margem.get().strip().replace(',', '.')

        try:
            return float(texto) / 100
        except ValueError:
            return ajustes.atuais()['margem']

    def _mostrar(self, resumo):

        self.tabela.limpar()

        for l in self.linhas:
            self.tabela.acrescentar((
                l['item'], l['combinacao'], l['quantidade'],
                comum.fmt(l['compra']), comum.fmt(l['venda']),
                f'{l["margem_bruta"] * 100:.1f}%',
                f'{l["margem"] * 100:.1f}%',
                comum.fmt(int(l['lucro']))))

        self.rota.mostrar(self.origem or '—',
                          f'→ {mercado.MERCADO_NEGRO}' if self.origem else '')
        self.custo.mostrar(comum.fmt(int(resumo['custo'])))
        self.receita.mostrar(comum.fmt(int(resumo['receita'])))
        self.ganho.mostrar(comum.fmt(int(resumo['lucro'])),
                           f'{resumo["margem"] * 100:.0f}% sobre o custo',
                           cor='ok' if resumo['lucro'] > 0 else 'texto_fraco')

        # OS DESCARTES, SEPARADOS POR MOTIVO. Uma lista vazia sem isto nao diz se
        # voce tem que coletar de novo ou baixar a margem.
        partes = []

        for chave, texto in (('sem_preco_de_compra', 'sem preço na cidade'),
                             ('sem_preco_de_venda', 'sem preço no Mercado Negro'),
                             ('precos_velhos', 'com preço velho'),
                             ('abaixo_da_margem', 'abaixo da margem'),
                             ('cortadas_pelo_teto', 'cortadas pelo teto')):
            if resumo[chave]:
                partes.append(f'{resumo[chave]} {texto}')

        self.nota.config(
            text=f'{len(self.linhas)} linhas  ·  de fora: ' + ' · '.join(partes)
            if partes else f'{len(self.linhas)} linhas')

        tem = bool(self.linhas)
        self.simular.habilitar(tem)
        self.comprar_botao.habilitar(tem)

    def _vazio(self, aviso):

        self.linhas = []
        self.tabela.limpar()

        for cartao in (self.rota, self.custo, self.receita, self.ganho):
            cartao.mostrar('—', '', cor='texto_fraco')

        self.nota.config(text=aviso)
        self.simular.habilitar(False)
        self.comprar_botao.habilitar(False)

    #endregion

    def comprar(self, de_verdade):

        if not self.linhas:
            return

        if de_verdade and not visual.perguntar(
                self.quadro, 'Comprar de verdade?',
                f'Isso vai gastar prata: até '
                f'{comum.fmt(int(sum(l["custo"] for l in self.linhas)))} em '
                f'{len(self.linhas)} linhas, em {self.origem}.\n\n'
                f'F12 para a qualquer momento.',
                tipo='perigo', sim='Comprar'):
            return

        conf = ajustes.atuais()

        self.app.rodar(
            lambda: comprador.comprar(
                self.origem, self.linhas,
                margem=self._margem(), taxa=conf['taxa'],
                teto_de_prata=self._teto(), de_verdade=de_verdade),
            rotulo=('comprando em ' if de_verdade else 'simulando ')
                   + str(self.origem),
            ao_terminar=self.app.avisar_telas)

    def ao_mostrar(self):

        self.precisa_atualizar = False

        atual = ajustes.atuais()

        if not self.margem.get():
            self.margem.set(f'{atual["margem"] * 100:.0f}')

        if not self.teto.get() and atual.get('teto'):
            self.teto.set(str(atual['teto']))

        self.calcular()
