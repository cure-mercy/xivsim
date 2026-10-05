/* The Classical Concepts II: block your tether, follow Panta Rhei's half turn, bait Palladian Ray, then dodge Implode. */
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
  <div class="layout" id="panel-classical2" role="tabpanel" aria-labelledby="tabBtn-classical2" hidden>

    <section class="arena-wrap">
      <div class="step-row">
        <span class="step-pill" id="k2-stepPill">Step 1 · Block a tether</span>
      </div>

      <svg class="arena-svg" id="k2-arena" viewBox="48.8 21.8 502.4 422.4" role="img" aria-label="Top-down view of Pallas Athena's arena with the twelve Classical Concepts shapes">
        <rect x="60" y="60" width="480" height="360" rx="6" fill="url(#floor)" pointer-events="none"/>
        <image href="assets/arena-phase2.svg" x="60" y="60" width="480" height="360" preserveAspectRatio="none" pointer-events="none"/>
        <!-- the six tiles left after the southern row fell away -->
        <g stroke="var(--line)" stroke-width="1.5" pointer-events="none">
          <line x1="300" y1="60" x2="300" y2="420"/>
          <line x1="60" y1="180" x2="540" y2="180"/>
          <line x1="60" y1="300" x2="540" y2="300"/>
        </g>
        <g id="k2-labels" font-family="Space Mono, monospace" font-size="12" fill="var(--mist-faint)" text-anchor="middle" pointer-events="none">
          <text x="156" y="46">COL 1</text>
          <text x="252" y="46">COL 2</text>
          <text x="348" y="46">COL 3</text>
          <text x="444" y="46">COL 4</text>
        </g>

        <g id="k2-under"></g>
        <g id="k2-shapes"></g>
        <g id="k2-over"></g>
        <g id="k2-players"></g>
        <g id="k2-hits"></g>

        <rect x="60" y="60" width="480" height="360" rx="6" fill="none" stroke="rgba(247,147,30,0.55)" stroke-width="2" filter="url(#glow)" pointer-events="none"/>
      </svg>

      <p class="arena-caption">North is up and columns count from the west. The shapes sit 8 yalms apart; Implode reaches 4 yalms around each.</p>

      <div class="feedback" id="k2-feedback" hidden aria-live="polite"></div>
    </section>

    <aside class="hud">
      <div class="card">
        <h2>Your marker</h2>
        <div class="lc-row">
          <div class="cc-mark" id="k2-mark"></div>
          <p class="assign-text" id="k2-assignText"></p>
        </div>
        <div class="cc-target" id="k2-target"></div>
      </div>

      <div class="card">
        <h2>Objective</h2>
        <p class="instr-text" id="k2-instrText"></p>
      </div>

      <details class="card">
        <summary>How the call works</summary>
        <ol>
          <li>It opens exactly like the first Classical Concepts: a marker and <b>Alpha</b> or <b>Beta Target</b> for everyone, shackled pairs, and twelve shapes in four columns of three.</li>
          <li>Solve it the same way. Your marker picks the column, west to east <b>blue ✕, purple square, red circle, green triangle</b>. <b>Alpha</b> blocks a <b>red pyramid</b> beside your blue, <b>Beta</b> a <b>yellow cube</b>, and if two touch it, take the one no other blue can use.</li>
          <li><b>Panta Rhei</b> then makes every shape vanish and reappear turned a <b>half turn</b> around the middle of the grid, mirrored north to south and west to east at once. The tethers resolve on the new positions.</li>
          <li>So walk to your spot's <b>mirror image</b>, slowly and together with your partner so the shackle holds. Icy Veins' shortcut is to solve the <b>opposite</b> column's blue and mirror that into your own column.</li>
          <li><b>Palladian Ray</b> is baited like the first time, columns 1–2 west and 3–4 east, Alpha north and Beta south, but Panta Rhei has mirrored every pair, so the column order is <b>reversed</b>: west to east <b>green triangle, red circle, purple square, blue ✕</b>.</li>
          <li>This time the shapes <b>Implode after the cones</b> go off. Step out of your cone to ground that is clear of every lingering cone and 4 yalms from every shape.</li>
        </ol>
      </details>

      <div class="card">
        <h2>Legend</h2>
        <div class="legend-list" id="k2-legend"></div>
      </div>
    </aside>

  </div>
  `;

  function initClassical2(){
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
    // Panta Rhei turns the grid a half turn about its middle, (300, 204): cell i moves to 11 - i.
    const GRID_MID = [300, 204];
    function rot(xy){ return [2 * GRID_MID[0] - xy[0], 2 * GRID_MID[1] - xy[1]]; }
    function rotatedSpot(c, t){ return rot(blockSpot(c, t)); }
    const same = (p, q) => Math.hypot(p[0] - q[0], p[1] - q[1]) < 1;
    // After Panta Rhei every pair stands mirrored across the grid, so the bait order is reversed:
    // west to east green triangle, red circle, purple square, blue ✕.
    const baitCol = c => 3 - c;
    function baitSpot(c, t){ return [COL_X[baitCol(c)], 180 + (t === 'alpha' ? -BAIT_DY : BAIT_DY)]; }
    function inImplode(xy){
      for(let i = 0; i < 12; i++){
        const p = cellXY(i);
        if(Math.hypot(xy[0] - p[0], xy[1] - p[1]) < R_IMPLODE + 6) return true;
      }
      return false;
    }

    let st = {};
    const fb = document.getElementById('k2-feedback');

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
      document.querySelectorAll('#panel-classical2 .hit').forEach(h => h.setAttribute('aria-disabled', 'true'));
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

    function shapeGlyph(host, i, faded, turned){
      const [x, y] = turned ? rot(cellXY(i)) : cellXY(i);
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

    function drawShapes(faded, turned){
      const host = layer('k2-shapes');
      for(let i = 0; i < 12; i++) shapeGlyph(host, i, faded, turned);
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
      const host = layer('k2-players');
      const under = document.getElementById('k2-under');
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
      const host = layer('k2-hits');
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
    function drawTethers(missed, turned){
      const host = layer('k2-over');
      ['red', 'yellow'].forEach(kind => {
        st.lay[kind].forEach((s, c) => {
          const p = turned ? rot(cellXY(s)) : cellXY(s), q = turned ? rot(cellXY(st.lay.blues[c])) : cellXY(st.lay.blues[c]);
          const miss = missed && missed.c === c && missed.kind === kind;
          host.appendChild(el('line', { x1:p[0], y1:p[1], x2:q[0], y2:q[1], stroke: miss ? 'var(--bad)' : SHAPE[kind].tether,
            'stroke-width': miss ? 4 : 3, 'stroke-linecap':'round', opacity: miss ? 1 : 0.8,
            'stroke-dasharray': miss ? '7 5' : 'none', class: miss ? 'stripe' : '' }));
        });
      });
    }

    function drawImplode(host){
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
      const host = document.getElementById('k2-under');
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
      const host = document.getElementById('k2-legend');
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
    function pill(t){ document.getElementById('k2-stepPill').textContent = t; }
    function instr(h){ document.getElementById('k2-instrText').innerHTML = h; }

    function renderHud(){
      const m = MARKERS[st.col], other = st.t === 'alpha' ? 'beta' : 'alpha';
      const box = layer('k2-mark');
      const s = el('svg', { viewBox:'0 0 34 34' });
      markerGlyph(s, m.id, 17, 17, 9, m.color, 3);
      box.appendChild(s);
      document.getElementById('k2-assignText').innerHTML =
        `You and the other <b>${m.name}</b> are shackled together. They hold <b>${TARGET[other].name}</b>.`;
      document.getElementById('k2-target').innerHTML =
        `<img src="${TARGET[st.t].icon}" alt=""><span>You hold <b>${TARGET[st.t].name}</b>.</span>`;
    }

    function render(){
      renderHud();
      ['k2-under', 'k2-shapes', 'k2-over', 'k2-players', 'k2-hits'].forEach(layer);
      fb.hidden = true;

      if(st.step === 1){
        pill('Step 1 · Block a tether');
        drawShapes(false);
        drawParty((c, t) => st.start[c][t], null, true);
        instr(`The shapes are about to tether. You are the <span class="hl">${MARKERS[st.col].name}</span> with <span class="hl">${TARGET[st.t].name}</span>. Click the spot you stand on to block your tether.<span class="hint"> Same read as the first time: your marker picks the column, <b>Alpha</b> blocks a red pyramid and <b>Beta</b> a yellow cube, and if two touch your blue, take the one <b>no other blue can use</b>.</span>`);
        spotHits(edgeSpots(), answerBlock);
        return;
      }

      if(st.step === 2){
        pill('Step 2 · Panta Rhei');
        // the shapes have not turned yet: you have to move to where your tether will be
        drawShapes(false);
        drawParty(blockSpot, null, true);
        instr(`<span class="hl">Panta Rhei</span> is casting, and the tethers resolve after it. Click where you move now, together with your partner.<span class="hint"> When it finishes, every shape is turned a <b>half turn</b> around the middle of the grid, which sends it to its <b>mirror image</b>, so walk to the mirror of the spot you are blocking now.</span>`);
        spotHits(edgeSpots(), answerTurn);
        return;
      }

      if(st.step === 3){
        pill('Step 3 · Palladian Ray');
        drawShapes(true, true);
        drawBlades(layer('k2-over'));
        drawParty(rotatedSpot, null, false);
        instr(`The tethers resolved and tentacles have struck the <span class="hl">west</span> and <span class="hl">east</span> of the floor, with the shapes still standing. Click the spot you bait from.<span class="hint"> Panta Rhei mirrored the party, so the bait order is <b>reversed</b>: west to east green triangle, red circle, purple square, blue ✕. <b>Alpha</b> baits north of its tentacle, <b>Beta</b> south.</span>`);
        const spots = [];
        for(let bc = 0; bc < 4; bc++){
          const c = 3 - bc;
          ['alpha', 'beta'].forEach(t => spots.push({ c, t, xy: baitSpot(c, t), label:`Column ${bc+1}, ${t === 'alpha' ? 'north' : 'south'} of the ${side(bc)} tentacle` }));
        }
        spotHits(spots, answerRay);
        return;
      }

      pill('Step 4 · Implode');
      drawShapes(false, true);
      drawCones(st.cones);
      drawBlades(layer('k2-over'));
      drawParty(baitSpot, null, false);
      instr(`The cones have hit and are lingering, and now every shape is about to <span class="hl">Implode</span>. Click where you step to before the Implode.<span class="hint"> The cones linger where they landed and every shape bursts 4 yalms around itself, so take a <b>gap no cone crosses</b> or the floor's edge away from them.</span>`);
      spotHits(dodgeSpots(), answerDodge);
    }

    // Every gap between two neighbouring shapes: the same set before and after the half turn.
    function edgeSpots(){
      const spots = [];
      for(let a = 0; a < 12; a++){
        neighbours(a).filter(b => b > a).forEach(b => spots.push({ a, b, xy: mid(a, b), label:`Gap ${spots.length + 1} between two shapes` }));
      }
      return spots;
    }

    // Where you might step once the cones land: the gaps inside the grid, the edges, between two shapes,
    // and staying put. The Implode circles only appear once you have picked.
    function dodgeSpots(){
      const spots = [{ id:'stay', xy: baitSpot(st.col, st.t), label:'Stay where you baited' }];
      [204, 300, 396].forEach(x => [156, 252].forEach(y => spots.push({ id:'gap', xy:[x, y], label:'Gap between four shapes' })));
      [[84, 156], [84, 252], [516, 156], [516, 252], [300, 378], [300, 76]].forEach(xy =>
        spots.push({ id:'edge', xy, label:'Out by the edge' }));
      // clear of every cone, but between two shapes of the bottom row and so inside their Implode
      [[204, 300], [396, 300]].forEach(xy => spots.push({ id:'row', xy, label:'Between two shapes' }));
      return spots;
    }
    function dodgeCheck(xy){
      const cone = st.cones.find(cn => coneHits(cn, xy));
      if(cone) return { ok:false, why:'cone', cone };
      for(let i = 0; i < 12; i++){
        const p = rot(cellXY(i));
        if(Math.hypot(xy[0] - p[0], xy[1] - p[1]) < R_IMPLODE + 6) return { ok:false, why:'implode' };
      }
      return { ok:true };
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
      if(n > 4) return { label:'New pull ↻', fn: () => newRound() };
      return { label:'Continue → Step ' + n, fn: () => { st.step = n; render(); } };
    }

    function blockReason(){
      const c = st.col, kind = TARGET[st.t].kind, blue = st.lay.blues[c], want = st.lay[kind][c];
      const candidates = neighbours(blue).filter(n => kindOf(n) === kind);
      if(candidates.length > 1){
        const owners = candidates.filter(n => n !== want).map(a => {
          const oc = st.lay[kind].indexOf(a);
          const onlyOne = neighbours(st.lay.blues[oc]).filter(n => kindOf(n) === kind).length === 1;
          return `the one ${where(blue, a)} is ${onlyOne ? 'the only' : 'needed as the'} ${SHAPE[kind].name} ${onlyOne ? 'beside' : 'for'} column ${oc+1}'s blue`;
        });
        return `More than one ${SHAPE[kind].name} touches your blue, but ${owners.join(', and ')}. That leaves you the one <b>${where(blue, want)}</b>.`;
      }
      return `Only one ${SHAPE[kind].name} touches your blue, the one <b>${where(blue, want)}</b>.`;
    }

    function answerBlock(spot){
      lock();
      const c = st.col, kind = TARGET[st.t].kind, blue = st.lay.blues[c];
      const want = st.lay[kind][c];
      const pair = [spot.a, spot.b];
      const bluesIn = pair.filter(i => kindOf(i) === 'blue');
      const ok = pair.indexOf(blue) >= 0 && pair.indexOf(want) >= 0;
      layer('k2-hits');
      layer('k2-under');
      drawParty(blockSpot, spot.xy, true);
      const m = MARKERS[c];
      const base = `As the <b>${m.name}</b> you take <b>column ${c+1}</b>, and <b>${TARGET[st.t].name}</b> blocks a <b>${SHAPE[kind].name}</b>. ${blockReason()}`;
      if(ok){
        judge(true, 'Found your tether', `${base} Remember this spot: Panta Rhei is coming, and the shapes will not stay put.`, stepTo(2));
        return;
      }
      let slip;
      const other = pair.find(i => i !== bluesIn[0]);
      if(bluesIn.length === 0) slip = `No tether runs there: reds and yellows only ever tether to a blue.`;
      else if(bluesIn.length === 2) slip = `No tether runs there: two blue icosahedrons never tether to each other.`;
      else if(bluesIn[0] !== blue) slip = `That spot is on <b>column ${colOf(bluesIn[0])+1}'s</b> blue.`;
      else if(kindOf(other) !== kind) slip = `Right blue, wrong shape: that is a <b>${SHAPE[kindOf(other)].name}</b>, your partner's to block.`;
      else slip = `Right blue and right colour, but the wrong one of the two.`;
      drawTethers({ c, kind });
      judge(false, 'Not your tether', `${slip} ${base}`, null);
    }

    function answerTurn(spot){
      lock();
      layer('k2-hits');
      const from = blockSpot(st.col, st.t), want = rotatedSpot(st.col, st.t);
      const ok = same(spot.xy, want);
      const kind = TARGET[st.t].kind;
      layer('k2-under');
      drawShapes(false, true);
      drawTethers(ok ? null : { c: st.col, kind }, true);
      drawParty(rotatedSpot, ok ? null : spot.xy, true);
      const newCol = 4 - st.col;
      const rule = `Panta Rhei turns the whole grid a <b>half turn</b> about its middle, so every shape, and every tether, ends up mirrored north to south <b>and</b> west to east. Your tether is now in <b>column ${newCol}</b>, on the far side of the grid from where you blocked it, and you walk there together with your partner so the shackle holds. Icy Veins' shortcut is to solve column ${newCol}'s blue from the start and mirror that into your own column.`;
      let why;
      if(ok) why = rule;
      else if(same(spot.xy, from)) why = `That is where your tether was <b>before</b> Panta Rhei. The shapes have moved on, so staying there blocks nothing. ${rule}`;
      else if(same(spot.xy, [2 * GRID_MID[0] - from[0], from[1]]) || same(spot.xy, [from[0], 2 * GRID_MID[1] - from[1]])) why = `That mirrors your spot only one way. ${rule}`;
      else why = `That is not where your tether went. ${rule}`;
      judge(ok, ok ? 'Tether blocked' : 'Missed the turn', why, stepTo(3));
    }

    function answerRay(spot){
      lock();
      layer('k2-hits');
      const positions = [];
      for(let c = 0; c < 4; c++){
        ['alpha', 'beta'].forEach(t => positions.push({ c, t, you: c === st.col && t === st.t, xy: (c === st.col && t === st.t) ? spot.xy : baitSpot(c, t) }));
      }
      const cones = rayTargets(positions);
      layer('k2-under');
      drawCones(cones);
      drawBlades(layer('k2-over'));
      drawParty(baitSpot, spot.xy, false);
      const ok = spot.c === st.col && spot.t === st.t;
      const bc = baitCol(st.col), s = side(bc), half = st.t === 'alpha' ? 'north' : 'south';
      const clean = `Panta Rhei mirrored every pair across the grid, so the bait order is <b>reversed</b>: west to east <b>green triangle, red circle, purple square, blue ✕</b>. As the ${MARKERS[st.col].name} you bait from <b>column ${bc + 1}</b>, one of the <b>${s}</b> tentacle's four nearest, ${TARGET[st.t].name} on the <b>${half}</b> side. That fans the cones into an X with clear wedges, none pointing across the middle.`;
      if(ok){
        st.cones = cones;
        judge(true, 'Cone baited', `${clean} The cones linger, and this time the shapes are still standing.`, stepTo(4));
      } else {
        const owner = positions.find(p => !p.you && p.c === spot.c && p.t === spot.t);
        const doubled = positions.filter(p => cones.filter(cn => coneHits(cn, p.xy)).length > 1).map(p => p.you ? 'you' : `the ${MARKERS[p.c].name} ${TARGET[p.t].name}`);
        const outcome = doubled.length ? `The cones overlap and <b>${doubled.join(' and ')}</b> ${doubled.length === 1 && doubled[0] !== 'you' ? 'takes' : 'take'} a second hit.` : `The cones land out of their X.`;
        judge(false, 'Wrong bait spot', `That is the <b>${MARKERS[owner.c].name}</b> ${TARGET[owner.t].name}'s spot. ${outcome} ${clean}`, null);
      }
    }

    function answerDodge(spot){
      lock();
      layer('k2-hits');
      const res = dodgeCheck(spot.xy);
      const under = layer('k2-under');
      drawCones(st.cones);
      drawImplode(under);
      drawBlades(layer('k2-over'));
      drawParty(baitSpot, spot.xy, false);
      const rule = `The cones linger where they landed, and every shape Implodes 4 yalms around itself right after. The ground that stays clear is the gaps between shapes that no cone crosses, and the edges of the floor away from the cones.`;
      let why, title;
      if(res.ok){
        title = 'Classical Concepts II cleared';
        why = `${spot.id === 'stay' ? '' : 'Clear of every cone and every shape. '}${rule} Then regroup for Ultima and Crush Helm.`;
      } else if(res.why === 'cone'){
        const t = res.cone.target;
        title = 'Still in a cone';
        why = `${spot.id === 'stay' ? 'Your own cone lingers where you baited it.' : `That spot is inside ${t.you ? 'your own' : `the ${MARKERS[t.c].name} ${TARGET[t.t].name}'s`} lingering cone.`} ${rule}`;
      } else {
        title = 'Caught by Implode';
        why = `That spot is within 4 yalms of a shape. ${rule}`;
      }
      judge(res.ok, title, why, stepTo(5));
    }

    legend();
    const newRound = T.trackRounds('classical2', startRound);
    newRound();
  }

  T.register({ id: 'classical2', label: 'Classical Concepts II', phase: 'Pallas Athena', markup: MARKUP, styles: STYLES, init: initClassical2 });
})(window.Twelfth);
