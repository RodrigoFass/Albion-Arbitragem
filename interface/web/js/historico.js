/* ==========================================================================
   historico.js - o que ja foi feito, somado do historico.csv
   ========================================================================== */

'use strict';

(() => {

  let onde, periodo, contagem, corpo, lado;
  let recebido, saldo, unidades, margem;

  // '2026-10-13 22:46:26' -> '13/10 22:46'
  const quando = (v) => {
    const m = /^(\d{4})-(\d\d)-(\d\d) (\d\d:\d\d)/.exec(v || '');
    return m ? `${m[3]}/${m[2]} ${m[4]}` : v;
  };

  const tab = tabela([
    { chave: 'quando', titulo: 'Quando', formato: quando },
    { chave: 'operacao', titulo: 'O quê', formato: (v, l) => h('span', { class: v === 'venda' ? 'ok' : '' }, v, l.modo ? h('span', { class: 'fraquissimo' }, ` · ${l.modo}`) : null) },
    { chave: 'mercado', titulo: 'Onde' },
    { chave: 'item', titulo: 'Item', classe: 'item' },
    { chave: 'combinacao', titulo: 'Combinação' },
    { chave: 'unidades', titulo: 'Quant.', direita: true, formato: fmt },
    { chave: 'preco', titulo: 'Preço', direita: true, formato: (v) => v ? fmt(v) : '' },
    { chave: 'total', titulo: 'Total', direita: true, formato: (v) => v ? fmt(v) : '' },
  ]);

  function destaque(titulo, d, formatar) {
    return h('div', { class: 'cartao destaque-lado' },
      h('div', { class: 'nota' }, titulo),
      h('div', { class: 'valor' }, d ? d.valor : '—'),
      h('div', { class: 'nota' }, d ? formatar(d.legenda) : ' '));
  }

  async function carregar() {
    const r = await api('historico', onde.value, periodo.valor);

    if (r.erro) { torrada(r.erro, 'perigo'); return; }

    const atual = onde.value;
    trocar(onde, h('option', { value: '' }, 'Todos os lugares'), r.lugares.map((l) => h('option', { value: l }, l)));
    onde.value = r.lugares.includes(atual) ? atual : '';

    contagem.textContent = r.filtradas === r.total ? `${fmt(r.total)} operações` : `${fmt(r.filtradas)} de ${fmt(r.total)} operações`;

    const s = r.resumo;

    if (!r.filtradas) {
      for (const c of [recebido, saldo, unidades, margem]) c.mostrar(null);
      trocar(corpo, h('div', { class: 'cartao' }, vazio('historico',
        r.total ? 'Nada nesse filtro' : 'Nenhuma operação ainda',
        r.total ? 'Troque o lugar ou o período.' : 'O histórico enche sozinho quando o bot compra e vende.',
        r.total ? null : { rotulo: 'Ir para a Operação', fazer: () => app.ir('operacao') })));
      trocar(lado);
      return;
    }

    const plural = (n, um, varios) => `${fmt(n)} ${n === 1 ? um : varios}`;
    // ORDEM DE VENDA CRIADA NAO E PRATA RECEBIDA: ela aparece a parte, e o saldo
    // nao a conta - o bot nao sabe quando ela vende
    recebido.mostrar(fmt(s.recebido), plural(s.vendas, 'venda', 'vendas')
      + (s.em_ordens ? ` · ${fmt(s.em_ordens)} em ordens` : ''));
    saldo.mostrar(fmt(s.saldo), `${fmt(s.gasto)} gastos`, s.saldo > 0 ? 'ok' : (s.saldo < 0 ? 'perigo' : ''));
    unidades.mostrar(fmt(s.unidades), plural(s.compras, 'compra', 'compras'));
    // so existe margem depois de vender, e com carga parada ela ainda inclui o
    // que nao foi vendido - a legenda diz isso em vez de deixar parecer prejuizo
    if (s.margem === null) margem.mostrar(null, 'ainda sem venda');
    else margem.mostrar(pct(s.margem), s.saldo < 0 ? 'inclui a carga ainda não vendida' : 'sobre o gasto',
      s.margem > 0 ? 'ok' : (s.saldo < 0 ? '' : 'perigo'));

    tab.encher(r.linhas);
    trocar(corpo, tab,
      r.filtradas > r.linhas.length ? h('div', { class: 'nota', style: { marginTop: '8px' } }, `Mostrando as ${fmt(r.linhas.length)} mais recentes.`) : null);

    // OS DESTAQUES NUMA FILA, e a tabela com a largura toda: ao lado dela, eles
    // a espremiam e cortavam as colunas de preco
    trocar(lado,
      destaque('Item mais negociado', r.destaques.item, (v) => v),
      destaque('Cidade onde mais comprou', r.destaques.cidade, (v) => `${fmt(v)} prata`),
      destaque('Maior venda', r.destaques.venda, (v) => `${fmt(v)} prata`));
  }

  TELAS.historico = {
    titulo: 'Histórico',
    subtitulo: 'o que já foi comprado e vendido — o lucro de verdade, não o previsto',

    montar(el) {
      onde = seletor([['', 'Todos os lugares']], '', carregar);
      periodo = segmentado([['tudo', 'Tudo'], ['hoje', 'Hoje'], ['24h', '24 h'], ['7d', '7 dias'], ['30d', '30 dias']], 'tudo', carregar);
      contagem = h('span', { class: 'nota' });

      recebido = numero('Recebido');
      saldo = numero('Saldo');
      unidades = numero('Unidades compradas');
      margem = numero('Margem realizada');

      corpo = h('div');
      lado = h('div', { class: 'grade-3' });

      el.append(h('div', { class: 'pilha' },
        h('div', { class: 'linha' }, onde, periodo, contagem, h('span', { class: 'empurra' }),
          h('button', { class: 'botao discreto', onclick: () => api('abrir_pasta') }, icone('pasta'), 'Abrir a pasta dos registros')),
        h('div', { class: 'grade-4' }, recebido, saldo, unidades, margem),
        lado,
        corpo));
    },

    mostrar: carregar,
  };
})();
