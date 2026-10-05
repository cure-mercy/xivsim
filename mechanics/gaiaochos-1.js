/* Gaiaochos I: break Missing Link down the safe line from Summon Darkness, then spread for Geocentrism. */
(function(T){

  const { shared, showFeedback } = T;

  const STYLES = /* css */ `
    .g1-slot{
      font-family: var(--font-mono); font-weight: 700; font-size: 1.3rem;
      width: 52px; height: 52px; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
      border-radius: 14px; border: 1px solid var(--line-strong); background: rgba(241,236,249,0.05);
    }
    .g1-debuffs{ display: flex; flex-wrap: wrap; gap: 8px 16px; margin-top: 12px; }
    .g1-debuff{ display: flex; align-items: center; gap: 8px; font-size: 0.88rem; color: var(--mist-dim); }
    .g1-debuff img{ width: 24px; height: 32px; border-radius: 4px; flex-shrink: 0; object-fit: contain; }
    .g1-debuff b{ color: var(--mist); font-weight: 600; }
  `;

  const MARKUP = /* html */ `
  <div class="layout" id="panel-gaiaochos1" role="tabpanel" aria-labelledby="tabBtn-gaiaochos1" hidden>

    <section class="arena-wrap">
      <div class="step-row">
        <span class="step-pill" id="g1-stepPill">Step 1 · Summon Darkness</span>
      </div>

      <svg class="arena-svg" id="g1-arena" viewBox="0 0 600 600" role="img" aria-label="Top-down view of the shrunken round arena during Gaiaochos">
        <defs>
          <clipPath id="g1-clip"><circle cx="300" cy="300" r="240"/></clipPath>
        </defs>
        <circle cx="300" cy="300" r="240" fill="url(#floor)" pointer-events="none"/>
        <circle cx="300" cy="300" r="240" fill="url(#weaveZoom)" pointer-events="none"/>
        <g id="g1-compass" font-family="Space Mono, monospace" font-size="12" font-weight="700" fill="var(--mist-faint)" text-anchor="middle" pointer-events="none">
          <text x="300" y="22">N</text><text x="300" y="590">S</text><text x="14" y="304">W</text><text x="586" y="304">E</text>
        </g>
        <g id="g1-under" clip-path="url(#g1-clip)" pointer-events="none"></g>
        <g id="g1-over" pointer-events="none"></g>
        <g id="g1-players" pointer-events="none"></g>
        <g id="g1-hits"></g>
        <circle cx="300" cy="300" r="240" fill="none" stroke="rgba(247,147,30,0.55)" stroke-width="2" filter="url(#glow)" pointer-events="none"/>
      </svg>

      <p class="arena-caption" id="g1-caption">North is up. Gaiaochos has shrunk the floor to this small circle, shown close up.</p>

      <div class="feedback" id="g1-feedback" hidden aria-live="polite"></div>
    </section>

    <aside class="hud">
      <div class="card">
        <h2>Your slot</h2>
        <div class="lc-row">
          <div class="g1-slot" id="g1-slot">H1</div>
          <p class="assign-text hint-only" id="g1-assignText"></p>
        </div>
        <div class="g1-debuffs" id="g1-debuffs"></div>
      </div>

      <div class="card">
        <h2>Objective</h2>
        <p class="instr-text" id="g1-instrText"></p>
      </div>

      <details class="card">
        <summary>How the call works</summary>
        <ol>
          <li><b>Gaiaochos</b> hits the raid, shrinks the floor to a small circle and gives everyone <b>Ascended</b>, which slows movement. Stack in the middle.</li>
          <li><b>Summon Darkness</b> puts three adds past the edge, each on a different line through the middle. They fire down those lines, so the <b>fourth line</b>, the one with no add at either end, is safe.</li>
          <li><b>Missing Link</b> chains every DPS to a support. Break it by running apart along the safe line: <b>supports</b> take the end between <b>west and north-east</b>, <b>DPS</b> the end between <b>east and south-west</b>. Then come back to the middle.</li>
          <li><b>Demi Parhelion</b> drops nine circles in a three by three grid, and <b>Geocentrism</b>'s tentacles show how the blasts spread: tentacles running <b>north to south</b> make columns, leaving two narrow columns safe; <b>east to west</b> makes rows, leaving two rows safe; <b>around the middle</b> makes a donut, leaving a ring safe.</li>
          <li>Everyone also gets <b>Divine Excoriation</b>, a small AoE, so spread in the safe ground by quadrant: <b>T1 and M1 north-west, T2 and M2 north-east, H1 and R1 south-west, H2 and R2 south-east</b>, supports on the inside and DPS on the outside.</li>
        </ol>
      </details>

      <div class="card">
        <h2>Legend</h2>
        <div class="legend-list" id="g1-legend"></div>
      </div>
    </aside>

  </div>
  `;

  function initGaiaochos1(){
    const SVGNS = 'http://www.w3.org/2000/svg';
    const C = 300, R = 240;
    // Positions are fractions of the arena's radius, read off Icy Veins' Geocentrism diagram.
    const P = (x, y) => [C + x * R, C + y * R];
    const DIRS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
    const DIR_WORD = { N:'north', NE:'north-east', E:'east', SE:'south-east', S:'south', SW:'south-west', W:'west', NW:'north-west' };
    const ANGLE = d => (DIRS.indexOf(d) * 45 - 90) * Math.PI / 180;
    const SUPPORT_ARC = ['W', 'NW', 'N', 'NE'];
    const LINE_HALF = 0.17, END_R = 0.8;

    const SLOTS = ['T1', 'T2', 'H1', 'H2', 'M1', 'M2', 'R1', 'R2'];
    const JOB = { T:'Tank', H:'Healer', M:'Melee DPS', R:'Ranged DPS' };
    const JOB_COLOR = { T:'var(--umbral-soft)', H:'var(--good)', M:'var(--astral-soft)', R:'var(--astral-soft)' };
    const isSupport = s => s[0] === 'T' || s[0] === 'H';
    const QUAD = { T1:'NW', M1:'NW', T2:'NE', M2:'NE', H1:'SW', R1:'SW', H2:'SE', R2:'SE' };

    // Where each slot spreads for each Geocentrism pattern.
    const SPREAD = {
      rows:    { M1:[-0.72,-0.36], T1:[-0.28,-0.36], T2:[0.28,-0.36], M2:[0.72,-0.36],
                 R1:[-0.72, 0.36], H1:[-0.28, 0.36], H2:[0.28, 0.36], R2:[0.72, 0.36] },
      columns: { M1:[-0.36,-0.7], R1:[-0.36, 0.7], M2:[ 0.36,-0.7], R2:[ 0.36, 0.7] },
      donut: {}
    };
    // the ring, clockwise from north: T2 M2 H2 R2 R1 H1 M1 T1
    ['T2', 'M2', 'H2', 'R2', 'R1', 'H1', 'M1', 'T1'].forEach((s, i) => {
      const a = (22.5 + i * 45 - 90) * Math.PI / 180;
      SPREAD.donut[s] = [Math.cos(a) * 0.42, Math.sin(a) * 0.42];
    });
    // The column supports stand where the ring's side spots are, so the two patterns share them.
    SPREAD.columns.T1 = SPREAD.donut.M1.slice(); SPREAD.columns.T2 = SPREAD.donut.M2.slice();
    SPREAD.columns.H1 = SPREAD.donut.H1.slice(); SPREAD.columns.H2 = SPREAD.donut.H2.slice();
    const PATTERN_WORD = { rows:'east to west', columns:'north to south', donut:'around the middle' };
    const BAND = 0.25, GRID = 0.72, RING_IN = 0.25, RING_OUT = 0.57;

    let st = {};
    const fb = document.getElementById('g1-feedback');
    const pick = arr => arr[Math.floor(Math.random() * arr.length)];

    function startRound(){
      st.me = shared.slot;
      // one line through the middle has no add on it
      const axes = [['N', 'S'], ['NE', 'SW'], ['E', 'W'], ['SE', 'NW']];
      st.safeAxis = pick(axes);
      st.adds = axes.filter(a => a !== st.safeAxis).map(a => pick(a));
      st.supportEnd = st.safeAxis.find(d => SUPPORT_ARC.indexOf(d) >= 0);
      st.dpsEnd = st.safeAxis.find(d => d !== st.supportEnd);
      st.pattern = pick(['rows', 'columns', 'donut']);
      st.step = 1;
      render();
    }

    /* ---------- geometry ---------- */
    function inGeo(pattern, xy){
      const [x, y] = xy;
      if(pattern === 'rows') return [-GRID, 0, GRID].some(c => Math.abs(y - c) <= BAND);
      if(pattern === 'columns') return [-GRID, 0, GRID].some(c => Math.abs(x - c) <= BAND);
      const r = Math.hypot(x, y);
      return r <= RING_IN || r >= RING_OUT;
    }
    function edgeSpot(d, r){ const a = ANGLE(d); return [Math.cos(a) * r, Math.sin(a) * r]; }
    // perpendicular distance from a point to the line through the middle towards d
    function lineDist(d, xy){ const a = ANGLE(d); return Math.abs(-Math.sin(a) * xy[0] + Math.cos(a) * xy[1]); }

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
      document.querySelectorAll('#panel-gaiaochos1 .hit').forEach(h => h.setAttribute('aria-disabled', 'true'));
    }

    function drawPlayer(host, slot, xy, o){
      { const layerHost = host; host = el('g', { class: 'player' + (slot === st.me ? ' me' : (QUAD[slot] === QUAD[st.me] ? ' related' : '')) }); layerHost.appendChild(host); }   // your quadrant partner stays in view
      o = o || {};
      const [cx, cy] = P(xy[0], xy[1]);
      const me = slot === st.me;
      if(o.aoe) host.appendChild(el('circle', { cx, cy, r:0.1 * R, fill:'rgba(226,82,63,0.18)', stroke:'var(--astral-soft)', 'stroke-width':1.2 }));
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
    // the party stacked in the middle, you on top
    function stackPositions(){
      const pos = {};
      SLOTS.forEach((s, i) => { const a = i * Math.PI / 4; pos[s] = [Math.cos(a) * 0.09, Math.sin(a) * 0.09]; });
      return pos;
    }
    function drawParty(pos, opts){
      const host = layer('g1-players');
      SLOTS.slice().sort((a, b) => (a === st.me) - (b === st.me)).forEach(s => drawPlayer(host, s, pos[s], opts));
    }

    function drawAdds(){
      const host = layer('g1-over');
      st.adds.forEach(d => {
        const [x, y] = P(...edgeSpot(d, 1.1));
        host.appendChild(el('circle', { cx:x, cy:y, r:15, fill:'rgba(10,9,22,0.9)', stroke:'var(--shape-purple)', 'stroke-width':2, filter:'url(#glow)' }));
        const u = el('use', { href:'#icon-add', x:x - 12, y:y - 12 });
        u.style.color = 'var(--shape-purple)';
        host.appendChild(u);
      });
    }
    function drawLines(){
      const host = document.getElementById('g1-under');
      st.adds.forEach(d => {
        const a = ANGLE(d);
        const ux = Math.cos(a), uy = Math.sin(a), px = -uy * LINE_HALF * R, py = ux * LINE_HALF * R;
        const e1 = P(ux * 1.2, uy * 1.2), e2 = P(-ux * 1.2, -uy * 1.2);
        host.appendChild(el('path', { d:`M${e1[0]+px} ${e1[1]+py} L${e2[0]+px} ${e2[1]+py} L${e2[0]-px} ${e2[1]-py} L${e1[0]-px} ${e1[1]-py} Z`,
          fill:'rgba(176,131,234,0.30)', stroke:'var(--shape-purple)', 'stroke-width':1.5 }));
      });
    }

    function drawParhelion(){
      const host = document.getElementById('g1-under');
      [-GRID, 0, GRID].forEach(x => [-GRID, 0, GRID].forEach(y => {
        const [cx, cy] = P(x, y);
        host.appendChild(el('circle', { cx, cy, r:BAND * R, fill:'rgba(242,165,60,0.22)', stroke:'var(--shape-orange)', 'stroke-width':1.5, 'stroke-dasharray':'6 5' }));
      }));
    }
    // Geocentrism's tentacles: they only show which way the blasts will spread.
    function drawTentacles(){
      const host = layer('g1-over');
      const style = { fill:'none', stroke:'rgba(106,196,168,0.85)', 'stroke-width':9, 'stroke-linecap':'round', opacity:0.8 };
      const wave = (pts) => 'M' + pts.map(p => P(p[0], p[1]).join(' ')).join(' L');
      if(st.pattern === 'donut'){
        const pts = [];
        for(let i = 0; i <= 64; i++){ const a = i / 64 * Math.PI * 2; const r = 0.93 + 0.03 * Math.sin(a * 10); pts.push([Math.cos(a) * r, Math.sin(a) * r]); }
        host.appendChild(el('path', Object.assign({ d: wave(pts) }, style)));
        return;
      }
      [-0.5, 0.5].forEach(off => {
        const pts = [];
        for(let i = 0; i <= 40; i++){
          const t = -1 + i / 20;
          const bulge = off * Math.sqrt(Math.max(0, 1 - t * t)) * 1.1 + 0.03 * Math.sin(t * 14);
          pts.push(st.pattern === 'columns' ? [bulge, t * 0.98] : [t * 0.98, bulge]);
        }
        host.appendChild(el('path', Object.assign({ d: wave(pts) }, style)));
      });
    }
    function drawGeocentrism(){
      const host = document.getElementById('g1-under');
      const fill = { fill:'rgba(242,165,60,0.38)', stroke:'var(--shape-orange)', 'stroke-width':1.5 };
      if(st.pattern === 'donut'){
        host.appendChild(el('circle', Object.assign({ cx:C, cy:C, r:RING_IN * R }, fill)));
        host.appendChild(el('path', Object.assign({ d:`M${C - 1.3*R} ${C} a${1.3*R} ${1.3*R} 0 1 0 ${2.6*R} 0 a${1.3*R} ${1.3*R} 0 1 0 ${-2.6*R} 0 Z M${C - RING_OUT*R} ${C} a${RING_OUT*R} ${RING_OUT*R} 0 1 1 ${2*RING_OUT*R} 0 a${RING_OUT*R} ${RING_OUT*R} 0 1 1 ${-2*RING_OUT*R} 0 Z`, 'fill-rule':'evenodd' }, fill)));
        return;
      }
      [-GRID, 0, GRID].forEach(c => {
        const a = P(st.pattern === 'columns' ? c - BAND : -1.2, st.pattern === 'columns' ? -1.2 : c - BAND);
        const w = st.pattern === 'columns' ? 2 * BAND * R : 2.4 * R, h = st.pattern === 'columns' ? 2.4 * R : 2 * BAND * R;
        host.appendChild(el('rect', Object.assign({ x:a[0], y:a[1], width:w, height:h }, fill)));
      });
    }

    function spotHits(spots, onPick){
      const host = layer('g1-hits');
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
      const host = document.getElementById('g1-legend');
      const row = (lead, html) => `<div class="legend-item">${lead}<span>${html}</span></div>`;
      host.innerHTML =
          row('<img src="assets/ascended.png" alt="">', '<b>Ascended</b> — shrunk and slowed on the small floor')
        + row('<img src="assets/missing-link.png" alt="">', '<b>Missing Link</b> — chains each DPS to a support; break it by distance')
        + row('<svg viewBox="0 0 24 24" fill="var(--shape-purple)"><use href="#icon-add"/></svg>', '<b>Darkness add</b> — fires down its line through the middle')
        + row('<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="rgba(242,165,60,0.25)" stroke="var(--shape-orange)" stroke-width="1.6" stroke-dasharray="3 2"/></svg>', '<b>Demi Parhelion</b> — nine circles the blasts spread from')
        + row('<svg viewBox="0 0 24 24"><path d="M5 20 Q12 2 19 20" fill="none" stroke="rgba(106,196,168,0.9)" stroke-width="3" stroke-linecap="round"/></svg>', '<b>Geocentrism tentacles</b> — which way the blasts spread');
    }

    /* ---------- render ---------- */
    function pill(t){ document.getElementById('g1-stepPill').textContent = t; }
    function instr(h){ document.getElementById('g1-instrText').innerHTML = h; }

    function renderHud(){
      const s = st.me;
      const slot = document.getElementById('g1-slot');
      slot.textContent = s;
      slot.style.color = JOB_COLOR[s[0]];
      document.getElementById('g1-assignText').innerHTML = `${JOB[s[0]]}, a ${isSupport(s) ? 'support' : 'DPS'}. Your spread quadrant is <b>${DIR_WORD[QUAD[s]]}</b>.`;
      document.getElementById('g1-debuffs').innerHTML =
          `<div class="g1-debuff"><img src="assets/ascended.png" alt=""><span><b>Ascended</b></span></div>`
        + (st.step === 1 ? `<div class="g1-debuff"><img src="assets/missing-link.png" alt=""><span><b>Missing Link</b></span></div>` : '');
    }

    function render(){
      renderHud();
      ['g1-under', 'g1-over', 'g1-players', 'g1-hits'].forEach(layer);
      fb.hidden = true;

      if(st.step === 1){
        pill('Step 1 · Summon Darkness');
        drawAdds();
        drawParty(stackPositions());
        instr(`Three Darkness adds are past the edge and Missing Link has chained every DPS to a support. Click where you run to before the adds fire.<span class="hint"> The adds fire down their own lines, so the <b>fourth line</b>, the one with no add at either end, is safe: <b>supports</b> take the end between west and north-east, <b>DPS</b> the other.</span>`);
        const spots = DIRS.map(d => ({ id:d, at: edgeSpot(d, END_R), label:`Out to the ${DIR_WORD[d]} edge` }));
        spots.push({ id:'mid', at:[0, 0], label:'Stay in the middle' });
        spotHits(spots, answerLink);
        return;
      }
      pill('Step 2 · Geocentrism');
      drawParhelion();
      drawTentacles();
      drawParty(stackPositions());
      instr(`Back in the middle. Demi Parhelion has dropped nine circles and Geocentrism's tentacles are wrapping the floor. Click your spread spot.<span class="hint"> The tentacles show how the blasts spread: north to south makes columns, east to west makes rows, around the middle makes a donut. Spread by quadrant — <b>T1 M1</b> north-west, <b>T2 M2</b> north-east, <b>H1 R1</b> south-west, <b>H2 R2</b> south-east — supports inside, DPS outside.</span>`);
      spotHits(geoSpots(), answerGeo);
    }

    // Every spread spot from all three patterns, the same set whatever the tentacles do, so they have
    // to be read rather than the layout.
    const ALL_SPOTS = (function(){
      const out = [];
      ['rows', 'columns', 'donut'].forEach(p => SLOTS.forEach(s => {
        const at = SPREAD[p][s];
        let spot = out.find(o => Math.hypot(o.at[0] - at[0], o.at[1] - at[1]) < 0.01);
        if(!spot){ spot = { at, owners:[] }; out.push(spot); }
        spot.owners.push({ pattern:p, slot:s });
      }));
      return out.sort((a, b) => Math.atan2(a.at[1], a.at[0]) - Math.atan2(b.at[1], b.at[0]) || Math.hypot(...a.at) - Math.hypot(...b.at));
    })();
    function geoSpots(){
      return ALL_SPOTS.map((sp, i) => {
        const here = sp.owners.find(o => o.pattern === st.pattern);
        const id = here ? 'own-' + here.slot : (inGeo(st.pattern, sp.at) ? 'decoy' : 'other');
        const o = here || sp.owners[0];
        return { id, slot:o.slot, pattern:o.pattern, at:sp.at, label:'Spread spot ' + (i + 1) };
      });
    }

    /* ---------- answers ---------- */
    function judge(ok, title, why, next){
      if(ok === 'warn') showFeedback(fb, 'warn', title, why, next.label, next.fn);
      else if(ok) showFeedback(fb, true, title, why, next.label, next.fn);
      else showFeedback(fb, false, title, why, 'New pull ↻', () => newRound());
    }
    function stepTo(n){
      if(n > 2) return { label:'New pull ↻', fn: () => newRound() };
      return { label:'Continue → Step ' + n, fn: () => { st.step = n; render(); } };
    }

    function answerLink(spot){
      lock();
      layer('g1-hits');
      const mine = isSupport(st.me) ? st.supportEnd : st.dpsEnd;
      const ok = spot.id === mine;
      drawLines();
      const pos = {};
      const sups = SLOTS.filter(isSupport), dps = SLOTS.filter(s => !isSupport(s));
      [[sups, st.supportEnd], [dps, st.dpsEnd]].forEach(([group, end]) => group.forEach((s, i) => {
        const base = edgeSpot(end, END_R + 0.02), a = ANGLE(end) + Math.PI / 2, off = (i - 1.5) * 0.075;
        pos[s] = [base[0] + Math.cos(a) * off, base[1] + Math.sin(a) * off];
      }));
      if(!ok) pos[st.me] = spot.at.slice();
      drawParty(pos);
      const lineWord = `${DIR_WORD[st.safeAxis[0]]} to ${DIR_WORD[st.safeAxis[1]]}`;
      const rule = `The adds sit on the other three lines, so the <b>${lineWord}</b> line is safe. Supports take the end between west and north-east, which is <b>${DIR_WORD[st.supportEnd]}</b>; DPS take the other, <b>${DIR_WORD[st.dpsEnd]}</b>. Running to opposite ends breaks every chain at once.`;
      let why;
      if(ok) why = rule + ' Once the lines fire, head back to the middle.';
      else if(spot.id === 'mid') why = `Staying in the middle leaves your chain intact and puts you where all three lines cross. ${rule}`;
      else if(spot.id === (isSupport(st.me) ? st.dpsEnd : st.supportEnd)) why = `Right line, wrong end: that is where the ${isSupport(st.me) ? 'DPS' : 'supports'} go, so you would run with your chain partner instead of away from them. ${rule}`;
      else why = `That end of the floor is on a Darkness add's line${st.adds.indexOf(spot.id) >= 0 ? ', right under the add' : ''}. ${rule}`;
      judge(ok, ok ? 'Chain broken' : 'Not there', why, stepTo(2));
    }

    // A spot is fine if the blasts miss it and your Divine Excoriation touches nobody, whoever's spot it is.
    const EXCORIATION_R = 0.1, BODY = 0.04;
    function geoCheck(q){
      if(inGeo(st.pattern, q)) return { ok:false, why:'blast' };
      const others = SLOTS.filter(o => o !== st.me);
      const who = others.sort((a, b) => Math.hypot(q[0] - SPREAD[st.pattern][a][0], q[1] - SPREAD[st.pattern][a][1])
                                     - Math.hypot(q[0] - SPREAD[st.pattern][b][0], q[1] - SPREAD[st.pattern][b][1]))[0];
      const d = Math.hypot(q[0] - SPREAD[st.pattern][who][0], q[1] - SPREAD[st.pattern][who][1]);
      if(d < EXCORIATION_R + BODY) return { ok:false, why:'clip', who };
      return { ok:true };
    }

    function answerGeo(spot){
      lock();
      layer('g1-hits');
      const res = geoCheck(spot.at);
      const usual = spot.id === 'own-' + st.me;
      drawGeocentrism();
      const pos = {};
      SLOTS.forEach(s => pos[s] = SPREAD[st.pattern][s].slice());
      pos[st.me] = spot.at.slice();
      drawParty(pos, { aoe:true });
      const shape = { rows:'rows, leaving two narrow rows safe', columns:'columns, leaving two narrow columns safe', donut:'a donut, leaving a ring safe around the middle circle' }[st.pattern];
      const place = st.pattern === 'donut'
        ? `On the ring the order clockwise from north is T2, M2, H2, R2, R1, H1, M1, T1.`
        : `In each quadrant the support takes the inside and the DPS the outside.`;
      const rule = `The tentacles run <b>${PATTERN_WORD[st.pattern]}</b>, so the blasts spread in ${shape}. The usual spot is by quadrant: yours is <b>${DIR_WORD[QUAD[st.me]]}</b>. ${place}`;
      let why, title;
      if(res.ok && usual){
        title = 'Spread clean';
        why = `${rule} Everyone's Divine Excoriation lands clear of the others. Ultima then restores the floor.`;
      } else if(res.ok){
        title = 'Safe, but off your spot';
        why = `You survive: the blasts miss that spot and your Divine Excoriation reaches nobody. It is not your spot, though, so the others have to read where you went instead of trusting the spread. ${rule}`;
      } else if(res.why === 'blast'){
        title = 'Caught in the blast';
        why = `That spot is inside the spreading blasts. ${rule}`;
      } else {
        title = 'Too close';
        why = `The blasts miss that spot, but <b>${res.who}</b> is standing right next to it, so your Divine Excoriation clips them. ${rule}`;
      }
      judge(res.ok ? (usual ? true : 'warn') : false, title, why, stepTo(3));
    }

    legend();
    const newRound = T.trackRounds('gaiaochos1', startRound);
    shared.roleListeners.push(newRound);
    newRound();
  }

  T.register({ id: 'gaiaochos1', label: 'Gaiaochos I', phase: 'Pallas Athena', players: 'slot', markup: MARKUP, styles: STYLES, init: initGaiaochos1 });
})(window.Twelfth);
