/* Caloric Theory II: take the spread, swap the red marker into the middle, then hand Entropifaction clockwise. */
(function(T){

  const { shared, showFeedback } = T;

  const STYLES = /* css */ `
    .c2-slot{
      font-family: var(--font-mono); font-weight: 700; font-size: 1.3rem;
      width: 52px; height: 52px; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
      border-radius: 14px; border: 1px solid var(--line-strong); background: rgba(241,236,249,0.05);
    }
    .c2-debuffs{ display: flex; flex-wrap: wrap; gap: 8px 16px; margin-top: 12px; }
    .c2-debuff{ display: flex; align-items: center; gap: 8px; font-size: 0.88rem; color: var(--mist-dim); }
    .c2-debuff img{ width: 24px; height: 32px; border-radius: 4px; flex-shrink: 0; object-fit: contain; }
    .c2-debuff b{ color: var(--mist); font-weight: 600; }
  `;

  const MARKUP = /* html */ `
  <div class="layout" data-dim="off" id="panel-caloric2" role="tabpanel" aria-labelledby="tabBtn-caloric2" hidden>

    <section class="arena-wrap">
      <div class="step-row">
        <span class="step-pill" id="c2-stepPill">Step 1 · Markers</span>
      </div>

      <svg class="arena-svg" id="c2-arena" viewBox="-14 -14 628 478" role="img" aria-label="Top-down view of Pallas Athena's arena with the Caloric Theory grid">
        <rect x="0" y="0" width="600" height="450" rx="6" fill="url(#floor)" pointer-events="none"/>
        <image href="assets/arena-phase2.svg" x="0" y="0" width="600" height="450" preserveAspectRatio="none" pointer-events="none"/>
        <g id="c2-grid" pointer-events="none"></g>
        <g id="c2-marks" pointer-events="none"></g>
        <g id="c2-under" pointer-events="none"></g>
        <g id="c2-players" pointer-events="none"></g>
        <g id="c2-hits"></g>
        <rect x="0" y="0" width="600" height="450" rx="6" fill="none" stroke="rgba(247,147,30,0.55)" stroke-width="2" filter="url(#glow)" pointer-events="none"/>
      </svg>

      <p class="arena-caption">North is up. Everyone stands on a grid intersection; neighbours in the spread are one rectangle diagonal apart.</p>

      <div class="feedback" id="c2-feedback" hidden aria-live="polite"></div>
    </section>

    <aside class="hud">
      <div class="card">
        <h2>Your slot</h2>
        <div class="lc-row">
          <div class="c2-slot" id="c2-slot">H1</div>
          <p class="assign-text" id="c2-assignText"></p>
        </div>
        <div class="c2-debuffs" id="c2-debuffs"></div>
      </div>

      <div class="card">
        <h2>Objective</h2>
        <p class="instr-text" id="c2-instrText"></p>
      </div>

      <details class="card">
        <summary>How the call works</summary>
        <ol>
          <li>During the cast everyone takes their spread spot on the grid: one player in the <b>middle</b>, six in a <b>hexagon</b> one rectangle diagonal out, and one more <b>south-east</b>, a diagonal beyond the hexagon. The drill seats T1 north, M2 north-east, H2 south-east, R2 far south-east, T2 south, H1 south-west, M1 north-west and R1 in the middle.</li>
          <li>Seven players get a <b>green</b> marker and one a <b>red</b> marker. If red is not already in the middle, the red player and the middle player <b>swap</b>.</li>
          <li>Everyone gets <b>Atmosfaction</b>, which goes off at the very end, so the final spots must stay spread. Green starts on 2 Close Caloric, red on 3. Walking more than about 18 yalms, two rectangle diagonals, is the fifth stack and wipes.</li>
          <li>One green-marked player, never the red one, gets <b>Entropifaction</b>, 8 stacks. It drops a big AoE under its holder each time a stack falls, and it passes to anyone it touches.</li>
          <li>As soon as the AoE appears under you, walk <b>clockwise to the next outside player</b> in a straight line and hand it over. The middle player is skipped and never moves.</li>
          <li>When the next AoE appears under the two of you, the passer steps <b>outward</b> and the new holder walks on. The usual spot is straight out into the gap beside you, but anywhere works that is clear of this AoE and every later one, outside everyone's Atmosfaction, and inside your walk limit.</li>
          <li>The last outside player carries it to the spot where the <b>first holder</b> started and stays there. Atmosfaction then goes off on everyone.</li>
        </ol>
      </details>

      <div class="card">
        <h2>Legend</h2>
        <div class="legend-list" id="c2-legend"></div>
      </div>
    </aside>

  </div>
  `;

  function initCaloric2(){
    const SVGNS = 'http://www.w3.org/2000/svg';
    const U = 15;
    const X = x => x * U, Y = y => y * U;
    const CENTRE = [20, 13];

    // The spread on the Caloric grid (lines every 7 yalms across and 4 down), read off Icy Veins' diagram.
    const SPOT = { N:[20, 5], NE:[27, 9], SE:[27, 17], FSE:[27, 25], S:[20, 21], SW:[13, 17], NW:[13, 9], C:[20, 13] };
    const RING = ['N', 'NE', 'SE', 'FSE', 'S', 'SW', 'NW'];         // clockwise, middle skipped
    const SEAT = { T1:'N', M2:'NE', H2:'SE', R2:'FSE', T2:'S', H1:'SW', M1:'NW', R1:'C' };
    const SPOT_WORD = { N:'north', NE:'north-east', SE:'south-east', FSE:'far south-east', S:'south', SW:'south-west', NW:'north-west', C:'middle' };
    const SLOTS = ['T1', 'T2', 'H1', 'H2', 'M1', 'M2', 'R1', 'R2'];
    const JOB = { T:'Tank', H:'Healer', M:'Melee DPS', R:'Ranged DPS' };
    const JOB_COLOR = { T:'var(--umbral-soft)', H:'var(--good)', M:'var(--astral-soft)', R:'var(--astral-soft)' };
    const OUT_STEP = 5.7;                     // how far the passer steps out, as in Icy Veins' diagram
    const EXCESS_R = 6.5, WIND_R = 5.4;
    const WALK_LIMIT = 18;                    // two 9-yalm Close Caloric stacks on top of the starting two
    const DIAGONALS = [[7, -4], [7, 4], [-7, 4], [-7, -4]];
    const DIAG_WORD = ['north-east', 'south-east', 'south-west', 'north-west'];
    const INTER_STEP = 8.5;

    const WAYMARK = {
      A:{ at:[20, 9], color:'#e2523f', shape:'circle' }, B:{ at:[24.4, 13], color:'#e8c14b', shape:'circle' },
      C:{ at:[20, 17], color:'#4a8fe0', shape:'circle' }, D:{ at:[15.6, 13], color:'#b083ea', shape:'circle' },
      '1':{ at:[7.3, 13], color:'#e2523f', shape:'square' }, '2':{ at:[32.7, 13], color:'#e8c14b', shape:'square' }
    };

    // Where the passer between two neighbouring ring spots steps out to: square off the line between
    // them, on the side away from the middle, so it is equally far from both AoEs.
    function outSpot(a, b){
      const pa = SPOT[a], pb = SPOT[b];
      const mx = (pa[0] + pb[0]) / 2, my = (pa[1] + pb[1]) / 2;
      const len = Math.hypot(pb[0] - pa[0], pb[1] - pa[1]);
      let nx = (pb[1] - pa[1]) / len, ny = -(pb[0] - pa[0]) / len;
      if(nx * (mx - CENTRE[0]) + ny * (my - CENTRE[1]) < 0){ nx = -nx; ny = -ny; }
      return [mx + nx * OUT_STEP, my + ny * OUT_STEP];
    }

    let st = {};
    const fb = document.getElementById('c2-feedback');
    const pick = arr => arr[Math.floor(Math.random() * arr.length)];

    function startRound(){
      st.me = shared.slot;
      st.red = pick(SLOTS);
      // seats after the swap
      st.seat = Object.assign({}, SEAT);
      const middle = SLOTS.find(s => SEAT[s] === 'C');
      if(st.red !== middle){ st.seat[middle] = SEAT[st.red]; st.seat[st.red] = 'C'; }
      st.who = {};
      SLOTS.forEach(s => st.who[st.seat[s]] = s);
      // the chain: clockwise from a random outside holder
      const start = Math.floor(Math.random() * RING.length);
      st.chain = RING.slice(start).concat(RING.slice(0, start));   // spot keys, holder order
      st.holders = st.chain.map(k => st.who[k]);
      st.outs = st.chain.slice(0, 6).map((k, i) => outSpot(k, st.chain[i + 1]));
      st.flow = buildFlow();
      st.step = 0;
      render();
    }

    // Which questions this player gets: the swap, the first hand-off, then their own turn.
    function buildFlow(){
      const steps = ['swap', 'first'];
      const i = st.holders.indexOf(st.me);
      if(i < 0) steps.push('hold');
      else {
        if(i >= 1) steps.push('carry');
        if(i <= 5) steps.push('exit');
      }
      return steps;
    }

    // Everyone's spot while holder k has just been handed the debuff (k = 0 is the opening drop).
    function positionsAt(k){
      const pos = {};
      SLOTS.forEach(s => pos[s] = SPOT[st.seat[s]].slice());
      for(let j = 0; j < st.holders.length; j++){
        const s = st.holders[j];
        if(j < k - 1) pos[s] = st.outs[j].slice();
        else if(j === k - 1) pos[s] = SPOT[st.chain[k]].slice();
      }
      return pos;
    }
    function finalPositions(){
      const pos = positionsAt(0);
      st.holders.forEach((s, j) => { pos[s] = j < 6 ? st.outs[j].slice() : SPOT[st.chain[0]].slice(); });
      return pos;
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
      document.querySelectorAll('#panel-caloric2 .hit').forEach(h => h.setAttribute('aria-disabled', 'true'));
    }

    function drawGrid(){
      const host = layer('c2-grid');
      const line = { stroke:'rgba(110,190,255,0.42)', 'stroke-width':1.5 };
      [6, 13, 20, 27, 34].forEach(x => host.appendChild(el('line', Object.assign({ x1:X(x), y1:0, x2:X(x), y2:Y(30) }, line))));
      [1, 5, 9, 13, 17, 21, 25, 29].forEach(y => host.appendChild(el('line', Object.assign({ x1:0, y1:Y(y), x2:X(40), y2:Y(y) }, line))));
      const marks = layer('c2-marks');
      Object.keys(WAYMARK).forEach(id => {
        const w = WAYMARK[id], cx = X(w.at[0]), cy = Y(w.at[1]);
        const style = { fill:w.color, 'fill-opacity':0.12, stroke:w.color, 'stroke-width':1.2, 'stroke-opacity':0.5 };
        marks.appendChild(w.shape === 'circle' ? el('circle', Object.assign({ cx, cy, r:12 }, style))
          : el('rect', Object.assign({ x:cx - 11, y:cy - 11, width:22, height:22, rx:3 }, style)));
        const t = el('text', { x:cx, y:cy + 4, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':11, 'font-weight':700, fill:w.color, opacity:0.6 });
        t.textContent = id;
        marks.appendChild(t);
      });
    }

    function drawPlayer(host, slot, at, o){
      { const layerHost = host; host = el('g', { class: 'player' + (slot === st.me ? ' me' : '') }); layerHost.appendChild(host); }
      o = o || {};
      const cx = X(at[0]), cy = Y(at[1]);
      const me = slot === st.me;
      if(o.marker){
        host.appendChild(el('circle', { cx, cy, r:19, fill:'none', stroke: o.marker === 'red' ? 'var(--bad)' : 'var(--good)',
          'stroke-width':3, 'stroke-dasharray':'5 4' }));
      }
      if(me) host.appendChild(el('circle', { cx, cy, r:16, fill:'none', stroke:'var(--mist)', 'stroke-width':2.5, class:'pulse' }));
      host.appendChild(el('circle', { cx, cy, r:12, fill:'rgba(10,9,22,0.94)', stroke: me ? 'var(--mist)' : JOB_COLOR[slot[0]], 'stroke-width': me ? 2 : 1.6 }));
      const t = el('text', { x:cx, y:cy + 3.6, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':10, 'font-weight':700, fill:JOB_COLOR[slot[0]] });
      t.textContent = slot;
      host.appendChild(t);
      if(o.holder){
        const bx = cx + 6, by = cy - 38;
        host.appendChild(el('rect', { x:bx - 1.5, y:by - 1.5, width:27, height:35, rx:4, fill:'var(--nebula-2)', stroke:'var(--line-strong)', 'stroke-width':1 }));
        host.appendChild(el('image', { href:'assets/entropifaction.png', x:bx, y:by, width:24, height:32, preserveAspectRatio:'xMidYMid meet' }));
      }
      if(me){
        const you = el('text', { x:cx, y:cy + 27, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':9, 'font-weight':700, fill:'var(--mist)' });
        you.textContent = 'YOU';
        host.appendChild(you);
      }
    }

    // Draw everyone; two players on one spot sit side by side.
    function drawParty(pos, opts){
      opts = opts || {};
      const host = layer('c2-players');
      const shown = {};
      SLOTS.forEach(s => shown[s] = pos[s].slice());
      SLOTS.forEach(a => SLOTS.forEach(b => {
        if(a < b && Math.hypot(pos[a][0] - pos[b][0], pos[a][1] - pos[b][1]) < 0.3){
          shown[a][0] -= 0.75; shown[b][0] += 0.75;
        }
      }));
      SLOTS.slice().sort((a, b) => (a === st.me) - (b === st.me)).forEach(s => drawPlayer(host, s, shown[s], {
        marker: opts.markers ? (s === st.red ? 'red' : 'green') : null,
        holder: opts.holder === s
      }));
    }

    function drawExcess(host, key){
      const at = SPOT[key];
      host.appendChild(el('circle', { cx:X(at[0]), cy:Y(at[1]), r:EXCESS_R * U, fill:'rgba(242,165,60,0.30)', stroke:'var(--shape-orange)', 'stroke-width':1.5 }));
    }
    function drawArrow(host, from, to){
      const x1 = X(from[0]), y1 = Y(from[1]), x2 = X(to[0]), y2 = Y(to[1]);
      const len = Math.hypot(x2 - x1, y2 - y1) || 1, ux = (x2 - x1) / len, uy = (y2 - y1) / len;
      const sx = x1 + ux * 18, sy = y1 + uy * 18, ex = x2 - ux * 18, ey = y2 - uy * 18;
      host.appendChild(el('line', { x1:sx, y1:sy, x2:ex, y2:ey, stroke:'var(--mist)', 'stroke-width':2.5, 'stroke-linecap':'round' }));
      host.appendChild(el('path', { d:`M${ex} ${ey} L${ex - ux*10 - uy*6} ${ey - uy*10 + ux*6} L${ex - ux*10 + uy*6} ${ey - uy*10 - ux*6} Z`, fill:'var(--mist)' }));
    }

    function spotHits(spots, onPick){
      const host = layer('c2-hits');
      spots.forEach(s => {
        const cx = X(s.at[0]), cy = Y(s.at[1]);
        const g = el('g', {});
        g.appendChild(el('circle', { cx, cy, r:19, class:'focus-ring', fill:'none', stroke:'var(--mist)', 'stroke-width':2.5, opacity:0 }));
        g.appendChild(el('circle', { cx, cy, r:14, fill:'rgba(241,236,249,0.16)', stroke:'var(--mist)', 'stroke-width':2 }));
        hitable(g, onPick, s, s.label);
        host.appendChild(g);
      });
    }
    const seatSpots = () => Object.keys(SPOT).map(k => ({ key:k, at:SPOT[k], label:`The ${SPOT_WORD[k]} spot` }));

    function legend(){
      const host = document.getElementById('c2-legend');
      const row = (lead, html) => `<div class="legend-item">${lead}<span>${html}</span></div>`;
      host.innerHTML =
          row('<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="none" stroke="var(--good)" stroke-width="2.4" stroke-dasharray="4 3"/></svg>', '<b>Green marker</b> — starts on 2 Close Caloric')
        + row('<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8" fill="none" stroke="var(--bad)" stroke-width="2.4" stroke-dasharray="4 3"/></svg>', '<b>Red marker</b> — starts on 3<span class="hint">, goes to the middle</span>')
        + row('<img src="assets/entropifaction.png" alt="">', '<b>Entropifaction</b> — drops an AoE per stack, passes on touch')
        + row('<img src="assets/atmosfaction.png" alt="">', '<b>Atmosfaction</b> — on everyone, goes off at the end')
        + row('<img src="assets/close-caloric.png" alt="">', '<b>Close Caloric</b> — five stacks wipes the raid')
        + row('<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9" fill="rgba(242,165,60,0.35)" stroke="var(--shape-orange)" stroke-width="1.6"/></svg>', '<b>Entropic Excess</b> — the AoE under the holder');
    }

    /* ---------- render ---------- */
    function pill(t){ document.getElementById('c2-stepPill').textContent = t; }
    function instr(h){ document.getElementById('c2-instrText').innerHTML = h; }

    function renderHud(){
      const s = st.me;
      const slot = document.getElementById('c2-slot');
      slot.textContent = s;
      slot.style.color = JOB_COLOR[s[0]];
      document.getElementById('c2-assignText').innerHTML = `${JOB[s[0]]}. Your spread spot is <b>${SPOT_WORD[SEAT[s]]}</b>.`;
      const red = s === st.red;
      document.getElementById('c2-debuffs').innerHTML =
          `<div class="c2-debuff"><span><b style="color:${red ? 'var(--bad)' : 'var(--good)'}">${red ? 'Red' : 'Green'} marker</b></span></div>`
        + `<div class="c2-debuff"><img src="assets/close-caloric.png" alt=""><span><b>Close Caloric ×${red ? 3 : 2}</b></span></div>`
        + `<div class="c2-debuff"><img src="assets/atmosfaction.png" alt=""><span><b>Atmosfaction</b></span></div>`
        + (st.flow[st.step] !== 'swap' && st.holders[0] === s ? `<div class="c2-debuff"><img src="assets/entropifaction.png" alt=""><span><b>Entropifaction ×8</b></span></div>` : '');
    }

    function render(){
      renderHud();
      ['c2-under', 'c2-players', 'c2-hits'].forEach(layer);
      fb.hidden = true;
      drawGrid();
      const kind = st.flow[st.step];
      const n = st.step + 1;

      if(kind === 'swap'){
        pill(`Step ${n} · Markers`);
        const pos = {};
        SLOTS.forEach(s => pos[s] = SPOT[SEAT[s]].slice());
        drawParty(pos, { markers:true });
        instr(`Everyone is in the spread and the markers are out: <span class="hl">${st.red}</span> has the red one. Click where you stand when the cast ends.<span class="hint"> The red marker swaps places with the player <b>clockwise</b> of it, and everyone else holds their spread spot.</span>`);
        spotHits(seatSpots(), answerSwap);
        return;
      }
      const under = layer('c2-under');
      if(kind === 'first'){
        pill(`Step ${n} · First hand-off`);
        drawExcess(under, st.chain[0]);
        drawParty(positionsAt(0), { holder: st.holders[0] });
        instr(st.holders[0] === st.me
          ? `Entropifaction is on <span class="hl">you</span> and its first AoE has appeared under you. Click where you walk to clear the AoE under you.`
          : `Entropifaction is on <span class="hl">${st.holders[0]}</span> and its first AoE has appeared. Click the spot it goes to first.`);
        spotHits(seatSpots(), answerFirst);
        return;
      }
      const i = st.holders.indexOf(st.me);
      if(kind === 'carry'){
        pill(`Step ${n} · Your carry`);
        drawExcess(under, st.chain[i]);
        drawParty(positionsAt(i), { holder: st.me });
        instr(`<span class="hl">${st.holders[i - 1]}</span> has handed you Entropifaction and the next AoE is under you both. Click where you walk to clear the AoE under you.<span class="hint"> Step <b>out of the AoE</b>, straight away from the middle and clear of the next one, and no further than <b>Close Caloric</b> allows.</span>`);
        spotHits(seatSpots(), answerCarry);
        return;
      }
      if(kind === 'exit'){
        pill(`Step ${n} · Your exit`);
        drawExcess(under, st.chain[i + 1]);
        drawParty(positionsAt(i + 1), { holder: st.holders[i + 1] });
        instr(`You have handed it to <span class="hl">${st.holders[i + 1]}</span>, and the next AoE is under you both. Click where you go now that you have passed Entropifaction on.<span class="hint"> You have passed it on, so step <b>back to your own spot</b> out of the AoE under you, without straying into the next one.</span>`);
        spotHits(exitCandidates(i), answerExit);
        return;
      }
      // hold: the middle player
      pill(`Step ${n} · Around you`);
      drawExcess(under, st.chain[2]);
      drawParty(positionsAt(2), { holder: st.holders[2] });
      instr(`You are in the middle and Entropifaction is making its way round. Click where you stand while it goes round the ring.<span class="hint"> The middle player never moves: the debuff passes clockwise round the outside and the AoEs land on the ring.</span>`);
      spotHits(seatSpots(), answerHold);
    }

    /* ---------- answers ---------- */
    function judge(ok, title, why, next){
      if(ok) showFeedback(fb, true, title, why, next.label, next.fn);
      else showFeedback(fb, false, title, why, 'New pull ↻', () => newRound());
    }
    function next(){
      if(st.step + 1 >= st.flow.length) return { label:'New pull ↻', fn: () => newRound() };
      return { label:'Continue → Step ' + (st.step + 2), fn: () => { st.step++; render(); } };
    }
    // After your last answer, show the whole thing resolved with Atmosfaction going off.
    /* ---------- the step out, judged by the rules rather than one fixed spot ---------- */
    const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);

    // Everything a spot has to satisfy for holder i stepping out after handing off.
    function exitCheck(i, q){
      const here = SPOT[st.chain[i + 1]];
      const walk = dist(SPOT[st.chain[i]], here) + dist(here, q);
      if(q[0] < 0.8 || q[0] > 39.2 || q[1] < 0.8 || q[1] > 29.2) return { ok:false, why:'floor', walk };
      if(walk > WALK_LIMIT) return { ok:false, why:'walk', walk };
      if(dist(q, here) <= EXCESS_R) return { ok:false, why:'current', walk };
      for(let k = i + 2; k <= 7; k++){
        const at = SPOT[st.chain[k % 7]];
        if(dist(q, at) <= EXCESS_R) return { ok:false, why:'later', k, walk };
      }
      const fin = finalPositions();
      const near = SLOTS.find(s => s !== st.holders[i] && dist(q, fin[s]) <= WIND_R);
      if(near) return { ok:false, why:'wind', who:near, walk };
      return { ok:true, walk };
    }

    // The textbook spot, the four grid intersections one diagonal away, and one spot just past the walk limit.
    function exitCandidates(i){
      const here = SPOT[st.chain[i + 1]];
      const out = [{ id:'std', at:st.outs[i], label:'Straight out, into the gap beside you' }];
      DIAGONALS.forEach((d, j) => out.push({ id:'diag' + j, at:[here[0] + d[0], here[1] + d[1]], label:`One grid diagonal ${DIAG_WORD[j]}` }));
      // true intercardinals, a little shorter than a grid diagonal
      [[1, -1], [1, 1], [-1, 1], [-1, -1]].forEach((d, j) => out.push({ id:'ic' + j,
        at:[here[0] + d[0] * INTER_STEP / Math.SQRT2, here[1] + d[1] * INTER_STEP / Math.SQRT2], label:`${INTER_STEP} yalms ${DIAG_WORD[j]}` }));
      const dirs = [[st.outs[i][0] - here[0], st.outs[i][1] - here[1]]].concat(DIAGONALS);
      for(const d of dirs){
        const len = Math.hypot(d[0], d[1]);
        const reach = WALK_LIMIT - dist(SPOT[st.chain[i]], here) + 1.2;
        const at = [here[0] + d[0] / len * reach, here[1] + d[1] / len * reach];
        if(at[0] >= 0.8 && at[0] <= 39.2 && at[1] >= 0.8 && at[1] <= 29.2){
          out.push({ id:'far', at, label:'Further out, well clear of everything' });
          break;
        }
      }
      const spots = out.filter((c, n) => c.at[0] >= 0.8 && c.at[0] <= 39.2 && c.at[1] >= 0.8 && c.at[1] <= 29.2
        && out.slice(0, n).every(o => dist(o.at, c.at) > 1.5));
      // Cramped corners of the ring can leave the textbook spot as the only safe one; find more
      // safe ground around you so there is always a real choice.
      for(const r of [7.2, 8, 8.8, 9.6]){
        for(let deg = 0; deg < 360 && spots.filter(c => exitCheck(i, c.at).ok).length < 3; deg += 15){
          const at = [here[0] + Math.cos(deg * Math.PI / 180) * r, here[1] + Math.sin(deg * Math.PI / 180) * r];
          if(exitCheck(i, at).ok && spots.every(c => dist(c.at, at) > 2.2)){
            spots.splice(spots.length - 1, 0, { id:'alt', at, label:`${r} yalms out` });
          }
        }
      }
      return spots;
    }

    function showEnd(mine){
      const pos = finalPositions();
      if(mine) pos[st.me] = mine;
      const under = layer('c2-under');
      SLOTS.forEach(s => under.appendChild(el('circle', { cx:X(pos[s][0]), cy:Y(pos[s][1]), r:WIND_R * U,
        fill:'rgba(111,209,154,0.13)', stroke:'var(--good)', 'stroke-width':1.2, 'stroke-opacity':0.7 })));
      drawParty(pos);
    }
    const last = () => st.step + 1 >= st.flow.length;

    function answerSwap(spot){
      lock();
      layer('c2-hits');
      const want = st.seat[st.me];
      const ok = spot.key === want;
      const pos = {};
      SLOTS.forEach(s => pos[s] = SPOT[st.seat[s]].slice());
      if(!ok) pos[st.me] = SPOT[spot.key].slice();
      drawParty(pos, { markers:true });
      const middle = SLOTS.find(s => SEAT[s] === 'C');
      let why;
      if(st.red === middle) why = `The red marker went to <b>${st.red}</b>, who is already in the middle, so nobody moves. You stay on the <b>${SPOT_WORD[want]}</b> spot.`;
      else if(st.me === st.red) why = `The red marker is yours and you are not in the middle, so you <b>swap with ${middle}</b>: you take the middle, they take your ${SPOT_WORD[SEAT[st.me]]} spot.`;
      else if(st.me === middle) why = `You hold the middle, but the red marker went to <b>${st.red}</b>. You swap: they come to the middle and you take their <b>${SPOT_WORD[want]}</b> spot.`;
      else why = `The red marker went to <b>${st.red}</b>, who swaps with <b>${middle}</b> in the middle. That does not touch you, so you stay on the <b>${SPOT_WORD[want]}</b> spot.`;
      judge(ok, ok ? 'Right spot' : 'Wrong spot', why, next());
    }

    function answerFirst(spot){
      lock();
      layer('c2-hits');
      const want = st.chain[1];
      const ok = spot.key === want;
      drawExcess(layer('c2-under'), st.chain[1]);
      drawParty(positionsAt(1), { holder: st.holders[1] });
      const why = `Entropifaction always goes <b>clockwise to the next outside player</b>, walked in a straight line. From the <b>${SPOT_WORD[st.chain[0]]}</b> spot that is <b>${st.holders[1]}</b> on the <b>${SPOT_WORD[want]}</b> spot. The middle player is never part of the chain.`
        + (spot.key === 'C' ? ' Walking to the middle would hand it to the one player who is meant to stay out of it.' : '');
      judge(ok, ok ? 'Right way round' : 'Wrong direction', why, next());
    }

    function answerCarry(spot){
      lock();
      layer('c2-hits');
      const i = st.holders.indexOf(st.me);
      const lastOne = i === 6;
      const want = lastOne ? st.chain[0] : st.chain[i + 1];
      const ok = spot.key === want;
      let why;
      if(lastOne){
        why = `You are the last outside player to get it, so there is nobody left to hand it to. Carry it to where the <b>first holder</b> started, the <b>${SPOT_WORD[want]}</b> spot, which they have left, and <b>stay there</b>. Its last AoE drops there, clear of everyone.`;
      } else {
        why = `As soon as the AoE appears under you, walk <b>clockwise</b> to the next outside player: <b>${st.holders[i + 1]}</b> on the <b>${SPOT_WORD[want]}</b> spot. ${st.holders[i - 1]} steps out behind you.`;
      }
      if(ok && lastOne){
        showEnd();
        judge(true, 'Caloric Theory II cleared', why + ' Everyone is now spread for <b>Atmosfaction</b>, and every outside player finishes on four Close Caloric stacks.', next());
        return;
      }
      if(ok){
        drawExcess(layer('c2-under'), want);
        drawParty(positionsAt(i + 1), { holder: st.holders[i + 1] });
      } else {
        const pos = positionsAt(i);
        pos[st.me] = SPOT[spot.key].slice();
        drawParty(pos, { holder: st.me });
      }
      judge(ok, ok ? 'Handed on' : 'Wrong spot', why, next());
    }

    function answerExit(spot){
      lock();
      layer('c2-hits');
      const i = st.holders.indexOf(st.me);
      const res = exitCheck(i, spot.at);
      const walked = `${res.walk.toFixed(1)} yalms`;
      const rule = `Step out of the AoE under you, stay clear of every AoE still to drop and of everyone's Atmosfaction, and keep your whole walk under <b>18 yalms</b>, two Close Caloric stacks.`;
      let why;
      if(res.ok){
        why = spot.id === 'std'
          ? `Straight out into the gap between your old <b>${SPOT_WORD[st.chain[i]]}</b> spot and the <b>${SPOT_WORD[st.chain[i + 1]]}</b> spot is the textbook step: one short walk, ${walked} in total.`
          : `That spot works too. ${rule} It does all of that, and your walk comes to ${walked}. The usual call is straight out into the gap beside you.`;
        showEnd(spot.at);
        judge(true, 'Caloric Theory II cleared', why + ' The chain finishes round the ring and Atmosfaction goes off on everyone, all spread. You end on four Close Caloric stacks.', next());
        return;
      }
      if(res.why === 'walk') why = `Too far. With the walk to ${st.holders[i + 1]} that comes to <b>${walked}</b>, past the 18 yalms that two stacks allow, so you reach <b>five Close Caloric stacks</b> and wipe the raid.`;
      else if(res.why === 'current') why = `That is still inside the AoE under you and ${st.holders[i + 1]}.`;
      else if(res.why === 'later') why = res.k === 7
        ? `That is where the <b>last</b> AoE drops, once the final carrier brings the debuff back to the ${SPOT_WORD[st.chain[0]]} spot.`
        : `That is inside the AoE that drops later on the <b>${SPOT_WORD[st.chain[res.k]]}</b> spot, when ${st.holders[res.k]} holds it.`;
      else if(res.why === 'wind') why = `That puts you inside <b>${st.holders.indexOf(res.who) < 0 ? 'the middle player' : res.who}</b>'s Atmosfaction when everyone's goes off at the end.`;
      else why = 'That is off the floor.';
      const pos = positionsAt(i + 1);
      pos[st.me] = spot.at.slice();
      drawParty(pos, { holder: st.holders[i + 1] });
      judge(false, res.why === 'walk' ? 'Fifth stack' : 'Not safe there', `${why} ${rule}`, next());
    }

    function answerHold(spot){
      lock();
      layer('c2-hits');
      const ok = spot.key === 'C';
      if(ok) showEnd();
      else {
        const pos = positionsAt(2);
        pos[st.me] = SPOT[spot.key].slice();
        drawParty(pos, { holder: st.holders[2] });
      }
      judge(ok, ok ? 'Caloric Theory II cleared' : 'Stay in the middle',
        `The middle player is <b>skipped</b> by the chain and never moves, so you keep the three stacks your red marker gave you. Every AoE drops one diagonal away from you, and the outside players step outward around you for Atmosfaction.`, next());
    }

    legend();
    const newRound = T.trackRounds('caloric2', startRound);
    shared.roleListeners.push(newRound);
    newRound();
  }

  T.register({ id: 'caloric2', label: 'Caloric Theory II', phase: 'Pallas Athena', players: 'slot', markup: MARKUP, styles: STYLES, init: initCaloric2 });
})(window.Twelfth);
