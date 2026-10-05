/* Paradeigma III: pick a surviving platform, place, and bait the White Flame lasers. */
(function(T){

  const { shared, shuffle, showFeedback, aspectColor, aspectSoft, aspectLabel } = T;

  const MARKUP = /* html */ `
  <div class="layout" data-dim="off" id="panel-para3" role="tabpanel" aria-labelledby="tabBtn-para3" hidden>

    <section class="arena-wrap">
      <div class="step-row">
        <span class="step-pill" id="p3-stepPill">Step 1 · Pick your platform</span>
      </div>

      <svg class="arena-svg" id="p3-arena" style="--zone-band: 16.67%" viewBox="0 0 600 672" role="img" aria-label="Top-down view of the Twelfth Circle arena split into eight tiles, four of them about to be destroyed">
        <rect x="60" y="60" width="480" height="480" rx="6" fill="url(#floor)"/>
        <image href="assets/arena-phase1.svg" x="60" y="60" width="480" height="480" preserveAspectRatio="none" pointer-events="none"/>
        <!-- Athena's target circle: one column width in radius, as in Paradeigma II -->
        <circle cx="300" cy="300" r="120" fill="none" stroke="rgba(247,147,30,0.45)" stroke-width="1.6" stroke-dasharray="4 6" pointer-events="none"/>

        <g id="p3-tiles"></g>
        <g id="p3-chains"></g>
        <g id="p3-adds"></g>

        <!-- boss -->
        <g class="spin" filter="url(#glow)" pointer-events="none">
          <g transform="translate(300,300)" fill="var(--aether)">
            <path d="M0 -22 L6 -6 L22 0 L6 6 L0 22 L-6 6 L-22 0 L-6 -6 Z"/>
          </g>
        </g>
        <circle cx="300" cy="300" r="9" fill="var(--void)" stroke="var(--aether)" stroke-width="1.5" pointer-events="none"/>

        <g id="p3-tethers"></g>
        <g id="p3-lasers" pointer-events="none"></g>
        <g id="p3-actors"></g>
        <g id="p3-hits"></g>
        <g id="p3-zones"></g>

        <rect x="60" y="60" width="480" height="480" rx="6" fill="none" stroke="rgba(247,147,30,0.55)" stroke-width="2" filter="url(#glow)" pointer-events="none"/>
      </svg>

      <p class="arena-caption">Four tiles survive in a zigzag. Enchained Soul pins every player to the one tile they are standing on.</p>

      <div class="feedback" id="p3-feedback" hidden aria-live="polite"></div>
    </section>

    <aside class="hud">
      <div class="card">
        <h2>Your debuffs</h2>
        <div class="assign-row" id="p3-badges"></div>
        <p class="assign-text hint-only" id="p3-assignText"></p>
      </div>

      <div class="card">
        <h2>Objective</h2>
        <p class="instr-text" id="p3-instrText"></p>
      </div>

      <details class="card">
        <summary>How the call works</summary>
        <ol>
          <li><b>Paradeigma</b> spawns Anthropos adds from four blue crystals — two on the west wall, two on the east — plus two yellow crystals on opposite intercardinals. Every add on the same wall carries the <b>same tether colour</b>.</li>
          <li><b>Engravement of Souls</b> gives the supports one <b>Quartered Soul</b>, one <b>X-marked Soul</b> and two matching bright souls. Everyone gets <b>Enchained Soul</b>: no jumping, so you are stuck on a single tile.</li>
          <li><b>Unnatural Enchainment</b> tethers four alternating tiles and destroys them, leaving a zigzag of four platforms. A plain tower lands on each one and a support has to soak it.</li>
          <li>Quartered Soul takes the <b>north-most</b> platform and X-marked the <b>south-most</b>. The two bright souls take the middle two, west to east by <b>H1 &gt; T1 &gt; T2 &gt; H2</b>.</li>
          <li><b>Middle platforms:</b> the plain tower sits in the outer half, right where the two DPS stretch their tethers, and their lasers run <b>east–west</b> across it. Soak it from its side <b>away from the arena's horizontal centre line</b>, in the outer gap the two lasers leave, or a DPS laser clips you.</li>
          <li>Each bright soul then drops an aspected tower. Compare your aspect with the tether colour of the two DPS on your tile: <b>same colour</b> and you drop it on the arena-centre corner so it spills onto the other middle platform; <b>opposite</b> and you drop it in the middle of your own tile.</li>
          <li>DPS stretch their tether to the <b>opposite</b> middle platform. The one whose add lines up with it has the <b>straight</b> tether and stands at the platform's <b>horizontal centre, level with the add</b>, so the laser runs dead east–west. That is only just the minimum stretch the tether needs, so not a step closer to the add; the other has the <b>crossed</b> tether and stands at the <b>middle of the platform's outer edge</b> — top middle on the northern platform, bottom middle on the southern — so the laser angles across.</li>
          <li>The DPS pair whose colour is opposite the towers soaks them — <b>crossed</b> tether takes the centre tower, <b>straight</b> tether the one on the platform. The matching-colour pair, along with the + and X supports, bait the two <b>White Flame</b> lasers away from the middle. The + and X are <b>delayed</b>: step out of your own arms before you bait and stay out — an arm of the X runs right through the southern add, so bait from a step towards the outer wall. Mind the add's <b>other line</b> too: it runs from the add to the DPS baiting it, so the + support baits from behind the add, well clear of that line's edge.</li>
        </ol>
      </details>

      <div class="card">
        <h2>Debuffs</h2>
        <div class="legend-list">
          <div class="legend-item"><img src="assets/quartered-soul.png" alt=""><span><b>Quartered Soul</b> — plus-shaped AoE, fixed to true north.<span class="hint"> North platform.</span></span></div>
          <div class="legend-item"><img src="assets/x-marked-soul.png" alt=""><span><b>X-marked Soul</b> — X-shaped AoE, fixed to true north.<span class="hint"> South platform.</span></span></div>
          <div class="legend-item"><img src="assets/astralbright-soul.png" alt=""><span><b>Astralbright Soul</b> — drops a dark tower<span class="hint"> for a light-tethered DPS</span></span></div>
          <div class="legend-item"><img src="assets/umbralbright-soul.png" alt=""><span><b>Umbralbright Soul</b> — drops a light tower<span class="hint"> for a dark-tethered DPS</span></span></div>
          <div class="legend-item"><img src="assets/enchained-soul.png" alt=""><span><b>Enchained Soul</b> — everyone, all mechanic: you cannot jump</span></div>
        </div>
      </div>
    </aside>

  </div>
  `;

  function initPara3(){
    const SVGNS = 'http://www.w3.org/2000/svg';
    const COLX = { L:180, R:420 };
    const ROWY = { 1:120, 2:240, 3:360, 4:480 };
    const PRIORITY = ['H1','T1','T2','H2'];          // west to east
    const JOB = { H1:'healer', H2:'healer', T1:'tank', T2:'tank' };

    const SOUL = {
      quartered: { label:'Quartered Soul', icon:'assets/quartered-soul.png', cls:'role' },
      xmarked:   { label:'X-marked Soul',  icon:'assets/x-marked-soul.png',  cls:'role' },
      astral:    { label:'Astralbright Soul', icon:'assets/astralbright-soul.png', cls:'astral' },
      umbral:    { label:'Umbralbright Soul', icon:'assets/umbralbright-soul.png', cls:'umbral' }
    };

    // Athena's aspects: Astral is the dark one, Umbral the light one.
    function lightWord(a){ return a === 'astral' ? 'dark' : 'light'; }

    let st = {};
    const fb = document.getElementById('p3-feedback');

    function tile(row, col){
      return { row, col, key: String(row) + col, x: col === 'L' ? 60 : 300, y: 60 + (row-1)*120,
               w:240, h:120, cx:COLX[col], cy:ROWY[row] };
    }
    // A plain tower lands in the middle of the outer half of its platform, the half away from the centre.
    function plainTowerX(t){ return t.col === 'L' ? t.x + t.w / 4 : t.x + t.w * 3 / 4; }
    function tileName(t){
      if(t.key === st.north.key) return 'NORTH';
      if(t.key === st.south.key) return 'SOUTH';
      return t.col === 'L' ? 'MID WEST' : 'MID EAST';
    }

    // The two DPS on a middle platform are always tethered to the far wall, so they can stretch.
    // The DPS whose add lines up with the platform has the straight tether and stands at the platform's
    // horizontal centre, level with the add, so the laser runs dead horizontal. That is only just far enough
    // to stretch the tether, so no closer. The crossed tether stands at the middle of
    // the platform's outer edge (top on the northern platform, bottom on the southern), so its laser
    // angles across. Between them the two lasers leave an outer gap on the plain tower for the support.
    // The wall adds sit level with the two middle rows, pulled halfway in towards the centre line.
    const WALL_ADD_Y = { 240: 270, 360: 330 };
    function dpsSpots(t){
      const fromSide = t.col === 'L' ? 'east' : 'west';
      const wallX = fromSide === 'west' ? 44 : 556;
      const dx = fromSide === 'west' ? t.x + t.w - 52 : t.x + 52;
      const slantAddY = t.cy === 240 ? 360 : 240;
      const color = fromSide === 'west' ? st.westColor : st.eastColor;
      return [
        { straight:true,  x:t.cx, y:WALL_ADD_Y[t.cy], addX:wallX, addY:WALL_ADD_Y[t.cy], color, side:fromSide },
        { straight:false, x:t.cx, y:t.row === 2 ? t.y + 18 : t.y + t.h - 18, addX:wallX, addY:WALL_ADD_Y[slantAddY], color, side:fromSide }
      ];
    }

    function startRound(){
      st.zig = Math.random() < 0.5 ? 'L' : 'R';
      const other = st.zig === 'L' ? 'R' : 'L';
      st.safe   = [tile(1, st.zig), tile(2, other), tile(3, st.zig), tile(4, other)];
      st.doomed = [tile(1, other), tile(2, st.zig), tile(3, other), tile(4, st.zig)];
      st.north = st.safe[0];
      st.south = st.safe[3];
      st.midW  = st.safe[1].col === 'L' ? st.safe[1] : st.safe[2];
      st.midE  = st.safe[1].col === 'R' ? st.safe[1] : st.safe[2];

      st.westColor = Math.random() < 0.5 ? 'astral' : 'umbral';
      st.eastColor = st.westColor === 'astral' ? 'umbral' : 'astral';
      st.bright    = Math.random() < 0.5 ? 'astral' : 'umbral';

      // The yellow-crystal adds land on the dead tile beside the north and south platforms.
      st.addN = { x: COLX[st.north.col], y: 180 };
      st.addS = { x: COLX[st.south.col], y: 420 };

      // Supports: one +, one X, two matching bright souls.
      const souls = shuffle(['quartered','xmarked','bright','bright']);
      st.slotSoul = {};
      PRIORITY.forEach((s, i) => { st.slotSoul[s] = souls[i]; });
      st.brightSlots = PRIORITY.filter(s => st.slotSoul[s] === 'bright');
      st.mySlot = shared.role === 'support' ? shared.slot : PRIORITY[Math.floor(Math.random() * 4)];
      // where each support happens to stand in the stack by Athena before the cast resolves
      st.stackOrder = shuffle(PRIORITY);
      st.mySoul = st.slotSoul[st.mySlot];

      // DPS: a tether from one of the two adds on one wall.
      st.mySide  = Math.random() < 0.5 ? 'west' : 'east';
      st.myColor = st.mySide === 'west' ? st.westColor : st.eastColor;

      if(shared.role === 'support'){
        if(st.mySoul === 'quartered')   st.home = st.north;
        else if(st.mySoul === 'xmarked') st.home = st.south;
        else st.home = (st.mySlot === st.brightSlots[0]) ? st.midW : st.midE;
        // The DPS sharing your platform are tethered to the wall opposite it.
        st.myDpsColor = st.home.col === 'L' ? st.eastColor : st.westColor;
        st.towerSpot  = (st.myDpsColor === st.bright) ? 'centre' : 'tile';
      } else {
        st.home  = st.mySide === 'west' ? st.midE : st.midW;
        st.myAddY = Math.random() < 0.5 ? 240 : 360;
        st.straight = st.myAddY === st.home.cy;
        st.job = (st.myColor === st.bright) ? 'bait' : 'soak';
        st.towerPick = st.straight ? 'tile' : 'centre';
      }

      st.step = 1;
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
      document.querySelectorAll('#panel-para3 .hit').forEach(h => h.setAttribute('aria-disabled','true'));
    }

    function drawTiles(){
      const host = layer('p3-tiles');
      const chains = layer('p3-chains');
      // Unnatural Enchainment is still casting on the opening step: the doomed tiles glow red
      // and carry their chains. Once it resolves they are simply gone.
      const gone = st.step > 1;
      [1,2,3,4].forEach(r => ['L','R'].forEach(c => {
        const t = tile(r, c);
        const safe = st.safe.some(s => s.key === t.key);
        if(safe){
          host.appendChild(el('rect', { x:t.x+3, y:t.y+3, width:t.w-6, height:t.h-6, rx:5,
            fill:'rgba(74,143,224,0.13)', stroke:'rgba(130,182,242,0.5)', 'stroke-width':1.5 }));
        } else if(gone){
          host.appendChild(el('rect', { x:t.x+3, y:t.y+3, width:t.w-6, height:t.h-6, rx:5,
            fill:'rgba(4,3,10,0.9)', stroke:'rgba(230,220,255,0.1)', 'stroke-width':1 }));
        } else {
          host.appendChild(el('rect', { x:t.x+3, y:t.y+3, width:t.w-6, height:t.h-6, rx:5,
            fill:'rgba(226,82,63,0.17)', stroke:'rgba(226,82,63,0.55)',
            'stroke-width':1.5, 'stroke-dasharray':'8 6' }));
          chains.appendChild(el('line', { x1:300, y1:300, x2:t.cx, y2:t.cy,
            stroke:'var(--astral)', 'stroke-width':2, 'stroke-dasharray':'6 6', opacity:0.55, class:'stripe' }));
        }
      }));
    }

    function crystal(host, x, y, color, r){
      const g = el('g', {});
      g.appendChild(el('circle', { cx:x, cy:y, r:r, fill:'rgba(10,9,22,0.9)', stroke:color, 'stroke-width':2 }));
      const u = el('use', { href:'#icon-add', x:x-12, y:y-12 });
      u.style.color = color;
      g.appendChild(u);
      host.appendChild(g);
      return g;
    }

    function drawAdds(){
      const host = layer('p3-adds');
      // as the pull opens they zoom out from Athena's hitbox to their spots
      const zoom = st.step === 1;
      // adds of one colour all set off together
      const add = (x, y, color, r) => { const g = crystal(host, x, y, color, r); if(zoom) T.zoomAdd(g, [x, y], null, 0); };
      [240,360].forEach(row => {
        const y = WALL_ADD_Y[row];
        add(44, y, aspectColor(st.westColor), 15);
        add(556, y, aspectColor(st.eastColor), 15);
      });
      add(st.addN.x, st.addN.y, 'var(--aether)', 14);
      add(st.addS.x, st.addS.y, 'var(--aether)', 14);
    }

    function unit(host, x, y, kind, opts){
      opts = opts || {};
      const g = el('g', { class: 'player' + (opts.me ? ' me' : '') });
      if(opts.me){
        g.appendChild(el('circle', { cx:x, cy:y, r:20, fill:'none', stroke:'var(--aether)',
          'stroke-width':2.5, class:'pulse' }));
      }
      g.appendChild(el('circle', { cx:x, cy:y, r:14, fill:'rgba(10,9,22,0.88)',
        stroke: opts.stroke || 'var(--line-strong)', 'stroke-width':1.5 }));
      const u = el('use', { href:'#icon-' + kind, x:x-12, y:y-12 });
      u.style.color = opts.color || 'var(--mist)';
      g.appendChild(u);
      if(opts.icon){
        g.appendChild(el('image', { href:opts.icon, x:x+8, y:y-32, width:24, height:32,
          preserveAspectRatio:'xMidYMid meet' }));
      }
      if(opts.tag){
        const t = el('text', { x:x, y:y+27, 'text-anchor':'middle', 'font-family':'Space Mono, monospace',
          'font-size':11, fill:'var(--mist-dim)' });
        t.textContent = opts.tag;
        g.appendChild(t);
      }
      host.appendChild(g);
    }

    function tower(host, x, y, aspect, label){
      const c = aspect ? aspectColor(aspect) : 'var(--aether)';
      const g = el('g', {});
      g.appendChild(el('circle', { cx:x, cy:y, r:25, fill:c, opacity:0.13 }));
      g.appendChild(el('circle', { cx:x, cy:y, r:25, fill:'none', stroke:c, 'stroke-width':2.5, opacity:0.9 }));
      g.appendChild(el('circle', { cx:x, cy:y, r:4, fill:c }));
      if(label){
        const t = el('text', { x:x, y:y-31, 'text-anchor':'middle', 'font-family':'Space Mono, monospace',
          'font-size':10, 'letter-spacing':'0.08em', fill:c });
        t.textContent = label;
        g.appendChild(t);
      }
      host.appendChild(g);
    }

    function drawPlus(host, x, y){
      const g = el('g', { 'clip-path':'url(#arenaClip)', opacity:0.45, 'pointer-events':'none' });
      g.appendChild(el('line', { x1:x, y1:-50, x2:x, y2:650, stroke:'var(--shape-orange)', 'stroke-width':46 }));
      g.appendChild(el('line', { x1:-50, y1:y, x2:650, y2:y, stroke:'var(--shape-orange)', 'stroke-width':46 }));
      host.appendChild(g);
    }
    function drawSaltire(host, x, y){
      const g = el('g', { 'clip-path':'url(#arenaClip)', opacity:0.45, 'pointer-events':'none' });
      [[1,1],[1,-1]].forEach(d => {
        const r = 900 / Math.SQRT2;
        g.appendChild(el('line', { x1:x - d[0]*r, y1:y - d[1]*r, x2:x + d[0]*r, y2:y + d[1]*r,
          stroke:'var(--shape-orange)', 'stroke-width':46 }));
      });
      host.appendChild(g);
    }

    /* ---------- the cast in position ---------- */
    // Who holds which platform's soul.
    function supportOn(t){
      if(t.key === st.north.key) return { slot: PRIORITY.find(s => st.slotSoul[s] === 'quartered'), soul:'quartered' };
      if(t.key === st.south.key) return { slot: PRIORITY.find(s => st.slotSoul[s] === 'xmarked'), soul:'xmarked' };
      return { slot: t.key === st.midW.key ? st.brightSlots[0] : st.brightSlots[1], soul: st.bright };
    }
    // The DPS on a middle platform are tethered to the far wall.
    const dpsColorOn = t => t.col === 'L' ? st.eastColor : st.westColor;
    // The pair whose tether is opposite the towers soaks; the matching pair baits White Flame.
    const soakTile = () => [st.midW, st.midE].find(t => dpsColorOn(t) !== st.bright);
    const baitTile = () => [st.midW, st.midE].find(t => dpsColorOn(t) === st.bright);
    const centreCorner = (t, inset) => [t.col === 'L' ? t.x + t.w - inset : t.x + inset, t.row === 2 ? t.y + t.h - inset : t.y + inset];
    const clampTo = (xy, t, inset) => [Math.min(Math.max(xy[0], t.x + inset), t.x + t.w - inset), Math.min(Math.max(xy[1], t.y + inset), t.y + t.h - inset)];
    const dist = (p, q) => Math.hypot(p[0] - q[0], p[1] - q[1]);
    const dpsKey = (t, straight) => t.key + (straight ? 'S' : 'C');
    // where each aspected tower lands: the soaking pair's own tile, and the corner by the arena centre
    const towerSpots = () => ({ tile: [soakTile().cx, soakTile().cy], centre: [300, 300] });
    // Where the + and X supports bait White Flame. Both AoEs are delayed, so each support has to be out
    // of their own arms and stay out: the plus's arms run along the walls, clear of the add, but an arm of
    // the X runs straight through the southern add, so the X support baits a step towards the outer wall.
    // The northern add's other line runs from it towards the DPS baiting it, so the + support baits from
    // behind the add, well clear of that line's edge rather than tucked in beside its start.
    const addSpot = t => {
      if(t.key !== st.north.key) return [st.addS.x + (t.col === 'L' ? -40 : 40), st.addS.y + 14];
      const bn = clampTo([st.addN.x, st.addN.y], baitTile(), 12);
      const len = Math.hypot(bn[0] - st.addN.x, bn[1] - st.addN.y) || 1;
      return [st.addN.x - (bn[0] - st.addN.x) / len * 44, st.addN.y - 50];
    };
    const aoeSpot = (t, soul) => soul === 'quartered' ? [t.col === 'L' ? 60 : 540, 60] : [300, 540];

    // Where everyone stands. 'two': tethers out, plain towers soaked. 'pre3': as the last step opens,
    // each where their last job left them. 'res3': as White Flame fires, everyone doing their job.
    function positions(stage){
      const pos = {};
      st.safe.forEach(t => {
        const { slot, soul } = supportOn(t);
        const isMid = t.key === st.midW.key || t.key === st.midE.key;
        if(stage === 'two'){
          // still on the plain tower they soaked
          // on a middle platform, on the tower's side away from the arena's horizontal centre line: the
          // outer gap the two DPS lasers leave
          if(isMid){
            pos[slot] = [plainTowerX(t), t.cy + (t.row === 2 ? -22 : 22)];
          } else {
            pos[slot] = [plainTowerX(t), t.cy];
          }
        } else if(!isMid){
          // as the last step opens they are still where they dropped their AoE; stepping out is part of the job
          pos[slot] = stage === 'pre3' ? aoeSpot(t, soul) : addSpot(t);
        } else {
          const dropped = t.key === soakTile().key ? [t.cx, t.cy] : centreCorner(t, 16);
          pos[slot] = stage === 'pre3' ? dropped : [t.col === 'L' ? t.x + t.w - 24 : t.x + 24, t.cy];
        }
      });
      [st.midW, st.midE].forEach(t => dpsSpots(t).forEach(d => { pos[dpsKey(t, d.straight)] = [d.x, d.y]; }));
      if(stage === 'res3'){
        const soak = soakTile(), bait = baitTile();
        pos[dpsKey(soak, true)] = towerSpots().tile;
        pos[dpsKey(soak, false)] = centreCorner(soak, 16);
        // the two baiters split, one to the corner facing each add
        const n = clampTo([st.addN.x, st.addN.y], bait, 12), so = clampTo([st.addS.x, st.addS.y], bait, 12);
        const sp = dpsSpots(bait), straight = sp.find(d => d.straight), crossed = sp.find(d => !d.straight);
        const straightNorth = dist([straight.x, straight.y], n) <= dist([crossed.x, crossed.y], n);
        pos[dpsKey(bait, true)] = straightNorth ? n : so;
        pos[dpsKey(bait, false)] = straightNorth ? so : n;
      }
      if(stage === 'pre3'){
        // The crossed DPS on the southern platform waits at its bottom middle, inside an arm of the X, so
        // they leave as soon as their laser has fired: straight for their job, or to the middle of the
        // platform when it is you, so the board does not answer your question for you.
        const south = st.midW.row === 3 ? st.midW : st.midE, key = dpsKey(south, false);
        pos[key] = (shared.role === 'dps' && key === myKey()) ? [south.cx, south.cy] : positions('res3')[key];
      }
      return pos;
    }
    // your own key in the positions table
    function myKey(){ return shared.role === 'support' ? st.mySlot : dpsKey(st.home, st.straight); }

    function drawCast(stage, pos){
      stage = stage || (st.step < 3 ? 'two' : 'pre3');
      pos = pos || positions(stage);
      const actors = layer('p3-actors');
      const tethers = layer('p3-tethers');
      // The tether lasers fire as step 2 opens, so the tethers are gone from then on —
      // the straight and crossed tags stay, since that is how you still know which is which.
      const tethered = st.step < 2;
      // the plain towers the supports have just soaked, fading out under them
      if(stage === 'two') st.safe.forEach(t => {
        const g = el('g', { opacity:0.35 });
        tower(g, plainTowerX(t), t.cy, null, null);
        actors.appendChild(g);
      });
      if(st.step >= 3){
        // the + and X go off as the aspected towers appear: the plus from the north platform's outer
        // arena corner, the X from the south platform's cardinal wall point
        drawPlus(actors, st.north.col === 'L' ? 60 : 540, 60);
        drawSaltire(actors, 300, 540);
        const tw = towerSpots();
        tower(actors, tw.tile[0], tw.tile[1], st.bright, stage === 'pre3' && shared.role === 'dps' && st.job === 'soak' ? 'ON PLATFORM' : null);
        tower(actors, tw.centre[0], tw.centre[1], st.bright, stage === 'pre3' && shared.role === 'dps' && st.job === 'soak' ? 'CENTRE' : null);
      }

      [st.midW, st.midE].forEach(t => {
        dpsSpots(t).forEach(d => {
          const mine = shared.role === 'dps' && t.key === st.home.key && d.straight === st.straight;
          const xy = pos[dpsKey(t, d.straight)];
          if(tethered){
            tethers.appendChild(el('line', { x1:d.addX, y1:d.addY, x2:xy[0], y2:xy[1],
              stroke: aspectSoft(d.color), 'stroke-width': mine ? 3 : 1.8, opacity: mine ? 0.95 : 0.5,
              'stroke-linecap':'round' }));
          }
          unit(actors, xy[0], xy[1], 'dps', {
            me: mine, color: aspectSoft(d.color),
            tag: d.straight ? 'straight' : 'crossed'
          });
        });
      });

      // supports last, so they sit on top of the DPS tags beside them
      st.safe.forEach(t => {
        const { slot, soul } = supportOn(t);
        const mine = shared.role === 'support' && slot === st.mySlot;
        unit(actors, pos[slot][0], pos[slot][1], JOB[slot], {
          me: mine, tag: slot, icon: SOUL[soul].icon,
          color: JOB[slot] === 'tank' ? 'var(--umbral-soft)' : 'var(--good)'
        });
      });
    }
    // The last step as it resolves: everyone at their job, you wherever you chose, and each
    // yellow-crystal add firing at whoever is nearest to it.
    function resolveLast(myXY){
      const pos = positions('res3');
      if(myXY) pos[myKey()] = myXY;
      drawCast('res3', pos);
      drawWhiteFlame(pos);
      return pos;
    }
    function layer0(){ return document.getElementById('p3-actors'); }
    // each wall add fires its line at the DPS it is tethered to, as the second step opens
    function fireTethers(){
      const pos = positions('two');
      const beams = [];
      [st.midW, st.midE].forEach(t => dpsSpots(t).forEach(d => beams.push({ from:[d.addX, d.addY], through: pos[dpsKey(t, d.straight)] })));
      T.playBeams(document.getElementById('p3-lasers'), beams);
    }

    /* ---------- hit targets ---------- */
    function spotHits(spots, onPick){
      const host = layer('p3-hits');
      spots.forEach(s => {
        const r = s.r || 22;
        const g = el('g', {});
        g.appendChild(el('circle', { cx:s.x, cy:s.y, r:r+5, class:'focus-ring', fill:'none',
          stroke:'var(--mist)', 'stroke-width':2.5, opacity:0 }));
        g.appendChild(el('circle', { cx:s.x, cy:s.y, r:r, fill:'rgba(241,236,249,0.10)',
          stroke:'var(--mist)', 'stroke-width':2 }));
        if(s.mark){
          const mark = el('text', { x:s.x, y:s.y+5, 'text-anchor':'middle',
            'font-family':'Space Mono, monospace', 'font-size':13, 'font-weight':700, fill:'var(--mist)' });
          mark.textContent = s.mark;
          g.appendChild(mark);
        }
        if(s.label){
          let lx, ly, anchor;
          if(s.labelSide === 'start' || s.labelSide === 'end'){
            anchor = s.labelSide;
            lx = s.x + (s.labelSide === 'start' ? r + 9 : -(r + 9));
            ly = s.y + 4;
          } else {
            anchor = 'middle';
            lx = Math.min(Math.max(s.x, 96), 504);
            ly = s.y > 455 ? s.y - (r + 12) : s.y + r + 20;
          }
          const lab = el('text', { x:lx, y:ly, 'text-anchor':anchor,
            'font-family':'Archivo, sans-serif', 'font-size':11.5, fill:'var(--mist)' });
          lab.textContent = s.label;
          g.appendChild(lab);
        }
        hitable(g, onPick, s.id, s.ariaLabel || s.label || s.id);
        host.appendChild(g);
      });
    }

    function drawZones(options, onPick){
      const host = layer('p3-zones');
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
    function pill(text){ document.getElementById('p3-stepPill').textContent = text; }
    function instr(html){ document.getElementById('p3-instrText').innerHTML = html; }

    function badges(){
      const host = document.getElementById('p3-badges');
      let rows = `<div class="badge role"><img src="assets/enchained-soul.png" alt=""><span>Enchained Soul</span></div>`;
      if(shared.role === 'support'){
        const s = SOUL[st.mySoul === 'bright' ? st.bright : st.mySoul];
        rows += `<div class="badge ${s.cls}"><img src="${s.icon}" alt=""><span>${s.label}</span></div>`;
        document.getElementById('p3-assignText').innerHTML =
          `You are <b>${st.mySlot}</b>. Supports take the souls this mechanic, DPS take the tethers.`;
      } else {
        const cls = st.myColor === 'astral' ? 'astral' : 'umbral';
        rows += `<div class="badge ${cls}"><svg viewBox="0 0 24 24"><use href="#icon-add"/></svg>` +
                `<span>${lightWord(st.myColor)} tether</span></div>`;
        document.getElementById('p3-assignText').innerHTML =
          `Your tether runs to an add on the <b>${st.mySide}</b> wall. Both adds on a wall share one colour.`;
      }
      host.innerHTML = rows;
    }

    function clearBoard(){
      layer('p3-tethers'); layer('p3-actors'); layer('p3-hits'); layer('p3-zones'); layer('p3-lasers');
      fb.hidden = true;
      drawTiles();
      drawAdds();
    }

    function render(){
      badges();
      clearBoard();
      if(shared.role === 'support') renderSupport(); else renderDps();
    }

    function renderSupport(){
      const soulKey = st.mySoul === 'bright' ? st.bright : st.mySoul;
      if(st.step === 1){
        pill('Step 1 · Take your tower');
        instr(`Unnatural Enchainment is casting and the red tiles are going away. A plain tower is landing on each platform that survives. Holding <span class="hl">${SOUL[soulKey].label}</span> as <span class="hl">${st.mySlot}</span>, which tower do you soak?<span class="hint"> <b>Quartered Soul</b> takes the north-most platform and <b>X-marked</b> the south-most; the two bright souls take the middle two, west to east by <b>H1 &gt; T1 &gt; T2 &gt; H2</b>.</span>`);
        const actors = layer('p3-actors');
        st.safe.forEach(t => tower(actors, plainTowerX(t), t.cy, null, null));
        // every support's soul is on show, so the priority can be worked out from the party
        st.stackOrder.forEach((slot, i) => {
          const soul = st.slotSoul[slot] === 'bright' ? st.bright : st.slotSoul[slot];
          unit(actors, 216 + i * 56, 236, JOB[slot], {
            me: slot === st.mySlot, tag: slot, icon: SOUL[soul].icon,
            color: JOB[slot] === 'tank' ? 'var(--umbral-soft)' : 'var(--good)'
          });
        });
        spotHits(st.safe.map(t => ({ id:t.key, x:plainTowerX(t), y:t.cy, r:31,
          ariaLabel:`Plain tower on the ${tileName(t).toLowerCase()} platform` })), answerTile);
      }
      else if(st.step === 2){
        drawCast();
        if(st.mySoul === 'bright'){
          pill('Step 2 · Drop your tower');
          instr(`Plain tower soaked. Your <span class="hl">${SOUL[soulKey].label}</span> is about to drop an aspected one, and the two DPS on your tile, tethered to the <span class="hl">far</span> wall, are <b style="color:${aspectSoft(st.myDpsColor)}">${lightWord(st.myDpsColor)}</b>. Where do you drop your aspected tower?<span class="hint"> If the DPS on your tile share your colour they cannot soak it, so push it over the <b>arena-centre corner</b> to the other middle platform; if they are the opposite colour, drop it in the <b>middle of your own tile</b>.</span>`);
          spotHits([
            { id:'tile',   x:st.home.cx, y:st.home.cy, mark:'A', label:'Middle of your own tile' },
            { id:'centre', x:300, y:300, mark:'B', label:'Arena-centre corner' }
          ], answerTower);
        } else {
          pill('Step 2 · Place your AoE');
          const shape = st.mySoul === 'quartered' ? 'plus-shaped' : 'X-shaped';
          const cast  = st.mySoul === 'quartered' ? "Theos's Cross" : "Theos's Saltire";
          instr(`Your <span class="hl">${shape}</span> ${cast} is about to land, locked to true north. Click where you stand to drop your ${shape}.<span class="hint"> It must miss the middle. Both shapes are locked to true north: the <b>plus</b> runs its arms along the walls from the outer arena corner, the <b>X</b> throws its arms into the corners from the cardinal wall point.</span>`);
          spotHits(aoeSpots(), answerAoe);
        }
      }
      else {
        drawCast('pre3');
        if(st.mySoul === 'bright'){
          pill('Step 3 · Get clear');
          instr(`Your tower is down and the DPS are coming for it. What do you do while the DPS take your tower?<span class="hint"> You already soaked the plain tower, so the aspected one is not yours: step aside, clear of every tower and of the + and X AoEs.</span>`);
          drawZones([
            { id:'clear', label:'STEP ASIDE', sub:'clear of everything', icon:'#icon-spread' },
            { id:'soak',  label:'SOAK IT',    sub:'your own tower',             icon:'#icon-stack'  },
            { id:'bait',  label:'BAIT',       sub:'a White Flame laser',        icon:'#icon-hold'   }
          ], answerLast);
        } else {
          pill('Step 3 · Last job');
          instr(`Your AoE is placed. The yellow-crystal add next to your platform is winding up <span class="hl">White Flame</span>. What is your last job before White Flame?<span class="hint"> Each yellow-crystal add fires at its two nearest players, so the + and X supports move in and <b>bait</b> one each, pointing the line away from the middle — out of their own delayed AoE, which is still to go off.</span>`);
          drawZones([
            { id:'bait', label:'BAIT', sub:'away from the middle', icon:'#icon-hold'   },
            { id:'soak', label:'SOAK', sub:'an aspected tower',                 icon:'#icon-stack'  },
            { id:'hold', label:'HOLD', sub:'stay out on the wall',              icon:'#icon-spread' }
          ], answerLast);
        }
      }
    }

    function renderDps(){
      if(st.step === 1){
        pill('Step 1 · Take your spot');
        const actors = layer('p3-actors');
        const tethers = layer('p3-tethers');
        const ax = st.mySide === 'west' ? 44 : 556;
        document.getElementById('p3-adds').appendChild(el('circle', { cx:ax, cy:WALL_ADD_Y[st.myAddY], r:21,
          fill:'none', stroke:'var(--aether)', 'stroke-width':2.5, class:'pulse' }));
        tethers.appendChild(el('line', { x1:ax, y1:WALL_ADD_Y[st.myAddY], x2:300, y2:264,
          stroke: aspectSoft(st.myColor), 'stroke-width':3, opacity:0.95, 'stroke-linecap':'round' }));
        unit(actors, 300, 264, 'dps', { me:true, color: aspectSoft(st.myColor) });
        instr(`Your tether runs to the <span class="hl">${st.myAddY === 240 ? 'northern' : 'southern'}</span> of the two <span class="hl">${lightWord(st.myColor)}</span> adds on the <span class="hl">${st.mySide}</span> wall. Click the spot you take.<span class="hint"> Stretch it across: both DPS from one wall cross to the <b>opposite middle platform</b>: if your add lines up with it yours is the <b>straight</b> tether, at the platform's horizontal centre level with your add (only just far enough, so no closer); otherwise yours is <b>crossed</b>, at the middle of the platform's outer edge (top on the northern platform, bottom on the southern).</span>`);
        spotHits(dpsCandidates(), answerSpot);
      }
      else if(st.step === 2){
        drawCast();
        pill('Step 2 · Soak or bait');
        instr(`The bright souls are dropping <span class="hl">${aspectLabel(st.bright)}</span> towers — ${lightWord(st.bright)} ones. Your tether is <span class="hl">${lightWord(st.myColor)}</span>. What is your job for the towers?<span class="hint"> Only the <b>opposite</b> colour can soak a tower, so the matching pair baits White Flame instead.</span>`);
        drawZones([
          { id:'soak', label:'SOAK', sub:'an aspected tower',   icon:'#icon-stack' },
          { id:'bait', label:'BAIT', sub:'a White Flame laser', icon:'#icon-hold'  }
        ], answerJob);
      }
      else {
        drawCast('pre3');
        if(st.job === 'soak'){
          pill('Step 3 · Take your tower');
          instr(`Two ${lightWord(st.bright)} towers are down. Your tether is the <span class="hl">${st.straight ? 'straight' : 'crossed'}</span> one — which tower is yours?<span class="hint"> The <b>straight</b> tether takes the tower on the platform, the <b>crossed</b> tether the one pushed to the middle.</span>`);
          spotHits([
            { id:'tile',   x:st.home.cx, y:st.home.cy, mark:'A' },
            { id:'centre', x:300, y:300, mark:'B' }
          ], answerTowerPick);
        } else {
          pill('Step 3 · Bait the laser');
          instr(`Your colour matches the towers, so they are not yours. <span class="hl">Enchained Soul</span> keeps you on your own tile — click the spot you bait a <span class="hl">yellow-crystal add</span> from.<span class="hint"> Take the <b>corner facing an add</b>: you and the + or X support on the platform beside it are its two nearest players, so it fires one line at each of you.</span>`);
          const adds = document.getElementById('p3-adds');
          [st.addN, st.addS].forEach(ad => {
            adds.appendChild(el('circle', { cx:ad.x, cy:ad.y, r:22, fill:'none',
              stroke:'var(--aether)', 'stroke-width':2.5, class:'pulse' }));
          });
          spotHits(baitSpots(), answerBait);
        }
      }
    }

    // Pinned to your own tile, the only bait spots are its corners. Two of them face a
    // yellow-crystal add; the third is the corner pointing back at the arena centre.
    function baitSpots(t){
      // every spot hugs the tile edge, 12 units in, so you are pressed as close to the add
      // as Enchained Soul lets you get
      t = t || st.home;
      const inset = 12;
      const clamp = ad => [
        Math.min(Math.max(ad.x, t.x + inset), t.x + t.w - inset),
        Math.min(Math.max(ad.y, t.y + inset), t.y + t.h - inset)
      ];
      const n = clamp(st.addN), sp = clamp(st.addS);
      return [
        { id:'addN', x:n[0],  y:n[1],  r:20, ariaLabel:'Spot facing the northern add' },
        { id:'addS', x:sp[0], y:sp[1], r:20, ariaLabel:'Spot facing the southern add' },
        { id:'inner', r:20, ariaLabel:'Corner facing the arena centre',
          x: t.col === 'L' ? t.x + t.w - inset : t.x + inset,
          y: t.row === 2   ? t.y + t.h - inset : t.y + inset }
      ];
    }

    // Each yellow-crystal add fires a line at each of its two nearest players: the support on
    // the platform beside it, and the DPS who stepped up to bait it.
    // Each yellow-crystal add fires a line at each of its two nearest players, wherever they stand.
    function drawWhiteFlame(pos){
      const host = document.getElementById('p3-chains');
      const people = Object.keys(pos).map(k => pos[k]);
      [st.addN, st.addS].forEach(ad => {
        people.slice().sort((p, q) => dist(p, [ad.x, ad.y]) - dist(q, [ad.x, ad.y])).slice(0, 2).forEach(t => {
          const dx = t[0] - ad.x, dy = t[1] - ad.y;
          const len = Math.hypot(dx, dy) || 1;
          const ex = ad.x + dx / len * 900, ey = ad.y + dy / len * 900;
          const common = { x1:ad.x, y1:ad.y, x2:ex, y2:ey,
            'clip-path':'url(#arenaClip)', 'pointer-events':'none' };
          host.appendChild(el('line', Object.assign({}, common, {
            stroke:'var(--aether)', 'stroke-width':68, opacity:0.18 })));
          host.appendChild(el('line', Object.assign({}, common, {
            stroke:'var(--aether-soft)', 'stroke-width':2, opacity:0.5, 'stroke-dasharray':'9 6' })));
        });
      });
    }
    // Every spot a tethered DPS could plausibly take: both stances on each middle platform,
    // plus the two support platforms.
    function spotId(t, straight){ return t.key + (straight ? 'S' : 'C'); }

    function dpsCandidates(){
      const out = [];
      [st.midW, st.midE].forEach(t => {
        dpsSpots(t).forEach(d => {
          out.push({
            id: spotId(t, d.straight), x:d.x, y:d.y, r:18,
            label: d.straight ? 'straight' : 'crossed',
            labelSide: t.col === 'L' ? 'start' : 'end',
            ariaLabel: tileName(t) + ' platform, ' + (d.straight ? 'straight' : 'crossed') + ' tether spot'
          });
        });
      });
      [st.north, st.south].forEach(t => {
        out.push({ id: t.key + 'X', x:t.cx, y:t.cy, r:18, ariaLabel: tileName(t) + ' platform' });
      });
      return out;
    }

    function aoeSpots(){
      const t = st.home;
      const cornerX = t.col === 'L' ? 60 : 540;
      const cornerY = t.row === 1 ? 60 : 540;
      const innerY  = t.row === 1 ? 180 : 420;
      return [
        { id:'corner',   x:cornerX, y:cornerY, mark:'A', label:'Outer arena corner' },
        { id:'cardinal', x:300,     y:cornerY, mark:'B', label:'Cardinal wall point' },
        { id:'inner',    x:300,     y:innerY,  mark:'C', label:'Inner corner, toward the middle' }
      ];
    }

    /* ---------- answers ---------- */
    function judge(ok, title, why, next){
      if(ok){
        const last = next > 3;
        showFeedback(fb, true, title, why,
          last ? 'New pull ↻' : 'Continue → Step ' + next,
          last ? () => newRound() : () => { st.step = next; render(); if(next === 2) fireTethers(); });
      } else {
        showFeedback(fb, false, title, why, 'New pull ↻', () => newRound());
      }
    }

    // DPS: the platform and the stance on it are one answer.
    function answerSpot(id){
      lock();
      const ok = id === spotId(st.home, st.straight);
      layer('p3-hits');
      drawCast();
      const far = st.mySide === 'west' ? 'east' : 'west';
      const lead = `Your add is on the <b>${st.mySide}</b> wall, so you cross to the <b>mid ${far}</b> platform — both DPS from one wall share that tile, and the distance is what cuts the proximity damage.`;
      const why = st.straight
        ? lead + ` Your add lines up with that platform, so yours is the <b>straight</b> tether: stand at its <b>horizontal centre, level with your add</b>, so your laser runs dead east–west. That is only just the minimum stretch your tether needs, so do not stand any closer to the add.`
        : lead + ` Your add does not line up with it, so yours is the <b>crossed</b> tether: stand at the <b>middle of the platform's outer edge</b> — ${st.home.row === 2 ? 'top middle, as this is the northern middle platform' : 'bottom middle, as this is the southern middle platform'} — so your laser angles across. Together the two lasers leave an outer gap on the plain tower for the support.`;
      judge(ok, ok ? 'Good spot' : 'Wrong spot', why, 2);
    }

    function answerTile(key){
      lock();
      const ok = key === st.home.key;
      let why;
      if(shared.role === 'support'){
        if(st.mySoul === 'quartered'){
          why = `Quartered Soul always takes the tower on the <b>north-most</b> platform — this pull that is the ${st.north.col === 'L' ? 'west' : 'east'} tile on the top row.`;
        } else if(st.mySoul === 'xmarked'){
          why = `X-marked Soul always takes the tower on the <b>south-most</b> platform — this pull the ${st.south.col === 'L' ? 'west' : 'east'} tile on the bottom row.`;
        } else {
          const first = st.brightSlots[0], second = st.brightSlots[1];
          why = `The bright souls went to <b>${first}</b> and <b>${second}</b>. Priority runs west to east as H1 &gt; T1 &gt; T2 &gt; H2, so ${first} takes the tower on the <b>mid west</b> platform and ${second} the one on <b>mid east</b>. You are ${st.mySlot}. Soak it from its side <b>away from the arena's horizontal centre line</b>: the DPS on your platform stretch their tethers right beside it, and you have to stand in the outer gap their two lasers leave, or one clips you.`;
        }
      }
      judge(ok, ok ? 'Right tower' : 'Wrong tower', why, 2);
    }

    function answerTower(id){
      lock();
      const ok = id === st.towerSpot;
      const same = st.myDpsColor === st.bright;
      const why = same
        ? `Your tower is <b>${lightWord(st.bright)}</b> and so are the two DPS on your tile, so they cannot take it. Drop it on the <b>arena-centre corner</b> of your tile and it spills onto the other middle platform, where the ${lightWord(st.bright === 'astral' ? 'umbral' : 'astral')} pair is waiting.`
        : `Your tower is <b>${lightWord(st.bright)}</b> and the DPS on your tile are <b>${lightWord(st.myDpsColor)}</b> — opposite colours, so they can soak it. Drop it in the <b>middle of your own tile</b>, clear of their tether lasers.`;
      const t = layer0();
      tower(t, st.towerSpot === 'centre' ? 300 : st.home.cx, st.towerSpot === 'centre' ? 300 : st.home.cy, st.bright, null);
      judge(ok, ok ? 'Tower placed' : 'Wrong spot', why, 3);
    }

    function answerAoe(id){
      lock();
      const correct = st.mySoul === 'quartered' ? 'corner' : 'cardinal';
      const ok = id === correct;
      const spots = aoeSpots();
      // the AoE lands where you chose to stand, so a wrong spot shows what it cuts through
      const picked = spots.find(s => s.id === id);
      const host = layer0();
      if(st.mySoul === 'quartered') drawPlus(host, picked.x, picked.y); else drawSaltire(host, picked.x, picked.y);
      const why = st.mySoul === 'quartered'
        ? `The plus is locked to true north, so from the <b>outer arena corner</b> both arms run along the walls and never cross the middle. From a cardinal point one arm would cut straight through the platforms.`
        : `The X is locked to true north, so from the <b>cardinal wall point</b> its arms run out to the corners and leave the middle clear. From the arena corner one arm would go right through the centre.`;
      judge(ok, ok ? 'AoE placed' : 'That clips the party', why, 3);
    }

    function answerJob(id){
      lock();
      const ok = id === st.job;
      const why = st.job === 'soak'
        ? `Your tether is <b>${lightWord(st.myColor)}</b> and the towers are <b>${lightWord(st.bright)}</b>. Opposite colours soak, so both towers are yours and your partner's.`
        : `Your tether is <b>${lightWord(st.myColor)}</b> and so are the towers. Matching colours cannot soak, so your pair leaves the towers to the other platform and baits White Flame instead.`;
      judge(ok, ok ? 'Right job' : 'Wrong job', why, 3);
    }

    function answerTowerPick(id){
      lock();
      const ok = id === st.towerPick;
      layer('p3-hits');
      resolveLast(id === 'tile' ? towerSpots().tile : centreCorner(st.home, 16));
      const why = st.straight
        ? `Yours is the <b>straight</b> tether, so you take the tower sitting <b>on your platform</b> and leave the centre one to the crossed tether.`
        : `Yours is the <b>crossed</b> tether, so you take the tower in the <b>middle of the arena</b> — the one the other support pushed over the corner — and leave the platform tower to the straight tether.`;
      judge(ok, ok ? 'Paradeigma III cleared' : 'Wrong tower', why, 4);
    }

    function answerBait(id){
      lock();
      const ok = id === 'addN' || id === 'addS';
      layer('p3-hits');
      const spot = baitSpots().find(sp => sp.id === id);
      const pos = positions('res3');
      pos[myKey()] = [spot.x, spot.y];
      // your partner takes the corner you left free
      if(id === 'addN' || id === 'addS'){
        const other = baitSpots().find(sp => sp.id === (id === 'addN' ? 'addS' : 'addN'));
        pos[dpsKey(st.home, !st.straight)] = [other.x, other.y];
      }
      drawCast('res3', pos);
      drawWhiteFlame(pos);
      judge(ok, ok ? 'Paradeigma III cleared' : 'Not a bait spot',
        `Enchained Soul keeps you on your tile, so you bait from its <b>corner</b>. Take the one facing a yellow-crystal add: you and the <b>+</b> or <b>X</b> support on the platform beside it are its two nearest players, so it fires one line at each of you. Your pair splits, one add each. The corner pointing back at the middle leaves you too far to bait and puts the line across the platforms.`,
        4);
    }

    // where a support ends up for each last-job answer; Enchained Soul keeps you on your own tile
    function lastJobSpot(id){
      const t = st.home, tw = towerSpots();
      const nearestTower = dist([t.cx, t.cy], tw.tile) <= dist([t.cx, t.cy], tw.centre) ? tw.tile : tw.centre;
      if(st.mySoul === 'bright'){
        if(id === 'soak') return t.key === soakTile().key ? tw.tile : centreCorner(t, 16);
        if(id === 'bait'){
          const ad = dist([t.cx, t.cy], [st.addN.x, st.addN.y]) <= dist([t.cx, t.cy], [st.addS.x, st.addS.y]) ? st.addN : st.addS;
          return clampTo([ad.x, ad.y], t, 12);
        }
        return null;                                   // step aside: where everyone expects you
      }
      if(id === 'soak') return clampTo(nearestTower, t, 14);
      if(id === 'hold') return aoeSpot(t, st.mySoul);   // out on the wall, right where your own AoE lands
      return null;                                     // bait: at your add
    }

    function answerLast(id){
      lock();
      let correct, why;
      if(shared.role === 'support' && st.mySoul === 'bright'){
        correct = 'clear';
        why = `The tower you dropped belongs to a DPS, not to you — you already soaked the plain one. <b>Step aside</b> and make sure you are not standing in a tower or in the + and X AoEs.`;
      } else if(shared.role === 'support'){
        correct = 'bait';
        why = `Once your AoE is down you move in and <b>bait White Flame</b> from the add beside your platform, pointing the line away from the middle. Your ${st.mySoul === 'quartered' ? 'plus' : 'X'} is <b>delayed</b>, so get out of its arms first and stay out while you bait${st.mySoul === 'xmarked' ? ': one arm runs straight through your add, so bait from a step towards the outer wall' : '. The add’s other line runs from it to the DPS baiting it, so bait from behind the add, well clear of that line’s edge — standing right beside the add puts you on its edge'}. Each of the two adds needs two baiters: you and one of the DPS whose colour matched the towers.`;
      } else {
        correct = 'away';
        why = `<b>Bait the line away from the middle</b> so it does not sweep the platforms. You and one of the + or X supports take one add each.`;
      }
      const ok = id === correct;
      // A + or X support has no tower within reach: Enchained Soul pins them to a platform with the
      // floor gone all round it.
      if(shared.role === 'support' && st.mySoul !== 'bright' && id === 'soak'){
        fallOff();
        judge(false, 'You fell off the platform',
          `You try to soak a tower and fall off the platform.<br><br><i>Enchained Soul will not let you jump. The void below the Twelfth Circle is very, very dark. Honey B will mourn your soul ❤️ </i><br><br><b>*** You have died ***</b><br><br>The aspected towers belong to the DPS on the middle platforms anyway. ${why}`, 4);
        return;
      }
      resolveLast(lastJobSpot(id));
      judge(ok, ok ? 'Paradeigma III cleared' : 'Not your job', why, 4);
    }

    // Step off the edge towards the nearest tower, fade away, and leave White Flame to whoever is left.
    function fallOff(){
      const t = st.home, tw = towerSpots();
      const toward = dist([t.cx, t.cy], tw.tile) <= dist([t.cx, t.cy], tw.centre) ? tw.tile : tw.centre;
      const pos = positions('res3');
      const edge = clampTo(toward, t, -22);                // just past the platform's edge
      delete pos[myKey()];
      drawCast('res3', Object.assign({}, pos, { [myKey()]: edge }));
      drawWhiteFlame(pos);
      const me = [...document.querySelectorAll('#p3-actors > g')].find(g => g.querySelector('.pulse'));
      if(me){
        me.setAttribute('opacity', '0.35');
        const drop = el('text', { x: edge[0], y: edge[1] - 24, 'text-anchor':'middle', 'font-family':'Space Mono, monospace',
          'font-size':11, 'font-weight':700, fill:'var(--bad)', 'pointer-events':'none' });
        drop.textContent = 'AAAaaa…';
        document.getElementById('p3-actors').appendChild(drop);
      }
    }

    const newRound = T.trackRounds('para3', startRound);
    shared.roleListeners.push(newRound);
    newRound();
  }

  T.register({ id: 'para3', label: 'Paradeigma III', phase: 'Athena', players: 'supports', playersNote: 'Supports are seated by the H1, T1, T2, H2 priority, so each has their own place; all four DPS play it the same way.', markup: MARKUP, init: initPara3 });
})(window.Twelfth);
