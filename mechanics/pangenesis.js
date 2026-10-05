/* Pangenesis: sort out of the conga line, then soak three sets of Pantheos towers while mixing Unstable Factor away. */
(function(T){

  const { shared, showFeedback } = T;

  const STYLES = /* css */ `
    .pg-slot{
      font-family: var(--font-mono);
      font-weight: 700;
      font-size: 1.3rem;
      width: 52px; height: 52px; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
      border-radius: 14px;
      border: 1px solid var(--line-strong);
      background: rgba(241,236,249,0.05);
    }
    .pg-debuffs{ display: flex; flex-wrap: wrap; gap: 8px 16px; margin-top: 12px; }
    .pg-debuff{ display: flex; align-items: center; gap: 8px; font-size: 0.88rem; color: var(--mist-dim); }
    .pg-debuff img{ width: 24px; height: 32px; border-radius: 4px; flex-shrink: 0; object-fit: contain; }
    .pg-debuff b{ color: var(--mist); font-weight: 600; }
    .pg-line{ display: flex; gap: 4px; margin-top: 12px; flex-wrap: wrap; }
    .pg-line span{
      font-family: var(--font-mono); font-size: 0.74rem; font-weight: 700;
      padding: 3px 6px; border-radius: 6px; border: 1px solid var(--line); color: var(--mist-dim);
    }
    .pg-line span.me{ color: var(--mist); border-color: var(--mist); }
  `;

  const MARKUP = /* html */ `
  <div class="layout" data-dim="off" id="panel-pangenesis" role="tabpanel" aria-labelledby="tabBtn-pangenesis" hidden>

    <section class="arena-wrap">
      <div class="step-row">
        <span class="step-pill" id="pg-stepPill">Step 1 · Leave the line</span>
      </div>

      <svg class="arena-svg" id="pg-arena" viewBox="-14 -14 628 478" role="img" aria-label="Top-down view of Pallas Athena's arena during Pangenesis">
        <rect x="0" y="0" width="600" height="450" rx="6" fill="url(#floor)" pointer-events="none"/>
        <image href="assets/arena-phase2.svg" x="0" y="0" width="600" height="450" preserveAspectRatio="none" pointer-events="none"/>
        <g stroke="var(--line)" stroke-width="1.5" pointer-events="none">
          <line x1="300" y1="0" x2="300" y2="450"/>
          <line x1="0" y1="150" x2="600" y2="150"/>
          <line x1="0" y1="300" x2="600" y2="300"/>
        </g>
        <g id="pg-marks" pointer-events="none"></g>
        <g id="pg-under" pointer-events="none"></g>
        <g id="pg-players" pointer-events="none"></g>
        <g id="pg-hits"></g>
        <rect x="0" y="0" width="600" height="450" rx="6" fill="none" stroke="rgba(247,147,30,0.55)" stroke-width="2" filter="url(#glow)" pointer-events="none"/>
      </svg>

      <p class="arena-caption">North is up. Purple numbers are Unstable Factor stacks; Tilt cards show 16 or 20 seconds.</p>

      <div class="feedback" id="pg-feedback" hidden aria-live="polite"></div>
    </section>

    <aside class="hud">
      <div class="card">
        <h2>Your slot</h2>
        <div class="lc-row">
          <div class="pg-slot" id="pg-slot">H1</div>
          <p class="assign-text" id="pg-assignText"></p>
        </div>
        <div class="pg-line" id="pg-line"></div>
        <div class="pg-debuffs" id="pg-debuffs"></div>
      </div>

      <div class="card">
        <h2>Objective</h2>
        <p class="instr-text" id="pg-instrText"></p>
      </div>

      <details class="card">
        <summary>How the call works</summary>
        <ol>
          <li>The party stands in a pre-assigned <b>conga line</b> west to east, main tank on the far east end. Two players get <b>no stacks</b>, two get <b>1 Unstable Factor</b>, and four get <b>2 stacks plus a Tilt</b>: Astral and Umbral, each once with <b>16 s</b> and once with <b>20 s</b>.</li>
          <li>Two players stacked together <b>mix</b>: their stacks add up, halve and round down. A player with no stacks can never gain one. Every stack has to be gone by the end, or that player explodes.</li>
          <li><b>No-stack</b> players step forward, <b>1-stack</b> players step back; in each pair the westmost goes <b>west</b> and the eastmost <b>east</b>. No-stack players take the <b>first tower</b> on their side, 1-stack players wait <b>outside</b>, near where the second south tower spawns.</li>
          <li>Towers take two: one player whose Tilt fits and one with no Tilt. <b>Astral Tilt soaks light towers, Umbral Tilt soaks dark towers.</b> A light tower then hands Umbral Tilt to one of the two at random, a dark tower Astral.</li>
          <li>When the first towers appear, one light and one dark, each 2-stack player goes to the side whose tower their Tilt soaks. The <b>16 s</b> Tilt soaks it with the no-stack player; the <b>20 s</b> Tilt waits outside and mixes with the 1-stack player.</li>
          <li>Second towers: whoever soaked the first tower takes the <b>north</b> tower on their side; whoever waited outside takes the <b>south</b> one.</li>
          <li>Third towers: if the second tower gave <b>you</b> a Tilt, <b>swap rows</b>; if not, <b>stay in your row</b>. Stack tightly every time so you mix.</li>
          <li>Afterwards the no-stack players drag the slime tethers away, west to the north-west corner and east to the north just east of the middle. The main tank takes Palladian Grasp on the east half; everyone else waits south of the middle on the west half.</li>
        </ol>
      </details>

      <div class="card">
        <h2>Legend</h2>
        <div class="legend-list" id="pg-legend"></div>
      </div>
    </aside>

  </div>
  `;

  function initPangenesis(){
    const SVGNS = 'http://www.w3.org/2000/svg';
    const U = 15;
    const X = x => x * U, Y = y => y * U;

    // Floor is 40 by 30 yalms. Tower spots are read off Icy Veins' diagrams, mirrored west to east.
    const LINE = ['T2', 'H1', 'M1', 'R1', 'R2', 'M2', 'H2', 'T1'];
    const LINE_Y = 19;
    const lineX = i => 6 + i * 4;
    const LINE_STEP = 2.2;   // how far no-stack players step forward (north) and 1-stack players step back
    const TOWER_R = 2.3;
    const FIRST = { W:[3.3, 10], E:[36.7, 10] };
    const OUTSIDE = { W:[7.6, 14.2], E:[32.4, 14.2] };
    const SECOND = { W:{ N:[8.7, 6.3], S:[8.7, 12.8] }, E:{ N:[31.3, 6.3], S:[31.3, 12.8] } };
    const THIRD  = { W:{ N:[15.2, 6.3], S:[15.2, 12.8] }, E:{ N:[24.8, 6.3], S:[24.8, 12.8] } };
    const FINAL = { NW:[1.6, 1.6], NC:[23.5, 1.6], NE:[38.4, 1.6], SW:[15.5, 22.5], SE:[24.5, 22.5] };
    const FACTOR_IN_R = 17;

    const JOB = { T:'Tank', H:'Healer', M:'Melee DPS', R:'Ranged DPS' };
    const JOB_COLOR = { T:'var(--umbral-soft)', H:'var(--good)', M:'var(--astral-soft)', R:'var(--astral-soft)' };
    const TILT = {
      astral: { name:'Astral Tilt', icon:'assets/astral-tilt.png', soaks:'light' },
      umbral: { name:'Umbral Tilt', icon:'assets/umbral-tilt.png', soaks:'dark' }
    };
    const GRANTS = { light:'umbral', dark:'astral' };
    const OPP = { light:'dark', dark:'light' };
    const SIDE_WORD = { W:'west', E:'east' };
    const ROW_WORD = { N:'north', S:'south' };

    const WAYMARK = {
      A:{ at:[20, 9], color:'#e2523f', shape:'circle' }, B:{ at:[24.4, 13], color:'#e8c14b', shape:'circle' },
      C:{ at:[20, 17], color:'#4a8fe0', shape:'circle' }, D:{ at:[15.6, 13], color:'#b083ea', shape:'circle' },
      '1':{ at:[7.3, 13], color:'#e2523f', shape:'square' }, '2':{ at:[32.7, 13], color:'#e8c14b', shape:'square' }
    };

    let st = {};
    const fb = document.getElementById('pg-feedback');
    const pick = arr => arr[Math.floor(Math.random() * arr.length)];

    /* ---------- the mechanic ---------- */
    function mix(a, b){
      const sa = st.stacks[a], sb = st.stacks[b];
      if(sa === 0 || sb === 0){
        if(sa > 0) st.stacks[a] = Math.floor(sa / 2);
        if(sb > 0) st.stacks[b] = Math.floor(sb / 2);
      } else {
        st.stacks[a] = st.stacks[b] = Math.floor((sa + sb) / 2);
      }
    }
    // Soak a tower: the Tilt that fitted is used up, then one of the two gets the tower's own Tilt.
    function soak(pair, colour){
      pair.forEach(p => { st.tilt[p] = null; });
      const lucky = pick(pair);
      st.tilt[lucky] = GRANTS[colour];
      mix(pair[0], pair[1]);
      return lucky;
    }

    function startRound(){
      st.me = shared.slot;

      // debuffs, shuffled over the line
      const roles = ['zero', 'zero', 'one', 'one', 'shortA', 'shortU', 'longA', 'longU'].sort(() => Math.random() - 0.5);
      st.kind = {}; st.stacks = {}; st.tilt = {}; st.timer = {};
      LINE.forEach((s, i) => {
        const r = roles[i];
        st.kind[s] = r === 'zero' ? 'zero' : r === 'one' ? 'one' : r.startsWith('short') ? 'short' : 'long';
        st.stacks[s] = r === 'zero' ? 0 : r === 'one' ? 1 : 2;
        st.tilt[s] = r.endsWith('A') ? 'astral' : r.endsWith('U') ? 'umbral' : null;
        st.timer[s] = r.startsWith('short') ? 16 : r.startsWith('long') ? 20 : null;
      });
      st.start = { stacks: Object.assign({}, st.stacks), tilt: Object.assign({}, st.tilt) };

      // sides: westmost of each pair goes west
      st.side = {};
      ['zero', 'one'].forEach(k => {
        const two = LINE.filter(s => st.kind[s] === k);
        st.side[two[0]] = 'W'; st.side[two[1]] = 'E';
      });
      st.colour1 = { W: Math.random() < 0.5 ? 'light' : 'dark' };
      st.colour1.E = OPP[st.colour1.W];
      LINE.forEach(s => {
        if(st.tilt[s]) st.side[s] = st.colour1.W === TILT[st.tilt[s]].soaks ? 'W' : 'E';
      });

      // set 1: tower = no-stack + 16 s, outside = 1-stack + 20 s
      st.snap = [snapshot()];
      st.pairs1 = {};
      st.got1 = {};
      ['W', 'E'].forEach(sd => {
        const inSide = LINE.filter(s => st.side[s] === sd);
        const tower = inSide.filter(s => st.kind[s] === 'zero' || st.kind[s] === 'short');
        const out = inSide.filter(s => st.kind[s] === 'one' || st.kind[s] === 'long');
        st.pairs1[sd] = { tower, out };
        st.got1[sd] = soak(tower, st.colour1[sd]);
        mix(out[0], out[1]);
      });
      st.snap.push(snapshot());

      // set 2: tower pair north (opposite colour), outside pair south (same colour)
      st.row2 = {}; st.got2 = {};
      ['W', 'E'].forEach(sd => {
        st.pairs1[sd].tower.forEach(s => st.row2[s] = 'N');
        st.pairs1[sd].out.forEach(s => st.row2[s] = 'S');
        st.got2[sd] = {
          N: soak(st.pairs1[sd].tower, OPP[st.colour1[sd]]),
          S: soak(st.pairs1[sd].out, st.colour1[sd])
        };
      });
      st.snap.push(snapshot());

      // set 3: whoever the second tower gave a Tilt swaps rows
      st.row3 = {};
      LINE.forEach(s => {
        const got = st.got2[st.side[s]][st.row2[s]] === s;
        st.row3[s] = got ? (st.row2[s] === 'N' ? 'S' : 'N') : st.row2[s];
      });
      ['W', 'E'].forEach(sd => {
        ['N', 'S'].forEach(row => {
          const pair = LINE.filter(s => st.side[s] === sd && st.row3[s] === row);
          soak(pair, row === 'N' ? OPP[st.colour1[sd]] : st.colour1[sd]);
        });
      });
      st.snap.push(snapshot());

      st.step = 1;
      render();
    }

    function snapshot(){ return { stacks: Object.assign({}, st.stacks), tilt: Object.assign({}, st.tilt) }; }

    // Debuff state as players see it at the start of each step.
    function stateAt(step){
      return st.snap[Math.max(0, Math.min(step - 2, 3))];
    }
    function colourAt(sd, row, set){
      if(set === 1) return st.colour1[sd];
      return row === 'N' ? OPP[st.colour1[sd]] : st.colour1[sd];
    }

    // Everyone's position for each beat.
    function positions(stage){
      const out = {};
      const inPair = (spot, s, others) => {
        const idx = others.indexOf(s);
        return [spot[0] + (idx === 0 ? -1 : 1), spot[1]];
      };
      LINE.forEach((s, i) => {
        const sd = st.side[s];
        if(stage === 'line'){ out[s] = [lineX(i), LINE_Y]; return; }
        // a beat after the debuffs: everyone else has stepped out of the line, you have not yet
        if(stage === 'stepped'){
          const dy = s === st.me ? 0 : st.kind[s] === 'zero' ? -LINE_STEP : st.kind[s] === 'one' ? LINE_STEP : 0;
          out[s] = [lineX(i), LINE_Y + dy];
          return;
        }
        if(stage === 'sorted'){
          if(st.kind[s] === 'zero') out[s] = FIRST[sd].slice();
          else if(st.kind[s] === 'one') out[s] = OUTSIDE[sd].slice();
          else out[s] = [lineX(i), LINE_Y];
          return;
        }
        if(stage === 'set1'){
          const p = st.pairs1[sd];
          out[s] = p.tower.indexOf(s) >= 0 ? inPair(FIRST[sd], s, p.tower) : inPair(OUTSIDE[sd], s, p.out);
          return;
        }
        if(stage === 'set2'){
          const pair = LINE.filter(q => st.side[q] === sd && st.row2[q] === st.row2[s]);
          out[s] = inPair(SECOND[sd][st.row2[s]], s, pair);
          return;
        }
        if(stage === 'set3'){
          const pair = LINE.filter(q => st.side[q] === sd && st.row3[q] === st.row3[s]);
          out[s] = inPair(THIRD[sd][st.row3[s]], s, pair);
          return;
        }
        // final
        const fk = finalKey(s);
        const same = LINE.filter(q => finalKey(q) === fk);
        const idx = same.indexOf(s);
        out[s] = [FINAL[fk][0] + (fk === 'SW' ? (idx % 3 - 1) * 1.8 : 0), FINAL[fk][1] + (fk === 'SW' ? Math.floor(idx / 3) * 1.8 : 0)];
      });
      return out;
    }
    function finalKey(s){
      if(st.kind[s] === 'zero') return st.side[s] === 'W' ? 'NW' : 'NC';
      if(s === 'T1') return 'SE';
      return 'SW';
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
      document.querySelectorAll('#panel-pangenesis .hit').forEach(h => h.setAttribute('aria-disabled', 'true'));
    }

    function drawWaymarks(){
      const host = layer('pg-marks');
      Object.keys(WAYMARK).forEach(id => {
        const w = WAYMARK[id], cx = X(w.at[0]), cy = Y(w.at[1]);
        const style = { fill:w.color, 'fill-opacity':0.14, stroke:w.color, 'stroke-width':1.2, 'stroke-opacity':0.55 };
        host.appendChild(w.shape === 'circle' ? el('circle', Object.assign({ cx, cy, r:13 }, style))
          : el('rect', Object.assign({ x:cx - 12, y:cy - 12, width:24, height:24, rx:3 }, style)));
        const t = el('text', { x:cx, y:cy + 4.5, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':12, 'font-weight':700, fill:w.color, opacity:0.7 });
        t.textContent = id;
        host.appendChild(t);
      });
    }

    function drawTower(host, at, colour, ghost){
      const cx = X(at[0]), cy = Y(at[1]), r = TOWER_R * U;
      if(ghost){
        host.appendChild(el('circle', { cx, cy, r, fill:'none', stroke:'var(--line-strong)', 'stroke-width':1.5, 'stroke-dasharray':'4 4' }));
        return;
      }
      const light = colour === 'light';
      host.appendChild(el('circle', { cx, cy, r, fill: light ? 'rgba(241,236,249,0.55)' : 'rgba(6,5,14,0.85)',
        stroke: light ? '#ffffff' : '#6d6590', 'stroke-width':2 }));
      host.appendChild(el('circle', { cx, cy, r:r - 6, fill:'none', stroke: light ? 'rgba(10,9,22,0.25)' : 'rgba(241,236,249,0.25)', 'stroke-width':1.2 }));
    }

    function drawPlayer(host, slot, at, state, opts){
      { const layerHost = host; host = el('g', { class: 'player' + (slot === st.me ? ' me' : '') }); layerHost.appendChild(host); }
      const o = opts || {};
      const cx = X(at[0]), cy = Y(at[1]);
      const me = slot === st.me;
      if(me) host.appendChild(el('circle', { cx, cy, r:17, fill:'none', stroke:'var(--mist)', 'stroke-width':2.5, class:'pulse' }));
      host.appendChild(el('circle', { cx, cy, r:12, fill:'rgba(10,9,22,0.94)', stroke: me ? 'var(--mist)' : JOB_COLOR[slot[0]], 'stroke-width': me ? 2 : 1.6 }));
      const t = el('text', { x:cx, y:cy + 3.6, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':10, 'font-weight':700, fill:JOB_COLOR[slot[0]] });
      t.textContent = slot;
      host.appendChild(t);
      if(state){
        const n = state.stacks[slot];
        if(n > 0){
          host.appendChild(el('circle', { cx:cx - 11, cy:cy + 11, r:7, fill:'#6a3fb0', stroke:'#c9a8ff', 'stroke-width':1.2 }));
          const d = el('text', { x:cx - 11, y:cy + 14.5, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':10, 'font-weight':700, fill:'#fff' });
          d.textContent = String(n);
          host.appendChild(d);
        }
        const tl = state.tilt[slot];
        if(tl){
          const bx = cx - 12 + (o.cardShift || 0), by = cy - 50;
          host.appendChild(el('rect', { x:bx - 1.5, y:by - 1.5, width:27, height:35, rx:4, fill:'var(--nebula-2)', stroke:'var(--line-strong)', 'stroke-width':1 }));
          host.appendChild(el('image', { href:TILT[tl].icon, x:bx, y:by, width:24, height:32, preserveAspectRatio:'xMidYMid meet' }));
          if(o.timer && st.timer[slot]){
            host.appendChild(el('rect', { x:bx + 11, y:by + 21, width:15, height:12, rx:3, fill:'rgba(10,9,22,0.9)' }));
            const tt = el('text', { x:bx + 18.5, y:by + 30.5, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':9, 'font-weight':700, fill:'#fff' });
            tt.textContent = String(st.timer[slot]);
            host.appendChild(tt);
          }
        }
      }
      if(me){
        const you = el('text', { x:cx, y:cy + 28, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':9, 'font-weight':700, fill:'var(--mist)' });
        you.textContent = 'YOU';
        host.appendChild(you);
      }
    }

    function drawParty(stage, state, mine, opts){
      const host = layer('pg-players');
      const pos = positions(stage);
      if(mine) pos[st.me] = mine;
      // pairs push their cards apart so both stay readable
      const shift = {};
      LINE.forEach(a => LINE.forEach(b => {
        if(a < b && Math.abs(pos[a][0] - pos[b][0]) < 2.2 && Math.abs(pos[a][1] - pos[b][1]) < 1){
          const left = pos[a][0] <= pos[b][0] ? a : b, right = left === a ? b : a;
          shift[left] = -8; shift[right] = 8;
        }
      }));
      LINE.slice().sort((a, b) => (a === st.me) - (b === st.me)).forEach(s =>
        drawPlayer(host, s, pos[s], state, Object.assign({ cardShift: shift[s] || 0 }, opts || {})));
      return pos;
    }

    function spotHits(spots, onPick){
      const host = layer('pg-hits');
      spots.forEach(s => {
        const cx = X(s.at[0]), cy = Y(s.at[1]);
        const g = el('g', {});
        g.appendChild(el('circle', { cx, cy, r:19, class:'focus-ring', fill:'none', stroke:'var(--mist)', 'stroke-width':2.5, opacity:0 }));
        g.appendChild(el('circle', { cx, cy, r:14, fill:'rgba(241,236,249,0.16)', stroke:'var(--mist)', 'stroke-width':2 }));
        hitable(g, onPick, s, s.label);
        host.appendChild(g);
      });
    }

    function legend(){
      const host = document.getElementById('pg-legend');
      const row = (lead, html) => `<div class="legend-item">${lead}<span>${html}</span></div>`;
      host.innerHTML =
          row('<img src="assets/unstable-factor.png" alt="">', '<b>Unstable Factor</b> — stacks that mix when players stand together<span class="hint">; mix it away before it runs out</span>')
        + row('<img src="assets/critical-factor.png" alt="">', '<b>Critical Factor</b> — after clearing your stacks; the slimes kill you')
        + row(`<img src="${TILT.astral.icon}" alt="">`, '<b>Astral Tilt</b> — soaks one colour of tower<span class="hint">: light</span>')
        + row(`<img src="${TILT.umbral.icon}" alt="">`, '<b>Umbral Tilt</b> — soaks the other colour<span class="hint">: dark</span>')
        + row('<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="rgba(241,236,249,0.6)" stroke="#fff" stroke-width="1.5"/></svg>', '<b>Light tower</b> — hands out Umbral Tilt')
        + row('<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="rgba(6,5,14,0.9)" stroke="#6d6590" stroke-width="1.5"/></svg>', '<b>Dark tower</b> — hands out Astral Tilt');
    }

    /* ---------- render ---------- */
    function pill(t){ document.getElementById('pg-stepPill').textContent = t; }
    function instr(h){ document.getElementById('pg-instrText').innerHTML = h; }
    const kindWord = s => ({ zero:'no stacks', one:'1 stack', short:'2 stacks and a 16 s Tilt', long:'2 stacks and a 20 s Tilt' })[st.kind[s]];

    function renderHud(){
      const s = st.me;
      const slot = document.getElementById('pg-slot');
      slot.textContent = s;
      slot.style.color = JOB_COLOR[s[0]];
      document.getElementById('pg-assignText').innerHTML = `${JOB[s[0]]}. Your place in the conga line, west to east:`;
      document.getElementById('pg-line').innerHTML = LINE.map(q => `<span class="${q === s ? 'me' : ''}">${q}</span>`).join('');
      const state = st.step >= 6 ? st.snap[3] : stateAt(st.step);
      const bits = [];
      const n = state.stacks[s];
      bits.push(n > 0
        ? `<div class="pg-debuff"><img src="assets/unstable-factor.png" alt=""><span><b>Unstable Factor ×${n}</b></span></div>`
        : (st.start.stacks[s] > 0
          ? `<div class="pg-debuff"><img src="assets/critical-factor.png" alt=""><span><b>Critical Factor</b></span></div>`
          : `<div class="pg-debuff"><span>No Unstable Factor.</span></div>`));
      const tl = state.tilt[s];
      if(tl) bits.push(`<div class="pg-debuff"><img src="${TILT[tl].icon}" alt=""><span><b>${TILT[tl].name}</b>${st.step <= 2 && st.timer[s] ? ` · ${st.timer[s]} s` : ''}</span></div>`);
      document.getElementById('pg-debuffs').innerHTML = bits.join('');
    }

    function drawTowers(set, ghostNext){
      const host = layer('pg-under');
      ['W', 'E'].forEach(sd => {
        if(set === 1) drawTower(host, FIRST[sd], st.colour1[sd]);
        if(set === 2) ['N', 'S'].forEach(r => drawTower(host, SECOND[sd][r], colourAt(sd, r, 2)));
        if(set === 3) ['N', 'S'].forEach(r => drawTower(host, THIRD[sd][r], colourAt(sd, r, 3)));
        if(ghostNext === 1) drawTower(host, FIRST[sd], null, true);
      });
      return host;
    }

    function render(){
      renderHud();
      ['pg-under', 'pg-players', 'pg-hits'].forEach(layer);
      fb.hidden = true;
      drawWaymarks();
      const state = stateAt(st.step);

      if(st.step === 1){
        pill('Step 1 · Leave the line');
        drawParty('stepped', state, null, { timer:true });
        instr(`Pangenesis has landed and you have <span class="hl">${kindWord(st.me)}</span>. The rest of the party has already stepped out of the line, and towers are coming. Click where you go, or your own spot to stay.<span class="hint"> <b>No-stack</b> players step forward and <b>1-stack</b> players step back, so each pair ends up in a row of its own; in each pair the westmost goes west and the eastmost east. The four with a Tilt hold the line.</span>`);
        spotHits([
          { id:'FW', at:FIRST.W, label:'West, where the first tower spawns' },
          { id:'FE', at:FIRST.E, label:'East, where the first tower spawns' },
          { id:'OW', at:OUTSIDE.W, label:'West, outside the towers' },
          { id:'OE', at:OUTSIDE.E, label:'East, outside the towers' },
          { id:'stay', at:[lineX(LINE.indexOf(st.me)), LINE_Y], label:'Stay in your place in the line' }
        ], answerLine);
        return;
      }
      if(st.step === 2){
        pill('Step 2 · First towers');
        drawTowers(1);
        drawParty('sorted', state, null, { timer:true });
        instr(`The first towers are up: <span class="hl">${st.colour1.W}</span> in the west, <span class="hl">${st.colour1.E}</span> in the east. Click where you stand while the first towers resolve.<span class="hint"> <b>Astral Tilt soaks light towers, Umbral Tilt soaks dark ones</b>, so go to the side your Tilt fits: the <b>16 s</b> Tilt soaks it with the no-stack player, the <b>20 s</b> waits just outside.</span>`);
        spotHits([
          { id:'FW', at:FIRST.W, label:'Into the west tower' },
          { id:'FE', at:FIRST.E, label:'Into the east tower' },
          { id:'OW', at:OUTSIDE.W, label:'West, outside the towers' },
          { id:'OE', at:OUTSIDE.E, label:'East, outside the towers' }
        ].concat(st.kind[st.me] === 'short' || st.kind[st.me] === 'long'
          ? [{ id:'stay', at:[lineX(LINE.indexOf(st.me)), LINE_Y], label:'Stay in your place in the line' }] : []), answerFirst);
        return;
      }
      if(st.step === 3){
        pill('Step 3 · Second towers');
        drawTowers(2);
        drawParty('set1', state);
        instr(`The first towers resolved and handed out new Tilts. Four more towers are up, two per side. Click the tower you take.<span class="hint"> Whoever soaked the first tower on your side takes the <b>north</b> one; whoever waited outside takes the <b>south</b> one.</span>`);
        const spots = [];
        ['W', 'E'].forEach(sd => ['N', 'S'].forEach(r => spots.push({ sd, r, at: SECOND[sd][r], label:`${SIDE_WORD[sd]} ${ROW_WORD[r]} tower, ${colourAt(sd, r, 2)}` })));
        spotHits(spots, answerSecond);
        return;
      }
      if(st.step === 4){
        pill('Step 4 · Third towers');
        drawTowers(3);
        drawParty('set2', state);
        instr(`The second towers resolved. The last four towers are up, closer to the middle. Click the tower you take.<span class="hint"> If the second tower handed <b>you</b> a Tilt, swap rows; if it did not, stay in your row.</span>`);
        const spots = [];
        ['W', 'E'].forEach(sd => ['N', 'S'].forEach(r => spots.push({ sd, r, at: THIRD[sd][r], label:`${SIDE_WORD[sd]} ${ROW_WORD[r]} tower, ${colourAt(sd, r, 3)}` })));
        spotHits(spots, answerThird);
        return;
      }
      pill('Step 5 · Slimes and Grasp');
      drawParty('set3', st.snap[3]);
      instr(`Every tower is done. The slimes are about to tether and the main tank is marked for <span class="hl">Palladian Grasp</span>. Click where you go for the tethers and Palladian Grasp.<span class="hint"> The <b>no-stack</b> players drag the tethers away, west to the north-west corner and east to just east of the middle; everyone else waits clear of the tank's half.</span>`);
      spotHits([
        { id:'NW', at:FINAL.NW, label:'North-west corner' },
        { id:'NC', at:FINAL.NC, label:'North wall, just east of the middle' },
        { id:'NE', at:FINAL.NE, label:'North-east corner' },
        { id:'SW', at:FINAL.SW, label:'South of the middle, west half' },
        { id:'SE', at:FINAL.SE, label:'South of the middle, east half' }
      ], answerFinal);
    }

    /* ---------- answers ---------- */
    function judge(ok, title, why, next){
      if(ok){
        showFeedback(fb, true, title, why, next.label, next.fn);
      } else {
        showFeedback(fb, false, title, why, 'New pull ↻', () => newRound());
      }
    }
    function stepTo(n){
      if(n > 5) return { label:'New pull ↻', fn: () => newRound() };
      return { label:'Continue → Step ' + n, fn: () => { st.step = n; render(); } };
    }
    const other = s => LINE.find(q => q !== s && st.kind[q] === st.kind[s] && (st.kind[s] === 'zero' || st.kind[s] === 'one'));

    function answerLine(spot){
      lock();
      layer('pg-hits');
      const s = st.me, k = st.kind[s], sd = st.side[s];
      const want = k === 'zero' ? 'F' + sd : k === 'one' ? 'O' + sd : 'stay';
      const ok = spot.id === want;
      drawParty('sorted', stateAt(1), ok ? null : spot.at, { timer:true });
      let why;
      if(k === 'zero' || k === 'one'){
        const o = other(s), westmost = LINE.indexOf(s) < LINE.indexOf(o);
        why = `${k === 'zero' ? 'No-stack players step forward' : '1-stack players step back'}, so your row is you and <b>${o}</b>. The westmost of the two goes west; ${o} is ${westmost ? 'east' : 'west'} of you, so you go <b>${SIDE_WORD[sd]}</b>. ${k === 'zero' ? 'You will soak the <b>first tower</b> there.' : 'You wait <b>outside</b> the towers there, near where the second south tower spawns.'}`;
      } else {
        why = `With <b>2 stacks and a Tilt</b> you hold the line while the others step out, and you cannot pick a side yet: it depends on which colour the first towers are. <b>Stay in your place in the line</b> until they appear.`;
      }
      judge(ok, ok ? 'Right spot' : 'Wrong spot', why, stepTo(2));
    }

    function answerFirst(spot){
      lock();
      layer('pg-hits');
      const s = st.me, k = st.kind[s], sd = st.side[s];
      const inTower = k === 'zero' || k === 'short';
      const want = (inTower ? 'F' : 'O') + sd;
      const ok = spot.id === want;
      drawParty('set1', stateAt(2), ok ? null : spot.at, { timer:true });
      const p = st.pairs1[sd];
      const mate = (inTower ? p.tower : p.out).find(q => q !== s);
      let why;
      if(k === 'short' || k === 'long'){
        const tl = st.start.tilt[s];
        why = `Your <b>${TILT[tl].name}</b> soaks <b>${TILT[tl].soaks}</b> towers, and the ${TILT[tl].soaks} first tower is in the <b>${SIDE_WORD[sd]}</b>. `
          + (k === 'short'
            ? `Yours is the <b>16 s</b> Tilt, so you soak it with <b>${mate}</b>, who has no stacks. Stack tightly so you mix: 2 and 0 leaves you on 1.`
            : `Yours is the <b>20 s</b> Tilt, so you wait <b>outside</b> and mix with <b>${mate}</b>, who has 1 stack: 2 and 1 leaves you both on 1. Your Tilt is saved for the south tower next.`);
      } else if(k === 'zero'){
        why = `You hold the <b>${SIDE_WORD[sd]} first tower</b>. <b>${mate}</b> brings the Tilt that fits it, and you are the partner without a Tilt. You have no stacks to lose, so the mix only helps them.`;
      } else {
        why = `You stay <b>outside</b> in the ${SIDE_WORD[sd]}. <b>${mate}</b> brings the 20 s Tilt over and you mix: 1 and 2 leaves you both on 1.`;
      }
      judge(ok, ok ? 'First towers covered' : 'Wrong spot', why, stepTo(3));
    }

    function answerSecond(spot){
      lock();
      layer('pg-hits');
      const s = st.me, sd = st.side[s], row = st.row2[s];
      const ok = spot.sd === sd && spot.r === row;
      drawParty('set2', stateAt(3), ok ? null : spot.at);
      const mate = LINE.find(q => q !== s && st.side[q] === sd && st.row2[q] === row);
      const col = colourAt(sd, row, 2);
      const before = stateAt(3);
      const fitter = [s, mate].find(q => before.tilt[q]);
      const why = (row === 'N'
        ? `You soaked the first tower, so you take the <b>north</b> tower on your side. It is <b>${col}</b>, the opposite colour of the first, which fits the Tilt the first tower handed out.`
        : `You waited outside, so you take the <b>south</b> tower on your side. It is <b>${col}</b>, the same colour as the first, which fits the 20 s Tilt.`)
        + ` <b>${fitter}</b> carries the ${TILT[before.tilt[fitter]].name}, and you stack with <b>${mate}</b> to mix.`;
      judge(ok, ok ? 'Right tower' : 'Wrong tower', why, stepTo(4));
    }

    function answerThird(spot){
      lock();
      layer('pg-hits');
      const s = st.me, sd = st.side[s], row = st.row3[s];
      const ok = spot.sd === sd && spot.r === row;
      drawParty('set3', stateAt(4), ok ? null : spot.at);
      const got = st.got2[sd][st.row2[s]] === s;
      const tl = stateAt(4).tilt[s];
      const col = colourAt(sd, row, 3);
      const why = got
        ? `The ${colourAt(sd, st.row2[s], 2)} tower gave <b>you</b> the ${TILT[tl].name}, so you <b>swap rows</b>: ${ROW_WORD[st.row2[s]]} to <b>${ROW_WORD[row]}</b>. That tower is <b>${col}</b>, which your Tilt soaks.`
        : `The second tower gave its Tilt to your partner, not you, so you <b>stay in the ${ROW_WORD[row]} row</b>. The ${col} tower there needs a player without a Tilt, and the player swapping in brings the one that fits.`;
      const end = st.snap[3].stacks[s];
      judge(ok, ok ? 'Towers cleared' : 'Wrong tower', `${why} After this mix you are on <b>${end}</b> stack${end === 1 ? '' : 's'}.`, stepTo(5));
    }

    function answerFinal(spot){
      lock();
      layer('pg-hits');
      const s = st.me, want = finalKey(s);
      const ok = spot.id === want;
      const under = layer('pg-under');
      // Palladian Grasp on the east half, Factor In around both tether takers
      under.appendChild(el('rect', { x:X(20), y:0, width:X(20), height:Y(30), fill:'rgba(226,82,63,0.20)', stroke:'var(--astral)', 'stroke-width':1.5, 'stroke-dasharray':'8 6' }));
      const g = el('g', { 'clip-path':'url(#caloricClip)' });
      LINE.filter(q => st.kind[q] === 'zero').forEach(q => {
        const at = FINAL[finalKey(q)];
        g.appendChild(el('circle', { cx:X(at[0]), cy:Y(at[1]), r:FACTOR_IN_R * U, fill:'rgba(10,9,22,0.35)', stroke:'var(--mist-faint)', 'stroke-width':1.5 }));
      });
      under.appendChild(g);
      drawParty('final', st.snap[3], ok ? null : spot.at);
      const why = st.kind[s] === 'zero'
        ? `You never had Unstable Factor, so you have no Critical Factor and are the only kind of player who survives the slimes. Take the three tethers on your side <b>${st.side[s] === 'W' ? 'to the north-west corner' : 'north, just east of the middle'}</b>, far from the party.${st.side[s] === 'E' ? ' Stay close enough to the middle to step west before Palladian Grasp.' : ''}`
        : s === 'T1'
          ? `You are the main tank at the east end of the line, so Palladian Grasp is yours. Take it on the <b>east half</b> with your invulnerability, away from the party.`
          : `You cleared your stacks and carry Critical Factor, so a slime would kill you. Wait <b>south of the middle on the west half</b>, clear of the tethers and of Palladian Grasp on the east.`;
      judge(ok, ok ? 'Pangenesis cleared' : 'Wrong spot', why, stepTo(6));
    }

    legend();
    const newRound = T.trackRounds('pangenesis', startRound);
    shared.roleListeners.push(newRound);
    newRound();
  }

  T.register({ id: 'pangenesis', label: 'Pangenesis', phase: 'Pallas Athena', players: 'slot', markup: MARKUP, styles: STYLES, init: initPangenesis });
})(window.Twelfth);
