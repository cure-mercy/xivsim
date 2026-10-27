/* Paradeigma III: pick a surviving platform, place, and bait the White Flame lasers. */
(function(T){

  const { shared, shuffle, showFeedback, aspectColor, aspectSoft, aspectLabel, tiltIcon, el, dist } = T;

  const STYLES = /* css */ `
    /* Real time: the fight clock and the casts running, above the arena */
    .p3-live{ display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; border: 1px solid var(--line);
      border-radius: 12px; background: var(--nebula); }
    .p3-live-head{ display: flex; align-items: center; gap: 12px; }
    .p3-clock{ font-family: var(--font-mono); font-weight: 700; font-size: 1.05rem; color: var(--mist);
      font-variant-numeric: tabular-nums; }
    .p3-clock small{ font-size: 0.7rem; color: var(--mist-faint); font-weight: 400; margin-left: 4px; }
    .p3-live-note{ flex: 1; font-size: 0.8rem; color: var(--mist-dim); }
    .p3-casts{ display: flex; flex-direction: column; gap: 6px; min-height: 26px; }
    .p3-cast{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 3px 10px; font-size: 0.8rem; color: var(--mist-dim); }
    .p3-cast b{ color: var(--mist); font-weight: 600; }
    .p3-left{ font-family: var(--font-mono); font-variant-numeric: tabular-nums; color: var(--mist); }
    .p3-cast-bar{ grid-column: 1 / -1; height: 5px; border-radius: 3px; background: var(--line); overflow: hidden; }
    .p3-cast-bar i{ display: block; height: 100%; background: var(--aether); transform-origin: left center; }
    .p3-cast.mine .p3-cast-bar i{ background: var(--brand-soft); }
    .p3-cast.mine .p3-left{ color: var(--brand-soft); }
    .p3-idle{ font-size: 0.8rem; color: var(--mist-faint); }
    /* the mechanic resolving: the towers pop in, bursts as they and the Souls go off, the + and X flash */
    .p3-fx-pop, .p3-fx-burst{ transform-box: fill-box; transform-origin: center; }
    @media (prefers-reduced-motion: no-preference){
      .p3-fx-pop{ animation: p3-pop 0.45s ease-out both; }
      .p3-fx-burst{ animation: p3-burst 0.8s ease-out forwards; }
      .p3-fx-flash{ animation: p3-flash 1.1s ease-out forwards; }
    }
    @media (prefers-reduced-motion: reduce){ .p3-fx-burst, .p3-fx-flash{ display: none; } }
    @keyframes p3-pop{ from{ transform: scale(0.3); opacity: 0; } to{ transform: scale(1); opacity: 1; } }
    @keyframes p3-burst{ from{ transform: scale(0.55); opacity: 1; } to{ transform: scale(1.7); opacity: 0; } }
    @keyframes p3-flash{ 0%{ opacity: 0; } 15%{ opacity: 0.9; } 100%{ opacity: 0; } }
    /* the Soul to practise, for supports: any of the four Engravement of Souls hands out, or any of them */
    .p3-pick-label{ margin: 14px 0 8px; font-family: var(--font-mono); font-size: 0.7rem; letter-spacing: 0.14em;
      text-transform: uppercase; color: var(--mist-faint); }
    .role-select.p3-debuff-pick{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 6px; margin-bottom: 8px; }
    .p3-debuff-pick .role-btn{ padding: 6px 4px; gap: 2px; min-height: 40px; }
    .p3-debuff-pick .role-btn img{ width: 18px; height: 24px; object-fit: contain; display: block; }
    .p3-debuff-pick .p3-any{ font-size: 0.86rem; }
    /* the party never takes a click: the spot under them stays reachable */
    #p3-actors, #p3-tethers, #p3-towers, #p3-aoes{ pointer-events: none; }
    /* against the clock there is no stepping back: only a new pull */
    .layout.p3-timed .history-ctrls [data-history="undo"],
    .layout.p3-timed .history-ctrls [data-history="redo"],
    .layout.p3-timed .history-ctrls [data-history="rewind"]{ display: none; }
  `;

  const MARKUP = /* html */ `
  <div class="layout" data-dim="off" id="panel-para3" role="tabpanel" aria-labelledby="tabBtn-para3" hidden>

    <section class="arena-wrap">
      <div class="step-row">
        <span class="step-pill" id="p3-stepPill">Step 1 · Pick your platform</span>
      </div>

      <div class="p3-live" id="p3-live" hidden>
        <div class="p3-live-head">
          <span class="p3-clock" id="p3-clock">0.0<small>s</small></span>
          <span class="p3-live-note" id="p3-liveNote"></span>
          <button type="button" class="btn" id="p3-start">Start ▶</button>
        </div>
        <div class="p3-casts" id="p3-casts"></div>
      </div>

      <svg class="arena-svg" id="p3-arena" style="--zone-band: 16.67%" viewBox="0 0 600 672" role="img" aria-label="Top-down view of the Twelfth Circle arena split into eight tiles, four of them about to be destroyed">
        <rect x="60" y="60" width="480" height="480" rx="6" fill="url(#floor)"/>
        <image href="assets/arena-phase1.svg" x="60" y="60" width="480" height="480" preserveAspectRatio="none" pointer-events="none"/>
        <!-- Athena's target circle: one column width in radius, as in Paradeigma II -->
        <circle cx="300" cy="300" r="120" fill="none" stroke="rgba(247,147,30,0.45)" stroke-width="1.6" stroke-dasharray="4 6" pointer-events="none"/>

        <g id="p3-tiles"></g>
        <g id="p3-waymarks" pointer-events="none"></g>
        <g id="p3-chains"></g>
        <g id="p3-adds"></g>

        <!-- boss -->
        <g class="spin" filter="url(#glow)" pointer-events="none">
          <g transform="translate(300,300)" fill="var(--aether)">
            <path d="M0 -22 L6 -6 L22 0 L6 6 L0 22 L-6 6 L-22 0 L-6 -6 Z"/>
          </g>
        </g>
        <circle cx="300" cy="300" r="9" fill="var(--void)" stroke="var(--aether)" stroke-width="1.5" pointer-events="none"/>

        <g id="p3-towers"></g>
        <g id="p3-aoes"></g>
        <g id="p3-tethers"></g>
        <g id="p3-lasers" pointer-events="none"></g>
        <g id="p3-actors"></g>
        <g id="p3-fx" pointer-events="none"></g>
        <g id="p3-hits"></g>
        <g id="p3-zones"></g>

        <rect x="60" y="60" width="480" height="480" rx="6" fill="none" stroke="rgba(247,147,30,0.55)" stroke-width="2" filter="url(#glow)" pointer-events="none"/>
        <!-- after a wrong answer against the clock: where you should have been -->
        <g id="p3-target" pointer-events="none"></g>
        <!-- against the clock: click anywhere to run there -->
        <g id="p3-freeHits"></g>
      </svg>

      <p class="arena-caption">Four tiles survive in a zigzag. Once the others fall, Enchained Soul keeps everyone on the platform they are standing on.</p>

      <div class="feedback" id="p3-feedback" hidden aria-live="polite"></div>
    </section>

    <aside class="hud">
      <div class="card player-card">
        <div class="card-head">
          <h2>Pace</h2>
          <span class="info-tip">
            <button type="button" class="info-btn" aria-label="About the pace" aria-expanded="false" aria-describedby="p3-paceTip">?</button>
            <span class="info-pop" role="tooltip" id="p3-paceTip"><b>Step by step</b> pauses the fight at each step while you answer each call. <b>Real time</b> runs the fight clock from a log: click anywhere to move, and where you stand when each tower, laser, AoE and White Flame goes off is what counts. Once the tiles fall, walking off your platform drops you into the void. Drop your + or X away from its spot and the pull pauses with a warning, even if it hits nobody.</span>
          </span>
        </div>
        <div class="role-select player-select cols-2" role="group" aria-label="Choose the pace">
          <button type="button" class="role-btn" data-pace="steps"><span>Step by step</span></button>
          <button type="button" class="role-btn" data-pace="live"><span>Real time</span></button>
        </div>
      </div>

      <div class="card">
        <h2>Your debuffs</h2>
        <div class="assign-row" id="p3-badges"></div>
        <p class="assign-text hint-only" id="p3-assignText"></p>
        <div class="p3-pick-label" id="p3-pickLabel">Practise</div>
        <div class="role-select p3-debuff-pick" id="p3-debuffPick" role="group" aria-labelledby="p3-pickLabel"></div>
        <p class="player-note hint-only" id="p3-pickNote"></p>
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
          <li>Quartered Soul takes the <b>north-most</b> platform and X-marked the <b>south-most</b>. The two bright souls take the middle two by priority <b>H1 &gt; T1 &gt; T2 &gt; H2</b>, west to east: the first of them the western one, the other the eastern.</li>
          <li><b>Middle platforms:</b> the plain tower sits by the outer wall, right where the two DPS stretch their tethers, and their lasers run <b>east–west</b> across it. Soak it from its side <b>away from the arena's horizontal centre line</b>, in the gap the two lasers leave, or a DPS laser clips you.</li>
          <li>Each bright soul then drops an aspected tower. Compare your aspect with the tether colour of the two DPS on your tile: <b>same colour</b> and you drop it on the arena-centre corner so it spills onto the other middle platform; <b>opposite</b> and you drop it in the middle of your own tile, clear of the X's arm. Then step out of it.</li>
          <li>DPS stretch their tether to the <b>opposite</b> middle platform. The one whose add lines up with it has the <b>straight</b> tether and stands <b>level with the add on the line of waymark B or D</b> (B east, D west, 10 yalms out), so the laser runs dead east–west. That is 35 yalms from the add, only half a yalm past the 34.5 where a holder's own laser kills them outright, so right on the waymark's line: not a step closer, and no further out or the laser clips another player; the other has the <b>crossed</b> tether and stands at the <b>middle of the platform's outer edge</b> — top middle on the northern platform, bottom middle on the southern — so the laser angles across.</li>
          <li>The DPS pair whose colour is opposite the towers soaks them — <b>straight</b> tether takes the centre tower, <b>crossed</b> tether the one in the middle of the platform — waiting clear of the bright souls' small AoEs until they have gone off. The matching-colour pair, along with the + and X supports, bait the two <b>White Flame</b> lasers away from the middle: each DPS the yellow add closest to them, from the corner of their tile that faces it. The + and X are <b>delayed</b>: step out of your own arms first. The + support baits from just beside the northern add, away from the middle; an arm of the X runs right through the southern add, so the X support waits for the X to go off, then baits from just below it.</li>
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
    const COLX = { L:180, R:420 };
    const ROWY = { 1:120, 2:240, 3:360, 4:480 };
    const PRIORITY = ['H1','T1','T2','H2'];
    const JOB = { H1:'healer', H2:'healer', T1:'tank', T2:'tank' };

    const SOUL = {
      quartered: { label:'Quartered Soul', icon:'assets/quartered-soul.png', cls:'role' },
      xmarked:   { label:'X-marked Soul',  icon:'assets/x-marked-soul.png',  cls:'role' },
      astral:    { label:'Astralbright Soul', icon:'assets/astralbright-soul.png', cls:'astral' },
      umbral:    { label:'Umbralbright Soul', icon:'assets/umbralbright-soul.png', cls:'umbral' }
    };

    // Athena's aspects: Astral is the dark one, Umbral the light one.
    function lightWord(a){ return a === 'astral' ? 'dark' : 'light'; }

    // What a support can choose to practise: any of the four Souls Engravement of Souls hands out, or a random one
    // each pull. A bright Soul also settles the towers' aspect, since both bright Souls share it.
    const PICKS = [
      { id:'quartered', soul:'quartered', icon:SOUL.quartered.icon, label:SOUL.quartered.label },
      { id:'xmarked',   soul:'xmarked',   icon:SOUL.xmarked.icon,   label:SOUL.xmarked.label },
      { id:'astral',    soul:'bright', aspect:'astral', icon:SOUL.astral.icon, label:SOUL.astral.label },
      { id:'umbral',    soul:'bright', aspect:'umbral', icon:SOUL.umbral.icon, label:SOUL.umbral.label },
      { id:'random',    soul:null, label:'Random' }
    ];
    let practise = 'random';
    try{ const saved = localStorage.getItem('twelfth-p3-debuff'); if(PICKS.some(p => p.id === saved)) practise = saved; }catch(e){}

    /* ---------- real time ---------- */
    // Seconds after Athena's third Paradeigma cast ends: the medians of six clean pulls from the groups' logs
    // (FFLogs reports yd7c8B9bxrYKR6ft pulls 27 and 29, 7MPaxKXWvkTRFqrg pull 23 and 13pQaDtFrRwzX8dx pulls 16, 47
    // and 52), none more than a tenth of a second off.
    const LIVE = {
      start: 3.0,                 // the clock opens a little before Engravement of Souls
      engrave: [3.16, 7.14],      // Athena casts Engravement of Souls
      adds: 7.5,                  // the six adds show up (not in the log: two seconds before the tethers, as in Paradeigma II)
      debuffs: 8.25,              // the supports' Souls land
      tethers: 9.48,              // the wall adds tether the DPS and start Searing Radiance / Shadowsear
      enchain: [10.30, 17.30],    // Unnatural Enchainment chains four tiles, and they fall as it ends
      shock: [13.34, 17.30],      // a plain tower on each platform that will survive
      lasers: 18.59,              // the tether lasers fire
      laserHit: 19.35,            // and land: each DPS takes the Tilt of their tether's colour
      enchained: 19.39,           // Enchained Soul: nobody jumps any more
      cross: 22.34,               // the + and X start casting
      marks: 22.25,               // Quartered and X-marked Soul run out: the + and X drop where they stand
      drop: 25.24,                // the bright Souls run out: their towers drop where they stand
      aoes: 25.31,                // the + and X go off
      glow: 26.25,                // the bright Souls' small AoEs land
      flame: 26.42,               // White Flame: each yellow add fires at its two nearest players
      towersUp: 26.65,            // the aspected towers appear and start casting
      towers: 28.61,              // and resolve
      end: 29.6                   // On the Soul starts: the floor is coming back
    };
    // In yalms times 12, from the logs: a tower takes whoever is within 3 yalms (the soaks reach 2.3 nine times in ten),
    // a tether laser or White Flame line is about 4.7 wide, an arm of the + or X about 4.3 (the widest any log caught:
    // 2.2 off the line) and a bright Soul's AoE 3 in radius.
    const TOWER_R = 36, LASER_HALF = 28, FLAME_HALF = 28, ARM_HALF = 26, GLOW_R = 36;
    // A + or X dropped more than 3 yalms from its planned spot is off it, even when it hits nobody.
    const MARK_NEAR = 36;
    // A tether laser kills its own holder outright closer than about 34.5 yalms to its add (742 lasers in the logs:
    // ~600,000 damage under it, ~50,000 from it). The wall adds are drawn 21.3 yalms out to fit the arena, but stand
    // 25 out in the fight, 3 either side of the centre line, so the stretch is measured where they really are.
    const MIN_STRETCH_Y = 34.5;
    const stretchYalms = (add, p) => Math.hypot(Math.sign(add[0] - 300) * 25 - (p[0] - 300) / 12, (add[1] - p[1]) / 12);
    // The groups' waymarks (their in-game preset "Clockspots", as in the raidplan), 10 yalms out from the centre: A north,
    // B east, C south, D west, 1-4 on the intercardinals from the north-east, clockwise, in the game's colours (letters
    // round, numbers square), at their size in the game: a letter's circle 1.25 yalms in radius, a number's square 2.2
    // across (the Waymark Studio plugin's Waymark.cs).
    const WAYMARK = 120, WAYMARK_R = 15, WAYMARK_HALF = 13.2;
    const WAYMARKS = [['A', 0, -1, '#e5534b'], ['B', 1, 0, '#e8c547'], ['C', 0, 1, '#4a9ae0'], ['D', -1, 0, '#b07ae8'],
                      ['1', 1, -1, '#e5534b'], ['2', 1, 1, '#e8c547'], ['3', -1, 1, '#4a9ae0'], ['4', -1, -1, '#b07ae8']];
    // Everyone runs at 7 yalms a second (a little above the real 6), and the rest of the party moves off about
    // 2 seconds after each thing they need to read, as in the other drills.
    const SPEED = 84, REACT = 2.0, STEP_OFF = 0.05, TICK_MS = 33;

    let pace = 'steps';
    try{ if(localStorage.getItem('twelfth-p3-pace') === 'live') pace = 'live'; }catch(e){}
    const clock = { t: 0, running: false, timer: 0, last: 0 };
    let st = {};
    const fb = document.getElementById('p3-feedback');
    const panel = document.getElementById('panel-para3');

    /* ---------- geometry ---------- */
    function tile(row, col){
      return { row, col, key: String(row) + col, x: col === 'L' ? 60 : 300, y: 60 + (row-1)*120,
               w:240, h:120, cx:COLX[col], cy:ROWY[row] };
    }
    const inTile = (p, t, m = 0) => p[0] >= t.x - m && p[0] <= t.x + t.w + m && p[1] >= t.y - m && p[1] <= t.y + t.h + m;
    const onSafe = p => st.safe.some(t => inTile(p, t));
    const tileAt = p => st.safe.find(t => inTile(p, t));
    // The plan below is written for the zigzag that starts north-east; the other one is its mirror image.
    const mx = p => st.zig === 'R' ? p : [600 - p[0], p[1]];
    // A plain tower lands by the outer wall of its platform, 4 yalms in, as in the log.
    const plainTower = t => [t.col === 'L' ? 108 : 492, t.cy];
    function tileName(t){
      if(t.key === st.north.key) return 'NORTH';
      if(t.key === st.south.key) return 'SOUTH';
      return t.col === 'L' ? 'MID WEST' : 'MID EAST';
    }
    const clampTo = (xy, t, inset) => [Math.min(Math.max(xy[0], t.x + inset), t.x + t.w - inset), Math.min(Math.max(xy[1], t.y + inset), t.y + t.h - inset)];
    const centreCorner = (t, inset) => [t.col === 'L' ? t.x + t.w - inset : t.x + inset, t.row === 2 ? t.y + t.h - inset : t.y + inset];

    // The two DPS on a middle platform are always tethered to the far wall, so they can stretch.
    // The DPS whose add lines up with the platform has the straight tether and stands on the line of waymark B
    // (east) or D (west), level with the add, so the laser runs dead horizontal: 35 yalms from the add, half a yalm
    // past the lethal 34.5, so no closer; further out than the waymark it clips others (the raidplan). The crossed tether stands at the middle of
    // the platform's outer edge (top on the northern platform, bottom on the southern), so its laser
    // angles across. Between them the two lasers leave an outer gap on the plain tower for the support.
    // The wall adds stand 3 yalms either side of the centre line, as in the log.
    const WALL_ADD_Y = { 240: 264, 360: 336 };
    function dpsSpots(t){
      const fromSide = t.col === 'L' ? 'east' : 'west';
      const wallX = fromSide === 'west' ? 44 : 556;
      const slantAddY = t.cy === 240 ? 360 : 240;
      const color = fromSide === 'west' ? st.westColor : st.eastColor;
      return [
        { straight:true,  x:300 + Math.sign(t.cx - 300) * WAYMARK, y:WALL_ADD_Y[t.cy], addX:wallX, addY:WALL_ADD_Y[t.cy], color, side:fromSide },
        { straight:false, x:t.cx, y:t.row === 2 ? t.y + 18 : t.y + t.h - 18, addX:wallX, addY:WALL_ADD_Y[slantAddY], color, side:fromSide }
      ];
    }
    const dpsKey = (t, straight) => t.key + (straight ? 'S' : 'C');

    function startRound(){
      st.zig = Math.random() < 0.5 ? 'L' : 'R';
      const other = st.zig === 'L' ? 'R' : 'L';
      st.safe   = [tile(1, st.zig), tile(2, other), tile(3, st.zig), tile(4, other)];
      st.doomed = [tile(1, other), tile(2, st.zig), tile(3, other), tile(4, st.zig)];
      st.north = st.safe[0];
      st.south = st.safe[3];
      st.midW  = st.safe[1].col === 'L' ? st.safe[1] : st.safe[2];
      st.midE  = st.safe[1].col === 'R' ? st.safe[1] : st.safe[2];
      st.midN  = st.safe[1];
      st.midS  = st.safe[2];

      st.westColor = Math.random() < 0.5 ? 'astral' : 'umbral';
      st.eastColor = st.westColor === 'astral' ? 'umbral' : 'astral';
      st.bright    = Math.random() < 0.5 ? 'astral' : 'umbral';

      // The yellow-crystal adds stand just inside the north and south platforms, on their edge with the middle,
      // 10 yalms out on the intercardinal as in the log.
      st.addN = { x: COLX[st.north.col], y: 174 };
      st.addS = { x: COLX[st.south.col], y: 426 };

      // Supports: one +, one X, two matching bright souls. A support practising one Soul always gets it, and the
      // other three share out the rest.
      const pick = shared.role === 'support' ? PICKS.find(p => p.id === practise) : null;
      const souls = shuffle(['quartered','xmarked','bright','bright']);
      if(pick && pick.soul){
        souls.splice(souls.indexOf(pick.soul), 1);
        souls.splice(PRIORITY.indexOf(shared.slot), 0, pick.soul);
      }
      if(pick && pick.aspect) st.bright = pick.aspect;
      st.slotSoul = {};
      PRIORITY.forEach((s, i) => { st.slotSoul[s] = souls[i]; });
      st.brightSlots = PRIORITY.filter(s => st.slotSoul[s] === 'bright');
      // The bright souls go by priority, west to east: the first of them takes the western middle platform.
      st.brightWest = st.brightSlots[0];
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
        else st.home = (st.mySlot === st.brightWest) ? st.midW : st.midE;
        // The DPS sharing your platform are tethered to the wall opposite it.
        st.myDpsColor = st.home.col === 'L' ? st.eastColor : st.westColor;
        st.towerSpot  = (st.myDpsColor === st.bright) ? 'centre' : 'tile';
      } else {
        st.home  = st.mySide === 'west' ? st.midE : st.midW;
        st.myAddY = Math.random() < 0.5 ? 240 : 360;
        st.straight = st.myAddY === st.home.cy;
        st.job = (st.myColor === st.bright) ? 'bait' : 'soak';
        st.towerPick = st.straight ? 'centre' : 'tile';
      }

      buildActors();
      // where everyone stands around Athena before anything lands, shuffled, so it says nothing about the jobs
      st.ring = shuffle(st.ids);
      st.me = myKey();

      st.step = 1;
      stopClock();
      (st.fxTimers || []).forEach(clearTimeout);
      st.fxTimers = [];
      st.live = pace === 'live';
      st.fired = {}; st.over = false;
      st.marks = {}; st.drops = {}; st.tagged = false; st.phase = -1;
      st.paused = false; st.warned = []; st.saved = null;
      ['p3-fx', 'p3-lasers', 'p3-target', 'p3-freeHits', 'p3-towers', 'p3-aoes'].forEach(id => { document.getElementById(id).innerHTML = ''; });
      clock.t = LIVE.start;
      panel.classList.toggle('p3-timed', st.live);
      document.getElementById('p3-start').textContent = 'Start ▶';
      document.getElementById('p3-start').hidden = !st.live;
      document.getElementById('p3-start').style.visibility = '';
      document.getElementById('p3-start').parentNode.style.minHeight = '';
      // the most casts the strip ever shows at once, so it keeps that many rows throughout
      st.castSlots = Math.max(1, ...Array.from({ length: 300 }, (_, k) => liveRows(k * 0.1).length));
      st.moves = {};
      st.ids.forEach(id => setAt(id, stackSpot(id)));
      render();
    }

    /* ---------- the party ---------- */
    // Supports go by their slot; the DPS by the platform they stretch to and their tether, straight or crossed.
    function buildActors(){
      st.actors = {};
      PRIORITY.forEach(s => {
        const soul = st.slotSoul[s];
        const home = soul === 'quartered' ? st.north : soul === 'xmarked' ? st.south : (s === st.brightWest ? st.midW : st.midE);
        st.actors[s] = { kind:'support', slot:s, soul, tile:home };
      });
      [st.midW, st.midE].forEach(t => dpsSpots(t).forEach(d => {
        st.actors[dpsKey(t, d.straight)] = { kind:'dps', tile:t, straight:d.straight, color:d.color, add:[d.addX, d.addY], stretch:[d.x, d.y] };
      }));
      st.ids = Object.keys(st.actors);
    }
    // your own key among them
    function myKey(){ return shared.role === 'support' ? st.mySlot : dpsKey(st.home, st.straight); }
    const isDps = id => st.actors[id].kind === 'dps';
    // Who holds which platform's soul.
    function supportOn(t){
      if(t.key === st.north.key) return { slot: PRIORITY.find(s => st.slotSoul[s] === 'quartered'), soul:'quartered' };
      if(t.key === st.south.key) return { slot: PRIORITY.find(s => st.slotSoul[s] === 'xmarked'), soul:'xmarked' };
      return { slot: t.key === st.midW.key ? st.brightWest : st.brightSlots.find(s => s !== st.brightWest), soul: st.bright };
    }
    // The DPS on a middle platform are tethered to the far wall.
    const dpsColorOn = t => t.col === 'L' ? st.eastColor : st.westColor;
    // The pair whose tether is opposite the towers soaks; the matching pair baits White Flame.
    const soakTile = () => [st.midW, st.midE].find(t => dpsColorOn(t) !== st.bright);
    const baitTile = () => [st.midW, st.midE].find(t => dpsColorOn(t) === st.bright);
    const holderOf = soul => PRIORITY.find(s => st.slotSoul[s] === soul);

    // Where each player stands for each part when everything goes to plan, from the groups' logs and their plan,
    // written for the zigzag that starts north-east (mirrored for the other) and keyed by the platform's row.
    const PLAN = {
      plusMark: [528, 72],      // the + drops in the outer corner of the north platform
      plusBait: [450, 164],     // and baits from just beside the northern add, away from the middle
      xMark: [288, 528],        // the X drops at the south wall, in the inner corner of the south platform
      xClear: [150, 470],       // waits out of its own arms (one runs right through the southern add)
      xBait: [180, 452],        // and baits from just below the add once the X has gone off
      // a bright Soul's tower: in the middle of the soaking pair's platform, nudged towards the centre line on
      // the southern one so it sits clear of the X's arm; or on the arena-centre corner of the other
      drop: { soak: { 2:[180, 240], 3:[396, 360] }, bait: { 2:[284, 284], 3:[316, 316] } },
      // and once it is down, out of it: well clear of the towers, the lines and the yellow adds
      aside: { soak: { 2:[96, 204], 3:[504, 396] }, bait: { 2:[240, 265], 3:[360, 335] } },
      // the soaking pair waits clear of the bright Souls' small AoEs (and of the X's arm) until they have gone off
      wait: { 2: { S:[264, 276], C:[180, 198] }, 3: { S:[340, 330], C:[440, 320] } }
    };
    const brightRole = t => t.key === soakTile().key ? 'soak' : 'bait';
    function supTowerSpot(t){
      const [x, y] = plainTower(t);
      // on a middle platform, on the tower's side away from the arena's horizontal centre line: the gap the two
      // DPS lasers leave
      return (t.row === 2 || t.row === 3) ? [x, y + (t.row === 2 ? -22 : 22)] : [x, y];
    }
    function stackSpot(id){
      const a = st.ring.indexOf(id) * Math.PI / 4;
      return [300 + Math.cos(a) * 60, 300 + Math.sin(a) * 60];
    }
    // the drop of the bright Soul on platform t: where it actually ran out against the clock, the plan otherwise
    const dropAt = t => { const s = supportOn(t).slot; return (st.drops && st.drops[s]) || mx(PLAN.drop[brightRole(t)][t.row]); };
    // the two aspected towers: in the middle of the soaking pair's platform, and on the centre corner of the other
    const towerSpots = () => ({ tile: dropAt(soakTile()), centre: dropAt(baitTile()) });
    // Pinned to your own tile, the only bait spots are its corners. Two of them face a yellow-crystal add; the
    // third is the corner pointing back at the arena centre. Every spot hugs the tile edge, a yalm in, so you are
    // as close to the add as Enchained Soul lets you get.
    function baitSpots(t){
      t = t || st.home;
      const inset = 12;
      const n = clampTo([st.addN.x, st.addN.y], t, inset), sp = clampTo([st.addS.x, st.addS.y], t, inset);
      return [
        { id:'addN', x:n[0],  y:n[1],  r:20, ariaLabel:'Spot facing the northern add' },
        { id:'addS', x:sp[0], y:sp[1], r:20, ariaLabel:'Spot facing the southern add' },
        { id:'inner', r:20, ariaLabel:'Corner facing the arena centre',
          x: t.col === 'L' ? t.x + t.w - inset : t.x + inset,
          y: t.row === 2   ? t.y + t.h - inset : t.y + inset }
      ];
    }
    // Each baiting DPS takes the yellow add closest to them: the straight tether the one in its own column, above
    // or below the platform, the crossed tether the one across.
    function baitSpot(a){
      const ownColumn = st.addN.x === a.tile.cx ? 'addN' : 'addS';
      const s = baitSpots(a.tile).find(s => s.id === (a.straight ? ownColumn : ownColumn === 'addN' ? 'addS' : 'addN'));
      return [s.x, s.y];
    }
    // The soaking pair: the crossed tether takes the tower in the middle of the platform, the straight tether the
    // one on the other platform's centre corner, from as far in as Enchained Soul lets them go.
    const soakSpot = a => a.straight ? clampTo(dropAt(baitTile()), a.tile, 4) : dropAt(soakTile());
    function plan(id, phase){
      const a = st.actors[id];
      if(phase === 'stack') return stackSpot(id);
      if(a.kind === 'support'){
        if(phase === 'first') return supTowerSpot(a.tile);
        if(a.soul === 'quartered') return mx(phase === 'job' ? PLAN.plusMark : PLAN.plusBait);
        if(a.soul === 'xmarked') return mx(phase === 'job' ? PLAN.xMark : phase === 'clear' ? PLAN.xClear : PLAN.xBait);
        return (phase === 'aside' || phase === 'soak') ? mx(PLAN.aside[brightRole(a.tile)][a.tile.row]) : dropAt(a.tile);
      }
      if(phase === 'first') return a.stretch;
      if(a.tile.key === baitTile().key) return baitSpot(a);
      if(phase === 'soak') return soakSpot(a);
      return mx(PLAN.wait[a.tile.row][a.straight ? 'S' : 'C']);
    }

    // Step by step: where everyone stands at each stage. 'two': plain towers soaked, tethers out. 'pre3': as the
    // last step opens, the + and X where they dropped their AoE, the bright souls on their tower spots, the DPS
    // still where their lasers left them. 'res3': everyone doing their last job.
    function positions(stage){
      const pos = {};
      st.ids.forEach(id => { pos[id] = plan(id, stage === 'two' ? 'first' : stage === 'res3' ? 'soak' : 'job'); });
      if(stage === 'pre3'){
        st.ids.filter(isDps).forEach(id => { pos[id] = st.actors[id].stretch; });
        // The crossed DPS on the southern middle platform waits at its bottom middle, inside an arm of the X, so
        // they leave as soon as their laser has fired: straight for their job, or to the middle of the platform
        // when it is you, so the board does not answer your question for you.
        const key = dpsKey(st.midS, false);
        pos[key] = (shared.role === 'dps' && key === st.me) ? [st.midS.cx, st.midS.cy] : plan(key, 'soak');
      }
      return pos;
    }

    /* ---------- movement, against the clock ---------- */
    function posAt(id, t){
      const m = st.moves[id];
      if(t <= m.t0) return m.from;
      if(m.dur <= 0 || t >= m.t0 + m.dur) return m.to;
      const k = (t - m.t0) / m.dur;
      return [m.from[0] + (m.to[0] - m.from[0]) * k, m.from[1] + (m.to[1] - m.from[1]) * k];
    }
    function setAt(id, p){ st.moves[id] = { from:p, to:p, t0:0, dur:0 }; }
    function moveTo(id, to, delay){
      const now = clock.t, from = posAt(id, now);
      st.moves[id] = { from, to, t0: now + (delay === undefined ? STEP_OFF : delay), dur: dist(from, to) / SPEED };
    }
    const here = t => posAt(st.me, t);
    const party = t => { const p = {}; st.ids.forEach(id => { p[id] = posAt(id, t); }); return p; };
    function othersTo(phase, kind){
      st.ids.filter(id => id !== st.me && (!kind || st.actors[id].kind === kind)).forEach(id => moveTo(id, plan(id, phase), 0));
    }

    /* ---------- the fight clock ---------- */
    function stopClock(){ clock.running = false; if(clock.timer) clearTimeout(clock.timer); clock.timer = 0; }
    // Starts the pull, or picks it up again where a pause left it.
    function startClock(){
      if(!st.live || clock.running || st.over) return;
      if(st.paused){
        st.paused = false;
        fb.hidden = true;
        layer('p3-target');
        drawFloorLive();
      }
      clock.running = true;
      clock.last = performance.now();
      // the button keeps its room and, when the strip sits above the arena, the header its height, so the
      // arena does not move as the clock starts
      const head = document.getElementById('p3-start').parentNode;
      if(!T.leadBeside('para3')) head.style.minHeight = head.getBoundingClientRect().height + 'px';
      document.getElementById('p3-start').style.visibility = 'hidden';
      // once the clock runs, the ask is the first beat's rather than to press Start
      liveText();
      freePick(here(clock.t), livePick);
      clock.timer = setTimeout(tick, TICK_MS);
    }
    // Stops the clock mid-pull: everyone freezes where they are (moves run on the fight clock) and the floor
    // takes no clicks until startClock picks it up again. A warning pauses the pull this way; a Pause button
    // would call the same pair. The strip's button turns into Resume meanwhile.
    function pauseClock(){
      if(!clock.running || st.over) return;
      stopClock();
      st.paused = true;
      endFreePick();
      const b = document.getElementById('p3-start');
      b.textContent = 'Resume ▶';
      b.style.visibility = '';
      renderLive();
    }
    // Takes the pull back to the moment the floor fell, as it stood then, and leaves it paused there.
    function checkpoint(){
      st.saved = { t: clock.t, moves: JSON.parse(JSON.stringify(st.moves)), fired: Object.assign({}, st.fired),
                   tagged: st.tagged, phase: st.phase, warned: st.warned.slice() };
    }
    function rewind(){
      const s = st.saved;
      if(!s || !st.paused) return;
      st.fxTimers.forEach(clearTimeout);
      st.fxTimers = [];
      clock.t = s.t;
      st.moves = JSON.parse(JSON.stringify(s.moves));
      st.fired = Object.assign({}, s.fired);
      st.tagged = s.tagged; st.phase = s.phase; st.warned = s.warned.slice();
      st.marks = {}; st.drops = {};
      T.playBeams(document.getElementById('p3-lasers'), []);
      layer('p3-fx'); layer('p3-target');
      fb.hidden = true;
      drawTiles();
      drawAdds();
      drawFloorLive();
      drawLive();
      renderBadges();
      liveText();
      renderLive();
    }
    // The clock only runs while you can see it: switching mechanic or tab pauses it.
    function tick(){
      if(!clock.running) return;
      clock.timer = setTimeout(tick, TICK_MS);
      const now = performance.now(), dt = Math.min(0.1, (now - clock.last) / 1000);
      clock.last = now;
      if(panel.hidden || document.hidden) return;
      clock.t += dt;
      onTime();
      // once the tiles have gone, walking off your platform drops you into the void
      if(!st.over && clock.t > LIVE.enchain[1] && !onSafe(here(clock.t))) fellOff();
      // the ask follows the fight
      const ph = phaseAt(clock.t);
      if(!st.over && ph !== st.phase){ st.phase = ph; liveText(); }
      if(!st.over) drawLive();
      renderLive();
    }
    function onTime(){
      const t = clock.t;
      // a beat due as the clock pauses waits for it to resume
      const at = (key, time, fn) => { if(t >= time && !st.fired[key] && !st.paused){ st.fired[key] = true; if(!st.over) fn(); } };
      at('adds', LIVE.adds, () => drawAdds(true));
      at('debuffs', LIVE.debuffs, () => { renderBadges(); liveText(); });
      at('tethers', LIVE.tethers, () => { renderBadges(); liveText(); drawAdds(false); });
      // the rest of the party: each move a beat after there is something new to read
      at('p-dps', LIVE.tethers + REACT, () => othersTo('first', 'dps'));
      at('chains', LIVE.enchain[0], drawTiles);
      at('p-sup', LIVE.enchain[0] + REACT, () => othersTo('first', 'support'));
      at('shock', LIVE.shock[0], () => drawPlainTowers(true));
      at('c-floor', LIVE.enchain[1], checkFloor);
      at('save', LIVE.enchain[1], checkpoint);
      at('c-lasers', LIVE.lasers, checkLasers);
      at('tilts', LIVE.laserHit, () => { renderBadges(); liveText(); });
      at('enchained', LIVE.enchained, renderBadges);
      at('p-job', LIVE.laserHit + 0.3, () => othersTo('job'));
      at('c-marks', LIVE.marks, placeMarks);
      at('p-clear', LIVE.marks + 0.15, () => othersTo('clear'));
      at('c-drop', LIVE.drop, checkDrop);
      at('c-aoes', LIVE.aoes, checkAoes);
      at('p-bait', LIVE.aoes + 0.05, () => othersTo('bait'));
      at('p-aside', LIVE.drop + 0.3, () => othersTo('aside'));
      at('c-glow', LIVE.glow, checkGlow);
      at('p-soak', LIVE.glow + 0.1, () => othersTo('soak'));
      at('c-flame', LIVE.flame, checkFlame);
      at('towersUp', LIVE.towersUp, () => drawBrightTowers(true));
      at('c-towers', LIVE.towers, checkTowers);
      at('end', LIVE.end, liveClear);
    }

    /* ---------- judging, on where you are ---------- */
    const yalms = d => (d / 12).toFixed(1);
    const sec = t => `<b>${t.toFixed(1)} s</b>`;
    const whoName = id => st.actors[id].kind === 'support' ? id
      : `the ${st.actors[id].straight ? 'straight' : 'crossed'}-tether DPS on the ${tileName(st.actors[id].tile).toLowerCase()} platform`;
    const names = ids => ids.map(whoName).join(' and ');
    // a line AoE from `from` through `through` and on to the edge: who it catches
    function inLine(from, through, p, half){
      const len = dist(from, through) || 1, ux = (through[0] - from[0]) / len, uy = (through[1] - from[1]) / len;
      const along = (p[0] - from[0]) * ux + (p[1] - from[1]) * uy;
      return along > 0 && Math.abs((p[0] - from[0]) * uy - (p[1] - from[1]) * ux) <= half;
    }
    const inPlus = (c, p) => Math.abs(p[0] - c[0]) <= ARM_HALF || Math.abs(p[1] - c[1]) <= ARM_HALF;
    const inSaltire = (c, p) => { const dx = p[0] - c[0], dy = p[1] - c[1]; return Math.min(Math.abs(dx - dy), Math.abs(dx + dy)) / Math.SQRT2 <= ARM_HALF; };

    function platformRule(){
      if(shared.role === 'dps') return `Your add is on the <b>${st.mySide}</b> wall, so you stretch across to the <b>${tileName(st.home).toLowerCase()}</b> platform. Yours is the <b>${st.straight ? 'straight' : 'crossed'}</b> tether: ${st.straight ? `stand level with your add on the line of waymark ${st.home.col === 'R' ? 'B' : 'D'}, so the laser runs dead east–west (any closer to the add and it kills you)` : `stand at the middle of the platform's ${st.home.row === 2 ? 'top' : 'bottom'} edge, so the laser angles across`}.`;
      if(st.mySoul === 'quartered') return `Quartered Soul takes the tower on the <b>north-most</b> platform.`;
      if(st.mySoul === 'xmarked') return `X-marked Soul takes the tower on the <b>south-most</b> platform.`;
      const west = st.brightWest, east = st.brightSlots.find(s => s !== west);
      return `The bright souls are <b>${west}</b> and <b>${east}</b>: they go by priority H1 &gt; T1 &gt; T2 &gt; H2, west to east, so <b>${st.mySlot}</b> takes the tower on the <b>${st.mySlot === west ? 'western' : 'eastern'}</b> middle platform. Soak it from its side away from the arena's horizontal centre line, in the gap the two DPS lasers leave.`;
    }
    function jobRule(){
      if(shared.role === 'dps'){
        if(st.job === 'soak') return `Your tether was <b>${lightWord(st.myColor)}</b>, the opposite of the ${lightWord(st.bright)} towers, so you soak: the <b>${st.straight ? 'straight' : 'crossed'}</b> tether takes the tower ${st.straight ? 'on the arena-centre corner of the other platform, from the very corner of yours' : 'in the middle of your platform'}. Wait clear of the bright Souls' small AoEs until they have gone off at ${LIVE.glow.toFixed(1)} s, then step in.`;
        return `Your tether was <b>${lightWord(st.myColor)}</b>, the same as the towers, so you bait White Flame: the yellow add closest to you, from the corner of your platform facing it — the ${st.straight ? `one in your own column, ${st.home.row === 3 ? 'above' : 'below'} your platform` : 'one across from your platform'}.`;
      }
      if(st.mySoul === 'quartered') return `Drop your plus in the <b>outer corner</b> of the north platform, where both arms run along the walls, step out of it, and bait White Flame from just beside the northern add, away from the middle.`;
      if(st.mySoul === 'xmarked') return `Drop your X at the <b>south wall</b>, in the inner corner of the south platform, so its arms run out to the corners. Step out of its arms and wait for it to go off — one runs right through the southern add — then bait White Flame from just below the add.`;
      return st.towerSpot === 'centre'
        ? `The DPS on your platform are <b>${lightWord(st.myDpsColor)}</b>, the same as your tower, so they cannot take it: drop it on the <b>arena-centre corner</b> of your platform, as close to the middle as you can, so it spills onto the other middle platform. Then step out of it, clear of the yellow adds and their lines.`
        : `The DPS on your platform are <b>${lightWord(st.myDpsColor)}</b>, the opposite of your tower, so they soak it: drop it in the <b>middle of your platform</b>${st.home.row === 3 ? ', nudged towards the centre line, clear of the arm of the X' : ''}, away from the other tower. Then step out of it.`;
    }

    // at the end of Unnatural Enchainment the chained tiles fall and the plain towers resolve
    function checkFloor(){
      const p = here(LIVE.enchain[1]);
      drawTiles();
      fxPlainTowers();
      if(!onSafe(p)) return liveFail('Went down with the floor', `When Unnatural Enchainment finished at ${sec(LIVE.enchain[1])} you were still on one of the four chained tiles, and it fell away under you. The chains appear as the cast starts at ${LIVE.enchain[0].toFixed(1)} s: get onto a tile that stays. ${platformRule()}`, plan(st.me, 'first'));
      const inside = st.safe.find(t => dist(p, plainTower(t)) <= TOWER_R);
      if(shared.role === 'dps'){
        if(inside) return liveFail('In a support tower', `You were standing in the plain tower on the ${tileName(inside).toLowerCase()} platform when it went off at ${sec(LIVE.shock[1])}. Those are for the supports: the hit and its Magic Vulnerability Up are not yours to take. ${platformRule()}`, plan(st.me, 'first'));
        return;
      }
      if(!inside) return liveFail('Tower not soaked', `Nobody stood in the plain tower on your platform when it went off at ${sec(LIVE.shock[1])}, so it exploded and wiped the raid. You have to be inside its circle. ${platformRule()}`, plan(st.me, 'first'));
      if(inside.key !== st.home.key) return liveFail('Wrong tower', `You soaked the tower on the ${tileName(inside).toLowerCase()} platform, where ${supportOn(inside).slot} was going, so yours on the ${tileName(st.home).toLowerCase()} platform went unsoaked and exploded. ${platformRule()}`, plan(st.me, 'first'));
    }
    // the four tether lasers: from each wall add through its DPS and on across the arena
    function checkLasers(){
      const pos = party(LIVE.lasers), dps = st.ids.filter(isDps);
      if(!st.over) drawLive(LIVE.lasers);
      T.playBeams(document.getElementById('p3-lasers'), dps.map(id => ({ from: st.actors[id].add, through: pos[id] })));
      st.tagged = true;
      const me = st.me, p = pos[me];
      if(isDps(me)){
        const a = st.actors[me], on = tileAt(p);
        if(!on) return;                       // off every platform: the fall has it
        if(on.key !== st.home.key){
          const near = on.row === 2 || on.row === 3;
          return liveFail(near ? 'Tether not stretched' : 'Wrong platform', near
            ? `When your laser fired at ${sec(LIVE.lasers)} you were still on the middle platform beside your own add, and that close the hit is lethal. ${platformRule()}`
            : `When your laser fired at ${sec(LIVE.lasers)} you were on the ${tileName(on).toLowerCase()} platform with its support, who took it with you. The DPS take the middle two. ${platformRule()}`, a.stretch);
        }
        if(stretchYalms(a.add, p) < MIN_STRETCH_Y) return liveFail('Not stretched far enough', `When your laser fired at ${sec(LIVE.lasers)} you were only ${stretchYalms(a.add, p).toFixed(1)} yalms from your add. Closer than about ${MIN_STRETCH_Y} the laser kills you outright. ${platformRule()}`, a.stretch);
        const clipped = st.ids.filter(id => id !== me && inLine(a.add, p, pos[id], LASER_HALF));
        if(clipped.length) return liveFail('Laser through a party member', `Your add's laser runs from the add through you and on across the arena, and when it fired at ${sec(LIVE.lasers)} ${names(clipped)} ${clipped.length > 1 ? 'were' : 'was'} in its path. Only you may take it. ${platformRule()}`, a.stretch);
      }
      const by = dps.find(id => id !== me && inLine(st.actors[id].add, pos[id], p, LASER_HALF));
      if(by) return liveFail('Caught in a laser', `When the tether lasers fired at ${sec(LIVE.lasers)} you were in the one from ${st.actors[by].add[0] < 300 ? 'the west' : 'the east'} wall through ${whoName(by)}. ${platformRule()}`, plan(me, 'first'));
    }
    // Quartered and X-marked Soul run out: the + and X drop where their holders stand, and go off three seconds later
    function placeMarks(){
      st.marks.plus = posAt(holderOf('quartered'), LIVE.marks);
      st.marks.x = posAt(holderOf('xmarked'), LIVE.marks);
      drawMarks(true);
    }
    // the bright Souls run out: their towers drop where they stand
    function checkDrop(){
      [st.midN, st.midS].forEach(t => { const s = supportOn(t).slot; st.drops[s] = posAt(s, LIVE.drop); });
      fxDrops();
      if(isDps(st.me) || st.mySoul !== 'bright') return;
      const p = st.drops[st.me], S = soakTile(), B = baitTile();
      const otherSlot = st.brightSlots.find(s => s !== st.me), other = st.drops[otherSlot];
      const want = mx(PLAN.drop[brightRole(st.home)][st.home.row]), when = sec(LIVE.drop);
      if(st.home.key === B.key){
        const reach = dist(p, clampTo(p, S, 0));
        if(reach > TOWER_R - 8) return liveFail('Tower out of reach', `Your Soul ran out at ${when} ${yalms(reach)} yalms from the other middle platform. The DPS on yours share its colour and cannot soak it, and the pair who can are stuck over there: it has to reach over the arena-centre corner. ${jobRule()}`, want);
      }
      if(dist(p, other) < 2 * TOWER_R) return liveFail('Towers overlap', `Your Soul ran out at ${when} so close to ${otherSlot}'s tower that the two overlap, and whoever soaks one is caught by both. ${jobRule()}`, want);
      // whoever soaks it sets off once the small AoEs have gone, and has to be in well before the towers go off
      const soaker = st.ids.find(id => isDps(id) && st.actors[id].tile.key === S.key && st.actors[id].straight === (st.home.key === B.key));
      const from = plan(soaker, 'job'), to = soakSpot(st.actors[soaker]);
      if(dist(to, p) > TOWER_R) return liveFail('Tower out of reach', `Your Soul ran out at ${when} where ${whoName(soaker)} cannot stand inside the tower from their own platform. ${jobRule()}`, want);
      const arrive = LIVE.glow + 0.1 + STEP_OFF + dist(from, to) / SPEED;
      if(arrive > LIVE.towers - 0.4) return liveFail('Out of reach', `Your Soul ran out at ${when} ${yalms(dist(from, to))} yalms from where ${whoName(soaker)} waits for the small AoEs to pass. Setting off after them, they would only get there at ${arrive.toFixed(1)} s, too late for the towers at ${sec(LIVE.towers)}. ${jobRule()}`, want);
      const caught = st.ids.filter(id => id !== st.me && id !== soaker && dist(plan(id, 'soak'), p) <= TOWER_R + 8);
      if(caught.length) return liveFail('Tower on the party', `Your Soul ran out at ${when} where ${names(caught)} will be standing when the towers go off, so your tower would catch them as well. ${jobRule()}`, want);
    }
    function checkAoes(){
      const pos = party(LIVE.aoes), me = st.me;
      fxMarks();
      const shapes = [['quartered', st.marks.plus, inPlus, 'plus'], ['xmarked', st.marks.x, inSaltire, 'X']];
      let offSpot = null;
      for(const [soul, c, inside, word] of shapes){
        const owner = holderOf(soul), hit = st.ids.filter(id => inside(c, pos[id]));
        if(owner === me){
          if(hit.includes(me)) return liveFail(`Caught in your own ${word}`, `Your ${word} went off at ${sec(LIVE.aoes)} with you still in one of its arms. It is delayed: drop it, then step out of its arms before it lands. ${jobRule()}`, plan(me, 'clear'));
          const others = hit.filter(id => id !== me);
          if(others.length) return liveFail(`Your ${word} hit the party`, `Your ${word} dropped at ${LIVE.marks.toFixed(1)} s where its arms ran through ${names(others)} when it went off at ${sec(LIVE.aoes)}. It is fixed to true north, so the spot decides where the arms go. ${jobRule()}`, plan(me, 'job'));
          if(dist(c, plan(me, 'job')) > MARK_NEAR) offSpot = [c, inside, word];
        } else if(hit.includes(me)){
          return liveFail(`Caught in the ${word}`, `${owner}'s ${word} went off at ${sec(LIVE.aoes)} with you in one of its arms. Both are fixed to true north: the plus runs along the walls from the north platform's outer corner, the X out to the corners from the south wall. ${isDps(me) || st.mySoul === 'bright' ? jobRule() : ''}`, plan(me, st.mySoul === 'quartered' || st.mySoul === 'xmarked' ? 'clear' : 'job'));
        }
      }
      // it hit nobody, but it was not where the group drops it: a warning, with the pull paused
      if(offSpot) warnOffSpot(...offSpot);
    }
    // How much of the middle of each platform, and whether the arena centre, an AoE's arms cover.
    function armsOver(c, inside){
      const out = { centre: inside(c, [300, 300]) };
      st.safe.forEach(t => {
        let n = 0;
        for(let i = 0; i < 8; i++) for(let j = 0; j < 4; j++)
          if(inside(c, [t.x + t.w / 4 + (i + 0.5) * t.w / 16, t.y + t.h / 4 + (j + 0.5) * t.h / 8])) n++;
        out[t.key] = n / 32;
      });
      return out;
    }
    // The + or X went off where the plan does not drop it and caught nobody: pause, say what it cut through that
    // the planned drop would not have, and offer to carry on, to take the drop again or a new pull.
    function warnOffSpot(c, inside, word){
      const want = plan(st.me, 'job'), off = dist(c, want);
      const spot = word === 'plus' ? 'the outer corner of the north platform' : 'the south wall, at the inner corner of the south platform';
      const now = armsOver(c, inside), planned = armsOver(want, inside);
      const cut = st.safe.filter(t => now[t.key] >= 0.2 && now[t.key] - planned[t.key] >= 0.15)
        .map(t => `the middle of ${t.key === st.home.key ? 'your own' : 'the ' + tileName(t).toLowerCase()} platform`);
      if(now.centre && !planned.centre) cut.push('the arena centre, where the two middle platforms meet');
      const risk = cut.length
        ? `From there its arms cut through ${cut.join(' and ')}, so it missed the party only because nobody happened to be standing there.`
        : `Its arms still miss the middle of every platform, but the party lines up on where the group drops it, and an AoE anywhere else is one they cannot plan around.`;
      st.warned.push(`Your ${word} dropped ${yalms(off)} yalms off its spot`);
      pauseClock();
      (word === 'plus' ? drawPlus : drawSaltire)(layer('p3-aoes'), c[0], c[1], 0.3);
      T.drawTarget(layer('p3-target'), want, c);
      fb.dataset.noUndo = '1';
      showFeedback(fb, 'warn', `${word === 'plus' ? 'Plus' : 'X'} dropped off its spot`,
        `Your ${word} dropped at ${sec(LIVE.marks)}, ${yalms(off)} yalms from ${spot}, and when it went off at ${sec(LIVE.aoes)} it hit nobody. ${risk} ${jobRule()}<br><br>The pull is paused: resume from here, take the drop again from ${st.saved.t.toFixed(1)} s, as the floor falls, or start a new pull.`,
        'Resume ▶', startClock,
        [{ label: `Retry from ${st.saved.t.toFixed(1)} s ↺`, onClick: rewind }, { label: 'New pull ↻', onClick: () => newRound() }]);
    }
    // the bright Souls' small AoEs, on the spots where their towers dropped
    function checkGlow(){
      const pos = party(LIVE.glow), me = st.me;
      fxGlow();
      for(const slot of st.brightSlots){
        const c = st.drops[slot], caught = st.ids.filter(id => id !== slot && dist(pos[id], c) <= GLOW_R);
        if(slot === me && caught.length) return liveFail('Your AoE hit someone', `Your Soul's small AoE went off at ${sec(LIVE.glow)} on ${names(caught)} as well, and its Magic Vulnerability Up would kill them in the towers. ${jobRule()}`, plan(me, 'job'));
        if(caught.includes(me)) return liveFail("Caught in a Soul's AoE", `${slot}'s ${SOUL[st.bright].label} went off at ${sec(LIVE.glow)} with you inside it, on the spot where its tower dropped. ${isDps(me) && st.job === 'soak' ? 'Its Magic Vulnerability Up makes the tower lethal for you. ' : ''}${jobRule()}`, plan(me, 'job'));
      }
    }
    // Each yellow-crystal add fires a line at its two nearest players, and on to the edge.
    function flameTargets(pos){
      return [st.addN, st.addS].map(ad => {
        const from = [ad.x, ad.y];
        return { from, ids: Object.keys(pos).sort((p, q) => dist(pos[p], from) - dist(pos[q], from)).slice(0, 2) };
      });
    }
    function checkFlame(){
      const pos = party(LIVE.flame), me = st.me, lines = flameTargets(pos);
      T.playBeams(document.getElementById('p3-lasers'), [].concat(...lines.map(l => l.ids.map(id => ({ from: l.from, through: pos[id] })))));
      const B = baitTile();
      const want = [holderOf('quartered'), holderOf('xmarked')].concat(st.ids.filter(id => isDps(id) && st.actors[id].tile.key === B.key));
      const got = [].concat(...lines.map(l => l.ids));
      const baiter = want.includes(me), targeted = got.includes(me);
      const spot = plan(me, 'bait');
      if(baiter && !targeted){
        const instead = got.filter(id => !want.includes(id));
        return liveFail('White Flame not baited', `When White Flame fired at ${sec(LIVE.flame)} you were not among the two players nearest either yellow add, so ${instead.length ? `its line went to ${names(instead)} instead` : 'someone else took yours'}. ${jobRule()}`, spot);
      }
      if(!baiter && targeted) return liveFail('Took a White Flame', `When White Flame fired at ${sec(LIVE.flame)} you were one of the two players nearest a yellow add, so it fired at you instead of at one of its baiters. Keep away from the yellow adds unless you are baiting. ${isDps(me) || st.mySoul === 'bright' ? jobRule() : ''}`, plan(me, 'soak'));
      if(baiter){
        const mine = lines.find(l => l.ids.includes(me)), stray = want.filter(id => !got.includes(id));
        if(stray.length){
          const mate = mine.ids.find(id => id !== me), wrongly = got.filter(id => !want.includes(id));
          return liveFail('Two baiters on one add', `When White Flame fired at ${sec(LIVE.flame)} you and ${whoName(mate)} were the two players nearest the ${mine.from[1] < 300 ? 'northern' : 'southern'} yellow add, so ${names(stray)} got no line and the other add fired at ${wrongly.length ? names(wrongly) : 'someone else'} instead. ${jobRule()}`, spot);
        }
        const clipped = st.ids.filter(id => !mine.ids.includes(id) && inLine(mine.from, pos[me], pos[id], FLAME_HALF));
        if(clipped.length) return liveFail('White Flame through the party', `Your White Flame line ran from the add through you and on across the arena, through ${names(clipped)}. Bait it from where the line points away from everyone. ${jobRule()}`, spot);
      }
      const by = lines.find(l => l.ids.some(id => id !== me && !l.ids.includes(me) && inLine(l.from, pos[id], pos[me], FLAME_HALF)));
      if(by){
        const holder = by.ids.find(id => inLine(by.from, pos[id], pos[me], FLAME_HALF));
        return liveFail('Caught in White Flame', `When White Flame fired at ${sec(LIVE.flame)} you stood in the line from the ${by.from[1] < 300 ? 'northern' : 'southern'} yellow add through ${whoName(holder)}. ${isDps(me) || st.mySoul === 'bright' ? jobRule() : ''}`, plan(me, 'soak'));
      }
    }
    function checkTowers(){
      const p = here(LIVE.towers), tw = towerSpots(), me = st.me;
      fxBrightTowers();
      const inside = ['tile', 'centre'].find(k => dist(p, tw[k]) <= TOWER_R);
      const word = k => k === 'tile' ? 'the tower in the middle of the platform' : 'the tower on the centre corner';
      if(isDps(me) && st.job === 'soak'){
        if(inside === st.towerPick) return;
        if(inside) return liveFail('Wrong tower', `You soaked ${word(inside)}, which your partner was taking, so two of you stood in one and ${word(st.towerPick)} went unsoaked and exploded. ${jobRule()}`, soakSpot(st.actors[me]));
        return liveFail('Tower not soaked', `Nobody stood in ${word(st.towerPick)} when it went off at ${sec(LIVE.towers)}, so it exploded. ${jobRule()}`, soakSpot(st.actors[me]));
      }
      if(inside) return liveFail('Standing in a tower', `You were inside ${word(inside)} when it went off at ${sec(LIVE.towers)}. Only the DPS whose tether was the opposite colour soak them. ${isDps(me) || st.mySoul === 'bright' ? jobRule() : ''}`, plan(me, 'soak'));
    }
    function fellOff(){
      liveFail('You fell off the platform', `Once the chained tiles have gone there is only the void between the platforms, and you walked off the edge of yours.<br><br><i>Enchained Soul will not let you jump. The void below the Twelfth Circle is very, very dark. Honey B will mourn your soul ❤️ </i><br><br><b>*** You have died ***</b><br><br>${clock.t < LIVE.laserHit ? platformRule() : jobRule()}`, null);
    }
    function liveFail(title, why, target){
      if(st.over) return;
      st.over = true;
      stopClock();
      endFreePick();
      drawLive();
      renderLive();
      const host = layer('p3-target');
      if(target) T.drawTarget(host, target, here(clock.t));
      fb.dataset.noUndo = '1';
      showFeedback(fb, false, title, why, 'New pull ↻', () => newRound());
    }
    function liveClear(){
      if(st.over) return;
      st.over = true;
      stopClock();
      endFreePick();
      renderLive();
      const items = [];
      if(isDps(st.me)){
        items.push(`Tether stretched across to the ${tileName(st.home).toLowerCase()} platform, <b>${st.straight ? 'straight' : 'crossed'}</b>, by <b>${LIVE.lasers.toFixed(1)} s</b>`);
        items.push(st.job === 'soak' ? `${st.straight ? 'Centre-corner' : 'Mid-platform'} tower soaked at <b>${LIVE.towers.toFixed(1)} s</b>` : `White Flame baited at <b>${LIVE.flame.toFixed(1)} s</b>`);
      } else {
        items.push(`Plain tower on the ${tileName(st.home).toLowerCase()} platform soaked at <b>${LIVE.shock[1].toFixed(1)} s</b>`);
        if(st.mySoul === 'bright') items.push(`${st.towerSpot === 'centre' ? 'Tower dropped on the centre corner' : 'Tower dropped in the middle of your platform'} at <b>${LIVE.drop.toFixed(1)} s</b>, clear of it when the towers went off`);
        else items.push(`${st.mySoul === 'quartered' ? 'Plus' : 'X'} dropped at <b>${LIVE.marks.toFixed(1)} s</b> and clear of it at <b>${LIVE.aoes.toFixed(1)} s</b>`, `White Flame baited at <b>${LIVE.flame.toFixed(1)} s</b>`);
      }
      fb.dataset.noUndo = '1';
      // a pull carried on past a warning clears, but not cleanly
      if(st.warned.length) return showFeedback(fb, 'warn', 'Cleared, off plan', `You survived every beat, but not the way the group plays it.<ul>${items.concat(st.warned.map(w => `Off plan: ${w}`)).map(i => `<li>${i}</li>`).join('')}</ul>`, 'New pull ↻', () => newRound());
      showFeedback(fb, true, 'Paradeigma III cleared', `You were where you needed to be at every beat.<ul>${items.map(i => `<li>${i}</li>`).join('')}</ul>`, 'New pull ↻', () => newRound());
    }

    /* ---------- the casts running ---------- */
    function liveRows(t = clock.t){
      const rows = [], dps = shared.role === 'dps';
      const addRow = (from, to, who, what, mine) => { if(t >= from && t < to) rows.push({ from, to, who, what, mine }); };
      addRow(LIVE.engrave[0], LIVE.engrave[1], 'Athena', 'Engravement of Souls');
      if(!dps && !st.over) addRow(LIVE.debuffs, st.mySoul === 'bright' ? LIVE.drop : LIVE.marks, 'You', SOUL[st.mySoul === 'bright' ? st.bright : st.mySoul].label, true);
      addRow(LIVE.tethers, LIVE.lasers, 'Tether adds', dps ? `${st.myColor === 'astral' ? 'Shadowsear' : 'Searing Radiance'} on you` : 'Searing Radiance / Shadowsear', dps);
      addRow(LIVE.enchain[0], LIVE.enchain[1], 'Athena', 'Unnatural Enchainment');
      addRow(LIVE.shock[0], LIVE.shock[1], 'Towers', 'Shock');
      addRow(LIVE.cross, LIVE.aoes, 'Athena', "Theos's Cross / Saltire");
      addRow(LIVE.towersUp, LIVE.towers, 'Towers', `${aspectLabel(st.bright)} Advance`);
      return rows;
    }
    function renderLive(){
      const box = document.getElementById('p3-live');
      box.hidden = !st.live;
      if(!st.live) return;
      document.getElementById('p3-clock').innerHTML = `${clock.t.toFixed(1)}<small>s</small>`;
      document.getElementById('p3-casts').innerHTML = T.castRows('p3', liveRows(), clock.t,
        clock.t < LIVE.engrave[0] ? 'Paradeigma has gone off. The adds are on their way.' : 'Nothing casting.', st.castSlots);
      document.getElementById('p3-liveNote').innerHTML = !clock.running && !st.over && clock.t <= LIVE.start
        ? '<span class="hint">Click to move as the fight unfolds: where you stand when each part goes off is what counts.</span>'
        : st.paused ? 'Paused. Resume when you are ready.' : '';
    }

    function setPace(p){
      pace = p;
      try{ localStorage.setItem('twelfth-p3-pace', p); }catch(e){}
      panel.querySelectorAll('[data-pace]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.pace === p)));
      newRound();
    }
    panel.querySelectorAll('[data-pace]').forEach(b => {
      b.setAttribute('aria-pressed', String(b.dataset.pace === pace));
      b.addEventListener('click', () => { if(b.dataset.pace !== pace) setPace(b.dataset.pace); });
    });
    document.getElementById('p3-start').addEventListener('click', startClock);

    // The Soul picker: supports only, since every DPS plays the tethers the same way.
    function renderPick(){
      const host = document.getElementById('p3-debuffPick'), note = document.getElementById('p3-pickNote');
      const dps = shared.role === 'dps';
      [host, note, document.getElementById('p3-pickLabel')].forEach(n => { n.hidden = dps; });
      if(dps) return;
      host.innerHTML = PICKS.map(p => `<button type="button" class="role-btn${p.soul ? '' : ' p3-any'}" data-pick="${p.id}" aria-pressed="${p.id === practise}" title="${p.label}" aria-label="${p.label}">`
        + (p.icon ? `<img src="${p.icon}" alt="">` : '<span>Random</span>') + '</button>').join('');
      const p = PICKS.find(x => x.id === practise);
      note.textContent = p.soul ? `Every pull deals you ${p.label}.` : 'Each pull deals you one of the four at random.';
    }
    document.getElementById('p3-debuffPick').addEventListener('click', e => {
      const b = e.target.closest('[data-pick]');
      if(!b || b.dataset.pick === practise) return;
      practise = b.dataset.pick;
      try{ localStorage.setItem('twelfth-p3-debuff', practise); }catch(e){}
      newRound();
    });

    /* ---------- drawing helpers ---------- */
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

    // The tiles: against the clock as the fight has them (whole, chained, gone); step by step the chained ones
    // glow red on the opening step and are gone after.
    function drawTiles(){
      const host = layer('p3-tiles');
      const chains = layer('p3-chains');
      const t = clock.t;
      const chained = st.live ? t >= LIVE.enchain[0] : true;
      const gone = st.live ? t >= LIVE.enchain[1] : st.step > 1;
      [1,2,3,4].forEach(r => ['L','R'].forEach(c => {
        const tl = tile(r, c);
        const safe = st.safe.some(s => s.key === tl.key);
        if(safe || !chained){
          host.appendChild(el('rect', { x:tl.x+3, y:tl.y+3, width:tl.w-6, height:tl.h-6, rx:5,
            fill:'rgba(74,143,224,0.13)', stroke:'rgba(130,182,242,0.5)', 'stroke-width':1.5 }));
        } else if(gone){
          host.appendChild(el('rect', { x:tl.x+3, y:tl.y+3, width:tl.w-6, height:tl.h-6, rx:5,
            fill:'rgba(4,3,10,0.9)', stroke:'rgba(230,220,255,0.1)', 'stroke-width':1 }));
        } else {
          host.appendChild(el('rect', { x:tl.x+3, y:tl.y+3, width:tl.w-6, height:tl.h-6, rx:5,
            fill:'rgba(226,82,63,0.17)', stroke:'rgba(226,82,63,0.55)',
            'stroke-width':1.5, 'stroke-dasharray':'8 6' }));
          chains.appendChild(el('line', { x1:300, y1:300, x2:tl.cx, y2:tl.cy,
            stroke:'var(--astral)', 'stroke-width':2, 'stroke-dasharray':'6 6', opacity:0.55, class:'stripe' }));
        }
      }));
      drawWaymarks();
    }

    // The waymarks stay put whichever way the zigzag runs: they are where the group places them.
    function drawWaymarks(){
      const host = layer('p3-waymarks');
      WAYMARKS.forEach(([label, dx, dy, colour]) => {
        const x = 300 + dx * WAYMARK, y = 300 + dy * WAYMARK;
        const g = el('g', { opacity:0.85 });
        g.appendChild(/[A-D]/.test(label) ? el('circle', { cx:x, cy:y, r:WAYMARK_R, fill:'rgba(10,9,22,0.6)', stroke:colour, 'stroke-width':2 })
                                          : el('rect', { x:x-WAYMARK_HALF, y:y-WAYMARK_HALF, width:2*WAYMARK_HALF, height:2*WAYMARK_HALF, rx:2, fill:'rgba(10,9,22,0.6)', stroke:colour, 'stroke-width':2 }));
        const t = el('text', { x:x, y:y+5.5, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':16, 'font-weight':700, fill:colour });
        t.textContent = label;
        g.appendChild(t);
        host.appendChild(g);
      });
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
    // The six adds. Against the clock they only show up a little before their tethers land, zooming out from
    // Athena's hitbox, and the wall adds only take their colour as they tether.
    function drawAdds(zoom){
      const host = layer('p3-adds');
      if(st.live && clock.t < LIVE.adds) return;
      const coloured = !st.live || clock.t >= LIVE.tethers;
      // as the pull opens step by step they zoom out from Athena's hitbox to their spots
      zoom = zoom || (!st.live && st.step === 1);
      const add = (x, y, color, r) => { const g = crystal(host, x, y, color, r); if(zoom) T.zoomAdd(g, [x, y], null, 0); };
      [240,360].forEach(row => {
        const y = WALL_ADD_Y[row];
        add(44, y, coloured ? aspectColor(st.westColor) : 'var(--mist-dim)', 15);
        add(556, y, coloured ? aspectColor(st.eastColor) : 'var(--mist-dim)', 15);
      });
      add(st.addN.x, st.addN.y, 'var(--aether)', 14);
      add(st.addS.x, st.addS.y, 'var(--aether)', 14);
    }

    function unit(host, x, y, kind, opts){
      opts = opts || {};
      x = +x.toFixed(1); y = +y.toFixed(1);
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

    function tower(host, x, y, aspect, label, cls){
      const c = aspect ? aspectColor(aspect) : 'var(--aether)';
      const g = el('g', cls ? { class: cls } : {});
      g.appendChild(el('circle', { cx:x, cy:y, r:TOWER_R, fill:c, opacity:0.13 }));
      g.appendChild(el('circle', { cx:x, cy:y, r:TOWER_R, fill:'none', stroke:c, 'stroke-width':2.5, opacity:0.9 }));
      g.appendChild(el('circle', { cx:x, cy:y, r:4, fill:c }));
      if(label){
        const t = el('text', { x:x, y:y-TOWER_R-6, 'text-anchor':'middle', 'font-family':'Space Mono, monospace',
          'font-size':10, 'letter-spacing':'0.08em', fill:c });
        t.textContent = label;
        g.appendChild(t);
      }
      host.appendChild(g);
      return g;
    }

    function drawPlus(host, x, y, opacity){
      const g = el('g', { 'clip-path':'url(#arenaClip)', opacity: opacity || 0.45, 'pointer-events':'none' });
      g.appendChild(el('line', { x1:x, y1:-50, x2:x, y2:650, stroke:'var(--shape-orange)', 'stroke-width':2 * ARM_HALF }));
      g.appendChild(el('line', { x1:-50, y1:y, x2:650, y2:y, stroke:'var(--shape-orange)', 'stroke-width':2 * ARM_HALF }));
      host.appendChild(g);
      return g;
    }
    function drawSaltire(host, x, y, opacity){
      const g = el('g', { 'clip-path':'url(#arenaClip)', opacity: opacity || 0.45, 'pointer-events':'none' });
      [[1,1],[1,-1]].forEach(d => {
        const r = 900 / Math.SQRT2;
        g.appendChild(el('line', { x1:x - d[0]*r, y1:y - d[1]*r, x2:x + d[0]*r, y2:y + d[1]*r,
          stroke:'var(--shape-orange)', 'stroke-width':2 * ARM_HALF }));
      });
      host.appendChild(g);
      return g;
    }

    // The party, wherever `pos` has them. Supports show their Soul while they hold it, the DPS the Tilt their
    // laser left them with; `tags` names each DPS's tether, straight or crossed; `tethered` draws the tethers.
    function drawParty(pos, opts){
      opts = opts || {};
      const actors = layer('p3-actors');
      const tethers = layer('p3-tethers');
      st.ids.filter(isDps).forEach(id => {
        const a = st.actors[id], mine = id === st.me, xy = pos[id];
        if(opts.tethered){
          tethers.appendChild(el('line', { x1:a.add[0], y1:a.add[1], x2:+xy[0].toFixed(1), y2:+xy[1].toFixed(1),
            stroke: aspectSoft(a.color), 'stroke-width': mine ? 3 : 1.8, opacity: mine ? 0.95 : 0.5,
            'stroke-linecap':'round' }));
        }
        unit(actors, xy[0], xy[1], 'dps', {
          me: mine, color: opts.coloured === false ? 'var(--mist)' : aspectSoft(a.color),
          tag: opts.tags ? (a.straight ? 'straight' : 'crossed') : null,
          icon: opts.tilts ? tiltIcon(a.color) : null
        });
      });
      // supports last, so they sit on top of the DPS tags beside them
      PRIORITY.forEach(slot => {
        const soul = st.slotSoul[slot];
        const shows = opts.souls === undefined ? true : typeof opts.souls === 'function' ? opts.souls(soul) : opts.souls;
        unit(actors, pos[slot][0], pos[slot][1], JOB[slot], {
          me: slot === st.me, tag: slot, icon: shows ? SOUL[soul === 'bright' ? st.bright : soul].icon : null,
          color: JOB[slot] === 'tank' ? 'var(--umbral-soft)' : 'var(--good)'
        });
      });
    }

    // Against the clock: the party where the clock has them, and the tethers while they last.
    function drawLive(t = clock.t){
      drawParty(party(t), {
        tethered: t >= LIVE.tethers && t < LIVE.lasers,
        coloured: t >= LIVE.tethers,
        tags: st.tagged || t >= LIVE.lasers,
        tilts: t >= LIVE.laserHit,
        souls: soul => t >= LIVE.debuffs && t < (soul === 'bright' ? LIVE.drop : LIVE.marks)
      });
    }
    // the plain towers, from Shock's cast until they go off
    function drawPlainTowers(pop){
      const host = layer('p3-towers');
      st.safe.forEach(t => { const [x, y] = plainTower(t); tower(host, x, y, null, null, pop ? 'p3-fx-pop' : null); });
    }
    function drawBrightTowers(pop){
      const host = layer('p3-towers'), tw = towerSpots();
      [tw.tile, tw.centre].forEach(p => tower(host, p[0], p[1], st.bright, null, pop ? 'p3-fx-pop' : null));
    }
    // the + and X once they have dropped: their arms marked out on the floor until they go off
    function drawMarks(pop){
      // the pop animates its own group's opacity, so the faint arms sit in a group inside it
      const host = layer('p3-aoes').appendChild(el('g', pop ? { class:'p3-fx-pop' } : {}));
      drawPlus(host, st.marks.plus[0], st.marks.plus[1], 0.2);
      drawSaltire(host, st.marks.x[0], st.marks.x[1], 0.2);
    }
    // What stands on the floor at fight time t, when the pull is (re)drawn.
    function drawFloorLive(){
      const t = clock.t;
      layer('p3-towers'); layer('p3-aoes');
      if(t >= LIVE.shock[0] && t < LIVE.shock[1]) drawPlainTowers(false);
      if(t >= LIVE.towersUp && t < LIVE.towers) drawBrightTowers(false);
      if(st.marks.plus && t < LIVE.aoes) drawMarks(false);
    }

    /* ---------- the mechanic resolving ---------- */
    function fxAdd(node, ms){
      if(T.isReplaying()) return;
      document.getElementById('p3-fx').appendChild(node);
      st.fxTimers.push(setTimeout(() => node.remove(), ms));
    }
    function burst(p, r, colour){
      fxAdd(el('circle', { cx:p[0].toFixed(1), cy:p[1].toFixed(1), r, fill:'none', stroke:colour, 'stroke-width':4, class:'p3-fx-burst', filter:'url(#glow)' }), 900);
    }
    function fxPlainTowers(){
      st.safe.forEach(t => burst(plainTower(t), TOWER_R + 6, 'var(--aether-soft)'));
      layer('p3-towers');
    }
    function fxDrops(){ st.brightSlots.forEach(s => burst(st.drops[s], 16, aspectSoft(st.bright))); }
    function fxGlow(){ st.brightSlots.forEach(s => burst(st.drops[s], GLOW_R, aspectSoft(st.bright))); }
    function fxMarks(){
      layer('p3-aoes');
      const g = el('g', { class:'p3-fx-flash' });
      drawPlus(g, st.marks.plus[0], st.marks.plus[1], 0.8);
      drawSaltire(g, st.marks.x[0], st.marks.x[1], 0.8);
      fxAdd(g, 1200);
    }
    function fxBrightTowers(){
      const tw = towerSpots();
      [tw.tile, tw.centre].forEach(p => burst(p, TOWER_R + 6, aspectSoft(st.bright)));
      layer('p3-towers');
    }

    // Against the clock a click anywhere sends you running there; you can change course at any time.
    function livePick(p){
      if(st.over) return;
      moveTo(st.me, p);
    }
    function endFreePick(){ document.getElementById('p3-freeHits').innerHTML = ''; }
    // The click layer over the whole floor: a ghost marker follows the pointer, and the arrow keys move it.
    function freePick(from, onPick){
      const host = layer('p3-freeHits');
      const g = el('g', { class:'hit free-pick', tabindex:'0', role:'button', 'data-free':'',
        'data-x': from[0].toFixed(1), 'data-y': from[1].toFixed(1),
        'aria-label':'Pick a spot on the arena to run to. Arrow keys move the marker, Enter confirms.' });
      g.appendChild(el('rect', { x:60, y:60, width:480, height:480, rx:6, class:'free-area' }));
      const ghost = el('g', { class:'free-ghost', 'pointer-events':'none', visibility:'hidden' });
      ghost.appendChild(el('circle', { cx:0, cy:0, r:15, class:'free-ring' }));
      const tag = el('text', { x:0, y:3.4, 'text-anchor':'middle', 'font-family':'Space Mono, monospace',
        'font-size':9, 'font-weight':700, fill:'var(--mist)' });
      tag.textContent = 'YOU';
      ghost.appendChild(tag);
      const place = p => {
        const x = Math.max(60, Math.min(540, p[0])), y = Math.max(60, Math.min(540, p[1]));
        g.setAttribute('data-x', x.toFixed(1));
        g.setAttribute('data-y', y.toFixed(1));
        ghost.setAttribute('transform', `translate(${x.toFixed(1)},${y.toFixed(1)})`);
        ghost.setAttribute('visibility', 'visible');
      };
      const current = () => [+g.getAttribute('data-x'), +g.getAttribute('data-y')];
      const pickIt = p => { if(g.getAttribute('aria-disabled') !== 'true') onPick(p); };
      g.addEventListener('pointermove', e => { if(g.getAttribute('aria-disabled') !== 'true') place(T.freePoint(g, e)); });
      g.addEventListener('pointerleave', () => { if(document.activeElement !== g) ghost.setAttribute('visibility', 'hidden'); });
      g.addEventListener('focus', () => place(current()));
      g.addEventListener('blur', () => ghost.setAttribute('visibility', 'hidden'));
      g.addEventListener('click', e => pickIt(T.freePoint(g, e)));
      g.addEventListener('keydown', e => {
        const d = e.shiftKey ? 24 : 8;
        const move = { ArrowLeft:[-d, 0], ArrowRight:[d, 0], ArrowUp:[0, -d], ArrowDown:[0, d] }[e.key];
        if(move){ e.preventDefault(); const c = current(); place([c[0] + move[0], c[1] + move[1]]); return; }
        if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); pickIt(current()); }
      });
      host.appendChild(g);
      host.appendChild(ghost);
    }

    /* ---------- step by step: the cast in position ---------- */
    // each wall add fires its line at the DPS it is tethered to, as the second step opens
    function fireTethers(){
      const pos = positions('two');
      T.playBeams(document.getElementById('p3-lasers'), st.ids.filter(isDps).map(id => ({ from: st.actors[id].add, through: pos[id] })));
    }
    function drawCast(stage, pos){
      stage = stage || (st.step < 3 ? 'two' : 'pre3');
      pos = pos || positions(stage);
      const towers = layer('p3-towers'), aoes = layer('p3-aoes');
      // the plain towers the supports have just soaked, fading out under them
      if(stage === 'two') st.safe.forEach(t => {
        const g = el('g', { opacity:0.35 });
        const [x, y] = plainTower(t);
        tower(g, x, y, null, null);
        towers.appendChild(g);
      });
      if(st.step >= 3){
        // the + and X go off as the aspected towers appear: the plus from the north platform's outer
        // corner, the X from the south wall
        drawPlus(aoes, ...mx(PLAN.plusMark));
        drawSaltire(aoes, ...mx(PLAN.xMark));
        const tw = towerSpots(), label = stage === 'pre3' && shared.role === 'dps' && st.job === 'soak';
        tower(towers, tw.tile[0], tw.tile[1], st.bright, label ? 'ON PLATFORM' : null);
        tower(towers, tw.centre[0], tw.centre[1], st.bright, label ? 'CENTRE' : null);
      }
      // The tether lasers fire as step 2 opens, so the tethers are gone from then on —
      // the straight and crossed tags stay, since that is how you still know which is which.
      drawParty(pos, { tethered: st.step < 2, tags: true });
    }
    // The last step as it resolves: everyone at their job, you wherever you chose, and each
    // yellow-crystal add firing at whoever is nearest to it.
    function resolveLast(myXY){
      const pos = positions('res3');
      if(myXY) pos[st.me] = myXY;
      drawCast('res3', pos);
      drawWhiteFlame(pos);
      return pos;
    }
    // Each yellow-crystal add fires a line at each of its two nearest players, wherever they stand.
    function drawWhiteFlame(pos){
      const host = document.getElementById('p3-chains');
      flameTargets(pos).forEach(l => l.ids.forEach(id => {
        const t = pos[id], dx = t[0] - l.from[0], dy = t[1] - l.from[1];
        const len = Math.hypot(dx, dy) || 1;
        const ex = l.from[0] + dx / len * 900, ey = l.from[1] + dy / len * 900;
        const common = { x1:l.from[0], y1:l.from[1], x2:ex.toFixed(1), y2:ey.toFixed(1),
          'clip-path':'url(#arenaClip)', 'pointer-events':'none' };
        host.appendChild(el('line', Object.assign({}, common, {
          stroke:'var(--aether)', 'stroke-width':2 * FLAME_HALF, opacity:0.18 })));
        host.appendChild(el('line', Object.assign({}, common, {
          stroke:'var(--aether-soft)', 'stroke-width':2, opacity:0.5, 'stroke-dasharray':'9 6' })));
      }));
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

    function renderBadges(){
      const host = document.getElementById('p3-badges');
      const t = clock.t, text = document.getElementById('p3-assignText');
      const enchained = `<div class="badge role"><img src="assets/enchained-soul.png" alt=""><span>Enchained Soul</span></div>`;
      let rows = !st.live || t >= LIVE.enchained ? enchained : '';
      if(shared.role === 'support'){
        if(st.live && t < LIVE.debuffs){
          host.innerHTML = '<div class="badge"><span>No debuff yet</span></div>';
          text.innerHTML = `Engravement of Souls hands them out at ${LIVE.debuffs.toFixed(1)} s.`;
          return;
        }
        const s = SOUL[st.mySoul === 'bright' ? st.bright : st.mySoul];
        rows += `<div class="badge ${s.cls}"><img src="${s.icon}" alt=""><span>${s.label}</span></div>`;
        text.innerHTML = `You are <b>${st.mySlot}</b>. Supports take the souls this mechanic, DPS take the tethers.`;
      } else {
        if(st.live && t < LIVE.tethers){
          host.innerHTML = '<div class="badge"><span>No tether yet</span></div>';
          text.innerHTML = `The wall adds tether the DPS at ${LIVE.tethers.toFixed(1)} s.`;
          return;
        }
        const cls = st.myColor === 'astral' ? 'astral' : 'umbral';
        rows += st.live && t >= LIVE.laserHit
          ? `<div class="badge ${cls}"><img src="${tiltIcon(st.myColor)}" alt=""><span>${aspectLabel(st.myColor)} Tilt</span></div>`
          : `<div class="badge ${cls}"><svg viewBox="0 0 24 24"><use href="#icon-add"/></svg><span>${lightWord(st.myColor)} tether</span></div>`;
        text.innerHTML = `Your tether runs to an add on the <b>${st.mySide}</b> wall. Both adds on a wall share one colour.`;
      }
      host.innerHTML = rows;
    }

    // what to do now, against the clock: the text before the clock starts, then each phase for your role
    const PRE_TEXT = `Athena has cast Paradeigma: six adds are on their way to the walls and the corners, and Engravement of Souls is next. The fight clock runs in real time from here. Press Start, then click to move as the fight unfolds.`;
    function phaseAt(t){
      if(shared.role === 'dps') return t < LIVE.tethers ? 0 : t < LIVE.lasers ? 1 : 2;
      if(t < LIVE.debuffs) return 0;
      if(t < LIVE.enchain[1]) return 1;
      return t < (st.mySoul === 'bright' ? LIVE.drop : LIVE.marks) ? 2 : 3;
    }
    function phaseText(i){
      if(shared.role === 'dps'){
        if(i === 0) return ['Paradeigma III', `Wait by Athena for your tether: Engravement of Souls is going out.`];
        if(i === 1) return ['Step 1 · Stretch', `Stretch your tether across to the middle platform on the far side from your add.<span class="hint"> The tiles chained by Unnatural Enchainment fall as it ends. If your add lines up with the platform yours is the <b>straight</b> tether: stand level with your add on the line of waymark B (eastern platform) or D (western), no closer: under about 34.5 yalms from the add its laser kills you. Otherwise it is <b>crossed</b>: stand at the middle of its outer edge, top on the northern platform, bottom on the southern.</span>`];
        return ['Step 2 · Soak or bait', `Soak a tower or bait White Flame, by your Tilt against the towers' colour.<span class="hint"> Opposite colour soaks: wait clear of the bright souls' small AoEs, then the <b>straight</b> tether takes the tower on the centre corner, the <b>crossed</b> tether the one in the middle of your platform. Same colour baits: the yellow add closest to you, from the corner of your platform facing it.</span>`];
      }
      if(i === 0) return ['Paradeigma III', `Wait by Athena for your Soul: Engravement of Souls is going out.`];
      if(i === 1) return ['Step 1 · Plain tower', `Take the plain tower on your platform before the chained tiles fall.<span class="hint"> Quartered Soul takes the <b>north-most</b> platform and X-marked the <b>south-most</b>; the two bright souls take the middle two by priority <b>H1 &gt; T1 &gt; T2 &gt; H2</b>, west to east. On a middle platform soak from the tower's side away from the arena's centre line, in the gap the DPS lasers leave.</span>`];
      if(i === 2){
        if(st.mySoul === 'bright') return ['Step 2 · Your tower', `Drop your aspected tower as your Soul runs out.<span class="hint"> DPS on your platform the <b>opposite</b> colour: in the middle of your platform, clear of the X's arm. The <b>same</b> colour: on your platform's arena-centre corner, as close to the middle as you can, so it spills onto the other middle platform.</span>`];
        return ['Step 2 · Your AoE', `Drop your ${st.mySoul === 'quartered' ? 'plus' : 'X'} as your Soul runs out, then step out of its arms.<span class="hint"> Both are fixed to true north: the <b>plus</b> from the north platform's outer corner, so its arms run along the walls; the <b>X</b> from the south wall, so its arms run out to the corners.</span>`];
      }
      if(st.mySoul === 'bright') return ['Step 3 · Clear', `Step out of your tower, clear of the yellow adds and their lines.<span class="hint"> The tower is for the DPS; your Soul's small AoE leaves you too vulnerable to stand in it.</span>`];
      return ['Step 3 · White Flame', `Bait White Flame from the yellow add beside your platform, out of the ${st.mySoul === 'quartered' ? 'plus' : 'X'}.<span class="hint"> The <b>plus</b> baits from just beside the northern add, away from the middle. An arm of the <b>X</b> runs through the southern add: wait for it to go off, then bait from just below the add.</span>`];
    }
    function liveText(){
      const [p, h] = phaseText(phaseAt(clock.t));
      pill(p); instr(h);
    }

    function clearBoard(){
      layer('p3-tethers'); layer('p3-actors'); layer('p3-hits'); layer('p3-zones'); layer('p3-lasers'); layer('p3-target');
      layer('p3-towers'); layer('p3-aoes');
      fb.hidden = true;
      drawTiles();
      drawAdds();
    }

    function render(){
      renderPick();
      renderBadges();
      renderLive();
      clearBoard();
      // against the clock the step text keeps the height of the tallest it will show, so the arena holds still
      T.holdPrompt('para3', st.live ? [PRE_TEXT, ...[0, 1, 2, 3].map(i => phaseText(i)[1])] : null);
      if(st.live){
        drawFloorLive();
        drawLive();
        if(!clock.running && clock.t <= LIVE.start){
          pill('Paradeigma III');
          instr(PRE_TEXT);
        } else liveText();
        return;
      }
      if(shared.role === 'support') renderSupport(); else renderDps();
    }

    function renderSupport(){
      const soulKey = st.mySoul === 'bright' ? st.bright : st.mySoul;
      if(st.step === 1){
        pill('Step 1 · Take your tower');
        instr(`Unnatural Enchainment is casting and the red tiles are going away. A plain tower is landing on each platform that survives. Holding <span class="hl">${SOUL[soulKey].label}</span> as <span class="hl">${st.mySlot}</span>, which tower do you soak?<span class="hint"> <b>Quartered Soul</b> takes the north-most platform and <b>X-marked</b> the south-most; the two bright souls take the middle two by priority <b>H1 &gt; T1 &gt; T2 &gt; H2</b>, west to east.</span>`);
        const towers = layer('p3-towers');
        st.safe.forEach(t => { const [x, y] = plainTower(t); tower(towers, x, y, null, null); });
        // every support's soul is on show, so the priority can be worked out from the party
        const actors = layer('p3-actors');
        st.stackOrder.forEach((slot, i) => {
          const soul = st.slotSoul[slot] === 'bright' ? st.bright : st.slotSoul[slot];
          unit(actors, 216 + i * 56, 236, JOB[slot], {
            me: slot === st.mySlot, tag: slot, icon: SOUL[soul].icon,
            color: JOB[slot] === 'tank' ? 'var(--umbral-soft)' : 'var(--good)'
          });
        });
        spotHits(st.safe.map(t => ({ id:t.key, x:plainTower(t)[0], y:t.cy, r:31,
          ariaLabel:`Plain tower on the ${tileName(t).toLowerCase()} platform` })), answerTile);
      }
      else if(st.step === 2){
        drawCast();
        if(st.mySoul === 'bright'){
          pill('Step 2 · Drop your tower');
          instr(`Plain tower soaked. Your <span class="hl">${SOUL[soulKey].label}</span> is about to drop an aspected one, and the two DPS on your tile, tethered to the <span class="hl">far</span> wall, are <b style="color:${aspectSoft(st.myDpsColor)}">${lightWord(st.myDpsColor)}</b>. Where do you drop your aspected tower?<span class="hint"> If the DPS on your tile share your colour they cannot soak it, so push it over the <b>arena-centre corner</b> to the other middle platform; if they are the opposite colour, drop it in the <b>middle of your own tile</b>.</span>`);
          const mid = mx(PLAN.drop.soak[st.home.row]);
          spotHits([
            { id:'tile',   x:mid[0], y:mid[1], mark:'A', label:'Middle of your own tile' },
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
        instr(`Your tether runs to the <span class="hl">${st.myAddY === 240 ? 'northern' : 'southern'}</span> of the two <span class="hl">${lightWord(st.myColor)}</span> adds on the <span class="hl">${st.mySide}</span> wall. Click the spot you take.<span class="hint"> Stretch it across: both DPS from one wall cross to the <b>opposite middle platform</b>: if your add lines up with it yours is the <b>straight</b> tether, level with your add right on the line of waymark B or D (only half a yalm past where its laser kills you, so no closer, and no further out than the waymark); otherwise yours is <b>crossed</b>, at the middle of the platform's outer edge (top on the northern platform, bottom on the southern).</span>`);
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
          instr(`Two ${lightWord(st.bright)} towers are down. Your tether is the <span class="hl">${st.straight ? 'straight' : 'crossed'}</span> one — which tower is yours?<span class="hint"> The <b>straight</b> tether takes the one pushed to the middle, the <b>crossed</b> tether the tower in the middle of the platform.</span>`);
          const tw = towerSpots();
          spotHits([
            { id:'tile',   x:tw.tile[0], y:tw.tile[1], mark:'A' },
            { id:'centre', x:tw.centre[0], y:tw.centre[1], mark:'B' }
          ], answerTowerPick);
        } else {
          pill('Step 3 · Bait the laser');
          instr(`Your colour matches the towers, so they are not yours. <span class="hl">Enchained Soul</span> keeps you on your own tile — click the spot you bait a <span class="hl">yellow-crystal add</span> from.<span class="hint"> Take the <b>corner facing an add</b>: you and the + or X support on the platform beside it are its two nearest players, so it fires one line at each of you. Your pair splits, the add closest to each of you.</span>`);
          const adds = document.getElementById('p3-adds');
          [st.addN, st.addS].forEach(ad => {
            adds.appendChild(el('circle', { cx:ad.x, cy:ad.y, r:22, fill:'none',
              stroke:'var(--aether)', 'stroke-width':2.5, class:'pulse' }));
          });
          spotHits(baitSpots(), answerBait);
        }
      }
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

    // Where the + or X could go on your platform: its outer corner, the cardinal point on the wall, or the corner
    // facing the middle; each a yalm in from the edge.
    function aoeSpots(){
      const t = st.home;
      const cornerX = t.col === 'L' ? 72 : 528;
      const cardX = t.col === 'L' ? 288 : 312;
      const cornerY = t.row === 1 ? 72 : 528;
      const innerY  = t.row === 1 ? 168 : 432;
      return [
        { id:'corner',   x:cornerX, y:cornerY, mark:'A', label:'Outer arena corner' },
        { id:'cardinal', x:cardX,   y:cornerY, mark:'B', label:'Cardinal wall point' },
        { id:'inner',    x:cardX,   y:innerY,  mark:'C', label:'Inner corner, toward the middle' }
      ];
    }

    /* ---------- answers, step by step ---------- */
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
        ? lead + ` Your add lines up with that platform, so yours is the <b>straight</b> tether: stand <b>level with your add on the line of waymark ${st.home.col === 'R' ? 'B' : 'D'}</b>, so your laser runs dead east–west. That is only half a yalm past where your own laser kills you outright (about 34.5 yalms from the add), so stand right on the waymark's line: not any closer to the add, and no further out.`
        : lead + ` Your add does not line up with it, so yours is the <b>crossed</b> tether: stand at the <b>middle of the platform's outer edge</b> — ${st.home.row === 2 ? 'top middle, as this is the northern middle platform' : 'bottom middle, as this is the southern middle platform'} — so your laser angles across. Together the two lasers leave an outer gap on the plain tower for the support.`;
      judge(ok, ok ? 'Good spot' : 'Wrong spot', why, 2);
    }

    function answerTile(key){
      lock();
      const ok = key === st.home.key;
      let why;
      if(st.mySoul === 'quartered'){
        why = `Quartered Soul always takes the tower on the <b>north-most</b> platform — this pull that is the ${st.north.col === 'L' ? 'west' : 'east'} tile on the top row.`;
      } else if(st.mySoul === 'xmarked'){
        why = `X-marked Soul always takes the tower on the <b>south-most</b> platform — this pull the ${st.south.col === 'L' ? 'west' : 'east'} tile on the bottom row.`;
      } else {
        const west = st.brightWest, east = st.brightSlots.find(s => s !== west);
        why = `The bright souls went to <b>${west}</b> and <b>${east}</b>. They go by priority H1 &gt; T1 &gt; T2 &gt; H2, west to east, so ${west} takes the tower on the <b>western</b> middle platform and ${east} the one on the <b>eastern</b>. You are ${st.mySlot}. Soak it from its side <b>away from the arena's horizontal centre line</b>: the DPS on your platform stretch their tethers right beside it, and you have to stand in the outer gap their two lasers leave, or one clips you.`;
      }
      judge(ok, ok ? 'Right tower' : 'Wrong tower', why, 2);
    }

    function answerTower(id){
      lock();
      const ok = id === st.towerSpot;
      const same = st.myDpsColor === st.bright;
      const why = same
        ? `Your tower is <b>${lightWord(st.bright)}</b> and so are the two DPS on your tile, so they cannot take it. Drop it on the <b>arena-centre corner</b> of your tile and it spills onto the other middle platform, where the ${lightWord(st.bright === 'astral' ? 'umbral' : 'astral')} pair is waiting.`
        : `Your tower is <b>${lightWord(st.bright)}</b> and the DPS on your tile are <b>${lightWord(st.myDpsColor)}</b> — opposite colours, so they can soak it. Drop it in the <b>middle of your own tile</b>, clear of their tether lasers${st.home.row === 3 ? ' and of the arm of the X' : ''}.`;
      const p = id === 'centre' ? centreCorner(st.home, 16) : mx(PLAN.drop.soak[st.home.row]);
      tower(layer('p3-towers'), p[0], p[1], st.bright, null);
      judge(ok, ok ? 'Tower placed' : 'Wrong spot', why, 3);
    }

    function answerAoe(id){
      lock();
      const correct = st.mySoul === 'quartered' ? 'corner' : 'cardinal';
      const ok = id === correct;
      const spots = aoeSpots();
      // the AoE lands where you chose to stand, so a wrong spot shows what it cuts through
      const picked = spots.find(s => s.id === id);
      const host = layer('p3-aoes');
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
      const tw = towerSpots();
      resolveLast(id === 'tile' ? tw.tile : clampTo(tw.centre, st.home, 4));
      const why = st.straight
        ? `Yours is the <b>straight</b> tether, so you take the tower on the <b>centre corner</b> — the one the other support pushed over from their platform, a short step from where you stand — and leave the platform tower to the crossed tether.`
        : `Yours is the <b>crossed</b> tether, so you take the tower in the <b>middle of your platform</b> and leave the centre one to the straight tether.`;
      judge(ok, ok ? 'Paradeigma III cleared' : 'Wrong tower', why, 4);
    }

    function answerBait(id){
      lock();
      const ok = id === 'addN' || id === 'addS';
      layer('p3-hits');
      const spot = baitSpots().find(sp => sp.id === id);
      const pos = positions('res3');
      pos[st.me] = [spot.x, spot.y];
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
        if(id === 'soak') return dropAt(t);
        if(id === 'bait'){
          const ad = dist([t.cx, t.cy], [st.addN.x, st.addN.y]) <= dist([t.cx, t.cy], [st.addS.x, st.addS.y]) ? st.addN : st.addS;
          return clampTo([ad.x, ad.y], t, 12);
        }
        return null;                                   // step aside: where everyone expects you
      }
      if(id === 'soak') return clampTo(nearestTower, t, 14);
      if(id === 'hold') return plan(st.me, 'job');      // out on the wall, right where your own AoE lands
      return null;                                     // bait: at your add
    }

    function answerLast(id){
      lock();
      let correct, why;
      if(st.mySoul === 'bright'){
        correct = 'clear';
        why = `The tower you dropped belongs to a DPS, not to you — you already soaked the plain one. <b>Step aside</b> and make sure you are not standing in a tower or in the + and X AoEs.`;
      } else {
        correct = 'bait';
        why = `Once your AoE is down you move in and <b>bait White Flame</b> from the add beside your platform, pointing the line away from the middle. Your ${st.mySoul === 'quartered' ? 'plus' : 'X'} is <b>delayed</b>, so get out of its arms first${st.mySoul === 'xmarked' ? ': one runs right through your add, so wait for the X to go off, then bait from just below the add' : ', then bait from just beside the add, on its side away from the middle'}. Each of the two adds needs two baiters: you and one of the DPS whose colour matched the towers.`;
      }
      const ok = id === correct;
      // A + or X support has no tower within reach: Enchained Soul pins them to a platform with the
      // floor gone all round it.
      if(st.mySoul !== 'bright' && id === 'soak'){
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
      const without = Object.assign({}, pos);
      delete without[st.me];
      drawCast('res3', Object.assign({}, pos, { [st.me]: edge }));
      drawWhiteFlame(without);
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

  T.register({ id: 'para3', label: 'Paradeigma III', phase: 'Athena', players: 'supports', playersNote: 'Supports are seated by priority, H1 > T1 > T2 > H2 west to east, so each has their own place; all four DPS play it the same way.', markup: MARKUP, styles: STYLES, init: initPara3 });
})(window.Twelfth);
