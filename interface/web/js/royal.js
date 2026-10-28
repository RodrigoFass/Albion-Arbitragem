/* ==========================================================================
   royal.js - vale a pena craftar Royal para vender na hora no Mercado Negro?
   ========================================================================== */

'use strict';

(() => {

  let cidade, lerNegro, lerCidade, sigils, corpo, faltas;
  let rentaveis, melhor, investido, taxaUsada;
  let ultimo = null;

  const tab = tabela([
    { chave: 'royal', titulo: 'Royal', classe: 'item' },
    { chave: 'combinacao', titulo: 'Combinação' },
    { chave: 'buy_order', titulo: 'Buy Order (BM)', direita: true, formato: fmt },
    { chave: 'receita', titulo: 'Recebe', direita: true, formato: fmt },
    { chave: 'normal', titulo: 'Item normal', formato: (v, l) => h('span', {}, v, h('span', { class: 'fraquissimo' }, ` · ${fmt(l.preco_normal)}`)) },
    { chave: 'sigils', titulo: 'Sigils', direita: true, formato: (v, l) => `${v} × ${fmt(l.preco_sigil)}` },
    { chave: 'custo', titulo: 'Custo', direita: true, formato: fmt },
    { chave: 'lucro', titulo: 'Lucro', direita: true, formato: (v) => h('span', { class: v > 0 ? 'ok' : 'perigo' }, fmt(v)) },
    { chave: 'margem', titulo: 'Margem', direita: true, formato: (v) => pct(v) },
  ]);

  function campoDoSigil(s) {
    const input = h('input', { class: 'entrada', inputmode: 'numeric', placeholder: 'sem preço', value: s.preco ? fmt(s.preco) : '' });
    const salvar = async () => {
      const texto = input.value.trim();
      if (!texto || (ultimo && texto === fmt(s.preco))) return;
      const r = await api('definir_sigil', cidade.value, s.grau, texto);
      if (r.erro) { torrada(r.erro, 'perigo'); return; }
      desenhar(r);
    };
    input.addEventListener('change', salvar);
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter') input.blur(); });
    const idade = s.idade === null ? '' : (s.idade < 1 ? 'agora há pouco' : `há ${horas(s.idade)}`);
    return campo(`T${s.grau}${idade ? ' · ' + idade : ''}`, comUnidade(input, 'prata'));
  }

  function desenhar(r) {
    ultimo = r;

    const atual = cidade.value;
    trocar(cidade, r.cidades.map((c) => h('option', { value: c }, c)));
    cidade.value = r.cidade || atual;
    lerCidade.lastChild.textContent = `Ler itens normais em ${cidade.value}`;

    trocar(sigils, ...r.sigils.map(campoDoSigil));

    const lucram = r.linhas.filter((l) => l.lucro > 0);
    rentaveis.mostrar(fmt(lucram.length), `de ${fmt(r.linhas.length)} combinações com os três preços`, lucram.length ? 'ok' : '');
    if (lucram.length) {
      const m = lucram[0];
      melhor.mostrar(fmt(m.lucro), `${m.royal} ${m.combinacao} · ${pct(m.margem)}`, 'ok');
      investido.mostrar(fmt(lucram.reduce((s, l) => s + l.custo, 0)), 'uma de cada combinação que lucra');
    } else {
      melhor.mostrar(null, 'nada lucra ainda');
      investido.mostrar(null);
    }
    taxaUsada.mostrar(pct(r.taxa, 0), 'taxa de venda na hora (Premium nos Ajustes)');

    if (r.linhas.length) {
      tab.encher(r.linhas);
      trocar(corpo, tab);
    } else {
      trocar(corpo, h('div', { class: 'cartao' }, vazio('coroa', 'Nenhuma conta ainda',
        'Leia os Royal no Mercado Negro, os itens normais na cidade, e coloque o preço dos Sigils — '
        + 'a tabela aparece quando uma combinação tiver os três.')));
    }

    const f = r.faltas;
    const partes = [];
    if (f.sem_buy_order) partes.push(`${fmt(f.sem_buy_order)} sem Buy Order no Mercado Negro`);
    if (f.sem_item_normal) partes.push(`${fmt(f.sem_item_normal)} sem item normal em ${cidade.value}`);
    if (f.sem_sigil) partes.push(`${fmt(f.sem_sigil)} sem preço de Sigil`);
    faltas.textContent = partes.length ? `Ficaram de fora: ${partes.join(' · ')}.` : '';

    habilitar(!!app.rodando);
  }

  async function carregar() {
    desenhar(await api('royal_estado', cidade.value || null));
  }

  function habilitar(rodando) {
    lerNegro.disabled = lerCidade.disabled = rodando;
  }

  TELAS.royal = {
    titulo: 'Craft Royal',
    subtitulo: 'item normal + Royal Sigils, vendido na hora no Buy Order do Mercado Negro',

    montar(el) {
      cidade = seletor([], '', carregar);
      lerNegro = h('button', { class: 'botao', onclick: () => app.rodar('ler_royal_negro') }, icone('negro'), 'Ler os Royal no Mercado Negro');
      lerCidade = h('button', { class: 'botao', onclick: () => app.rodar('ler_royal_cidade', cidade.value) }, icone('moeda'), 'Ler itens normais');

      sigils = h('div', { class: 'linha' });
      corpo = h('div');
      faltas = h('p', { class: 'nota', style: { margin: '8px 0 0' } });

      rentaveis = numero('Combinações que lucram');
      melhor = numero('Melhor lucro por unidade');
      investido = numero('Para craftar uma de cada');
      taxaUsada = numero('Taxa de venda');

      el.append(h('div', { class: 'pilha' },
        cartao('De onde vêm os preços',
          h('p', { class: 'nota', style: { margin: '0 0 12px' } },
            'O Buy Order de cada Royal vem da leitura no Mercado Negro — a venda na hora. O item normal (Scholar, '
            + 'Mercenary, Soldier...) vem da leitura na cidade, e vale o mais barato dos três da receita. O Sigil você '
            + 'abre no mercado da cidade e a rede pega o preço sozinha — ou digita aqui embaixo. Não há prata nem foco '
            + 'no craft do Royal.'),
          h('div', { class: 'linha' }, campo('Cidade', cidade), h('span', { class: 'empurra' }), lerNegro, lerCidade)),
        cartao('Royal Sigil — preço de um, na cidade', sigils),
        h('div', { class: 'grade-4' }, rentaveis, melhor, investido, taxaUsada),
        corpo,
        faltas));
    },

    mostrar: carregar,

    aoRodar(rodando) {
      habilitar(rodando);
      if (!rodando && app.montadas.royal) carregar();
    },
  };
})();
