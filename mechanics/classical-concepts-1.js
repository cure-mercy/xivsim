/* The Classical Concepts I: block your shape's tether, dodge Implode, then bait Palladian Ray. */
(function(T){

  const { showFeedback } = T;

  const STYLES = /* css */ `
    .cc-mark{
      width: 52px; height: 52px; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
      background: rgba(241,236,249,0.05);
      border: 1px solid var(--line-strong);
      border-radius: 14px;
    }
    .cc-mark svg{ width: 34px; height: 34px; }
    .cc-target{ display: flex; align-items: center; gap: 10px; margin-top: 12px; }
    .cc-target img{ width: 24px; height: 32px; border-radius: 4px; flex-shrink: 0; object-fit: contain; }
    .cc-target b{ color: var(--mist); font-weight: 600; }
  `;

  const MARKUP = /* html */ `
  <div class="layout" id="panel-classical1" role="tabpanel" aria-labelledby="tabBtn-classical1" hidden>

    <section class="arena-wrap">
      <div class="step-row">
        <span class="step-pill" id="c1-stepPill">Step 1 · Block a tether</span>
      </div>

      <svg class="arena-svg" id="c1-arena" viewBox="48.8 21.8 502.4 422.4" role="img" aria-label="Top-down view of Pallas Athena's arena with the twelve Classical Concepts shapes">
        <rect x="60" y="60" width="480" height="360" rx="6" fill="url(#floor)" pointer-events="none"/>
        <image href="assets/arena-phase2.svg" x="60" y="60" width="480" height="360" preserveAspectRatio="none" pointer-events="none"/>
        <!-- the six tiles left after the southern row fell away -->
        <g stroke="var(--line)" stroke-width="1.5" pointer-events="none">
          <line x1="300" y1="60" x2="300" y2="420"/>
          <line x1="60" y1="180" x2="540" y2="180"/>
          <line x1="60" y1="300" x2="540" y2="300"/>
        </g>
        <g id="c1-labels" font-family="Space Mono, monospace" font-size="12" fill="var(--mist-faint)" text-anchor="middle" pointer-events="none">
          <text x="156" y="46">COL 1</text>
          <text x="252" y="46">COL 2</text>
          <text x="348" y="46">COL 3</text>
          <text x="444" y="46">COL 4</text>
        </g>

        <g id="c1-under"></g>
        <g id="c1-shapes"></g>
        <g id="c1-over"></g>
        <g id="c1-players"></g>
        <g id="c1-hits"></g>

        <rect x="60" y="60" width="480" height="360" rx="6" fill="none" stroke="rgba(247,147,30,0.55)" stroke-width="2" filter="url(#glow)" pointer-events="none"/>
      </svg>

      <p class="arena-caption">North is up and columns count from the west. The shapes sit 8 yalms apart; Implode reaches 4 yalms around each.</p>

      <div class="feedback" id="c1-feedback" hidden aria-live="polite"></div>
    </section>

    <aside class="hud">
      <div class="card">
        <h2>Your marker</h2>
        <div class="lc-row">
          <div class="cc-mark" id="c1-mark"></div>
          <p class="assign-text" id="c1-assignText"></p>
        </div>
        <div class="cc-target" id="c1-target"></div>
      </div>

      <div class="card">
        <h2>Objective</h2>
        <p class="instr-text" id="c1-instrText"></p>
      </div>

      <details class="card">
        <summary>How the call works</summary>
        <ol>
          <li><b>The Classical Concepts</b> gives everyone a marker: blue ✕, purple square, red circle or green triangle. Each marker is shared by two players, one with <b>Alpha Target</b> and one with <b>Beta Target</b>, and they are then <b>Shackled Together</b>. Drift too far apart and both die.</li>
          <li>Twelve shapes appear in <b>four columns of three</b>: a blue icosahedron in every column, plus four red pyramids and four yellow cubes. Every red pyramid and yellow cube tethers to a blue <b>directly beside it</b>, and any tether nobody stands in fuses and wipes the raid.</li>
          <li>Go to your column by marker, west to east: <b>blue ✕, purple square, red circle, green triangle</b>. Stand between your column's blue and a shape beside it: <b>Alpha</b> blocks a <b>red pyramid</b>, <b>Beta</b> a <b>yellow cube</b>.</li>
          <li>If two of your colour touch your blue, take the one <b>no other blue can have</b>. Every layout has exactly one answer.</li>
          <li>Once the shackles drop, every shape <b>Implodes</b> on a short telegraph. Wait in a gap between four shapes on your tentacle's side: <b>Alpha north, Beta south</b>.</li>
          <li><b>Palladian Ray</b> drives a tentacle into the west and east of the floor, each firing lingering cones at its <b>four nearest players</b>. Columns 1–2 bait west and 3–4 bait east, each player in their <b>own column</b>, Alpha north and Beta south. Then step out of your cone.</li>
        </ol>
      </details>

      <div class="card">
        <h2>Legend</h2>
        <div class="legend-list" id="c1-legend"></div>
      </div>
    </aside>

  </div>
  `;

  function initClassical1(){
    const SVGNS = 'http://www.w3.org/2000/svg';
    const RAD = Math.PI / 180;

    // Pallas Athena's floor is the first phase's with the southern row of tiles gone, 40 by 30 yalms,
    // drawn at 12 units a yalm. The shapes sit on an 8-yalm grid, 8 in from the west wall and 4 in from
    // the north one; the tentacles land about 13 yalms in from each side wall, 10 down from the north.
    const COL_X = [156, 252, 348, 444];
    const ROW_Y = [108, 204, 300];
    const R_IMPLODE = 48;
    const R_BODY = 13;
    const BLADE = { west:[216, 180], east:[384, 180] };
    const BAIT_DY = 64;
    const CONE_HALF = 14 * RAD, CONE_LEN = 520;
    const WAIT_Y = { alpha:148, beta:260 };

    const MARKERS = [
      { id:'cross',    name:'blue ✕',         color:'var(--umbral-soft)' },
      { id:'square',   name:'purple square',  color:'var(--shape-purple)' },
      { id:'circle',   name:'red circle',     color:'var(--astral-soft)' },
      { id:'triangle', name:'green triangle', color:'var(--good)' }
    ];
    const TARGET = {
      alpha: { name:'Alpha Target', short:'α', kind:'red',    icon:'assets/alpha-target.png' },
      beta:  { name:'Beta Target',  short:'β', kind:'yellow', icon:'assets/beta-target.png' }
    };
    const SHAPE = {
      blue:   { name:'blue icosahedron', plural:'blue icosahedrons', stroke:'var(--umbral-soft)', fill:'rgba(74,143,224,0.30)', tether:'var(--umbral)' },
      red:    { name:'red pyramid',      plural:'red pyramids',      stroke:'var(--astral-soft)', fill:'rgba(226,82,63,0.32)',  tether:'var(--astral)' },
      yellow: { name:'yellow cube',      plural:'yellow cubes',      stroke:'var(--aether-soft)', fill:'rgba(247,147,30,0.30)', tether:'var(--aether)' }
    };

    /* ---------- layouts ---------- */
    // Cells run row by row: 0–3 is the north row, 8–11 the south row.
    const rowOf = i => Math.floor(i / 4), colOf = i => i % 4;
    function neighbours(i){
      const r = rowOf(i), c = colOf(i), out = [];
      if(r > 0) out.push(i - 4);
      if(r < 2) out.push(i + 4);
      if(c > 0) out.push(i - 1);
      if(c < 3) out.push(i + 1);
      return out;
    }
    function adjacent(a, b){ return neighbours(a).indexOf(b) >= 0; }

    // Ways to give each column's blue its own shape from `pool`, stopping once two are found.
    function matchings(blues, pool){
      let count = 0, found = null;
      const used = [];
      (function walk(k, acc){
        if(count > 1) return;
        if(k === blues.length){ count++; found = acc.slice(); return; }
        pool.forEach(s => {
          if(used.indexOf(s) < 0 && adjacent(blues[k], s)){
            used.push(s); acc.push(s);
            walk(k + 1, acc);
            acc.pop(); used.pop();
          }
        });
      })(0, []);
      return { count, found };
    }

    // Every layout the fight's rules allow: one blue per column, four of each other shape, no blue
    // boxed in by two reds and two yellows, and exactly one way to block every tether.
    const LAYOUTS = (function(){
      const out = [];
      for(let code = 0; code < 81; code++){
        const blues = [0, 1, 2, 3].map(c => (Math.floor(code / Math.pow(3, c)) % 3) * 4 + c);
        const rest = [];
        for(let i = 0; i < 12; i++) if(blues.indexOf(i) < 0) rest.push(i);
        for(let mask = 0; mask < 256; mask++){
          let bits = 0;
          for(let k = 0; k < 8; k++) bits += (mask >> k) & 1;
          if(bits !== 4) continue;
          const reds = rest.filter((_, k) => (mask >> k) & 1);
          const yellows = rest.filter((_, k) => !((mask >> k) & 1));
          const boxed = blues.some(b => {
            const n = neighbours(b);
            return n.filter(x => reds.indexOf(x) >= 0).length >= 2 && n.filter(x => yellows.indexOf(x) >= 0).length >= 2;
          });
          if(boxed) continue;
          const mr = matchings(blues, reds);
          if(mr.count !== 1) continue;
          const my = matchings(blues, yellows);
          if(my.count !== 1) continue;
          out.push({ blues, reds, yellows, red: mr.found, yellow: my.found });
        }
      }
      return out;
    })();

    /* ---------- geometry ---------- */
    function cellXY(i){ return [COL_X[colOf(i)], ROW_Y[rowOf(i)]]; }
    function mid(a, b){
      const p = cellXY(a), q = cellXY(b);
      return [(p[0] + q[0]) / 2, (p[1] + q[1]) / 2];
    }
    function kindOf(i){
      if(st.lay.blues.indexOf(i) >= 0) return 'blue';
      return st.lay.reds.indexOf(i) >= 0 ? 'red' : 'yellow';
    }
    function side(c){ return c < 2 ? 'west' : 'east'; }
    function where(blue, other){
      const d = other - blue;
      return d === -4 ? 'above it' : d === 4 ? 'below it' : d === -1 ? 'to its left' : 'to its right';
    }
    function blockSpot(c, t){ return mid(st.lay.blues[c], st.lay[TARGET[t].kind][c]); }
    // The gap you pick for Implode, and where you are drawn waiting in it once the step is done.
    function gapSpot(c, t){ return [c < 2 ? 204 : 396, t === 'alpha' ? 156 : 252]; }
    function waitSpot(c, t){ return [c < 2 ? 204 : 396, WAIT_Y[t]]; }
    function baitSpot(c, t){ return [COL_X[c], 180 + (t === 'alpha' ? -BAIT_DY : BAIT_DY)]; }
    function inImplode(xy){
      for(let i = 0; i < 12; i++){
        const p = cellXY(i);
        if(Math.hypot(xy[0] - p[0], xy[1] - p[1]) < R_IMPLODE + 6) return true;
      }
      return false;
    }

    let st = {};
    const fb = document.getElementById('c1-feedback');

    function startRound(){
      st.lay = LAYOUTS[Math.floor(Math.random() * LAYOUTS.length)];
      st.col = Math.floor(Math.random() * 4);
      st.t = Math.random() < 0.5 ? 'alpha' : 'beta';
      st.step = 1;
      // the party waits south in shackled pairs, in no particular order
      const order = [0, 1, 2, 3].sort(() => Math.random() - 0.5);
      st.start = {};
      order.forEach((c, k) => {
        st.start[c] = { alpha:[246 + k * 36, 368], beta:[246 + k * 36, 402] };
      });
      render();
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
      document.querySelectorAll('#panel-classical1 .hit').forEach(h => h.setAttribute('aria-disabled', 'true'));
    }

    function markerGlyph(host, id, x, y, s, color, width){
      const w = width || 2.5;
      const common = { fill:'none', stroke:color, 'stroke-width':w, 'stroke-linecap':'round', 'stroke-linejoin':'round' };
      if(id === 'cross'){
        host.appendChild(el('path', Object.assign({ d:`M${x-s} ${y-s} L${x+s} ${y+s} M${x+s} ${y-s} L${x-s} ${y+s}` }, common)));
      } else if(id === 'square'){
        host.appendChild(el('rect', Object.assign({ x:x-s, y:y-s, width:2*s, height:2*s, rx:1.5 }, common)));
      } else if(id === 'circle'){
        host.appendChild(el('circle', Object.assign({ cx:x, cy:y, r:s * 1.1 }, common)));
      } else {
        host.appendChild(el('path', Object.assign({ d:`M${x} ${y-s*1.15} L${x+s*1.15} ${y+s*0.85} L${x-s*1.15} ${y+s*0.85} Z` }, common)));
      }
    }

    function shapeGlyph(host, i, faded){
      const [x, y] = cellXY(i);
      const k = kindOf(i), sp = SHAPE[k];
      const g = el('g', { opacity: faded ? 0.35 : 1 });
      if(k === 'blue'){
        const pts = [];
        for(let a = 0; a < 6; a++) pts.push([x + Math.cos((a * 60 - 90) * RAD) * 21, y + Math.sin((a * 60 - 90) * RAD) * 21]);
        g.appendChild(el('polygon', { points: pts.map(p => p.join(',')).join(' '), fill:sp.fill, stroke:sp.stroke, 'stroke-width':2 }));
        g.appendChild(el('path', { d:`M${pts[0]} L${pts[2]} L${pts[4]} Z M${pts[1]} L${pts[3]} L${pts[5]} Z`,
          fill:'none', stroke:sp.stroke, 'stroke-width':1, opacity:0.55 }));
      } else if(k === 'red'){
        g.appendChild(el('path', { d:`M${x} ${y-21} L${x+19} ${y+14} L${x-19} ${y+14} Z`, fill:sp.fill, stroke:sp.stroke, 'stroke-width':2, 'stroke-linejoin':'round' }));
        g.appendChild(el('path', { d:`M${x} ${y-21} L${x+4} ${y+14}`, fill:'none', stroke:sp.stroke, 'stroke-width':1, opacity:0.55 }));
      } else {
        g.appendChild(el('rect', { x:x-16, y:y-16, width:32, height:32, rx:2, fill:sp.fill, stroke:sp.stroke, 'stroke-width':2 }));
        g.appendChild(el('path', { d:`M${x-16} ${y-16} L${x-8} ${y-8} H${x+16} M${x-8} ${y-8} V${y+16}`,
          fill:'none', stroke:sp.stroke, 'stroke-width':1, opacity:0.55 }));
      }
      host.appendChild(g);
    }

    function drawShapes(faded){
      const host = layer('c1-shapes');
      for(let i = 0; i < 12; i++) shapeGlyph(host, i, faded);
    }

    function drawPlayer(host, c, t, xy, isYou){
      { const layerHost = host; host = el('g', { class: 'player' + (isYou ? ' me' : (c === st.col ? ' related' : '')) }); layerHost.appendChild(host); }   // your shackled partner stays in view
      const [x, y] = xy, m = MARKERS[c];
      if(isYou){
        host.appendChild(el('circle', { cx:x, cy:y, r:R_BODY + 6, fill:'none', stroke:'var(--mist)', 'stroke-width':2.5, class:'pulse' }));
      }
      host.appendChild(el('circle', { cx:x, cy:y, r:R_BODY, fill:'rgba(10,9,22,0.92)',
        stroke: isYou ? 'var(--mist)' : 'var(--line-strong)', 'stroke-width': isYou ? 2 : 1.5 }));
      markerGlyph(host, m.id, x, y, 5.5, m.color, 2.2);
      const tag = el('text', { x:x + R_BODY + 1, y:y - R_BODY + 3, 'font-family':'Space Mono, monospace',
        'font-size':11, 'font-weight':700, fill: t === 'alpha' ? 'var(--astral-soft)' : 'var(--aether-soft)' });
      tag.textContent = TARGET[t].short;
      host.appendChild(tag);
      if(isYou){
        const you = el('text', { x, y:y + R_BODY + 15, 'text-anchor':'middle', 'font-family':'Space Mono, monospace',
          'font-size':10, 'font-weight':700, fill:'var(--mist)' });
        you.textContent = 'YOU';
        host.appendChild(you);
      }
    }

    // Everyone at once. `spotFor(c, t)` gives each player's position; yours can be overridden.
    function drawParty(spotFor, yours, shackles){
      const host = layer('c1-players');
      const under = document.getElementById('c1-under');
      for(let c = 0; c < 4; c++){
        const a = (c === st.col && st.t === 'alpha' && yours) ? yours : spotFor(c, 'alpha');
        const b = (c === st.col && st.t === 'beta'  && yours) ? yours : spotFor(c, 'beta');
        if(shackles){
          under.appendChild(el('line', { x1:a[0], y1:a[1], x2:b[0], y2:b[1], stroke:'var(--good)',
            'stroke-width':2, 'stroke-dasharray':'2 4', 'stroke-linecap':'round', opacity:0.8 }));
        }
      }
      for(let c = 0; c < 4; c++){
        ['alpha', 'beta'].forEach(t => {
          const mine = c === st.col && t === st.t;
          const xy = (mine && yours) ? yours : spotFor(c, t);
          if(!mine) drawPlayer(host, c, t, xy, false);
        });
      }
      drawPlayer(host, st.col, st.t, yours || spotFor(st.col, st.t), true);
    }

    function spotHits(spots, onPick){
      const host = layer('c1-hits');
      spots.forEach(s => {
        const [x, y] = s.xy;
        const g = el('g', {});
        g.appendChild(el('circle', { cx:x, cy:y, r:20, class:'focus-ring', fill:'none', stroke:'var(--mist)', 'stroke-width':2.5, opacity:0 }));
        g.appendChild(el('circle', { cx:x, cy:y, r:15, fill:'rgba(241,236,249,0.12)', stroke:'var(--mist)', 'stroke-width':2 }));
        hitable(g, onPick, s, s.label);
        host.appendChild(g);
      });
    }

    // Each red and yellow's tether to its blue. Blocked ones are solid; a missed one flickers.
    function drawTethers(missed){
      const host = layer('c1-over');
      ['red', 'yellow'].forEach(kind => {
        st.lay[kind].forEach((s, c) => {
          const p = cellXY(s), q = cellXY(st.lay.blues[c]);
          const miss = missed && missed.c === c && missed.kind === kind;
          host.appendChild(el('line', { x1:p[0], y1:p[1], x2:q[0], y2:q[1], stroke: miss ? 'var(--bad)' : SHAPE[kind].tether,
            'stroke-width': miss ? 4 : 3, 'stroke-linecap':'round', opacity: miss ? 1 : 0.8,
            'stroke-dasharray': miss ? '7 5' : 'none', class: miss ? 'stripe' : '' }));
        });
      });
    }

    function drawImplode(){
      const host = layer('c1-under');
      for(let i = 0; i < 12; i++){
        const [x, y] = cellXY(i);
        host.appendChild(el('circle', { cx:x, cy:y, r:R_IMPLODE, fill:'rgba(242,165,60,0.20)',
          stroke:'var(--shape-orange)', 'stroke-width':1.5, opacity:0.9 }));
      }
    }

    function drawBlades(host){
      ['west', 'east'].forEach(s => {
        const [x, y] = BLADE[s];
        host.appendChild(el('circle', { cx:x, cy:y, r:15, fill:'rgba(242,165,60,0.35)', stroke:'var(--shape-orange)',
          'stroke-width':2, filter:'url(#glow)' }));
        host.appendChild(el('path', { d:`M${x} ${y-10} L${x+4} ${y} L${x} ${y+10} L${x-4} ${y} Z`, fill:'var(--shape-orange)' }));
      });
    }

    // Cones from each tentacle at its four nearest players.
    function rayTargets(positions){
      const out = [];
      ['west', 'east'].forEach(s => {
        const [bx, by] = BLADE[s];
        positions.slice().sort((p, q) => Math.hypot(p.xy[0]-bx, p.xy[1]-by) - Math.hypot(q.xy[0]-bx, q.xy[1]-by))
          .slice(0, 4).forEach(p => out.push({ blade:s, angle: Math.atan2(p.xy[1]-by, p.xy[0]-bx), target:p }));
      });
      return out;
    }
    function coneHits(cone, xy){
      const [bx, by] = BLADE[cone.blade];
      const d = Math.hypot(xy[0]-bx, xy[1]-by);
      if(d > CONE_LEN) return false;
      let da = Math.atan2(xy[1]-by, xy[0]-bx) - cone.angle;
      while(da > Math.PI) da -= 2*Math.PI;
      while(da < -Math.PI) da += 2*Math.PI;
      return Math.abs(da) <= CONE_HALF + Math.atan2(R_BODY * 0.6, Math.max(d, 1));
    }
    function drawCones(cones){
      const host = layer('c1-under');
      const g = el('g', { 'clip-path':'url(#pallasClip)', 'pointer-events':'none' });
      cones.forEach(cn => {
        const [bx, by] = BLADE[cn.blade];
        const a1 = cn.angle - CONE_HALF, a2 = cn.angle + CONE_HALF;
        g.appendChild(el('path', { d:`M${bx} ${by} L${bx + Math.cos(a1)*CONE_LEN} ${by + Math.sin(a1)*CONE_LEN} L${bx + Math.cos(a2)*CONE_LEN} ${by + Math.sin(a2)*CONE_LEN} Z`,
          fill:'rgba(242,165,60,0.26)', stroke:'var(--shape-orange)', 'stroke-width':1.2 }));
      });
      host.appendChild(g);
    }

    function legend(){
      const host = document.getElementById('c1-legend');
      const row = (svg, html) => `<div class="legend-item">${svg}<span>${html}</span></div>`;
      const shapeSvg = kind => {
        const sp = SHAPE[kind];
        const inner = kind === 'blue' ? `<polygon points="12,2 20.7,7 20.7,17 12,22 3.3,17 3.3,7" fill="${sp.fill}" stroke="${sp.stroke}" stroke-width="1.6"/>`
          : kind === 'red' ? `<path d="M12 3 L21 19 L3 19 Z" fill="${sp.fill}" stroke="${sp.stroke}" stroke-width="1.6" stroke-linejoin="round"/>`
          : `<rect x="4" y="4" width="16" height="16" rx="1.5" fill="${sp.fill}" stroke="${sp.stroke}" stroke-width="1.6"/>`;
        return `<svg viewBox="0 0 24 24">${inner}</svg>`;
      };
      const markSvg = m => {
        const s = document.createElementNS(SVGNS, 'svg');
        s.setAttribute('viewBox', '0 0 24 24');
        markerGlyph(s, m.id, 12, 12, 6.5, m.color, 2.2);
        return s.outerHTML;
      };
      host.innerHTML =
        row(shapeSvg('blue'), '<b>Blue icosahedron</b> — Concept of Water, one per column')
        + row(shapeSvg('red'), '<b>Red pyramid</b> — Concept of Fire')
        + row(shapeSvg('yellow'), '<b>Yellow cube</b> — Concept of Earth')
        + row(`<img src="${TARGET.alpha.icon}" alt="">`, '<b>Alpha Target</b> — one in every shackled pair<span class="hint">; blocks a red pyramid</span>')
        + row(`<img src="${TARGET.beta.icon}" alt="">`, '<b>Beta Target</b> — the other in every shackled pair<span class="hint">; blocks a yellow cube</span>')
        + row('<img src="assets/shackled-together.png" alt="">', '<b>Shackled Together</b> — both die if you move too far from your partner')
        + MARKERS.map(m => row(markSvg(m), `<b>${m.name[0].toUpperCase() + m.name.slice(1)}</b>`)).join('');
    }

    /* ---------- render ---------- */
    function pill(t){ document.getElementById('c1-stepPill').textContent = t; }
    function instr(h){ document.getElementById('c1-instrText').innerHTML = h; }

    function renderHud(){
      const m = MARKERS[st.col], other = st.t === 'alpha' ? 'beta' : 'alpha';
      const box = layer('c1-mark');
      const s = el('svg', { viewBox:'0 0 34 34' });
      markerGlyph(s, m.id, 17, 17, 9, m.color, 3);
      box.appendChild(s);
      document.getElementById('c1-assignText').innerHTML =
        `You and the other <b>${m.name}</b> are shackled together. They hold <b>${TARGET[other].name}</b>.`;
      document.getElementById('c1-target').innerHTML =
        `<img src="${TARGET[st.t].icon}" alt=""><span>You hold <b>${TARGET[st.t].name}</b>.</span>`;
    }

    function render(){
      renderHud();
      ['c1-under', 'c1-shapes', 'c1-over', 'c1-players', 'c1-hits'].forEach(layer);
      fb.hidden = true;

      if(st.step === 1){
        pill('Step 1 · Block a tether');
        drawShapes(false);
        drawParty((c, t) => st.start[c][t], null, true);
        instr(`The shapes are about to tether. You are the <span class="hl">${MARKERS[st.col].name}</span> with <span class="hl">${TARGET[st.t].name}</span>. Click the spot you stand on to block your tether.<span class="hint"> Your marker picks the column, west to east <b>blue ✕, purple square, red circle, green triangle</b>; <b>Alpha</b> blocks a red pyramid beside your blue and <b>Beta</b> a yellow cube. If two of your colour touch it, take the one <b>no other blue can use</b>.</span>`);
        // Every gap between two neighbouring shapes is offered, tethered or not.
        const spots = [];
        for(let a = 0; a < 12; a++){
          neighbours(a).filter(b => b > a).forEach(b => {
            spots.push({ a, b, xy: mid(a, b),
              label:`Between the ${SHAPE[kindOf(a)].name} in column ${colOf(a)+1}, row ${rowOf(a)+1} and the ${SHAPE[kindOf(b)].name} ${where(a, b)}` });
          });
        }
        spotHits(spots, answerBlock);
        return;
      }

      if(st.step === 2){
        pill('Step 2 · Implode');
        drawShapes(false);
        drawImplode();
        drawParty(blockSpot, null, false);
        instr(`Your tether resolved and the shackles are gone. Every shape is about to <span class="hl">Implode</span>. Click where you wait out the Implode.<span class="hint"> Implode reaches 4 yalms around every shape, so wait in a <b>gap between four of them</b>, on the side you will bait the tentacles from.</span>`);
        const mine = blockSpot(st.col, st.t);
        const spots = [{ id:'stay', xy: mine, label:'Stay where you blocked your tether' }];
        [204, 300, 396].forEach(x => [156, 252].forEach(y => {
          spots.push({ id:`gap-${x}-${y}`, xy:[x, y], label:`Gap between columns ${COL_X.findIndex(cx => cx > x)} and ${COL_X.findIndex(cx => cx > x) + 1}, ${y < 200 ? 'north' : 'south'} of the middle row` });
        }));
        spots.push({ id:'west', xy:[84, 204], label:'Against the west wall' });
        spots.push({ id:'east', xy:[516, 204], label:'Against the east wall' });
        spots.push({ id:'south', xy:[300, 378], label:'South, below the shapes' });
        spotHits(spots, answerImplode);
        return;
      }

      pill('Step 3 · Palladian Ray');
      const over = layer('c1-over');
      drawBlades(over);
      drawParty((c, t) => {
        const w = waitSpot(c, t);
        return [w[0] + (c % 2 === 0 ? -14 : 14), w[1]];
      }, null, false);
      instr(`The shapes are gone and tentacles have struck the <span class="hl">west</span> and <span class="hl">east</span> of the floor.<span class="hint"> Each fires at its four nearest players.</span> Click the spot you bait from.<span class="hint"> Columns <b>1 and 2</b> bait the west tentacle and <b>3 and 4</b> the east, each in your own column, <b>Alpha</b> north of it and <b>Beta</b> south.</span>`);
      const spots = [];
      for(let c = 0; c < 4; c++){
        ['alpha', 'beta'].forEach(t => {
          spots.push({ c, t, xy: baitSpot(c, t),
            label:`Column ${c+1}, ${t === 'alpha' ? 'north' : 'south'} of the ${side(c)} tentacle` });
        });
      }
      spotHits(spots, answerRay);
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
      if(n > 3) return { label:'New pull ↻', fn: () => newRound() };
      return { label:'Continue → Step ' + n, fn: () => { st.step = n; render(); } };
    }

    function answerBlock(spot){
      lock();
      const c = st.col, kind = TARGET[st.t].kind, blue = st.lay.blues[c];
      const want = st.lay[kind][c];
      const pair = [spot.a, spot.b];
      const bluesIn = pair.filter(i => kindOf(i) === 'blue');
      const ok = pair.indexOf(blue) >= 0 && pair.indexOf(want) >= 0;

      layer('c1-hits');
      layer('c1-under');
      drawParty(blockSpot, spot.xy, false);
      drawTethers(ok ? null : { c, kind });

      const m = MARKERS[c];
      const candidates = neighbours(blue).filter(n => kindOf(n) === kind);
      let reason;
      if(candidates.length > 1){
        const alt = candidates.filter(n => n !== want);
        const owners = alt.map(a => {
          const oc = st.lay[kind].indexOf(a);
          const onlyOne = neighbours(st.lay.blues[oc]).filter(n => kindOf(n) === kind).length === 1;
          return `the one ${where(blue, a)} is ${onlyOne ? 'the only' : 'needed as the'} ${SHAPE[kind].name} ${onlyOne ? 'beside' : 'for'} column ${oc+1}'s blue`;
        });
        reason = `More than one ${SHAPE[kind].name} touches your blue, but ${owners.join(', and ')}. That leaves you the one <b>${where(blue, want)}</b>.`;
      } else {
        reason = `Only one ${SHAPE[kind].name} touches your blue, the one <b>${where(blue, want)}</b>.`;
      }
      const base = `As the <b>${m.name}</b> you take <b>column ${c+1}</b>, and <b>${TARGET[st.t].name}</b> blocks a <b>${SHAPE[kind].name}</b>.`;

      if(ok){
        judge(true, 'Tether blocked', `${base} ${reason} Your partner blocks the ${SHAPE[kind === 'red' ? 'yellow' : 'red'].name} on the same blue, so neither of you strains the shackle.`, stepTo(2));
        return;
      }
      let slip;
      const other = pair.find(i => i !== bluesIn[0]);
      if(bluesIn.length === 0){
        const ka = kindOf(spot.a), kb = kindOf(spot.b);
        slip = `No tether runs there. Reds and yellows only ever tether to a blue, so the gap between ${ka === kb ? `two ${SHAPE[ka].plural}` : `a ${SHAPE[ka].name} and a ${SHAPE[kb].name}`} never needs blocking.`;
      } else if(bluesIn.length === 2){
        slip = `No tether runs there. Two blue icosahedrons never tether to each other.`;
      } else if(bluesIn[0] !== blue){
        slip = `That spot is on <b>column ${colOf(bluesIn[0])+1}'s</b> blue. Markers take the columns west to east: blue ✕, purple square, red circle, green triangle.`;
      } else if(kindOf(other) !== kind){
        slip = `Right blue, wrong shape: that is a <b>${SHAPE[kindOf(other)].name}</b>, which is your partner's to block.`;
      } else {
        slip = `Right blue and right colour, but the wrong one of the two.`;
      }
      judge(false, 'Tether missed', `${slip} ${base} ${reason} The dashed tether is the one left unblocked.`, null);
    }

    function answerImplode(spot){
      lock();
      layer('c1-hits');
      const want = gapSpot(st.col, st.t);
      const ok = spot.xy[0] === want[0] && spot.xy[1] === want[1];
      const hit = inImplode(spot.xy);
      drawParty((c, t) => {
        const w = waitSpot(c, t);
        return [w[0] + (c % 2 === 0 ? -14 : 14), w[1]];
      }, spot.xy, false);

      const s = side(st.col), half = st.t === 'alpha' ? 'north' : 'south';
      const clean = `Implode covers 4 yalms around every shape, so the only clear ground inside the grid is the <b>gap between four shapes</b>. Columns ${st.col < 2 ? '1 and 2' : '3 and 4'} bait the <b>${s}</b> tentacle and ${TARGET[st.t].name} goes <b>${half}</b>, so you wait in the <b>${half}-${s}</b> gap, beside where that tentacle will land.`;

      if(ok){
        judge(true, 'Clear of Implode', clean, stepTo(3));
      } else if(hit){
        judge(false, 'Caught by Implode', `${spot.id === 'stay' ? 'Your blocking spot sits right between two shapes, inside both blasts.' : 'That spot is inside a shape’s blast.'} ${clean}`, null);
      } else if(spot.id === 'west' || spot.id === 'east' || spot.id === 'south'){
        judge(false, 'Safe, but out of position', `You would live, but that is too far out to be one of your tentacle's four nearest players. ${clean}`, null);
      } else {
        judge(false, 'Safe, but the wrong gap', `That gap survives Implode, but it is not where you bait from. ${clean}`, null);
      }
    }

    function answerRay(spot){
      lock();
      layer('c1-hits');
      const mine = spot.xy;
      const positions = [];
      for(let c = 0; c < 4; c++){
        ['alpha', 'beta'].forEach(t => {
          positions.push({ c, t, you: c === st.col && t === st.t, xy: (c === st.col && t === st.t) ? mine : baitSpot(c, t) });
        });
      }
      const cones = rayTargets(positions);
      drawCones(cones);
      const over = layer('c1-over');
      drawBlades(over);
      drawParty(baitSpot, mine, false);

      const hits = cones.filter(cn => coneHits(cn, mine)).length;
      const ok = spot.c === st.col && spot.t === st.t;
      const s = side(st.col), half = st.t === 'alpha' ? 'north' : 'south';
      const clean = `Columns ${st.col < 2 ? '1 and 2' : '3 and 4'} are the <b>${s}</b> tentacle's four nearest. Standing in your <b>own column</b>, ${TARGET[st.t].name} on the <b>${half}</b> side, spreads its four cones into an X with clear wedges between them, and none of them points across the middle at the other group.`;

      if(ok){
        judge(true, 'Classical Concepts cleared', `${clean} The cones linger, so once yours hits, <b>step sideways out of it</b> into a wedge. Then regroup in the middle for Ultima.`, stepTo(4));
      } else {
        // Who actually eats a second cone depends on which four each tentacle now picks.
        const owner = positions.find(p => !p.you && p.c === spot.c && p.t === spot.t);
        const doubled = positions.filter(p => cones.filter(cn => coneHits(cn, p.xy)).length > 1)
          .map(p => p.you ? 'you' : `the ${MARKERS[p.c].name} ${TARGET[p.t].name}`);
        const outcome = doubled.length
          ? `The cones now overlap and <b>${doubled.join(' and ')}</b> ${doubled.length === 1 && doubled[0] !== 'you' ? 'takes' : 'take'} a second hit, which kills.`
          : `The cones land out of their X and the wedges between them close up.`;
        judge(false, hits > 1 ? `Hit by ${hits} cones` : 'Wrong bait spot',
          `That is the <b>${MARKERS[owner.c].name}</b> ${TARGET[owner.t].name}'s spot. ${outcome} ${clean}`, null);
      }
    }

    legend();
    const newRound = T.trackRounds('classical1', startRound);
    newRound();
  }

  T.register({ id: 'classical1', label: 'Classical Concepts I', phase: 'Pallas Athena', markup: MARKUP, styles: STYLES, init: initClassical1 });
})(window.Twelfth);
