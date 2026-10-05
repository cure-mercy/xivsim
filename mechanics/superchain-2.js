/* Superchain Theory II: IIA with Trinity of Souls, then IIB with Parthenos and the dives. */
(function(T){

  const { shared, showFeedback } = T;

  const STYLES = /* css */ `
    .lc-num.sm{ font-size: 1.02rem; letter-spacing: 0.04em; }
    .wing-panel{ display: flex; flex-direction: column; gap: 4px; }
    .wing-svg{ width: 100%; height: auto; display: block; }
    .wing-caption{ margin: 0; font-size: 0.76rem; color: var(--mist-faint); text-align: center; }
    .wing-caption b{ color: var(--mist-dim); font-weight: 600; }
  `;

  const MARKUP = /* html */ `
  <div class="layout" id="panel-superchain2" role="tabpanel" aria-labelledby="tabBtn-superchain2" hidden>

    <section class="arena-wrap">
      <div class="step-row">
        <span class="step-pill" id="p5-stepPill">Step 1 · First cluster</span>
      </div>

      <div class="wing-panel" id="p5-wingPanel" hidden>
        <svg class="wing-svg" id="p5-wingArt" viewBox="0 0 600 142" role="img"
             aria-label="Athena's three wing pairs, showing which side glows for each cleave"></svg>
        <p class="wing-caption">Wings light <b>bottom to top</b>.</p>
      </div>

      <svg class="arena-svg" id="p5-arena" style="--zone-band: 23.09%" viewBox="48.8 18.8 502.4 648.4" role="img" aria-label="Top-down view of the Twelfth Circle arena during Superchain Theory II">
        <defs>
          <!-- the adds' column AoE is untelegraphed: only a quick fade off the north edge hints at it -->
          <linearGradient id="p5-addFade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#e2523f" stop-opacity="0.42"/>
            <stop offset="0.07" stop-color="#e2523f" stop-opacity="0.14"/>
            <stop offset="0.2" stop-color="#e2523f" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <rect x="60" y="60" width="480" height="480" rx="6" fill="url(#floor)" pointer-events="none"/>
        <image href="assets/arena-phase1.svg" x="60" y="60" width="480" height="480" preserveAspectRatio="none" pointer-events="none"/>
        <!-- Athena's target circle: one column width in radius, as in Paradeigma II -->
        <circle cx="300" cy="300" r="120" fill="none" stroke="rgba(247,147,30,0.45)" stroke-width="1.6" stroke-dasharray="4 6" pointer-events="none"/>
        <g opacity="0.4" pointer-events="none">
          <g transform="translate(300,300)" fill="var(--aether)">
            <path d="M0 -18 L5 -5 L18 0 L5 5 L0 18 L-5 5 L-18 0 L-5 -5 Z"/>
          </g>
        </g>

        <g id="p5-tiles"></g>
        <g id="p5-chains"></g>
        <g id="p5-hits"></g>
        <g id="p5-zones"></g>

        <rect x="60" y="60" width="480" height="480" rx="6" fill="none" stroke="rgba(247,147,30,0.55)" stroke-width="2" filter="url(#glow)" pointer-events="none"/>
      </svg>

      <p class="arena-caption" id="p5-caption">Clusters appear in waves, so earlier ones fade once they have fired.</p>

      <div class="feedback" id="p5-feedback" hidden aria-live="polite"></div>
    </section>

    <aside class="hud">
      <div class="card">
        <h2>Objective</h2>
        <p class="instr-text" id="p5-instrText"></p>
      </div>

      <details class="card">
        <summary>How the call works</summary>
        <ol>
          <li><b>Superchain Theory IIA</b> puts three clusters on the north, middle and south. The middle one always fires a green orb, then a donut, then a green orb, so the middle is <b>out, in, out</b>.</li>
          <li>North and south carry two shapes each: one short green orb, one long green orb, one <b>short purple jack</b>, and one long spiked shape that is orange or purple. Start at the cluster with the short purple jack and <b>pair up</b> there, staying clear of the middle: pairs line up from the <b>arena centre outwards</b>: <b>T1 and M1</b> nearest the centre, then <b>T2 and M2</b>, <b>H1 and R1</b>, and <b>H2 and R2</b> furthest out.</li>
          <li>Move into the middle for the donut, then finish at whichever cluster holds the <b>long spiked shape</b>. If your first cluster's long chain was green you run straight through to the far one; if it was orange or purple you come back. <b>Orange spreads, purple pairs.</b></li>
          <li><b>Trinity of Souls</b> runs alongside it. Three wings glow in order, each marking the half of the room it will cleave. Because IIA always glows bottom to top, Athena spins 180° between cleaves, so the <b>second</b> cleave lands on the half <b>opposite</b> its wing while the first and third land on theirs. Lit bottom to top, the pattern never makes you switch halves twice. Take every position on the safe half.</li>
          <li><b>Superchain Theory IIB</b> spawns in waves. Two clusters inside the middle first, one donut and one green orb: start <b>in the donut</b>.</li>
          <li>Then east and west, one green orb and one spiked shape. Go to the <b>spiked</b> side and resolve it there. <b>Parthenos</b> fires as you leave: an untelegraphed line aimed at the tank holding Athena, who baits it exactly <b>north to south</b> so it runs straight down her hitbox and covers the middle of the floor, knocking back anyone still in it. The red Paradeigma adds' columns follow afterwards.</li>
          <li>Last, north and south on long chains. One holds a lone green orb, the other a <b>green orb and an orange spiked ball</b> — go to that one and resolve <b>out and spread</b>. <b>Unnatural Enchainment</b> destroys seven tiles, and the survivor is always one of the four beside that final cluster.</li>
        </ol>
      </details>

      <div class="card">
        <h2>Shapes</h2>
        <div class="legend-list">
          <div class="legend-item"><svg viewBox="0 0 24 24" fill="var(--good)"><use href="#icon-orb"/></svg><span><b>Green orb</b> — point-blank<span class="hint">, stay out</span></span></div>
          <div class="legend-item"><svg viewBox="0 0 24 24" fill="none" stroke="var(--umbral-soft)"><use href="#icon-donut"/></svg><span><b>Blue donut</b> — ring<span class="hint">, get in close</span></span></div>
          <div class="legend-item"><svg viewBox="0 0 24 24" fill="var(--shape-orange)"><use href="#icon-add"/></svg><span><b>Orange spiked ball</b> — cones everyone<span class="hint">, spread</span></span></div>
          <div class="legend-item"><svg viewBox="0 0 24 24" fill="var(--shape-purple)"><use href="#icon-jack"/></svg><span><b>Purple jack</b> — cones one role<span class="hint">, pair up</span></span></div>
        </div>
      </div>
    </aside>

  </div>
  `;

  function initSuperchain2(){
    const SVGNS = 'http://www.w3.org/2000/svg';
    const RAD = Math.PI / 180;

    const SHAPE = {
      orb:    { icon:'#icon-orb',   color:'var(--good)',         label:'green orb' },
      donut:  { icon:'#icon-donut', color:'var(--umbral-soft)',  label:'blue donut' },
      orange: { icon:'#icon-add',   color:'var(--shape-orange)', label:'orange spiked ball' },
      purple: { icon:'#icon-jack',  color:'var(--shape-purple)', label:'purple jack' }
    };

    const A_POS = { N:[300,185], M:[300,300], S:[300,415] };
    const B_POS = { iN:[300,235], iS:[300,365], E:[430,300], W:[170,300], oN:[300,150], oS:[300,450] };
    const A_NAME = { N:'north', M:'middle', S:'south' };
    const B_NAME = { iN:'inner north', iS:'inner south', E:'east', W:'west', oN:'north', oS:'south' };

    // Fan directions for each cluster's chains, in screen degrees.
    const A_FAN = { N:[-135,-45], M:[160,180,200], S:[135,45] };
    const B_FAN = { iN:[-90], iS:[90], E:[0], W:[180], oN:[-133,-47], oS:[133,47] };

    const COLX = { L:180, R:420 }, ROWY = { 1:120, 2:240, 3:360, 4:480 };

    // Vertical bands, one per cluster row, split west and east by the cleave line.
    const BAND = { N:[60,242], M:[243,357], S:[358,540] };
    const HALF_NAME = { W:'west', E:'east' };
    // Trinity of Souls glows bottom to top in this set, so Athena spins 180° between cleaves:
    // the second one lands on the half opposite its wing, the first and third on theirs.
    const CLEAVE_FLIP = [false, true, false];

    // The first shapes: pairs line up north to south beside the first cluster, on the safe half.
    const PAIR_OF = { T1:0, M1:0, T2:1, M2:1, H1:2, R1:2, H2:3, R2:3 };
    const PAIR_NAME = ['T1 and M1', 'T2 and M2', 'H1 and R1', 'H2 and R2'];
    // Eight spots around the first cluster, between the shapes' diagonals. The four on the half the first
    // cleave spares are the pair spots, taken north to south.
    const PAIR_R = 80;

    let st = {};
    const fb = document.getElementById('p5-feedback');

    function other(side){ return side === 'N' ? 'S' : 'N'; }
    function otherHalf(h){ return h === 'W' ? 'E' : 'W'; }

    function genA(){
      {
        st.firstSide  = Math.random() < 0.5 ? 'N' : 'S';
        st.returnToFirst = Math.random() < 0.5;
        st.finalSide  = st.returnToFirst ? st.firstSide : other(st.firstSide);
        st.finalShape = Math.random() < 0.5 ? 'orange' : 'purple';
        // Four shapes across north and south: short green orb, long green orb,
        // short purple jack, and the long spiked shape that decides the finish.
        st.shapes = {};
        st.shapes[st.firstSide] = [
          { s:'purple', len:'short' },
          { s: st.returnToFirst ? st.finalShape : 'orb', len:'long' }
        ];
        st.shapes[other(st.firstSide)] = [
          { s:'orb', len:'short' },
          { s: st.returnToFirst ? 'orb' : st.finalShape, len:'long' }
        ];
        st.shapes.M = [{ s:'orb', len:'short' }, { s:'donut', len:'medium' }, { s:'orb', len:'long' }];

        // Trinity of Souls: three wings glow in order, each marking the half it cleaves. Lighting bottom to
        // top, the game never makes you switch halves twice, which leaves six safe-half patterns, each
        // equally likely.
        const SAFE = ['WWW', 'EEE', 'WEE', 'EWW', 'WWE', 'EEW'];
        st.safeHalf = [...SAFE[Math.floor(Math.random() * SAFE.length)]];
        st.cleave = st.safeHalf.map(otherHalf);
        st.wings  = st.cleave.map((c, i) => CLEAVE_FLIP[i] ? otherHalf(c) : c);
        st.aCluster = [st.firstSide, 'M', st.finalSide];
        st.wingsLit = true;   // the glow goes out once she starts cleaving
      }
    }

    function genB(){
      {
        st.donutSide = Math.random() < 0.5 ? 'N' : 'S';
        st.spikeSide = Math.random() < 0.5 ? 'E' : 'W';
        st.spikeShape = Math.random() < 0.5 ? 'orange' : 'purple';
        st.finalSide = Math.random() < 0.5 ? 'N' : 'S';
        const rows = st.finalSide === 'N' ? [1,2] : [3,4];
        st.safeTile = rows[Math.floor(Math.random()*2)] + (Math.random() < 0.5 ? 'L' : 'R');
        st.shapes = {};
        st.shapes['i' + st.donutSide] = [{ s:'donut', len:'short' }];
        st.shapes['i' + other(st.donutSide)] = [{ s:'orb', len:'short' }];
        st.shapes[st.spikeSide] = [{ s:st.spikeShape, len:'medium' }];
        st.shapes[st.spikeSide === 'E' ? 'W' : 'E'] = [{ s:'orb', len:'medium' }];
        st.shapes['o' + st.finalSide] = [{ s:'orb', len:'long' }, { s:'orange', len:'long' }];
        st.shapes['o' + other(st.finalSide)] = [{ s:'orb', len:'long' }];
        // Two red-crystal adds sit north and fire down their own columns, as in Paradeigma II: the floor's
        // four 120-wide columns, with the adds over the first and third or the second and fourth.
        st.diveCols = Math.random() < 0.5 ? [120, 360] : [240, 480];
      }
    }

    const DIVE_HALF = 60;

    // Walk the band edges to get the lanes across the floor, flagged safe or lethal.
    function diveLanes(){
      const edges = [60, 540];
      st.diveCols.forEach(c => {
        edges.push(Math.max(60, c - DIVE_HALF), Math.min(540, c + DIVE_HALF));
      });
      const cuts = [...new Set(edges)].sort((a, b) => a - b);
      const lanes = [];
      for(let i = 0; i < cuts.length - 1; i++){
        const a = cuts[i], b = cuts[i+1];
        if(b - a < 6) continue;
        const mid = (a + b) / 2;
        lanes.push({ x:a, w:b - a, danger: st.diveCols.some(c => Math.abs(mid - c) < DIVE_HALF) });
      }
      return lanes;
    }

    // A pull always runs IIA and then IIB, the order the fight uses.
    function startRound(){ genA(); st.set = 'A'; st.step = 1; render(); }
    function toB(){ genB(); st.set = 'B'; st.step = 1; render(); }

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
      document.querySelectorAll('#panel-superchain2 .hit').forEach(h => h.setAttribute('aria-disabled','true'));
    }

    const LEN = { short:62, medium:82, long:104 };

    function drawCluster(host, key, opts){
      opts = opts || {};
      const posMap = st.set === 'A' ? A_POS : B_POS;
      const fanMap = st.set === 'A' ? A_FAN : B_FAN;
      const [cx, cy] = posMap[key];
      const g = el('g', { opacity: opts.dim ? 0.3 : 1 });

      (st.shapes[key] || []).forEach((sh, i) => {
        const fan = fanMap[key];
        const ang = (i < fan.length ? fan[i] : fan[fan.length - 1]) * RAD;
        const len = LEN[sh.len];
        const sx = cx + Math.cos(ang)*len, sy = cy + Math.sin(ang)*len;
        const s = SHAPE[sh.s];
        g.appendChild(el('line', { x1:cx, y1:cy, x2:sx, y2:sy, stroke:'rgba(160,180,255,0.45)',
          'stroke-width':2, 'stroke-dasharray':'5 4' }));
        g.appendChild(el('circle', { cx:sx, cy:sy, r:14, fill:'rgba(10,9,22,0.85)',
          stroke:s.color, 'stroke-width':1.5 }));
        const u = el('use', { href:s.icon, x:sx-12, y:sy-12 });
        u.style.color = s.color;
        g.appendChild(u);
      });

      if(opts.highlight){
        g.appendChild(el('circle', { cx, cy, r:27, fill:'none', stroke:'var(--aether)',
          'stroke-width':2.5, class:'pulse' }));
      }
      g.appendChild(el('circle', { cx, cy, r:15, fill:'var(--umbral)', opacity:0.35 }));
      g.appendChild(el('circle', { cx, cy, r:15, fill:'none', stroke:'var(--umbral-soft)', 'stroke-width':2 }));
      host.appendChild(g);
    }

    function clusterHits(keys, onPick){
      const host = layer('p5-hits');
      const posMap = st.set === 'A' ? A_POS : B_POS;
      const nameMap = st.set === 'A' ? A_NAME : B_NAME;
      keys.forEach(k => {
        const [cx, cy] = posMap[k];
        const g = el('g', {});
        g.appendChild(el('circle', { cx, cy, r:33, class:'focus-ring', fill:'none',
          stroke:'var(--mist)', 'stroke-width':2.5, opacity:0 }));
        g.appendChild(el('circle', { cx, cy, r:28, fill:'rgba(241,236,249,0.08)',
          stroke:'var(--mist)', 'stroke-width':2 }));
        hitable(g, onPick, k, nameMap[k] + ' cluster');
        host.appendChild(g);
      });
    }

    // One target per cluster row per half of the room: a click answers both the cluster
    // and the side of the cleave line at once.
    function bandHits(onPick){
      const host = layer('p5-hits');
      ['N','M','S'].forEach(k => {
        const [y0, y1] = BAND[k];
        ['W','E'].forEach(h => {
          const x = (h === 'W' ? 60 : 300) + 5, y = y0 + 5;
          const w = 235, hh = (y1 - y0) - 10;
          const g = el('g', {});
          g.appendChild(el('rect', { x, y, width:w, height:hh, rx:9, class:'focus-ring',
            fill:'none', stroke:'var(--mist)', 'stroke-width':2.5, opacity:0 }));
          g.appendChild(el('rect', { x, y, width:w, height:hh, rx:9,
            fill:'rgba(241,236,249,0.045)', stroke:'rgba(241,236,249,0.26)', 'stroke-width':1.5 }));
          const t = el('text', { x: h === 'W' ? x + 34 : x + w - 34, y: y + hh/2 + 4,
            'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':12,
            'font-weight':700, 'letter-spacing':'0.08em', fill:'var(--mist-dim)' });
          t.textContent = h === 'W' ? 'WEST' : 'EAST';
          g.appendChild(t);
          hitable(g, onPick, k + '-' + h, A_NAME[k] + ' cluster, ' + HALF_NAME[h] + ' half');
          host.appendChild(g);
        });
      });
    }

    // Parthenos: an untelegraphed line aimed at the tank, baited exactly north to south down Athena's hitbox, covering
    // roughly the middle 30% of the floor and knocking back anyone caught in it.
    function drawParthenos(){
      const host = document.getElementById('p5-chains');
      const w = 144, x = 300 - w/2;
      const g = el('g', { 'pointer-events':'none' });
      g.appendChild(el('rect', { x, y:60, width:w, height:480, rx:4,
        fill:'rgba(242,165,60,0.20)', stroke:'var(--shape-orange)', 'stroke-width':2,
        'stroke-dasharray':'14 10', class:'stripe' }));
      const t = el('text', { x:300, y:94, 'text-anchor':'middle',
        'font-family':'Space Mono, monospace', 'font-size':12, 'font-weight':700,
        'letter-spacing':'0.1em', fill:'var(--shape-orange)' });
      t.textContent = 'PARTHENOS';
      g.appendChild(t);
      host.appendChild(g);
    }

    // Before you answer the columns are only hinted at below their adds, as in Paradeigma II; the full
    // lines show once you have picked.
    function drawDiveColumns(full){
      const host = document.getElementById('p5-chains');
      host.querySelectorAll('.p5-dive').forEach(n => n.remove());
      st.diveCols.forEach(c => {
        const x = Math.max(60, c - DIVE_HALF), w = Math.min(540, c + DIVE_HALF) - x;
        host.appendChild(el('rect', full
          ? { x, y:60, width:w, height:480, rx:4, fill:'rgba(226,82,63,0.16)', stroke:'var(--astral)', 'stroke-width':3,
              'stroke-dasharray':'13 11', class:'p5-dive stripe', 'pointer-events':'none' }
          : { x, y:60, width:w, height:480, fill:'url(#p5-addFade)', class:'p5-dive', 'pointer-events':'none' }));
        const add = el('circle', { cx:c, cy:42, r:12, fill:'var(--astral)',
          filter:'url(#glow)', class:'p5-dive', 'pointer-events':'none' });
        // Paradeigma's adds zoom out from Athena's hitbox the first time they show
        if(!full) T.zoomAdd(add, [c, 42], null, 0);
        host.appendChild(add);
      });
    }

    function drawDive(onPick){
      const hits = layer('p5-hits');
      drawDiveColumns(false);
      diveLanes().forEach((ln, i) => {
        const g = el('g', {});
        g.appendChild(el('rect', { x:ln.x+4, y:64, width:ln.w-8, height:472, rx:8, class:'focus-ring',
          fill:'none', stroke:'var(--mist)', 'stroke-width':2.5, opacity:0 }));
        // no outline: the lanes are just the floor, only a keyboard focus ring shows them
        g.appendChild(el('rect', { x:ln.x+4, y:64, width:ln.w-8, height:472, rx:8, fill:'transparent' }));
        hitable(g, onPick, String(i), 'Lane ' + (i+1) + ' of ' + diveLanes().length);
        hits.appendChild(g);
      });
    }

    function drawCleave(half){
      const host = document.getElementById('p5-chains');
      host.appendChild(el('rect', { x: half === 'W' ? 60 : 300, y:60, width:240, height:480, rx:6,
        fill:'rgba(226,82,63,0.24)', stroke:'rgba(226,82,63,0.65)', 'stroke-width':2,
        'stroke-dasharray':'9 6', 'pointer-events':'none' }));
      const t = el('text', { x: half === 'W' ? 180 : 420, y:88, 'text-anchor':'middle',
        'font-family':'Space Mono, monospace', 'font-size':12, 'font-weight':700,
        'letter-spacing':'0.1em', fill:'var(--astral-soft)', 'pointer-events':'none' });
      t.textContent = 'CLEAVED';
      host.appendChild(t);
    }

    function tileHits(onPick, doomed, only){
      const host = layer('p5-tiles');
      const hits = layer('p5-hits');
      [1,2,3,4].forEach(r => ['L','R'].forEach(c => {
        const key = r + c;
        const x = c === 'L' ? 60 : 300, y = 60 + (r-1)*120;
        const dead = doomed.indexOf(key) >= 0;
        host.appendChild(el('rect', { x:x+3, y:y+3, width:234, height:114, rx:5,
          fill: dead ? 'rgba(226,82,63,0.17)' : 'rgba(74,143,224,0.13)',
          stroke: dead ? 'rgba(226,82,63,0.55)' : 'rgba(130,182,242,0.5)',
          'stroke-width':1.5, 'stroke-dasharray': dead ? '8 6' : 'none' }));
        if(dead){
          host.appendChild(el('line', { x1:300, y1:300, x2:COLX[c], y2:ROWY[r],
            stroke:'var(--astral)', 'stroke-width':2, 'stroke-dasharray':'6 6',
            opacity:0.5, class:'stripe' }));
        }
        if(only && key !== only) return;
        const g = el('g', {});
        g.appendChild(el('rect', { x:x+10, y:y+10, width:220, height:100, rx:7, class:'focus-ring',
          fill:'none', stroke:'var(--mist)', 'stroke-width':2.5, opacity:0 }));
        g.appendChild(el('rect', { x:x+10, y:y+10, width:220, height:100, rx:7,
          fill:'rgba(241,236,249,0.05)', stroke:'rgba(241,236,249,0.3)', 'stroke-width':1.5 }));
        hitable(g, onPick, key, 'Tile ' + key);
        hits.appendChild(g);
      }));
    }

    function drawZones(options, onPick){
      const host = layer('p5-zones');
      const n = options.length, gap = 14, span = 480;
      const w = (span - gap*(n-1)) / n;
      options.forEach((o, i) => {
        const x = 60 + i*(w + gap), y = 556, h = 100, cx = x + w/2;
        const g = el('g', {});
        g.appendChild(el('rect', { x, y, width:w, height:h, rx:12, class:'focus-ring',
          fill:'none', stroke:'var(--mist)', 'stroke-width':2, opacity:0 }));
        g.appendChild(el('rect', { x, y, width:w, height:h, rx:12,
          fill:'rgba(241,236,249,0.06)', stroke:'var(--line-strong)', 'stroke-width':1.5 }));
        if(o.icon){
          const u = el('use', { href:o.icon, x: cx-12, y: y+16 });
          u.style.color = o.color || 'var(--mist)';
          g.appendChild(u);
        }
        const t1 = el('text', { x:cx, y: o.icon ? y+62 : y+46, 'text-anchor':'middle',
          'font-family':'Space Mono, monospace', 'font-size':13, 'font-weight':700, fill:'var(--mist)' });
        t1.textContent = o.label;
        g.appendChild(t1);
        const t2 = el('text', { x:cx, y: o.icon ? y+80 : y+66, 'text-anchor':'middle',
          'font-family':'Archivo, sans-serif', 'font-size':11, fill:'var(--mist-dim)' });
        t2.textContent = o.sub || '';
        g.appendChild(t2);
        hitable(g, onPick, o.id, o.label + ' ' + (o.sub || ''));
        host.appendChild(g);
      });
    }

    /* ---------- render ---------- */
    function pill(t){
      document.getElementById('p5-stepPill').textContent =
        (st.set === 'A' ? 'IIA' : 'IIB') + ' · ' + t;
    }
    function instr(h){ document.getElementById('p5-instrText').innerHTML = h; }
    function caption(t){ document.getElementById('p5-caption').textContent = t; }

    const WING_ROW_Y = [110, 78, 46];          // first to glow sits at the bottom
    const WING_ORD = ['1st', '2nd', '3rd'];

    function renderWings(){
      const panel = document.getElementById('p5-wingPanel');
      panel.hidden = st.set !== 'A';
      if(st.set !== 'A') return;
      const host = document.getElementById('p5-wingArt');
      host.innerHTML = '';

      const title = el('text', { x:300, y:18, 'text-anchor':'middle',
        'font-family':'Space Mono, monospace', 'font-size':10, 'letter-spacing':'0.18em',
        fill:'var(--mist-faint)' });
      title.textContent = 'TRINITY OF SOULS';
      host.appendChild(title);

      WING_ROW_Y.forEach((y, i) => {
        ['W','E'].forEach(side => {
          const on = st.wingsLit && side === st.wings[i];
          const d = side === 'W'
            ? `M288,${y} L206,${y-15} Q190,${y} 206,${y+15} Z`
            : `M312,${y} L394,${y-15} Q410,${y} 394,${y+15} Z`;
          const wing = el('path', { d,
            fill: on ? 'var(--aether)' : 'none',
            stroke: on ? 'var(--aether-soft)' : 'var(--line-strong)',
            'stroke-width': on ? 2 : 1.5,
            opacity: on ? 0.95 : 0.35 });
          if(on) wing.setAttribute('filter', 'url(#glow)');
          host.appendChild(wing);
        });
        const ord = el('text', { x:62, y:y + 4, 'font-family':'Space Mono, monospace',
          'font-size':11, 'font-weight':700, fill:'var(--mist-faint)' });
        ord.textContent = WING_ORD[i];
        host.appendChild(ord);
      });


      const boss = el('g', { filter:'url(#glow)' });
      boss.appendChild(el('path', { d:'M0 -20 L6 -6 L20 0 L6 6 L0 20 L-6 6 L-20 0 L-6 -6 Z',
        fill:'var(--aether)', transform:'translate(300,78)' }));
      host.appendChild(boss);

      [['WEST', 150], ['EAST', 450]].forEach(([txt, x]) => {
        const t = el('text', { x, y:136, 'text-anchor':'middle',
          'font-family':'Space Mono, monospace', 'font-size':10, 'letter-spacing':'0.12em',
          fill:'var(--mist-faint)' });
        t.textContent = txt;
        host.appendChild(t);
      });
    }

    function render(){
      renderWings();
      layer('p5-tiles'); layer('p5-chains'); layer('p5-hits'); layer('p5-zones');
      fb.hidden = true;
      if(st.set === 'A') renderA(); else renderB();
    }

    function renderA(){
      const host = document.getElementById('p5-chains');
      caption('Every position is a cluster and a half of the room: the cluster answers the chain, the half answers the cleave.');
      if(st.step === 1){
        pill('Step 1 · Open the set');
        instr(`Three clusters are chained up and Athena's wings are lighting. Click where you stand for the <span class="hl">first</span> shapes.<span class="hint"> Go to the cluster that opens the set, the one with the <span class="hl">short purple chain</span>, on the half the first cleave spares.</span>`);
        ['N','M','S'].forEach(k => drawCluster(host, k, {}));
        bandHits(answerA1);
      } else if(st.step === 2){
        pill('Step 2 · First shapes');
        instr(`You are at the <span class="hl">${A_NAME[st.firstSide]}</span> cluster on the <span class="hl">${HALF_NAME[st.safeHalf[0]]}</span> half, and its short chains are pulling in. As <span class="hl">${shared.slot}</span>, click where you stand to take the short chains' shapes.<span class="hint"> The short purple jack cones one role, so <b>pair up</b>: the pairs line up from the <b>arena centre outwards</b>, <b>T1 M1</b>, <b>T2 M2</b>, <b>H1 R1</b>, <b>H2 R2</b>.</span>`);
        ['N','M','S'].forEach(k => drawCluster(host, k, { dim: k !== st.firstSide, highlight: k === st.firstSide }));
        drawFirstSpots(answerFirst);
      } else if(st.step === 3){
        pill('Step 3 · Into the donut');
        instr(`You paired up and the first shapes have fired. Click where you stand for the <span class="hl">second</span> shapes.<span class="hint"> Take the <b>donut</b>, on the half the second cleave spares: IIA always lights <b>bottom to top</b>, so Athena spins 180° between cleaves and the second one lands on the half <b>opposite</b> its wing.</span>`);
        ['N','M','S'].forEach(k => drawCluster(host, k, { dim: k === st.firstSide }));
        bandHits(answerA2);
      } else if(st.step === 4){
        pill('Step 4 · Finish the set');
        instr(`Donut resolved, and the middle's long green orb is about to go off. Click where you stand for the <span class="hl">last</span> shapes.<span class="hint"> Go to the cluster that finishes the set, the one with the <span class="hl">long spiked shape</span>, on the half the third cleave spares.</span>`);
        ['N','M','S'].forEach(k => drawCluster(host, k, { dim: k === 'M' }));
        bandHits(answerA3);
      } else {
        pill('Step 5 · Final shape');
        instr(`You are at the <span class="hl">${A_NAME[st.finalSide]}</span> cluster for its long chain. How do you take the long chain's shape?<span class="hint"> <b>Orange spreads</b> to clock positions, <b>purple pairs</b> a DPS with a support, both taken relative to the boss.</span>`);
        ['N','M','S'].forEach(k => drawCluster(host, k, { dim: k !== st.finalSide, highlight: k === st.finalSide }));
        drawZones([
          { id:'spread', label:'SPREAD', sub:'clock positions', icon:'#icon-spread' },
          { id:'pairs',  label:'PAIR UP', sub:'with your partner', icon:'#icon-stack' }
        ], answerA4);
      }
    }

    function renderB(){
      const host = document.getElementById('p5-chains');
      caption('Clusters appear in waves, so earlier ones fade once they have fired.');
      if(st.step === 1){
        pill('Step 1 · Open inside');
        instr(`Two clusters have spawned inside the middle.<span class="hint"> One is chained to a donut and one to a green orb.</span> Where do you <span class="hl">start</span>?`);
        ['iN','iS'].forEach(k => drawCluster(host, k, {}));
        clusterHits(['iN','iS'], answerB1);
      } else if(st.step === 2){
        pill('Step 2 · East or west');
        instr(`East and west have spawned while Athena casts Paradeigma.<span class="hint"> One holds a green orb, the other a <span class="hl">spiked shape</span>.</span> Which way do you go?`);
        ['iN','iS'].forEach(k => drawCluster(host, k, { dim:true }));
        ['E','W'].forEach(k => drawCluster(host, k, {}));
        clusterHits(['E','W'], answerB2);
      } else if(st.step === 3){
        pill('Step 3 · Resolve the spike');
        instr(`Parthenos has knocked you out of Athena's line and you are at the <span class="hl">${B_NAME[st.spikeSide]}</span> cluster. How do you take this cluster's shape?<span class="hint"> <b>Orange spreads</b> to clock positions, <b>purple pairs</b> a DPS with a support.</span>`);
        ['iN','iS'].forEach(k => drawCluster(host, k, { dim:true }));
        ['E','W'].forEach(k => drawCluster(host, k, { dim: k !== st.spikeSide, highlight: k === st.spikeSide }));
        drawZones([
          { id:'spread', label:'SPREAD', sub:'clock positions', icon:'#icon-spread' },
          { id:'pairs',  label:'PAIR UP', sub:'with your partner', icon:'#icon-stack' }
        ], answerB3);
      } else if(st.step === 4){
        pill('Step 4 · Reposition');
        instr(`The shape is resolved, and north and south are already up on long chains. Click where you move to now.<span class="hint"> The two red <b>Paradeigma</b> adds north of the platform fire down their own columns next, so take a column with no add above it.</span>`);
        ['E','W'].forEach(k => drawCluster(host, k, { dim:true }));
        // the final clusters are already showing, to draw the eye away from the adds
        ['oN','oS'].forEach(k => drawCluster(host, k, {}));
        drawDive(answerB4);
      } else if(st.step === 5){
        pill('Step 5 · Final cluster');
        instr(`Columns dodged. North and south are up on long chains — one carries a lone green orb, the other a <span class="hl">green orb and an orange spiked ball</span>. Which cluster is yours?<span class="hint"> The set finishes on the cluster carrying <b>both</b> shapes.</span>`);
        ['E','W'].forEach(k => drawCluster(host, k, { dim:true }));
        ['oN','oS'].forEach(k => drawCluster(host, k, {}));
        clusterHits(['oN','oS'], answerB5);
      } else if(st.step === 6){
        pill('Step 6 · Final shapes');
        instr(`You are at the <span class="hl">${B_NAME['o'+st.finalSide]}</span> cluster and its long chains are pulling in, while Unnatural Enchainment starts taking tiles. How do you take the shapes?<span class="hint"> A green orb is a point-blank and the orange ball cones everyone, so it is always <b>out and spread</b> — the tiles come after.</span>`);
        const doomed = [];
        [1,2,3,4].forEach(r => ['L','R'].forEach(c => { if(r+c !== st.safeTile) doomed.push(r+c); }));
        // the surviving tile is already readable and clickable, but the shapes come first
        tileHits(answerB6Tile, doomed, st.safeTile);
        drawCluster(host, 'o' + st.finalSide, { highlight:true });
        drawZones([
          { id:'in-spread',  label:'IN',  sub:'spread', icon:'#icon-spread' },
          { id:'in-pairs',   label:'IN',  sub:'pairs',  icon:'#icon-stack' },
          { id:'out-spread', label:'OUT', sub:'spread', icon:'#icon-spread' },
          { id:'out-pairs',  label:'OUT', sub:'pairs',  icon:'#icon-stack' }
        ], answerB6);
      } else {
        pill('Step 7 · The last tile');
        instr(`You are out from the <span class="hl">${B_NAME['o'+st.finalSide]}</span> cluster and spread. Unnatural Enchainment is taking <span class="hl">seven of the eight tiles</span> — click the one that survives.<span class="hint"> The survivor is always one of the <b>four tiles beside the final cluster</b>.</span>`);
        const doomed = [];
        [1,2,3,4].forEach(r => ['L','R'].forEach(c => { if(r+c !== st.safeTile) doomed.push(r+c); }));
        tileHits(answerB7, doomed);
        drawCluster(host, 'o' + st.finalSide, { highlight:true });
      }
    }

    /* ---------- answers ---------- */
    function step(n){
      return { label: 'Continue → Step ' + n, fn: () => { st.step = n; render(); } };
    }

    function judge(ok, title, why, next){
      if(ok){
        showFeedback(fb, true, title, why, next.label, next.fn);
      } else {
        showFeedback(fb, false, title, why, 'New pull ↻', () => newRound());
      }
    }

    // Each IIA position is judged on both halves of the answer: the cluster and the side.
    function cleaveWhy(i){
      const w = st.wings[i], c = st.cleave[i];
      return CLEAVE_FLIP[i]
        ? `The <b>${HALF_NAME[w]}</b> wing glowed, but she has spun 180° since the first cleave, so this one lands <b>${HALF_NAME[c]}</b> instead — stand <b>${HALF_NAME[st.safeHalf[i]]}</b>.`
        : `The <b>${HALF_NAME[w]}</b> wing glowed and she is facing as she started, so it cleaves <b>${HALF_NAME[c]}</b> — stand <b>${HALF_NAME[st.safeHalf[i]]}</b>.`;
    }

    function judgeA(id, i, clusterWhy, next){
      lock();
      const parts = String(id).split('-');
      const wantCluster = st.aCluster[i], wantHalf = st.safeHalf[i];
      const okCluster = parts[0] === wantCluster, okHalf = parts[1] === wantHalf;
      const ok = okCluster && okHalf;
      drawCleave(st.cleave[i]);
      const title = ok ? 'Good position'
        : (!okCluster && !okHalf) ? 'Wrong cluster and wrong half'
        : (!okCluster ? 'Wrong cluster' : 'Caught by the cleave');
      judge(ok, title, clusterWhy + ' ' + cleaveWhy(i), next);
    }

    // The eight spots around the first cluster, each tagged with its half and its place north to south there.
    function firstSpots(){
      const spots = [];
      ['N', 'S'].forEach(c => {
        const [cx, cy] = A_POS[c], mine = [];
        for(let k = 0; k < 8; k++){
          const a = (k * 45 - 67.5) * RAD;
          mine.push({ cluster:c, xy:[cx + Math.cos(a) * PAIR_R, cy + Math.sin(a) * PAIR_R], half: Math.cos(a) > 0 ? 'E' : 'W' });
        }
        // pairs count from the arena's centre outwards, so the order flips between the north and south clusters
        ['E', 'W'].forEach(h => mine.filter(sp => sp.half === h).sort((p, q) => Math.abs(p.xy[1] - 300) - Math.abs(q.xy[1] - 300))
          .forEach((sp, i) => { sp.index = i; sp.id = c + '-' + h + '-' + i; sp.label = `${A_NAME[c]} cluster, ${HALF_NAME[h]} side, spot ${i + 1} from the arena centre`; }));
        spots.push(...mine);
      });
      return spots;
    }
    function pairSpot(i){ return firstSpots().find(sp => sp.cluster === st.firstSide && sp.half === st.safeHalf[0] && sp.index === i).xy; }
    function drawFirstSpots(onPick){
      const host = layer('p5-hits');
      firstSpots().filter(sp => sp.cluster === st.firstSide && sp.half === st.safeHalf[0]).forEach(sp => {
        const [x, y] = sp.xy;
        const g = el('g', {});
        g.appendChild(el('circle', { cx:x, cy:y, r:20, class:'focus-ring', fill:'none', stroke:'var(--mist)', 'stroke-width':2.5, opacity:0 }));
        g.appendChild(el('circle', { cx:x, cy:y, r:15, fill:'rgba(241,236,249,0.12)', stroke:'var(--mist)', 'stroke-width':2 }));
        hitable(g, onPick, sp.id, sp.label);
        host.appendChild(g);
      });
    }
    function drawPairs(yours){
      const host = document.getElementById('p5-chains');
      const me = shared.slot;
      ['T1','M1','T2','M2','H1','R1','H2','R2'].forEach(slot => {
        const i = PAIR_OF[slot], [px, py] = pairSpot(i);
        const dps = slot[0] === 'M' || slot[0] === 'R';
        let [x, y] = [px + (dps ? 9 : -9), py];
        if(slot === me && yours) [x, y] = yours;
        const color = slot[0] === 'T' ? 'var(--umbral-soft)' : slot[0] === 'H' ? 'var(--good)' : 'var(--astral-soft)';
        const g = el('g', { 'pointer-events':'none' });
        if(slot === me) g.appendChild(el('circle', { cx:x, cy:y, r:15, fill:'none', stroke:'var(--mist)', 'stroke-width':2.2 }));
        g.appendChild(el('circle', { cx:x, cy:y, r:10.5, fill:'rgba(10,9,22,0.94)', stroke:color, 'stroke-width':1.5 }));
        const t = el('text', { x, y:y + 3.2, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':8, 'font-weight':700, fill:color });
        t.textContent = slot;
        g.appendChild(t);
        host.appendChild(g);
      });
    }

    function answerFirst(id){
      lock();
      layer('p5-hits');
      const want = PAIR_OF[shared.slot];
      const ok = id === st.firstSide + '-' + st.safeHalf[0] + '-' + want;
      const spot = firstSpots().find(sp => sp.id === id);
      drawCleave(st.cleave[0]);
      drawPairs(ok ? null : spot.xy);
      const rule = `The short chain on the ${A_NAME[st.firstSide]} cluster is the <b>purple jack</b>, which cones one role, so everyone <b>pairs up</b>, a DPS with a support. In IIA the first shape is <b>always pairs</b>. The pairs take the four spots around the cluster on the <b>${HALF_NAME[st.safeHalf[0]]}</b> half, the one the first cleave spares, lined up from the <b>arena centre outwards</b>: <b>T1 and M1</b> nearest the centre, then <b>T2 and M2</b>, <b>H1 and R1</b>, and <b>H2 and R2</b> furthest out — so on the ${A_NAME[st.firstSide]} cluster T1 and M1 take the ${st.firstSide === 'N' ? 'southmost' : 'northmost'} spot. As <b>${shared.slot}</b> you stand with the <b>${PAIR_NAME[want]}</b> pair.`;
      let title, why;
      if(ok){ title = 'Paired up'; why = `${rule} The cones fan out between the pairs.`; }
      else { title = 'Wrong pair spot'; why = `That is where the <b>${PAIR_NAME[spot.index]}</b> pair stands, so two pairs would share one cone. ${rule}`; }
      judge(ok, title, why, step(3));
    }

    function answerA1(id){
      st.wingsLit = false;   // the glow goes out once she starts cleaving
      judgeA(id, 0,
        `The <b>short purple jack</b> is on the ${A_NAME[st.firstSide]} cluster, so the set opens there, well clear of the middle's green orb.`,
        step(2));
    }

    function answerA2(id){
      judgeA(id, 1,
        `The middle cluster's medium chain is the <b>blue donut</b>, so everyone runs <b>into the middle</b> and hugs it.`,
        step(4));
    }

    function answerA3(id){
      const why = st.returnToFirst
        ? `Your first cluster's long chain was the <b>${SHAPE[st.finalShape].label}</b>, so you turn around and come <b>back to where you started</b>, in the ${A_NAME[st.finalSide]}.`
        : `Your first cluster's long chain was a <b>green orb</b>, so the spiked shape has to be on the far cluster — <b>run straight through</b> to the ${A_NAME[st.finalSide]}.`;
      judgeA(id, 2, why, step(5));
    }

    function answerA4(id){
      lock();
      const want = st.finalShape === 'orange' ? 'spread' : 'pairs';
      const ok = id === want;
      judge(ok, ok ? 'Superchain IIA cleared' : 'Wrong formation',
        `The long chain there is the <b>${SHAPE[st.finalShape].label}</b>, so ${st.finalShape === 'orange' ? 'it cones every player and you take your <b>clock position</b> around the cluster' : 'it cones one role and you <b>pair up</b>, a DPS with a support'}. Watch the middle's long green orb at the same time and keep the melee out of it. Apodialogos or Peridialogos follows, then On the Soul, then IIB.`,
        { label: 'Continue → Superchain IIB', fn: toB });
    }

    function answerB1(k){
      lock();
      const ok = k === 'i' + st.donutSide;
      judge(ok, ok ? 'Good start' : 'Wrong cluster',
        `The <b>blue donut</b> is on the ${B_NAME['i'+st.donutSide]} cluster and the other holds a green orb, so the party opens <b>inside the donut</b>.`,
        step(2));
    }

    function answerB2(k){
      lock();
      const ok = k === st.spikeSide;
      drawParthenos();
      judge(ok, ok ? 'Right side' : 'Wrong side',
        `The <b>${SHAPE[st.spikeShape].label}</b> is chained ${B_NAME[st.spikeSide]}, and the other side is only a green orb, so you leave the donut toward the <b>${B_NAME[st.spikeSide]}</b>. <b>Parthenos</b> fires as you go: an untelegraphed line aimed at the tank holding Athena, who baits it exactly north to south, straight down her hitbox and across the middle of the floor. Either flank clears it — but anyone still hugging the donut gets knocked back.`,
        step(3));
    }

    function answerB3(id){
      lock();
      const want = st.spikeShape === 'orange' ? 'spread' : 'pairs';
      const ok = id === want;
      judge(ok, ok ? 'Correct formation' : 'Wrong formation',
        `A <b>${SHAPE[st.spikeShape].label}</b> means ${st.spikeShape === 'orange' ? '<b>spread</b> to your clock positions' : '<b>pair up</b>, a DPS with a support'}, taken relative to the boss just as in the first Superchain. While you sit there, find the gap between the red Paradeigma adds in the north, because their columns fire next.`,
        step(4));
    }

    function answerB4(idx){
      lock();
      const lanes = diveLanes();
      const ln = lanes[Number(idx)];
      const ok = !ln.danger;
      drawDiveColumns(true);
      judge(ok, ok ? 'Clear of the columns' : 'Caught by a column',
        (ok ? '' : `The final clusters can wait: they resolve only after the adds have fired. `) +
        `Two red Paradeigma adds float just north of the platform and fire straight down their own columns, ` +
        `exactly as in Paradeigma II, so the <b>two columns with no add above them</b> stay clear. ` +
        `Find them while you are still resolving the shape rather than after.`,
        step(5));
    }

    function answerB5(k){
      lock();
      const ok = k === 'o' + st.finalSide;
      judge(ok, ok ? 'Right cluster' : 'Wrong cluster',
        `The ${B_NAME['o'+st.finalSide]} cluster carries <b>both a green orb and an orange spiked ball</b>, so that is the last one.`,
        step(6));
    }

    function tileWords(key){
      const ROW = { '1':'first', '2':'second', '3':'third', '4':'fourth' };
      return `the ${ROW[key[0]]} row, ${key[1] === 'L' ? 'west' : 'east'}`;
    }

    const OUT_SPREAD = `The final cluster carries a <b>green orb</b>, a point-blank, so stay <b>out</b> off the cluster, and an <b>orange spiked ball</b>, which cones everyone, so <b>spread</b> to your clock position. In IIB the last shape is <b>always out and spread</b>.`;
    function answerB6(id){
      lock();
      const ok = id === 'out-spread';
      const inside = id.indexOf('in') === 0, pairs = id.indexOf('pairs') > 0;
      let title, why;
      if(ok){ title = 'Out and spread'; why = `${OUT_SPREAD} Keep an eye on the tiles while you stand there.`; }
      else if(inside && pairs){ title = 'Wrong on both counts'; why = `Inside, the green orb's point-blank hits everyone, and in pairs the orange cones double up. ${OUT_SPREAD}`; }
      else if(inside){ title = 'Caught by the green orb'; why = `Inside the cluster you are in the green orb's point-blank. ${OUT_SPREAD}`; }
      else { title = 'Doubled up in the cones'; why = `The orange ball cones <b>every</b> player, so pairs take two cones each. ${OUT_SPREAD}`; }
      judge(ok, title, why, step(7));
    }

    function answerB6Tile(){
      lock();
      judge(false, 'Shapes first',
        `That tile does survive, but the final shapes land before Unnatural Enchainment resolves. Leaving now means you miss the out-and-spread. ${OUT_SPREAD} Move to the tile straight after.`,
        step(7));
    }

    function answerB7(key){
      lock();
      const ok = key === st.safeTile;
      judge(ok, ok ? 'Superchain IIB cleared' : 'That tile is going away',
        `Only <b>${tileWords(st.safeTile)}</b> survives. Unnatural Enchainment always leaves one of the <b>four tiles beside the final cluster</b>, so you already know which half of the floor to read before the tethers appear. Move there straight out of the spread, while the cast is still running. Athena then casts On the Soul twice and goes untargetable for her enrage.`,
        { label: 'New pull ↻', fn: newRound });
    }

    const newRound = T.trackRounds('superchain2', startRound);
    shared.roleListeners.push(newRound);
    newRound();
  }

  T.register({ id: 'superchain2', label: 'Superchain II', phase: 'Athena', players: 'slot', markup: MARKUP, styles: STYLES, init: initSuperchain2 });
})(window.Twelfth);
