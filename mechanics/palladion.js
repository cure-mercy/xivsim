/* Palladion (limit cut): follow Athena dash by dash and take, dodge or bait each one. */
(function(T){

  const { showFeedback } = T;

  const MARKUP = /* html */ `
  <div class="layout" id="panel-palladion" role="tabpanel" aria-labelledby="tabBtn-palladion" hidden>

    <section class="arena-wrap">
      <div class="step-row">
        <span class="step-pill" id="p4-stepPill">Step 1 · Starting spot</span>
      </div>

      <svg class="arena-svg" id="p4-arena" style="--zone-band: 23.09%" viewBox="48.8 36.8 502.4 630.4" role="img" aria-label="Top-down view of the compressed octagonal arena during Palladion">
        <rect x="60" y="60" width="480" height="480" rx="6" fill="url(#floor)" pointer-events="none"/>
        <image href="assets/arena-phase1.svg" x="60" y="60" width="480" height="480" preserveAspectRatio="none" pointer-events="none"/>

        <!-- Ultima Blade compresses the floor to an octagon. Drawn inscribed in the board so the
             usable ground fills it; everything outside the octagon is a lethal AoE. -->
        <path d="M60 60 H540 V540 H60 Z M300 60 L469.7 130.3 L540 300 L469.7 469.7 L300 540 L130.3 469.7 L60 300 L130.3 130.3 Z"
              fill-rule="evenodd" fill="rgba(226,82,63,0.22)" pointer-events="none"/>
        <polygon points="300,60 469.7,130.3 540,300 469.7,469.7 300,540 130.3,469.7 60,300 130.3,130.3"
                 fill="none" stroke="rgba(226,82,63,0.65)" stroke-width="2" stroke-dasharray="9 6" pointer-events="none"/>

        <g id="p4-marks"></g>
        <g id="p4-actors"></g>
        <g id="p4-hits"></g>
        <g id="p4-zones"></g>

        <rect x="60" y="60" width="480" height="480" rx="6" fill="none" stroke="rgba(247,147,30,0.55)" stroke-width="2" filter="url(#glow)" pointer-events="none"/>
      </svg>

      <p class="arena-caption">The board is turned so Athena's corner, relative north, is always at the top. In the fight she can pick any corner, and every call is read from hers.</p>

      <div class="feedback" id="p4-feedback" hidden aria-live="polite"></div>
    </section>

    <aside class="hud">
      <div class="card">
        <h2>Your number</h2>
        <div class="lc-row">
          <div class="lc-num" id="p4-num">1</div>
          <p class="assign-text hint-only" id="p4-assignText"></p>
        </div>
      </div>

      <div class="card">
        <h2>Objective</h2>
        <p class="instr-text" id="p4-instrText"></p>
      </div>

      <details class="card">
        <summary>How the call works</summary>
        <ol>
          <li><b>Ultima Blade</b> shrinks the arena to an octagon ringed by a lethal edge and summons eight adds, which fly off and then return to the middle one per dash.</li>
          <li><b>Palladion</b> puts a 1–8 marker on everyone. Athena reappears on a random corner, and that corner is <b>relative north</b> for the whole mechanic. Partners are <b>1+3, 2+4, 5+7, 6+8</b>.</li>
          <li>She dashes to each number in order. The dash lays a line AoE with proximity damage, then a point-blank that must be <b>shared with your partner</b> and leaves a blue puddle that kills on contact.</li>
          <li>Starting spots, all relative: <b>1/3 south</b> corner, <b>2/4 north-east</b> corner, <b>5/7 close to the middle</b> on the west side, <b>6/8 south-east</b> corner. 2 and 4 may start anywhere in the northern tiles off dash 1's path. They let the first dash land, then step into the corner Athena left to take the second; anywhere up there off dash 1's path would do, but the corner keeps the puddles packed.</li>
          <li>A <b>purple</b> add is Clear Cut, a 270° cone you can ignore; a <b>yellow</b> add fires <b>White Flame</b> at the two players nearest the middle. The first four adds are two of each in a <b>random order</b>, and the last four return in the <b>reverse</b> of that order.</li>
          <li>So <b>one pair always stands in</b> close to the middle, on its own half (1/3/5/7 west, 2/4/6/8 east), in the bait order <b>5/7 → 6/8 → 1/3 → 2/4</b>. On a purple add it holds; on a yellow add it spreads, takes one laser each and goes straight back out to the wall, and the next pair, holding at the wall until then, steps in on the next dash: a reposition close to the middle, or straight to Bait if that add is yellow too. While standing in, Hold and Bait both keep you there. A pair still owed a dash steps in as soon as its dashes are done, which is always in time. Everyone else stays against the wall.</li>
          <li>Only the first two dashes land in corners: 1 straight across from Athena, 2 in the corner she left. After your dash, move <b>clockwise to just outside your puddle</b>, as close to it as you can, and your second dash lands there. The pair that takes over steps just clockwise of that puddle in turn, so the puddles pack along the wall, <b>1-3-5-7</b> from the south corner and <b>2-4-6-8</b> from Athena's, and leave the rest of the wall free with less walking.</li>
          <li>Once a pair has taken both its dashes it <b>trades places</b> with the next dash pair: 5/7 take over from 1/3 after dash 3, and 6/8 from 2/4 after dash 4. 1/3 step straight in for the third lasers, unless 6/8 are baiting on dash 4 itself: then they wait at the wall first. 2/4 run <b>clockwise along the wall until a puddle stops them</b> and step in on the dash after 1/3 bait. After its lasers every pair goes back out to the wall: 1/3 just short of puddle 2, 2/4 just short of puddle 1.</li>
          <li>After the eighth dash everyone edges north, avoiding the puddles. Athena destroys the middle of the floor and casts <b>Theos's Ultima</b>, which splits its damage between everyone still alive.</li>
        </ol>
      </details>

      <div class="card">
        <h2>The middle add</h2>
        <div class="legend-list">
          <div class="legend-item"><svg viewBox="0 0 24 24" fill="var(--shape-purple)"><use href="#icon-add"/></svg><span><b>Purple glyph</b> — Clear Cut, a 270° cone in the middle.<span class="hint"> Ignore it.</span></span></div>
          <div class="legend-item"><svg viewBox="0 0 24 24" fill="var(--aether)"><use href="#icon-add"/></svg><span><b>Yellow glyph</b> — White Flame at the two nearest players.<span class="hint"> The pair standing in baits it.</span></span></div>
        </div>
      </div>
    </aside>

  </div>
  `;

  function initPalladion(){
    const SVGNS = 'http://www.w3.org/2000/svg';
    const RAD = Math.PI / 180;
    // The octagon wall is drawn at 240 so it fills the board. Players walk a ring just inside it, and
    // puddles are allowed to spill over the wall and off the board.
    const R_PATH = 216, R_BOSS = 216, R_LABEL = 58;
    const R_PUDDLE = 78, R_STACK = 40;
    // The pair standing in for the lasers waits this close to the middle add, on its own side.
    const R_STANDIN = 110;
    // A puddle dropped as close as possible to the last one: its centre sits where you stood, just
    // outside the old puddle's edge.
    const PACK = R_PUDDLE + 26;
    // How far a click may land from the spot and still count. Standing in counts anywhere in a ring
    // around the add: near enough to be one of its two nearest players, not on top of it.
    const TOL_START = 50, TOL_MOVE = 40;
    const STANDIN_MIN = 55, STANDIN_MAX = 150;
    // 5/7's last move may also go straight north, where the party meets for Theos's Ultima: anywhere this
    // far north of the add counts, which also keeps clear of dash 8's line across the middle.
    const NORTH_Y = 240;
    // Athena's dash path is about as wide as the add in the middle is across.
    const DASH_W = 36;
    // 2/4's loose spots, before dash 2: the northern tiles, down to the first tile line.
    const NORTH_TILES_Y = 180;
    const REL = ['N','NE','E','SE','S','SW','W','NW'];

    const GROUP_OF  = { 1:'13', 3:'13', 2:'24', 4:'24', 5:'57', 7:'57', 6:'68', 8:'68' };
    const PARTNER   = { 1:3, 3:1, 2:4, 4:2, 5:7, 7:5, 6:8, 8:6 };
    const PAIR_NAME = { '13':'1 and 3', '24':'2 and 4', '57':'5 and 7', '68':'6 and 8' };
    const DASHES    = { '13':[1,3], '24':[2,4], '57':[5,7], '68':[6,8] };
    const BAIT_ORDER = ['57', '68', '13', '24'];
    // Each pair baits the lasers from its own half: 1/3/5/7 west of the middle, 2/4/6/8 east.
    const HALF = { '13':'W', '57':'W', '24':'E', '68':'E' };
    const ORDINAL   = ['first', 'second', 'third', 'fourth'];

    let st = {};
    const fb = document.getElementById('p4-feedback');

    /* ---------- geometry ---------- */
    // half lets a marker sit between two corners
    function posAt(i, half, r){
      const a = (-90 + (i + half)*45) * RAD;
      return [300 + Math.cos(a)*r, 300 + Math.sin(a)*r];
    }
    function relOf(i){ return REL[(i - st.boss + 8) % 8]; }
    const dist = (p, q) => Math.hypot(p[0] - q[0], p[1] - q[1]);
    function inward(p, r){
      const dx = p[0] - 300, dy = p[1] - 300, len = Math.hypot(dx, dy) || 1;
      return [300 + dx / len * r, 300 + dy / len * r];
    }

    // The ring players walk, an octagon just inside the wall, measured clockwise from Athena's corner.
    const SIDE = 2 * R_PATH * Math.sin(22.5 * RAD);
    const PERIM = 8 * SIDE;
    function pathPt(s){
      s = ((s % PERIM) + PERIM) % PERIM;
      const k = Math.floor(s / SIDE), t = s / SIDE - k;
      const a = posAt(k, 0, R_PATH), b = posAt((k + 1) % 8, 0, R_PATH);
      return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
    }
    // The spot along the ring, clockwise (dir 1) or counter-clockwise (dir -1), just clear of the puddle at s.
    function packFrom(s, dir){
      const p = pathPt(s);
      let lo = PACK, hi = PACK * 1.1;
      for(let i = 0; i < 40; i++){
        const mid = (lo + hi) / 2;
        if(dist(pathPt(s + dir * mid), p) < PACK) lo = mid; else hi = mid;
      }
      return s + dir * hi;
    }

    // The first two dashes land in corners: 1 straight across from Athena, 2 in the corner she left.
    // Every later puddle packs clockwise against the one before it on that side, 1-3-5-7 and 2-4-6-8.
    const ALONG = { 1: 4 * SIDE, 2: 0 };
    for(let n = 3; n <= 8; n++) ALONG[n] = packFrom(ALONG[n - 2], 1);
    const DASH = {};
    for(let n = 1; n <= 8; n++) DASH[n] = pathPt(ALONG[n]);

    // Each pair's spot at the wall while it is neither dashing nor standing in. 1/3 and 2/4 run clockwise
    // off their dashes until a puddle stops them: 1/3 short of puddle 2, 2/4 short of puddle 1.
    const WALL = { '13': pathPt(packFrom(ALONG[2], -1)), '24': pathPt(packFrom(ALONG[1], -1)),
                   '57': posAt(6, 0, R_PATH), '68': posAt(3, 0, R_PATH) };
    const STANDIN = {};
    Object.keys(WALL).forEach(g => { STANDIN[g] = inward(WALL[g], R_STANDIN); });
    const OUT_57 = pathPt(packFrom(ALONG[7], 1));
    // Running clockwise until a puddle stops you counts anywhere from the octagon corner before that
    // puddle up to the spot just short of it: the south-east corner for 2/4 (puddle 1), the north-west
    // corner for 1/3 and for 5/7 leaving puddle 7 (puddle 2).
    const CORNER_BEFORE = { '24': posAt(3, 0, R_PATH), '13': posAt(7, 0, R_PATH), '57': posAt(7, 0, R_PATH) };
    const START = { '13': DASH[1], '24': posAt(1, 0, R_PATH), '57': STANDIN['57'], '68': WALL['68'] };

    /* ---------- the adds ---------- */
    // One add returns per dash. Among the first four, two are yellow (White Flame) and two purple (Clear
    // Cut) in a random order; the last four come back in the reverse of that order.
    function rollAdds(){
      const first = ['Y', 'Y', 'P', 'P'];
      for(let i = first.length - 1; i > 0; i--){
        const j = Math.floor(Math.random() * (i + 1));
        [first[i], first[j]] = [first[j], first[i]];
      }
      return [null].concat(first, first.slice().reverse());
    }

    // Every pair's job on every dash, for this pull's adds. One pair always stands in near the middle, in
    // the bait order; it takes the lasers when a yellow add appears and goes straight back out while the
    // next pair steps in. A pair still owed a dash steps in once its dashes are done, which is always in
    // time: 1/3 are free from dash 4, and no third laser set can come before dash 5.
    // `early57` is set once you, as 5 or 7, have already moved to the dash 5 spot on dash 3.
    function buildPlan(adds, early57){
      const ys = [];
      for(let n = 1; n <= 8; n++) if(adds[n] === 'Y') ys.push(n);
      const plan = { '13':[], '24':[], '57':[], '68':[] };
      const set = (g, n, e) => { plan[g][n - 1] = e; };
      const take = { act:'take' }, dashTo = d => ({ act:'move', kind:'dash', dash:d });
      const stepIn = { act:'move', kind:'stepin' }, toWall = { act:'move', kind:'swap' };
      const standBy = { act:'hold', standin:true }, wall = { act:'hold' }, bait = { act:'bait' };
      // From beat `from`: step in (unless the pair is in already), stand in, bait on the pair's yellow add,
      // then back at the wall until beat `to`. If the yellow add comes on the very beat the pair steps in,
      // stepping in and baiting are one move.
      const laserRun = (g, from, to, alreadyIn) => {
        const y = ys[BAIT_ORDER.indexOf(g)];
        for(let n = from; n <= to; n++){
          if(plan[g][n - 1]) continue;
          set(g, n, n === y ? bait : n > y ? wall : (!alreadyIn && n === from ? stepIn : standBy));
        }
      };

      // 5/7: in from the start and bait the first set, then take over the south dashes after dash 3
      // After baiting on dash 1 or 2, 5/7 may hold at the wall through dash 3 and move on dash 4, the dash
      // before their own; moving over on dash 3 counts too.
      const moveIn57 = ys[0] < 3 && early57 ? 3 : 4;
      set('57', moveIn57, dashTo(5));
      if(moveIn57 === 3) set('57', 4, { act:'hold', dashSpot:true });
      else if(ys[0] < 3) set('57', 3, { act:'hold', early:5 });
      laserRun('57', 1, 4, true);
      set('57', 5, take); set('57', 6, dashTo(7)); set('57', 7, take);
      set('57', 8, { act:'move', kind:'out' });

      // 6/8: hold at the wall while 5/7 take their lasers, step in on the next dash, bait the second set,
      // then the north dashes
      for(let n = 1; n <= ys[0]; n++) set('68', n, wall);
      laserRun('68', ys[0] + 1, 4, false);
      set('68', 5, dashTo(6)); set('68', 6, take); set('68', 7, dashTo(8)); set('68', 8, take);

      // 1/3: the south dashes, then straight in for the third set; if 6/8 are baiting on dash 4 itself,
      // to the wall first and in on dash 5
      set('13', 1, take); set('13', 2, dashTo(3)); set('13', 3, take);
      set('13', 4, ys[1] === 4 ? toWall : stepIn);
      laserRun('13', 5, 8, ys[1] !== 4);

      // 2/4: the north dashes, to the wall while 1/3 have the lasers, then in on the dash after theirs
      set('24', 1, dashTo(2)); set('24', 2, take); set('24', 3, dashTo(4)); set('24', 4, take);
      set('24', 5, toWall);
      for(let n = 6; n <= ys[2]; n++) set('24', n, wall);
      laserRun('24', ys[2] + 1, 8, false);
      return { plan, ys };
    }

    // Where a pair stands before and after each beat. Standing in and baiting spread the pair a little
    // wider and count as being in the middle; after baiting it is back at its wall spot for the next beat.
    function trackPositions(plan){
      const pre = {}, post = {}, target = {};
      Object.keys(plan).forEach(g => {
        let cur = { at: START[g], wide: g === '57', mid: g === '57', dash: g === '13' ? 1 : 0 };
        pre[g] = []; post[g] = []; target[g] = [];
        for(let n = 1; n <= 8; n++){
          const e = plan[g][n - 1];
          pre[g][n] = cur;
          if(e.act === 'take') cur = { at: DASH[n], wide:false, dash:n };
          else if(e.act === 'move'){
            const at = e.kind === 'dash' ? DASH[e.dash] : e.kind === 'stepin' ? STANDIN[g]
              : e.kind === 'swap' ? WALL[g] : OUT_57;
            cur = { at, wide: e.kind === 'stepin', mid: e.kind === 'stepin', dash: e.kind === 'dash' ? e.dash : 0 };
            target[g][n] = at;
          }
          if(e.act === 'bait'){
            post[g][n] = { at: STANDIN[g], wide:true, mid:true };
            cur = { at: WALL[g], wide:false };
          } else post[g][n] = cur;
        }
      });
      const mid = (g, n, when) => !!(when === 'pre' ? pre : post)[g][n].mid;
      return { pre, post, target, mid };
    }

    // How the other pairs are drawn. A pair about to step in for its lasers is shown stepping in as soon as
    // the set before it has been taken, not a dash later, so the middle never looks empty when it is not.
    // Your own pair follows the real plan, since stepping in is one of your answers.
    function shownTrack(track, plan){
      const pre = {}, post = {};
      Object.keys(plan).forEach(g => {
        pre[g] = track.pre[g].slice();
        post[g] = track.post[g].slice();
        if(g === st.group) return;
        for(let m = 2; m <= 8; m++){
          const e = plan[g][m - 1];
          const entering = (e.act === 'move' && e.kind === 'stepin') || (e.act === 'bait' && !track.pre[g][m].mid);
          if(!entering || plan[g][m - 2].act === 'take') continue;
          const inMiddle = { at: STANDIN[g], wide:true, mid:true };
          post[g][m - 1] = inMiddle;
          pre[g][m] = inMiddle;
        }
      });
      return { pre, post };
    }

    // One player's own marker: partners sit side by side. `where` is 'stack' (the middle, before the
    // numbers go out), 'start', or [n, 'pre' | 'post'] around dash n.
    function numAt(num, where){
      if(where === 'stack') return posAt(num - 1, 0, R_STACK);
      const g = GROUP_OF[num];
      const src = g === st.group ? st.track : st.shown;
      const s = where === 'start' ? src.pre[g][1] : src[where[1]][g][where[0]];
      const dx = s.at[0] - 300, dy = s.at[1] - 300, len = Math.hypot(dx, dy) || 1;
      // On a dash spot the number Athena comes for stands right on it, where her dash ends, and the
      // partner beside it on the clockwise side, away from the last puddle.
      if(s.dash){
        const gap = num === s.dash ? 0 : 24;
        return [s.at[0] - dy / len * gap, s.at[1] + dx / len * gap];
      }
      const side = (num === 1 || num === 2 || num === 5 || num === 6) ? -1 : 1;
      const gap = s.wide ? 26 : 12;
      return [s.at[0] - dy / len * gap * side, s.at[1] + dx / len * gap * side];
    }
    // Who is standing in for the lasers as dash n goes out, if anyone still is.
    function standInAt(n){
      const k = st.ys.filter(y => y < n).length;
      return k < 4 ? BAIT_ORDER[k] : null;
    }

    function distToSegment(p, a, b){
      const vx = b[0] - a[0], vy = b[1] - a[1];
      const t = Math.max(0, Math.min(1, ((p[0] - a[0]) * vx + (p[1] - a[1]) * vy) / (vx * vx + vy * vy)));
      return dist(p, [a[0] + vx * t, a[1] + vy * t]);
    }

    // Where 2/4 may stand before dash 2 comes to them: in the northern tiles, off dash 1's path.
    function northTiles(p){
      if(distToSegment(p, posAt(st.boss, 0, R_BOSS), DASH[1]) <= DASH_W / 2 + 12) return 'onDash';
      if(p[1] > NORTH_TILES_Y) return 'northTiles';
      return 'ok';
    }

    const APOTHEM = 240 * Math.cos(22.5 * RAD);
    function inOctagon(p){
      for(let i = 0; i < 8; i++){
        const a = (-90 + 22.5 + i * 45) * RAD;
        if((p[0] - 300) * Math.cos(a) + (p[1] - 300) * Math.sin(a) > APOTHEM) return false;
      }
      return true;
    }
    // What a clicked spot amounts to: off the edge, in a puddle, near enough, or too far. A null target
    // means standing in, which counts anywhere in the ring around the middle add.
    function verdict(p, target, tol, puddles, half){
      if(!inOctagon(p)) return { kind:'edge' };
      for(let k = 1; k <= puddles; k++) if(dist(p, DASH[k]) < R_PUDDLE) return { kind:'puddle', puddle:k };
      if(target) return { kind: dist(p, target) <= tol ? 'ok' : 'far' };
      const r = dist(p, [300, 300]);
      if(r < STANDIN_MIN) return { kind:'onAdd' };
      if(r > STANDIN_MAX) return { kind:'outer' };
      if(half && (half === 'W' ? p[0] >= 300 : p[0] <= 300)) return { kind:'wrongHalf', half };
      return { kind:'ok' };
    }
    function missNote(v){
      if(v.kind === 'edge') return `That spot is past the octagon's edge, which kills on contact.`;
      if(v.kind === 'puddle') return `That spot is inside puddle ${v.puddle}, which kills on contact.`;
      if(v.kind === 'wrongHalf') return v.half === 'W'
        ? `That spot is on the east half, and 1, 3, 5 and 7 bait from the <b>west</b> half.`
        : `That spot is on the west half, and 2, 4, 6 and 8 bait from the <b>east</b> half.`;
      if(v.kind === 'northTiles') return `That spot is too far south: 2 and 4 stay in the northern tiles, above the first tile line.`;
      if(v.kind === 'onDash') return `That spot is on dash 1's path, where Athena runs from her corner to 1.`;
      if(v.kind === 'onAdd') return `That spot is right on top of the add in the middle.`;
      if(v.kind === 'outer') return `That spot is too far out to be one of the two players nearest the middle add.`;
      return `That spot is too far from where you need to be.`;
    }

    /* ---------- what each beat is about ---------- */
    function whyText(g, n){
      const e = st.plan[g][n - 1];
      const p = `<b>${st.partner}</b>`;
      const baitIdx = BAIT_ORDER.indexOf(g), myYellow = st.ys[baitIdx];
      const prev = BAIT_ORDER[baitIdx - 1], next = BAIT_ORDER[baitIdx + 1];
      const sameSpot = ` Bait or a reposition close to the middle on your ${HALF[g] === 'W' ? 'west' : 'east'} half both count: they take you to the same spot.`;
      if(e.act === 'take'){
        const holdToo = ` Holding counts too: you are already standing where it lands.`;
        if(n === 1) return `Dash 1 comes straight to your corner. You and ${p} share the point-blank.` + holdToo;
        if(n === 2) return `Dash 2 arrives at the corner Athena left, where you are standing. Share it with ${p}.` + holdToo;
        if(n === 8) return `Dash 8 is the last one. Take it with ${p}, then everyone edges north for Theos's Ultima.` + holdToo;
        if(n === DASHES[g][0]) return `Dash ${n} comes to you, just clockwise of puddle ${n - 2}. Share it with ${p}.` + holdToo;
        return `Dash ${n} is your pair's second. Take it with ${p}.` + holdToo;
      }
      if(e.act === 'move'){
        if(e.kind === 'dash' && e.dash === 2) return `Let dash 1 land first, then <b>step back into the corner Athena just left</b>. Dash 2 comes to you wherever you stand, so any spot in the northern tiles clear of dash 1's path works, but the corner keeps puddle 2 tucked in and the wall free.`;
        if(e.kind === 'dash' && e.dash === DASHES[g][1]) return `Move <b>clockwise, to just outside your puddle</b>, as close to it as you can: dash ${e.dash} lands wherever you stand.`;
        if(e.kind === 'dash'){
          const before = e.dash === 5 ? '13' : '24';
          return `${PAIR_NAME[before]} have taken both their dashes. <b>Move to just clockwise of puddle ${e.dash - 2}</b>, as close to it as you can: dashes ${e.dash} and ${e.dash + 2} are yours now.`;
        }
        if(e.kind === 'stepin'){
          const lead = g === '13' && n === 4
            ? `Your dashes are done, and 6 and 8 took their lasers on dash ${st.ys[1]}`
            : `${PAIR_NAME[prev]} have just taken their lasers`;
          return `${lead}, so you are next in the bait order. <b>Step in close to the middle</b> now, before another yellow add can appear.${sameSpot}`;
        }
        if(e.kind === 'swap' && g === '13') return `Your dashes are done, but 6 and 8 are taking their lasers right now, so do not walk into the middle yet. <b>Run clockwise along the wall toward puddle 2</b> and wait between the north-west corner and it, then step in on the next dash.`;
        if(e.kind === 'swap') return `Your dashes are done. <b>Trade places with 6 and 8</b>: they take the dash spot, and you run clockwise along the wall toward puddle 1 and wait between the south-east corner and it. ${st.ys[2] === 5 ? '1 and 3 are taking their lasers right now, so step in on the next dash.' : 'Wait there until 1 and 3 have taken their lasers, then step in.'}`;
        return `Dash 7 was your last. <b>Step clockwise out of your puddle</b>, anywhere along the wall up to the north-west corner, or head straight north to where the party meets for Theos's Ultima, clear of the puddles and of dash 8's line across the middle.`;
      }
      if(e.act === 'bait'){
        const after = ` Spread apart from ${p}, take one laser each, then go straight back out to the wall${next ? ` so <b>${PAIR_NAME[next]}</b> can step in for the next set.` : `. That was the last set.`}`;
        if(!st.track.mid(g, n, 'pre')){
          const lead = g === '13' ? `6 and 8 took their lasers on dash ${st.ys[1]}` : `${PAIR_NAME[prev]} have just taken their lasers`;
          return `${lead}, and this add is <b>yellow</b> too, so step straight in close to the middle: you are next.${after}${sameSpot}`;
        }
        return `A <b>yellow</b> add: White Flame fires at the two players nearest the middle, and that is you and ${p}, standing in.${after} Holding counts too: you are already where the lasers go.`;
      }
      if(e.standin) return `A <b>purple</b> add: Clear Cut, which you can ignore. You are standing in for the lasers, so <b>stay close to the middle</b> until a yellow add appears.`;
      if(e.dashSpot) return `You are already in the dash spot. <b>Hold</b> while dash 4 lands, clear of the middle.`;
      if(e.early) return `Your lasers are done, and dash 4 is not yours. <b>Hold at the wall</b> and move over on dash 4, the dash before your own; stepping just clockwise of puddle 3 already counts too.`;
      const done = myYellow < n ? 'Your lasers are done. ' : '';
      const s = standInAt(n);
      if(!s) return `${done}Every set of lasers is done. <b>Hold at the wall</b>, then edge north once the last dash lands.`;
      if(st.adds[n] === 'Y' && g === BAIT_ORDER[BAIT_ORDER.indexOf(s) + 1])
        return `${PAIR_NAME[s]} take these lasers, and you are next. <b>Hold at the wall</b> until they have: walking in now could put you nearer the add than them. Step in on the next dash.`;
      const them = st.adds[n] === 'Y' ? 'take these lasers' : 'are standing in for the lasers';
      return `${done}Not your dash, and ${PAIR_NAME[s]} ${them}. <b>Hold at the wall</b>, well away from the middle.`;
    }

    function rebuild(){
      const built = buildPlan(st.adds, st.early57);
      st.plan = built.plan;
      st.ys = built.ys;
      st.track = trackPositions(st.plan);
      st.shown = shownTrack(st.track, st.plan);
    }

    function startRound(){
      // The board is always turned so Athena's corner, relative north, sits at the top.
      st.boss  = 0;
      st.num   = 1 + Math.floor(Math.random() * 8);
      st.group = GROUP_OF[st.num];
      st.partner = PARTNER[st.num];
      st.adds = rollAdds();
      st.early57 = false;
      rebuild();
      st.step = 1;
      st.sub = false;
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
      document.querySelectorAll('#panel-palladion .hit').forEach(h => h.setAttribute('aria-disabled','true'));
    }

    function drawMarker(host, num, at, me){
      const [x, y] = at;
      const g = el('g', { class: 'player' + (me ? ' me' : num === st.partner ? ' related' : '') });
      host.appendChild(g);
      if(me) g.appendChild(el('circle', { cx:x, cy:y, r:20, fill:'none', stroke:'var(--mist)', 'stroke-width':2.5, class:'pulse' }));
      g.appendChild(el('circle', { cx:x, cy:y, r: me ? 15 : 12, fill:'rgba(10,9,22,0.92)',
        stroke: me ? 'var(--mist)' : 'var(--mist-dim)', 'stroke-width': me ? 2 : 1.5 }));
      const t = el('text', { x, y: y + (me ? 5 : 4), 'text-anchor':'middle',
        'font-family':'Space Mono, monospace', 'font-size': me ? 14 : 11, 'font-weight':700,
        fill: me ? 'var(--mist)' : 'var(--mist-dim)' });
      t.textContent = String(num);
      g.appendChild(t);
    }
    // The whole party at one moment; your own marker can be put somewhere else.
    function drawParty(host, where, meAt){
      for(let num = 1; num <= 8; num++) if(num !== st.num) drawMarker(host, num, numAt(num, where), false);
      drawMarker(host, st.num, meAt || numAt(st.num, where), true);
    }
    // After a miss: where you should have gone.
    function drawTarget(host, at){
      host.appendChild(el('circle', { cx:at[0], cy:at[1], r:19, fill:'rgba(111,207,151,0.14)',
        stroke:'var(--good)', 'stroke-width':2, 'stroke-dasharray':'5 4' }));
    }
    // White Flame on a yellow add: a laser from the middle through each of the two players baiting it.
    function drawLasers(host, n){
      const g = st.adds[n] === 'Y' ? standInAt(n) : null;
      if(!g) return;
      [DASHES[g][0], DASHES[g][1]].forEach(num => {
        const p = numAt(num, [n, 'post']);
        const end = inward(p, 330);
        host.appendChild(el('line', { x1:300, y1:300, x2:end[0], y2:end[1], stroke:'var(--aether)',
          'stroke-width':10, opacity:0.2, 'stroke-linecap':'round', 'clip-path':'url(#arenaClip)' }));
        host.appendChild(el('line', { x1:300, y1:300, x2:end[0], y2:end[1], stroke:'var(--aether-soft)',
          'stroke-width':2, opacity:0.85, 'clip-path':'url(#arenaClip)' }));
      });
    }

    function bossGlyph(host, x, y){
      const g = el('g', { filter:'url(#glow)' });
      g.appendChild(el('path', { d:'M0 -17 L5 -5 L17 0 L5 5 L0 17 L-5 5 L-17 0 L-5 -5 Z',
        fill:'var(--aether)', transform:`translate(${x},${y})` }));
      host.appendChild(g);
    }

    // The add in the middle, in the colour of the one that has just returned (grey before any has).
    function centreAdd(host, colour){
      const c = colour === 'Y' ? 'var(--aether)' : colour === 'P' ? 'var(--shape-purple)' : 'var(--mist-faint)';
      host.appendChild(el('circle', { cx:300, cy:300, r:18, fill:'rgba(10,9,22,0.9)', stroke:c, 'stroke-width':2 }));
      const u = el('use', { href:'#icon-add', x:288, y:288 });
      u.style.color = c;
      host.appendChild(u);
    }

    // Athena on her own corner, before the dashes start.
    function drawOpening(){
      const host = layer('p4-actors');
      const [bx, by] = posAt(st.boss, 0, R_BOSS);
      bossGlyph(host, bx, by);
      const [tx, ty] = posAt(st.boss, 0, R_BOSS + 28);
      const tag = el('text', { x:tx, y:ty + 4, 'text-anchor':'middle',
        'font-family':'Space Mono, monospace', 'font-size':11, 'font-weight':700,
        'letter-spacing':'0.1em', fill:'var(--aether-soft)' });
      tag.textContent = 'REL N';
      host.appendChild(tag);
      centreAdd(host, null);
      return host;
    }

    function drawPuddles(host, count){
      const clip = el('g', { 'clip-path':'url(#arenaClip)' });
      host.appendChild(clip);
      for(let k = 1; k <= count; k++){
        const [px, py] = DASH[k];
        clip.appendChild(el('circle', { cx:px, cy:py, r:R_PUDDLE, fill:'rgba(74,143,224,0.26)',
          stroke:'var(--umbral-soft)', 'stroke-width':1.5 }));
      }
      // numbers on top of every puddle, so an overlapping neighbour never hides one
      for(let k = 1; k <= count; k++){
        const [px, py] = inward(DASH[k], R_PATH - 52);
        const t = el('text', { x:px, y:py + 6, 'text-anchor':'middle',
          'font-family':'Space Mono, monospace', 'font-size':17, 'font-weight':700,
          fill:'var(--umbral-soft)', opacity:0.8 });
        t.textContent = String(k);
        host.appendChild(t);
      }
    }

    // One beat of the dash sequence: puddles so far, the dash going out now, Athena arriving, this dash's add.
    function drawDash(n){
      const host = layer('p4-actors');
      drawPuddles(host, n - 1);
      const from = n === 1 ? posAt(st.boss, 0, R_BOSS) : DASH[n - 1];
      const to = DASH[n];
      host.appendChild(el('line', { x1:from[0], y1:from[1], x2:to[0], y2:to[1],
        stroke:'var(--aether)', 'stroke-width':DASH_W, opacity:0.16, 'stroke-linecap':'round' }));
      host.appendChild(el('line', { x1:from[0], y1:from[1], x2:to[0], y2:to[1],
        stroke:'var(--aether)', 'stroke-width':2, 'stroke-dasharray':'7 5', class:'stripe' }));
      const clip = el('g', { 'clip-path':'url(#arenaClip)' });
      clip.appendChild(el('circle', { cx:to[0], cy:to[1], r:R_PUDDLE, fill:'none',
        stroke:'var(--astral)', 'stroke-width':2.5, class:'pulse' }));
      host.appendChild(clip);
      bossGlyph(host, to[0], to[1]);
      return host;
    }

    // Relative compass. During the dashes Athena has left her corner, so mark it here.
    function drawRelLabels(markNorth){
      const host = layer('p4-marks');
      for(let i = 0; i < 8; i++){
        if(!markNorth && i === st.boss) continue;
        const [x, y] = posAt(i, 0, R_LABEL);
        const isN = i === st.boss;
        const t = el('text', { x, y: y + 4, 'text-anchor':'middle',
          'font-family':'Space Mono, monospace', 'font-size':11, 'font-weight':700,
          'letter-spacing':'0.06em', fill: isN ? 'var(--aether-soft)' : 'var(--mist-faint)' });
        t.textContent = relOf(i);
        host.appendChild(t);
      }
    }

    // Freeform pick: click anywhere on the board. A ghost of your marker follows the pointer, and the
    // arrow keys move it for keyboard play, Enter confirms. The spot is kept on the element as data-x and
    // data-y, which is also where undo and redo read it back from.
    function freePick(from, onPick){
      const host = layer('p4-hits');
      const g = el('g', { class:'hit free-pick', tabindex:'0', role:'button', 'data-free':'',
        'data-x': from[0].toFixed(1), 'data-y': from[1].toFixed(1),
        'aria-label':'Pick a spot on the arena. Arrow keys move the marker, Enter confirms.' });
      g.appendChild(el('rect', { x:60, y:60, width:480, height:480, rx:6, class:'free-area' }));
      const ghost = el('g', { class:'free-ghost', 'pointer-events':'none', visibility:'hidden' });
      ghost.appendChild(el('circle', { cx:0, cy:0, r:17, class:'free-ring' }));
      const t = el('text', { x:0, y:5, 'text-anchor':'middle', 'font-family':'Space Mono, monospace',
        'font-size':13, 'font-weight':700, fill:'var(--aether-soft)' });
      t.textContent = String(st.num);
      ghost.appendChild(t);
      const place = p => {
        const x = Math.max(60, Math.min(540, p[0])), y = Math.max(60, Math.min(540, p[1]));
        g.setAttribute('data-x', x.toFixed(1));
        g.setAttribute('data-y', y.toFixed(1));
        ghost.setAttribute('transform', `translate(${x.toFixed(1)},${y.toFixed(1)})`);
        ghost.setAttribute('visibility', 'visible');
      };
      const current = () => [+g.getAttribute('data-x'), +g.getAttribute('data-y')];
      // the picked spot is written back, so a pull rebuilt by undo or redo ends up with the same markup
      const pick = p => {
        ghost.remove();
        g.setAttribute('data-x', p[0].toFixed(1));
        g.setAttribute('data-y', p[1].toFixed(1));
        onPick(p);
      };
      g.addEventListener('pointermove', e => { if(g.getAttribute('aria-disabled') !== 'true') place(T.freePoint(g, e)); });
      g.addEventListener('pointerleave', () => { if(document.activeElement !== g) ghost.setAttribute('visibility', 'hidden'); });
      g.addEventListener('focus', () => place(current()));
      g.addEventListener('blur', () => ghost.setAttribute('visibility', 'hidden'));
      g.addEventListener('click', e => pick(T.freePoint(g, e)));
      g.addEventListener('keydown', e => {
        const d = e.shiftKey ? 24 : 8;
        const move = { ArrowLeft:[-d, 0], ArrowRight:[d, 0], ArrowUp:[0, -d], ArrowDown:[0, d] }[e.key];
        if(move){ e.preventDefault(); const c = current(); place([c[0] + move[0], c[1] + move[1]]); return; }
        if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); pick(current()); }
      });
      host.appendChild(g);
      host.appendChild(ghost);
    }

    function drawZones(options, onPick){
      const host = layer('p4-zones');
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
    function pill(t){ document.getElementById('p4-stepPill').textContent = t; }
    function instr(h){ document.getElementById('p4-instrText').innerHTML = h; }
    const addWord = n => st.adds[n] === 'Y' ? '<span class="hl">yellow</span>' : '<span class="hl">purple</span>';

    function render(){
      document.getElementById('p4-num').textContent = String(st.num);
      document.getElementById('p4-assignText').innerHTML =
        `Partnered with <b>${st.partner}</b>, standing in for the <b>${ORDINAL[BAIT_ORDER.indexOf(st.group)]}</b> set of lasers. Limit cut numbers ignore role.`;
      layer('p4-marks'); layer('p4-actors'); layer('p4-hits'); layer('p4-zones');
      fb.hidden = true;

      if(st.step === 1){
        pill('Starting spot');
        drawParty(drawOpening(), 'stack');
        instr(`Athena has taken a corner and marked you <span class="hl">${st.num}</span>. Her corner is <span class="hl">relative north</span>, and the party is still stacked in the middle. Click where you start.<span class="hint"> <b>1 and 3</b> take the first dash in the corner straight across from her, <b>2 and 4</b> wait in the north-east corner off that line, <b>5 and 7</b> stand in close to the middle on the west side for the first lasers, and <b>6 and 8</b> hold in the south-east corner.</span>`);
        freePick(numAt(st.num, 'stack'), answerStart);
        return;
      }

      const n = st.step - 1;

      if(st.sub){
        pill('Dash ' + n + ' of 8 · where to');
        const host = layer('p4-actors');
        drawPuddles(host, n);
        centreAdd(host, st.adds[n]);
        drawParty(host, [n, 'pre']);
        drawRelLabels(true);
        // Neutral on purpose: nothing here says whether repositioning was the right call.
        instr(`You reposition. Click where you reposition to.<span class="hint"> Your pair's next dash lands wherever you stand, so step <b>clockwise to just outside the last puddle</b> on your side, as close to it as you can. Once your dashes are done, run clockwise along the wall until a puddle stops you, or step straight in close to the middle on your own half if you are next to bait: 1/3/5/7 west, 2/4/6/8 east.</span>`);
        freePick(numAt(st.num, [n, 'pre']), answerMove);
        return;
      }

      pill('Dash ' + n + ' of 8');
      const host = drawDash(n);
      centreAdd(host, st.adds[n]);
      drawParty(host, [n, 'pre']);
      drawRelLabels(true);
      instr(`Athena is diving to <span class="hl">${n}</span>, and a ${addWord(n)} add has returned to the middle. As <span class="hl">${st.num}</span>, what are you doing right now?<span class="hint"> You share a dash only on your own two numbers and reposition between them. One pair at a time stands in near the middle, in the order 5/7, 6/8, 1/3, 2/4: it baits only a yellow add, then goes back out as the next pair steps in.</span>`);
      drawZones([
        { id:'take', label:'TAKE IT',    sub:'share the dash',    icon:'#icon-stack'  },
        { id:'move', label:'REPOSITION', sub:'to your next spot', icon:'#icon-move'  },
        { id:'bait', label:'BAIT',       sub:'take the lasers',   icon:'#icon-spread' },
        { id:'hold', label:'HOLD',       sub:'stay where you are', icon:'#icon-hold'  }
      ], answerDash);
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
      if(n > 9) return { label:'New pull ↻', fn: () => newRound() };
      return { label:'Continue → Step ' + n, fn: () => { st.sub = false; st.step = n; render(); } };
    }

    function answerStart(p){
      lock();
      const standIn = st.group === '57';
      let v = verdict(p, standIn ? null : START[st.group], TOL_START, 0, HALF[st.group]);
      // 2/4 may start anywhere in the northern tiles off dash 1's path, and the marker stays put.
      let loose = false;
      if(st.group === '24' && v.kind === 'far'){
        v = { kind: northTiles(p) };
        loose = v.kind === 'ok';
      }
      const ok = v.kind === 'ok';
      const host = drawOpening();
      drawParty(host, 'start', ok && !loose ? null : p);
      if(!ok) drawTarget(host, numAt(st.num, 'start'));
      drawRelLabels(false);
      const why = {
        '13': `1 and 3 start in the <b>relative south</b> corner, straight across from Athena, because the first dash comes to you.`,
        '24': `2 and 4 start off the line the first dash will take, usually in the <b>relative north-east</b> corner. Anywhere in the northern tiles, above the first tile line, works as long as you keep off dash 1's path.`,
        '57': `5 and 7 are first in the bait order, so you start <b>standing in close to the middle</b>, spread a little and clear of the dash line, ready for the first yellow add.`,
        '68': `6 and 8 start in the <b>relative south-east</b> corner and wait there.`
      }[st.group];
      judge(ok, ok ? 'Right spot' : 'Wrong spot',
        (ok ? '' : missNote(v) + ' ') + why + ` Everything is read off Athena's corner, which is relative north this pull.`, stepTo(2));
    }

    const TITLE_OK = { take:'Yours to take', move:'Good move', bait:'Your lasers', hold:'Right to wait' };

    function answerDash(id){
      lock();
      const n = st.step - 1;
      const g = st.group, want = st.plan[g][n - 1].act;
      // Reposition is judged together with the spot you pick, so choosing it gives nothing away.
      if(id === 'move'){
        st.sub = true;
        render();
        return;
      }
      // A beat that ends with you standing in counts for Bait, and for Hold if you were in already.
      const endsIn = st.track.mid(g, n, 'post'), wasIn = st.track.mid(g, n, 'pre');
      const ok = id === want || (endsIn && (id === 'bait' || (id === 'hold' && wasIn))) || (want === 'take' && id === 'hold');
      if(ok){
        const host = drawDash(n);
        drawLasers(host, n);
        centreAdd(host, st.adds[n]);
        drawParty(host, [n, 'post']);
        layer('p4-zones');
      }
      const title = ok ? (n === 8 ? 'Palladion cleared' : id === want ? TITLE_OK[want] : 'Right call')
                       : (want === 'take' ? 'That dash is yours' : 'Not what you do here');
      judge(ok, title, whyText(g, n), stepTo(st.step + 1));
    }

    function answerMove(p){
      lock();
      const n = st.step - 1;
      const g = st.group, e = st.plan[g][n - 1];
      const endsIn = st.track.mid(g, n, 'post');
      // a wrong answer sends you back to the dash question, not the spot picker
      st.sub = false;
      // Moving to the dash 5 spot a dash early, or again once you stand on it, counts as well as holding.
      const dashSpotAlt = e.early || (e.dashSpot ? 5 : 0);
      if(e.act !== 'move' && !endsIn && !dashSpotAlt){
        // the mistake was choosing Reposition, so Undo goes back past the spot to the dash question
        fb.dataset.undoDepth = '2';
        judge(false, e.act === 'take' ? 'That dash is yours' : 'Not what you do here',
          `This is not a dash to reposition on. ${whyText(g, n)}`, stepTo(st.step + 1));
        return;
      }
      // Anywhere close to the middle counts for a beat that ends with you standing in.
      const middle = e.kind === 'stepin' || (e.act !== 'move' && endsIn);
      const target = dashSpotAlt ? DASH[dashSpotAlt] : st.track.target[g][n];
      let v = verdict(p, middle ? null : target, TOL_MOVE, n, HALF[g]);
      // Spots that count as well as the exact one, and keep your marker where you clicked: a spot close to
      // the middle, 5/7 finishing straight north, and for dash 2 anywhere in the northern tiles clear of
      // dash 1's path, since the dash comes to wherever you stand.
      let loose = middle && v.kind === 'ok';
      if(v.kind === 'far'){
        if(e.kind === 'out' && p[1] <= NORTH_Y) loose = true;
        if((e.kind === 'swap' || e.kind === 'out') && distToSegment(p, target, CORNER_BEFORE[g]) <= TOL_MOVE) loose = true;
        if(e.kind === 'dash' && e.dash === 2){
          v = { kind: northTiles(p) };
          loose = v.kind === 'ok';
        }
      }
      if(loose) v = { kind:'ok' };
      const ok = v.kind === 'ok';
      // moving over early changes where you stand from here on, so the plan follows you
      if(ok && e.early){ st.early57 = true; rebuild(); }
      const host = layer('p4-actors');
      drawPuddles(host, n);
      drawLasers(host, n);
      centreAdd(host, st.adds[n]);
      drawParty(host, [n, 'post'], ok && !loose ? null : p);
      if(!ok) drawTarget(host, numAt(st.num, [n, 'post']));
      const title = ok ? (n === 8 ? 'Palladion cleared' : 'Right move, right spot') : 'Right move, wrong spot';
      judge(ok, title, (ok ? '' : missNote(v) + ' ') + whyText(g, n), stepTo(st.step + 1));
    }

    const newRound = T.trackRounds('palladion', startRound);
    newRound();
  }

  T.register({ id: 'palladion', label: 'Palladion', phase: 'Athena', markup: MARKUP, init: initPalladion });
})(window.Twelfth);
