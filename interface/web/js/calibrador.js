/* ==========================================================================
   calibrador.js - remarca as posicoes sobre uma captura da tela do jogo
   ========================================================================== */

'use strict';

(() => {

  const LUPA_PIXELS = 15;
  const LUPA_ZOOM = 10;

  const palco = document.getElementById('palco');
  const tela = document.getElementById('tela');
  const lupa = document.getElementById('lupa');
  const ctx = tela.getContext('2d');
  const ctxLupa = lupa.getContext('2d');

  let passos = [];
  let grupo = 0;
  let marca = 0;
  let imagem = null;
  let escala = 1;
  let arrasto = null;
  const valores = {};

  const TIPO = { ponto: 'um clique', regiao: 'arraste um retângulo', altura: 'um clique (só a altura conta)' };

  function atual() { return passos[grupo] && passos[grupo].marcas[marca]; }

  /* --- painel ----------------------------------------------------------------- */

  function pintarPainel() {
    trocar(document.getElementById('grupos'), passos.map((g, i) => {
      const feitas = g.marcas.filter((m) => m.nome in valores).length;
      return h('button', {
        'aria-current': i === grupo ? 'step' : null,
        onclick: () => { grupo = i; marca = primeiraFaltando(i); pintarPainel(); desenhar(); },
      }, g.titulo, h('span', { class: `selo ${feitas === g.marcas.length ? 'ok' : ''}` }, `${feitas}/${g.marcas.length}`));
    }));

    const g = passos[grupo];
    document.getElementById('preparo').textContent = g
      ? `Antes de capturar: ${g.preparo.charAt(0).toLowerCase()}${g.preparo.slice(1)}` : '';

    const m = atual();
    const caixa = document.getElementById('marca');

    if (!g) {
      trocar(caixa, h('div', { class: 'oque' }, 'Tudo marcado.'), h('div', { class: 'nota' }, 'Grave para aplicar.'));
    } else if (!m) {
      trocar(caixa, h('div', { class: 'oque' }, `"${g.titulo}" pronto.`), h('div', { class: 'nota' }, 'Escolha o próximo grupo na lista.'));
    } else if (!imagem) {
      trocar(caixa, h('div', { class: 'tipo' }, TIPO[m.tipo]), h('div', { class: 'oque' }, m.o_que),
        h('div', { class: 'nota' }, 'Capture a tela do jogo para começar a marcar.'));
    } else {
      trocar(caixa, h('div', { class: 'tipo' }, TIPO[m.tipo]), h('div', { class: 'oque' }, m.o_que),
        m.dica ? h('div', { class: 'nota' }, m.dica) : null);
    }

    const total = passos.reduce((s, x) => s + x.marcas.length, 0);
    const feitas = Object.keys(valores).length;
    document.getElementById('contagem').textContent = `${feitas} de ${total} marcas feitas`;
    document.getElementById('gravar').disabled = !feitas;
    document.getElementById('refazer').disabled = !Object.keys(valores).length;
    document.getElementById('pular').disabled = !m;
  }

  function primeiraFaltando(i) {
    const n = passos[i].marcas.findIndex((m) => !(m.nome in valores));
    return n < 0 ? passos[i].marcas.length : n;
  }

  /* --- desenho ------------------------------------------------------------------ */

  function encaixar() {
    if (!imagem) return;
    const r = palco.getBoundingClientRect();
    escala = Math.min(r.width / imagem.width, r.height / imagem.height);
    tela.width = Math.round(imagem.width * escala);
    tela.height = Math.round(imagem.height * escala);
    tela.style.left = `${Math.round((r.width - tela.width) / 2)}px`;
    tela.style.top = `${Math.round((r.height - tela.height) / 2)}px`;
    desenhar();
  }

  function desenhar(provisorio) {
    if (!imagem) return;
    ctx.imageSmoothingQuality = 'high';
    ctx.drawImage(imagem, 0, 0, tela.width, tela.height);

    const cor = getComputedStyle(document.documentElement).getPropertyValue('--destaque').trim() || '#7b8fff';
    ctx.lineWidth = 2;
    ctx.strokeStyle = cor;
    ctx.fillStyle = cor;
    ctx.font = '600 12px Segoe UI';

    const g = passos[grupo];
    if (g) {
      for (const m of g.marcas) {
        const v = valores[m.nome];
        if (v === undefined) continue;
        if (m.tipo === 'ponto') {
          ctx.beginPath(); ctx.arc(v.x * escala, v.y * escala, 5, 0, Math.PI * 2); ctx.fill();
        } else if (m.tipo === 'regiao') {
          ctx.strokeRect(v[0] * escala, v[1] * escala, (v[2] - v[0]) * escala, (v[3] - v[1]) * escala);
        } else {
          ctx.beginPath(); ctx.moveTo(0, v * escala); ctx.lineTo(tela.width, v * escala); ctx.stroke();
        }
      }
    }

    if (provisorio) {
      const [x1, y1, x2, y2] = provisorio;
      ctx.setLineDash([6, 4]);
      ctx.strokeRect(x1 * escala, y1 * escala, (x2 - x1) * escala, (y2 - y1) * escala);
      ctx.setLineDash([]);
    }
  }

  function naTela(e) {
    const r = tela.getBoundingClientRect();
    return [Math.round((e.clientX - r.left) / escala), Math.round((e.clientY - r.top) / escala)];
  }

  function pintarLupa(e, x, y) {
    const meio = Math.floor(LUPA_PIXELS / 2);
    ctxLupa.imageSmoothingEnabled = false;
    ctxLupa.clearRect(0, 0, lupa.width, lupa.height);
    ctxLupa.drawImage(imagem, x - meio, y - meio, LUPA_PIXELS, LUPA_PIXELS, 0, 0, LUPA_PIXELS * LUPA_ZOOM, LUPA_PIXELS * LUPA_ZOOM);
    ctxLupa.strokeStyle = '#fff';
    ctxLupa.lineWidth = 2;
    ctxLupa.strokeRect(meio * LUPA_ZOOM, meio * LUPA_ZOOM, LUPA_ZOOM, LUPA_ZOOM);

    const r = palco.getBoundingClientRect();
    let lx = e.clientX - r.left + 24;
    let ly = e.clientY - r.top + 24;
    if (lx + 150 > r.width) lx -= 198;
    if (ly + 150 > r.height) ly -= 198;
    lupa.style.left = `${lx}px`;
    lupa.style.top = `${ly}px`;
    lupa.classList.remove('oculto');
  }

  /* --- marcar ------------------------------------------------------------------ */

  function guardar(m, valor) {
    valores[m.nome] = valor;
    marca = primeiraFaltando(grupo);
    pintarPainel();
    desenhar();
  }

  tela.addEventListener('pointerdown', (e) => {
    const m = atual();
    if (!imagem || !m) return;
    tela.setPointerCapture(e.pointerId);
    const [x, y] = naTela(e);
    if (m.tipo === 'regiao') { arrasto = [x, y]; return; }
    guardar(m, m.tipo === 'ponto' ? { x, y } : y);
  });

  tela.addEventListener('pointermove', (e) => {
    if (!imagem) return;
    const [x, y] = naTela(e);
    pintarLupa(e, x, y);
    if (arrasto) {
      const [x1, y1] = arrasto;
      document.getElementById('coordenada').textContent = `${Math.abs(x - x1)} × ${Math.abs(y - y1)} px`;
      desenhar([Math.min(x1, x), Math.min(y1, y), Math.max(x1, x), Math.max(y1, y)]);
    } else {
      document.getElementById('coordenada').textContent = `x ${x} · y ${y}`;
    }
  });

  tela.addEventListener('pointerleave', () => lupa.classList.add('oculto'));

  tela.addEventListener('pointerup', (e) => {
    if (!arrasto) return;
    const [x1, y1] = arrasto;
    const [x2, y2] = naTela(e);
    arrasto = null;
    if (Math.abs(x2 - x1) < 4 || Math.abs(y2 - y1) < 4) {
      torrada('Retângulo pequeno demais — arraste de novo.', 'perigo');
      desenhar();
      return;
    }
    guardar(atual(), [Math.min(x1, x2), Math.min(y1, y2), Math.max(x1, x2), Math.max(y1, y2)]);
  });

  document.getElementById('refazer').addEventListener('click', () => {
    const g = passos[grupo];
    const feitas = g.marcas.filter((m) => m.nome in valores);
    if (!feitas.length) return;
    const ultima = feitas[feitas.length - 1];
    delete valores[ultima.nome];
    marca = g.marcas.indexOf(ultima);
    pintarPainel();
    desenhar();
  });

  document.getElementById('pular').addEventListener('click', () => {
    const g = passos[grupo];
    marca = Math.min(g.marcas.length, marca + 1);
    pintarPainel();
  });

  document.getElementById('capturar').addEventListener('click', async (e) => {
    const botao = e.currentTarget;
    botao.disabled = true;
    trocar(botao, h('span', { class: 'girando' }), 'Capturando…');
    const r = await api('capturar_tela');
    botao.disabled = false;
    trocar(botao, 'Capturar de novo');
    if (r.erro) { torrada(r.erro, 'perigo'); return; }
    const img = new Image();
    img.onload = () => { imagem = img; encaixar(); pintarPainel(); };
    img.src = r.imagem;
  });

  document.getElementById('gravar').addEventListener('click', async () => {
    const n = Object.keys(valores).filter((k) => !k.startsWith('_')).length;
    const sim = await dialogo({
      titulo: 'Gravar as coordenadas?',
      texto: `${n} coordenadas vão para o coordenadas.json. O que você não marcou continua com o valor de fábrica; para desfazer tudo, apague esse arquivo.\n\n`
        + 'Depois de gravar, rode uma vez em Simular antes de qualquer coisa que mexa com prata: uma coordenada errada num bot de compra é uma compra errada.',
      sim: 'Gravar',
    });
    if (!sim) return;
    const r = await api('salvar_coordenadas', valores);
    if (!r.ok) { torrada(r.motivo, 'perigo'); return; }
    for (const k of Object.keys(valores)) delete valores[k];
    torrada(`${r.trocadas} coordenadas gravadas. Já valem na próxima operação.`, 'ok');
    pintarPainel();
    desenhar();
  });

  window.addEventListener('resize', encaixar);

  (async () => {
    const { tema } = await api('estado');
    const claro = tema === 'claro' || (tema === 'sistema' && matchMedia('(prefers-color-scheme: light)').matches);
    document.documentElement.dataset.tema = claro ? 'claro' : 'escuro';

    passos = await api('calibrador_passos');
    pintarPainel();
    palco.append(vazio('alvo', 'Nenhuma captura ainda', 'Deixe o jogo na tela pedida à direita e clique em "Capturar a tela do jogo". Esta janela sai da frente por um instante.'));
    const aviso = palco.querySelector('.vazio');
    document.getElementById('capturar').addEventListener('click', () => aviso && aviso.remove(), { once: true });
  })();
})();
