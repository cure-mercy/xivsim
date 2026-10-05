/* Caloric Theory I: pair fire with wind on the waymarks, spread the wind, restack the fire, then Ekpyrosis. */
(function(T){

  const { shared, showFeedback } = T;

  const STYLES = /* css */ `
    .ct-slot{
      font-family: var(--font-mono);
      font-weight: 700;
      font-size: 1.3rem;
      width: 52px; height: 52px; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
      border-radius: 14px;
      border: 1px solid var(--line-strong);
      background: rgba(241,236,249,0.05);
    }
    .ct-debuffs{ display: flex; flex-wrap: wrap; gap: 8px 16px; margin-top: 12px; }
    .ct-debuff{ display: flex; align-items: center; gap: 8px; font-size: 0.88rem; color: var(--mist-dim); }
    .ct-debuff img{ width: 24px; height: 32px; border-radius: 4px; flex-shrink: 0; object-fit: contain; }
    .ct-debuff b{ color: var(--mist); font-weight: 600; }
  `;

  const MARKUP = /* html */ `
  <div class="layout" data-dim="off" id="panel-caloric1" role="tabpanel" aria-labelledby="tabBtn-caloric1" hidden>

    <section class="arena-wrap">
      <div class="step-row">
        <span class="step-pill" id="ct-stepPill">Step 1 · Opening spot</span>
      </div>

      <svg class="arena-svg" id="ct-arena" viewBox="-14 -14 628 478" role="img" aria-label="Top-down view of Pallas Athena's arena with the Caloric Theory grid">
        <rect x="0" y="0" width="600" height="450" rx="6" fill="url(#floor)" pointer-events="none"/>
        <image href="assets/arena-phase2.svg" x="0" y="0" width="600" height="450" preserveAspectRatio="none" pointer-events="none"/>
        <g id="ct-grid" pointer-events="none"></g>
        <g id="ct-marks" pointer-events="none"></g>
        <g id="ct-under" pointer-events="none"></g>
        <g id="ct-players" pointer-events="none"></g>
        <g id="ct-over" pointer-events="none"></g>
        <g id="ct-hits"></g>
        <rect x="0" y="0" width="600" height="450" rx="6" fill="none" stroke="rgba(247,147,30,0.55)" stroke-width="2" filter="url(#glow)" pointer-events="none"/>
      </svg>

      <p class="arena-caption" id="ct-caption"></p>

      <div class="feedback" id="ct-feedback" hidden aria-live="polite"></div>
    </section>

    <aside class="hud">
      <div class="card">
        <h2>Your slot</h2>
        <div class="lc-row">
          <div class="ct-slot" id="ct-slot">H1</div>
          <p class="assign-text" id="ct-assignText"></p>
        </div>
        <div class="ct-debuffs" id="ct-debuffs"></div>
      </div>

      <div class="card">
        <h2>Objective</h2>
        <p class="instr-text" id="ct-instrText"></p>
      </div>

      <details class="card">
        <summary>How the call works</summary>
        <ol>
          <li>During the cast one support and one DPS get an orange <b>beacon</b>. The beaconed support takes <b>D</b> and the beaconed DPS <b>B</b>, standing on the line just inside the marker. Their counterparts in the other light party take <b>A</b> (support) and <b>C</b> (DPS). The other four wait in the middle.</li>
          <li>When the cast ends everyone gets <b>Close Caloric</b>: a stack for every 9 yalms walked or every fire stack taken, and five stacks wipes the raid. Four players get <b>Atmosfaction</b> (wind, starts at 2 stacks), the other four <b>Pyrefaction</b> (fire, 1 stack). The beacons are always wind.</li>
          <li>Each middle player walks out to someone with the <b>other</b> debuff. Supports move first, then DPS. <b>Light party 1</b> checks from <b>D counter-clockwise</b>, <b>light party 2</b> from <b>A clockwise</b>, skipping anyone already taken. Walk straight, never curve.</li>
          <li>The fire stacks go off. Two of the fire players get Pyrefaction again. The wind players now walk out: <b>A one row north</b>, <b>C one row south</b>, <b>D and B out beside waymarks 1 and 2</b>. That walk is their fourth stack, so they do not move again.</li>
          <li>The fire players on A and C restack with B or D: <b>clockwise</b> (A to B, C to D) unless that player has the same debuff state, then <b>counter-clockwise</b>. B and D hold still. Everyone ends on <b>four stacks</b>, so nobody moves until Close Caloric fades.</li>
          <li><b>Ekpyrosis</b> sends exaflares in from two opposite walls. Exaflares on the north and south walls: <b>tanks and melee north, healers and ranged south</b>. On the west and east walls: <b>light party 1 west, light party 2 east</b>. Wait in the gap between the two lanes on your wall. Once the first exaflares have gone off, spread along your wall in the <b>Gaiaochos</b> order: north and south walls like its rows (M1 T1 T2 M2, R1 H1 H2 R2), west and east walls like its columns (M1 T1 H1 R1, M2 T2 H2 R2).</li>
        </ol>
      </details>

      <div class="card">
        <h2>Legend</h2>
        <div class="legend-list" id="ct-legend"></div>
      </div>
    </aside>

  </div>
  `;

  function initCaloric1(){
    const SVGNS = 'http://www.w3.org/2000/svg';
    // The floor is 40 by 30 yalms, drawn at 15 units a yalm. The Caloric grid lines sit 7 yalms apart
    // across and 4 down, centred on the waymark diamond at (20, 13).
    const U = 15;
    const X = x => x * U, Y = y => y * U;
    const CENTRE = [20, 13];

    const WAYMARK = {
      A: { at:[20, 9],    color:'#e2523f', shape:'circle' },
      B: { at:[24.4, 13], color:'#e8c14b', shape:'circle' },
      C: { at:[20, 17],   color:'#4a8fe0', shape:'circle' },
      D: { at:[15.6, 13], color:'#b083ea', shape:'circle' },
      '1': { at:[7.3, 13],  color:'#e2523f', shape:'square' },
      '2': { at:[32.7, 13], color:'#e8c14b', shape:'square' }
    };
    // Where the players on each waymark actually stand: B and D sit on the grid line just inside.
    const SPOT = { A:[20, 9], B:[23.5, 13], C:[20, 17], D:[16.5, 13], mid:[20, 13] };
    const OUT  = { A:[20, 5], C:[20, 21], D:[9.3, 13], B:[30.7, 13] };
    const RING_LP1 = ['D', 'C', 'B', 'A'];   // counter-clockwise from D
    const RING_LP2 = ['A', 'B', 'C', 'D'];   // clockwise from A
    const WIND_R = 5.4, PULSE_R = 1.7, EXA_R = 5.2;
    const WIND_WALK = 9;                      // the walk out is one Close Caloric stack; further is a second

    const SLOTS = ['T1', 'T2', 'H1', 'H2', 'M1', 'M2', 'R1', 'R2'];
    const JOB = { T:'Tank', H:'Healer', M:'Melee DPS', R:'Ranged DPS' };
    const JOB_COLOR = { T:'var(--umbral-soft)', H:'var(--good)', M:'var(--astral-soft)', R:'var(--astral-soft)' };
    const CLOCK = { T1:0, M1:45, T2:90, M2:135, H2:180, R2:225, H1:270, R1:315 };
    const DEBUFF = {
      wind: { name:'Atmosfaction', icon:'assets/atmosfaction.png', word:'wind' },
      fire: { name:'Pyrefaction',  icon:'assets/pyrefaction.png',  word:'fire' }
    };

    const isSupport = s => s[0] === 'T' || s[0] === 'H';
    const lpOf = s => Number(s[1]);
    const counterpart = s => s[0] + (3 - lpOf(s));

    let st = {};
    const fb = document.getElementById('ct-feedback');

    /* ---------- the mechanic ---------- */
    function startRound(){
      const pick = arr => arr[Math.floor(Math.random() * arr.length)];
      st.me = shared.slot;
      st.beaconSup = pick(['T1', 'T2', 'H1', 'H2']);
      st.beaconDps = pick(['M1', 'M2', 'R1', 'R2']);

      // opening spots
      st.open = {};
      SLOTS.forEach(s => st.open[s] = 'mid');
      st.open[st.beaconSup] = 'D';
      st.open[st.beaconDps] = 'B';
      st.open[counterpart(st.beaconSup)] = 'A';
      st.open[counterpart(st.beaconDps)] = 'C';

      // debuffs: beacons are wind, two more wind at random, the rest fire
      st.debuff = {};
      const rest = SLOTS.filter(s => s !== st.beaconSup && s !== st.beaconDps);
      const extraWind = rest.slice().sort(() => Math.random() - 0.5).slice(0, 2);
      SLOTS.forEach(s => st.debuff[s] = (s === st.beaconSup || s === st.beaconDps || extraWind.indexOf(s) >= 0) ? 'wind' : 'fire');

      solvePairs();

      // two of the fire players take Pyrefaction again
      const fires = SLOTS.filter(s => st.debuff[s] === 'fire');
      st.second = fires.slice().sort(() => Math.random() - 0.5).slice(0, 2);
      solveRestack();

      st.ekpy = Math.random() < 0.5 ? 'ns' : 'we';
      st.mirror = Math.random() < 0.5;
      st.step = 1;
      render();
    }

    // Supports first, then DPS; light party 1 from D counter-clockwise, light party 2 from A clockwise.
    function solvePairs(){
      st.pairAt = {};          // middle player -> waymark
      st.partnerAt = {};       // waymark -> middle player
      st.trace = {};
      const outerAt = {};
      SLOTS.forEach(s => { if(st.open[s] !== 'mid') outerAt[st.open[s]] = s; });
      st.outerAt = outerAt;
      const mids = SLOTS.filter(s => st.open[s] === 'mid');
      const order = mids.filter(isSupport).sort((a, b) => lpOf(a) - lpOf(b))
        .concat(mids.filter(s => !isSupport(s)).sort((a, b) => lpOf(a) - lpOf(b)));
      order.forEach(p => {
        const ring = lpOf(p) === 1 ? RING_LP1 : RING_LP2;
        const steps = [];
        for(const m of ring){
          const who = outerAt[m];
          if(st.partnerAt[m]){ steps.push({ m, who, why:'taken', by: st.partnerAt[m] }); continue; }
          if(st.debuff[who] === st.debuff[p]){ steps.push({ m, who, why:'same' }); continue; }
          steps.push({ m, who, why:'match' });
          st.pairAt[p] = m;
          st.partnerAt[m] = p;
          break;
        }
        st.trace[p] = steps;
      });
      st.order = order;
    }

    // After the wind leaves, the fire players on A and C rotate onto B or D.
    function solveRestack(){
      st.stayAt = {};       // waymark -> the fire player left there
      ['A', 'B', 'C', 'D'].forEach(m => {
        const pair = [st.outerAt[m], st.partnerAt[m]];
        st.stayAt[m] = pair.find(s => st.debuff[s] === 'fire');
      });
      const has = m => st.second.indexOf(st.stayAt[m]) >= 0;
      st.restack = {};
      st.restack.A = has('A') !== has('B') ? 'B' : 'D';
      st.restack.C = has('C') !== has('D') ? 'D' : 'B';
    }

    function markOf(s){ return st.open[s] === 'mid' ? st.pairAt[s] : st.open[s]; }
    function isWind(s){ return st.debuff[s] === 'wind'; }

    // Everyone's position for each beat, in yalms.
    function positions(stage){
      const out = {};
      SLOTS.forEach(s => {
        if(stage === 'clock'){
          const a = (CLOCK[s] - 90) * Math.PI / 180;
          out[s] = [CENTRE[0] + Math.cos(a) * 6, CENTRE[1] + Math.sin(a) * 6];
          return;
        }
        if(stage === 'open'){
          if(st.open[s] !== 'mid'){ out[s] = SPOT[st.open[s]].slice(); return; }
          const dx = lpOf(s) === 1 ? -1.3 : 1.3, dy = isSupport(s) ? -1.3 : 1.3;
          out[s] = [CENTRE[0] + dx, CENTRE[1] + dy];
          return;
        }
        const m = markOf(s);
        if(stage === 'pair'){
          out[s] = pairSpot(m, st.open[s] === 'mid');
          return;
        }
        if(isWind(s)){ out[s] = OUT[m].slice(); return; }
        if(stage === 'spread'){ out[s] = SPOT[m].slice(); return; }
        // final: A and C rotate onto B or D, B and D hold
        if(m === 'B' || m === 'D'){ out[s] = pairSpot(m, false); return; }
        out[s] = pairSpot(st.restack[m], true);
      });
      return out;
    }
    function pairSpot(m, arriving){
      const base = SPOT[m];
      const off = arriving ? 0.8 : -0.8;
      return (m === 'A' || m === 'C') ? [base[0] + off, base[1]] : [base[0], base[1] + off];
    }

    /* ---------- drawing helpers ---------- */
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
      document.querySelectorAll('#panel-caloric1 .hit').forEach(h => h.setAttribute('aria-disabled', 'true'));
    }

    // Steps 1–4 zoom onto the middle of the floor; Ekpyrosis needs the walls, so it shows all of it.
    // `k` shrinks glyphs in the zoomed view so icons and labels keep their on-screen size.
    const FULL_VIEW = [-14, -14, 628, 478];
    const ZOOM_VIEW = [X(5), Y(1.5), X(30), X(30) * 478 / 628];
    let k = 1;
    function setView(zoom){
      const v = zoom ? ZOOM_VIEW : FULL_VIEW;
      document.getElementById('ct-arena').setAttribute('viewBox', v.join(' '));
      k = v[2] / FULL_VIEW[2];
      document.getElementById('ct-caption').textContent = zoom
        ? 'Zoomed on the middle of the floor, north up. Each blue rectangle is about 7 by 4 yalms; one diagonal stays just under a Close Caloric stack.'
        : 'The whole floor, north up. The exaflares march in from the walls shown.';
    }

    function drawGrid(){
      const host = layer('ct-grid');
      const line = { stroke:'rgba(110,190,255,0.42)', 'stroke-width':1.5 * k };
      [6, 13, 20, 27, 34].forEach(x => host.appendChild(el('line', Object.assign({ x1:X(x), y1:0, x2:X(x), y2:Y(30) }, line))));
      [1, 5, 9, 13, 17, 21, 25, 29].forEach(y => host.appendChild(el('line', Object.assign({ x1:0, y1:Y(y), x2:X(40), y2:Y(y) }, line))));
    }

    function drawWaymarks(){
      const host = layer('ct-marks');
      Object.keys(WAYMARK).forEach(id => {
        const w = WAYMARK[id], cx = X(w.at[0]), cy = Y(w.at[1]);
        const style = { fill:w.color, 'fill-opacity':0.18, stroke:w.color, 'stroke-width':1.5 * k, 'stroke-opacity':0.7 };
        if(w.shape === 'circle'){
          host.appendChild(el('circle', Object.assign({ cx, cy, r:15 * k }, style)));
        } else {
          host.appendChild(el('rect', Object.assign({ x:cx - 14 * k, y:cy - 14 * k, width:28 * k, height:28 * k, rx:3 * k }, style)));
        }
        const t = el('text', { x:cx, y:cy + 5 * k, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':14 * k, 'font-weight':700, fill:w.color, opacity:0.85 });
        t.textContent = id;
        host.appendChild(t);
      });
    }

    // One player: a role-coloured chip with the slot name, a debuff card turned away from the middle.
    function drawPlayer(host, slot, at, opts){
      { const layerHost = host; host = el('g', { class: 'player' + (slot === st.me ? ' me' : '') }); layerHost.appendChild(host); }
      const o = opts || {};
      const cx = X(at[0]), cy = Y(at[1]);
      const me = slot === st.me;
      if(o.beacon){
        host.appendChild(el('circle', { cx, cy, r:20 * k, fill:'none', stroke:'var(--shape-orange)', 'stroke-width':3 * k, 'stroke-dasharray':`${5 * k} ${4 * k}`, class:'pulse' }));
      }
      if(me){
        host.appendChild(el('circle', { cx, cy, r:17 * k, fill:'none', stroke:'var(--mist)', 'stroke-width':2.5 * k, class:'pulse' }));
      }
      host.appendChild(el('circle', { cx, cy, r:12 * k, fill:'rgba(10,9,22,0.92)', stroke: me ? 'var(--mist)' : JOB_COLOR[slot[0]], 'stroke-width':(me ? 2 : 1.6) * k }));
      const t = el('text', { x:cx, y:cy + 3.6 * k, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':10 * k, 'font-weight':700, fill:JOB_COLOR[slot[0]] });
      t.textContent = slot;
      host.appendChild(t);
      if(o.debuff){
        const sx = Math.sign(at[0] - CENTRE[0]) || (o.side || 1);
        const sy = Math.sign(at[1] - CENTRE[1]) || -1;
        const bx = sx > 0 ? cx + 6 * k : cx - 33 * k, by = sy > 0 ? cy - 2 * k : cy - 36 * k;
        host.appendChild(el('rect', { x:bx - 1.5 * k, y:by - 1.5 * k, width:27 * k, height:35 * k, rx:4 * k, fill:'var(--nebula-2)', stroke:'var(--line-strong)', 'stroke-width':k }));
        host.appendChild(el('image', { href:DEBUFF[o.debuff].icon, x:bx, y:by, width:24 * k, height:32 * k, preserveAspectRatio:'xMidYMid meet' }));
      }
      if(me){
        const you = el('text', { x:cx, y:cy + 27 * k, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':9 * k, 'font-weight':700, fill:'var(--mist)' });
        you.textContent = 'YOU';
        host.appendChild(you);
      }
    }

    // `debuffOf(slot)` decides which card each player shows; `mine` overrides your own position.
    function drawParty(stage, debuffOf, mine, extra){
      const host = layer('ct-players');
      const pos = positions(stage);
      if(mine) pos[st.me] = mine;
      SLOTS.slice().sort((a, b) => (a === st.me) - (b === st.me)).forEach(s => {
        const side = (st.open[s] === 'mid') ? 1 : -1;
        drawPlayer(host, s, pos[s], Object.assign({ debuff: debuffOf ? debuffOf(s) : null, side }, extra ? extra(s) : {}));
      });
      return pos;
    }

    function spotHits(spots, onPick){
      const host = layer('ct-hits');
      spots.forEach(s => {
        const cx = X(s.at[0]), cy = Y(s.at[1]);
        const g = el('g', {});
        g.appendChild(el('circle', { cx, cy, r:19 * k, class:'focus-ring', fill:'none', stroke:'var(--mist)', 'stroke-width':2.5 * k, opacity:0 }));
        g.appendChild(el('circle', { cx, cy, r:14 * k, fill:'rgba(241,236,249,0.14)', stroke:'var(--mist)', 'stroke-width':2 * k }));
        hitable(g, onPick, s, s.label);
        host.appendChild(g);
      });
    }

    // Dynamic Atmosphere: a plain circle that hits everyone in it except the player it comes from.
    function drawWind(host, at){
      host.appendChild(el('circle', { cx:X(at[0]), cy:Y(at[1]), r:WIND_R * U, fill:'rgba(111,209,154,0.24)',
        stroke:'var(--good)', 'stroke-width':1.2 * k }));
    }
    function drawPulse(host, at){
      host.appendChild(el('circle', { cx:X(at[0]), cy:Y(at[1]), r:PULSE_R * U, fill:'rgba(242,165,60,0.28)', stroke:'var(--shape-orange)', 'stroke-width':1.5 * k }));
    }

    /* ---------- Ekpyrosis ---------- */
    // Exaflares start in alternating lanes on two opposite walls; the proximity markers sit on the other two.
    function ekpyrosis(){
      const m = st.mirror;
      if(st.ekpy === 'ns'){
        const north = m ? [15, 35] : [4.5, 25], south = m ? [4.5, 25] : [15, 35];
        return {
          exa: north.map(x => ({ at:[x, 0.5], dir:[0, 1] })).concat(south.map(x => ({ at:[x, 29.5], dir:[0, -1] }))),
          prox: [[0.8, 15], [39.2, 15]],
          walls: { N:[(north[0] + north[1]) / 2, 1.6], S:[(south[0] + south[1]) / 2, 28.4], W:[1.6, 15], E:[38.4, 15] }
        };
      }
      const west = m ? [9.3, 25.3] : [2, 18.5], east = m ? [2, 18.5] : [9.3, 25.3];
      return {
        exa: west.map(y => ({ at:[0.5, y], dir:[1, 0] })).concat(east.map(y => ({ at:[39.5, y], dir:[-1, 0] }))),
        prox: [[20, 0.8], [20, 29.2]],
        walls: { W:[1.6, (west[0] + west[1]) / 2], E:[38.4, (east[0] + east[1]) / 2], N:[20, 1.6], S:[20, 28.4] }
      };
    }
    // After the first exaflare, each wall spreads out in the same order as Gaiaochos' Geocentrism spread:
    // the rows layout on the north and south walls, the columns layout on the west and east walls.
    const WALL_ORDER = {
      ns: { N:['M1', 'T1', 'T2', 'M2'], S:['R1', 'H1', 'H2', 'R2'] },
      we: { W:['M1', 'T1', 'H1', 'R1'], E:['M2', 'T2', 'H2', 'R2'] }
    };
    function spreadSpot(s){
      const order = WALL_ORDER[st.ekpy], w = ekpyWall(s), i = order[w].indexOf(s);
      if(st.ekpy === 'ns') return [[7, 15.5, 24.5, 33][i], w === 'N' ? 1.8 : 28.2];
      return [w === 'W' ? 1.8 : 38.2, [3.5, 11, 19, 26.5][i]];
    }
    function spreadCheck(q){
      const e = ekpyrosis();
      const hit = e.exa.find(x => Math.hypot(q[0] - (x.at[0] + x.dir[0] * EXA_STEP), q[1] - (x.at[1] + x.dir[1] * EXA_STEP)) < EXA_R + BODY);
      if(hit) return { ok:false, why:'exa' };
      const who = SLOTS.filter(o => o !== st.me).sort((a, b) =>
        Math.hypot(q[0] - spreadSpot(a)[0], q[1] - spreadSpot(a)[1]) - Math.hypot(q[0] - spreadSpot(b)[0], q[1] - spreadSpot(b)[1]))[0];
      if(Math.hypot(q[0] - spreadSpot(who)[0], q[1] - spreadSpot(who)[1]) < SPREAD_R + BODY) return { ok:false, why:'clip', who };
      return { ok:true };
    }
    // Out off each wall, halfway between its two marching exaflares: clear for now, but not a spread spot.
    function gapSpots(){
      const e = ekpyrosis();
      return [[0, 1], [2, 3]].map(([a, b]) => {
        const pa = e.exa[a], pb = e.exa[b];
        return [(pa.at[0] + pb.at[0]) / 2 + pa.dir[0] * EXA_STEP, (pa.at[1] + pb.at[1]) / 2 + pa.dir[1] * EXA_STEP];
      });
    }
    function wallGroup(){
      const walls = ekpyrosis().walls, pos = {}, byWall = {};
      SLOTS.forEach(q => { const w = ekpyWall(q); (byWall[w] = byWall[w] || []).push(q); });
      Object.keys(byWall).forEach(w => byWall[w].forEach((q, i) => {
        const along = (i - (byWall[w].length - 1) / 2) * 1.8, base = walls[w];
        pos[q] = (w === 'N' || w === 'S') ? [base[0] + along, base[1]] : [base[0], base[1] + along];
      }));
      return pos;
    }

    function ekpyWall(s){
      if(st.ekpy === 'ns') return (s[0] === 'T' || s[0] === 'M') ? 'N' : 'S';
      return lpOf(s) === 1 ? 'W' : 'E';
    }
    const EXA_STEP = 8, SPREAD_R = 3.5, BODY = 0.8;
    function drawEkpyrosis(advanced){
      const host = layer('ct-under');
      const e = ekpyrosis();
      const g = el('g', { 'clip-path':'url(#caloricClip)' });
      e.exa.forEach(x => {
        if(advanced){
          g.appendChild(el('circle', { cx:X(x.at[0]), cy:Y(x.at[1]), r:EXA_R * U, fill:'none', stroke:'var(--shape-orange)', 'stroke-width':1.2, 'stroke-dasharray':'4 5', opacity:0.5 }));
        }
        const at = advanced ? [x.at[0] + x.dir[0] * EXA_STEP, x.at[1] + x.dir[1] * EXA_STEP] : x.at;
        const cx = X(at[0]), cy = Y(at[1]);
        g.appendChild(el('circle', { cx, cy, r:EXA_R * U, fill:'rgba(242,165,60,0.30)', stroke:'var(--shape-orange)', 'stroke-width':1.5 }));
        for(let n = 1; n <= 3; n++){
          const ax = cx + x.dir[0] * (EXA_R * U + 16 * n), ay = cy + x.dir[1] * (EXA_R * U + 16 * n);
          const px = -x.dir[1] * 7, py = x.dir[0] * 7;
          g.appendChild(el('path', { d:`M${ax - x.dir[0]*7 + px} ${ay - x.dir[1]*7 + py} L${ax} ${ay} L${ax - x.dir[0]*7 - px} ${ay - x.dir[1]*7 - py}`,
            fill:'none', stroke:'var(--shape-orange)', 'stroke-width':2.5, 'stroke-linecap':'round', opacity: 0.9 - n * 0.2 }));
        }
      });
      if(!advanced) e.prox.forEach(p => {
        const cx = X(p[0]), cy = Y(p[1]);
        [70, 46, 22].forEach((r, i) => g.appendChild(el('circle', { cx, cy, r, fill: i === 2 ? 'rgba(226,82,63,0.45)' : 'none',
          stroke:'var(--astral)', 'stroke-width':2, opacity: 0.45 + i * 0.2 })));
      });
      host.appendChild(g);
    }

    function legend(){
      const host = document.getElementById('ct-legend');
      const row = (lead, html) => `<div class="legend-item">${lead}<span>${html}</span></div>`;
      host.innerHTML =
          row(`<img src="${DEBUFF.wind.icon}" alt="">`, '<b>Atmosfaction</b> — wind. Blows away anyone near you when it ends')
        + row(`<img src="${DEBUFF.fire.icon}" alt="">`, '<b>Pyrefaction</b> — fire. A stack for you and one partner')
        + row('<img src="assets/close-caloric.png" alt="">', '<b>Close Caloric</b> — five stacks wipes the raid')
        + row('<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="none" stroke="var(--shape-orange)" stroke-width="2.4" stroke-dasharray="4 3"/></svg>', '<b>Beacon</b> — during the cast, always ends as wind')
        + row('<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="none" stroke="var(--astral)" stroke-width="2"/><circle cx="12" cy="12" r="4" fill="var(--astral)"/></svg>', '<b>Proximity marker</b> — Ekpyrosis, damage falls off with distance<span class="hint">; get as far away as you can</span>')
        + row('<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="rgba(242,165,60,0.35)" stroke="var(--shape-orange)" stroke-width="1.6"/></svg>', '<b>Exaflare</b> — Ekpyrosis, marches across the floor');
    }

    /* ---------- render ---------- */
    function pill(t){ document.getElementById('ct-stepPill').textContent = t; }
    function instr(h){ document.getElementById('ct-instrText').innerHTML = h; }

    // Close Caloric: wind starts on 2 and fire on 1, the first fire stacks add one to everyone, and the
    // wind walk out is the wind players' fourth. Everyone ends the mechanic on 4. The fire players' count
    // going into the second stacks isn't given, so it isn't shown.
    function stacksAt(step){
      const w = isWind(st.me);
      if(step <= 2) return w ? 2 : 1;
      if(step === 3) return w ? 3 : 2;
      return w ? 4 : null;
    }

    function renderHud(){
      const s = st.me;
      const slot = document.getElementById('ct-slot');
      slot.textContent = s;
      slot.style.color = JOB_COLOR[s[0]];
      const beacon = s === st.beaconSup || s === st.beaconDps;
      document.getElementById('ct-assignText').innerHTML =
        `${JOB[s[0]]}, light party ${lpOf(s)}. Your counterpart is <b>${counterpart(s)}</b>.`;
      const box = document.getElementById('ct-debuffs');
      if(st.step === 1){
        box.innerHTML = `<div class="ct-debuff"><span>${beacon ? '<b>You have a beacon.</b>' : 'No beacon on you.'}</span></div>`;
        return;
      }
      if(st.step >= 5){
        box.innerHTML = `<div class="ct-debuff"><img src="assets/close-caloric.png" alt=""><span>Close Caloric wore off at <b>×4</b>, the same as everyone.</span></div>`;
        return;
      }
      const d = st.step === 4 && !isWind(s) ? (st.second.indexOf(s) >= 0 ? 'fire' : null) : st.debuff[s];
      box.innerHTML =
        (d ? `<div class="ct-debuff"><img src="${DEBUFF[d].icon}" alt=""><span><b>${DEBUFF[d].name}</b></span></div>` : `<div class="ct-debuff"><span>No fire or wind left.</span></div>`)
        + (stacksAt(st.step) ? `<div class="ct-debuff"><img src="assets/close-caloric.png" alt=""><span><b>Close Caloric ×${stacksAt(st.step)}</b></span></div>` : '');
    }

    function render(){
      renderHud();
      ['ct-under', 'ct-players', 'ct-over', 'ct-hits'].forEach(layer);
      fb.hidden = true;
      setView(st.step < 5);
      drawGrid();
      drawWaymarks();

      if(st.step === 1){
        pill('Step 1 · Opening spot');
        drawParty('clock', null, null, s => ({ beacon: s === st.beaconSup || s === st.beaconDps }));
        instr(`Caloric Theory is casting and two beacons have appeared. You are <span class="hl">${st.me}</span>. Click where you stand before the cast ends.<span class="hint"> The two <b>beacons</b> take B and D, supports on D and DPS on B; the unmarked player of the same role as the other light party's beacon takes A or C, supports A and DPS C. Everyone else waits <b>between</b> two markers.</span>`);
        spotHits(['A', 'B', 'C', 'D', 'mid'].map(m => ({ m, at: SPOT[m], label: m === 'mid' ? 'The middle, between all four waymarks' : 'Waymark ' + m })), answerOpen);
        return;
      }
      if(st.step === 2){
        pill('Step 2 · First stacks');
        drawParty('open', s => st.debuff[s]);
        instr(`The cast is done and everyone has fire or wind.<span class="hint"> Every fire needs a wind partner.</span> Click where you stand for the first stacks.`);
        spotHits(['A', 'B', 'C', 'D', 'mid'].map(m => ({ m, at: SPOT[m], label: m === 'mid' ? 'Stay in the middle' : 'Waymark ' + m })), answerPair);
        return;
      }
      if(st.step === 3){
        pill('Step 3 · Wind out');
        drawParty('pair', s => isWind(s) ? 'wind' : (st.second.indexOf(s) >= 0 ? 'fire' : null));
        instr(`The first stacks went off and two fire players have Pyrefaction again. Wind is about to go off. Click where you go before the wind goes off.<span class="hint"> Wind players leave the middle: north and south go out on their row, east and west just past the 1 and 2 markers, far enough that the donut misses the party but no further — that is the <b>fourth</b> stack of Close Caloric.</span>`);
        spotHits(windSpots(), answerSpread);
        return;
      }
      if(st.step === 4){
        pill('Step 4 · Second stacks');
        drawParty('spread', s => isWind(s) ? 'wind' : (st.second.indexOf(s) >= 0 ? 'fire' : null));
        instr(`The wind players are out and cannot move again. Two fire stacks are left to share. Click where you stand for the fire stacks.<span class="hint"> The middle players stack <b>east and west</b>: north and south rotate <b>clockwise</b> unless the player clockwise of them holds the same debuff, in which case they go the other way.</span>`);
        const spots = ['A', 'B', 'C', 'D'].map(m => ({ id:m, m, at: SPOT[m], label:'Waymark ' + m }));
        if(isWind(st.me)) spots.push({ id:'stay', at: OUT[markOf(st.me)], label:'Stay where you are' });
        spotHits(spots, answerRestack);
        return;
      }
      if(st.step === 6){
        pill('Step 6 · Spread');
        drawEkpyrosis(true);
        const group = wallGroup();
        drawParty('final', null);
        const host = layer('ct-players');
        SLOTS.forEach(q => drawPlayer(host, q, group[q], {}));
        instr(`The first exaflares have gone off and are marching in. Everyone is about to be hit by a big AoE. Click your spread spot.<span class="hint"> Spread along your wall in the <b>Gaiaochos</b> order: north and south walls west to east <b>M1 T1 T2 M2</b> and <b>R1 H1 H2 R2</b>, west and east walls north to south <b>M1 T1 H1 R1</b> and <b>M2 T2 H2 R2</b>.</span>`);
        const spots = SLOTS.map(q => ({ id:'spot-' + q, at: spreadSpot(q), label:'Spread spot on the ' + { N:'north', S:'south', W:'west', E:'east' }[ekpyWall(q)] + ' wall' }));
        gapSpots().forEach((at, i) => spots.push({ id:'gap' + i, at, label:'Out between the exaflares' }));
        spotHits(spots, answerSpreadWall);
        return;
      }
      pill('Step 5 · Ekpyrosis');
      drawEkpyrosis();
      drawParty('final', null);
      instr(`Close Caloric has worn off and <span class="hl">Ekpyrosis</span> is casting. Click the wall you run to.<span class="hint"> The exaflares decide it: north and south means <b>tanks and melee north</b>, healers and ranged south; east and west means <b>light party 1 west</b>, light party 2 east. Wait in the gap between the two lanes.</span>`);
      const walls = ekpyrosis().walls;
      spotHits(['N', 'E', 'S', 'W'].map(w => ({ w, at: walls[w], label:{ N:'North wall', E:'East wall', S:'South wall', W:'West wall' }[w] })), answerEkpy);
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
      if(n > 6) return { label:'New pull ↻', fn: () => newRound() };
      return { label:'Continue → Step ' + n, fn: () => { st.step = n; render(); } };
    }

    function answerOpen(spot){
      lock();
      layer('ct-hits');
      const want = st.open[st.me];
      const ok = spot.m === want;
      drawParty('open', null, ok ? null : spot.at, s => ({ beacon: s === st.beaconSup || s === st.beaconDps }));
      const s = st.me, mine = s === st.beaconSup || s === st.beaconDps, theirs = counterpart(s);
      const why = mine
        ? `The beacon is on you. The beaconed support stands on <b>D</b> and the beaconed DPS on <b>B</b>, on the grid line just inside the waymark, so you take <b>${want}</b>.`
        : (theirs === st.beaconSup || theirs === st.beaconDps)
          ? `Your counterpart <b>${theirs}</b> has the beacon, so you mirror them from the other light party: supports take <b>A</b> and DPS take <b>C</b>. That puts you on <b>${want}</b>.`
          : `Neither you nor your counterpart <b>${theirs}</b> has a beacon, so you wait in <b>the middle</b> between all four waymarks. The beacons are on <b>${st.beaconSup}</b> and <b>${st.beaconDps}</b>.`;
      judge(ok, ok ? 'Right spot' : 'Wrong spot', why, stepTo(2));
    }

    function traceText(p){
      return st.trace[p].map(t => {
        if(t.why === 'taken') return `${t.m} taken by ${t.by}`;
        if(t.why === 'same') return `${t.m} ${t.who} is ${DEBUFF[st.debuff[t.who]].word} too`;
        return `<b>${t.m} ${t.who} has ${DEBUFF[st.debuff[t.who]].word}</b>`;
      }).join(' → ');
    }

    function answerPair(spot){
      lock();
      layer('ct-hits');
      const s = st.me, fromMid = st.open[s] === 'mid';
      const want = fromMid ? st.pairAt[s] : st.open[s];
      const ok = spot.m === want;
      drawParty('pair', q => st.debuff[q], ok ? null : spot.at);
      let why;
      if(!fromMid){
        why = `You are on <b>${want}</b>, so you hold still and let a middle player come to you. <b>${st.partnerAt[want]}</b> has ${DEBUFF[st.debuff[st.partnerAt[want]]].word} and reaches you through the rotation. Walking anywhere would only cost you a stack.`;
      } else {
        const ring = lpOf(s) === 1 ? 'from <b>D counter-clockwise</b>' : 'from <b>A clockwise</b>';
        const first = isSupport(s) ? 'Supports move first' : `The supports have already picked (${st.order.filter(isSupport).map(q => q + ' to ' + st.pairAt[q]).join(', ')})`;
        why = `You have <b>${DEBUFF[st.debuff[s]].word}</b>, so you need a <b>${st.debuff[s] === 'fire' ? 'wind' : 'fire'}</b> partner. ${first}, and light party ${lpOf(s)} checks ${ring}: ${traceText(s)}. Walk straight out to <b>${want}</b>.`;
      }
      judge(ok, ok ? 'Paired up' : 'Wrong partner', why, stepTo(3));
    }

    /* ---------- the wind walk out, judged by the rules ---------- */
    const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
    function windPlayerAt(m){ return SLOTS.find(q => isWind(q) && markOf(q) === m); }

    // A wind spot is safe if it clips nobody when the wind goes off and the walk stays one stack.
    function windCheck(s, q){
      const walk = dist(positions('pair')[s], q);
      if(walk > WIND_WALK) return { ok:false, why:'far', walk };
      const fin = positions('final');
      const who = SLOTS.filter(o => o !== s).sort((a, b) => dist(q, fin[a]) - dist(q, fin[b]))[0];
      if(dist(q, fin[who]) < WIND_R) return { ok:false, why:'close', who, walk };
      return { ok:true, walk };
    }

    // Each direction gets its proper spot, a step too short and a walk too long, so the layout does
    // not give away which way your own wind goes.
    function windSpots(){
      const view = { x0: ZOOM_VIEW[0] / U + 1.2, x1: (ZOOM_VIEW[0] + ZOOM_VIEW[2]) / U - 1.2,
                     y0: ZOOM_VIEW[1] / U + 1.2, y1: (ZOOM_VIEW[1] + ZOOM_VIEW[3]) / U - 1.2 };
      const inView = q => q[0] >= view.x0 && q[0] <= view.x1 && q[1] >= view.y0 && q[1] <= view.y1;
      const spots = [];
      ['A', 'B', 'C', 'D'].forEach(m => {
        const w = windPlayerAt(m), start = positions('pair')[w];
        spots.push({ id:'out-' + m, at: OUT[m], label:`Out from ${m}` });
        // too close: partway along the walk, where the blast still reaches someone
        for(let t = 0.55; t >= 0.08; t -= 0.02){
          const q = [start[0] + (OUT[m][0] - start[0]) * t, start[1] + (OUT[m][1] - start[1]) * t];
          if(windCheck(w, q).why === 'close' && dist(q, start) >= 1.1){ spots.push({ id:'close-' + m, at:q, label:`A short step out from ${m}` }); break; }
        }
        // too far: a walk worth two stacks, turned along the wall if the straight line runs out of floor
        const base = Math.atan2(OUT[m][1] - start[1], OUT[m][0] - start[0]);
        for(const turn of [0, 30, -30, 50, -50, 70, -70]){
          const a = base + turn * Math.PI / 180, r = WIND_WALK + 2;
          const q = [start[0] + Math.cos(a) * r, start[1] + Math.sin(a) * r];
          if(inView(q)){ spots.push({ id:'far-' + m, at:q, label:`A long way out from ${m}` }); break; }
        }
      });
      spots.push({ id:'stay', at: positions('pair')[st.me], label:'Stay where you are' });
      return spots.filter((c, n) => spots.slice(0, n).every(o => dist(o.at, c.at) > 1.0));
    }

    function answerSpread(spot){
      lock();
      layer('ct-hits');
      const s = st.me, m = markOf(s), wind = isWind(s);
      const res = wind ? windCheck(s, spot.at) : null;
      const ok = wind ? res.ok : spot.id === 'stay';
      drawParty('spread', q => isWind(q) ? 'wind' : (st.second.indexOf(q) >= 0 ? 'fire' : null), ok && spot.id === 'out-' + m ? null : spot.at);
      const dest = { A:'one row north of A', C:'one row south of C', D:'out beside waymark 1', B:'out beside waymark 2' }[m];
      const rule = `From <b>${m}</b> the call is <b>${dest}</b>, slightly past the middle of the rectangle: far enough that your blast reaches nobody, and short enough that the walk is only your fourth Close Caloric stack.`;
      let why, title;
      if(!wind){
        title = ok ? 'Holding' : 'Not this time';
        why = `You have ${st.second.indexOf(s) >= 0 ? 'fire again' : 'nothing left'}, and your wind partner is the one leaving. <b>Stay on ${m}</b>: the second stacks form from here, and every step costs Close Caloric.`;
      } else if(ok){
        title = 'Wind clear';
        why = (spot.id === 'out-' + m ? '' : 'That spot works too. ') + `Your wind goes off next and blows away anyone near you, so you leave the stack. ${rule} You do not move again.`;
      } else if(res.why === 'far'){
        title = 'Fifth stack';
        why = `Too far. That walk is <b>${res.walk.toFixed(1)} yalms</b>, more than the one Close Caloric stack you have room for, so you reach <b>five</b> and wipe the raid. ${rule}`;
      } else {
        title = 'Too close';
        why = `Not far enough. When your wind goes off <b>${res.who}</b> is only ${dist(spot.at, positions('final')[res.who]).toFixed(1)} yalms away, inside the blast, and gets knocked back and killed. ${rule}`;
      }
      judge(ok, title, why, stepTo(4));
    }

    function answerRestack(spot){
      lock();
      layer('ct-hits');
      const s = st.me, m = markOf(s), wind = isWind(s);
      let want;
      if(wind) want = 'stay';
      else if(m === 'B' || m === 'D') want = m;
      else want = st.restack[m];
      const ok = spot.id === want;
      const pos = drawParty('final', q => isWind(q) ? 'wind' : (st.second.indexOf(q) >= 0 ? 'fire' : null), ok ? null : spot.at);
      const under = layer('ct-under');
      SLOTS.filter(isWind).forEach(q => drawWind(under, pos[q]));
      st.second.forEach(q => drawPulse(under, pos[q]));

      const has = q => st.second.indexOf(st.stayAt[q]) >= 0;
      const state = q => has(q) ? 'fire' : 'no debuff';
      let why;
      if(wind){
        why = `You are at four stacks after walking out. <b>Stay exactly where you are</b>: one more step is the fifth stack and wipes the raid. Your wind goes off out here, clear of both fire stacks.`;
      } else if(m === 'B' || m === 'D'){
        why = `You are on <b>${m}</b>, which holds still. The players from A and C come to B and D, so you wait for your new partner.`;
      } else {
        const cw = m === 'A' ? 'B' : 'D', ccw = m === 'A' ? 'D' : 'B';
        why = `From <b>${m}</b> you rotate <b>clockwise to ${cw}</b> unless its player has the same state as you. You have ${state(m)} and ${cw} has ${state(cw)}, so you go to <b>${want}</b>${want === ccw ? ', counter-clockwise' : ''}. One fire and one clean player end up on B and on D.`;
      }
      judge(ok, ok ? 'Caloric Theory cleared' : 'Not this spot',
        why + ' Once these stacks go off, all eight players sit on <b>four Close Caloric stacks</b>, one short of the wipe, so nobody moves until it fades.', stepTo(5));
    }

    function answerEkpy(spot){
      lock();
      layer('ct-hits');
      const want = ekpyWall(st.me);
      const ok = spot.w === want;
      drawEkpyrosis();
      const host = layer('ct-players');
      const group = wallGroup();
      SLOTS.forEach(q => { if(q !== st.me || ok) drawPlayer(host, q, group[q], {}); });
      if(!ok) drawPlayer(host, st.me, spot.at, {});
      const why = st.ekpy === 'ns'
        ? `The exaflares start on the <b>north and south</b> walls, with the proximity markers on the other two. <b>Tanks and melee go north, healers and ranged go south</b>, into the gap between the two lanes. As ${JOB[st.me[0]].toLowerCase()} you take the <b>${want === 'N' ? 'north' : 'south'}</b> wall.`
        : `The exaflares start on the <b>west and east</b> walls, with the proximity markers on the other two. <b>Light party 1 goes west, light party 2 east</b>, into the gap between the two lanes. You are in light party ${lpOf(st.me)}, so <b>${want === 'W' ? 'west' : 'east'}</b>.`;
      judge(ok, ok ? 'Out of the proximity' : 'Wrong wall',
        `${why} Wait there for the first exaflare to go off.`, stepTo(6));
    }

    function answerSpreadWall(spot){
      lock();
      layer('ct-hits');
      const res = spreadCheck(spot.at);
      const usual = spot.id === 'spot-' + st.me;
      drawEkpyrosis(true);
      const host = layer('ct-players');
      SLOTS.forEach(q => {
        const at = q === st.me ? spot.at : spreadSpot(q);
        host.appendChild(el('circle', { cx:X(at[0]), cy:Y(at[1]), r:SPREAD_R * U, fill:'rgba(226,82,63,0.14)', stroke:'var(--astral-soft)', 'stroke-width':1.2 }));
      });
      SLOTS.forEach(q => drawPlayer(host, q, q === st.me ? spot.at : spreadSpot(q), {}));
      const w = ekpyWall(st.me), order = WALL_ORDER[st.ekpy][w];
      const wallWord = { N:'north', S:'south', W:'west', E:'east' }[w];
      const rule = st.ekpy === 'ns'
        ? `Each wall spreads out in the same order as Gaiaochos' rows spread: north wall west to east <b>M1, T1, T2, M2</b>, south wall <b>R1, H1, H2, R2</b>. You are ${order.indexOf(st.me) + 1} of 4 on the <b>${wallWord}</b> wall.`
        : `Each wall spreads out in the same order as Gaiaochos' columns spread: west wall north to south <b>M1, T1, H1, R1</b>, east wall <b>M2, T2, H2, R2</b>. You are ${order.indexOf(st.me) + 1} of 4 on the <b>${wallWord}</b> wall.`;
      let why, title, verdict;
      if(res.ok && usual){
        verdict = true; title = 'Ekpyrosis cleared';
        why = `${rule} The first exaflares have already passed the wall, so it is safe to spread along it. After the hits, weave back to the middle between the rest.`;
      } else if(res.ok && spot.id.startsWith('gap')){
        verdict = 'warn'; title = 'Safe, but out between the lanes';
        why = `Nothing hits you there yet and your AoE reaches nobody, but you have walked out between the exaflares instead of spreading on the wall. They keep marching, so you will have more to dodge, and your place on the wall is empty. ${rule}`;
      } else if(res.ok){
        verdict = 'warn'; title = 'Safe, but off your spot';
        why = `You survive: nothing marches through there and your AoE reaches nobody. It is not your spot, though, so the rest of your wall has to adjust around you. ${rule}`;
      } else if(res.why === 'exa'){
        verdict = false; title = 'In the exaflare';
        why = `That is right in front of an exaflare marching in off the wall. Stay against the wall behind it. ${rule}`;
      } else {
        verdict = false; title = 'Too close';
        why = `That is <b>${res.who}</b>'s spot, so your AoE and theirs land on each other. ${rule}`;
      }
      if(verdict === 'warn') showFeedback(fb, 'warn', title, why, 'New pull ↻', () => newRound());
      else judge(verdict, title, why, stepTo(7));
    }

    legend();
    const newRound = T.trackRounds('caloric1', startRound);
    shared.roleListeners.push(newRound);
    newRound();
  }

  T.register({ id: 'caloric1', label: 'Caloric Theory I', phase: 'Pallas Athena', players: 'slot', markup: MARKUP, styles: STYLES, init: initCaloric1 });
})(window.Twelfth);
