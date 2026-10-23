/* ==========================================================================
   ajustes.js - como o bot compra, le e se comporta

   COMO OS AJUSTES DO MAC: abas no topo, grupos em lista, o nome a esquerda e o
   controle a direita - sempre no mesmo lugar. A explicacao e curta, embaixo do
   nome; o que e contexto vai para o pe do grupo.

   SALVA SOZINHO. Interruptor, opcao e tecla gravam na hora; numero e caminho,
   ao sair do campo ou apertar Enter. Cada mudanca vai junto com o resto JA
   SALVO, e nao com o resto da tela: um campo com erro mostra o erro so nele e
   nao segura os outros.
   ========================================================================== */

'use strict';

(() => {

  let raiz, conteudo, abasEl, salvoEl, info = null;
  let aba = 'geral';
  const controles = {};
  let situacaoRede = null;
  let relogioRede = null;

  /* --- o que vai em cada aba ------------------------------------------------
     linha: [chave, nome, dica, tipo, extra]
       tipo: chave (interruptor) | numero (extra = unidade) | opcoes (extra =
       [[valor, rotulo]]) | tecla | caminho
     grupo: { titulo, linhas, rodape, fim: () => elemento extra no fim } */

  const ABAS = [
    ['geral', 'Geral'],
    ['compra', 'Compra'],
    ['leitura', 'Leitura'],
    ['avancado', 'Avançado'],
  ];

  const GRUPOS = {
    geral: [
      { titulo: 'Conta', linhas: [
        ['premium', 'Conta Premium', '', 'chave'],
      ] },
      { titulo: 'Durante a operação', linhas: [
        ['minimizar', 'Minimizar esta janela ao começar', '', 'chave'],
        ['focar_jogo', 'Trazer o jogo para a frente', 'Sem isso, o bot clicaria nesta janela.', 'chave'],
        ['avisar_no_fim', 'Avisar quando terminar', 'Som e ícone piscando na barra de tarefas.', 'chave'],
        ['faixa', 'Faixa de andamento no topo da tela', '', 'chave'],
        ['avisos', 'Cartões de preço no canto da tela', '', 'chave'],
      ], rodape: 'A faixa e os cartões ficam por cima do jogo e não aceitam clique.' },
      { titulo: 'Teclas', linhas: [
        ['tecla_pausa', 'Pausar e retomar', '', 'tecla'],
        ['tecla_pular', 'Pular o item atual', 'Para o item que trava sem dar erro.', 'tecla'],
        ['tecla_parada', 'Parar agora', 'Duas vezes seguidas encerra o programa.', 'tecla'],
      ] },
      { titulo: 'Aparência', linhas: [
        ['tema', 'Tema', '', 'opcoes', [['escuro', 'Escuro'], ['claro', 'Claro'], ['sistema', 'Do Windows']]],
      ] },
    ],
    compra: [
      { titulo: 'Lucro', linhas: [
        ['margem', 'Margem mínima', 'Já descontadas as taxas de venda e de ordem.', 'numero', '%'],
        ['idade_maxima', 'Idade máxima do preço', 'Preço mais velho que isso não decide compra.', 'numero', 'h'],
      ] },
      { titulo: 'Limites da viagem', linhas: [
        ['teto', 'Teto de gasto', '', 'numero', 'prata'],
        ['espacos', 'Espaços livres no inventário', 'Equipamento não empilha: cada unidade ocupa um.', 'numero', 'espaços'],
      ], rodape: 'Vazio é sem limite. O que passa do limite sai da lista, sempre o pior negócio primeiro.' },
      { titulo: 'Como comprar', linhas: [
        ['modo_de_compra', 'Modo', '', 'opcoes', [['smart', 'Automático'], ['ordem', 'Sempre ordem'], ['na_hora', 'Sempre na hora']]],
        ['ordem_a_partir_de', 'Ordem a partir de', 'Uma ordem leva todas as ofertas do preço de uma vez.', 'numero', 'unid.'],
        ['na_hora_acima_de', 'Na hora acima de', 'Por unidade. Em item caro, os 2,5% da ordem pesam.', 'numero', 'prata'],
      ], rodape: 'No automático, cada linha da lista escolhe entre ordem e compra na hora por essas duas regras.' },
      { titulo: 'Qualidade', linhas: [
        ['comprar_por_qualidade', 'Comprar por qualidade', 'Só quando o Mercado Negro paga 15% a mais de lucro que a Normal.', 'chave'],
      ], rodape: 'Desligado, tudo é comprado e vendido como Normal, que vende mais rápido. Ligado, precisa da leitura pela rede e do filtro de qualidade calibrado.' },
    ],
    leitura: [
      { titulo: 'Pela rede (albiondata-client)', linhas: [
        ['rede_ativa', 'Ler os preços pela rede', 'Exato e sem OCR. Os preços ficam só neste computador.', 'chave'],
      ], fim: () => montarSituacaoRede() },
      { titulo: 'Ao ler', linhas: [
        ['apagar_antes', 'Apagar antes os preços dos itens a ler', 'Só os itens desta leitura; os outros grupos ficam. Uma cópia fica guardada.', 'chave'],
        ['repescar', 'Reler o que faltar, no fim', 'O que volta vazio costuma ser lentidão da tela.', 'chave'],
        ['amostras', 'Conferir combinações sorteadas', 'Relê algumas no fim e compara. Zero desliga.', 'numero', ''],
      ] },
      { titulo: 'Tela do jogo', linhas: [], fim: () => linhaBotao(
        'Coordenadas', 'O padrão é 1920×1080, tela cheia, no monitor principal.',
        h('button', {
          class: 'botao pequeno', onclick: async () => {
            const r = await api('abrir_calibrador');
            if (!r.ok) torrada(r.motivo, 'perigo');
          },
        }, icone('alvo'), 'Calibrar…')),
      rodape: 'Recalibre se o jogo estiver em outra resolução ou se uma leitura sair errada.' },
    ],
    avancado: [
      { titulo: 'Velocidade', linhas: [
        ['ms_clique', 'Pausa depois do clique', '', 'numero', 'ms'],
        ['ms_escrita', 'Pausa ao mover o mouse', '', 'numero', 'ms'],
        ['ms_leitura', 'Tempo de preço parado', 'Aumente com máquina lenta ou ping alto.', 'numero', 'ms'],
      ] },
      { titulo: 'Rede', linhas: [
        ['cliente_dados', 'Onde está o albiondata-client', 'Vazio procura onde o instalador põe.', 'caminho'],
        ['porta_rede', 'Porta local', 'Só mude se outro programa já usa esta.', 'numero', ''],
      ] },
      { titulo: 'Restaurar', linhas: [], fim: () => linhaBotao(
        'Voltar tudo ao padrão', 'O catálogo, os preços e o histórico não mudam.',
        h('button', { class: 'botao perigo-acao pequeno', onclick: restaurar }, 'Restaurar…')) },
    ],
  };

  const NUMEROS_PCT = new Set(['margem']);
  const VAZIO_E_SEM_LIMITE = new Set(['teto', 'espacos']);

  /* --- valores -------------------------------------------------------------- */

  // como o valor guardado aparece no campo
  function paraTela(chave, v) {
    if (v === null || v === undefined) return '';
    if (NUMEROS_PCT.has(chave)) return (v * 100).toLocaleString('pt-BR', { maximumFractionDigits: 2 });
    if (typeof v === 'number') return String(v).replace('.', ',');
    return v;
  }

  function valorNaTela(chave) {
    const c = controles[chave];
    if (c.tipo === 'chave') return c.input.checked;
    if (c.tipo === 'opcoes') return c.el.valor;
    return c.el.value;
  }

  // o que ja esta salvo, no formato que a ponte confere
  function salvosNoFormatoDaTela() {
    const dados = {};
    for (const [chave, c] of Object.entries(controles)) {
      const v = info.valores[chave];
      dados[chave] = c.tipo === 'chave' ? !!v : (c.tipo === 'numero' ? paraTela(chave, v) : v);
    }
    return dados;
  }

  function mostrarValor(chave) {
    const c = controles[chave];
    const v = info.valores[chave];
    if (c.tipo === 'chave') c.input.checked = !!v;
    else if (c.tipo === 'opcoes') c.el.definir(v);
    else if (c.tipo === 'tecla') c.el.value = v;
    else if (document.activeElement !== c.el) c.el.value = paraTela(chave, v);
    if (chave === 'premium') pintarTaxa();
  }

  function marcarErro(chave, motivo) {
    const c = controles[chave];
    if (!c) return;
    c.erro.textContent = motivo || '';
    if (c.el.classList && (c.tipo === 'numero' || c.tipo === 'caminho')) {
      (c.caixa || c.el).classList.toggle('invalida', !!motivo);
    }
  }

  /* --- salvar uma mudanca --------------------------------------------------- */

  let fila = Promise.resolve();

  function salvar(chave) {
    // uma de cada vez, na ordem: duas mudancas rapidas nao podem se atropelar
    fila = fila.then(() => salvarAgora(chave)).catch(() => {});
    return fila;
  }

  async function salvarAgora(chave) {
    const valor = valorNaTela(chave);

    // nada mudou de verdade (ex.: saiu do campo sem editar)
    if (String(valor) === String(salvosNoFormatoDaTela()[chave])) {
      marcarErro(chave, '');
      return;
    }

    const dados = Object.assign(salvosNoFormatoDaTela(), { [chave]: valor });
    const r = await api('salvar_ajustes', dados);

    if (!r.ok) {
      const erros = r.erros || {};
      if (erros._) torrada(`Não deu para salvar: ${erros._}`, 'perigo');
      // o erro e da mudanca; os outros campos ja salvos nao tem culpa
      marcarErro(chave, erros[chave] || Object.values(erros)[0] || 'Não salvou.');
      return;
    }

    marcarErro(chave, '');
    info = await api('ajustes_atuais');
    mostrarValor(chave);
    if (chave === 'tema') app.aplicarTema(info.valores.tema);
    piscarSalvo();
    app.atualizarEstado();
    if (chave === 'rede_ativa' || chave === 'cliente_dados' || chave === 'porta_rede') atualizarRede();
  }

  let relogioSalvo = null;

  function piscarSalvo() {
    salvoEl.classList.add('visivel');
    clearTimeout(relogioSalvo);
    relogioSalvo = setTimeout(() => salvoEl.classList.remove('visivel'), 1400);
  }

  /* --- linhas --------------------------------------------------------------- */

  function rotulo(nome, dica, extra) {
    return h('div', { class: 'rotulo' }, h('strong', {}, nome), dica ? h('small', {}, dica) : null, extra || null);
  }

  function interruptor(nome) {
    const input = h('input', { type: 'checkbox', 'aria-label': nome });
    const el = h('label', { class: 'chave so-trilho' }, input, h('span', { class: 'trilho' }));
    return [el, input];
  }

  function linhaAjuste(chave, nome, dica, tipo, extra) {
    const erro = h('div', { class: 'erro-campo', role: 'alert' });
    let controle;
    const c = { tipo, erro };

    if (tipo === 'chave') {
      const [el, input] = interruptor(nome);
      Object.assign(c, { el, input });
      input.addEventListener('change', () => {
        if (chave === 'premium') pintarTaxa();
        salvar(chave);
      });
      controle = el;
    } else if (tipo === 'opcoes') {
      controle = segmentado(extra, null, (v) => {
        if (chave === 'tema') app.aplicarTema(v);
        salvar(chave);
      });
      c.el = controle;
    } else if (tipo === 'tecla') {
      controle = h('select', { class: 'entrada larga', 'aria-label': nome },
        info.teclas.map((t) => h('option', { value: t }, t.toUpperCase())));
      controle.addEventListener('change', () => salvar(chave));
      c.el = controle;
    } else if (tipo === 'caminho') {
      const campo = h('input', { class: 'entrada', placeholder: 'procurar onde o instalador põe', spellcheck: 'false', 'aria-label': nome });
      campo.addEventListener('change', () => salvar(chave));
      campo.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') campo.blur();
        if (e.key === 'Escape') { campo.value = info.valores[chave] || ''; marcarErro(chave, ''); campo.blur(); }
      });
      c.el = campo;
      controles[chave] = c;
      return h('div', { class: 'linha-ajuste' },
        rotulo(nome, dica),
        h('button', {
          class: 'botao pequeno', onclick: async () => {
            const escolhido = await api('escolher_cliente');
            if (escolhido) { campo.value = escolhido; salvar(chave); }
          },
        }, 'Procurar…'),
        h('div', { class: 'inteira' }, campo),
        erro);
    } else {
      const campo = h('input', {
        class: 'entrada', inputmode: 'decimal', 'aria-label': nome,
        placeholder: VAZIO_E_SEM_LIMITE.has(chave) ? 'sem limite' : '',
      });
      campo.addEventListener('change', () => salvar(chave));
      campo.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') campo.blur();
        // Esc desiste: volta ao que esta salvo
        if (e.key === 'Escape') { campo.value = paraTela(chave, info.valores[chave]); marcarErro(chave, ''); campo.blur(); }
      });
      // A UNIDADE MORA DENTRO DO CAMPO: todos da mesma largura, alinhados
      controle = h('label', { class: 'com-unidade' }, campo, extra ? h('span', {}, extra) : null);
      Object.assign(c, { el: campo, caixa: controle });
    }

    controles[chave] = c;
    return h('div', { class: 'linha-ajuste' },
      rotulo(nome, chave === 'premium' ? ' ' : dica),
      controle,
      erro);
  }

  function linhaBotao(nome, dica, botao) {
    return h('div', { class: 'linha-ajuste' }, rotulo(nome, dica), botao);
  }

  // A TAXA SEGUE O PREMIUM, e a frase diz qual vale agora
  function pintarTaxa() {
    const c = controles.premium;
    if (!c || !info) return;
    const t = c.input.checked ? info.taxas.com_premium : info.taxas.sem_premium;
    c.el.closest('.linha-ajuste').querySelector('small').textContent =
      `Taxa de venda de ${pct(t, 0)}. A de criar ordem (${pct(info.taxas.ordem)}) não muda.`;
  }

  /* --- a situacao da rede ---------------------------------------------------- */

  function montarSituacaoRede() {
    situacaoRede = h('span', {});
    const ponto = h('span', { class: 'ponto' });
    situacaoRede.ponto = ponto;
    return h('div', { class: 'linha-ajuste situacao-rede' },
      h('div', { class: 'rotulo' },
        h('strong', {}, 'Situação'),
        h('small', { class: 'com-ponto' }, ponto, situacaoRede)),
      h('div', { class: 'linha', style: { gap: '8px', justifyContent: 'flex-end' } },
        h('button', { class: 'botao pequeno', onclick: async () => pintarRede(await api('religar_rede')) },
          'Abrir de novo'),
        h('button', { class: 'botao discreto pequeno', onclick: () => api('abrir_site_do_cliente') },
          'Baixar')));
  }

  function pintarRede(s) {
    if (!situacaoRede || !s) return;
    const [texto, tom] = textoDaRede(s);
    situacaoRede.textContent = texto;
    situacaoRede.ponto.className = 'ponto ' + (tom || (s.ligada ? 'esperando' : 'desligado'));
  }

  async function atualizarRede() {
    if (aba === 'leitura') pintarRede(await api('rede'));
  }

  /* --- restaurar ------------------------------------------------------------- */

  async function restaurar() {
    const sim = await dialogo({
      titulo: 'Voltar tudo ao padrão?',
      texto: 'Todos os ajustes voltam ao valor de fábrica. O catálogo, os preços e o histórico não mudam.',
      sim: 'Restaurar', tom: 'perigo',
    });
    if (!sim) return;
    info = await api('restaurar_ajustes');
    for (const chave of Object.keys(controles)) { mostrarValor(chave); marcarErro(chave, ''); }
    app.aplicarTema(info.valores.tema);
    torrada('Ajustes de fábrica restaurados.', 'ok');
    app.atualizarEstado();
  }

  /* --- desenho ---------------------------------------------------------------- */

  function grupo({ titulo, linhas, rodape, fim }) {
    const lista = h('div', { class: 'lista-ajustes' }, linhas.map((l) => linhaAjuste(...l)), fim ? fim() : null);
    return h('section', { class: 'grupo-ajustes' },
      h('h3', {}, titulo),
      lista,
      rodape ? h('p', { class: 'rodape-grupo' }, rodape) : null);
  }

  function desenhar() {
    raiz.dataset.montado = '1';

    abasEl = segmentado(ABAS, aba, (v) => irPara(v));
    abasEl.classList.add('abas-ajustes');
    salvoEl = h('span', { class: 'salvo', role: 'status' }, '✓ Salvo');

    conteudo = h('div', { class: 'paginas-ajustes' });

    // todas as abas sao montadas uma vez; trocar so mostra outra
    for (const [id] of ABAS) {
      conteudo.append(h('div', { class: 'pagina-ajustes', 'data-aba': id }, GRUPOS[id].map(grupo)));
    }

    raiz.append(h('div', { class: 'ajustes' },
      h('div', { class: 'topo-ajustes' }, abasEl, salvoEl),
      conteudo));
  }

  function irPara(id) {
    aba = id;
    abasEl.definir(id);
    for (const p of conteudo.children) p.hidden = p.dataset.aba !== id;
    try { localStorage.setItem('ajustes-aba', id); } catch { /* sem memoria, tudo bem */ }

    clearInterval(relogioRede);
    if (id === 'leitura') {
      atualizarRede();
      relogioRede = setInterval(atualizarRede, 3000);
    }
  }

  async function carregar() {
    info = await api('ajustes_atuais');
    if (!raiz.dataset.montado) {
      try { aba = localStorage.getItem('ajustes-aba') || aba; } catch { /* idem */ }
      if (!GRUPOS[aba]) aba = 'geral';
      desenhar();
    }
    for (const chave of Object.keys(controles)) { mostrarValor(chave); marcarErro(chave, ''); }
    app.aplicarTema(info.valores.tema);
    irPara(aba);
  }

  TELAS.ajustes = {
    titulo: 'Ajustes',
    subtitulo: 'como o bot compra, lê e se comporta',
    montar(el) { raiz = el; },
    mostrar(qual) {
      if (qual && GRUPOS[qual]) aba = qual;
      return carregar();
    },
    aoSair() {
      clearInterval(relogioRede);
      // o campo que estava sendo editado e salvo ao sair da tela
      const ativo = document.activeElement;
      if (ativo && raiz.contains(ativo)) ativo.blur();
    },
  };
})();
