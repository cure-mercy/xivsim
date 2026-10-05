/* Gaiaochos II: break Missing Link into the safe corner, spread in the narrow lane, then two sets of Ultima Blow tethers. */
(function(T){

  const { shared, showFeedback } = T;

  const STYLES = /* css */ `
    .g2-slot{
      font-family: var(--font-mono); font-weight: 700; font-size: 1.3rem;
      width: 52px; height: 52px; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
      border-radius: 14px; border: 1px solid var(--line-strong); background: rgba(241,236,249,0.05);
    }
    .g2-debuffs{ display: flex; flex-wrap: wrap; gap: 8px 16px; margin-top: 12px; }
    .g2-debuff{ display: flex; align-items: center; gap: 8px; font-size: 0.88rem; color: var(--mist-dim); }
    .g2-debuff img{ width: 24px; height: 32px; border-radius: 4px; flex-shrink: 0; object-fit: contain; }
    .g2-debuff svg{ width: 24px; height: 24px; flex-shrink: 0; color: var(--shape-purple); }
    .g2-debuff b{ color: var(--mist); font-weight: 600; }
  `;

  const MARKUP = /* html */ `
  <div class="layout" id="panel-gaiaochos2" role="tabpanel" aria-labelledby="tabBtn-gaiaochos2" hidden>

    <section class="arena-wrap">
      <div class="step-row">
        <span class="step-pill" id="g2-stepPill">Step 1 · Missing Link</span>
      </div>

      <svg class="arena-svg" id="g2-arena" viewBox="0 0 600 600" role="img" aria-label="Top-down view of the shrunken round arena during the second Gaiaochos">
        <defs>
          <clipPath id="g2-clip"><circle cx="300" cy="300" r="240"/></clipPath>
        </defs>
        <circle cx="300" cy="300" r="240" fill="url(#floor)" pointer-events="none"/>
        <circle cx="300" cy="300" r="240" fill="url(#weaveZoom)" pointer-events="none"/>
        <g font-family="Space Mono, monospace" font-size="12" font-weight="700" fill="var(--mist-faint)" text-anchor="middle" pointer-events="none">
          <text x="300" y="22">N</text><text x="300" y="590">S</text><text x="14" y="304">W</text><text x="586" y="304">E</text>
        </g>
        <g id="g2-under" clip-path="url(#g2-clip)" pointer-events="none"></g>
        <g id="g2-over" pointer-events="none"></g>
        <g id="g2-players" pointer-events="none"></g>
        <g id="g2-hits"></g>
        <circle cx="300" cy="300" r="240" fill="none" stroke="rgba(247,147,30,0.55)" stroke-width="2" filter="url(#glow)" pointer-events="none"/>
      </svg>

      <p class="arena-caption" id="g2-caption">North is up. Gaiaochos has shrunk the floor to this small circle again, shown close up.</p>

      <div class="feedback" id="g2-feedback" hidden aria-live="polite"></div>
    </section>

    <aside class="hud">
      <div class="card">
        <h2>Your slot</h2>
        <div class="lc-row">
          <div class="g2-slot" id="g2-slot">H1</div>
          <p class="assign-text" id="g2-assignText"></p>
        </div>
        <div class="g2-debuffs" id="g2-debuffs"></div>
      </div>

      <div class="card">
        <h2>Objective</h2>
        <p class="instr-text" id="g2-instrText"></p>
      </div>

      <details class="card">
        <summary>How the call works</summary>
        <ol>
          <li><b>Gaiaochos</b> shrinks the floor and gives everyone <b>Ascended</b> again. Stack in the middle.</li>
          <li><b>Summon Darkness</b> puts a single add on an <b>intercardinal</b>. Its line runs across that diagonal, so the other two intercardinal corners are safe. <b>Demi Parhelion</b> and <b>Geocentrism</b> follow straight away, but only as <b>rows or columns</b>, never the donut.</li>
          <li>When <b>Missing Link</b> appears, break it: <b>supports</b> run to the <b>north</b> safe corner, <b>DPS</b> to the <b>south</b> one, both inside the narrow safe row or column.</li>
          <li>Spread there for <b>Divine Excoriation</b>. From the corner inwards: <b>healers</b> then <b>tanks</b>, and <b>ranged</b> then <b>melee</b>, so tanks and melee move further in.</li>
          <li><b>Summon Darkness</b> again: four adds, one on each line through the middle, tether all of one role. Tethered players take their tether to the <b>opposite wall</b>; their partner (T1 with M1, T2 with M2, H1 with R1, H2 with R2) stands on the line to share the <b>Ultima Blow</b>, just in front of them or out by their add, but not near the middle where the lines cross. Ultima, then the other role is tethered.</li>
        </ol>
      </details>

      <div class="card">
        <h2>Legend</h2>
        <div class="legend-list" id="g2-legend"></div>
      </div>
    </aside>

  </div>
  `;

  function initGaiaochos2(){
    const SVGNS = 'http://www.w3.org/2000/svg';
    const C = 300, R = 240;
    const P = (x, y) => [C + x * R, C + y * R];
    const DIRS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    const DIR_WORD = { N:'north', NE:'north-east', E:'east', SE:'south-east', S:'south', SW:'south-west', W:'west', NW:'north-west' };
    const ANGLE = d => (DIRS.indexOf(d) * 45 - 90) * Math.PI / 180;
    const OPP = d => DIRS[(DIRS.indexOf(d) + 4) % 8];

    const SLOTS = ['T1', 'T2', 'H1', 'H2', 'M1', 'M2', 'R1', 'R2'];
    const JOB = { T:'Tank', H:'Healer', M:'Melee DPS', R:'Ranged DPS' };
    const JOB_COLOR = { T:'var(--umbral-soft)', H:'var(--good)', M:'var(--astral-soft)', R:'var(--astral-soft)' };
    const isSupport = s => s[0] === 'T' || s[0] === 'H';
    const PARTNER = { T1:'M1', M1:'T1', T2:'M2', M2:'T2', H1:'R1', R1:'H1', H2:'R2', R2:'H2' };
    const PATTERN_WORD = { rows:'east to west', columns:'north to south' };
    const LANE = { rows:'row', columns:'column' };

    // Geocentrism and the lines, the same measures as the first Gaiaochos (fractions of the radius)
    const BAND = 0.25, GRID = 0.72, LANE_AT = 0.36, LINE_HALF = 0.17;
    const EXCORIATION_R = 0.1, BODY = 0.04;
    // where the groups run to along their lane, and the spread from the corner inwards
    const RUN_AT = 0.5, ALONG = [0.82, 0.57, 0.32, 0.07];
    const ORDER = { sup:['H1', 'H2', 'T1', 'T2'], dps:['R1', 'R2', 'M1', 'M2'] };
    // Ultima Blow
    const ADD_R = 1.1, WALL_R = 0.82, BLOCK_R = 0.55, ADD_SIDE_R = 0.7, DEEP_R = 0.2, BLOW_HALF = 0.12;

    let st = {};
    const fb = document.getElementById('g2-feedback');
    const pick = arr => arr[Math.floor(Math.random() * arr.length)];
    function shuffled(arr){
      const a = arr.slice();
      for(let i = a.length - 1; i > 0; i--){ const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
      return a;
    }

    function startRound(){
      st.me = shared.slot;
      st.add = pick(['NE', 'SE', 'SW', 'NW']);
      const safe = ['NE', 'SE', 'SW', 'NW'].filter(d => d !== st.add && d !== OPP(st.add));
      st.corner = { sup: safe.find(d => d[0] === 'N'), dps: safe.find(d => d[0] === 'S') };
      st.pattern = pick(['rows', 'columns']);
      // two sets of tethers, one per role, in a random order; one add on each line through the middle
      const first = pick(['sup', 'dps']);
      st.sets = [first, first === 'sup' ? 'dps' : 'sup'].map(role => {
        const adds = [['N', 'S'], ['NE', 'SW'], ['E', 'W'], ['SE', 'NW']].map(pick);
        const players = shuffled(SLOTS.filter(s => isSupport(s) === (role === 'sup')));
        const tether = {};
        players.forEach((s, i) => tether[s] = adds[i]);
        return { role, tether };
      });
      st.step = 1;
      render();
    }

    /* ---------- geometry ---------- */
    const groupOf = s => isSupport(s) ? 'sup' : 'dps';
    const cornerSign = d => [d.indexOf('E') >= 0 ? 1 : -1, d.indexOf('S') >= 0 ? 1 : -1];
    function laneSpot(pattern, corner, along){
      const [sx, sy] = cornerSign(corner);
      return pattern === 'rows' ? [sx * along, sy * LANE_AT] : [sx * LANE_AT, sy * along];
    }
    function inGeo(xy){
      const v = st.pattern === 'rows' ? xy[1] : xy[0];
      return [-GRID, 0, GRID].some(c => Math.abs(v - c) <= BAND);
    }
    function edgeSpot(d, r){ const a = ANGLE(d); return [Math.cos(a) * r, Math.sin(a) * r]; }
    function lineDist(d, xy){ const a = ANGLE(d); return Math.abs(-Math.sin(a) * xy[0] + Math.cos(a) * xy[1]); }
    function spreadSpot(s){
      const g = groupOf(s);
      return laneSpot(st.pattern, st.corner[g], ALONG[ORDER[g].indexOf(s)]);
    }
    function segDist(p, a, b){
      const dx = b[0] - a[0], dy = b[1] - a[1];
      const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)));
      return Math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy);
    }

    /* ---------- drawing ---------- */
    function el(name, attrs){
      const n = document.createElementNS(SVGNS, name);
      for(const k in attrs) n.setAttribute(k, attrs[k]);
      return n;
    }
    function layer(id){
      const g = document.getElementById(id);
      g.innerHTML = '';
      return g;
    }
    function hitable(g, onPick, value, label){
      g.setAttribute('class', 'hit');
      g.setAttribute('tabindex', '0');
      g.setAttribute('role', 'button');
      g.setAttribute('aria-label', label);
      g.addEventListener('click', () => onPick(value));
      g.addEventListener('keydown', e => {
        if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); onPick(value); }
      });
    }
    function lock(){
      document.querySelectorAll('#panel-gaiaochos2 .hit').forEach(h => h.setAttribute('aria-disabled', 'true'));
    }

    function drawPlayer(host, slot, xy, o){
      { const layerHost = host; host = el('g', { class: 'player' + (slot === st.me ? ' me' : (slot === PARTNER[st.me] || slot[0] === st.me[0] ? ' related' : '')) }); layerHost.appendChild(host); }   // your Ultima Blow partner and your job partner stay in view
      o = o || {};
      const [cx, cy] = P(xy[0], xy[1]);
      const me = slot === st.me;
      if(o.aoe) host.appendChild(el('circle', { cx, cy, r:EXCORIATION_R * R, fill:'rgba(226,82,63,0.18)', stroke:'var(--astral-soft)', 'stroke-width':1.2 }));
      if(me) host.appendChild(el('circle', { cx, cy, r:17, fill:'none', stroke:'var(--mist)', 'stroke-width':2.5, class:'pulse' }));
      host.appendChild(el('circle', { cx, cy, r:12, fill:'rgba(10,9,22,0.94)', stroke: me ? 'var(--mist)' : JOB_COLOR[slot[0]], 'stroke-width': me ? 2 : 1.6 }));
      const t = el('text', { x:cx, y:cy + 3.6, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':10, 'font-weight':700, fill:JOB_COLOR[slot[0]] });
      t.textContent = slot;
      host.appendChild(t);
      if(me){
        const you = el('text', { x:cx, y:cy + 27, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':9, 'font-weight':700, fill:'var(--mist)' });
        you.textContent = 'YOU';
        host.appendChild(you);
      }
    }
    function stackPositions(){
      const pos = {};
      SLOTS.forEach((s, i) => { const a = i * Math.PI / 4; pos[s] = [Math.cos(a) * 0.09, Math.sin(a) * 0.09]; });
      return pos;
    }
    // each group bunched up at its run spot, spread along the lane
    function cornerPositions(){
      const pos = {};
      ['sup', 'dps'].forEach(g => ORDER[g].forEach((s, i) => pos[s] = laneSpot(st.pattern, st.corner[g], RUN_AT + (1.5 - i) * 0.1)));
      return pos;
    }
    function drawParty(pos, opts){
      const host = layer('g2-players');
      SLOTS.slice().sort((a, b) => (a === st.me) - (b === st.me)).forEach(s => drawPlayer(host, s, pos[s], opts));
    }

    function drawAdd(host, d){
      const [x, y] = P(...edgeSpot(d, ADD_R));
      host.appendChild(el('circle', { cx:x, cy:y, r:15, fill:'rgba(10,9,22,0.9)', stroke:'var(--shape-purple)', 'stroke-width':2, filter:'url(#glow)' }));
      const u = el('use', { href:'#icon-add', x:x - 12, y:y - 12 });
      u.style.color = 'var(--shape-purple)';
      host.appendChild(u);
    }
    function band(host, a, b, half, attrs){
      const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy);
      const px = -dy / len * half * R, py = dx / len * half * R;
      const e1 = P(a[0], a[1]), e2 = P(b[0], b[1]);
      host.appendChild(el('path', Object.assign({ d:`M${e1[0]+px} ${e1[1]+py} L${e2[0]+px} ${e2[1]+py} L${e2[0]-px} ${e2[1]-py} L${e1[0]-px} ${e1[1]-py} Z` }, attrs)));
    }
    function drawRay(){
      band(document.getElementById('g2-under'), edgeSpot(st.add, 1.2), edgeSpot(OPP(st.add), 1.2), LINE_HALF,
        { fill:'rgba(176,131,234,0.30)', stroke:'var(--shape-purple)', 'stroke-width':1.5 });
    }
    function drawParhelion(){
      const host = document.getElementById('g2-under');
      [-GRID, 0, GRID].forEach(x => [-GRID, 0, GRID].forEach(y => {
        const [cx, cy] = P(x, y);
        host.appendChild(el('circle', { cx, cy, r:BAND * R, fill:'rgba(242,165,60,0.22)', stroke:'var(--shape-orange)', 'stroke-width':1.5, 'stroke-dasharray':'6 5' }));
      }));
    }
    function drawTentacles(){
      const host = document.getElementById('g2-over');
      const style = { fill:'none', stroke:'rgba(106,196,168,0.85)', 'stroke-width':9, 'stroke-linecap':'round', opacity:0.8 };
      [-0.5, 0.5].forEach(off => {
        const pts = [];
        for(let i = 0; i <= 40; i++){
          const t = -1 + i / 20;
          const bulge = off * Math.sqrt(Math.max(0, 1 - t * t)) * 1.1 + 0.03 * Math.sin(t * 14);
          pts.push(st.pattern === 'columns' ? [bulge, t * 0.98] : [t * 0.98, bulge]);
        }
        host.appendChild(el('path', Object.assign({ d: 'M' + pts.map(p => P(p[0], p[1]).join(' ')).join(' L') }, style)));
      });
    }
    function drawGeocentrism(){
      const host = document.getElementById('g2-under');
      const fill = { fill:'rgba(242,165,60,0.38)', stroke:'var(--shape-orange)', 'stroke-width':1.5 };
      [-GRID, 0, GRID].forEach(c => {
        const a = P(st.pattern === 'columns' ? c - BAND : -1.2, st.pattern === 'columns' ? -1.2 : c - BAND);
        const w = st.pattern === 'columns' ? 2 * BAND * R : 2.4 * R, h = st.pattern === 'columns' ? 2.4 * R : 2 * BAND * R;
        host.appendChild(el('rect', Object.assign({ x:a[0], y:a[1], width:w, height:h }, fill)));
      });
    }

    // Ultima Blow: from each add towards its tethered player, running on across the floor
    function blows(set, pos){
      return Object.keys(set.tether).map(s => {
        const a = edgeSpot(set.tether[s], ADD_R), to = pos[s];
        const dx = to[0] - a[0], dy = to[1] - a[1], len = Math.hypot(dx, dy) || 1;
        return { slot:s, a, b:[a[0] + dx / len * 2.4, a[1] + dy / len * 2.4] };
      });
    }
    function blowsOn(q, lines){ return lines.filter(l => segDist(q, l.a, l.b) <= BLOW_HALF + BODY).map(l => l.slot); }
    function drawTethers(set, pos){
      const host = document.getElementById('g2-over');
      Object.keys(set.tether).forEach(s => {
        const a = P(...edgeSpot(set.tether[s], ADD_R)), b = P(...pos[s]);
        host.appendChild(el('line', { x1:a[0], y1:a[1], x2:b[0], y2:b[1], stroke:'var(--shape-purple)', 'stroke-width': s === st.me || s === PARTNER[st.me] ? 2.6 : 1.6, 'stroke-dasharray':'7 5', opacity:0.9 }));
      });
      Object.keys(set.tether).forEach(s => drawAdd(host, set.tether[s]));
    }
    function drawBlows(lines){
      const host = document.getElementById('g2-under');
      lines.forEach(l => band(host, l.a, l.b, BLOW_HALF, { fill:'rgba(176,131,234,0.26)', stroke:'var(--shape-purple)', 'stroke-width':1.3 }));
    }

    function spotHits(spots, onPick){
      const host = layer('g2-hits');
      spots.forEach(s => {
        const [cx, cy] = P(s.at[0], s.at[1]);
        const g = el('g', {});
        g.appendChild(el('circle', { cx, cy, r:19, class:'focus-ring', fill:'none', stroke:'var(--mist)', 'stroke-width':2.5, opacity:0 }));
        g.appendChild(el('circle', { cx, cy, r:14, fill:'rgba(241,236,249,0.16)', stroke:'var(--mist)', 'stroke-width':2 }));
        hitable(g, onPick, s, s.label);
        host.appendChild(g);
      });
    }

    function legend(){
      const host = document.getElementById('g2-legend');
      const row = (lead, html) => `<div class="legend-item">${lead}<span>${html}</span></div>`;
      host.innerHTML =
          row('<img src="assets/ascended.png" alt="">', '<b>Ascended</b> — shrunk and slowed on the small floor')
        + row('<img src="assets/missing-link.png" alt="">', '<b>Missing Link</b> — chains each DPS to a support; break it by distance')
        + row('<svg viewBox="0 0 24 24" fill="var(--shape-purple)"><use href="#icon-add"/></svg>', '<b>Darkness add</b> — fires a line across the floor')
        + row('<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="rgba(242,165,60,0.25)" stroke="var(--shape-orange)" stroke-width="1.6" stroke-dasharray="3 2"/></svg>', '<b>Demi Parhelion</b> — nine circles the blasts spread from')
        + row('<svg viewBox="0 0 24 24"><path d="M5 20 Q12 2 19 20" fill="none" stroke="rgba(106,196,168,0.9)" stroke-width="3" stroke-linecap="round"/></svg>', '<b>Geocentrism tentacles</b> — which way the blasts spread')
        + row('<svg viewBox="0 0 24 24"><line x1="3" y1="21" x2="21" y2="3" stroke="var(--shape-purple)" stroke-width="2" stroke-dasharray="4 3"/></svg>', '<b>Ultima Blow tether</b> — a shared line from the add to its player');
    }

    /* ---------- render ---------- */
    function pill(t){ document.getElementById('g2-stepPill').textContent = t; }
    function instr(h){ document.getElementById('g2-instrText').innerHTML = h; }
    const setAt = step => step === 3 ? st.sets[0] : st.sets[1];
    const tethered = (set, s) => set.tether[s] !== undefined;

    function renderHud(){
      const s = st.me;
      const slot = document.getElementById('g2-slot');
      slot.textContent = s;
      slot.style.color = JOB_COLOR[s[0]];
      document.getElementById('g2-assignText').innerHTML = `${JOB[s[0]]}, a ${isSupport(s) ? 'support' : 'DPS'}. Your partner is <b>${PARTNER[s]}</b>.`;
      let chips = `<div class="g2-debuff"><img src="assets/ascended.png" alt=""><span><b>Ascended</b></span></div>`;
      if(st.step === 1) chips += `<div class="g2-debuff"><img src="assets/missing-link.png" alt=""><span><b>Missing Link</b></span></div>`;
      if(st.step >= 3 && tethered(setAt(st.step), s)) chips += `<div class="g2-debuff"><svg viewBox="0 0 24 24"><use href="#icon-add"/></svg><span><b>Tethered</b> to the ${DIR_WORD[setAt(st.step).tether[s]]} add</span></div>`;
      document.getElementById('g2-debuffs').innerHTML = chips;
    }

    function render(){
      renderHud();
      ['g2-under', 'g2-over', 'g2-players', 'g2-hits'].forEach(layer);
      fb.hidden = true;

      if(st.step === 1){
        pill('Step 1 · Missing Link');
        drawParhelion();
        drawTentacles();
        drawAdd(document.getElementById('g2-over'), st.add);
        drawParty(stackPositions());
        instr(`One Darkness add is past the edge, Demi Parhelion has dropped nine circles and Geocentrism's tentacles are wrapping the floor. Missing Link has just chained every DPS to a support. Click where you run to before the add fires.<span class="hint"> The add's line cuts its own diagonal, so the other two corners are safe: <b>supports</b> take the north one, <b>DPS</b> the south one, each inside the narrow safe row or column.</span>`);
        spotHits(runSpots(), answerRun);
        return;
      }
      if(st.step === 2){
        pill('Step 2 · Divine Excoriation');
        drawParhelion();
        drawTentacles();
        drawAdd(document.getElementById('g2-over'), st.add);
        drawParty(cornerPositions());
        instr(`The chains are broken and everyone is marked for Divine Excoriation. The blasts and the add's line are about to go off. Click your spread spot.<span class="hint"> Spread along your lane from the corner inwards: <b>healers</b> and <b>ranged</b> nearest the corner, <b>tanks</b> and <b>melee</b> further in.</span>`);
        spotHits(spreadSpots(), answerSpread);
        return;
      }
      const set = setAt(st.step);
      pill(`Step ${st.step} · Ultima Blow ${st.step === 3 ? 'I' : 'II'}`);
      const roleWord = set.role === 'sup' ? 'supports' : 'DPS';
      if(tethered(set, st.me)){
        const pos = stackPositions();
        drawTethers(set, pos);
        drawParty(pos);
        instr(`${st.step === 3 ? 'Summon Darkness puts four adds past the edge and tethers' : 'After Ultima, four new adds tether'} all four ${roleWord}, you included. Click where you take your tether.<span class="hint"> Take it <b>straight across</b> to the wall opposite your add, so the four lines fan apart at the walls.</span>`);
        spotHits(tetherSpots(), answerTether);
      } else {
        const pos = stackPositions();
        Object.keys(set.tether).forEach(s => pos[s] = edgeSpot(OPP(set.tether[s]), WALL_R));
        drawTethers(set, pos);
        drawParty(pos);
        instr(`${st.step === 3 ? 'Summon Darkness puts four adds past the edge and tethers' : 'After Ultima, four new adds tether'} all four ${roleWord}, and they have taken their tethers out. Your partner <b>${PARTNER[st.me]}</b> is one of them. Click where you stand to share your partner's Ultima Blow.<span class="hint"> Stand on their line, <b>just in front of them</b> or out by their add, and away from the middle where all four lines cross.</span>`);
        spotHits(blockSpots(set), answerBlock);
      }
    }

    // both lanes' run spots in all four corners, so the tentacles, the add and your role all have to be read
    function runSpots(){
      const out = [];
      ['NW', 'NE', 'SE', 'SW'].forEach(c => ['rows', 'columns'].forEach(p =>
        out.push({ id:c + '-' + p, corner:c, pattern:p, at: laneSpot(p, c, RUN_AT), label:`${DIR_WORD[c]} corner, in the ${LANE[p]}` })));
      out.push({ id:'mid', at:[0, 0], label:'Stay in the middle' });
      return out;
    }
    function spreadSpots(){
      const out = [];
      ['NW', 'NE', 'SE', 'SW'].forEach(c => ALONG.forEach((a, i) =>
        out.push({ id:c + '-' + i, corner:c, index:i, at: laneSpot(st.pattern, c, a), label:`${DIR_WORD[c]} side of the ${LANE[st.pattern]}, spot ${i + 1} from the edge` })));
      return out;
    }
    function tetherSpots(){
      const out = DIRS.map(d => ({ id:d, at: edgeSpot(d, WALL_R), label:`Out to the ${DIR_WORD[d]} wall` }));
      out.push({ id:'mid', at:[0, 0], label:'Stay in the middle' });
      return out;
    }
    function blockSpots(set){
      const out = [];
      Object.keys(set.tether).sort((a, b) => DIRS.indexOf(set.tether[a]) - DIRS.indexOf(set.tether[b])).forEach(s => {
        const d = set.tether[s];
        out.push({ id:'front-' + s, slot:s, at: edgeSpot(OPP(d), BLOCK_R), label:`In front of the player at the ${DIR_WORD[OPP(d)]} wall` });
        out.push({ id:'deep-' + s, slot:s, at: edgeSpot(OPP(d), DEEP_R), label:`Near the middle, towards the ${DIR_WORD[OPP(d)]}` });
        out.push({ id:'add-' + s, slot:s, at: edgeSpot(d, ADD_SIDE_R), label:`Out by the ${DIR_WORD[d]} add` });
      });
      return out;
    }

    /* ---------- answers ---------- */
    function judge(ok, title, why, next){
      if(ok === 'warn') showFeedback(fb, 'warn', title, why, next.label, next.fn);
      else if(ok) showFeedback(fb, true, title, why, next.label, next.fn);
      else showFeedback(fb, false, title, why, 'New pull ↻', () => newRound());
    }
    function stepTo(n){
      if(n > 4) return { label:'New pull ↻', fn: () => newRound() };
      return { label:'Continue → Step ' + n, fn: () => { st.step = n; render(); } };
    }

    function answerRun(spot){
      lock();
      layer('g2-hits');
      const g = groupOf(st.me), mine = st.corner[g], theirs = st.corner[g === 'sup' ? 'dps' : 'sup'];
      const ok = spot.id === mine + '-' + st.pattern;
      drawGeocentrism();
      drawRay();
      const pos = cornerPositions();
      if(!ok) pos[st.me] = spot.at.slice();
      drawParty(pos);
      const lane = LANE[st.pattern];
      const rule = `The add is in the <b>${DIR_WORD[st.add]}</b>, so its line cuts that diagonal and leaves the ${DIR_WORD[st.corner.sup]} and ${DIR_WORD[st.corner.dps]} corners safe. The tentacles run <b>${PATTERN_WORD[st.pattern]}</b>, so the blasts spread in ${st.pattern} and only two narrow ${st.pattern} stay clear. Supports take the north safe corner, <b>${DIR_WORD[st.corner.sup]}</b>, and DPS the south one, <b>${DIR_WORD[st.corner.dps]}</b>, each inside its ${lane}.`;
      let why, title = 'Not there';
      if(ok){ title = 'Chain broken'; why = `${rule} Running to opposite corners breaks every chain at once.`; }
      else if(spot.id === 'mid') why = `Staying in the middle keeps your chain whole, and the add's line and a blast both go through there. ${rule}`;
      else if(spot.pattern !== st.pattern) why = `That spot is in the <b>${spot.pattern}</b>' lane, but this time the blasts spread in ${st.pattern}, so it is inside one. ${rule}`;
      else if(spot.corner !== mine && spot.corner !== theirs) why = `That corner is on the add's line, which fires across the whole diagonal. ${rule}`;
      else why = `Right lane, wrong corner: that is where the ${g === 'sup' ? 'DPS' : 'supports'} go, so you would run with your chain partner instead of away from them. ${rule}`;
      judge(ok, title, why, stepTo(2));
    }

    function answerSpread(spot){
      lock();
      layer('g2-hits');
      const g = groupOf(st.me);
      const pos = {};
      SLOTS.forEach(s => pos[s] = spreadSpot(s));
      // either spot of your job is your own; your job partner takes the other
      const jobMate = ORDER[g].find(s => s !== st.me && s[0] === st.me[0]);
      const usual = spot.corner === st.corner[g] && ORDER[g][spot.index][0] === st.me[0];
      if(usual && ORDER[g][spot.index] === jobMate) pos[jobMate] = spreadSpot(st.me);
      pos[st.me] = spot.at.slice();
      const q = spot.at;
      let res = { ok:true };
      if(inGeo(q)) res = { ok:false, why:'blast' };
      else if(lineDist(st.add, q) <= LINE_HALF + BODY) res = { ok:false, why:'ray' };
      else {
        const who = SLOTS.filter(s => s !== st.me).sort((a, b) => Math.hypot(q[0] - pos[a][0], q[1] - pos[a][1]) - Math.hypot(q[0] - pos[b][0], q[1] - pos[b][1]))[0];
        if(Math.hypot(q[0] - pos[who][0], q[1] - pos[who][1]) < EXCORIATION_R + BODY) res = { ok:false, why:'clip', who };
      }
      drawGeocentrism();
      drawRay();
      drawParty(pos, { aoe:true });
      const lane = LANE[st.pattern];
      const inner = g === 'sup' ? '<b>healers</b> nearest the corner and <b>tanks</b> further in' : '<b>ranged</b> nearest the corner and <b>melee</b> further in';
      const rule = `Your group spreads along the ${lane} from the <b>${DIR_WORD[st.corner[g]]}</b> corner: ${inner}. Either of your job's two spots is yours.`;
      let why, title, verdict;
      if(res.ok && usual){ verdict = true; title = 'Spread clean'; why = `${rule} Every Divine Excoriation lands clear of the others, and the add's line passes between the groups.`; }
      else if(res.ok){ verdict = 'warn'; title = 'Safe, but off your spot'; why = `You survive: nothing hits that spot and your Divine Excoriation reaches nobody. It is not where your group spreads, though, so the others cannot trust the line-up. ${rule}`; }
      else if(res.why === 'blast'){ verdict = false; title = 'Caught in the blast'; why = `That spot is inside the spreading blasts. ${rule}`; }
      else if(res.why === 'ray'){ verdict = false; title = "On the add's line"; why = `That part of the ${lane} is under the add's line across the ${DIR_WORD[st.add]} diagonal. ${rule}`; }
      else { verdict = false; title = 'Too close'; why = `<b>${res.who}</b> is standing right there, so your Divine Excoriation clips them. ${rule}`; }
      judge(verdict, title, why, stepTo(3));
    }

    // where everyone ends up when the tethers go to plan
    function planPositions(set){
      const pos = stackPositions();
      Object.keys(set.tether).forEach(s => {
        pos[s] = edgeSpot(OPP(set.tether[s]), WALL_R);
        pos[PARTNER[s]] = edgeSpot(OPP(set.tether[s]), BLOCK_R);
      });
      return pos;
    }
    function nextAfterBlow(){
      return st.step === 3 ? { label:'Continue → Step 4', fn: () => { st.step = 4; render(); } } : stepTo(5);
    }
    const afterWord = () => st.step === 3 ? ' Ultima follows, then the other role is tethered.' : ' Ultima follows, and then the enrage, Ignorabimus.';

    function answerTether(spot){
      lock();
      layer('g2-hits');
      const set = setAt(st.step);
      const d = set.tether[st.me], want = OPP(d);
      const ok = spot.id === want;
      const pos = planPositions(set);
      pos[st.me] = spot.at.slice();
      const lines = blows(set, pos);
      layer('g2-over');
      drawBlows(lines);
      drawTethers(set, pos);
      drawParty(pos);
      const p = PARTNER[st.me];
      const rule = `Your add is in the <b>${DIR_WORD[d]}</b>, so you take the tether straight across to the <b>${DIR_WORD[want]}</b> wall. With everyone doing that, the four lines all run through the middle and fan apart at the walls, so each blocker stands on one line only. <b>${p}</b> steps in front of you to share the hit.`;
      let why, title = 'Not there';
      if(ok){ title = 'Tether stretched'; why = rule + afterWord(); }
      else if(spot.id === 'mid') why = `In the middle every line runs through you and your blocker has nowhere to stand. Only a tank with an invulnerability can take all four there, when someone is dead. ${rule}`;
      else if(spot.id === d) why = `That is right under your own add, so there is no room between you for <b>${p}</b> to block, and your line then runs on through the whole party. ${rule}`;
      else why = `From there your line no longer runs through the middle: it misses <b>${p}</b>, who blocks on the straight line, and crosses the others. With Magic Vulnerability Up the unshared hit kills you. ${rule}`;
      judge(ok, title, why, nextAfterBlow());
    }

    function answerBlock(spot){
      lock();
      layer('g2-hits');
      const set = setAt(st.step);
      const p = PARTNER[st.me], d = set.tether[p];
      const pos = planPositions(set);
      pos[st.me] = spot.at.slice();
      const lines = blows(set, pos);
      const on = blowsOn(spot.at, lines);
      const ok = on.length === 1 && on[0] === p;
      layer('g2-over');
      drawBlows(lines);
      drawTethers(set, pos);
      drawParty(pos);
      const rule = `<b>${p}</b> is tethered to the <b>${DIR_WORD[d]}</b> add and has taken it to the <b>${DIR_WORD[OPP(d)]}</b> wall. Share their line by standing on it, just in front of them or out by their add, away from the middle where all four lines cross.`;
      let why, title;
      if(ok){
        title = 'Blow shared';
        why = (spot.id.indexOf('add-') === 0
          ? `Out by the add works just as well as in front of your partner: the line starts there, and the other lines are far away. `
          : `Just in front of your partner, where the other lines are well apart. `) + rule + afterWord();
      } else if(on.length > 1){
        title = 'Hit twice';
        why = `Near the middle the lines crowd together: you are standing in <b>${on.length}</b> of them, and the first leaves you with Magic Vulnerability Up for the next. ${rule}`;
      } else if(on.length === 1){
        title = 'Wrong line';
        why = `That line belongs to <b>${on[0]}</b>, whose own partner is blocking it already. <b>${p}</b> takes theirs alone and dies to Magic Vulnerability Up. ${rule}`;
      } else {
        title = 'Not on a line';
        why = `No line passes there, so <b>${p}</b> takes theirs alone. ${rule}`;
      }
      judge(ok, title, why, nextAfterBlow());
    }

    legend();
    const newRound = T.trackRounds('gaiaochos2', startRound);
    shared.roleListeners.push(newRound);
    newRound();
  }

  T.register({ id: 'gaiaochos2', label: 'Gaiaochos II', phase: 'Pallas Athena', players: 'slot', markup: MARKUP, styles: STYLES, init: initGaiaochos2 });
})(window.Twelfth);
