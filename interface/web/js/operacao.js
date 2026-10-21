/* ==========================================================================
   operacao.js - os tres passos da viagem: ler precos, comprar, vender
   ========================================================================== */

'use strict';

(() => {

  const ICONE_CIDADE = {
    'Martlock': 'martlock', 'Thetford': 'thetford', 'Fort Sterling': 'fort-sterling',
    'Lymhurst': 'lymhurst', 'Bridgewatch': 'bridgewatch', 'Caerleon': 'caerleon',
  };

  const PASSOS = [
    ['precos', 'Ler preços'],
    ['comprar', 'Comprar'],
    ['vender', 'Vender'],
  ];

  let raiz, passosEl, corpo;
  let passo = 'precos';
  const paineis = {};

  /* ------------------------------------------------------------------------
     cabecalho de passos: onde estou, o que ja esta pronto
     ------------------------------------------------------------------------ */

  function montarPassos() {
    passosEl = h('nav', { class: 'passos', 'aria-label': 'Passos' });
    PASSOS.forEach(([chave, nome], i) => {
      passosEl.append(h('button', { class: 'passo', 'data-passo': chave, onclick: () => irPasso(chave) },
        h('span', { class: 'indice' }, i + 1),
        h('div', {}, h('strong', {}, nome), h('small', { 'data-resumo': chave }, ' '))));
    });
    return passosEl;
  }

  function pintarPassos() {
    for (const b of passosEl.children) {
      if (b.dataset.passo === passo) b.setAttribute('aria-current', 'step');
      else b.removeAttribute('aria-current');
    }
  }

  function resumoPasso(chave, texto) {
    const el = passosEl.querySelector(`[data-resumo="${chave}"]`);
    if (el) el.textContent = texto || ' ';
  }

  function irPasso(chave) {
    passo = chave;
    pintarPassos();
    for (const [k, p] of Object.entries(paineis)) p.el.classList.toggle('oculto', k !== chave);
    paineis[chave].mostrar();
  }

  /* ========================================================================
     1 - LER PRECOS
     ======================================================================== */

  const precos = (() => {
    const el = h('div', { class: 'pilha' });
    let dados = null;
    let escolhido = null;
    let plano = null;
    let pedido = 0;

    const grade = h('div', { class: 'mercados', role: 'group', 'aria-label': 'Onde você está' });
    const grupoSel = seletor([['', 'Todos os grupos']], '', () => calcularPlano());
    const faltando = h('input', { type: 'checkbox' });
    faltando.addEventListener('change', () => calcularPlano());

    // AS COMBINACOES DA LEITURA: o botao diz quantas estao marcadas e abre as
    // caixas embaixo. Desmarcar pula aquela combinacao em todos os itens.
    let combos = null;    // {rotulos, marcadas}
    const combosBotao = h('button', { type: 'button', class: 'entrada botao-combinacoes', 'aria-expanded': 'false', onclick: () => alternarCombos() }, '…');
    const combosPainel = h('div', { class: 'combinacoes oculto' });

    // a situacao da rede, no canto do cartao: clicar leva aos ajustes dela
    const redeTexto = h('span', {});
    const redePonto = h('span', { class: 'ponto' });
    const redeEl = h('button', { class: 'pilula-rede', onclick: () => app.ir('ajustes', 'leitura') }, redePonto, redeTexto);
    const tempo = h('div', { class: 'tempo' }, '—');
    const detalhe = h('div', { class: 'detalhe' });
    const explica = h('div', { class: 'nota' });
    const comecar = h('button', { class: 'botao principal-acao', onclick: () => varrer() }, 'Começar a leitura');
    const trazer = h('button', { class: 'botao discreto pequeno', onclick: () => restaurar() }, icone('desfazer'), 'Trazer de volta os preços apagados');
    const apagar = h('button', { class: 'botao discreto pequeno', onclick: () => apagarVelhos() }, icone('lixo'), 'Apagar preços com mais de 24 h');

    el.append(
      cartao(null, h('div', { class: 'cabeca-cartao' }, h('h2', {}, 'Onde você está agora'), redeEl), grade),
      cartao('O que ler',
        h('div', { class: 'linha' },
          campo('Grupo', grupoSel),
          campo('Combinações', combosBotao),
          h('label', { class: 'marcar', style: { alignSelf: 'flex-end', height: '36px' } }, faltando, 'Só o que ainda não foi lido')),
        combosPainel,
        h('div', { class: 'plano separado' },
          h('div', {}, tempo, h('div', { class: 'nota' }, 'estimado')),
          h('div', { style: { flex: 1 } }, detalhe, explica),
          comecar),
        h('div', { class: 'linha', style: { marginTop: '8px' } }, trazer, apagar)));

    function desenharCombos() {
      const marcadas = new Set(combos.marcadas);
      const graus = {};
      for (const r of combos.rotulos) {
        const g = r.slice(1).split('.')[0];
        (graus[g] = graus[g] || []).push(r);
      }

      trocar(combosPainel,
        h('div', { class: 'linha' },
          h('button', { type: 'button', class: 'botao discreto pequeno', onclick: () => marcarCombos(combos.rotulos) }, 'Marcar todas'),
          h('button', { type: 'button', class: 'botao discreto pequeno', onclick: () => marcarCombos([]) }, 'Desmarcar todas'),
          h('span', { class: 'nota' }, 'Vale só para a leitura. Para tirar uma combinação da compra também, zere a quantidade dela na tela Itens.')),
        Object.entries(graus).map(([g, rotulos]) => h('div', { class: 'combinacoes-grau', role: 'group', 'aria-label': `Grau ${g}` },
          h('strong', {}, `Grau ${g}`),
          rotulos.map((r) => {
            const caixa = h('input', { type: 'checkbox', 'data-rotulo': r });
            caixa.checked = marcadas.has(r);
            caixa.addEventListener('change', () => marcarCombos(
              combos.rotulos.filter((x) => (x === r ? caixa.checked : marcadas.has(x)))));
            return h('label', { class: 'marcar' }, caixa, r.slice(1));
          }))));

      const n = combos.marcadas.length;
      const total = combos.rotulos.length;
      combosBotao.textContent = n === total ? `Todas (${total})` : `${n} de ${total}`;
    }

    async function marcarCombos(lista) {
      combos = await api('marcar_combinacoes_para_ler', lista);
      desenharCombos();
      calcularPlano();
    }

    function alternarCombos() {
      const aberto = !combosPainel.classList.toggle('oculto');
      combosBotao.setAttribute('aria-expanded', aberto ? 'true' : 'false');
    }

    function corDaIdade(m) {
      if (!m.quantos) return '';
      if (m.idade > 24) return 'perigo';
      if (m.idade > 6) return 'aviso';
      return 'ok';
    }

    function desenharMercados() {
      trocar(grade, dados.mercados.map((m) => {
        const img = m.negro
          ? h('span', { class: 'emblema' }, icone('negro'))
          : h('img', { src: `img/cidades/${ICONE_CIDADE[m.nome]}.png`, alt: '' });
        const estado = m.quantos ? `${fmt(m.quantos)} · ${horas(m.idade)}` : 'nunca lido';
        return h('button', {
          class: 'mercado', 'aria-pressed': m.nome === escolhido ? 'true' : 'false',
          onclick: () => escolher(m.nome),
        }, img, h('strong', {}, m.nome), h('small', { class: corDaIdade(m) }, estado));
      }));
      trazer.classList.toggle('oculto', !escolhido || !(dados.mercados.find((m) => m.nome === escolhido) || {}).tem_copia);
    }

    async function escolher(nome) {
      escolhido = nome;
      desenharMercados();
      await api('escolher_mercado', nome);
      calcularPlano();
    }

    async function calcularPlano() {
      plano = null;
      comecar.disabled = true;

      if (!escolhido) {
        tempo.textContent = '—';
        detalhe.textContent = 'Escolha acima o mercado em que você está.';
        explica.textContent = 'O bot não tem como saber onde você está, e guardar um preço no mercado errado estraga a conta das duas cidades.';
        return;
      }

      const meu = ++pedido;

      const r = await api('plano_varredura', escolhido, grupoSel.value || null, faltando.checked);
      if (meu !== pedido) return;

      plano = r;

      if (r.erro || !r.combinacoes) {
        tempo.textContent = '—';
        detalhe.textContent = r.erro || r.aviso || 'Nada a ler.';
        explica.textContent = '';
        return;
      }

      tempo.textContent = minutos(r.minutos);

      trocar(detalhe, `${fmt(r.combinacoes)} combinações em ${r.itens} itens, em ${escolhido}`);

      const partes = [];
      if (r.apagar && r.tinha) partes.push(`Os ${fmt(r.tinha)} preços que já existem em ${escolhido} serão apagados antes — dá para trazer de volta.`);
      explica.textContent = partes.join(' ');

      comecar.disabled = !!app.rodando;
    }

    async function varrer() {
      if (!plano || !plano.combinacoes) return;

      const sim = await dialogo({
        titulo: `Ler os preços de ${escolhido}?`,
        dados: [
          ['Combinações', fmt(plano.combinacoes)],
          ['Itens', fmt(plano.itens)],
          ['Tempo estimado', minutos(plano.minutos)],
        ],
        texto: 'Durante a leitura o jogo fica em primeiro plano e o mouse é do bot. '
          + 'F11 pausa, F12 para.',
        sim: 'Começar',
      });
      if (!sim) return;

      await app.rodar('varrer', escolhido, grupoSel.value || null, faltando.checked);
    }

    async function restaurar() {
      const n = await api('restaurar_precos', escolhido);
      torrada(n ? `${fmt(n)} preços de ${escolhido} voltaram.` : 'Não há cópia guardada desse mercado.', n ? 'ok' : '');
      await app.atualizarEstado();
      mostrar();
    }

    async function apagarVelhos() {
      const sim = await dialogo({
        titulo: 'Apagar os preços antigos?',
        texto: 'Tira tudo que foi lido há mais de 24 horas.\n\nPreço velho é pior que preço nenhum: '
          + 'sem ele a tela diz "sem preço" e você vai ler; com ele a tela mostra um número, e número na tela parece verdade.',
        sim: 'Apagar',
        tom: 'perigo',
      });
      if (!sim) return;
      const n = await api('apagar_velhos');
      torrada(`${fmt(n)} preços apagados.`, 'ok');
      await app.atualizarEstado();
      mostrar();
    }

    function pintarRede(d) {
      const [texto, tom] = curtoDaRede(d.rede);
      redeTexto.textContent = texto;
      redePonto.className = 'ponto ' + tom;
      redeEl.title = textoDaRede(d.rede)[0];
    }

    // O JOGO SABE ONDE VOCE ESTA: com a rede mandando, o mercado se escolhe
    // sozinho - e um preco nunca e guardado na cidade errada.
    async function seguirARede(d) {
      if (d.pela_rede && d.pela_rede !== escolhido && !app.rodando) {
        torrada(`A rede diz que você está em ${d.pela_rede}.`);
        await escolher(d.pela_rede);
        return true;
      }
      return false;
    }

    // enquanto a tela esta aberta, a rede e conferida de tempos em tempos
    setInterval(async () => {
      if (el.offsetParent === null || app.rodando) return;
      const d = await api('mercados');
      pintarRede(d);
      if (!(await seguirARede(d))) {
        dados = d;
        desenharMercados();
      }
    }, 5000);

    async function mostrar() {
      dados = await api('mercados');
      if (escolhido === null) escolhido = dados.escolhido;
      pintarRede(dados);

      combos = await api('combinacoes_para_ler');
      desenharCombos();

      const atual = grupoSel.value;
      trocar(grupoSel, h('option', { value: '' }, 'Todos os grupos'),
        dados.grupos.map((g) => h('option', { value: g }, g)));
      grupoSel.value = dados.grupos.includes(atual) ? atual : '';

      resumir();

      // escolher() ja redesenha e recalcula
      if (await seguirARede(dados)) return;

      desenharMercados();
      calcularPlano();
    }

    function resumir(novos) {
      if (novos) dados = novos;
      if (!dados) return;
      const lidos = dados.mercados.filter((m) => m.quantos);
      if (!lidos.length) { resumoPasso('precos', 'nenhum mercado lido'); return; }
      const velho = Math.max(...lidos.map((m) => m.idade || 0));
      resumoPasso('precos', `${lidos.length} de 7 lidos · mais velho ${horas(velho)}`);
    }

    return { el, mostrar, resumir, aoRodar: (r) => { comecar.disabled = r || !plano || !plano.combinacoes; } };
  })();

  /* ========================================================================
     2 - COMPRAR
     ======================================================================== */

  const comprar = (() => {
    const el = h('div', { class: 'pilha' });
    let ultimo = null;
    let lidosDosAjustes = null;

    const cidade = seletor([['a melhor', 'A melhor cidade']], 'a melhor', () => calcular());
    const margem = h('input', { class: 'entrada', inputmode: 'decimal' });
    const teto = h('input', { class: 'entrada', inputmode: 'numeric', placeholder: 'sem limite' });
    const espacos = h('input', { class: 'entrada', inputmode: 'numeric', placeholder: 'sem limite' });
    for (const c of [margem, teto, espacos]) {
      c.addEventListener('change', () => calcular());
      c.addEventListener('keydown', (e) => e.key === 'Enter' && calcular());
    }

    const rota = numero('Rota');
    const custo = numero('Custo');
    const receita = numero('Venda, já com a taxa');
    const lucro = numero('Lucro');

    const tab = tabela([
      { chave: 'item', titulo: 'Item', classe: 'item' },
      { chave: 'combinacao', titulo: 'Combinação' },
      { chave: 'qualidade', titulo: 'Qualidade', formato: (v) => v ? h('span', { class: 'selo destaque' }, nomeDaQualidade(v)) : h('span', { class: 'fraquissimo' }, 'qualquer') },
      { chave: 'quantidade', titulo: 'Quant.', direita: true, formato: fmt },
      // na cidade, a media das ofertas ate a quantidade da linha; a menor
      // oferta fica no balao, para conferir com o jogo
      { chave: 'compra', titulo: 'Compra', direita: true,
        formato: (v, l) => l.compra_por_media
          ? h('span', { title: `menor oferta: ${fmt(l.menor_oferta)}` }, fmt(v), h('span', { class: 'fraquissimo' }, ' · média'))
          : fmt(v) },
      // o caminho da venda que a conta usou: o pedido de compra (na hora) ou uma
      // prata abaixo da fila (por ordem, com os 2,5% a mais)
      { chave: 'venda', titulo: 'Venda', direita: true,
        formato: (v, l) => h('span', null, fmt(v), h('span', { class: 'fraquissimo' }, l.venda_por_ordem ? ' · ordem' : ' · na hora')) },
      { chave: 'margem_bruta', titulo: 'Margem bruta', direita: true, formato: (v) => pct(v) },
      { chave: 'margem', titulo: 'Margem real', direita: true, formato: (v) => pct(v) },
      { chave: 'lucro', titulo: 'Lucro', direita: true, formato: fmt },
    ]);

    const lista = h('div');
    const nota = h('div', { class: 'nota' });
    const simular = h('button', { class: 'botao', onclick: () => executar(false) }, 'Simular');
    const deVerdade = h('button', { class: 'botao perigo-acao', onclick: () => executar(true) }, 'Comprar de verdade');
    const porque = h('span', { class: 'nota' });

    el.append(
      cartao(null, h('div', { class: 'linha' },
        campo('Comprar em', cidade),
        campo('Margem mínima', comUnidade(margem, '%')),
        campo('Teto de gasto', comUnidade(teto, 'prata')),
        campo('Espaços no inventário', comUnidade(espacos, 'espaços')))),
      h('div', { class: 'grade-4' }, rota, custo, receita, lucro),
      h('div', { class: 'linha' }, h('span', { class: 'secao-titulo', style: { margin: 0 } }, 'Lista de compras'),
        h('span', { class: 'empurra' }), porque, simular, deVerdade),
      lista,
      nota);

    function preencherDosAjustes(valores) {
      // OS CAMPOS SEGUEM OS AJUSTES QUANDO ELES MUDAM. O que voce digitar aqui
      // vale ate a proxima mudanca la.
      const chave = JSON.stringify([valores.margem, valores.teto, valores.espacos]);
      if (chave === lidosDosAjustes) return;
      lidosDosAjustes = chave;
      margem.value = (valores.margem * 100).toLocaleString('pt-BR', { maximumFractionDigits: 1 });
      teto.value = valores.teto ? fmt(valores.teto) : '';
      espacos.value = valores.espacos || '';
    }

    async function calcular() {
      const r = await api('calcular_compra', cidade.value, margem.value, teto.value, espacos.value);
      ultimo = r;

      const atual = cidade.value;
      trocar(cidade, h('option', { value: 'a melhor' }, 'A melhor cidade'), r.cidades.map((c) => h('option', { value: c }, c)));
      cidade.value = atual;

      const tem = r.linhas && r.linhas.length;

      if (r.resumo) {
        rota.mostrar(r.origem, '→ Mercado Negro');
        custo.mostrar(fmt(r.resumo.custo), `${fmt(r.resumo.unidades)} unidades`);
        receita.mostrar(fmt(r.resumo.receita), 'o que entra depois das taxas');
        lucro.mostrar(fmt(r.resumo.lucro), r.resumo.custo ? `${pct(r.resumo.margem, 0)} sobre o custo` : '', r.resumo.lucro > 0 ? 'ok' : '');
      } else {
        for (const c of [rota, custo, receita, lucro]) c.mostrar(null);
      }

      if (tem) {
        tab.encher(r.linhas);
        // com a compra por qualidade desligada, a coluna so repetiria "qualquer"
        tab.classList.toggle('sem-qualidade', !r.linhas.some((l) => l.qualidade));
        trocar(lista, tab);
      } else {
        const a = r.aviso || {};
        trocar(lista, h('div', { class: 'cartao' }, vazio('caixa', a.texto || 'Nada a comprar.',
          'A lista mostra só o que paga a margem mínima, com os dois preços lidos há pouco tempo.',
          a.acao ? { rotulo: a.rotulo, fazer: () => a.acao === 'itens' ? app.ir('itens') : irPasso('precos') } : null)));
      }

      // OS DESCARTES, SEPARADOS POR MOTIVO: sem isto uma lista vazia nao diz se
      // e para ler de novo ou baixar a margem
      const partes = [];
      const s = r.resumo || {};
      for (const [k, t] of [['sem_preco_de_compra', 'sem preço na cidade'], ['sem_preco_de_venda', 'sem preço no Mercado Negro'],
        ['precos_velhos', 'com preço velho'], ['abaixo_da_margem', 'abaixo da margem'],
        ['cortadas_pelo_teto', 'cortadas pelo teto'], ['sem_espaco', 'sem espaço no inventário']]) {
        if (s[k]) partes.push(`${fmt(s[k])} ${t}`);
      }
      const avisos = [];
      if (partes.length) avisos.push(`Ficaram de fora: ${partes.join(' · ')}.`);
      if (r.qualidade && r.qualidade.ligada && !r.qualidade.pode_comprar) {
        avisos.push(`A compra por qualidade está ligada, mas as linhas de qualidade só compram com ${r.qualidade.faltam.join(' e ')}.`);
      }
      nota.textContent = avisos.join(' ');

      resumoPasso('comprar', tem ? `${r.linhas.length} linhas em ${r.origem} · lucro ${fmt(r.resumo.lucro)}` : 'nada que pague a margem');
      habilitar();
    }

    function habilitar() {
      const tem = ultimo && ultimo.linhas && ultimo.linhas.length;
      simular.disabled = deVerdade.disabled = !tem || !!app.rodando;
      porque.textContent = app.rodando ? 'Há uma operação em andamento.' : (tem ? '' : 'Sem linhas para comprar.');
    }

    async function executar(real) {
      if (real) {
        const s = ultimo.resumo;
        const sim = await dialogo({
          titulo: `Comprar em ${ultimo.origem}?`,
          dados: [['Linhas', fmt(ultimo.linhas.length)], ['Unidades', fmt(s.unidades)], ['Gasto máximo', `${fmt(s.custo)} prata`], ['Lucro previsto', fmt(s.lucro)]],
          texto: 'Isto gasta prata de verdade. Antes de cada compra o bot relê o livro e confere o valor no diálogo do jogo. F12 para a qualquer momento.',
          sim: 'Comprar',
          tom: 'perigo',
        });
        if (!sim) return;
      }
      await app.rodar('comprar', real);
    }

    async function mostrar() {
      const a = await api('ajustes_atuais');
      preencherDosAjustes(a.valores);
      calcular();
    }

    return { el, mostrar, aoRodar: habilitar };
  })();

  /* ========================================================================
     3 - VENDER
     ======================================================================== */

  const vender = (() => {
    const el = h('div', { class: 'pilha' });
    let ultimo = null;
    let lidosDosAjustes = null;

    const margem = h('input', { class: 'entrada', inputmode: 'decimal' });
    const perto = h('input', { class: 'entrada', inputmode: 'decimal', value: '95' });
    for (const c of [margem, perto]) {
      c.addEventListener('change', () => calcular());
      c.addEventListener('keydown', (e) => e.key === 'Enter' && calcular());
    }

    const pago = numero('Pago');
    const receber = numero('A receber');
    const saldo = numero('Saldo de hoje');
    const parada = numero('Carga parada');

    const tab = tabela([
      { chave: 'item', titulo: 'Item', classe: 'item' },
      { chave: 'combinacao', titulo: 'Combinação', formato: (v) => v || h('span', { class: 'fraquissimo' }, '?') },
      { chave: 'qualidade', titulo: 'Qualidade', formato: (v) => v ? nomeDaQualidade(v) : h('span', { class: 'fraquissimo' }, 'Normal') },
      { chave: 'pago', titulo: 'Pago', direita: true, formato: fmt },
      { chave: 'quantidade', titulo: 'Quant.', direita: true, formato: fmt },
      { chave: 'alvo', titulo: 'Alvo', direita: true, formato: fmt },
      { chave: 'modo', titulo: 'Caminho', formato: (v) => v ? v : h('span', { class: 'fraquissimo' }, 'não paga') },
      { chave: 'previsto', titulo: 'Previsto', direita: true, formato: (v, l) => l.modo ? fmt(v) : '—' },
    ]);

    const lista = h('div');
    const nota = h('div', { class: 'nota' });
    const simular = h('button', { class: 'botao', onclick: () => executar(false) }, 'Simular');
    const deVerdade = h('button', { class: 'botao perigo-acao', onclick: () => executar(true) }, 'Vender de verdade');
    const porque = h('span', { class: 'nota' });

    // VENDER PELO MERCADO: sem depender da compra - cada linha da lista "Sell
    // from Inventory", uma prata abaixo do menor preco da qualidade Normal
    const simularMercado = h('button', { class: 'botao', onclick: () => executarMercado(false) }, 'Simular');
    const venderMercado = h('button', { class: 'botao perigo-acao', onclick: () => executarMercado(true) }, 'Vender a mochila');

    el.append(
      cartao('Vender a mochila pelo mercado',
        h('div', { class: 'linha' },
          h('p', { class: 'nota', style: { margin: 0, flex: 1 } },
            'Não precisa ter comprado pelo bot. Com o Mercado Negro aberto em "Sell from Inventory", o bot clica no Sell '
            + 'de cada linha, de cima para baixo, e cria a ordem 1 prata abaixo do menor preço da qualidade Normal — na '
            + 'frente da fila, com a pilha inteira. O que a lista mostrar é o que será vendido. Serve também para recolocar '
            + 'uma ordem que você cancelou, com o preço de agora.'),
          simularMercado, venderMercado)),
      cartao(null, h('div', { class: 'linha' },
        campo('Margem mínima', comUnidade(margem, '%')),
        campo('Vender na hora a partir de', comUnidade(perto, '% do alvo'))),
        h('p', { class: 'nota', style: { margin: '12px 0 0' } },
          'O que já tem comprador perto do alvo sai na hora; o resto entra na fila uma prata abaixo do vendedor mais barato. Nada é vendido abaixo do custo.')),
      h('div', { class: 'grade-4' }, pago, receber, saldo, parada),
      h('div', { class: 'linha' }, h('span', { class: 'secao-titulo', style: { margin: 0 } }, 'Carga a vender'),
        h('span', { class: 'empurra' }), porque, simular, deVerdade),
      lista,
      nota);

    async function calcular() {
      const r = await api('calcular_venda', margem.value, perto.value);
      ultimo = r;
      const d = r.do_dia;

      saldo.mostrar(fmt(d.saldo), `${d.compras} compras · ${d.vendas} vendas`, d.saldo > 0 ? 'ok' : (d.saldo < 0 ? 'perigo' : ''));

      if (r.linhas.length) {
        pago.mostrar(fmt(r.pago), 'o que já saiu');
        receber.mostrar(fmt(r.previsto), 'já com a taxa');
        parada.mostrar(fmt(r.unidades), `${r.linhas.length} itens diferentes`);
        tab.encher(r.linhas);
        // tudo Normal (o de sempre): a coluna nao diria nada
        tab.classList.toggle('sem-qualidade', !r.linhas.some((l) => l.qualidade && l.qualidade > 1));
        trocar(lista, tab);
        nota.textContent = 'Os preços aqui são a última leitura do Mercado Negro; no jogo a decisão é refeita com o livro do momento.';
      } else {
        for (const c of [pago, receber, parada]) c.mostrar(null);
        trocar(lista, h('div', { class: 'cartao' }, vazio('caixa', 'Nenhuma compra do bot para vender',
          `Esta carga vem das compras do bot nas últimas ${r.horas} horas, com o preço pago por cada unidade. `
          + 'Para vender o que já está na mochila, use "Vender a mochila pelo mercado", acima.',
          { rotulo: 'Ir para Comprar', fazer: () => irPasso('comprar') })));
        nota.textContent = '';
      }

      resumoPasso('vender', r.unidades ? `${fmt(r.unidades)} unidades na carga` : 'sem carga');
      habilitar();
    }

    function habilitar() {
      const tem = ultimo && ultimo.linhas && ultimo.linhas.length;
      simular.disabled = deVerdade.disabled = !tem || !!app.rodando;
      simularMercado.disabled = venderMercado.disabled = !!app.rodando;
      porque.textContent = app.rodando ? 'Há uma operação em andamento.' : (tem ? '' : 'Sem carga para vender.');
    }

    async function executarMercado(real) {
      if (real) {
        const sim = await dialogo({
          titulo: 'Vender a mochila pelo mercado?',
          texto: 'Para cada linha da lista "Sell from Inventory", o bot cria a ordem de venda com a pilha inteira, '
            + '1 prata abaixo do menor preço da qualidade Normal. Não há piso de custo: o preço é o do mercado agora, '
            + 'e tudo o que a lista mostrar será posto à venda. F11 pausa, F12 para.',
          sim: 'Vender',
          tom: 'perigo',
        });
        if (!sim) return;
      }
      await app.rodar('vender_pelo_mercado', real);
    }

    async function executar(real) {
      if (real) {
        const sim = await dialogo({
          titulo: 'Vender no Mercado Negro?',
          dados: [['Itens', fmt(ultimo.linhas.length)], ['Unidades', fmt(ultimo.unidades)], ['Previsto', fmt(ultimo.previsto)]],
          texto: 'O que tiver comprador perto do alvo sai na hora; o resto entra na fila. Nada é vendido abaixo do custo. F11 pausa, F12 para.',
          sim: 'Vender',
          tom: 'perigo',
        });
        if (!sim) return;
      }
      await app.rodar('vender', real);
    }

    async function mostrar() {
      const a = await api('ajustes_atuais');
      const chave = String(a.valores.margem);
      if (chave !== lidosDosAjustes) {
        lidosDosAjustes = chave;
        margem.value = (a.valores.margem * 100).toLocaleString('pt-BR', { maximumFractionDigits: 1 });
      }

      calcular();
    }

    return { el, mostrar, aoRodar: habilitar };
  })();

  paineis.precos = precos;
  paineis.comprar = comprar;
  paineis.vender = vender;

  /* ------------------------------------------------------------------------ */

  TELAS.operacao = {
    titulo: 'Operação',
    subtitulo: 'ler os preços, comprar na cidade, vender no Mercado Negro',

    montar(el) {
      raiz = el;
      corpo = h('div');
      for (const p of Object.values(paineis)) corpo.append(p.el);
      raiz.append(montarPassos(), corpo);
    },

    mostrar(qual) {
      if (qual) passo = qual;
      irPasso(passo);
      // os resumos dos outros passos tambem, para o cabecalho dizer o que falta
      if (passo !== 'precos') api('mercados').then((d) => precos.resumir(d));
      api('estado').then((e) => {
        if (passo !== 'vender') resumoPasso('vender', e.carga ? `${fmt(e.carga)} unidades na carga` : 'sem carga');
        if (passo !== 'comprar') {
          const atual = passosEl.querySelector('[data-resumo="comprar"]').textContent.trim();
          if (!e.precos) resumoPasso('comprar', 'leia os preços primeiro');
          else if (!atual || atual === 'leia os preços primeiro') resumoPasso('comprar', 'ver o que comprar');
        }
      });
    },

    aoRodar(r) {
      for (const p of Object.values(paineis)) p.aoRodar && p.aoRodar(r);
    },
  };
})();
