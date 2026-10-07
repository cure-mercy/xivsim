/* Superchain Theory I: read the chains, then resolve your aspect, shape and tower. */
(function(T){

  const { shared, showFeedback, shuffle } = T;

  const STYLES = /* css */ `
    /* Real time: the fight clock and the casts running, above the arena */
    .sc-live{ display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; border: 1px solid var(--line);
      border-radius: 12px; background: var(--nebula); }
    .sc-live-head{ display: flex; align-items: center; gap: 12px; }
    .sc-clock{ font-family: var(--font-mono); font-weight: 700; font-size: 1.05rem; color: var(--mist);
      font-variant-numeric: tabular-nums; }
    .sc-clock small{ font-size: 0.7rem; color: var(--mist-faint); font-weight: 400; margin-left: 4px; }
    .sc-live-note{ flex: 1; font-size: 0.8rem; color: var(--mist-dim); }
    .sc-casts{ display: flex; flex-direction: column; gap: 6px; min-height: 26px; }
    .sc-cast{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 3px 10px; font-size: 0.8rem; color: var(--mist-dim); }
    .sc-cast b{ color: var(--mist); font-weight: 600; }
    .sc-left{ font-family: var(--font-mono); font-variant-numeric: tabular-nums; color: var(--mist); }
    .sc-cast-bar{ grid-column: 1 / -1; height: 5px; border-radius: 3px; background: var(--line); overflow: hidden; }
    .sc-cast-bar i{ display: block; height: 100%; background: var(--aether); transform-origin: left center; }
    .sc-cast.mine .sc-cast-bar i{ background: var(--brand-soft); }
    .sc-cast.mine .sc-left{ color: var(--brand-soft); }
    .sc-idle{ font-size: 0.8rem; color: var(--mist-faint); }
    /* the mechanic resolving: the AoEs flash, the towers pop in, the souls burst */
    .sc-fx-pop, .sc-fx-burst{ transform-box: fill-box; transform-origin: center; }
    @media (prefers-reduced-motion: no-preference){
      .sc-fx-pop{ animation: sc-pop 0.5s cubic-bezier(0.3, 1.5, 0.6, 1) both; }
      .sc-fx-burst{ animation: sc-burst 0.8s ease-out forwards; }
      .sc-fx-flash{ animation: sc-flash 1.1s ease-out forwards; }
      .sc-fx-aoe{ animation: sc-aoe 1.6s ease-out forwards; }
    }
    @media (prefers-reduced-motion: reduce){ .sc-fx-burst, .sc-fx-flash{ display: none; } }
    @keyframes sc-pop{ from{ transform: scale(0.2); opacity: 0; } to{ transform: scale(1); opacity: 1; } }
    @keyframes sc-burst{ from{ transform: scale(0.5); opacity: 1; } to{ transform: scale(1.6); opacity: 0; } }
    @keyframes sc-flash{ 0%{ opacity: 0; } 15%{ opacity: 0.9; } 100%{ opacity: 0; } }
    @keyframes sc-aoe{ 0%{ opacity: 0; } 12%{ opacity: 1; } 70%{ opacity: 1; } 100%{ opacity: 0; } }
    /* the debuff to practise: the six Engravement of Souls hands out, or any of them */
    .sc-pick-label{ margin: 14px 0 8px; font-family: var(--font-mono); font-size: 0.7rem; letter-spacing: 0.14em;
      text-transform: uppercase; color: var(--mist-faint); }
    .role-select.sc-debuff-pick{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 6px; margin-bottom: 8px; }
    .sc-debuff-pick .role-btn{ padding: 6px 4px; gap: 2px; min-height: 40px; }
    .sc-debuff-pick .role-btn img{ width: 18px; height: 24px; object-fit: contain; display: block; }
    .sc-debuff-pick .sc-any{ grid-column: span 2; font-size: 0.86rem; }
    /* against the clock there is no stepping back: only a new pull */
    .layout.sc-timed .history-ctrls [data-history="undo"],
    .layout.sc-timed .history-ctrls [data-history="redo"],
    .layout.sc-timed .history-ctrls [data-history="rewind"]{ display: none; }
  `;

  const MARKUP = /* html */ `
  <div class="layout" id="panel-superchain" role="tabpanel" aria-labelledby="tabBtn-superchain" hidden>

    <section class="arena-wrap">
      <div class="step-row">
        <span class="step-pill" id="sc-stepPill">Step 1 · Call your spot</span>
      </div>

      <div class="sc-live" id="sc-live" hidden>
        <div class="sc-live-head">
          <span class="sc-clock" id="sc-clock">0.0<small>s</small></span>
          <span class="sc-live-note" id="sc-liveNote"></span>
          <button type="button" class="btn" id="sc-start">Start ▶</button>
        </div>
        <div class="sc-casts" id="sc-casts"></div>
      </div>

      <svg class="arena-svg" id="sc-arena" style="--zone-band: 23.09%" viewBox="48.8 48.8 502.4 618.4" role="img" aria-label="Top-down view of the Twelfth Circle arena with Athena's four Superchain clusters">
        <!-- floor -->
        <rect x="60" y="60" width="480" height="480" rx="6" fill="url(#floor)"/>
        <image href="assets/arena-phase1.svg" x="60" y="60" width="480" height="480" preserveAspectRatio="none" pointer-events="none"/>
        <!-- Athena's target circle: one column width in radius, as in Paradeigma II -->
        <circle cx="300" cy="300" r="120" fill="none" stroke="rgba(247,147,30,0.45)" stroke-width="1.6" stroke-dasharray="4 6" pointer-events="none"/>
        <rect x="60" y="60" width="480" height="480" rx="6" fill="none" stroke="rgba(247,147,30,0.55)" stroke-width="2" filter="url(#glow)"/>

        <!-- what has gone off, under everything else -->
        <g id="sc-under" clip-path="url(#arenaClip)" pointer-events="none"></g>

        <!-- boss -->
        <g class="spin" filter="url(#glow)">
          <g transform="translate(300,300)" fill="var(--aether)">
            <path d="M0 -22 L6 -6 L22 0 L6 6 L0 22 L-6 6 L-22 0 L-6 -6 Z"/>
          </g>
        </g>
        <circle cx="300" cy="300" r="9" fill="var(--void)" stroke="var(--aether)" stroke-width="1.5"/>

        <!-- dynamic layers, all drawn per step by JS -->
        <g id="sc-axis"></g>
        <g id="sc-clusters"></g>
        <g id="sc-towers" pointer-events="none"></g>
        <g id="sc-beams" pointer-events="none"></g>
        <g id="sc-players" pointer-events="none"></g>
        <g id="sc-fx" pointer-events="none"></g>
        <g id="sc-groups"></g>
        <g id="sc-zones"></g>

        <!-- player marker -->
        <g id="sc-playerMarker" opacity="0">
          <circle cx="300" cy="300" r="10" fill="var(--mist)" filter="url(#glow)"/>
        </g>

        <!-- after a wrong answer: where you should have been -->
        <g id="sc-target" pointer-events="none"></g>
        <!-- against the clock: click anywhere to run there -->
        <g id="sc-freeHits"></g>
      </svg>

      <p class="arena-caption">Left and right are called from your own view, looking towards the boss.</p>

      <div class="feedback" id="sc-feedback" hidden aria-live="polite"></div>
    </section>

    <aside class="hud">
      <div class="card player-card">
        <div class="card-head">
          <h2>Pace</h2>
          <span class="info-tip">
            <button type="button" class="info-btn" aria-label="About the pace" aria-expanded="false" aria-describedby="sc-paceTip">?</button>
            <span class="info-pop" role="tooltip" id="sc-paceTip"><b>Step by step</b> pauses the fight at each step while you answer each call. <b>Real time</b> runs the fight clock from a log: click anywhere to move, and where you stand when each cluster, laser, tower and Heavensflame goes off is what counts.</span>
          </span>
        </div>
        <div class="role-select player-select cols-2" role="group" aria-label="Choose the pace">
          <button type="button" class="role-btn" data-pace="steps"><span>Step by step</span></button>
          <button type="button" class="role-btn" data-pace="live"><span>Real time</span></button>
        </div>
      </div>

      <div class="card">
        <h2>Engravement of Souls</h2>
        <div class="assign-row" id="sc-badges"></div>
        <p class="assign-text hint-only" id="sc-assignText"></p>
        <div class="sc-pick-label" id="sc-pickLabel">Practise</div>
        <div class="role-select sc-debuff-pick" id="sc-debuffPick" role="group" aria-labelledby="sc-pickLabel"></div>
        <p class="player-note hint-only" id="sc-pickNote"></p>
      </div>

      <div class="card">
        <h2>Objective</h2>
        <p class="instr-text" id="sc-instrText"></p>
      </div>

      <details class="card">
        <summary>How the call works</summary>
        <ol>
          <li><b>Engravement of Souls</b> splits the party 4/4. One role takes <b>Heavensflame Soul</b> plus a Tilt — two Astral, two Umbral. The other role takes one each of <b>Astralbright</b>, <b>Umbralbright</b>, <b>Astralstrong</b> and <b>Umbralstrong Soul</b>.</li>
          <li>Four clusters spawn on the intercardinals. The one with <b>two short chains</b> resolves first.</li>
          <li>Read its two shapes: a <b>Blue donut</b> means get in, a <b>Green orb</b> is point-blank so stay out; an <b>Orange spiked ball</b> cones every player so spread, a <b>Purple jack</b> cones one role so pair up across roles. The spots are relative to Athena, as for the lasers: facing her from the cluster, the tanks in front, then melee, healers and ranged behind, the 1s on your right and the 2s on your left. To pair, each DPS stacks with the support beside it (M1 with T1, M2 with T2, R1 with H1, R2 with H2), midway between their spots.</li>
          <li>Rotate 90° to the cluster chained to <b>only a blue donut</b> — that's where the Impact lasers land. Astral Impact can only be shared by Umbral-family players and vice versa, so the split is <b>Astralstrong + Umbralbright + both Umbral Tilts</b> against <b>Umbralstrong + Astralbright + both Astral Tilts</b>. Note each <b>strong</b> soul stands with the group named opposite to it — it's their own laser being shared. Facing the boss, the first group is on your <b>left</b> and the second on your <b>right</b>. The debuff icons show it: the figure on each Tilt leans to its side (Astral right, Umbral left), and each strong soul's laser aims to its side (Astral left, Umbral right).</li>
          <li>Rotate again to the last cluster, chained to both a green orb and a blue donut. The <b>shorter chain resolves first</b>, so it's either out-then-in or in-then-out.</li>
          <li>At the last cast the jobs split three ways: the <b>bright</b> souls drop the towers on the two cardinals beside the last cluster at max melee, the two <b>strong</b> souls soak them now that their own lasers have fired, and the four <b>Heavensflame</b> players spread well away from everyone before their AoEs land: melee run through Athena all the way to the far side, ranged run back into the corner behind the last cluster, the 1s on the right and the 2s on the left. Heavensflame never soaks.</li>
          <li>A tower takes the <b>opposite Tilt</b>. Each bright soul drops a tower of its own aspect, and each strong soul holds the Tilt of its own laser, so <b>Umbralstrong</b> soaks Astralbright's tower and <b>Astralstrong</b> soaks Umbralbright's. Facing the boss, the Astral tower is on the <b>right</b> and the Umbral one on the <b>left</b>: each pair already shared a laser group, so nobody crosses over.</li>
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

      <div class="card">
        <h2>Debuffs</h2>
        <div class="legend-list">
          <div class="legend-item"><img src="assets/astralbright-soul.png" alt=""><span><b>Astralbright Soul</b> — drops a tower<span class="hint">; laser on your right, drops the right tower</span></span></div>
          <div class="legend-item"><img src="assets/umbralbright-soul.png" alt=""><span><b>Umbralbright Soul</b> — drops a tower<span class="hint">; laser on your left, drops the left tower</span></span></div>
          <div class="legend-item"><img src="assets/astralstrong-soul.png" alt=""><span><b>Astralstrong Soul</b> — targeted by Astral Impact<span class="hint">; on your left, then soaks the left tower</span></span></div>
          <div class="legend-item"><img src="assets/umbralstrong-soul.png" alt=""><span><b>Umbralstrong Soul</b> — targeted by Umbral Impact<span class="hint">; on your right, then soaks the right tower</span></span></div>
          <div class="legend-item"><img src="assets/heavensflame-soul.png" alt=""><span><b>Heavensflame Soul</b> — spread AoE<span class="hint">; never soaks</span></span></div>
          <div class="legend-item"><img src="assets/astral-tilt.png" alt=""><span><b>Astral Tilt</b> — can share an Impact laser<span class="hint">: Umbral Impact, on your right</span></span></div>
          <div class="legend-item"><img src="assets/umbral-tilt.png" alt=""><span><b>Umbral Tilt</b> — can share an Impact laser<span class="hint">: Astral Impact, on your left</span></span></div>
        </div>
      </div>
    </aside>

  </div>
  `;

  function initSuperchain(){
    const SVGNS = 'http://www.w3.org/2000/svg';
    const RAD = Math.PI / 180;
    const CW = ['NE','SE','SW','NW'];
    // The clusters sit 8 yalms out on the intercardinals (as in the log), 12 units to the yalm.
    const CPOS = { NE:[396,204], SE:[396,396], SW:[204,396], NW:[204,204] };
    const CANG = { NE:-45, SE:45, SW:135, NW:-135 };   // outward from the boss, degrees
    const SLOTS = ['T1', 'T2', 'H1', 'H2', 'M1', 'M2', 'R1', 'R2'];
    const roleOf = s => (s[0] === 'T' || s[0] === 'H') ? 'support' : 'dps';
    const JOB_COLOR = { T:'var(--umbral-soft)', H:'var(--good)', M:'var(--astral-soft)', R:'var(--astral-soft)' };

    const SHAPE = {
      orb:    { icon:'#icon-orb',   color:'var(--good)',         label:'Green orb' },
      donut:  { icon:'#icon-donut', color:'var(--umbral-soft)',  label:'Blue donut' },
      orange: { icon:'#icon-add',   color:'var(--shape-orange)', label:'Orange spiked ball' },
      purple: { icon:'#icon-jack',  color:'var(--shape-purple)', label:'Purple jack' }
    };

    const DEBUFF = {
      astralbright: { label:'Astralbright Soul', icon:'assets/astralbright-soul.png', fam:'astral', kind:'bright' },
      umbralbright: { label:'Umbralbright Soul', icon:'assets/umbralbright-soul.png', fam:'umbral', kind:'bright' },
      astralstrong: { label:'Astralstrong Soul', icon:'assets/astralstrong-soul.png', fam:'astral', kind:'strong' },
      umbralstrong: { label:'Umbralstrong Soul', icon:'assets/umbralstrong-soul.png', fam:'umbral', kind:'strong' },
      heavensflame: { label:'Heavensflame Soul', icon:'assets/heavensflame-soul.png', fam:null,     kind:'flame' },
      astraltilt:   { label:'Astral Tilt',       icon:'assets/astral-tilt.png',       fam:'astral', kind:'tilt' },
      umbraltilt:   { label:'Umbral Tilt',       icon:'assets/umbral-tilt.png',       fam:'umbral', kind:'tilt' }
    };

    // Astral Impact can only be shared by Umbral-family players and vice versa, so each
    // strong soul ends up standing with the group named opposite to itself.
    // Sides are called from the player's view, facing the boss, and match the debuff icons: the figure
    // on each Tilt leans to its side (Astral right, Umbral left) and each strong soul's laser aims to its
    // side (Astral left, Umbral right).
    const GROUP = {
      astralstrong:'left',  umbralbright:'left',  umbraltilt:'left',
      umbralstrong:'right', astralbright:'right', astraltilt:'right'
    };

    const SOUL_POOL = ['astralbright','umbralbright','astralstrong','umbralstrong'];
    // What you can choose to practise: any of the six debuff sets Engravement of Souls hands out, or a random
    // one each pull. Choosing one also settles which role group holds Heavensflame.
    const PICKS = [
      { id:'astralbright', key:'astralbright', icons:['astralbright'] },
      { id:'umbralbright', key:'umbralbright', icons:['umbralbright'] },
      { id:'astralstrong', key:'astralstrong', icons:['astralstrong'] },
      { id:'umbralstrong', key:'umbralstrong', icons:['umbralstrong'] },
      { id:'flame-astral', key:'astraltilt', icons:['heavensflame', 'astraltilt'] },
      { id:'flame-umbral', key:'umbraltilt', icons:['heavensflame', 'umbraltilt'] },
      { id:'random', key:null, icons:[] }
    ];
    const pickLabel = p => !p.key ? 'Random' : p.icons.map(k => DEBUFF[k].label).join(' + ');
    let practise = 'random';
    try{ const saved = localStorage.getItem('twelfth-sc-debuff'); if(PICKS.some(p => p.id === saved)) practise = saved; }catch(e){}

    /* ---------- real time ---------- */
    // Seconds after Athena's Superchain Theory I cast ends, from a P12S log (FFLogs report n8hcdZG2gx9LrQT7,
    // pull 26, checked against BY6AVjCDP7ZrWRQt, pull 33).
    const LIVE = {
      start: 0,
      engrave: [3.17, 7.13],      // Athena casts Engravement of Souls
      debuffs: 8.25,              // and the Souls and Tilts land
      first: 12.22,               // the first cluster: its distance shape and its cones (12.26) together
      second: 19.18,              // the donut-only cluster, with the far cluster's orb
      lasers: 19.54,              // Astral and Umbral Impact fire along their lines
      laserHit: 20.2,             // and land: everyone they hit takes that laser's Tilt
      third: [24.22, 26.18],      // the last cluster: the shorter chain, then the longer
      drop: 27.25,                // the bright Souls run out and the towers drop
      glow: 28.27,                // the bright Souls' small AoEs land
      towersUp: 28.67,            // and only then do the towers appear and start casting
      flame: 29.30,               // Heavensflame Soul runs out: Theos's Holy on each of the four (lands 29.9)
      towers: 30.63,              // the towers resolve
      towerHit: 31.1,             // and land: the soaker's Tilt turns to the tower's colour
      end: 31.4
    };
    const STRONG_END = 19.22;      // the strong Souls run out as their lasers go
    // Everyone runs at 7 yalms a second (a little above the real 6), and the rest of the party moves off
    // about 2 seconds after each thing they need to read.
    const SPEED = 84, REACT = 2.0, STEP_OFF = 0.05, TICK_MS = 33;
    // step by step nobody is racing the clock, so everyone runs twice as fast
    const STEP_SPEED = SPEED * 2;
    // In yalms times 12: inside the donut's gap within 6, the orb reaches 7, each cone is 30° across,
    // an Impact laser about 4 wide, a tower 5 wide, a bright Soul's AoE 3 and Heavensflame 6 in radius.
    const DONUT_SAFE = 72, ORB_R = 84, CONE_HALF = 15, LASER_HALF = 24, TOWER_R = 30, GLOW_R = 36, FLAME_R = 72;
    const IN_AT = 36, OUT_AT = 108, MAX_MELEE = 156;

    let pace = 'steps';
    try{ if(localStorage.getItem('twelfth-sc-pace') === 'live') pace = 'live'; }catch(e){}
    const clock = { t: 0, running: false, timer: 0, last: 0 };
    let st = {};
    const fb = document.getElementById('sc-feedback');
    const panel = document.getElementById('panel-superchain');

    // At the last cluster the bright souls put towers down, the two strong souls soak them
    // once their own lasers have gone off, and the Heavensflame four spread their AoEs.
    function towerJob(key){
      const d = DEBUFF[key];
      if(d.kind === 'bright') return 'drop';
      if(d.kind === 'strong') return 'soak';
      return 'spread';
    }

    function debuffPhrase(){
      return st.debuffs.map(k => DEBUFF[k].label).join(' + ');
    }

    function startRound(){
      const startIdx = Math.floor(Math.random() * 4);
      const dir = Math.random() < 0.5 ? 1 : -1;
      st.first  = CW[startIdx];
      st.second = CW[(startIdx + dir + 4) % 4];
      st.third  = CW[(startIdx + 2*dir + 4) % 4];
      st.decoy  = CW[(startIdx + 3*dir + 4) % 4];

      st.firstDist   = Math.random() < 0.5 ? 'orb' : 'donut';
      st.firstForm   = Math.random() < 0.5 ? 'orange' : 'purple';
      st.finalShort  = Math.random() < 0.5 ? 'orb' : 'donut';
      st.purpleRole  = Math.random() < 0.5 ? 'support' : 'dps';

      // Everyone's debuffs: one role holds Heavensflame and a Tilt (two of each), the other one Soul each.
      st.me = shared.slot;
      // a chosen debuff puts your role group on its side of the split: Heavensflame with a Tilt, or the Souls
      const pick = PICKS.find(p => p.id === practise);
      const coin = Math.random() < 0.5 ? 'support' : 'dps';
      const otherRole = roleOf(st.me) === 'support' ? 'dps' : 'support';
      st.flameRole = !pick.key ? coin : DEBUFF[pick.key].kind === 'tilt' ? roleOf(st.me) : otherRole;
      const tilts = shuffle(['astraltilt', 'astraltilt', 'umbraltilt', 'umbraltilt']);
      const souls = shuffle(SOUL_POOL.slice());
      if(pick.key){ const pool = DEBUFF[pick.key].kind === 'tilt' ? tilts : souls; pool.splice(pool.indexOf(pick.key), 1); }
      st.deb = {};
      SLOTS.forEach(s => {
        if(s === st.me && pick.key){ st.deb[s] = pick.key; return; }
        st.deb[s] = roleOf(s) === st.flameRole ? tilts.pop() : souls.pop();
      });
      st.key = st.deb[st.me];
      st.debuffs = roleOf(st.me) === st.flameRole ? ['heavensflame', st.key] : [st.key];

      st.a2 = (st.firstDist === 'donut' ? 'in' : 'out') + '-' + (st.firstForm === 'orange' ? 'spread' : 'pairs');
      st.a4 = GROUP[st.key];
      st.a5 = st.finalShort === 'orb' ? 'out-in' : 'in-out';
      st.a6 = towerJob(st.key);
      // A tower takes the opposite Tilt: each bright soul drops a tower of its own aspect, and each strong
      // soul holds the Tilt of its own laser, so the bright and strong souls who shared a laser group pair
      // up on that same side.
      st.a7 = GROUP[st.key];

      st.step = 1;
      stopClock();
      clearTimeout(animTimer); animTimer = 0;
      (st.fxTimers || []).forEach(clearTimeout);
      st.fxTimers = [];
      st.live = pace === 'live';
      st.fired = {}; st.over = false; st.myDrop = null;
      ['sc-fx', 'sc-beams', 'sc-towers', 'sc-under', 'sc-target', 'sc-freeHits', 'sc-players'].forEach(id => { document.getElementById(id).innerHTML = ''; });
      clock.t = LIVE.start;
      panel.classList.toggle('sc-timed', st.live);
      document.getElementById('sc-start').hidden = !st.live;
      document.getElementById('sc-start').style.visibility = '';
      document.getElementById('sc-start').parentNode.style.minHeight = '';
      // the most casts the strip ever shows at once, so it keeps that many rows throughout
      st.castSlots = Math.max(1, ...Array.from({ length: 330 }, (_, k) => liveRows(k * 0.1).length));
      st.moves = {};
      const start = startPositions();
      SLOTS.forEach(s => setAt(s, start[s]));
      render();
    }

    /* ---------- geometry ---------- */
    const unit = (a, b) => { const dx = b[0] - a[0], dy = b[1] - a[1], l = Math.hypot(dx, dy) || 1; return [dx / l, dy / l]; };
    const add = (p, v, k) => [p[0] + v[0] * k, p[1] + v[1] * k];
    const dist = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]);
    const CENTRE = [300, 300];
    // facing the boss from cluster q (looking along -out), your left hand points along left(q)
    const outOf = q => [Math.cos(CANG[q] * RAD), Math.sin(CANG[q] * RAD)];
    const leftOf = q => { const f = outOf(q); return [-f[1], f[0]]; };
    const rightOf = q => { const f = outOf(q); return [f[1], -f[0]]; };
    const CARD = { N:[0,-1], E:[1,0], S:[0,1], W:[-1,0] };
    const CARD_WORD = { N:'north', E:'east', S:'south', W:'west' };
    // The towers go on the two cardinals beside the last cluster, at max melee: Astral on the right, Umbral
    // on the left as you face the boss from it.
    function towerCard(side){
      const f = outOf(st.third), v = side === 'right' ? rightOf(st.third) : leftOf(st.third);
      return Object.keys(CARD).find(c => CARD[c][0] * f[0] + CARD[c][1] * f[1] > 0 && CARD[c][0] * v[0] + CARD[c][1] * v[1] > 0);
    }
    const towerSpot = side => add(CENTRE, CARD[towerCard(side)], MAX_MELEE);
    // Heavensflame spreads in two pairs: melee (tanks, for supports) run through Athena all the way to the
    // far side, ranged (healers) back into the corner behind the last cluster. In each pair the 1 goes right
    // and the 2 left as you face the boss from the cluster, far enough apart that the AoEs miss each other.
    const frontLine = s => 'TM'.includes(s[0]);
    const flameSide = s => s[1] === '1' ? rightOf(st.third) : leftOf(st.third);
    function flameSpot(s){
      const f = outOf(st.third);
      return frontLine(s) ? add(add(CENTRE, f, -120), flameSide(s), 44) : add(add(CPOS[st.third], f, 110), flameSide(s), 44);
    }
    const FLAME_WORD = s => `${frontLine(s) ? 'through Athena to the far side' : 'back into the corner behind the cluster'}, on the <b>${s[1] === '1' ? 'right' : 'left'}</b>`;
    const kindOf = s => DEBUFF[st.deb[s]].kind;
    const isFlame = s => roleOf(s) === st.flameRole;

    // What you hold at fight time t, as the log shows it changing: the Souls and Tilts land with
    // Engravement of Souls; a strong Soul runs out as its laser goes; the laser that hits you leaves its
    // own Tilt; a bright Soul's own AoE leaves a Tilt of its own aspect; Heavensflame runs out with its AoE;
    // soaking a tower turns your Tilt to the tower's colour.
    function myDebuffsAt(t){
      if(t < LIVE.debuffs) return [];
      const key = st.key, d = DEBUFF[key];
      const laserTilt = GROUP[key] === 'left' ? 'astraltilt' : 'umbraltilt';   // left shares Astral Impact
      const flip = k => k === 'astraltilt' ? 'umbraltilt' : 'astraltilt';
      if(isFlame(st.me)){
        const tilt = t < LIVE.laserHit ? key : laserTilt;
        return t < LIVE.flame ? ['heavensflame', tilt] : [tilt];
      }
      if(d.kind === 'strong'){
        if(t < STRONG_END) return [key];
        if(t < LIVE.laserHit) return [];
        return [t < LIVE.towerHit ? laserTilt : flip(laserTilt)];
      }
      // bright
      if(t < LIVE.laserHit) return [key];
      if(t < LIVE.drop) return [key, laserTilt];
      return [t < LIVE.glow ? laserTilt : (d.fam === 'astral' ? 'astraltilt' : 'umbraltilt')];
    }
    const heldNow = () => st.live ? myDebuffsAt(clock.t) : st.debuffs;

    /* ---------- where everyone belongs ---------- */
    // Around the first cluster everyone takes a spot relative to Athena, as for the lasers: facing her from
    // the cluster, the tanks in front, then melee, healers and ranged behind, the 1s on the right and the 2s
    // on the left. Degrees from the line towards Athena.
    const AROUND = { T:22.5, M:67.5, H:112.5, R:157.5 };
    // To pair up, each DPS stacks with the support beside it, midway between their two spots.
    const PAIR = { M1:'T1', M2:'T2', R1:'H1', R2:'H2' };
    const PAIR_AT = { T:45, M:45, H:135, R:135 };
    function aroundDir(s, deg){
      const q = st.first, toBoss = unit(CPOS[q], CENTRE), side = s[1] === '1' ? rightOf(q) : leftOf(q), a = deg * RAD;
      return [toBoss[0] * Math.cos(a) + side[0] * Math.sin(a), toBoss[1] * Math.cos(a) + side[1] * Math.sin(a)];
    }
    // dist and form default to the real ones; step by step your own marker goes where your answer says
    function spotFirst(s, dist = st.firstDist, form = st.firstForm){
      const c = CPOS[st.first], d = dist === 'donut' ? IN_AT : OUT_AT;
      if(form === 'orange') return add(c, aroundDir(s, AROUND[s[0]]), d);
      // the DPS just behind its support, so both stay inside the one cone
      return add(c, aroundDir(s, PAIR_AT[s[0]]), d + (PAIR[s] ? 14 : 0));
    }
    const SIDE_WORD = s => s[1] === '1' ? 'right' : 'left';
    const AROUND_WORD = { T:'in front, towards Athena', M:'beside it, towards the front', H:'beside it, towards the back', R:'behind it' };
    // The two laser groups stand 3 yalms either side of the donut-only cluster, each lined up along the
    // line from Athena through its strong soul: the bright soul a little nearer her, the Tilts behind.
    function spotLaser(s, side = GROUP[st.deb[s]]){
      const key = st.deb[s], c = CPOS[st.second];
      const g = add(c, side === 'left' ? leftOf(st.second) : rightOf(st.second), 36);
      const u = unit(CENTRE, g), r = dist(CENTRE, g);
      let off = 0;
      if(DEBUFF[key].kind === 'bright') off = -26;
      else if(DEBUFF[key].kind === 'tilt'){
        const mates = SLOTS.filter(x => st.deb[x] === key);
        off = mates.indexOf(s) === 0 ? 26 : 52;
      }
      return add(CENTRE, u, r + off);
    }
    // At the last cluster everyone dodges towards their next job: the tower souls towards their tower,
    // Heavensflame towards Athena. k is 0 for the shorter chain, 1 for the longer.
    function spotLast(s, k){
      const c = CPOS[st.third];
      const shape = (k === 0) === (st.finalShort === 'donut') ? 'donut' : 'orb';
      if(isFlame(s)){
        // melee dodge on Athena's side of the cluster, ranged on the corner side, each pair spread apart; with
        // the orb going off first the ranged stay on Athena's side too, rather than run past the cluster
        const u = unit(c, CENTRE), toward = frontLine(s) || (k === 0 && shape === 'orb') ? u : [-u[0], -u[1]];
        return add(add(c, toward, shape === 'donut' ? IN_AT + 8 : OUT_AT), flameSide(s), shape === 'donut' ? 18 : 24);
      }
      // Step by step the tower souls dodge in a plain spread on Athena's side, with no lean towards their
      // tower: where they stand must not answer the tower question still to come.
      if(!st.live){
        const u = unit(c, CENTRE), perp = [-u[1], u[0]];
        const i = SLOTS.filter(x => !isFlame(x)).indexOf(s);
        return add(add(c, u, shape === 'donut' ? IN_AT - 8 : OUT_AT + 22), perp, [-42, -14, 14, 42][i]);
      }
      const tw = towerSpot(towerSideOf(s));
      const u = unit(c, tw), perp = [-u[1], u[0]];
      // for the longer chain a strong soul already takes its waiting spot
      if(k === 1 && kindOf(s) === 'strong') return waitSpot(s);
      if(shape === 'donut') return add(add(c, u, 44), perp, kindOf(s) === 'bright' ? -12 : 12);
      return kindOf(s) === 'bright' ? tw : add(tw, unit(tw, CENTRE), 48);
    }
    // A strong soul waits in the middle between the two towers, just off it towards its own, out of reach of
    // its bright soul's AoE: inside the donut's gap when the donut goes off last, further in by Athena when
    // the green orb does. Once the AoE has gone it steps into its tower.
    function waitSpot(s){
      const mid = add(CENTRE, outOf(st.third), st.finalShort === 'donut' ? 40 : 110);
      return add(mid, unit(mid, towerSpot(towerSideOf(s))), 20);
    }
    // the bright soul steps back off its tower once the AoE has gone, so only the strong soul is in it
    const postSpot = tw => add(tw, unit(tw, CPOS[st.third]), 50);
    // The tower this soul drops or soaks: a strong soul holds the Tilt of its own laser and needs the
    // other colour, which is the bright soul's tower on its own side.
    const towerSideOf = s => GROUP[st.deb[s]];
    function dropOf(side){
      const holder = SLOTS.find(x => kindOf(x) === 'bright' && GROUP[st.deb[x]] === side);
      return holder === st.me && st.myDrop ? st.myDrop : towerSpot(side);
    }
    function spotTowers(s, late){
      if(isFlame(s)) return flameSpot(s);
      const side = towerSideOf(s), tw = towerSpot(side);
      if(kindOf(s) === 'bright') return late ? postSpot(dropOf(side)) : tw;
      return late ? dropOf(side) : waitSpot(s);
    }
    // before the cast: the party stacked around Athena
    function startPositions(){
      const pos = {};
      SLOTS.forEach((s, k) => { const a = k * Math.PI / 4; pos[s] = [300 + Math.cos(a) * 60, 300 + Math.sin(a) * 60]; });
      return pos;
    }

    /* ---------- the party, step by step ---------- */
    // Where everyone stands as each step opens: around Athena, then at the first cluster, gathered at the
    // laser cluster (not yet split, so the groups give nothing away), in the laser groups, at the last
    // cluster, and at the towers.
    const gatherAt = (q, s) => { const a = SLOTS.indexOf(s) * Math.PI / 4; return add(CPOS[q], [Math.cos(a), Math.sin(a)], 30); };
    function stepSpot(step, s){
      if(step <= 2) return startPositions()[s];
      if(step === 3) return spotFirst(s);
      if(step === 4) return gatherAt(st.second, s);
      if(step === 5) return spotLaser(s);
      if(step === 6) return spotLast(s, 1);
      // the tower question: Heavensflame has spread, the tower souls are still at the last cluster
      return isFlame(s) ? spotTowers(s, false) : spotLast(s, 1);
    }
    // the last cluster's spots as if the other chain were the shorter: where a wrong order leads you
    function lastSpotIf(short, s, k = 1){
      const real = st.finalShort;
      st.finalShort = short;
      const p = spotLast(s, k);
      st.finalShort = real;
      return p;
    }
    // Step by step the mechanic plays out once the party has got where it is going; none of it is replayed
    // by undo or redo, and moving on to the next step cuts it short.
    function after(ms, fn){ if(!T.isReplaying()) st.fxTimers.push(setTimeout(fn, ms)); }
    const arrivalMs = () => 150 + 1000 * Math.max(0, ...SLOTS.map(s => st.moves[s].t0 + st.moves[s].dur - sceneNow()));
    const settled = () => { const p = {}; SLOTS.forEach(s => { p[s] = st.moves[s].to; }); return p; };
    function fireLasers(pos){
      fxShape(st.second, 'donut');
      fxShape(st.decoy, 'orb');
      T.playBeams(document.getElementById('sc-beams'), SLOTS.filter(s => kindOf(s) === 'strong').map(s => ({ from: CENTRE, through: pos[s] })));
    }
    // the towers drop, the bright souls' small AoEs go off, then Heavensflame
    // Everyone to their tower spots (you to `mine`, if given), then the towers drop, Heavensflame goes off,
    // the strong souls step in and the towers resolve (you to `mineLate`).
    function playTowers(mine, mineLate){
      runOn(s => spotTowers(s, false), mine);
      after(arrivalMs(), () => towersAndFlames(() => {
        runOn(s => spotTowers(s, true), mineLate);
        after(arrivalMs(), fxTowersGo);
      }));
    }
    function towersAndFlames(then){
      // the bright souls' small AoEs ping first, then the towers appear
      fxGlow(settled(), SLOTS.filter(s => kindOf(s) === 'bright'));
      after(450, () => {
        drawTowersLive();
        after(700, () => { fxFlame(settled(), SLOTS.filter(isFlame)); if(then) after(1300, then); });
      });
    }
    // once you answer, the party runs on to where the step resolves, and you to where your answer leads
    function runOn(others, mine){
      othersTo(others);
      if(mine) moveTo(st.me, mine);
    }

    /* ---------- movement ---------- */
    const sceneNow = () => st.live ? clock.t : performance.now() / 1000;
    function posAt(s, t){
      const m = st.moves[s];
      if(t <= m.t0) return m.from;
      if(m.dur <= 0 || t >= m.t0 + m.dur) return m.to;
      const k = (t - m.t0) / m.dur;
      return [m.from[0] + (m.to[0] - m.from[0]) * k, m.from[1] + (m.to[1] - m.from[1]) * k];
    }
    function setAt(s, p){ st.moves[s] = { from:p, to:p, t0:0, dur:0 }; }
    function moveTo(s, to, delay){
      const now = sceneNow(), from = posAt(s, now);
      const t0 = now + (delay === undefined ? STEP_OFF : delay);
      st.moves[s] = { from, to, t0, dur: Math.hypot(to[0] - from[0], to[1] - from[1]) / (st.live ? SPEED : STEP_SPEED) };
      kickAnim();
    }
    function othersTo(fn, delay){ SLOTS.filter(s => s !== st.me).forEach(s => moveTo(s, fn(s), delay)); }
    let animTimer = 0;
    function kickAnim(){
      if(st.live || animTimer) return;
      const step = () => {
        drawParty();
        const t = sceneNow();
        animTimer = SLOTS.some(s => t < st.moves[s].t0 + st.moves[s].dur) ? setTimeout(step, TICK_MS) : 0;
      };
      animTimer = setTimeout(step, TICK_MS);
    }

    /* ---------- the fight clock ---------- */
    function stopClock(){ clock.running = false; if(clock.timer) clearTimeout(clock.timer); clock.timer = 0; }
    function startClock(){
      if(!st.live || clock.running || st.over) return;
      clock.running = true;
      clock.last = performance.now();
      // the button keeps its room and, when the strip sits above the arena, the header its height, so the
      // arena does not move as the clock starts
      const head = document.getElementById('sc-start').parentNode;
      if(!T.leadBeside('superchain')) head.style.minHeight = head.getBoundingClientRect().height + 'px';
      document.getElementById('sc-start').style.visibility = 'hidden';
      // once the clock runs, the ask is the first beat's rather than to press Start
      liveText();
      freePick(posAt(st.me, clock.t), livePick);
      clock.timer = setTimeout(tick, TICK_MS);
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
      if(!st.over){ drawParty(); drawClustersLive(); }
      renderLive();
    }
    function onTime(){
      const t = clock.t;
      const at = (key, time, fn) => { if(t >= time && !st.fired[key]){ st.fired[key] = true; fn(); } };
      // the rest of the party: each move a beat after there is something new to read
      at('p-first', REACT, () => othersTo(spotFirst, 0));
      at('debuffs', LIVE.debuffs, () => { renderBadges(); liveText(); });
      at('c-first', LIVE.first, checkFirst);
      at('p-laser', LIVE.first + 0.4, () => { othersTo(spotLaser, 0); liveText(); });
      at('c-second', LIVE.second, checkSecond);
      at('c-lasers', LIVE.lasers, checkLasers);
      at('p-last0', LIVE.lasers + 0.8, () => { othersTo(s => spotLast(s, 0), 0); liveText(); });
      at('c-last0', LIVE.third[0], () => checkLast(0));
      at('p-last1', LIVE.third[0] + 0.2, () => othersTo(s => spotLast(s, 1), 0));
      at('c-last1', LIVE.third[1], () => checkLast(1));
      at('p-towers', LIVE.third[1] + 0.1, () => { othersTo(s => spotTowers(s, false), 0); liveText(); });
      at('c-drop', LIVE.drop, checkDrop);
      at('c-glow', LIVE.glow, checkGlow);
      at('towersUp', LIVE.towersUp, drawTowersLive);
      at('p-soak', LIVE.glow + 0.1, () => othersTo(s => spotTowers(s, true), 0));
      at('c-flame', LIVE.flame, checkFlame);
      at('c-towers', LIVE.towers, checkTowers);
      at('end', LIVE.end, liveClear);
    }

    /* ---------- judging, on where you are ---------- */
    const here = t => posAt(st.me, t);
    const party = t => { const p = {}; SLOTS.forEach(s => { p[s] = posAt(s, t); }); return p; };
    const angleAt = (c, p) => Math.atan2(p[1] - c[1], p[0] - c[0]) / RAD;
    const angGap = (a, b) => { const d = Math.abs(a - b) % 360; return d > 180 ? 360 - d : d; };
    const inCone = (c, aim, p) => dist(c, p) > 6 && angGap(angleAt(c, aim), angleAt(c, p)) <= CONE_HALF;
    // who an Impact laser from Athena through `through` hits
    function lineHits(through, pos){
      const u = unit(CENTRE, through);
      return SLOTS.filter(s => {
        const v = [pos[s][0] - 300, pos[s][1] - 300], along = v[0] * u[0] + v[1] * u[1];
        return along > 0 && Math.abs(v[0] * u[1] - v[1] * u[0]) <= LASER_HALF;
      });
    }
    function shapeCheck(q, shape, when){
      const d = dist(here(when), CPOS[q]);
      if(shape === 'donut' && d > DONUT_SAFE) return { donut: q, title:'Outside the donut', why:`When the ${q} cluster's donut went off at <b>${when.toFixed(1)} s</b> you were ${(d / 12).toFixed(1)} yalms from it. The donut only leaves a gap of about 6 yalms around the cluster, so get in close.` };
      if(shape === 'orb' && d < ORB_R) return { orb: q, title:'Caught in the orb', why:`When the ${q} cluster's green orb went off at <b>${when.toFixed(1)} s</b> you were ${(d / 12).toFixed(1)} yalms from it. It hits everything within about 7 yalms, so get well out.` };
      return null;
    }

    function checkFirst(){
      const c = CPOS[st.first], when = LIVE.first;
      flashFirst();
      const bad = shapeCheck(st.first, st.firstDist, when);
      if(bad) return liveFail(bad.title, bad.why + ` ${firstRule()}`, bad.orb || bad.donut ? null : spotFirst(st.me), bad);
      const pos = party(when), me = pos[st.me];
      if(st.firstForm === 'orange'){
        const clash = SLOTS.find(s => s !== st.me && inCone(c, me, pos[s]));
        if(clash) return liveFail('Cones overlap', `The orange spiked ball sends a narrow cone at every player, and yours and <b>${clash}</b>'s overlapped, so you both took two. Spread to your own clock spot. ${firstRule()}`, spotFirst(st.me));
      } else {
        const targeted = SLOTS.filter(s => roleOf(s) === st.purpleRole);
        const word = st.purpleRole === 'support' ? 'supports' : 'DPS';
        if(targeted.includes(st.me)){
          const sharers = SLOTS.filter(s => s !== st.me && inCone(c, me, pos[s]));
          if(sharers.length === 0) return liveFail('Cone not shared', `The purple jack aimed its cones at the ${word}, you among them, and nobody stood in yours to split it, so you took its full damage alone, which most likely kills you. ${firstRule()}`, spotFirst(st.me));
          if(sharers.some(s => targeted.includes(s)) || sharers.length > 1) return liveFail('Cones overlap', `The purple jack aimed its cones at the ${word}, and yours caught <b>${sharers.join(' and ')}</b> as well as your partner. ${firstRule()}`, spotFirst(st.me));
        } else {
          const cones = targeted.filter(s => inCone(c, pos[s], me));
          if(cones.length === 0) return liveFail('Cone not shared', `The purple jack aimed its cones at the ${word}, and you were in none of them, so your partner <b>${partnerOf(st.me)}</b> took theirs alone, and its full damage most likely kills them. ${firstRule()}`, spotFirst(st.me));
          if(cones.length > 1) return liveFail('Two cones', `The purple jack aimed its cones at the ${word}, and you stood in <b>${cones.join(' and ')}</b>'s both. ${firstRule()}`, spotFirst(st.me));
          // a cone's damage is split among everyone in it, so sharing the wrong one leaves your partner's to them alone
          const partner = partnerOf(st.me);
          if(cones[0] !== partner) return liveFail('Cone taken alone', `The purple jack aimed its cones at the ${word}. You stood in <b>${cones[0]}</b>'s cone rather than your partner <b>${partner}</b>'s, so ${partner} took theirs alone, and its full damage most likely kills them. ${firstRule()}`, spotFirst(st.me));
        }
      }
    }
    const partnerOf = s => PAIR[s] || Object.keys(PAIR).find(k => PAIR[k] === s);
    function firstRule(){
      const dWord = st.firstDist === 'donut' ? '<b>in</b>, about 3 yalms from it' : '<b>out</b>, about 9 yalms from it';
      const fWord = st.firstForm === 'orange'
        ? `<b>spread</b> around it relative to Athena: yours is ${AROUND_WORD[st.me[0]]}, on the <b>${SIDE_WORD(st.me)}</b>`
        : `<b>paired</b>: you stack with <b>${partnerOf(st.me)}</b> midway between your two spots, on the <b>${SIDE_WORD(st.me)}</b> ${'TM'.includes(st.me[0]) ? 'towards the front' : 'towards the back'}`;
      return `The ${st.first} cluster had a ${SHAPE[st.firstDist].label.toLowerCase()} and a ${SHAPE[st.firstForm].label.toLowerCase()}: ${dWord}, ${fWord}.`;
    }

    function checkSecond(){
      fxShape(st.second, 'donut');
      fxShape(st.decoy, 'orb');
      const bad = shapeCheck(st.second, 'donut', LIVE.second) || shapeCheck(st.decoy, 'orb', LIVE.second);
      if(bad) return liveFail(bad.title, bad.why + ` ${laserRule()}`, bad.orb || bad.donut ? null : spotLaser(st.me), bad);
    }
    function checkLasers(){
      const pos = party(LIVE.lasers);
      const strongs = SLOTS.filter(s => kindOf(s) === 'strong');
      const hits = {}; strongs.forEach(s => { hits[s] = lineHits(pos[s], pos); });
      T.playBeams(document.getElementById('sc-beams'), strongs.map(s => ({ from: CENTRE, through: pos[s] })));
      const mine = SLOTS.filter(s => GROUP[st.deb[s]] === GROUP[st.key]);
      const myStrong = strongs.find(s => GROUP[st.deb[s]] === GROUP[st.key]);
      const other = strongs.find(s => s !== myStrong);
      if(hits[other].includes(st.me))
        return liveFail('Wrong laser', `When the Impact lasers fired at <b>${LIVE.lasers.toFixed(1)} s</b> you stood in <b>${DEBUFF[st.deb[other]].label.replace(' Soul', '')}</b>'s laser, which only the other family can share. ${laserRule()}`, spotLaser(st.me));
      const missing = mine.filter(s => !hits[myStrong].includes(s));
      if(missing.length) return liveFail('Laser not shared', missing.includes(st.me)
        ? `When the Impact lasers fired at <b>${LIVE.lasers.toFixed(1)} s</b> you were not on the line from Athena through <b>${myStrong}</b>, so your group took its laser one short. ${laserRule()}`
        : `When the Impact lasers fired at <b>${LIVE.lasers.toFixed(1)} s</b> your laser ran from Athena through you and missed <b>${missing.join(', ')}</b>, so it was not shared four ways. Stand where your group lines up behind you. ${laserRule()}`, spotLaser(st.me));
      const extra = hits[myStrong].filter(s => !mine.includes(s));
      if(extra.length) return liveFail('Laser through the other group', `Your laser also caught <b>${extra.join(', ')}</b> of the other family. ${laserRule()}`, spotLaser(st.me));
    }
    function laserRule(){
      const d = DEBUFF[st.key], side = GROUP[st.key];
      const who = side === 'left' ? 'Astralstrong, Umbralbright and both Umbral Tilts' : 'Umbralstrong, Astralbright and both Astral Tilts';
      return `Holding ${d.label}, you take the <b>${side}</b> group at the ${st.second} cluster as you face the boss: ${who}, lined up along the line from Athena through the strong soul.`;
    }

    function checkLast(k){
      const when = LIVE.third[k];
      const shape = (k === 0) === (st.finalShort === 'donut') ? 'donut' : 'orb';
      fxShape(st.third, shape);
      const bad = shapeCheck(st.third, shape, when);
      if(bad) return liveFail(bad.title, bad.why + ` The ${st.third} cluster's ${SHAPE[st.finalShort].label.toLowerCase()} has the shorter chain, so it is <b>${st.a5 === 'out-in' ? 'out, then in' : 'in, then out'}</b>.`, bad.orb || bad.donut ? null : spotLast(st.me, k), bad);
    }
    function towerRule(){
      const d = DEBUFF[st.key];
      if(d.kind === 'bright') return `As ${d.label} you drop an ${d.fam === 'astral' ? 'Astral' : 'Umbral'} tower on the <b>${GROUP[st.key]}</b> cardinal beside the ${st.third} cluster (${CARD_WORD[towerCard(GROUP[st.key])]}), at max melee, then step back off it once your AoE has gone.`;
      if(d.kind === 'strong') return `Your laser left you with ${d.fam === 'astral' ? 'Astral' : 'Umbral'} Tilt, so yours is ${d.fam === 'astral' ? 'Umbralbright' : 'Astralbright'}'s tower. Soak the <b>${d.fam === 'astral' ? 'Umbral' : 'Astral'}</b> tower on the <b>${GROUP[st.key]}</b> (${CARD_WORD[towerCard(GROUP[st.key])]}): wait in the middle between the two towers, just off it towards yours${st.finalShort === 'donut' ? ', further in by Athena since the green orb goes off last,' : ''} until its bright soul's AoE has gone, then step in.`;
      return `Heavensflame spreads in two pairs, clear of the towers and of each other: melee run through Athena all the way to the far side, ranged run back into the corner behind the ${st.third} cluster, the 1s on the right and the 2s on the left as you face the boss from it. Spread ${FLAME_WORD(st.me)}.`;
    }
    // The Souls run out where their carriers stand; the towers themselves only show up once the souls' small
    // AoEs have gone off, so a soaker is not drawn in too early.
    // Any drop passes that is on your side, clips nobody, and that your soaker can comfortably reach: the strong
    // soul from your laser group sets off from its waiting spot once your AoE has gone and has to be in well
    // before the towers go off. Where everyone else ends up is where the plan puts them.
    const REACH_SPARE = 0.5;
    const sideAt = p => { const r = rightOf(st.third); return (p[0] - 300) * r[0] + (p[1] - 300) * r[1] > 0 ? 'right' : 'left'; };
    function checkDrop(){
      if(kindOf(st.me) !== 'bright') return;
      const mine = GROUP[st.key], p = here(LIVE.drop), want = towerSpot(mine), when = `<b>${LIVE.drop.toFixed(1)} s</b>`;
      st.myDrop = p;
      const soaker = SLOTS.find(s => kindOf(s) === 'strong' && GROUP[st.deb[s]] === mine);
      if(sideAt(p) !== mine)
        return liveFail('Wrong side', `Your Soul ran out at ${when} on the ${sideAt(p)} of the line through Athena and the ${st.third} cluster, the other tower's side, where <b>${soaker}</b> is not going. ${towerRule()}`, want);
      const other = towerSpot(mine === 'left' ? 'right' : 'left');
      if(dist(p, other) < 2 * TOWER_R + 12)
        return liveFail('Towers overlap', `Your Soul ran out at ${when} on top of the other tower, so whoever soaks one is caught by both. ${towerRule()}`, want);
      const clipped = SLOTS.filter(s => s !== st.me && s !== soaker && dist(spotTowers(s, true), p) <= TOWER_R + 12);
      if(clipped.length)
        return liveFail('Tower on the party', `Your Soul ran out at ${when} where <b>${clipped.join(', ')}</b> will be standing when the towers go off, so your tower would catch them as well. ${towerRule()}`, want);
      const flame = SLOTS.filter(isFlame).find(s => dist(spotTowers(s, true), p) <= FLAME_R + 12);
      if(flame)
        return liveFail('Soaker in Heavensflame', `Your Soul ran out at ${when} inside the reach of <b>${flame}</b>'s Heavensflame, so <b>${soaker}</b> would be caught by it while soaking your tower. ${towerRule()}`, want);
      const from = waitSpot(soaker), arrive = LIVE.glow + 0.1 + STEP_OFF + dist(from, p) / SPEED;
      if(arrive > LIVE.towers - REACH_SPARE)
        return liveFail('Out of reach', `Your Soul ran out at ${when} ${(dist(from, p) / 12).toFixed(0)} yalms from where <b>${soaker}</b> waits for your AoE to pass. Setting off after it, they would only get there at ${arrive.toFixed(1)} s, too late for the towers at <b>${LIVE.towers.toFixed(1)} s</b>. ${towerRule()}`, want);
    }
    function checkGlow(){
      const pos = party(LIVE.glow), brights = SLOTS.filter(s => kindOf(s) === 'bright');
      fxGlow(pos, brights);
      if(kindOf(st.me) === 'bright'){
        const caught = SLOTS.filter(s => s !== st.me && dist(pos[s], pos[st.me]) <= GLOW_R);
        if(caught.length) return liveFail('Your AoE hit someone', `Your Soul's small AoE went off at <b>${LIVE.glow.toFixed(1)} s</b> on <b>${caught.join(', ')}</b> as well. ${towerRule()}`, spotTowers(st.me, false));
        return;
      }
      const by = brights.find(s => dist(pos[s], pos[st.me]) <= GLOW_R);
      if(by) liveFail('Caught in a Soul\'s AoE', `<b>${by}</b>'s ${DEBUFF[st.deb[by]].label} went off at <b>${LIVE.glow.toFixed(1)} s</b> with you inside it. ${towerRule()}`, spotTowers(st.me, false));
    }
    function checkFlame(){
      const pos = party(LIVE.flame), flames = SLOTS.filter(isFlame);
      fxFlame(pos, flames);
      if(isFlame(st.me)){
        const caught = SLOTS.filter(s => s !== st.me && dist(pos[s], pos[st.me]) <= FLAME_R);
        if(caught.length){
          liveFail('Heavensflame on the party', `Your Heavensflame went off at <b>${LIVE.flame.toFixed(1)} s</b> with <b>${caught.join(', ')}</b> inside it. ${towerRule()}`, spotTowers(st.me, false));
          return keepRings(pos, [st.me]);
        }
        return;
      }
      const by = flames.filter(s => dist(pos[s], pos[st.me]) <= FLAME_R);
      if(by.length){
        liveFail('Caught in Heavensflame', `<b>${by.join(' and ')}</b>'s Heavensflame went off at <b>${LIVE.flame.toFixed(1)} s</b> with you inside it. ${towerRule()}`, spotTowers(st.me, true));
        keepRings(pos, by);
      }
    }
    // the circles that caught someone stay up under the "your spot" mark
    function keepRings(pos, who){
      const host = document.getElementById('sc-target');
      who.forEach(s => host.insertBefore(flameRing(pos[s], ''), host.firstChild));
    }
    function checkTowers(){
      const p = here(LIVE.towers);
      const sides = ['left', 'right'], inside = sides.find(sd => dist(p, dropOf(sd)) <= TOWER_R);
      fxTowersGo();
      if(kindOf(st.me) === 'strong'){
        const mine = GROUP[st.key];
        if(inside === mine) return;
        if(inside) return liveFail('Same colour', `You stood in the ${inside} tower, the same colour as the Tilt your laser left you with, so it exploded. ${towerRule()}`, dropOf(mine));
        return liveFail('Tower not soaked', `Nobody stood in the ${mine} tower when it went off at <b>${LIVE.towers.toFixed(1)} s</b>, so it exploded. ${towerRule()}`, dropOf(mine));
      }
      if(inside) liveFail('Standing in a tower', `You were inside the ${inside} tower when it went off at <b>${LIVE.towers.toFixed(1)} s</b>. Only the strong soul soaks it. ${towerRule()}`, spotTowers(st.me, true));
    }
    // `shape`: caught by a green orb or outside a donut's gap, where the way out is plain once you see how far
    // it reaches, so it shows the edge instead of a spot: the orb's in red, the donut's safe gap in green.
    function liveFail(title, why, target, shape){
      if(st.over) return;
      st.over = true;
      stopClock();
      endFreePick();
      renderLive();
      drawClustersLive();
      const host = layer('sc-target');
      if(target) T.drawTarget(host, target, here(clock.t));
      if(shape && shape.orb) host.appendChild(el('circle', { cx:CPOS[shape.orb][0], cy:CPOS[shape.orb][1], r:ORB_R, fill:'rgba(226,82,63,0.14)',
        stroke:'var(--astral)', 'stroke-width':3, 'stroke-dasharray':'7 5', class:'stripe' }));
      if(shape && shape.donut) host.appendChild(el('circle', { cx:CPOS[shape.donut][0], cy:CPOS[shape.donut][1], r:DONUT_SAFE, fill:'rgba(111,209,154,0.14)',
        stroke:'var(--good)', 'stroke-width':3, 'stroke-dasharray':'7 5', class:'stripe' }));
      fb.dataset.noUndo = '1';
      showFeedback(fb, false, title, why, 'New pull ↻', () => newRound());
    }
    function liveClear(){
      if(st.over) return;
      st.over = true;
      stopClock();
      endFreePick();
      renderLive();
      fb.dataset.noUndo = '1';
      showFeedback(fb, true, 'Superchain cleared',
        `You were where you needed to be at every beat.<ul>`
        + `<li>First cluster at <b>${LIVE.first.toFixed(1)} s</b>: ${st.firstDist === 'donut' ? 'in' : 'out'}, ${st.firstForm === 'orange' ? 'spread' : 'paired'}</li>`
        + `<li>Impact lasers at <b>${LIVE.lasers.toFixed(1)} s</b>: shared in the ${GROUP[st.key]} group</li>`
        + `<li>Last cluster at <b>${LIVE.third[0].toFixed(1)}</b> and <b>${LIVE.third[1].toFixed(1)} s</b>: ${st.a5 === 'out-in' ? 'out, then in' : 'in, then out'}</li>`
        + `<li>${{ bright:'Tower dropped', strong:'Tower soaked', flame:'Heavensflame spread' }[isFlame(st.me) ? 'flame' : kindOf(st.me)]} by <b>${(isFlame(st.me) ? LIVE.flame : kindOf(st.me) === 'bright' ? LIVE.drop : LIVE.towers).toFixed(1)} s</b></li></ul>`,
        'New pull ↻', () => newRound());
    }

    /* ---------- the casts running ---------- */
    function liveRows(t = clock.t){
      const rows = [];
      const addRow = (from, to, who, what, mine) => { if(t >= from && t < to) rows.push({ from, to, who, what, mine }); };
      addRow(LIVE.engrave[0], LIVE.engrave[1], 'Athena', 'Engravement of Souls');
      if(t >= LIVE.debuffs && !st.over){
        const d = DEBUFF[st.key];
        if(d.kind === 'strong') addRow(LIVE.debuffs, STRONG_END, 'You', d.label, true);
        if(d.kind === 'bright') addRow(LIVE.debuffs, LIVE.drop, 'You', d.label, true);
        if(isFlame(st.me)) addRow(LIVE.debuffs, LIVE.flame, 'You', 'Heavensflame Soul', true);
      }
      addRow(LIVE.first - 0.98, LIVE.first, 'Athena', 'Superchain: first cluster');
      addRow(LIVE.second - 0.98, LIVE.second, 'Athena', 'Superchain: donut cluster');
      addRow(LIVE.third[0] - 0.98, LIVE.third[0], 'Athena', 'Superchain: last cluster, shorter chain');
      addRow(LIVE.third[1] - 0.98, LIVE.third[1], 'Athena', 'Superchain: last cluster, longer chain');
      addRow(LIVE.towers - 1.96, LIVE.towers, 'Towers', 'Astral / Umbral Advance');
      return rows;
    }
    function renderLive(){
      const box = document.getElementById('sc-live');
      box.hidden = !st.live;
      if(!st.live) return;
      document.getElementById('sc-clock').innerHTML = `${clock.t.toFixed(1)}<small>s</small>`;
      const rows = liveRows();
      document.getElementById('sc-casts').innerHTML = T.castRows('sc', rows, clock.t,
        clock.t < LIVE.engrave[0] ? 'Superchain Theory I has gone off. The chains are drifting in.' : 'Nothing casting.', st.castSlots);
      document.getElementById('sc-liveNote').innerHTML = !clock.running && !st.over && clock.t <= LIVE.start
        ? '<span class="hint">Click to move as the fight unfolds: where you stand when each part goes off is what counts.</span>'
        : '';
    }

    function renderPick(){
      const host = document.getElementById('sc-debuffPick');
      host.innerHTML = PICKS.map(p => `<button type="button" class="role-btn${p.key ? '' : ' sc-any'}" data-pick="${p.id}" aria-pressed="${p.id === practise}" title="${pickLabel(p)}" aria-label="${pickLabel(p)}">`
        + (p.key ? p.icons.map(k => `<img src="${DEBUFF[k].icon}" alt="">`).join('') : '<span>Random</span>') + '</button>').join('');
      const p = PICKS.find(x => x.id === practise);
      document.getElementById('sc-pickNote').textContent = p.key
        ? `Every pull deals you ${pickLabel(p)}.`
        : 'Each pull deals you one of the six at random.';
    }
    document.getElementById('sc-debuffPick').addEventListener('click', e => {
      const b = e.target.closest('[data-pick]');
      if(!b || b.dataset.pick === practise) return;
      practise = b.dataset.pick;
      try{ localStorage.setItem('twelfth-sc-debuff', practise); }catch(e){}
      renderPick();
      newRound();
    });
    renderPick();

    function setPace(p){
      pace = p;
      try{ localStorage.setItem('twelfth-sc-pace', p); }catch(e){}
      panel.querySelectorAll('[data-pace]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.pace === p)));
      newRound();
    }
    panel.querySelectorAll('[data-pace]').forEach(b => {
      b.setAttribute('aria-pressed', String(b.dataset.pace === pace));
      b.addEventListener('click', () => { if(b.dataset.pace !== pace) setPace(b.dataset.pace); });
    });
    document.getElementById('sc-start').addEventListener('click', startClock);

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
      document.querySelectorAll('#panel-superchain .hit').forEach(h => h.setAttribute('aria-disabled','true'));
    }
    function markPos(p){
      const m = document.getElementById('sc-playerMarker');
      m.setAttribute('transform', `translate(${p[0]-300},${p[1]-300})`);
      m.setAttribute('opacity', '1');
    }

    function clusterShapes(q){
      if(q === st.first)  return [{ s: st.firstDist, len:'short', at: LIVE.first }, { s: st.firstForm, len:'short', at: LIVE.first }];
      if(q === st.second) return [{ s:'donut', len:'short', at: LIVE.second }];
      if(q === st.third)  return [{ s:'orb',   len: st.finalShort === 'orb'   ? 'short' : 'long', at: LIVE.third[st.finalShort === 'orb' ? 0 : 1] },
                                  { s:'donut', len: st.finalShort === 'donut' ? 'short' : 'long', at: LIVE.third[st.finalShort === 'donut' ? 0 : 1] }];
      return [{ s:'orb', len:'long', at: LIVE.second }];
    }

    // Against the clock each shape drifts in along its chain and lands when it reaches the cluster;
    // `t` is the fight clock, or undefined step by step.
    function drawCluster(host, q, opts){
      opts = opts || {};
      const [cx, cy] = CPOS[q];
      const a = CANG[q];
      const shapes = clusterShapes(q);
      const live = opts.t !== undefined;
      const left = live ? shapes.filter(sh => opts.t < sh.at) : shapes;
      const g = el('g', { opacity: opts.dim || (live && !left.length) ? 0.26 : 1 });

      shapes.forEach((sh, i) => {
        if(live && opts.t >= sh.at) return;
        const fan = shapes.length > 1 ? (i === 0 ? -32 : 32) : 0;
        const ang = (a + fan) * RAD;
        // against the clock the shape lands right on the cluster's centre as it goes off, a little further
        // out for every second still to go
        const len = live ? 5.4 * (sh.at - opts.t) : (sh.len === 'short' ? 46 : 84);
        const sx = cx + Math.cos(ang) * len;
        const sy = cy + Math.sin(ang) * len;
        const meta = SHAPE[sh.s];
        g.appendChild(el('line', { x1:cx, y1:cy, x2:sx, y2:sy, stroke: meta.color,
          'stroke-width':2.5, 'stroke-dasharray':'3 4', opacity:0.85 }));
        g.appendChild(el('circle', { cx:sx, cy:sy, r:14, fill:'var(--nebula-2)',
          stroke: meta.color, 'stroke-width':2 }));
        const u = el('use', { href: meta.icon, x: sx-12, y: sy-12 });
        u.style.color = meta.color;
        g.appendChild(u);
      });

      if(opts.highlight){
        g.appendChild(el('circle', { cx, cy, r:24, fill:'none', stroke:'var(--aether)',
          'stroke-width':3, filter:'url(#glow)', class:'pulse' }));
      }
      g.appendChild(el('circle', { cx, cy, r:14, fill:'var(--void-2)',
        stroke:'var(--aether-soft)', 'stroke-width':2 }));
      g.appendChild(el('circle', { cx, cy, r:5, fill:'var(--aether-soft)' }));

      const label = el('text', { x:cx, y:cy+33, 'text-anchor':'middle',
        'font-family':'Space Mono, monospace', 'font-size':11, fill:'var(--mist-faint)' });
      label.textContent = q;
      g.appendChild(label);

      if(opts.onPick){
        const hit = el('g', {});
        hit.appendChild(el('circle', { cx, cy, r:34, class:'focus-ring', fill:'none',
          stroke:'var(--mist)', 'stroke-width':2, opacity:0 }));
        hit.appendChild(el('circle', { cx, cy, r:34, fill:'transparent' }));
        hitable(hit, opts.onPick, q, 'Cluster ' + q);
        g.appendChild(hit);
      }
      host.appendChild(g);
    }
    // Step by step each step stands at a moment of the fight, so the chains are as long as they would be
    // then, and gone once their shape has gone off. Answering reels them in to when the shapes go off.
    const STEP_T = [0, 0, 6, 12.3, 15, 19.3, 26.3, 27];
    function drawStepClusters(){
      const host = layer('sc-clusters'), t = st.chainT, step = st.step;
      if(step === 1) CW.forEach(q => drawCluster(host, q, { onPick: answer1, t }));
      else if(step === 2) CW.forEach(q => drawCluster(host, q, { dim: q !== st.first, highlight: q === st.first, t }));
      else if(step === 3){
        drawCluster(host, st.first, { dim:true, t });
        [st.second, st.third, st.decoy].forEach(q => drawCluster(host, q, { onPick: answer3, t }));
      } else if(step === 4){
        [st.first, st.third, st.decoy].forEach(q => drawCluster(host, q, { dim:true, t }));
        drawCluster(host, st.second, { highlight:true, t });
      } else {
        [st.first, st.second, st.decoy].forEach(q => drawCluster(host, q, { dim:true, t }));
        drawCluster(host, st.third, step === 7 ? { dim:true, t } : { highlight:true, t });
      }
    }
    // the chains run in to fight time `to` over `ms`, then `then`
    function playChains(to, ms, then){
      if(T.isReplaying()) return;
      const from = st.chainT, t0 = performance.now();
      const tick = () => {
        const k = Math.min(1, (performance.now() - t0) / ms);
        st.chainT = from + (to - from) * k;
        drawStepClusters();
        if(k < 1) st.fxTimers.push(setTimeout(tick, TICK_MS));
        else if(then) then();
      };
      st.fxTimers.push(setTimeout(tick, 0));
    }
    function drawClustersLive(){
      const host = layer('sc-clusters');
      CW.forEach(q => drawCluster(host, q, { t: clock.t }));
    }

    function drawAxis(q){
      const host = layer('sc-axis');
      const a = CANG[q] * RAD;
      host.appendChild(el('line', { x1:300, y1:300,
        x2: 300 + Math.cos(a)*250, y2: 300 + Math.sin(a)*250,
        stroke:'rgba(247,147,30,0.45)', 'stroke-width':2, 'stroke-dasharray':'5 7' }));
    }

    function drawGroups(onPick){
      const host = layer('sc-groups');
      const q = st.second;
      const [cx, cy] = CPOS[q];
      const a = CANG[q] * RAD;
      const fx = Math.cos(a), fy = Math.sin(a);
      // Called from the player's view, facing the boss: facing -f, the left hand is (-fy, fx)
      // in screen coordinates. The two groups stand where they always did; only the names differ.
      [['left', -fy, fx], ['right', fy, -fx]].forEach(([id, ux, uy]) => {
        const x = cx + ux*64, y = cy + uy*64;
        const g = el('g', {});
        g.appendChild(el('circle', { cx:x, cy:y, r:30, class:'focus-ring', fill:'none',
          stroke:'var(--mist)', 'stroke-width':2, opacity:0 }));
        g.appendChild(el('circle', { cx:x, cy:y, r:26, fill:'rgba(241,236,249,0.08)',
          stroke:'var(--line-strong)', 'stroke-width':1.5 }));
        const t = el('text', { x, y:y+4, 'text-anchor':'middle', 'font-family':'Archivo, sans-serif',
          'font-size':12, 'font-weight':700, fill:'var(--mist)' });
        t.textContent = id.toUpperCase();
        g.appendChild(t);
        hitable(g, onPick, id, id + ' group');
        host.appendChild(g);
      });
    }

    function drawZones(options, onPick){
      const host = layer('sc-zones');
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

    /* ---------- the party, against the clock ---------- */
    function drawPlayer(host, s, at){
      const me = s === st.me;
      const rel = !me && roleOf(s) === roleOf(st.me);
      const g = el('g', { class:'player' + (me ? ' me' : rel ? ' related' : '') });
      host.appendChild(g);
      const cx = +at[0].toFixed(1), cy = +at[1].toFixed(1);
      if(me) g.appendChild(el('circle', { cx, cy, r:17, fill:'none', stroke:'var(--mist)', 'stroke-width':2.5, class:'pulse' }));
      g.appendChild(el('circle', { cx, cy, r:12, fill:'rgba(10,9,22,0.94)', stroke: me ? 'var(--mist)' : JOB_COLOR[s[0]], 'stroke-width': me ? 2 : 1.6 }));
      const t = el('text', { x:cx, y:cy + 3.6, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':10, 'font-weight':700, fill:JOB_COLOR[s[0]] });
      t.textContent = s;
      g.appendChild(t);
      if(me){
        const you = el('text', { x:cx, y:cy + 29, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':9, 'font-weight':700, fill:'var(--mist)' });
        you.textContent = 'YOU';
        g.appendChild(you);
        // what you hold right now, in a row up and to the right of your marker
        heldNow().forEach((k, i) => {
          const x = cx + 11 + i * 19, y = cy - 36;
          g.appendChild(el('rect', { x: x - 1.5, y: y - 1.5, width:20, height:26, rx:3, fill:'var(--nebula-2)', stroke:'var(--line-strong)', 'stroke-width':1 }));
          g.appendChild(el('image', { x, y, width:17, height:23, href: DEBUFF[k].icon, preserveAspectRatio:'xMidYMid meet' }));
        });
      }
    }
    function drawParty(){
      const host = layer('sc-players');
      const t = sceneNow();
      SLOTS.slice().sort((a, b) => (a === st.me) - (b === st.me)).forEach(s => drawPlayer(host, s, posAt(s, t)));
    }

    // Against the clock a click anywhere sends you running there; you can change course at any time.
    function livePick(p){
      if(st.over) return;
      moveTo(st.me, p);
    }
    function endFreePick(){ document.getElementById('sc-freeHits').innerHTML = ''; }
    // The click layer over the whole floor: a ghost marker follows the pointer, and the arrow keys move it.
    function freePick(from, onPick){
      const host = layer('sc-freeHits');
      const g = el('g', { class:'hit free-pick', tabindex:'0', role:'button', 'data-free':'',
        'data-x': from[0].toFixed(1), 'data-y': from[1].toFixed(1),
        'aria-label':'Pick a spot on the arena to run to. Arrow keys move the marker, Enter confirms.' });
      g.appendChild(el('rect', { x:60, y:60, width:480, height:480, rx:6, class:'free-area' }));
      const ghost = el('g', { class:'free-ghost', 'pointer-events':'none', visibility:'hidden' });
      ghost.appendChild(el('circle', { cx:0, cy:0, r:15, class:'free-ring' }));
      const tag = el('text', { x:0, y:3.6, 'text-anchor':'middle', 'font-family':'Space Mono, monospace',
        'font-size':10, 'font-weight':700, fill:'var(--aether-soft)' });
      tag.textContent = st.me;
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

    /* ---------- the mechanic resolving ---------- */
    function fxAdd(node, ms){
      if(T.isReplaying()) return;
      document.getElementById('sc-fx').appendChild(node);
      st.fxTimers.push(setTimeout(() => node.remove(), ms));
    }
    function fxShape(q, shape){
      const c = CPOS[q];
      if(shape === 'orb') fxAdd(el('circle', { cx:c[0], cy:c[1], r:ORB_R, fill:'rgba(111,209,154,0.4)', class:'sc-fx-flash' }), 1200);
      else fxAdd(el('path', { d:`M60 60H540V540H60Z M${c[0] - DONUT_SAFE} ${c[1]}a${DONUT_SAFE} ${DONUT_SAFE} 0 1 0 ${2 * DONUT_SAFE} 0a${DONUT_SAFE} ${DONUT_SAFE} 0 1 0 ${-2 * DONUT_SAFE} 0Z`,
        'fill-rule':'evenodd', fill:'rgba(130,182,242,0.32)', class:'sc-fx-flash', 'clip-path':'url(#arenaClip)' }), 1200);
    }
    function wedge(c, aim, colour){
      const a = angleAt(c, aim) * RAD, h = CONE_HALF * RAD, L = 520;
      const p1 = [c[0] + Math.cos(a - h) * L, c[1] + Math.sin(a - h) * L], p2 = [c[0] + Math.cos(a + h) * L, c[1] + Math.sin(a + h) * L];
      return el('path', { d:`M${c[0]} ${c[1]}L${p1[0].toFixed(1)} ${p1[1].toFixed(1)}L${p2[0].toFixed(1)} ${p2[1].toFixed(1)}Z`, fill:colour, class:'sc-fx-flash', 'clip-path':'url(#arenaClip)' });
    }
    function flashFirst(pos = party(LIVE.first)){
      fxShape(st.first, st.firstDist);
      const c = CPOS[st.first];
      const aims = st.firstForm === 'orange' ? SLOTS : SLOTS.filter(s => roleOf(s) === st.purpleRole);
      aims.forEach(s => fxAdd(wedge(c, pos[s], st.firstForm === 'orange' ? 'rgba(242,165,60,0.4)' : 'rgba(176,131,234,0.42)'), 1200));
    }
    function drawTowersLive(){
      const host = layer('sc-towers');
      ['left', 'right'].forEach(side => {
        const [x, y] = dropOf(side), astral = side === 'right';
        const g = el('g', { class:'sc-fx-pop' });
        g.appendChild(el('circle', { cx:x, cy:y, r:TOWER_R, fill: astral ? 'rgba(226,82,63,0.22)' : 'rgba(74,143,224,0.22)', stroke: astral ? 'var(--astral)' : 'var(--umbral)', 'stroke-width':2.5, filter:'url(#glow)' }));
        g.appendChild(el('image', { x:x - 12, y:y - 16, width:24, height:32, href: astral ? 'assets/astralbright-soul.png' : 'assets/umbralbright-soul.png', preserveAspectRatio:'xMidYMid meet' }));
        host.appendChild(g);
      });
    }
    function burst(p, r, colour){
      fxAdd(el('circle', { cx:p[0], cy:p[1], r, fill:'none', stroke:colour, 'stroke-width':4, class:'sc-fx-burst', filter:'url(#glow)' }), 900);
    }
    function fxGlow(pos, brights){ brights.forEach(s => burst(pos[s], GLOW_R, DEBUFF[st.deb[s]].fam === 'astral' ? 'var(--astral-soft)' : 'var(--umbral-soft)')); }
    // Heavensflame shows its real reach: a circle around each of the four, held for a moment
    function flameRing(p, cls){
      return el('circle', { cx:p[0].toFixed(1), cy:p[1].toFixed(1), r:FLAME_R, fill:'rgba(255,203,69,0.16)', stroke:'var(--aether-soft)', 'stroke-width':2.5, class:cls, 'clip-path':'url(#arenaClip)' });
    }
    function fxFlame(pos, flames){ flames.forEach(s => fxAdd(flameRing(pos[s], 'sc-fx-aoe'), 1700)); }
    function fxTowersGo(){
      ['left', 'right'].forEach(side => burst(dropOf(side), TOWER_R + 6, side === 'right' ? 'var(--astral-soft)' : 'var(--umbral-soft)'));
      st.fxTimers.push(setTimeout(() => layer('sc-towers'), 600));
    }

    /* ---------- render ---------- */
    function pill(text){ document.getElementById('sc-stepPill').textContent = text; }
    function instr(html){ document.getElementById('sc-instrText').innerHTML = html; }

    function renderBadges(){
      const badges = document.getElementById('sc-badges');
      const shown = !st.live || clock.t >= LIVE.debuffs;
      // the card keeps what Engravement of Souls handed you, your role for the whole drill; what you hold
      // from moment to moment shows on your marker instead
      badges.innerHTML = !shown ? '<div class="badge"><span>No debuff yet</span></div>'
        : st.debuffs.map(k => {
        const d = DEBUFF[k];
        const cls = d.fam === 'astral' ? 'astral' : (d.fam === 'umbral' ? 'umbral' : 'role');
        return `<div class="badge ${cls}"><img src="${d.icon}" alt=""><span>${d.label}</span></div>`;
      }).join('');
      const roleWord = roleOf(st.me) === 'support' ? 'Supports' : 'DPS';
      document.getElementById('sc-assignText').textContent = !shown
        ? `Engravement of Souls hands them out at ${LIVE.debuffs.toFixed(1)} s.`
        : st.debuffs.length === 2
          ? `${roleWord} drew the Heavensflame group this pull, so your Tilt picks your laser side and you spread at the end.`
          : `${roleWord} drew the Soul group this pull.`;
    }

    // what to do now, against the clock: four phases, and the text before the clock starts
    const PRE_TEXT = `Athena has cast Superchain Theory I: four clusters are chained to their shapes, and the shorter the chain, the sooner it lands. The fight clock runs in real time from here. Press Start, then click to move as the fight unfolds.`;
    const phaseAt = t => t < LIVE.first ? 0 : t < LIVE.lasers ? 1 : t < LIVE.third[1] ? 2 : 3;
    function liveText(){
      const [p, h] = phaseText(phaseAt(clock.t));
      pill(p); instr(h);
    }
    function phaseText(i){
      const out = [];
      const pill = p => { out[0] = p; }, instr = h => { out[1] = h; };
      if(i === 0){
        pill('Step 1 · First cluster');
        instr(`Take your spot around the cluster that goes first, in or out.<span class="hint"> It is the one with <span class="hl">two short chains</span>. Donut: in, about 3 yalms from it. Green orb: out, about 9 yalms. Spots are relative to Athena, facing her from the cluster: tanks in front, then melee, healers and ranged behind, 1s on the right and 2s on the left. Orange: spread on them. Purple: each DPS stacks with the support beside it (M1 with T1, M2 with T2, R1 with H1, R2 with H2), midway between their spots.</span>`);
      } else if(i === 1){
        pill('Step 2 · Laser groups');
        instr(`Rotate to the next cluster and take your laser group inside it.<span class="hint"> It is 90° on, chained to <span class="hl">only a blue donut</span>. Facing the boss, left: Astralstrong, Umbralbright and both Umbral Tilts; right: Umbralstrong, Astralbright and both Astral Tilts, lined up along the line from Athena through the strong soul.</span>`);
      } else if(i === 2){
        pill('Step 3 · Last cluster');
        instr(`Rotate to the last cluster and dodge it, in or out as each shape lands.<span class="hint"> It is 90° on again, and the <span class="hl">shorter chain lands first</span>. In is within 6 yalms of it, out beyond 7. Drift towards your next job as you dodge: the tower souls towards their cardinal, Heavensflame melee towards Athena and ranged towards the corner.</span>`);
      } else {
        pill('Step 4 · Towers');
        instr(`${towerRule()}`);
      }
      return out;
    }

    function render(){
      renderBadges();
      renderLive();

      layer('sc-clusters');
      st.chainT = STEP_T[st.step];
      layer('sc-axis'); layer('sc-groups'); layer('sc-zones'); layer('sc-target');
      if(!st.live){
        // whatever was still playing from the last step stops, and the towers stand once they have dropped
        (st.fxTimers || []).forEach(clearTimeout);
        st.fxTimers = [];
        layer('sc-fx'); layer('sc-beams');
        layer('sc-towers');
      }
      document.getElementById('sc-playerMarker').setAttribute('opacity','0');
      document.getElementById('sc-playerMarker').removeAttribute('transform');
      fb.hidden = true;
      // step by step everyone stands where this step finds them
      if(!st.live) SLOTS.forEach(s => setAt(s, stepSpot(st.step, s)));
      drawParty();

      // against the clock the step text keeps the height of the tallest it will show, so the arena holds still
      T.holdPrompt('superchain', st.live ? [PRE_TEXT, ...[0, 1, 2, 3].map(i => phaseText(i)[1])] : null);
      if(st.live){
        drawClustersLive();
        if(!clock.running && clock.t <= LIVE.start){
          pill('Superchain Theory I');
          instr(PRE_TEXT);
        } else liveText();
        return;
      }

      if(st.step === 1){
        pill('Step 1 · Read the chains');
        instr(`Four clusters just spawned. Click the cluster that resolves <span class="hl">first</span><span class="hint"> — the one chained to <span class="hl">two short</span> tethers</span>.`);
        drawStepClusters();
      }
      else if(st.step === 2){
        pill('Step 2 · Call the shapes');
        instr(`Read the two shapes on the <span class="hl">${st.first}</span> cluster, which goes first, and call where the party goes.<span class="hint"> A green orb lands on the cluster, so <b>out</b>; a blue donut lands away from it, so <b>in</b>. The orange ball cones everyone, so <b>spread</b>; the purple jack cones one role, so <b>pairs</b>.</span>`);
        drawStepClusters();
        drawZones([
          { id:'in-spread',  label:'IN',  sub:'spread', icon:'#icon-spread' },
          { id:'in-pairs',   label:'IN',  sub:'pairs',  icon:'#icon-stack' },
          { id:'out-spread', label:'OUT', sub:'spread', icon:'#icon-spread' },
          { id:'out-pairs',  label:'OUT', sub:'pairs',  icon:'#icon-stack' }
        ], answer2);
      }
      else if(st.step === 3){
        pill('Step 3 · Rotate');
        instr(`That cluster is done. Click the cluster the <span class="hl">Impact lasers</span> land on.<span class="hint"> Rotate 90° to the one chained to <span class="hl">only a blue donut</span>.</span>`);
        drawStepClusters();
      }
      else if(st.step === 4){
        pill('Step 4 · Laser groups');
        instr(`The Impact lasers are about to fire. Holding <span class="hl">${DEBUFF[st.key].label}</span>, which laser group do you take?<span class="hint"> Only the <b>opposite</b> family can share a laser, so each group is named for the aspect it does not hold: a strong soul stands with the crowd named opposite to it, a bright soul with the laser it can share.</span>`);
        drawAxis(st.second);
        drawStepClusters();
        drawGroups(answer4);
      }
      else if(st.step === 5){
        pill('Step 5 · Final dodge');
        instr(`Which way do you dodge the <span class="hl">last cluster</span> as it resolves?<span class="hint"> Rotate again to it: the <span class="hl">shorter chain lands first</span>.</span>`);
        drawStepClusters();
        drawZones([
          { id:'out-in', label:'OUT → IN', sub:'green orb lands first' },
          { id:'in-out', label:'IN → OUT', sub:'donut lands first' }
        ], answer5);
      }
      else if(st.step === 6){
        pill('Step 6 · Towers');
        instr(`Holding <span class="hl">${debuffPhrase()}</span>, what is your job in the last cast of the set?<span class="hint"> The <b>bright</b> souls drop the towers, the <b>strong</b> souls soak them, and Heavensflame Soul only spreads.</span>`);
        drawStepClusters();
        drawZones([
          { id:'drop',   label:'DROP',   sub:'a tower',        icon:'#icon-hold' },
          { id:'soak',   label:'SOAK',   sub:'a tower',        icon:'#icon-stack' },
          { id:'spread', label:'SPREAD', sub:'away from all',  icon:'#icon-spread' }
        ], answer6);
      }
      else {
        const verb = st.a6 === 'drop' ? 'drop' : 'soak';
        pill('Step 7 · Which tower');
        instr(`The towers go down on the cardinals beside the last cluster at max melee. Holding <span class="hl">${DEBUFF[st.key].label}</span>, which tower do you <span class="hl">${verb}</span>?<span class="hint"> A tower takes the <b>opposite</b> Tilt: each strong soul soaks the tower of the bright soul it shared a laser group with, so everyone stays on the side they took for the laser.</span>`);
        drawStepClusters();
        drawZones([
          { id:'left',  label:'LEFT',  sub:'facing the boss' },
          { id:'right', label:'RIGHT', sub:'facing the boss' }
        ], answer7);
      }
    }

    /* ---------- answers, step by step ---------- */
    function judge(ok, title, why, next){
      if(ok){
        const last = next > 7;
        showFeedback(fb, true, title, why,
          last ? 'New pull ↻' : 'Continue → Step ' + next,
          last ? () => newRound() : () => { st.step = next; render(); });
      } else {
        showFeedback(fb, false, title, why, 'New pull ↻', () => newRound());
      }
    }

    function answer1(q){
      lock(); markPos(CPOS[q]);
      const ok = q === st.first;
      judge(ok, ok ? 'Right cluster' : 'Wrong cluster',
        ok ? `${st.first} is chained to two short tethers, so it fires first.`
           : `${q} isn't first — ${st.first} is the one with two short chains. Long chains take longer to reach the cluster.`,
        2);
    }

    function answer2(id){
      lock();
      const ok = id === st.a2;
      runOn(s => spotFirst(s), spotFirst(st.me, id.startsWith('in') ? 'donut' : 'orb', id.endsWith('spread') ? 'orange' : 'purple'));
      playChains(LIVE.first, arrivalMs(), () => flashFirst(settled()));
      const distWord = st.firstDist === 'donut' ? 'IN' : 'OUT';
      const formWord = st.firstForm === 'orange' ? 'spread' : 'pairs';
      judge(ok, ok ? 'Good call' : 'Wrong call',
        `${SHAPE[st.firstDist].label} → <b>${distWord}</b> (${st.firstDist === 'donut' ? 'the ring lands away from the cluster' : 'the point-blank lands on the cluster'}), and ${SHAPE[st.firstForm].label} → <b>${formWord}</b>.`,
        3);
    }

    function answer3(q){
      lock(); markPos(CPOS[q]);
      const ok = q === st.second;
      runOn(s => gatherAt(st.second, s), gatherAt(q, st.me));
      judge(ok, ok ? 'Rotated correctly' : 'Wrong cluster',
        ok ? `${st.second} carries a single blue donut — get in close and take the lasers there.`
           : `${st.second} is the donut-only cluster. ${st.third} has two shapes chained to it and ${st.decoy} is holding a green orb.`,
        4);
    }

    function answer4(side){
      lock();
      const d = DEBUFF[st.key];
      const ok = side === st.a4;
      runOn(s => spotLaser(s), spotLaser(st.me, side));
      playChains(LIVE.second, arrivalMs(), () => fireLasers(settled()));
      const mine = d.fam === 'astral' ? 'Astral' : 'Umbral';
      const other = d.fam === 'astral' ? 'Umbral' : 'Astral';
      const why = d.kind === 'strong'
        ? `${d.label} is the target of <b>${mine} Impact</b>, and only ${other}-family players can share it — so you stand with the ${other} crowd on the <b>${st.a4}</b>. The strong souls always sit with the group named opposite to them.`
        : `${d.label} is ${mine}-family, so you can only share <b>${other} Impact</b> — the <b>${st.a4}</b> group, alongside ${other}strong Soul.`;
      judge(ok, ok ? 'Correct side' : 'Wrong side', why, 5);
    }

    function answer5(id){
      lock();
      const ok = id === st.a5;
      // in or out for the shorter chain, it goes off, then the other way for the longer one, and it goes off;
      // you follow the order you called
      const short = id === 'out-in' ? 'orb' : 'donut';
      const shapeA = st.finalShort, shapeB = st.finalShort === 'orb' ? 'donut' : 'orb';
      if(T.isReplaying()) runOn(s => spotLast(s, 1), lastSpotIf(short, st.me, 1));
      else {
        runOn(s => spotLast(s, 0), lastSpotIf(short, st.me, 0));
        playChains(LIVE.third[0], arrivalMs(), () => {
          fxShape(st.third, shapeA);
          after(450, () => {
            runOn(s => spotLast(s, 1), lastSpotIf(short, st.me, 1));
            playChains(LIVE.third[1], arrivalMs(), () => fxShape(st.third, shapeB));
          });
        });
      }
      const firstShape = st.finalShort === 'orb' ? 'Green orb' : 'Blue donut';
      judge(ok, ok ? 'Dodged clean' : 'Caught by the first hit',
        `The ${firstShape} has the shorter chain, so it lands first — that makes it <b>${st.a5 === 'out-in' ? 'OUT then IN' : 'IN then OUT'}</b>.`,
        6);
    }

    function answer6(id){
      lock();
      const ok = id === st.a6;
      // Heavensflame's pull ends here, so the whole tower part plays out now; otherwise only Heavensflame
      // spreads, and the towers wait for your tower answer, so nothing gives it away
      if(ok && st.a6 === 'spread') playTowers(spotTowers(st.me, false), spotTowers(st.me, true));
      else othersTo(s => isFlame(s) ? spotTowers(s, false) : posAt(s, sceneNow()));
      const d = DEBUFF[st.key];
      let why;
      if(st.a6 === 'drop'){
        why = `${d.label} <b>drops</b> a tower — put it on a cardinal at max melee so your soaker can find it.`;
      } else if(st.a6 === 'soak'){
        why = `${d.label} already fired its Impact laser, so you're free to <b>soak</b> — the two strong souls take the towers the bright souls put down.`;
      } else {
        why = `Heavensflame Soul just <b>spreads</b> — you're not on tower duty at all. The strong souls soak; you get clear of everyone before your AoE lands.`;
      }
      // Only the tower jobs carry on into the side call.
      const onTowers = st.a6 === 'drop' || st.a6 === 'soak';
      judge(ok, ok ? (onTowers ? 'Right job' : 'Superchain cleared') : 'Wrong job',
        why, onTowers ? 7 : 8);
    }

    function answer7(side){
      lock();
      const d = DEBUFF[st.key];
      const ok = side === st.a7;
      // your tower drops on the side you chose, and you soak or step off it there
      if(d.kind === 'bright') st.myDrop = towerSpot(side);
      const near = add(add(CENTRE, outOf(st.third), st.finalShort === 'donut' ? 40 : 110), unit(CENTRE, towerSpot(side)), 20);
      playTowers(d.kind === 'bright' ? towerSpot(side) : near, d.kind === 'bright' ? postSpot(towerSpot(side)) : towerSpot(side));
      const mine = d.fam === 'astral' ? 'Astral' : 'Umbral';
      const other = d.fam === 'astral' ? 'Umbral' : 'Astral';
      const why = d.kind === 'bright'
        ? `${d.label} drops an <b>${mine}</b> tower, and it stays on the side it took for the laser: the <b>${st.a7}</b>. ${other}strong Soul, who shared your laser group, holds ${other} Tilt from its own laser and soaks it.`
        : `Your laser left you with <b>${mine} Tilt</b>, and a tower takes the opposite Tilt, so yours is the <b>${other}</b> tower: ${other}bright Soul's, on the <b>${st.a7}</b>. You shared a laser group with ${other}bright, so you stay on that side.`;
      judge(ok, ok ? 'Superchain cleared' : 'Wrong tower', why, 8);
    }

    const newRound = T.trackRounds('superchain', startRound);
    shared.roleListeners.push(newRound);
    newRound();
  }

  T.register({ id: 'superchain', label: 'Superchain I', phase: 'Athena', players: 'slot', markup: MARKUP, styles: STYLES, init: initSuperchain });
})(window.Twelfth);
