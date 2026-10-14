/* ==========================================================================
   itens.js - o que negociar, em que grupo, e quanto de cada combinacao
   ========================================================================== */

'use strict';

(() => {

  let arvore = [];          // itens do jogo, por categoria e familia
  let cat = null;           // o catalogo atual
  const abertosEsq = new Set();
  const abertosDir = new Set();
  const marcadosEsq = new Set();
  const selecionados = new Set();
  let nivel = { nivel: 'tabela', alvo: null };

  let listaEsq, listaDir, buscaEsq, buscaDir, esconder, grupoDestino, acrescentar;
  let resumoEl, nomeSel, barraSel, contaSel, removerB, moverSel, desfazerB;
  let qtdTitulo, qtdGrade, qtdVoltar, todas, loteRotulos, loteQuanto, loteAlvo;

  /* --- esquerda: itens do jogo ---------------------------------------------- */

  function noCatalogo() {
    const s = new Set();
    if (cat) for (const g of cat.grupos) for (const i of g.itens) s.add(i.nome);
    return s;
  }

  function desenharEsquerda() {
    const tenho = noCatalogo();
    const filtro = buscaEsq.value.trim().toLowerCase();
    const abrirTudo = !!filtro;
    const frag = document.createDocumentFragment();

    const cabe = (i) => (!esconder.checked || !tenho.has(i)) && (!filtro || i.toLowerCase().includes(filtro));

    for (const c of arvore) {
      const fams = c.familias.map((f) => ({ ...f, visiveis: f.itens.filter(cabe) })).filter((f) => f.visiveis.length);
      if (!fams.length) continue;

      const total = fams.reduce((s, f) => s + f.visiveis.length, 0);
      const ja = fams.reduce((s, f) => s + f.visiveis.filter((i) => tenho.has(i)).length, 0);
      const chaveC = c.nome;
      const abertaC = abrirTudo || abertosEsq.has(chaveC);

      frag.append(no('cat', c.nome, `${ja}/${total}`, abertaC,
        () => alternar(abertosEsq, chaveC, desenharEsquerda),
        fams.flatMap((f) => f.visiveis), tenho));

      if (!abertaC) continue;

      for (const f of fams) {
        const raso = f.nome === null;
        let abertaF = true;

        if (!raso) {
          const chaveF = `${c.nome}/${f.nome}`;
          abertaF = abrirTudo || abertosEsq.has(chaveF);
          const jaF = f.visiveis.filter((i) => tenho.has(i)).length;
          frag.append(no('fam', f.nome, `${jaF}/${f.visiveis.length}`, abertaF,
            () => alternar(abertosEsq, chaveF, desenharEsquerda), f.visiveis, tenho));
        }

        if (!abertaF) continue;

        for (const i of f.visiveis) {
          const tem = tenho.has(i);
          const el = h('div', {
            class: `no folha${raso ? ' raso' : ''}${tem ? ' ja-tenho' : ''}${marcadosEsq.has(i) ? ' selecionado' : ''}`,
            role: 'option', 'aria-selected': marcadosEsq.has(i) ? 'true' : 'false',
            title: tem ? 'Já está no catálogo' : 'Clique para escolher',
            onclick: () => { if (!tem) { alternar(marcadosEsq, i, desenharEsquerda); } },
          }, h('span', {}, i), tem ? h('span', { class: 'conta tem' }, 'no catálogo') : null);
          frag.append(el);
        }
      }
    }

    trocar(listaEsq, frag.childNodes.length ? frag : h('div', { class: 'nota', style: { padding: '12px' } }, 'Nada encontrado.'));
    pintarAcrescentar();
  }

  // Uma categoria ou familia: a seta abre, o clique no nome escolhe tudo dela.
  function no(tipo, nome, conta, aberto, abrir, itens, tenho) {
    const livres = itens.filter((i) => !tenho.has(i));
    const todos = livres.length && livres.every((i) => marcadosEsq.has(i));
    const seta = h('button', { class: 'botao discreto icone pequeno', 'aria-label': aberto ? 'Fechar' : 'Abrir', onclick: (e) => { e.stopPropagation(); abrir(); } }, icone('seta'));
    seta.firstChild.classList.add('seta');
    return h('div', {
      class: `no ${tipo}${aberto ? ' aberto' : ''}${todos ? ' selecionado' : ''}`,
      title: livres.length ? 'Clique para escolher todos de uma vez' : 'Todos já estão no catálogo',
      onclick: () => {
        if (!livres.length) { abrir(); return; }
        for (const i of livres) { if (todos) marcadosEsq.delete(i); else marcadosEsq.add(i); }
        desenharEsquerda();
      },
    }, seta, h('span', {}, nome), h('span', { class: 'conta' }, conta));
  }

  function alternar(conjunto, chave, depois) {
    if (conjunto.has(chave)) conjunto.delete(chave); else conjunto.add(chave);
    depois();
  }

  function pintarAcrescentar() {
    const n = marcadosEsq.size;
    acrescentar.disabled = !n;
    acrescentar.textContent = n ? `Acrescentar ${n} →` : 'Acrescentar →';
    acrescentar.title = n ? '' : 'Escolha itens na lista acima';
  }

  async function fazerAcrescentar() {
    let grupo = grupoDestino.value;
    if (grupo === '__novo__') {
      grupo = await dialogo({ titulo: 'Novo grupo', texto: 'Cada grupo é uma viagem: o inventário tem limite.', campo: { dica: 'nome do grupo' }, sim: 'Criar' });
      if (!grupo) return;
    }
    const r = await api('acrescentar', [...marcadosEsq], grupo);
    marcadosEsq.clear();
    if (r.avisos && r.avisos.length) torrada(r.avisos[0], 'perigo');
    else torrada(`Acrescentados em "${grupo}".`, 'ok');
    abertosDir.add(grupo);
    receber(r);
  }

  /* --- direita: o catalogo ---------------------------------------------------- */

  function receber(r) {
    if (r && r.erro) { torrada(r.erro, 'perigo'); return; }
    cat = r;
    for (const s of [...selecionados]) if (![...noCatalogo()].includes(s)) selecionados.delete(s);
    desenharDireita();
    desenharEsquerda();
    carregarQuantidades();
    app.atualizarEstado();
  }

  function desenharDireita() {
    const r = cat.resumo;
    resumoEl.textContent = `${r.itens} itens · ${r.grupos} grupos · ${fmt(r.combinacoes)} combinações · ${fmt(r.unidades)} unidades · ≈ ${minutos(r.minutos)} por mercado`;

    trocar(nomeSel, cat.salvos.map((n) => h('option', { value: n }, n === 'padrao' ? 'padrão' : n)));
    nomeSel.value = cat.nome;

    // os grupos para onde mandar o que vem da esquerda
    const atualDestino = grupoDestino.value;
    trocar(grupoDestino, cat.grupos.map((g) => h('option', { value: g.nome }, g.nome)), h('option', { value: '__novo__' }, 'Novo grupo…'));
    grupoDestino.value = cat.grupos.some((g) => g.nome === atualDestino) ? atualDestino : (cat.grupos[0] ? cat.grupos[0].nome : '__novo__');

    trocar(moverSel, h('option', { value: '' }, 'Mover para…'), cat.grupos.map((g) => h('option', { value: g.nome }, g.nome)), h('option', { value: '__novo__' }, 'Novo grupo…'));

    const filtro = buscaDir.value.trim().toLowerCase();
    const frag = document.createDocumentFragment();

    if (!cat.grupos.length) {
      frag.append(vazio('itens', 'O catálogo está vazio', 'Escolha itens na lista ao lado e acrescente. Cada grupo é uma viagem.'));
    }

    for (const g of cat.grupos) {
      const itens = g.itens.filter((i) => !filtro || i.nome.toLowerCase().includes(filtro));
      if (filtro && !itens.length) continue;

      const aberto = !!filtro || abertosDir.has(g.nome);
      const ehNivel = nivel.nivel === 'grupo' && nivel.alvo === g.nome;
      const seta = h('button', { class: 'botao discreto icone pequeno', 'aria-label': aberto ? 'Fechar' : 'Abrir', onclick: (e) => { e.stopPropagation(); alternar(abertosDir, g.nome, desenharDireita); } }, icone('seta'));
      seta.firstChild.classList.add('seta');

      frag.append(h('div', {
        class: `no cat${aberto ? ' aberto' : ''}${ehNivel ? ' selecionado' : ''}`,
        title: 'Clique para ajustar as quantidades deste grupo',
        onclick: () => definirNivel('grupo', g.nome),
      },
      seta,
      h('span', {}, g.nome),
      g.proprio ? h('span', { class: 'marca-propria', title: 'Este grupo tem quantidades próprias' }) : null,
      h('span', { class: 'conta' }, g.itens.length),
      h('button', { class: 'botao discreto icone pequeno', title: 'Renomear', 'aria-label': `Renomear ${g.nome}`, onclick: (e) => { e.stopPropagation(); renomear(g.nome); } }, icone('lapis')),
      h('button', { class: 'botao discreto icone pequeno', title: 'Excluir grupo', 'aria-label': `Excluir ${g.nome}`, onclick: (e) => { e.stopPropagation(); excluir(g); } }, icone('lixo'))));

      if (!aberto) continue;

      for (const i of itens) {
        const marcado = selecionados.has(i.nome);
        const caixa = h('input', { type: 'checkbox', 'aria-label': `Selecionar ${i.nome}`, onclick: (e) => e.stopPropagation(), onchange: () => { alternar(selecionados, i.nome, () => { desenharDireita(); }); } });
        caixa.checked = marcado;
        frag.append(h('div', {
          class: `no folha raso${(nivel.nivel === 'item' && nivel.alvo === i.nome) ? ' selecionado' : ''}`,
          title: 'Clique para ajustar as quantidades deste item',
          onclick: () => definirNivel('item', i.nome),
        }, h('label', { class: 'marcar', onclick: (e) => e.stopPropagation() }, caixa),
        h('span', {}, i.nome),
        i.proprio ? h('span', { class: 'marca-propria', title: 'Este item tem quantidades próprias' }) : null));
      }
    }

    trocar(listaDir, frag);

    const n = selecionados.size;
    contaSel.textContent = n ? `${n} selecionado${n > 1 ? 's' : ''}` : 'Marque itens para mover ou remover';
    // O QUE NAO DA PARA FAZER SOME, em vez de ficar apagado a espera
    removerB.classList.toggle('oculto', !n);
    moverSel.classList.toggle('oculto', !n);
    desfazerB.classList.toggle('oculto', !cat.desfazer);
  }

  async function renomear(nome) {
    const novo = await dialogo({ titulo: 'Renomear grupo', campo: { valor: nome }, sim: 'Renomear' });
    if (!novo || novo === nome) return;
    abertosDir.add(novo);
    if (nivel.nivel === 'grupo' && nivel.alvo === nome) nivel.alvo = novo;
    receber(await api('renomear_grupo', nome, novo));
  }

  async function excluir(g) {
    const outros = cat.grupos.filter((x) => x.nome !== g.nome);
    let destino = null;

    if (g.itens.length) {
      const resposta = await dialogo({
        titulo: `Excluir "${g.nome}"?`,
        texto: outros.length
          ? `Os ${g.itens.length} itens dele vão para "${outros[0].nome}". Para tirá-los do catálogo, remova os itens antes.`
          : `É o único grupo: os ${g.itens.length} itens saem do catálogo junto, e isso não tem desfazer.`,
        sim: 'Excluir',
        tom: 'perigo',
      });
      if (!resposta) return;
      destino = outros.length ? outros[0].nome : null;
    }

    if (nivel.alvo === g.nome) nivel = { nivel: 'tabela', alvo: null };
    receber(await api('apagar_grupo', g.nome, destino));
  }

  async function remover() {
    const itens = [...selecionados];
    selecionados.clear();
    receber(await api('remover', itens));
    torrada(`${itens.length} removido${itens.length > 1 ? 's' : ''}. Dá para desfazer.`);
  }

  async function mover(grupo) {
    moverSel.value = '';
    if (grupo === '__novo__') {
      grupo = await dialogo({ titulo: 'Novo grupo', campo: { dica: 'nome do grupo' }, sim: 'Criar e mover' });
      if (!grupo) return;
    }
    const itens = [...selecionados];
    selecionados.clear();
    abertosDir.add(grupo);
    receber(await api('mover', itens, grupo));
  }

  /* --- quantidades -------------------------------------------------------------
     Tres niveis, cada um por cima do anterior: todos os itens, o grupo, o item.
     Num grupo ou item, o campo vazio volta a herdar. */

  function definirNivel(n, alvo) {
    nivel = (nivel.nivel === n && nivel.alvo === alvo) ? { nivel: 'tabela', alvo: null } : { nivel: n, alvo };
    desenharDireita();
    carregarQuantidades();
  }

  async function carregarQuantidades() {
    const r = await api('quantidades', nivel.nivel, nivel.alvo);
    desenharQuantidades(r);
  }

  function desenharQuantidades(r) {
    nivel = { nivel: r.nivel, alvo: r.alvo };
    qtdTitulo.textContent = r.nivel === 'item' ? `Item: ${r.alvo}` : r.nivel === 'grupo' ? `Grupo: ${r.alvo}` : 'Todos os itens';
    qtdVoltar.classList.toggle('oculto', r.nivel === 'tabela');

    trocar(qtdGrade, r.quantidades.map((q) => {
      const proprio = r.nivel !== 'tabela' && q.proprio;
      const entrada = h('input', {
        class: `entrada${proprio ? ' propria' : ''}${q.valor === 0 ? ' zero' : ''}`,
        inputmode: 'numeric',
        value: (r.nivel === 'tabela' || proprio) ? q.valor : '',
        placeholder: r.nivel === 'tabela' ? '0' : q.herdado,
        title: r.nivel === 'tabela' ? '' : (proprio ? `Próprio. Apague para voltar a ${q.herdado}.` : `Herdado: ${q.herdado}`),
        'aria-label': `Quantidade de ${q.rotulo}`,
      });
      entrada.addEventListener('change', async () => {
        const texto = entrada.value.trim();
        const valor = texto === '' ? (r.nivel === 'tabela' ? '0' : null) : texto;
        const resposta = await api('definir_quantidade', r.nivel, r.alvo, q.rotulo, valor);
        if (resposta.erro) { entrada.classList.add('invalida'); torrada(resposta.erro, 'perigo'); return; }
        desenharQuantidades(resposta);
        recarregarCatalogo();
      });
      return h('div', { class: 'quantidade' }, h('label', {}, q.rotulo), entrada);
    }));
  }

  async function recarregarCatalogo() {
    cat = await api('catalogo_atual');
    desenharDireita();
    app.atualizarEstado();
  }

  async function aplicarTodas() {
    const valor = todas.value.trim();
    if (!valor) return;
    const r = await api('definir_todas', nivel.nivel, nivel.alvo, valor);
    if (r.erro) { torrada(r.erro, 'perigo'); return; }
    todas.value = '';
    desenharQuantidades(r);
    recarregarCatalogo();
  }

  async function aplicarLote() {
    const itens = loteAlvo.value === 'selecionados' ? [...selecionados] : null;
    if (loteAlvo.value === 'selecionados' && !itens.length) { torrada('Marque itens no catálogo primeiro.', 'perigo'); return; }
    const r = await api('em_lote', loteRotulos.value, loteQuanto.value, itens);
    if (r.erro) { torrada(r.erro, 'perigo'); return; }
    torrada(r.feito, 'ok');
    receber(r);
  }

  /* --- montagem ----------------------------------------------------------------- */

  function montar(el) {
    buscaEsq = h('input', { class: 'entrada', placeholder: 'Procurar um item do jogo', 'aria-label': 'Procurar um item do jogo' });
    buscaEsq.addEventListener('input', desenharEsquerda);
    buscaEsq.addEventListener('keydown', (e) => { if (e.key === 'Escape') { buscaEsq.value = ''; desenharEsquerda(); } });
    esconder = h('input', { type: 'checkbox' });
    esconder.addEventListener('change', desenharEsquerda);
    listaEsq = h('div', { class: 'lista-arvore', role: 'listbox', 'aria-multiselectable': 'true' });
    grupoDestino = h('select', { class: 'entrada', style: { flex: '1', minWidth: '0', maxWidth: '240px' }, 'aria-label': 'Grupo de destino' });
    acrescentar = h('button', { class: 'botao principal-acao', onclick: fazerAcrescentar }, 'Acrescentar →');

    const esquerda = cartao('Itens do jogo',
      h('div', { class: 'linha' }, h('div', { class: 'busca' }, icone('busca'), buscaEsq)),
      h('label', { class: 'marcar', style: { marginTop: '10px' } }, esconder, 'Esconder os que já estão no catálogo'),
      listaEsq,
      h('div', { class: 'linha', style: { marginTop: '12px', flexWrap: 'nowrap' } }, h('span', { class: 'fraco' }, 'no grupo'), grupoDestino, h('span', { class: 'empurra' }), acrescentar));

    nomeSel = h('select', { class: 'entrada', 'aria-label': 'Catálogo' });
    nomeSel.addEventListener('change', async () => receber(await api('abrir_catalogo', nomeSel.value)));
    const salvarComo = h('button', {
      class: 'botao discreto pequeno', onclick: async () => {
        const nome = await dialogo({ titulo: 'Salvar como', texto: 'Uma cópia deste catálogo com outro nome. As mudanças passam a valer nela.', campo: { dica: 'nome do catálogo' }, sim: 'Salvar' });
        if (nome) receber(await api('salvar_catalogo_como', nome));
      },
    }, 'Salvar como…');

    buscaDir = h('input', { class: 'entrada', placeholder: 'Procurar no catálogo', 'aria-label': 'Procurar no catálogo' });
    buscaDir.addEventListener('input', desenharDireita);
    buscaDir.addEventListener('keydown', (e) => { if (e.key === 'Escape') { buscaDir.value = ''; desenharDireita(); } });
    listaDir = h('div', { class: 'lista-arvore' });
    resumoEl = h('div', { class: 'nota', style: { marginTop: '8px' } });
    contaSel = h('span', { class: 'nota' });
    removerB = h('button', { class: 'botao perigo-acao pequeno', onclick: remover }, 'Remover');
    moverSel = h('select', { class: 'entrada', style: { height: '30px', width: 'auto' }, 'aria-label': 'Mover para' });
    moverSel.addEventListener('change', () => moverSel.value && mover(moverSel.value));
    desfazerB = h('button', { class: 'botao discreto pequeno', onclick: async () => receber(await api('desfazer')) }, icone('desfazer'), 'Desfazer');
    const novoGrupo = h('button', {
      class: 'botao discreto pequeno', onclick: async () => {
        const nome = await dialogo({ titulo: 'Novo grupo', texto: 'Cada grupo é uma viagem: o inventário tem limite.', campo: { dica: 'nome do grupo' }, sim: 'Criar' });
        if (nome) { abertosDir.add(nome); receber(await api('criar_grupo', nome)); }
      },
    }, icone('mais'), 'Novo grupo');

    barraSel = h('div', { class: 'linha barra-selecao' }, contaSel, h('span', { class: 'empurra' }), desfazerB, moverSel, removerB);

    const direita = cartao(null,
      h('div', { class: 'linha' }, h('h2', { style: { margin: 0, font: '700 15px/1.3 var(--fonte-titulo)' } }, 'Seu catálogo'), h('span', { class: 'empurra' }), nomeSel, salvarComo),
      resumoEl,
      h('div', { class: 'linha', style: { marginTop: '12px', flexWrap: 'nowrap' } }, h('div', { class: 'busca' }, icone('busca'), buscaDir), novoGrupo),
      listaDir,
      barraSel);

    qtdTitulo = h('strong');
    qtdVoltar = h('button', { class: 'botao discreto pequeno oculto', onclick: () => { nivel = { nivel: 'tabela', alvo: null }; desenharDireita(); carregarQuantidades(); } }, '← Voltar para todos os itens');
    qtdGrade = h('div', { class: 'quantidades' });
    todas = h('input', { class: 'entrada curta', inputmode: 'numeric', 'aria-label': 'Quantidade para todas as combinações' });
    todas.addEventListener('keydown', (e) => e.key === 'Enter' && aplicarTodas());
    loteRotulos = h('input', { class: 'entrada', style: { width: '140px' }, placeholder: 'ex.: T8.3, T7.2', 'aria-label': 'Combinações' });
    loteQuanto = h('input', { class: 'entrada curta', inputmode: 'numeric', value: '0', 'aria-label': 'Quantidade' });
    loteAlvo = seletor([['todos', 'em todos os itens'], ['selecionados', 'nos itens marcados']], 'todos');

    const quantidades = cartao(null,
      h('div', { class: 'linha' }, h('h2', { style: { margin: 0, font: '700 15px/1.3 var(--fonte-titulo)' } }, 'Quanto comprar de cada combinação'),
        h('span', { class: 'nivel' }, h('span', { class: 'fraco' }, '·'), qtdTitulo), qtdVoltar),
      h('p', { class: 'nota', style: { margin: '6px 0 14px' } },
        'Clique num grupo ou num item do catálogo para mudar só ele — campo vazio herda. Zero não lê a combinação.'),
      qtdGrade,
      h('div', { class: 'ferramentas-qtd' },
        h('div', { class: 'linha' },
          h('span', { class: 'fraco' }, 'Pôr'), todas, h('span', { class: 'fraco' }, 'em todas as combinações acima'),
          h('button', { class: 'botao pequeno', onclick: aplicarTodas }, 'Aplicar')),
        h('div', { class: 'linha' },
          h('span', { class: 'fraco' }, 'Mudar só'), loteRotulos, h('span', { class: 'fraco' }, 'para'), loteQuanto, loteAlvo,
          h('button', { class: 'botao pequeno', onclick: aplicarLote }, 'Aplicar'))));

    el.append(h('div', { class: 'pilha' }, h('div', { class: 'itens' }, esquerda, direita), quantidades));
  }

  TELAS.itens = {
    titulo: 'Itens',
    subtitulo: 'o que negociar, em que grupo, e quanto de cada combinação',
    montar,
    async mostrar() {
      if (!arvore.length) arvore = await api('itens_do_jogo');
      cat = await api('catalogo_atual');
      if (!abertosDir.size && cat.grupos[0]) abertosDir.add(cat.grupos[0].nome);
      desenharDireita();
      desenharEsquerda();
      carregarQuantidades();
    },
  };
})();
