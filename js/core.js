/* Twelfth Circle Trainer: shared state, settings, player and tab switching, feedback panel and
   aspect helpers. Mechanics register themselves from mechanics/*.js; index.html calls start(). */
window.Twelfth = (function(){

  // Who you play is one party slot. Mechanics that only care about the role group read `role`.
  const SLOTS = ['T1', 'T2', 'H1', 'H2', 'M1', 'M2', 'R1', 'R2'];
  const isSupportSlot = s => s[0] === 'T' || s[0] === 'H';
  const shared = {
    slot: 'H1',
    get role(){ return isSupportSlot(this.slot) ? 'support' : 'dps'; },
    roleListeners: [],
    autoAdvance: false,
    hints: false,
    layout: 'auto'
  };
  const AUTO_DELAY = 1100;
  // the slot you last had in each group, so switching group and back lands where you were
  const lastInGroup = { support:'H1', dps:'M1' };

  try{
    const savedSlot = localStorage.getItem('twelfth-slot');
    if(SLOTS.indexOf(savedSlot) >= 0) shared.slot = savedSlot;
    else if(localStorage.getItem('twelfth-role') === 'dps') shared.slot = 'M1';
    ['support', 'dps'].forEach(g => {
      const saved = localStorage.getItem('twelfth-last-' + g);
      if(SLOTS.indexOf(saved) >= 0 && isSupportSlot(saved) === (g === 'support')) lastInGroup[g] = saved;
    });
    shared.autoAdvance = localStorage.getItem('twelfth-auto') === '1';
    shared.hints = localStorage.getItem('twelfth-hints') === '1';
    const savedLayout = localStorage.getItem('twelfth-layout');
    if(['auto', 'three', 'two'].includes(savedLayout)) shared.layout = savedLayout;
  }catch(e){}
  lastInGroup[shared.role] = shared.slot;

  /* ---------- settings ---------- */
  const optAuto = document.getElementById('optAuto');
  const optHints = document.getElementById('optHints');
  const settingsBtn = document.getElementById('settingsBtn');
  const settingsPanel = document.getElementById('settingsPanel');

  function setAutoAdvance(v){
    shared.autoAdvance = !!v;
    optAuto.checked = shared.autoAdvance;
    try{ localStorage.setItem('twelfth-auto', shared.autoAdvance ? '1' : '0'); }catch(e){}
  }
  optAuto.addEventListener('change', () => setAutoAdvance(optAuto.checked));
  setAutoAdvance(shared.autoAdvance);

  // Hints are the tells a step could give away: with them off, the text says what is happening and
  // what to answer, but not how to work it out.
  function setHints(v){
    shared.hints = !!v;
    optHints.checked = shared.hints;
    document.body.classList.toggle('show-hints', shared.hints);
    remeasurePrompts();
    document.querySelectorAll('.hint-row input').forEach(cb => { cb.checked = shared.hints; });
    try{ localStorage.setItem('twelfth-hints', shared.hints ? '1' : '0'); }catch(e){}
  }
  optHints.addEventListener('change', () => setHints(optHints.checked));
  setHints(shared.hints);

  // The layout: three columns (the ask and the feedback left of the arena) or two (above and below it).
  // Auto takes three from 1240 px; on a phone it always stacks.
  const wideMQ = window.matchMedia('(min-width: 1240px)'), phoneMQ = window.matchMedia('(max-width: 900px)');
  let onLayout = null;      // set once the drills are built: moves their parts to suit
  const threeColumns = () => !phoneMQ.matches && (shared.layout === 'three' || (shared.layout === 'auto' && wideMQ.matches));
  function applyLayout(){
    document.body.classList.toggle('layout-three', threeColumns());
    document.querySelectorAll('[data-layout]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.layout === shared.layout)));
    if(onLayout) onLayout();
  }
  function setLayout(v){
    shared.layout = v;
    try{ localStorage.setItem('twelfth-layout', v); }catch(e){}
    applyLayout();
  }
  document.querySelectorAll('[data-layout]').forEach(b => b.addEventListener('click', () => setLayout(b.dataset.layout)));
  wideMQ.addEventListener('change', applyLayout);
  phoneMQ.addEventListener('change', applyLayout);
  applyLayout();

  function openSettings(open){
    settingsPanel.hidden = !open;
    settingsBtn.setAttribute('aria-expanded', String(open));
  }
  settingsBtn.addEventListener('click', e => {
    e.stopPropagation();
    openSettings(settingsPanel.hidden);
  });
  document.addEventListener('click', e => {
    if(!settingsPanel.hidden && !settingsPanel.contains(e.target) && !settingsBtn.contains(e.target)){
      openSettings(false);
    }
  });
  document.addEventListener('keydown', e => {
    if(e.key === 'Escape' && !settingsPanel.hidden){ openSettings(false); settingsBtn.focus(); }
  });

  /* ---------- "?" tips beside card headings ---------- */
  // Hover or focus shows them; a tap pins one open until you tap elsewhere or press Escape.
  function closeTips(except){
    document.querySelectorAll('.info-tip.open').forEach(t => {
      if(t === except) return;
      t.classList.remove('open');
      t.querySelector('.info-btn').setAttribute('aria-expanded', 'false');
    });
  }
  document.addEventListener('click', e => {
    const btn = e.target.closest && e.target.closest('.info-btn');
    if(!btn){ closeTips(); return; }
    const tip = btn.closest('.info-tip'), open = !tip.classList.contains('open');
    closeTips(tip);
    tip.classList.toggle('open', open);
    btn.setAttribute('aria-expanded', String(open));
  });
  document.addEventListener('keydown', e => { if(e.key === 'Escape') closeTips(); });

  /* ---------- who you play ---------- */
  // Each mechanic offers only the distinctions it actually makes.
  const JOB_COLOR = { T:'var(--umbral-soft)', H:'var(--good)', M:'var(--astral-soft)', R:'var(--astral-soft)' };
  const slotChoice = s => ({ id:s, label:s, color:JOB_COLOR[s[0]] });
  const PICKERS = {
    role: {
      choices: [{ id:'support', label:'Support', icon:'#icon-support' }, { id:'dps', label:'DPS', icon:'#icon-sword' }],
      note: 'Only your role group matters here: tanks and healers play it one way, DPS the other.'
    },
    supports: {
      choices: ['T1', 'T2', 'H1', 'H2'].map(slotChoice).concat([{ id:'dps', label:'DPS' }]),
      note: 'Each support has their own seat here; all four DPS play it the same way.'
    },
    slot: {
      choices: SLOTS.map(slotChoice),
      note: 'Your exact slot matters here: job, light party and position all come into it.'
    }
  };
  const isGroup = id => id === 'support' || id === 'dps';

  function updatePickers(){
    document.querySelectorAll('.player-card [data-choice]').forEach(b => {
      const id = b.dataset.choice;
      b.setAttribute('aria-pressed', String(isGroup(id) ? shared.role === id : shared.slot === id));
    });
  }

  function setSlot(slot){
    if(SLOTS.indexOf(slot) < 0 || slot === shared.slot) return;
    clearAutoTimer();
    shared.slot = slot;
    lastInGroup[shared.role] = slot;
    try{
      localStorage.setItem('twelfth-slot', slot);
      localStorage.setItem('twelfth-last-' + shared.role, slot);
    }catch(e){}
    updatePickers();
    shared.roleListeners.forEach(fn => fn());
  }
  function choose(id){
    if(isGroup(id)) setSlot(shared.role === id ? shared.slot : lastInGroup[id]);
    else setSlot(id);
  }

  function pickerCard(mode, note){
    const p = PICKERS[mode];
    const card = document.createElement('div');
    card.className = 'card player-card';
    const h = document.createElement('h2');
    h.textContent = 'Playing as';
    card.appendChild(h);
    const row = document.createElement('div');
    row.className = 'role-select player-select cols-' + p.choices.length;
    row.setAttribute('role', 'group');
    row.setAttribute('aria-label', 'Choose who you play');
    p.choices.forEach(c => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'role-btn';
      b.dataset.choice = c.id;
      if(c.icon){
        const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        svg.setAttribute('viewBox', '0 0 24 24');
        svg.setAttribute('fill', c.id === 'dps' ? 'currentColor' : 'none');
        svg.setAttribute('stroke', 'currentColor');
        const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
        use.setAttribute('href', c.icon);
        svg.appendChild(use);
        b.appendChild(svg);
      }
      const label = document.createElement('span');
      label.textContent = c.label;
      if(c.color) label.style.color = c.color;
      b.appendChild(label);
      b.addEventListener('click', () => choose(c.id));
      row.appendChild(b);
    });
    card.appendChild(row);
    const n = document.createElement('p');
    n.className = 'player-note hint-only';
    n.textContent = note || p.note;
    card.appendChild(n);
    return card;
  }

  /* ---------- the step's ask ---------- */
  // Every drill writes its step text into its own .instr-text element. That element moves out of the
  // side column to sit right under the step pill, and the last sentence — the actual ask — is set
  // apart from the scene-setting that comes before it.
  const balancedTags = h => (h.match(/<(?!\/)/g) || []).length === (h.match(/<\//g) || []).length;
  function splitAsk(html){
    if(!html) return html;
    let cut = -1, m;
    const re = /[.!?]["’”)]?\s+/g;
    while((m = re.exec(html)) !== null){
      const end = m.index + m[0].length;
      if(balancedTags(html.slice(0, end))) cut = end;
    }
    return cut > 0
      ? `<span class="prompt-note">${html.slice(0, cut)}</span><span class="prompt-ask">${html.slice(cut)}</span>`
      : `<span class="prompt-ask">${html}</span>`;
  }
  // Against the clock the step text changes as the fight moves on, and each change would shove the arena
  // below it up or down just as you go to click. A drill hands over every text a pull can show, and the box
  // keeps the height of the tallest: measured once the drill is on screen, and again if the width or the
  // hints setting changes.
  // var, not const: the hints setting asks for a re-measure while the page is still starting up
  var heldPrompts = {};
  const nativeHTML = Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML');
  // On wide screens the step text sits in a column beside the arena, where its height moves nothing, so
  // it is only held when that column sits above the arena.
  function leadBeside(id){
    const panel = document.getElementById('panel-' + id);
    const lead = panel && panel.querySelector('.lead'), wrap = panel && panel.querySelector('.arena-wrap');
    return !!(lead && wrap && lead.getBoundingClientRect().right <= wrap.getBoundingClientRect().left + 1);
  }
  function measurePrompt(id){
    const held = heldPrompts[id], panel = document.getElementById('panel-' + id);
    const p = panel && panel.querySelector('.instr-text');
    if(!p) return;
    if(!held){ p.style.minHeight = ''; return; }
    if(panel.hidden || !p.offsetWidth || held.width === p.offsetWidth) return;
    if(leadBeside(id)){ p.style.minHeight = ''; held.width = p.offsetWidth; return; }
    const saved = nativeHTML.get.call(p);
    p.style.minHeight = '';
    let max = 0;
    held.texts.forEach(h => { p.innerHTML = h; max = Math.max(max, p.getBoundingClientRect().height); });
    nativeHTML.set.call(p, saved);
    p.style.minHeight = Math.ceil(max) + 'px';
    held.width = p.offsetWidth;
  }
  function holdPrompt(id, texts){
    heldPrompts[id] = texts ? { texts, width: 0 } : null;
    measurePrompt(id);
  }
  function remeasurePrompts(){
    if(!heldPrompts) return;
    Object.keys(heldPrompts).forEach(id => { if(heldPrompts[id]) heldPrompts[id].width = 0; measurePrompt(id); });
  }
  window.addEventListener('resize', remeasurePrompts);

  // The casts under a fight clock, always in the same number of rows (empty ones kept but unseen), so the
  // arena below never moves as casts come and go.
  function castRows(prefix, rows, now, idle, slots){
    const row = r => `<div class="${prefix}-cast${r.mine ? ' mine' : ''}"><span><b>${r.who}</b> · ${r.what}</span><span class="${prefix}-left">${Math.max(0, r.to - now).toFixed(1)}</span><span class="${prefix}-cast-bar"><i style="transform:scaleX(${Math.min(1, (now - r.from) / (r.to - r.from)).toFixed(3)})"></i></span></div>`;
    const blank = text => `<div class="${prefix}-cast"${text ? '' : ' aria-hidden="true" style="visibility:hidden"'}><span${text ? ` class="${prefix}-idle"` : ''}>${text || '&nbsp;'}</span><span class="${prefix}-left">${text ? '' : '0.0'}</span><span class="${prefix}-cast-bar" style="visibility:hidden"></span></div>`;
    const out = rows.length ? rows.map(row) : [blank(idle)];
    while(out.length < (slots || 1)) out.push(blank(''));
    return out.join('');
  }

  function promoteInstruction(id){
    const panel = document.getElementById('panel-' + id);
    const p = panel && panel.querySelector('.instr-text');
    const row = panel && panel.querySelector('.step-row');
    if(!p || !row) return;
    const card = p.closest('.card');
    const box = document.createElement('div');
    box.className = 'prompt';
    box.appendChild(p);
    row.insertAdjacentElement('afterend', box);
    if(card && !card.querySelector('.instr-text')) card.remove();
    // the split happens as the drill writes, so a replayed pull rebuilds exactly the same markup
    const native = Object.getOwnPropertyDescriptor(Element.prototype, 'innerHTML');
    Object.defineProperty(p, 'innerHTML', {
      configurable: true,
      get(){ return native.get.call(p); },
      set(v){ native.set.call(p, splitAsk(String(v))); }
    });
  }

  /* ---------- mechanics + tabs ---------- */
  // Each file under mechanics/ calls Twelfth.register(); start() then builds the tabs and panels
  // in registration order.
  const mechanics = [];
  const TABS = [];
  let currentTab = '';

  // While the trainer is being playtested only these drills are open. The rest stay in the list under a
  // neutral name, locked, so their titles and phases give nothing away. Add an id here to open it again.
  const OPEN = ['para1', 'engrave', 'superchain'];
  const PHASE_NAME = { 'Athena':'Phase 1', 'Pallas Athena':'Phase 2' };

  function register(m){
    m.phase = PHASE_NAME[m.phase] || m.phase;
    if(OPEN.indexOf(m.id) < 0){
      m.locked = true;
      m.label = 'Mechanic ' + (mechanics.length + 1);
    }
    mechanics.push(m);
    TABS.push(m.id);
  }
  const isOpen = id => { const m = mechanics[TABS.indexOf(id)]; return !!m && !m.locked; };

  function selectTab(name){
    if(!isOpen(name)) name = TABS.find(isOpen);
    clearAutoTimer();
    currentTab = name;
    TABS.forEach(t => { document.getElementById('panel-' + t).hidden = (t !== name); });
    measurePrompt(name);
    updateMechNav();
    try{ localStorage.setItem('twelfth-tab', name); }catch(e){}
  }

  /* ---------- mechanic switcher ---------- */
  // One compact bar: step through the fight with the arrows, or open the list to jump anywhere.
  const pad2 = n => String(n).padStart(2, '0');
  const CHEVRON = d => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="${d}"/></svg>`;

  function buildMechNav(){
    const nav = document.getElementById('tabs');
    const groups = [];
    mechanics.forEach((m, i) => {
      if(!groups.length || groups[groups.length - 1].phase !== (m.phase || '')) groups.push({ phase: m.phase || '', items: [] });
      groups[groups.length - 1].items.push(`<li><button type="button" class="mech-item" data-mech="${m.id}"${m.locked ? ' disabled title="Not open yet"' : ''}><span class="mech-item-num">${pad2(i + 1)}</span><span>${m.label}</span>${m.locked ? '<span class="mech-lock">Soon</span>' : ''}</button></li>`);
    });
    nav.innerHTML = `
      <button type="button" class="icon-btn mech-step" id="mechPrev">${CHEVRON('M15 5l-7 7 7 7')}</button>
      <div class="mech-wrap">
        <button type="button" class="mech-current" id="mechBtn" aria-haspopup="true" aria-expanded="false" aria-controls="mechMenu">
          <span class="mech-num" id="mechNum"></span>
          <span class="mech-meta"><span class="mech-phase" id="mechPhase"></span><span class="mech-name" id="mechName"></span></span>
          <span class="mech-count" id="mechCount"></span>
          <span class="mech-caret">${CHEVRON('M6 9l6 6 6-6')}</span>
        </button>
        <div class="mech-menu" id="mechMenu" hidden>
          ${groups.map(g => `<div class="mech-group"><h2>${g.phase}</h2><ul>${g.items.join('')}</ul></div>`).join('')}
        </div>
      </div>
      <button type="button" class="icon-btn mech-step" id="mechNext">${CHEVRON('M9 5l7 7-7 7')}</button>`;

    const btn = document.getElementById('mechBtn'), menu = document.getElementById('mechMenu');
    const items = () => [...menu.querySelectorAll('.mech-item:not(:disabled)')];
    function openMenu(open, focusCurrent){
      menu.hidden = !open;
      btn.setAttribute('aria-expanded', String(open));
      if(open && focusCurrent) (menu.querySelector('[aria-current="true"]') || items()[0]).focus();
    }
    const step = d => {
      for(let i = TABS.indexOf(currentTab) + d; i >= 0 && i < TABS.length; i += d) if(isOpen(TABS[i])){ selectTab(TABS[i]); return; }
    };
    document.getElementById('mechPrev').addEventListener('click', () => step(-1));
    document.getElementById('mechNext').addEventListener('click', () => step(1));
    btn.addEventListener('click', e => { e.stopPropagation(); openMenu(menu.hidden, true); });
    btn.addEventListener('keydown', e => {
      if(e.key === 'ArrowDown' && menu.hidden){ e.preventDefault(); openMenu(true, true); }
    });
    menu.addEventListener('click', e => {
      const it = e.target.closest('.mech-item');
      if(!it || it.disabled) return;
      selectTab(it.dataset.mech);
      openMenu(false);
      btn.focus();
    });
    menu.addEventListener('keydown', e => {
      const list = items(), i = list.indexOf(document.activeElement);
      let to = -1;
      if(e.key === 'ArrowDown') to = (i + 1) % list.length;
      else if(e.key === 'ArrowUp') to = (i - 1 + list.length) % list.length;
      else if(e.key === 'Home') to = 0;
      else if(e.key === 'End') to = list.length - 1;
      else if(e.key === 'Escape'){ e.preventDefault(); openMenu(false); btn.focus(); return; }
      else if(e.key === 'Tab'){ openMenu(false); return; }
      if(to >= 0){ e.preventDefault(); list[to].focus(); }
    });
    document.addEventListener('click', e => {
      if(!menu.hidden && !menu.contains(e.target) && !btn.contains(e.target)) openMenu(false);
    });
  }

  function updateMechNav(){
    const i = TABS.indexOf(currentTab), m = mechanics[i];
    if(!m || !document.getElementById('mechBtn')) return;
    document.getElementById('mechNum').textContent = pad2(i + 1);
    document.getElementById('mechPhase').textContent = m.phase || '';
    document.getElementById('mechName').textContent = m.label;
    document.getElementById('mechCount').textContent = `of ${TABS.length}`;
    document.getElementById('mechBtn').setAttribute('aria-label', `Mechanic ${i + 1} of ${TABS.length}: ${m.label}, ${m.phase}. Choose another`);
    document.querySelectorAll('#mechMenu .mech-item').forEach(it => it.setAttribute('aria-current', String(it.dataset.mech === currentTab)));
    const near = d => { for(let k = i + d; k >= 0 && k < mechanics.length; k += d) if(!mechanics[k].locked) return mechanics[k]; return null; };
    const prev = near(-1), next = near(1);
    const pb = document.getElementById('mechPrev'), nb = document.getElementById('mechNext');
    pb.disabled = !prev; nb.disabled = !next;
    pb.setAttribute('aria-label', prev ? 'Previous mechanic: ' + prev.label : 'No previous mechanic');
    nb.setAttribute('aria-label', next ? 'Next mechanic: ' + next.label : 'No next mechanic');
    pb.title = prev ? prev.label : ''; nb.title = next ? next.label : '';
  }

  function shuffle(arr){
    const a = arr.slice();
    for(let i=a.length-1;i>0;i--){
      const j = Math.floor(Math.random()*(i+1));
      [a[i],a[j]] = [a[j],a[i]];
    }
    return a;
  }

  let autoTimer = null;
  function clearAutoTimer(){
    if(autoTimer){ clearTimeout(autoTimer); autoTimer = null; }
  }

  /* ---------- undo / redo ---------- */
  // Every pull is rebuilt from its random seed, so a history is just the seed plus the list of things
  // you clicked. Undo and redo rebuild the pull and replay that list up to the chosen point.
  // Each mechanic draws from its own random stream so switching tabs never disturbs another pull.
  const nativeRandom = Math.random;
  const streams = {};
  let activeStream = null;
  function seedStream(id, seed){ streams[id] = seed >>> 0; }
  Math.random = function(){
    if(activeStream === null || streams[activeStream] === undefined) return nativeRandom();
    let t = (streams[activeStream] = (streams[activeStream] + 0x6D2B79F5) >>> 0);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };

  const history = {};        // id -> { start, seed, actions, cursor }
  const pristine = {};       // id -> each static element's attributes and, for leaves, content

  // Drills redraw their own layers, but some leave attributes behind on the panel's fixed markup.
  // Putting that markup back exactly as shipped makes a replayed pull identical to the original.
  function capturePristine(id){
    const panel = document.getElementById('panel-' + id);
    pristine[id] = Array.prototype.filter.call(panel.querySelectorAll('*'),
      el => !el.closest('.player-card, .history-ctrls')).map(el => ({
        el,
        attrs: Array.prototype.map.call(el.attributes, a => [a.name, a.value]),
        html: el.children.length === 0 ? el.innerHTML : null
      }));
  }
  function restorePristine(id){
    (pristine[id] || []).forEach(rec => {
      const keep = {};
      rec.attrs.forEach(([n, v]) => { keep[n] = true; if(rec.el.getAttribute(n) !== v) rec.el.setAttribute(n, v); });
      Array.prototype.slice.call(rec.el.attributes).forEach(a => { if(!keep[a.name]) rec.el.removeAttribute(a.name); });
      if(rec.html !== null && rec.el.innerHTML !== rec.html) rec.el.innerHTML = rec.html;
    });
  }
  const pendingAuto = {};    // id -> the continue that auto-advance would have pressed
  let replaying = false;

  function trackRounds(id, start){
    history[id] = { start, seed:0, actions:[], cursor:0 };
    return history[id].reroll = function newRound(){
      const h = history[id];
      h.seed = Math.floor(nativeRandom() * 4294967296) >>> 0;
      h.actions = [];
      h.cursor = 0;
      seedStream(id, h.seed);
      activeStream = id;
      start();
      updateHistoryButtons(id);
    };
  }

  function record(id, action){
    const h = history[id];
    if(replaying || !h) return;
    h.actions.length = h.cursor;          // a new choice drops anything you could have redone
    h.actions.push(action);
    h.cursor++;
    updateHistoryButtons(id);
  }

  function replayTo(id, upto){
    const h = history[id];
    const panel = document.getElementById('panel-' + id);
    clearAutoTimer();
    replaying = true;
    try{
      seedStream(id, h.seed);
      activeStream = id;
      delete pendingAuto[id];
      restorePristine(id);
      h.start();
      for(let i = 0; i < upto; i++){
        const a = h.actions[i];
        if(a.kind === 'hit'){
          const el = panel.querySelectorAll('.hit')[a.index];
          const ev = new MouseEvent('click', { bubbles:true });
          if(a.at) ev.freeAt = a.at;
          if(el) el.dispatchEvent(ev);
        } else if(a.kind === 'btn'){
          const el = panel.querySelectorAll('.feedback .btn')[a.index];
          if(el) el.click();
        } else if(a.kind === 'auto' && pendingAuto[id]){
          const go = pendingAuto[id];
          delete pendingAuto[id];
          go();
        }
      }
    } finally {
      replaying = false;
    }
    h.cursor = upto;
    updateHistoryButtons(id);
  }

  // Rewind is undo all the way back to step 1, so redo still walks forward again.
  function rewind(id){
    const h = history[id];
    if(h && h.cursor > 0) replayTo(id, 0);
  }
  function reroll(id){
    const h = history[id];
    if(h && h.reroll){ clearAutoTimer(); h.reroll(); }
  }

  function undo(id, depth){
    const h = history[id];
    if(h && h.cursor > 0) replayTo(id, Math.max(0, h.cursor - (depth || 1)));
  }
  function redo(id){
    const h = history[id];
    if(h && h.cursor < h.actions.length) replayTo(id, h.cursor + 1);
  }

  function updateHistoryButtons(id){
    const h = history[id];
    const panel = document.getElementById('panel-' + id);
    if(!h || !panel) return;
    const u = panel.querySelector('[data-history="undo"]'), r = panel.querySelector('[data-history="redo"]');
    const w = panel.querySelector('[data-history="rewind"]');
    if(u) u.disabled = h.cursor === 0;
    if(w) w.disabled = h.cursor === 0;
    if(r) r.disabled = h.cursor >= h.actions.length;
  }

  // A freeform pick (a .hit with data-free) answers with a spot, not just a click: the point in the arena's
  // own coordinates. A replayed click carries it along; a keyboard pick reads it off data-x and data-y.
  function freePoint(el, e){
    if(e && e.freeAt) return e.freeAt.slice();
    if(e && typeof e.clientX === 'number' && (e.clientX || e.clientY)){
      const svg = el.ownerSVGElement || el, m = svg.getScreenCTM && svg.getScreenCTM();
      if(m){
        const p = new DOMPoint(e.clientX, e.clientY).matrixTransform(m.inverse());
        return [Math.round(p.x * 10) / 10, Math.round(p.y * 10) / 10];
      }
    }
    return [+el.getAttribute('data-x'), +el.getAttribute('data-y')];
  }

  /* ---------- the recap of your runs, against the clock ---------- */
  // Each drill logs the runs it gives you as { at, t0, dur }: when it was set, when you set off and for how
  // long you run. A run ends when it reaches its spot or the next one replaces it, and runs that follow
  // straight on from each other, with no more than a beat standing still between, are one stretch on the
  // move.
  function movingSpans(track){
    const spans = [];
    track.forEach((m, k) => {
      const end = Math.min(m.t0 + m.dur, k + 1 < track.length ? track[k + 1].at : Infinity);
      if(end <= m.t0) return;
      const last = spans[spans.length - 1];
      if(last && m.t0 - last[1] <= 0.1) last[1] = Math.max(last[1], end);
      else spans.push([m.t0, end]);
    });
    return spans;
  }
  // For a part you could set off for at `since` that resolves at `deadline`: when you set off and when you
  // came to a stop (Infinity if you were still moving when it resolved), or null if you never moved between.
  function runRecap(track, since, deadline){
    const span = movingSpans(track).filter(s => s[1] > since && s[0] < deadline).pop();
    if(!span) return null;
    return { t: Math.max(span[0], since), ready: span[1] <= deadline ? span[1] : Infinity };
  }
  // The same, as words for a recap line; `idle` is what to say if you never moved.
  function recapText(r, deadline, idle){
    if(!r) return idle || 'already in place';
    if(r.ready === Infinity) return `set off at <b>${r.t.toFixed(1)} s</b>, still on the move when it went off`;
    return `set off at <b>${r.t.toFixed(1)} s</b>, in place at <b>${r.ready.toFixed(1)} s</b>, ${(deadline - r.ready).toFixed(1)} s to spare`;
  }

  // Watches a panel for the clicks that move a pull along: answers on the arena and feedback buttons.
  function watchPanel(id){
    const panel = document.getElementById('panel-' + id);
    const hitIndex = el => Array.prototype.indexOf.call(panel.querySelectorAll('.hit'), el);
    const hitAction = (hit, e) => hit.hasAttribute('data-free')
      ? { kind:'hit', index: hitIndex(hit), at: freePoint(hit, e) }
      : { kind:'hit', index: hitIndex(hit) };
    panel.addEventListener('click', e => {
      if(replaying) return;
      activeStream = id;
      const hit = e.target.closest && e.target.closest('.hit');
      if(hit && panel.contains(hit) && hit.getAttribute('aria-disabled') !== 'true'){
        record(id, hitAction(hit, e));
        return;
      }
      const btn = e.target.closest && e.target.closest('.feedback .btn');
      if(btn && panel.contains(btn) && !btn.hasAttribute('data-fb-undo')){
        record(id, { kind:'btn', index: Array.prototype.indexOf.call(panel.querySelectorAll('.feedback .btn'), btn) });
      }
    }, true);
    panel.addEventListener('keydown', e => {
      if(replaying || (e.key !== 'Enter' && e.key !== ' ')) return;
      activeStream = id;
      const hit = e.target.closest && e.target.closest('.hit');
      if(hit && panel.contains(hit) && hit.getAttribute('aria-disabled') !== 'true'){
        record(id, hitAction(hit, null));
      }
    }, true);
  }

  function historyControls(id){
    const wrap = document.createElement('div');
    wrap.className = 'history-ctrls';
    const ACTIONS = {
      rewind: () => rewind(id), undo: () => undo(id), redo: () => redo(id), reroll: () => reroll(id)
    };
    [
      ['rewind', 'Rewind', '#icon-rewind', 'Back to step 1 of this pull'],
      ['undo', 'Undo', '#icon-undo', 'Undo (Ctrl+Z)'],
      ['redo', 'Redo', '#icon-redo', 'Redo (Ctrl+Shift+Z)'],
      ['reroll', 'Reroll', '#icon-reroll', 'Deal a new pull']
    ].forEach(([kind, label, icon, tip]) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.className = 'history-btn' + (kind === 'reroll' ? ' history-reroll' : '');
      b.dataset.history = kind;
      b.title = tip;
      b.setAttribute('aria-label', tip);
      b.disabled = kind !== 'reroll';
      const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      svg.setAttribute('viewBox', '0 0 24 24');
      const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
      use.setAttribute('href', icon);
      svg.appendChild(use);
      b.appendChild(svg);
      const span = document.createElement('span');
      span.textContent = label;
      b.appendChild(span);
      b.addEventListener('click', ACTIONS[kind]);
      wrap.appendChild(b);
    });
    return wrap;
  }

  document.addEventListener('keydown', e => {
    if(!(e.ctrlKey || e.metaKey) || e.altKey) return;
    const tag = (e.target.tagName || '').toLowerCase();
    if(tag === 'input' || tag === 'textarea') return;
    const key = e.key.toLowerCase();
    if(key === 'z' && !e.shiftKey){ e.preventDefault(); undo(currentTab); }
    else if((key === 'z' && e.shiftKey) || key === 'y'){ e.preventDefault(); redo(currentTab); }
  });

  // `good` is true, false, or 'warn': a pass that could have been done better, which never auto-advances.
  function showFeedback(fb, good, title, body, btnLabel, onNext, extraActions){
    clearAutoTimer();
    const warn = good === 'warn';
    fb.hidden = false;
    fb.dataset.verdict = warn ? 'warn' : good ? 'good' : 'bad';
    // A drill whose answer took two clicks (a choice, then a spot for it) sets data-undo-depth so this
    // feedback's Undo takes the whole answer back, not just the last click.
    const undoDepth = Math.max(1, +(fb.dataset.undoDepth || 1));
    delete fb.dataset.undoDepth;
    // A run against the clock cannot be stepped back, so it sets data-no-undo to leave the Undo out.
    const noUndo = fb.dataset.noUndo === '1';
    delete fb.dataset.noUndo;
    fb.innerHTML = `<div class="feedback-head">${warn ? '!' : good ? '✓' : '✕'} ${title}</div><div class="feedback-body">${body}</div>`;

    // Auto-advance only carries you on through a pull, never into a fresh one.
    const continues = /^Continue/.test(btnLabel);
    const panel = fb.closest('.layout');
    const id = panel ? panel.id.replace('panel-', '') : null;
    if(good && continues && id) pendingAuto[id] = onNext;
    if(good === true && continues && shared.autoAdvance && !replaying){
      const note = document.createElement('div');
      note.className = 'auto-note';
      note.innerHTML = '<span>Advancing…</span><span class="auto-bar"><i></i></span>';
      fb.appendChild(note);
      autoTimer = setTimeout(() => {
        autoTimer = null;
        if(id){ activeStream = id; delete pendingAuto[id]; record(id, { kind:'auto' }); }
        onNext();
      }, AUTO_DELAY);
      fb.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
      return;
    }

    const row = document.createElement('div');
    row.className = 'btn-row';
    // Undo takes back exactly the last answer and is not itself recorded. After a wrong answer it is
    // the main way on, so it comes first; after a warning it sits beside Continue.
    const undoBtn = main => {
      const u = document.createElement('button');
      u.className = 'btn fb-undo' + (main ? ' bad' : ' ghost');
      u.dataset.fbUndo = '';
      u.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true"><use href="#icon-undo"/></svg><span>Undo last action</span>';
      u.addEventListener('click', () => { clearAutoTimer(); undo(id, undoDepth); });
      return u;
    };
    const canUndo = id && !noUndo;
    if(good === false && canUndo) row.appendChild(undoBtn(true));
    const btn = document.createElement('button');
    btn.className = good === false && canUndo ? 'btn ghost' : 'btn' + (good ? '' : ' bad');
    btn.textContent = btnLabel;
    btn.addEventListener('click', () => { clearAutoTimer(); onNext(); });
    row.appendChild(btn);
    if(warn && canUndo) row.appendChild(undoBtn(false));
    (extraActions || []).forEach(a => {
      const b = document.createElement('button');
      b.className = 'btn ghost';
      b.textContent = a.label;
      b.addEventListener('click', () => { clearAutoTimer(); a.onClick(); });
      row.appendChild(b);
    });
    fb.appendChild(row);

    if(good === true && continues){
      const lab = document.createElement('label');
      lab.className = 'auto-row';
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      const txt = document.createTextNode('Automatically advance to the next step');
      cb.addEventListener('change', () => {
        if(!cb.checked) return;
        setAutoAdvance(true);
        lab.className = 'auto-row done';
        lab.textContent = '✓ On — the next correct answer advances by itself.';
      });
      lab.appendChild(cb);
      lab.appendChild(txt);
      fb.appendChild(lab);
    }
    // After a wrong answer, offer hint mode right there: the step's tells appear in place as soon as it is on.
    if(good === false){
      const lab = document.createElement('label');
      lab.className = 'auto-row hint-row';
      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = shared.hints;
      cb.addEventListener('change', () => setHints(cb.checked));
      lab.appendChild(cb);
      lab.appendChild(document.createTextNode('Show hints — each step adds the rule it asks you to read'));
      fb.appendChild(lab);
    }
    if(!replaying) fb.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }

  /* ---------- add lasers ---------- */
  // Plays each line AoE once: from its add, through its target, on to the edge of the floor. A one-off
  // effect, so a rebuilt pull (undo, redo) never replays it.
  const beamTimers = new WeakMap();
  // Where you should have been, shown when an answer fails: the rest of the floor dims, with a ring on
  // the right spot and, if you were somewhere else, a dashed line from there to it. Both spots stay lit.
  function drawTarget(host, at, from){
    const NS = 'http://www.w3.org/2000/svg';
    const mk = (name, attrs) => { const n = document.createElementNS(NS, name); for(const k in attrs) n.setAttribute(k, attrs[k]); return n; };
    const [x, y] = at.map(v => +v.toFixed(1));
    const g = mk('g', { class:'target-mark', 'pointer-events':'none' });
    const hole = (cx, cy, r) => `M${(cx - r).toFixed(1)} ${cy.toFixed(1)}a${r} ${r} 0 1 0 ${2 * r} 0a${r} ${r} 0 1 0 ${-2 * r} 0Z`;
    g.appendChild(mk('path', { d: 'M60 60H540V540H60Z' + hole(x, y, 30) + (from ? hole(from[0], from[1] + 8, 32) : ''),
      'fill-rule':'evenodd', class:'target-dim' }));
    if(from){
      const dx = x - from[0], dy = y - from[1], len = Math.hypot(dx, dy);
      if(len > 40){
        const ux = dx / len, uy = dy / len;
        g.appendChild(mk('line', { x1:(from[0] + ux * 16).toFixed(1), y1:(from[1] + uy * 16).toFixed(1),
          x2:(x - ux * 22).toFixed(1), y2:(y - uy * 22).toFixed(1), class:'target-path' }));
      }
    }
    g.appendChild(mk('circle', { cx:x, cy:y, r:19, class:'target-ring' }));
    g.appendChild(mk('circle', { cx:x, cy:y, r:3.5, class:'target-dot' }));
    // the label sits beside the ring, away from the middle line, and flips if it would leave the floor
    let side = x >= 300 ? 1 : -1;
    if(x + side * 92 > 540 || x + side * 92 < 60) side = -side;
    const label = mk('text', { x: x + side * 26, y: y + 3.5, 'text-anchor': side > 0 ? 'start' : 'end', class:'target-label' });
    label.textContent = 'YOUR SPOT';
    g.appendChild(label);
    host.appendChild(g);
    return g;
  }

  function playBeams(host, beams, bounds){
    const NS = 'http://www.w3.org/2000/svg';
    const W = 44, PULSE = 26, TRAIL = 70, h = W / 2;
    const b = Object.assign({ x0:60, y0:60, x1:540, y1:540 }, bounds || {});
    host.innerHTML = '';
    clearTimeout(beamTimers.get(host));
    if(replaying) return;
    const mk = (name, attrs) => { const n = document.createElementNS(NS, name); for(const k in attrs) n.setAttribute(k, attrs[k]); return n; };
    beams.forEach(({ from, through }) => {
      const dx = through[0] - from[0], dy = through[1] - from[1], len = Math.hypot(dx, dy) || 1, ux = dx / len, uy = dy / len;
      const exits = [];
      if(ux > 0) exits.push((b.x1 - through[0]) / ux); if(ux < 0) exits.push((b.x0 - through[0]) / ux);
      if(uy > 0) exits.push((b.y1 - through[1]) / uy); if(uy < 0) exits.push((b.y0 - through[1]) / uy);
      const t = Math.max(0, Math.min(...exits));
      const x1 = from[0] + ux * 18, y1 = from[1] + uy * 18;
      const run = Math.hypot(through[0] + ux * t - x1, through[1] + uy * t - y1);
      const grp = mk('g', { class:'beam', transform:`translate(${x1},${y1}) rotate(${Math.atan2(uy, ux) * 180 / Math.PI})` });
      grp.appendChild(mk('rect', { x:0, y:-h, width:run, height:W, fill:'rgba(247,147,30,0.34)', stroke:'var(--aether)', 'stroke-width':1.5, class:'beam-band' }));
      // the pulse: a soft crescent bowed forward, horns trailing at the edges, with a streak behind it
      const crescent = (back, apex, inner, fill, alpha) =>
        mk('path', { d:`M${back} ${-h} Q${back + 2 * apex} 0 ${back} ${h} Q${back + 2 * inner} 0 ${back} ${-h} Z`, fill, 'fill-opacity':alpha });
      const pulse = mk('g', { class:'beam-pulse' });
      pulse.appendChild(mk('rect', { x:-PULSE - TRAIL, y:-h * 0.62, width:TRAIL + PULSE * 0.7, height:h * 1.24, rx:h * 0.62, fill:'url(#beam-trail)' }));
      const wave = mk('g', { filter:'url(#beam-soft)' });
      wave.appendChild(crescent(-PULSE, PULSE, PULSE * 0.45, 'var(--aether)', 0.3));
      wave.appendChild(crescent(-PULSE * 0.55, PULSE * 0.55 + 6, PULSE * 0.55 - 8, '#fbe7ae', 0.78));
      pulse.appendChild(wave);
      pulse.style.setProperty('--run', run + 'px');
      grp.appendChild(pulse);
      host.appendChild(grp);
    });
    beamTimers.set(host, setTimeout(() => { host.innerHTML = ''; }, 1700));
  }

  // Paradeigma's adds appear on a ring around Athena (at 300,300), about her hitbox, and zoom out to their
  // spots. `at` is where the add ends up; `offset` is any translation its element already carries; `from`,
  // if given, is where on the ring it starts (otherwise the point facing its spot).
  const HITBOX_R = 120;
  function zoomAdd(node, at, offset, delay, from){
    const o = offset || [0, 0];
    const dx = at[0] - 300, dy = at[1] - 300, len = Math.hypot(dx, dy) || 1;
    const f = from || [300 + dx / len * HITBOX_R, 300 + dy / len * HITBOX_R];
    const sx = f[0] - at[0] + o[0], sy = f[1] - at[1] + o[1];
    node.classList.add('add-zoom');
    node.style.setProperty('--zx', sx.toFixed(1) + 'px');
    node.style.setProperty('--zy', sy.toFixed(1) + 'px');
    node.style.setProperty('--tx', o[0].toFixed(1) + 'px');
    node.style.setProperty('--ty', o[1].toFixed(1) + 'px');
    node.style.animationDelay = (delay || 0).toFixed(2) + 's';
  }
  function unzoomAdd(node){
    node.classList.remove('add-zoom');
    ['--zx', '--zy', '--tx', '--ty', 'animation-delay'].forEach(k => node.style.removeProperty(k));
    if(!node.getAttribute('style')) node.removeAttribute('style');
    if(!node.getAttribute('class')) node.removeAttribute('class');
  }

  function aspectColor(a){ return a === 'astral' ? 'var(--astral)' : 'var(--umbral)'; }
  function aspectSoft(a){ return a === 'astral' ? 'var(--astral-soft)' : 'var(--umbral-soft)'; }
  function aspectLabel(a){ return a === 'astral' ? 'Astral' : 'Umbral'; }
  function tiltIcon(a){ return a === 'astral' ? 'assets/astral-tilt.png' : 'assets/umbral-tilt.png'; }
  function soulIcon(a){ return a === 'astral' ? 'assets/astralbright-soul.png' : 'assets/umbralbright-soul.png'; }

  function start(){
    const page = document.querySelector('.page');
    mechanics.forEach(m => {
      if(m.styles){
        const style = document.createElement('style');
        style.textContent = m.styles;
        document.head.appendChild(style);
      }
      page.insertAdjacentHTML('beforeend', m.markup);
      // panels were written as tabs; they are plain named regions under the switcher
      const panel = document.getElementById('panel-' + m.id);
      panel.setAttribute('role', 'region');
      panel.removeAttribute('aria-labelledby');
      panel.setAttribute('aria-label', m.label);
      if(m.players){
        const hud = document.querySelector('#panel-' + m.id + ' .hud');
        hud.insertBefore(pickerCard(m.players, m.playersNote), hud.firstChild);
      }
    });
    mechanics.forEach(m => promoteInstruction(m.id));
    // The step pill, its ask and the fight clock move into a column of their own: left of the arena on wide
    // screens, above it on narrower ones, so nothing above the arena ever changes height and moves it.
    mechanics.forEach(m => {
      const panel = document.getElementById('panel-' + m.id), wrap = panel.querySelector('.arena-wrap');
      if(!wrap) return;
      const lead = document.createElement('div');
      lead.className = 'lead';
      ['.step-row', '.prompt', '[id$="-live"]'].forEach(sel => {
        const el = wrap.querySelector(':scope > ' + sel);
        if(el) lead.appendChild(el);
      });
      panel.insertBefore(lead, wrap);
      const fb = wrap.querySelector(':scope > .feedback');
      if(fb) wrap.after(fb);
    });
    // On wide screens the step pill and its undo row go back to the top of the arena, and the left column
    // takes the feedback, right under the ask, then the pace and how the call works; narrower, the step row
    // heads the stacked column again, the feedback goes back under the arena and the cards back into the
    // side column where they were.
    const leadParts = mechanics.map(m => {
      const panel = document.getElementById('panel-' + m.id);
      const lead = panel.querySelector('.lead'), hud = panel.querySelector('.hud'), wrap = panel.querySelector('.arena-wrap');
      if(!lead || !hud) return null;
      const cards = Array.prototype.filter.call(hud.children, c => c.matches('details.card') || !!c.querySelector('[data-pace]'))
        .map(c => ({ c, at: Array.prototype.indexOf.call(hud.children, c) }));
      return { lead, hud, wrap, row: panel.querySelector('.step-row'), fb: panel.querySelector('.feedback'), cards };
    }).filter(Boolean);
    function placeLead(){
      leadParts.forEach(({ lead, hud, wrap, row, fb, cards }) => {
        if(threeColumns()){
          if(row) wrap.insertBefore(row, wrap.firstChild);
          if(fb) lead.appendChild(fb);
          cards.forEach(({ c }) => lead.appendChild(c));
        } else {
          if(row) lead.insertBefore(row, lead.firstChild);
          if(fb) wrap.after(fb);
          cards.forEach(({ c, at }) => hud.insertBefore(c, hud.children[at] || null));
        }
      });
      remeasurePrompts();
    }
    onLayout = placeLead;
    placeLead();
    buildMechNav();
    updatePickers();
    mechanics.forEach(m => {
      const row = document.querySelector('#panel-' + m.id + ' .step-row');
      if(row) row.appendChild(historyControls(m.id));
      watchPanel(m.id);
    });
    mechanics.forEach(m => m.init());
    // taken after start-up, so one-off content like legends is part of the baseline
    mechanics.forEach(m => capturePristine(m.id));

    let initialTab = TABS.find(isOpen);
    try{
      const savedTab = localStorage.getItem('twelfth-tab');
      if(isOpen(savedTab)) initialTab = savedTab;
    }catch(e){}
    selectTab(initialTab);

    function boot(data){
      if(data && data.slot){ setSlot(data.slot); }
      else if(data && data.role){ choose(data.role); }
      if(data && typeof data.auto === 'boolean'){ setAutoAdvance(data.auto); }
      if(data && data.tab){ selectTab(data.tab); }
    }
    function snapshot(){ return { slot: shared.slot, tab: currentTab, auto: shared.autoAdvance }; }

    if(window.claude && window.claude.hot){
      window.claude.hot.snapshot(snapshot);
      window.claude.hot.ready ? window.claude.hot.ready(boot) : boot(window.claude.hot.data || {});
    }
  }

  return {
    shared, shuffle, showFeedback, trackRounds,
    isReplaying: () => replaying, playBeams, freePoint, runRecap, recapText, zoomAdd, unzoomAdd, drawTarget, holdPrompt, castRows, leadBeside,
    aspectColor, aspectSoft, aspectLabel, tiltIcon, soulIcon,
    register, start
  };
})();
