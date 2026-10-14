/* ==========================================================================
   sobreposicao.js - a faixa do topo e os cartoes do canto, por cima do jogo.
   faixa.html chama sobre.iniciar('faixa'); cada cartao e uma janela propria
   (cartao.html), e o Python manda nela o aviso que ela mostra.
   ========================================================================== */

'use strict';

window.sobre = (() => {
  const raiz = document.getElementById('raiz');
  const fmt = (n) => new Intl.NumberFormat('pt-BR').format(Math.round(n));
  const TONS = { ok: '--ok', aviso: '--aviso', perigo: '--perigo' };

  let modo = null;
  let texto, conta, placarEl, barra;
  const placar = {};

  function iniciar(qual) {
    modo = qual;
    if (modo === 'faixa') {
      raiz.innerHTML = `<div class="faixa">
        <img src="img/marca.svg" alt="">
        <span class="texto" id="texto">Começando…</span>
        <span class="placar num" id="placar"></span>
        <span class="conta num" id="conta"></span>
        <span class="teclas">F11 pausa · F12 para</span>
        <span class="trilho"><span class="barra" id="barra"></span></span></div>`;
      texto = document.getElementById('texto');
      conta = document.getElementById('conta');
      placarEl = document.getElementById('placar');
      barra = document.getElementById('barra');
    }
  }

  // A COR DA ESQUERDA: o tom do aviso quando ele tem um (pausa, erro), senao a
  // cor do grau do item - "Broadsword T7.3" fica amarelo, como no jogo.
  function cor(titulo, tom) {
    if (TONS[tom]) return `var(${TONS[tom]})`;
    const grau = /\bT([1-8])(?:\.\d)?\b/.exec(titulo || '');
    return grau ? `var(--t${grau[1]})` : 'var(--destaque)';
  }

  function mostrar(aviso) {
    const el = document.createElement('div');
    el.className = 'cartao';
    el.style.setProperty('--cor', cor(aviso.titulo, aviso.tom));

    const faixaCor = document.createElement('span');
    faixaCor.className = 'cor';

    // "Broadsword T7.3": o nome apagado, o grau em destaque
    const t = document.createElement('span');
    t.className = 't';
    const partes = /^(.*?)\s*(\bT[1-8](?:\.\d)?)$/.exec(aviso.titulo || '');
    if (partes) {
      t.append(partes[1] + ' ');
      const b = document.createElement('b');
      b.textContent = partes[2];
      t.append(b);
    } else {
      t.textContent = aviso.titulo || '';
    }

    el.append(faixaCor, t);
    if (aviso.valor !== null && aviso.valor !== undefined && aviso.valor !== '') {
      const v = document.createElement('span');
      v.className = 'v';
      v.textContent = aviso.valor;
      el.append(v);
    }
    raiz.replaceChildren(el);
  }

  function pintarPlacar() {
    const partes = [];
    if (placar.gasto !== undefined) partes.push(`gasto <b>${fmt(placar.gasto)}</b>`);
    if (placar.previsto !== undefined) partes.push(`lucro <b>${fmt(placar.previsto)}</b>`);
    if (placar.recebido !== undefined) partes.push(`recebido <b>${fmt(placar.recebido)}</b>`);
    placarEl.innerHTML = partes.join(' · ');
  }

  function eventos(lote) {
    if (modo !== 'faixa') return;
    for (const e of lote) {
      if (e.tipo === 'progresso') {
        texto.textContent = e.rotulo || '';
        conta.textContent = e.total ? `${e.feito}/${e.total}` : '';
        barra.style.width = e.total ? `${(100 * e.feito) / e.total}%` : '0';
      } else if (e.tipo === 'inicio') {
        texto.textContent = e.rotulo;
      } else if (e.tipo === 'placar') {
        Object.assign(placar, e);
        pintarPlacar();
      } else if (e.tipo === 'linha' && e.etiqueta === 'erro') {
        texto.textContent = e.texto.trim();
      }
    }
  }

  return { iniciar, eventos, mostrar };
})();
