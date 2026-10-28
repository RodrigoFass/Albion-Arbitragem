/* ==========================================================================
   app.js - a casca: navegacao, tema, gaveta do Andamento, barra da operacao
   ========================================================================== */

'use strict';

const ORDEM = [
  ['operacao', 'Operação', 'operacao'],
  ['itens', 'Itens', 'itens'],
  ['royal', 'Craft Royal', 'coroa'],
  ['historico', 'Histórico', 'historico'],
  ['ajustes', 'Ajustes', 'ajustes'],
];

const app = {
  estado: null,
  atual: null,
  rodando: null,
  montadas: {},
  logNovo: 0,
  logAberto: false,
};

window.app = app;

/* --- tema ------------------------------------------------------------------ */

const sistemaEscuro = matchMedia('(prefers-color-scheme: dark)');

app.aplicarTema = (tema) => {
  app.tema = tema;
  const efetivo = tema === 'sistema' ? (sistemaEscuro.matches ? 'escuro' : 'claro') : tema;
  document.documentElement.dataset.tema = efetivo === 'claro' ? 'claro' : 'escuro';
};
sistemaEscuro.addEventListener('change', () => app.tema === 'sistema' && app.aplicarTema('sistema'));

/* --- navegacao ----------------------------------------------------------- */

function montarNav() {
  const nav = document.getElementById('nav');
  for (const [chave, nome, ic] of ORDEM) {
    nav.append(h('button', { 'data-tela': chave, title: nome, onclick: () => app.ir(chave) },
      icone(ic), h('span', {}, nome), h('span', { class: 'selo oculto', 'data-selo': chave })));
  }
}

app.ir = (chave, ...args) => {
  const tela = TELAS[chave];
  if (!tela) return;

  const anterior = TELAS[app.atual];
  if (anterior && anterior.aoSair && app.atual !== chave) anterior.aoSair();

  for (const b of document.querySelectorAll('#nav button')) {
    if (b.dataset.tela === chave) b.setAttribute('aria-current', 'page');
    else b.removeAttribute('aria-current');
  }

  const conteudo = document.getElementById('conteudo');

  if (!app.montadas[chave]) {
    const el = h('div', { class: 'tela', 'data-tela': chave });
    tela.montar(el);
    app.montadas[chave] = el;
  }

  for (const [k, el] of Object.entries(app.montadas)) el.classList.toggle('oculto', k !== chave);
  if (!app.montadas[chave].isConnected) conteudo.append(app.montadas[chave]);

  app.atual = chave;
  document.getElementById('titulo').textContent = tela.titulo;
  document.getElementById('subtitulo').textContent = tela.subtitulo || '';
  conteudo.scrollTop = 0;

  try { localStorage.setItem('tela', chave); } catch (_) { /* nada */ }

  tela.mostrar && tela.mostrar(...args);
};

app.atualizarEstado = async () => {
  const e = await api('estado');
  app.estado = e;

  document.getElementById('pe-catalogo').textContent =
    `${e.catalogo.itens} itens · ${fmt(e.precos)} preços`;
  document.getElementById('pe-versao').textContent = `versão ${e.versao}`;

  const seloItens = document.querySelector('[data-selo="itens"]');
  seloItens.textContent = e.catalogo.itens;
  seloItens.classList.toggle('oculto', !e.catalogo.itens);

  const seloOp = document.querySelector('[data-selo="operacao"]');
  seloOp.textContent = e.carga ? `${e.carga} na carga` : '';
  seloOp.classList.toggle('oculto', !e.carga);

  return e;
};

/* --- lateral recolhivel ---------------------------------------------------- */

function montarRecolher() {
  const casca = document.getElementById('casca');
  const botao = document.getElementById('recolher');
  botao.append(icone('recolher', 18));

  const aplicar = (recolhida) => {
    casca.classList.toggle('recolhida', recolhida);
    botao.title = recolhida ? 'Abrir a lateral' : 'Recolher a lateral';
    botao.setAttribute('aria-label', botao.title);
  };

  let recolhida = false;
  try { recolhida = localStorage.getItem('lateral') === 'recolhida'; } catch (_) { /* nada */ }
  aplicar(recolhida);

  botao.addEventListener('click', () => {
    recolhida = !casca.classList.contains('recolhida');
    aplicar(recolhida);
    try { localStorage.setItem('lateral', recolhida ? 'recolhida' : 'aberta'); } catch (_) { /* nada */ }
  });
}

/* --- gaveta do Andamento ----------------------------------------------------
   Nao bloqueia a tela, entao nao escurece o fundo: e um painel paralelo. Sobe e
   desce pelo mesmo caminho, numa mola que pode ser invertida no meio. */

let molaGaveta = null;

function montarGaveta() {
  const gaveta = document.getElementById('gaveta');
  document.getElementById('icone-log').replaceWith(icone('terminal', 16));
  document.getElementById('log-fechar').append(icone('fechar', 16));

  molaGaveta = new Mola(1, (v) => {
    gaveta.style.transform = `translateY(${v * 100}%)`;
    gaveta.style.visibility = v > 0.995 ? 'hidden' : 'visible';
  }, { resposta: 0.32 });

  document.getElementById('abrir-log').addEventListener('click', () => app.gaveta(!app.logAberto));
  document.getElementById('log-fechar').addEventListener('click', () => app.gaveta(false));
  document.getElementById('log-limpar').addEventListener('click', () => {
    document.getElementById('log').replaceChildren();
    contarLog();
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && app.logAberto && !document.querySelector('.veu')) app.gaveta(false);
  });
}

app.gaveta = (abrir) => {
  app.logAberto = abrir;
  molaGaveta.ir(abrir ? 0 : 1);
  if (abrir) {
    app.logNovo = 0;
    pintarSeloLog();
    const log = document.getElementById('log');
    log.scrollTop = log.scrollHeight;
  }
};

function pintarSeloLog() {
  const selo = document.getElementById('selo-log');
  selo.textContent = app.logNovo > 99 ? '99+' : app.logNovo;
  selo.classList.toggle('oculto', !app.logNovo);
  selo.classList.toggle('destaque', app.logNovo > 0);
}

function contarLog() {
  const n = document.getElementById('log').childElementCount;
  document.getElementById('log-conta').textContent = n ? `${n} linhas` : '';
}

app.escrever = (texto, etiqueta = '') => {
  const log = document.getElementById('log');
  const noFim = log.scrollHeight - log.scrollTop - log.clientHeight < 40;

  log.append(h('div', { class: etiqueta }, texto || ' '));

  while (log.childElementCount > 5000) log.firstChild.remove();

  if (noFim) log.scrollTop = log.scrollHeight;

  if (!app.logAberto) {
    app.logNovo += 1;
    pintarSeloLog();
  }
  contarLog();
};

/* --- operacao em andamento ------------------------------------------------- */

const placar = {};

function pintarPlacar() {
  const partes = [];
  if (placar.gasto !== undefined) partes.push(['gasto', fmt(placar.gasto)]);
  if (placar.previsto !== undefined) partes.push(['lucro previsto', fmt(placar.previsto)]);
  if (placar.recebido !== undefined) partes.push(['recebido', fmt(placar.recebido)]);
  if (placar.unidades !== undefined) partes.push(['unidades', fmt(placar.unidades)]);
  trocar(document.getElementById('op-placar'),
    partes.map(([k, v]) => h('span', {}, `${k} `, h('b', {}, v))));
}

function inicio(rotulo) {
  app.rodando = rotulo;
  for (const k of Object.keys(placar)) delete placar[k];
  pintarPlacar();
  document.getElementById('op-rotulo').textContent = rotulo;
  document.getElementById('op-andamento').textContent = '';
  document.getElementById('op-barra').style.width = '0';
  document.getElementById('operacao').classList.remove('oculto');
  document.body.dataset.rodando = '1';
  for (const t of Object.values(TELAS)) t.aoRodar && t.aoRodar(true);
}

async function fim(rotulo) {
  app.rodando = null;
  document.getElementById('operacao').classList.add('oculto');
  delete document.body.dataset.rodando;
  torrada(`Terminou: ${rotulo}`, 'ok');
  for (const t of Object.values(TELAS)) t.aoRodar && t.aoRodar(false);
  await app.atualizarEstado();
  const tela = TELAS[app.atual];
  if (tela && tela.mostrar) tela.mostrar();
}

app.eventos = (lote) => {
  for (const e of lote) {
    if (e.tipo === 'linha') app.escrever(e.texto, e.etiqueta);
    else if (e.tipo === 'progresso') {
      document.getElementById('op-andamento').textContent =
        e.total ? `${e.rotulo} · ${e.feito} de ${e.total}` : e.rotulo;
      if (e.total) document.getElementById('op-barra').style.width = `${(100 * e.feito) / e.total}%`;
    } else if (e.tipo === 'placar') {
      Object.assign(placar, e);
      delete placar.tipo;
      pintarPlacar();
    } else if (e.tipo === 'inicio') inicio(e.rotulo);
    else if (e.tipo === 'fim') fim(e.rotulo);
  }
};

/* Comecar qualquer coisa que mexe no jogo passa por aqui: se o jogo nao estiver
   pronto, a ponte devolve a lista de problemas e a pergunta e feita aqui. */
app.rodar = async (nome, ...args) => {
  let r = await api(nome, ...args, false);
  if (r && r.problemas) {
    const sim = await dialogo({
      titulo: 'O jogo não está pronto',
      lista: r.problemas,
      texto: 'Quer tentar mesmo assim?',
      sim: 'Tentar mesmo assim',
      tom: 'perigo',
    });
    if (!sim) return false;
    r = await api(nome, ...args, true);
  }
  if (r && !r.ok) {
    if (r.motivo) torrada(r.motivo, 'perigo');
    return false;
  }
  return true;
};

app.confirmarSaida = async () => {
  const sim = await dialogo({
    titulo: 'Sair agora?',
    texto: 'Há uma operação em andamento. Sair vai interrompê-la.',
    sim: 'Sair',
    nao: 'Continuar',
    tom: 'perigo',
  });
  if (sim) api('sair');
};

/* --- comeco ----------------------------------------------------------------- */

document.getElementById('op-parar').addEventListener('click', () => api('parar'));

async function comecar() {
  montarNav();
  montarRecolher();
  montarGaveta();

  const e = await app.atualizarEstado();
  app.aplicarTema(e.tema);

  if (e.erro_ao_abrir) app.escrever(`ATENCAO ao abrir - ${e.erro_ao_abrir}`, 'aviso');
  if (e.rodando) inicio(e.rodando);

  let inicial = 'operacao';
  try { inicial = localStorage.getItem('tela') || inicial; } catch (_) { /* nada */ }
  if (!TELAS[inicial]) inicial = 'operacao';

  app.ir(inicial);
}

comecar();
