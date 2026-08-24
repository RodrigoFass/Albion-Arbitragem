################################
#                              #
#         TELA VENDER          #
#                              #
################################

# A outra ponta da rota: vender no Mercado Negro o que foi comprado na cidade.
#
#
# A CARGA VEM DO HISTORICO, e nao de um inventario lido da tela.
#
# O que se precisa saber de cada unidade e QUANTO ELA CUSTOU - e isso a tela do
# jogo nao mostra em lugar nenhum. Sem esse numero nao ha alvo de venda, e sem
# alvo a decisao vira chute: vender por 2.000 e otimo se custou 1.000 e pessimo
# se custou 1.900, e as duas unidades sao identicas no inventario.
#
# Por isso esta tela nao pergunta "o que voce tem?". Ela mostra o que o proprio
# programa comprou hoje e ainda nao vendeu.
#
#
# AS DUAS SAIDAS, LADO A LADO NA TABELA. Cada linha ja diz por qual caminho vai e
# por que - "97% do alvo" ou "uma prata abaixo de 1.500". A decisao acontece de
# novo no jogo, com os precos do momento, mas quem olha a tela antes de clicar
# precisa saber o que vai acontecer.
#
# Antes de alterar: python -m pyflakes tela_vender.py

import tkinter as tk

import ajustes
import comum
import historico
import mercado
import vendedor
import visual
from visual import COR, ESPACO, ESPACO_M, ESPACO_G

COLUNAS = (
    ('item',     'item',      200),
    ('pago',     'pago',      100, 'e'),
    ('qtd',      'quant.',     60, 'e'),
    ('alvo',     'alvo',      100, 'e'),
    ('caminho',  'caminho',   100),
    ('previsto', 'previsto',  110, 'e'),
)


class Tela:

    def __init__(self, quadro, app):

        self.quadro = quadro
        self.app = app
        self.precisa_atualizar = True
        self.carga = []

        self._montar()

    #region Montagem

    def _montar(self):

        visual.titulo_da_pagina(
            self.quadro, 'Vender',
            'levar a carga para o Mercado Negro — na hora, ou entrando na fila')

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

        visual.rotulo(linha, 'margem mín.', visual.FONTE_PEQUENA,
                      cor='texto_fraco').pack(side='left', padx=(0, ESPACO))

        self.margem = tk.StringVar()
        visual.Entrada(linha, self.margem, largura=5, alinhamento='center',
                       ao_confirmar=self.calcular).pack(side='left')

        visual.rotulo(linha, '%', visual.FONTE_PEQUENA,
                      cor='texto_fraco').pack(side='left', padx=(4, ESPACO_M))

        # QUANTO DO ALVO BASTA PARA VENDER AGORA. Exigir o alvo exato faria o bot
        # recusar 99% e ficar com a carga na mao esperando uma ordem que talvez
        # nunca case - trocando prata garantida por prata possivel.
        visual.rotulo(linha, 'vender na hora a partir de', visual.FONTE_PEQUENA,
                      cor='texto_fraco').pack(side='left', padx=(0, ESPACO))

        self.perto = tk.StringVar(value=f'{vendedor.PERTO_DO_ALVO * 100:.0f}')
        visual.Entrada(linha, self.perto, largura=5, alinhamento='center',
                       ao_confirmar=self.calcular).pack(side='left')

        visual.rotulo(linha, '% do alvo', visual.FONTE_PEQUENA,
                      cor='texto_fraco').pack(side='left', padx=(4, 0))

        visual.Botao(linha, 'Recalcular', self.calcular, largura=12).pack(
            side='left', padx=ESPACO_M)

        self.vender_botao = visual.Botao(linha, 'Vender de verdade',
                                         lambda: self.vender(True),
                                         tipo='perigo', largura=17)
        self.vender_botao.pack(side='right')
        self.vender_botao.habilitar(False)

        self.simular = visual.Botao(linha, 'Simular',
                                    lambda: self.vender(False), largura=10)
        self.simular.pack(side='right', padx=ESPACO)
        self.simular.habilitar(False)

    def _montar_resumo(self):

        caixa = tk.Frame(self.quadro, bg=COR['fundo'])
        caixa.pack(fill='x', padx=ESPACO_G, pady=(ESPACO_M, 0))

        self.pago = visual.Numero(caixa, 'pago', 'o que já saiu', '💸')
        self.previsto = visual.Numero(caixa, 'a receber', 'já com a taxa', '🏷️')
        self.saldo = visual.Numero(caixa, 'saldo do dia', 'realizado', '💰')
        self.parada = visual.Numero(caixa, 'carga parada', 'sem vender', '📦')

        for i, cartao in enumerate((self.pago, self.previsto, self.saldo,
                                    self.parada)):
            cartao.pack(side='left', fill='x', expand=True,
                        padx=(0 if i == 0 else ESPACO // 2,
                              0 if i == 3 else ESPACO // 2))

    def _montar_tabela(self):

        caixa = tk.Frame(self.quadro, bg=COR['fundo'])
        caixa.pack(fill='both', expand=True, padx=ESPACO_G,
                   pady=(ESPACO_M, ESPACO_M))

        visual.secao(caixa, 'Carga de hoje').pack(anchor='w', pady=(0, ESPACO))

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

        self.carga = vendedor.carga_do_dia()

        if not self.carga:
            self._vazio('Nada comprado hoje que ainda não tenha sido vendido. '
                        'A carga aparece aqui depois que a tela Comprar rodar.')
            return

        margem = self._margem()
        taxa = ajustes.atuais()['taxa']
        perto = self._perto()

        self.tabela.limpar()

        pago_total = 0
        previsto_total = 0

        for item, pago, quantas in self.carga:

            # OS PRECOS DO ULTIMO CONFERIR, para a tela poder decidir antes de
            # ir ao jogo. La a decisao acontece de novo, com o livro do momento -
            # esta aqui e uma previsao, e a tabela diz isso no cabecalho.
            pedido = self._pedido_de_compra(item)
            menor = self._menor_venda(item)

            modo, preco, motivo = vendedor.decidir(pago, pedido, menor, margem,
                                                   taxa, perto)

            alvo = vendedor.alvo(pago, margem, taxa)

            previsto = (preco or 0) * quantas
            pago_total += pago * quantas
            previsto_total += previsto if modo else 0

            self.tabela.acrescentar((
                item, comum.fmt(pago), quantas, comum.fmt(alvo),
                modo or 'não paga',
                comum.fmt(previsto) if modo else '—'))

        self._mostrar(pago_total, previsto_total)

    def _pedido_de_compra(self, item):
        """O melhor pedido de compra lido no Mercado Negro, de qualquer grau.

        A carga nao guarda a combinacao - o historico registra o item e o preco
        pago. Entre os graus lidos, o pedido mais alto e a melhor estimativa do
        que da para receber agora."""

        precos = [mercado.ler_outro(mercado.MERCADO_NEGRO, item, rot)
                  for rot in mercado.combinacoes(mercado.MERCADO_NEGRO, item)]

        validos = [p for p in precos if p]

        return max(validos) if validos else None

    def _menor_venda(self, item):

        precos = [mercado.ler(mercado.MERCADO_NEGRO, item, rot)[0]
                  for rot in mercado.combinacoes(mercado.MERCADO_NEGRO, item)]

        validos = [p for p in precos if p]

        return min(validos) if validos else None

    def _margem(self):

        texto = self.margem.get().strip().replace(',', '.')

        try:
            return float(texto) / 100
        except ValueError:
            return ajustes.atuais()['margem']

    def _perto(self):

        texto = self.perto.get().strip().replace(',', '.')

        try:
            return max(0.5, min(1.5, float(texto) / 100))
        except ValueError:
            return vendedor.PERTO_DO_ALVO

    def _mostrar(self, pago_total, previsto_total):

        do_dia = historico.do_dia()

        self.pago.mostrar(comum.fmt(pago_total))
        self.previsto.mostrar(comum.fmt(previsto_total))

        self.saldo.mostrar(
            comum.fmt(do_dia['saldo']),
            f'{do_dia["compras"]} compras, {do_dia["vendas"]} vendas',
            cor='ok' if do_dia['saldo'] > 0 else 'texto_fraco')

        unidades = sum(q for _, _, q in self.carga)

        self.parada.mostrar(str(unidades),
                            f'{len(self.carga)} itens diferentes')

        self.nota.config(
            text=f'{len(self.carga)} itens · {unidades} unidades  ·  os preços '
                 f'aqui são a última leitura do Conferir; no jogo a decisão é '
                 f'refeita com o livro do momento')

        self.simular.habilitar(True)
        self.vender_botao.habilitar(True)

    def _vazio(self, aviso):

        self.carga = []
        self.tabela.limpar()

        for cartao in (self.pago, self.previsto, self.parada):
            cartao.mostrar('—', '', cor='texto_fraco')

        do_dia = historico.do_dia()

        self.saldo.mostrar(comum.fmt(do_dia['saldo']),
                           f'{do_dia["compras"]} compras, '
                           f'{do_dia["vendas"]} vendas',
                           cor='ok' if do_dia['saldo'] > 0 else 'texto_fraco')

        self.nota.config(text=aviso)
        self.simular.habilitar(False)
        self.vender_botao.habilitar(False)

    #endregion

    def vender(self, de_verdade):

        if not self.carga:
            return

        unidades = sum(q for _, _, q in self.carga)

        if de_verdade and not visual.perguntar(
                self.quadro, 'Vender de verdade?',
                f'{unidades} unidades de {len(self.carga)} itens no '
                f'{mercado.MERCADO_NEGRO}.\n\n'
                f'O que já tiver comprador perto do alvo sai na hora; o resto '
                f'entra na fila uma prata abaixo do vendedor mais barato. '
                f'Nada é vendido abaixo do custo.\n\n'
                f'F11 pausa, F12 para.',
                tipo='perigo', sim='Vender'):
            return

        conf = ajustes.atuais()

        self.app.rodar(
            lambda: vendedor.vender(self.carga, margem=self._margem(),
                                    taxa=conf['taxa'], de_verdade=de_verdade),
            rotulo=('vendendo no ' if de_verdade else 'simulando venda no ')
                   + mercado.MERCADO_NEGRO,
            ao_terminar=self.app.avisar_telas)

    def ao_mostrar(self):

        self.precisa_atualizar = False

        if not self.margem.get():
            self.margem.set(f'{ajustes.atuais()["margem"] * 100:.0f}')

        mercado.carregar()
        self.calcular()
