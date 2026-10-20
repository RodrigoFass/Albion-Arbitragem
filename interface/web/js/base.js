/* ==========================================================================
   base.js - pecas que todas as telas usam
   ========================================================================== */

'use strict';

/* --- DOM ------------------------------------------------------------------ */

// h('div', {class: 'x', onclick: f}, filho, 'texto', [mais, filhos])
function h(tag, props, ...filhos) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k === 'style' && typeof v === 'object') Object.assign(el.style, v);
    else if (k.startsWith('on')) el.addEventListener(k.slice(2), v);
    else if (k === 'html') el.innerHTML = v;
    else if (v === true) el.setAttribute(k, '');
    else el.setAttribute(k, v);
  }
  colocar(el, filhos);
  return el;
}

function colocar(el, filhos) {
  for (const f of filhos.flat(Infinity)) {
    if (f === null || f === undefined || f === false) continue;
    el.append(f instanceof Node ? f : document.createTextNode(String(f)));
  }
  return el;
}

function trocar(el, ...filhos) {
  el.replaceChildren();
  return colocar(el, filhos);
}

/* --- icones (traco, 24x24) ---------------------------------------------- */

const ICONES = {
  operacao: '<path d="M4 17l5-5 4 4 7-8"/><path d="M15 8h5v5"/>',
  itens: '<path d="M21 8l-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/><path d="M12 13v8"/>',
  historico: '<path d="M3 12a9 9 0 1 0 3-6.7"/><path d="M3 4v4h4"/><path d="M12 7v5l3 2"/>',
  ajustes: '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
  terminal: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 9l3 3-3 3M13 15h4"/>',
  fechar: '<path d="M6 6l12 12M18 6L6 18"/>',
  recolher: '<path d="M15 6l-6 6 6 6"/>',
  seta: '<path d="M9 6l6 6-6 6"/>',
  busca: '<circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4-4"/>',
  caixa: '<path d="M21 8l-9-5-9 5 9 5 9-5z"/><path d="M3 8v8l9 5 9-5V8"/>',
  moeda: '<circle cx="12" cy="12" r="8.5"/><path d="M14.5 9.5c-.5-1-1.5-1.5-2.5-1.5-1.4 0-2.5.8-2.5 2s1 1.7 2.5 2 2.5.8 2.5 2-1.1 2-2.5 2c-1 0-2-.5-2.5-1.5M12 6.5V8M12 16v1.5"/>',
  relogio: '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
  desfazer: '<path d="M9 14L4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 0 12h-3"/>',
  lixo: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  lapis: '<path d="M4 20h4L19 9l-4-4L4 16v4z"/>',
  mais: '<path d="M12 5v14M5 12h14"/>',
  pasta: '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/>',
  alvo: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="3.5"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
  negro: '<path d="M12 3l7 9-7 9-7-9 7-9z"/>',
};

function icone(nome, tamanho) {
  const el = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  el.setAttribute('viewBox', '0 0 24 24');
  el.setAttribute('fill', 'none');
  el.setAttribute('stroke', 'currentColor');
  el.setAttribute('stroke-width', '1.8');
  el.setAttribute('stroke-linecap', 'round');
  el.setAttribute('stroke-linejoin', 'round');
  el.setAttribute('aria-hidden', 'true');
  if (tamanho) { el.style.width = el.style.height = tamanho + 'px'; }
  el.innerHTML = ICONES[nome] || '';
  return el;
}

/* --- numeros ------------------------------------------------------------- */

const _int = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 0 });
const _dec = new Intl.NumberFormat('pt-BR', { maximumFractionDigits: 1, minimumFractionDigits: 1 });

const fmt = (n) => (n === null || n === undefined || Number.isNaN(n)) ? '—' : _int.format(Math.round(n));
const pct = (x, casas = 1) => (x === null || x === undefined) ? '—' :
  (x * 100).toLocaleString('pt-BR', { maximumFractionDigits: casas, minimumFractionDigits: casas }) + '%';
const horas = (h) => (h === null || h === undefined) ? '' :
  h < 1 ? `${Math.max(1, Math.round(h * 60))} min` : `${_dec.format(h)} h`;
const minutos = (m) => m < 1 ? 'menos de 1 min' : m < 90 ? `${Math.round(m)} min` : `${_dec.format(m / 60)} h`;

/* --- a ponte com o Python ------------------------------------------------ */

const _pronta = new Promise((ok) => {
  if (window.pywebview && window.pywebview.api) ok();
  else window.addEventListener('pywebviewready', ok, { once: true });
});

async function api(nome, ...args) {
  await _pronta;
  try {
    return await window.pywebview.api[nome](...args);
  } catch (e) {
    const texto = (e && e.message) || String(e);
    torrada(`Algo deu errado: ${texto}`, 'perigo');
    try { window.pywebview.api.erro_js(`${nome}: ${texto}`); } catch (_) { /* nada */ }
    throw e;
  }
}

window.addEventListener('error', (e) => {
  _pronta.then(() => window.pywebview.api.erro_js(`${e.message} @ ${e.filename}:${e.lineno}`));
});
window.addEventListener('unhandledrejection', (e) => {
  _pronta.then(() => window.pywebview.api.erro_js(`promessa: ${e.reason && (e.reason.message || e.reason)}`));
});

/* --- mola: movimento que parte de onde esta e pode ser interrompido -------
   Criticamente amortecida (sem quique) por padrao. Um novo alvo no meio do
   caminho continua da posicao e da velocidade atuais - nao ha salto. Com
   "reduzir movimento" ligado, vai direto ao alvo. */

const reduzirMovimento = matchMedia('(prefers-reduced-motion: reduce)');

class Mola {
  constructor(valor, aoQuadro, { resposta = 0.35, amortecimento = 1 } = {}) {
    this.valor = valor;
    this.alvo = valor;
    this.velocidade = 0;
    this.aoQuadro = aoQuadro;
    this.k = Math.pow((2 * Math.PI) / resposta, 2);
    this.c = 2 * amortecimento * Math.sqrt(this.k);
    this._quadro = null;
    this._fim = null;
    aoQuadro(valor);
  }

  ir(alvo, aoFim) {
    this.alvo = alvo;
    this._fim = aoFim || null;

    if (reduzirMovimento.matches) {
      this.valor = alvo;
      this.velocidade = 0;
      this.aoQuadro(alvo);
      this._acabar();
      return;
    }

    if (this._quadro) return;

    let antes = performance.now();
    const passo = (agora) => {
      let dt = Math.min(0.032, (agora - antes) / 1000);
      antes = agora;
      // em pedacos pequenos, para a conta nao divergir com quadro lento
      while (dt > 0) {
        const d = Math.min(dt, 1 / 240);
        const a = -this.k * (this.valor - this.alvo) - this.c * this.velocidade;
        this.velocidade += a * d;
        this.valor += this.velocidade * d;
        dt -= d;
      }
      this.aoQuadro(this.valor);
      if (Math.abs(this.valor - this.alvo) < 0.001 && Math.abs(this.velocidade) < 0.01) {
        this.valor = this.alvo;
        this.aoQuadro(this.valor);
        this._quadro = null;
        this._acabar();
      } else {
        this._quadro = requestAnimationFrame(passo);
      }
    };
    this._quadro = requestAnimationFrame(passo);
  }

  _acabar() {
    const f = this._fim;
    this._fim = null;
    if (f) f();
  }
}

/* --- avisos rapidos ------------------------------------------------------ */

function torrada(texto, tom = '') {
  const el = h('div', { class: `torrada ${tom}`, role: 'status' }, texto);
  document.getElementById('torradas').append(el);
  setTimeout(() => {
    el.style.transition = 'opacity 200ms ease-out';
    el.style.opacity = '0';
    setTimeout(() => el.remove(), 220);
  }, tom === 'perigo' ? 6000 : 3200);
}

/* --- dialogo -------------------------------------------------------------
   Modal de verdade: escurece o fundo (foco), nasce do botao que o abriu e
   volta para ele. Esc e clique fora cancelam. So para o que precisa de uma
   decisao - confirmacao demais ensina a clicar sem ler. */

let _ultimoClique = null;
document.addEventListener('pointerdown', (e) => {
  const b = e.target.closest('button');
  if (b) _ultimoClique = b.getBoundingClientRect();
}, true);

function dialogo({ titulo, texto, dados, lista, campo, sim = 'OK', nao = 'Cancelar', tom = '' }) {
  return new Promise((resolver) => {
    const origem = _ultimoClique;
    let entrada = null;

    const caixa = h('div', { class: 'dialogo', role: 'dialog', 'aria-modal': 'true', 'aria-label': titulo });
    caixa.append(h('h3', {}, titulo));
    if (texto) caixa.append(h('div', { class: 'texto' }, texto));
    if (lista && lista.length) caixa.append(h('div', { class: 'texto' }, h('ul', {}, lista.map((l) => h('li', {}, l)))));
    if (dados) {
      caixa.append(h('dl', { class: 'dados' }, dados.flatMap(([k, v]) => [h('dt', {}, k), h('dd', {}, v)])));
    }
    if (campo) {
      entrada = h('input', { class: 'entrada', value: campo.valor || '', placeholder: campo.dica || '', maxlength: 60 });
      caixa.append(entrada);
    }

    const botoes = h('div', { class: 'botoes' });
    const bNao = nao ? h('button', { class: 'botao discreto' }, nao) : null;
    const bSim = h('button', { class: `botao ${tom === 'perigo' ? 'perigo-cheio' : 'principal-acao'}` }, sim);
    if (bNao) botoes.append(bNao);
    botoes.append(bSim);
    caixa.append(botoes);

    const veu = h('div', { class: 'veu' }, caixa);
    document.body.append(veu);

    const foco = document.activeElement;

    // nasce do botao: a escala parte do ponto de onde ele foi pedido
    if (origem) {
      const r = caixa.getBoundingClientRect();
      caixa.style.transformOrigin =
        `${origem.left + origem.width / 2 - r.left}px ${origem.top + origem.height / 2 - r.top}px`;
    }

    const mola = new Mola(0, (v) => {
      veu.style.opacity = Math.min(1, Math.max(0, v));
      caixa.style.transform = `scale(${0.92 + 0.08 * v})`;
    }, { resposta: 0.3 });
    mola.ir(1);

    (entrada || bSim).focus();

    const fechar = (resposta) => {
      document.removeEventListener('keydown', tecla, true);
      mola.ir(0, () => veu.remove());
      veu.style.pointerEvents = 'none';
      if (foco && foco.focus) foco.focus();
      resolver(resposta);
    };

    const tecla = (e) => {
      if (e.key === 'Escape') { e.preventDefault(); fechar(null); }
      if (e.key === 'Enter' && (entrada || document.activeElement === bSim)) { e.preventDefault(); fechar(entrada ? entrada.value : true); }
    };
    document.addEventListener('keydown', tecla, true);

    bSim.addEventListener('click', () => fechar(entrada ? entrada.value : true));
    if (bNao) bNao.addEventListener('click', () => fechar(null));
    veu.addEventListener('pointerdown', (e) => { if (e.target === veu) fechar(null); });
  });
}

/* --- pecas de tela --------------------------------------------------------- */

function cartao(titulo, ...filhos) {
  return h('section', { class: 'cartao' }, titulo ? h('h2', {}, titulo) : null, ...filhos);
}

// Um numero grande com nome e legenda. .mostrar(valor, legenda, tom)
function numero(nome) {
  const valor = h('div', { class: 'valor' }, '—');
  const legenda = h('div', { class: 'legenda' }, ' ');
  const el = h('div', { class: 'cartao numero sem-valor' }, h('div', { class: 'nome' }, nome), valor, legenda);
  el.mostrar = (v, l, tom) => {
    const nada = v === null || v === undefined || v === '—';
    el.classList.toggle('sem-valor', nada);
    valor.textContent = nada ? '—' : v;
    valor.className = 'valor' + (tom ? ' ' + tom : '');
    legenda.textContent = l || ' ';
  };
  return el;
}

function vazio(iconeNome, titulo, texto, acao) {
  return h('div', { class: 'vazio' },
    icone(iconeNome),
    h('strong', {}, titulo),
    texto ? h('p', {}, texto) : null,
    acao ? h('button', { class: 'botao principal-acao', onclick: acao.fazer }, acao.rotulo) : null);
}

function segmentado(opcoes, valor, aoMudar) {
  const el = h('div', { class: 'segmentado', role: 'group' });
  const pintar = (v) => {
    for (const b of el.children) b.setAttribute('aria-pressed', b.dataset.valor === v ? 'true' : 'false');
  };
  for (const [v, rotulo] of opcoes) {
    el.append(h('button', { type: 'button', 'data-valor': v, onclick: () => { pintar(v); el.valor = v; aoMudar(v); } }, rotulo));
  }
  el.valor = valor;
  el.definir = (v) => { el.valor = v; pintar(v); };
  pintar(valor);
  return el;
}

function seletor(opcoes, valor, aoMudar, props = {}) {
  const el = h('select', Object.assign({ class: 'entrada' }, props));
  for (const op of opcoes) {
    const [v, rotulo] = Array.isArray(op) ? op : [op, op];
    el.append(h('option', { value: v }, rotulo));
  }
  el.value = valor;
  if (aoMudar) el.addEventListener('change', () => aoMudar(el.value));
  return el;
}

function campo(rotulo, controle, sufixo) {
  return h('div', { class: 'campo' },
    h('label', {}, rotulo),
    sufixo ? h('div', { class: 'junto' }, controle, h('span', {}, sufixo)) : controle);
}

// um numero com a unidade DENTRO do campo ("23 %", "sem limite prata"): todos
// da mesma largura, como nos Ajustes
function comUnidade(input, unidade) {
  return h('div', { class: 'com-unidade', onclick: () => input.focus() }, input, unidade ? h('span', {}, unidade) : null);
}

function chave(titulo, dica, ligado, aoMudar) {
  const input = h('input', { type: 'checkbox' });
  input.checked = !!ligado;
  input.addEventListener('change', () => aoMudar && aoMudar(input.checked));
  const el = h('label', { class: 'chave' }, input, h('span', { class: 'trilho' }),
    h('span', {}, h('strong', {}, titulo), dica ? h('small', {}, dica) : null));
  el.input = input;
  return el;
}

/* --- tabela ---------------------------------------------------------------
   colunas: [{chave, titulo, direita, formato(v, linha), classe, ordenar}]
   Clique no cabecalho ordena; a numeracao segue a ordem na tela. */

function tabela(colunas, { numerada = true, aoOrdenar } = {}) {
  const thead = h('thead');
  const tbody = h('tbody');
  const caixa = h('div', { class: 'tabela-caixa' }, h('table', { class: 'tabela' }, thead, tbody));
  let linhas = [];
  let ordem = null;

  const cab = h('tr');
  if (numerada) cab.append(h('th', { class: 'n' }, '#'));
  for (const c of colunas) {
    const th = h('th', { class: (c.direita ? 'd ' : '') + (c.ordenar !== false ? 'ordenavel' : ''), 'data-col': c.chave }, c.titulo);
    if (c.ordenar !== false) {
      th.addEventListener('click', () => {
        const desc = ordem && ordem.chave === c.chave ? !ordem.desc : !!c.direita;
        ordem = { chave: c.chave, desc };
        for (const t of cab.children) t.removeAttribute('aria-sort');
        th.setAttribute('aria-sort', desc ? 'descending' : 'ascending');
        desenhar();
        if (aoOrdenar) aoOrdenar(ordem);
      });
    }
    cab.append(th);
  }
  thead.append(cab);

  function desenhar() {
    let vista = linhas;
    if (ordem) {
      const { chave: k, desc } = ordem;
      vista = [...linhas].sort((a, b) => {
        const x = a[k], y = b[k];
        const r = typeof x === 'number' && typeof y === 'number' ? x - y : String(x ?? '').localeCompare(String(y ?? ''), 'pt-BR');
        return desc ? -r : r;
      });
    }
    const frag = document.createDocumentFragment();
    vista.forEach((l, i) => {
      const tr = h('tr');
      if (numerada) tr.append(h('td', { class: 'n' }, i + 1));
      for (const c of colunas) {
        const v = c.formato ? c.formato(l[c.chave], l) : l[c.chave];
        tr.append(h('td', { class: (c.direita ? 'd ' : '') + (c.classe || ''), 'data-col': c.chave }, v ?? ''));
      }
      frag.append(tr);
    });
    tbody.replaceChildren(frag);
  }

  caixa.encher = (novas) => { linhas = novas || []; desenhar(); };
  return caixa;
}

/* as telas se registram aqui: TELAS.nome = {titulo, subtitulo, montar(el), mostrar()} */
const TELAS = {};

/* a leitura pela rede em uma frase: o que esta acontecendo e o que fazer */
function textoDaRede(s) {
  if (!s.ligada) return ['Desligada: a leitura é pela tela, com OCR.', ''];
  if (s.recebendo) {
    return [`Recebendo: último pacote há ${s.ha_segundos} s, de ${s.local}. `
      + `${fmt(s.ordens)} ofertas recebidas desde que o bot abriu.`, 'ok'];
  }
  if (s.mensagem) return [s.mensagem, 'aviso'];
  if (s.cliente === 'rodando') {
    return ['Cliente aberto, esperando o primeiro pacote. No jogo, troque de mapa uma vez '
      + '(é assim que o cliente descobre onde você está) e abra um item no mercado. '
      + 'Com ExitLag, VPN ou afins ligados nenhum pacote chega: feche o programa e reabra o jogo.', ''];
  }
  return ['Ligando…', ''];
}


// a mesma coisa em poucas palavras, para caber numa pilula: [texto, tom]
function curtoDaRede(s) {
  if (!s || !s.ligada) return ['Rede desligada', 'desligado'];
  if (s.recebendo) return [`Rede · ${s.local || 'recebendo'}`, 'ok'];
  if (s.mensagem) return ['Rede com problema', 'aviso'];
  if (s.cliente === 'rodando') return ['Rede · esperando o jogo', 'esperando'];
  return ['Rede · ligando…', 'esperando'];
}

/* os nomes do jogo em portugues; vazio = qualquer qualidade (a Normal de sempre) */
const QUALIDADES = { 1: 'Normal', 2: 'Bom', 3: 'Excepcional', 4: 'Excelente', 5: 'Obra-prima' };
const nomeDaQualidade = (q) => (q ? QUALIDADES[q] || q : '—');
