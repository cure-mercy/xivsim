/* Paradeigma I: four yellow adds on one half of the room fire White Flame at the nearest players in two
   waves while Trinity of Souls cleaves three times. Done without tank invulnerabilities: the light party
   on the adds' half lines up to bait the first wave, the parties swap, and the other one baits the second. */
(function(T){

  const { shared, showFeedback } = T;

  const STYLES = /* css */ `
    .p1-wing-panel{ display: flex; flex-direction: column; gap: 4px; }
    .p1-wing-svg{ width: 100%; height: auto; display: block; }
    /* one line kept even when its text is a hidden hint, so the arena below never moves */
    .p1-wing-caption{ margin: 0; font-size: 0.76rem; line-height: 1.5; min-height: 1.5em; color: var(--mist-faint); text-align: center; }
    .p1-wing-caption b{ color: var(--mist-dim); font-weight: 600; }
    .p1-slot{
      font-family: var(--font-mono); font-weight: 700; font-size: 1.3rem;
      width: 52px; height: 52px; flex-shrink: 0;
      display: flex; align-items: center; justify-content: center;
      border-radius: 14px; border: 1px solid var(--line-strong); background: rgba(241,236,249,0.05);
    }

    /* Real time: the fight clock and the casts running, above the wings */
    .p1-live{ display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; border: 1px solid var(--line);
      border-radius: 12px; background: var(--nebula); }
    .p1-live-head{ display: flex; align-items: center; gap: 12px; }
    .p1-clock{ font-family: var(--font-mono); font-weight: 700; font-size: 1.05rem; color: var(--mist);
      font-variant-numeric: tabular-nums; }
    .p1-clock small{ font-size: 0.7rem; color: var(--mist-faint); font-weight: 400; margin-left: 4px; }
    .p1-live-note{ flex: 1; font-size: 0.8rem; color: var(--mist-dim); }
    .p1-casts{ display: flex; flex-direction: column; gap: 6px; min-height: 26px; }
    .p1-cast{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 3px 10px; font-size: 0.8rem; color: var(--mist-dim); }
    .p1-cast b{ color: var(--mist); font-weight: 600; }
    .p1-left{ font-family: var(--font-mono); font-variant-numeric: tabular-nums; color: var(--mist); }
    .p1-cast-bar{ grid-column: 1 / -1; height: 5px; border-radius: 3px; background: var(--line); overflow: hidden; }
    .p1-cast-bar i{ display: block; height: 100%; background: var(--aether); transform-origin: left center; }
    .p1-idle{ font-size: 0.8rem; color: var(--mist-faint); }
    .p1-locked{ font-size: 0.8rem; color: var(--good); }
    /* the mechanic resolving: wings and adds popping in, the cleave sweeping its half, White Flame bursting
       on the players it hits; the lasers themselves use the shared add-laser animation */
    .p1-fx-pop, .p1-fx-burst{ transform-box: fill-box; transform-origin: center; }
    @media (prefers-reduced-motion: no-preference){
      .p1-fx-pop{ animation: p1-pop 0.5s cubic-bezier(0.3, 1.5, 0.6, 1) both; }
      .p1-fx-burst{ animation: p1-burst 0.75s ease-out forwards; }
      .p1-fx-flash{ animation: p1-flash 1.1s ease-out forwards; }
      .p1-fx-late{ animation: p1-fadein 0.3s ease-out both; }
      /* against the clock the thin lines only telegraph: they fade as the wide pulse sets off */
      .p1-fx-brief{ animation: p1-brief 0.75s ease-out both; }
      .p1-fx-settle{ animation: p1-fadein 0.4s ease-out 1.0s both; }
    }
    @media (prefers-reduced-motion: reduce){ .p1-fx-burst, .p1-fx-flash{ display: none; } }
    @keyframes p1-pop{ from{ transform: scale(0.2); opacity: 0; } to{ transform: scale(1); opacity: 1; } }
    @keyframes p1-burst{ from{ transform: scale(0.5); opacity: 1; } to{ transform: scale(2); opacity: 0; } }
    @keyframes p1-flash{ 0%{ opacity: 0; } 15%{ opacity: 0.9; } 100%{ opacity: 0; } }
    @keyframes p1-fadein{ from{ opacity: 0; } to{ opacity: 1; } }
    @keyframes p1-brief{ 0%{ opacity: 0; } 40%{ opacity: 1; } 67%{ opacity: 1; } 100%{ opacity: 0; } }
    /* against the clock there is no stepping back: only a new pull */
    .layout.p1-timed .history-ctrls [data-history="undo"],
    .layout.p1-timed .history-ctrls [data-history="redo"],
    .layout.p1-timed .history-ctrls [data-history="rewind"]{ display: none; }
  `;

  const MARKUP = /* html */ `
  <div class="layout" id="panel-para1" role="tabpanel" aria-labelledby="tabBtn-para1" hidden>

    <section class="arena-wrap">
      <div class="step-row">
        <span class="step-pill" id="p1-stepPill">Step 1 · First wave</span>
      </div>

      <div class="p1-live" id="p1-live" hidden>
        <div class="p1-live-head">
          <span class="p1-clock" id="p1-clock">0.0<small>s</small></span>
          <span class="p1-live-note" id="p1-liveNote"></span>
          <button type="button" class="btn" id="p1-start">Start ▶</button>
        </div>
        <div class="p1-casts" id="p1-casts"></div>
      </div>

      <div class="p1-wing-panel">
        <svg class="p1-wing-svg" id="p1-wingArt" viewBox="0 0 600 142" role="img"
             aria-label="Athena's three wing pairs, showing which side glows for each cleave"></svg>
        <p class="p1-wing-caption" id="p1-wingCaption"></p>
      </div>

      <svg class="arena-svg" id="p1-arena" viewBox="36.8 48.8 526.4 502.4" role="img" aria-label="Top-down view of the Twelfth Circle arena during the first Paradeigma">
        <rect x="60" y="60" width="480" height="480" rx="6" fill="url(#floor)" pointer-events="none"/>
        <image href="assets/arena-phase1.svg" x="60" y="60" width="480" height="480" preserveAspectRatio="none" pointer-events="none"/>
        <!-- Athena's target circle: one column width in radius, as in Paradeigma II -->
        <circle cx="300" cy="300" r="120" fill="none" stroke="rgba(247,147,30,0.45)" stroke-width="1.6" stroke-dasharray="4 6" pointer-events="none"/>
        <g id="p1-under" clip-path="url(#arenaClip)" pointer-events="none"></g>
        <g transform="translate(300,300)" fill="var(--aether)" filter="url(#glow)" pointer-events="none">
          <path d="M0 -20 L6 -6 L20 0 L6 6 L0 20 L-6 6 L-20 0 L-6 -6 Z"/>
        </g>
        <g id="p1-adds" pointer-events="none"></g>
        <g id="p1-beams" pointer-events="none"></g>
        <g id="p1-players" pointer-events="none"></g>
        <g id="p1-fx" pointer-events="none"></g>
        <g id="p1-target" pointer-events="none"></g>
        <g id="p1-hits"></g>
        <rect x="60" y="60" width="480" height="480" rx="6" fill="none" stroke="rgba(247,147,30,0.55)" stroke-width="2" filter="url(#glow)" pointer-events="none"/>
      </svg>

      <p class="arena-caption">North is up. The wings above are drawn as they sit on the map, west wings on the west.</p>

      <div class="feedback" id="p1-feedback" hidden aria-live="polite"></div>
    </section>

    <aside class="hud">
      <div class="card player-card">
        <div class="card-head">
          <h2>Pace</h2>
          <span class="info-tip">
            <button type="button" class="info-btn" aria-label="About the pace" aria-expanded="false" aria-describedby="p1-paceTip">?</button>
            <span class="info-pop" role="tooltip" id="p1-paceTip"><b>Step by step</b> pauses the fight at each step while you pick your spot. <b>Real time</b> runs the fight clock from a log: click to move, and where you stand when each cleave and wave lands is what counts.</span>
          </span>
        </div>
        <div class="role-select player-select cols-2" role="group" aria-label="Choose the pace">
          <button type="button" class="role-btn" data-pace="steps"><span>Step by step</span></button>
          <button type="button" class="role-btn" data-pace="live"><span>Real time</span></button>
        </div>
      </div>

      <div class="card">
        <h2>Your slot</h2>
        <div class="lc-row">
          <div class="p1-slot" id="p1-slot">H1</div>
          <p class="assign-text" id="p1-assignText"></p>
        </div>
      </div>

      <div class="card">
        <h2>Objective</h2>
        <p class="instr-text" id="p1-instrText"></p>
      </div>

      <details class="card">
        <summary>How the call works</summary>
        <ol>
          <li>The party splits into its two light parties: <b>light party 1</b> (T1, H1, M1, R1) and <b>light party 2</b> (T2, H2, M2, R2). Light party 1 always baits the <b>first</b> wave, light party 2 the second.</li>
          <li><b>Paradeigma</b> summons four yellow adds. They go to the <b>north or the south half</b>, onto its west and east walls, two per wall.</li>
          <li>The adds show up around Athena and fly out a pair at a time, one wall's pair about 5 seconds after the cast and the other's 5 seconds later. They fire <b>White Flame</b> in the same order, one wall at a time: both adds on the first wall out together, then both on the other. Each hits the <b>two players nearest</b> to it with heavy damage and Magic Vulnerability Up. The first wave goes off with the <b>first</b> cleave, the second wave with the <b>third</b>.</li>
          <li>Light party 1 goes to the <b>adds' half</b> and <b>lines up</b> down the middle of it to bait the first wave: ranged by the wall, then healer, then melee, and the tank next to Athena. Light party 2 <b>stacks at max melee</b> on the far side of Athena, where no add is near.</li>
          <li>After the first wave, the light parties <b>swap</b>: light party 2 takes the same line-up and baits the second wave, and light party 1 stacks at max melee on the far side.</li>
          <li>At the same time <b>Trinity of Souls</b> lights three wings, always <b>bottom to top</b> the first time, so Athena spins 180° between cleaves. The safe side is <b>opposite</b> the bottom wing, the <b>same</b> side as the middle wing, and <b>opposite</b> the top wing. Everyone takes the line-up or the stack on that side of the middle line. Lit bottom to top, the pattern never makes you switch sides twice: you switch once at most. (Only a top-to-bottom Trinity, where she doesn't spin, can.)</li>
        </ol>
      </details>

      <div class="card">
        <h2>Legend</h2>
        <div class="legend-list">
          <div class="legend-item"><svg viewBox="0 0 24 24" fill="var(--aether)" style="color:var(--aether)"><use href="#icon-add"/></svg><span><b>Yellow add</b> — White Flame at the two nearest players</span></div>
          <div class="legend-item"><svg viewBox="0 0 24 24"><path d="M20 12 L6 7 Q3 12 6 17 Z" fill="var(--aether)"/></svg><span><b>Glowing wing</b> — marks a half-room cleave</span></div>
        </div>
      </div>
    </aside>

  </div>
  `;

  function initPara1(){
    const SVGNS = 'http://www.w3.org/2000/svg';
    const SLOTS = ['T1', 'T2', 'H1', 'H2', 'M1', 'M2', 'R1', 'R2'];
    const JOB = { T:'Tank', H:'Healer', M:'Melee DPS', R:'Ranged DPS' };
    const JOB_COLOR = { T:'var(--umbral-soft)', H:'var(--good)', M:'var(--astral-soft)', R:'var(--astral-soft)' };
    const HALF_WORD = { N:'north', S:'south', W:'west', E:'east' };
    const OTHER = { N:'S', S:'N', W:'E', E:'W' };
    const ORD_WORD = ['first', 'second', 'third'];
    // Trinity of Souls lights bottom to top the first time, so she spins between cleaves:
    // the second lands opposite its wing.
    const FLIP = [false, true, false];

    // Light party 1 always baits the first wave, wherever the adds go; light party 2 the second.
    const lpOf = s => s[1] === '1' ? 1 : 2;
    // The line-up down the middle of the adds' half, as a distance from Athena towards the wall:
    // tank next to her, then melee, healer, and ranged by the wall. Each add hits the two nearest,
    // so the add nearer the wall takes ranged and healer and the one nearer the middle melee and tank.
    const LINE_AT = { T:35, M:90, H:165, R:220 };
    const ADD_AT = [185, 45];                       // outer and inner add, from Athena towards the wall
    const SIDE_OFF = 30;                            // how far off the middle line to stand, on the safe side
    const BAIT_OFF = 15;                            // the line-up hugs it: the icon 3 px clear of the line
    const STACK_AT = 95;                            // max melee on the far side of Athena
    const TOL = 28, STACK_TOL = 45;
    // One wall at a time: both adds on the first wall fire together, then both on the other.
    const LASER_AT = [0, null, 1];                  // waves go off with the first and third cleaves

    /* ---------- real time ---------- */
    // Seconds after Athena's Paradeigma cast, taken from a P12S log (FFLogs report BY6AVjCDP7ZrWRQt, pull 33).
    const LIVE = {
      start: 3.0,
      adds: 4.2,                   // the yellow adds show up on a ring around Athena
      fly: [5.0, 10.0],            // and fly out a pair at a time: the first wall's pair, then the other
      trinity: [5.6, 15.56],       // Athena casts Trinity of Souls
      glow: [6.5, 9.5, 12.5],      // the three wings light, bottom to top
      lock: [15.43, null, 20.45],  // White Flame picks its targets: the first wall, then the second
      hit: [16.3, null, 21.35],    // and lands
      cleave: [15.56, 18.19, 20.77],
      end: 22.0
    };
    // Everyone runs at 7 yalms a second (a little above the real 6), and the rest of the party reacts
    // about 2 seconds after the first wing lights, as they did in the log.
    const SPEED = 84, REACT = 2.0, STEP_OFF = 0.05, TICK_MS = 33;
    // step by step nobody is racing the clock, so everyone runs twice as fast
    const STEP_SPEED = SPEED * 2;
    // step by step the adds' flights come closer together: the first pair after a beat, the other soon after
    const STEP_FLY = [0.3, 1.5];

    let pace = 'steps';
    try{ if(localStorage.getItem('twelfth-p1-pace') === 'live') pace = 'live'; }catch(e){}
    const clock = { t: 0, running: false, timer: 0, last: 0 };
    let st = {};
    const fb = document.getElementById('p1-feedback');
    const panel = document.getElementById('panel-para1');

    function startRound(){
      st.me = shared.slot;
      st.adds = Math.random() < 0.5 ? 'N' : 'S';
      st.firstWall = Math.random() < 0.5 ? 'W' : 'E';
      // The safe sides run opposite the bottom wing, with the middle wing, opposite the top wing, and the
      // game never makes you switch sides twice when the wings light bottom to top (only top to bottom, with
      // no spin, allows it). That leaves six patterns, each equally likely.
      const SAFE = ['WWW', 'EEE', 'WEE', 'EWW', 'WWE', 'EEW'];
      const safe = SAFE[Math.floor(Math.random() * SAFE.length)];
      st.wings = [OTHER[safe[0]], safe[1], OTHER[safe[2]]];
      st.cleave = st.wings.map((w, i) => FLIP[i] ? OTHER[w] : w);
      st.step = 1;
      stopClock();
      clearTimeout(animTimer); animTimer = 0;
      (st.fxTimers || []).forEach(clearTimeout);
      st.fxTimers = [];
      st.live = pace === 'live';
      st.fired = {}; st.over = false; st.passed = []; st.lastPick = null; st.litShown = {};
      document.getElementById('p1-fx').innerHTML = '';
      document.getElementById('p1-beams').innerHTML = '';
      clock.t = LIVE.start;
      panel.classList.toggle('p1-timed', st.live);
      document.getElementById('p1-start').hidden = !st.live;
      document.getElementById('p1-start').style.visibility = '';
      document.getElementById('p1-start').parentNode.style.minHeight = '';
      // the most casts the strip ever shows at once, so it keeps that many rows throughout
      st.castSlots = Math.max(1, ...Array.from({ length: 300 }, (_, k) => liveRows(k * 0.1).length));
      st.moves = {}; st.track = [];
      const start = startPositions();
      SLOTS.forEach(s => setAt(s, start[s]));
      render();
    }

    /* ---------- where everyone belongs ---------- */
    const dirY = half => half === 'N' ? -1 : 1;
    // Which light party baits at cleave i: light party 1 first, light party 2 after the swap.
    const baitLP = i => i === 0 ? 1 : 2;
    const safeX = (i, off) => 300 + (st.cleave[i] === 'W' ? 1 : -1) * (off || SIDE_OFF);
    function spotFor(s, i){
      if(lpOf(s) === baitLP(i)) return [safeX(i, BAIT_OFF), 300 + dirY(st.adds) * LINE_AT[s[0]]];
      return [safeX(i), 300 - dirY(st.adds) * STACK_AT];
    }
    function partyAt(i){
      const pos = {};
      SLOTS.forEach(s => {
        const at = spotFor(s, i);
        if(lpOf(s) === baitLP(i)){ pos[s] = at; return; }
        // the stack: four in a small diamond
        const k = ['T', 'H', 'M', 'R'].indexOf(s[0]), a = k * Math.PI / 2 + Math.PI / 4;
        pos[s] = [at[0] + Math.cos(a) * 17, at[1] + Math.sin(a) * 17];
      });
      return pos;
    }
    // before the cast: the party stacked around Athena
    function startPositions(){
      const pos = {};
      SLOTS.forEach((s, k) => { const a = k * Math.PI / 4; pos[s] = [300 + Math.cos(a) * 60, 300 + Math.sin(a) * 60]; });
      return pos;
    }
    function addSpots(){
      const out = [];
      ['W', 'E'].forEach(w => ADD_AT.forEach((d, k) => out.push({ wall:w, k, at:[w === 'W' ? 60 : 540, 300 + dirY(st.adds) * d] })));
      return out;
    }

    /* ---------- movement ---------- */
    // On the fight clock against the clock, on the wall clock step by step.
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
      // your own runs against the clock, for the recap
      if(st.live && s === st.me) st.track.push({ at: now, t0, dur: st.moves[s].dur });
      kickAnim();
    }
    function othersTo(pos, delay){ SLOTS.filter(s => s !== st.me).forEach(s => moveTo(s, pos[s], delay)); }
    // seconds until the last runner is in place
    function arrivalWait(){
      const t = sceneNow();
      return Math.max(0, ...SLOTS.map(s => st.moves[s].t0 + st.moves[s].dur - t));
    }
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
      const head = document.getElementById('p1-start').parentNode;
      if(!T.leadBeside('para1')) head.style.minHeight = head.getBoundingClientRect().height + 'px';
      document.getElementById('p1-start').style.visibility = 'hidden';
      // once the clock runs, the ask is the first step's rather than to press Start
      pill(STEP_PILL[0]); instr(stepText(0));
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
      if(!st.over) drawParty();
      renderLive();
    }
    function onTime(){
      const t = clock.t;
      const at = (key, time, fn) => { if(t >= time && !st.fired[key]){ st.fired[key] = true; fn(); } };
      at('adds', LIVE.adds, () => {
        drawAdds();
        pill(STEP_PILL[0]);
        instr(stepText(0));
        if(!st.lastPick) freePick(posAt(st.me, t), pick);
      });
      at('fly0', LIVE.fly[0], () => drawAdds(st.firstWall));
      at('fly1', LIVE.fly[1], () => drawAdds(OTHER[st.firstWall]));
      LIVE.glow.forEach((g, i) => at('glow' + i, g, () => renderWings()));
      // the rest of the party: out to their first places once the first wing has lit, swapped after the first
      // wave, and across to the third cleave's side after the second
      at('party0', LIVE.glow[0] + REACT, () => othersTo(partyAt(0), 0));
      at('check0', LIVE.cleave[0], () => liveCheck(0));
      at('party1', LIVE.hit[0], () => othersTo(partyAt(1), 0.1));
      at('check1', LIVE.cleave[1], () => liveCheck(1));
      at('party2', LIVE.cleave[1] + 0.1, () => othersTo(partyAt(2), 0.1));
      at('check2', LIVE.cleave[2], () => liveCheck(2));
      at('end', LIVE.end, liveClear);
    }

    // At each cleave: where were you when White Flame picked its targets, and when the cleave landed?
    // The second cleave has no lasers and comes while everyone is still swapping, so only its side counts.
    function liveCheck(i){
      renderWings();
      const pLock = posAt(st.me, LIVE.lock[i] !== null ? LIVE.lock[i] : LIVE.cleave[i]);
      const pCleave = posAt(st.me, LIVE.cleave[i]);
      const verdict = judge(i, pLock, pCleave, i === 1);
      if(!verdict.ok){
        st.over = true;
        stopClock();
        lock();
        drawVerdict(i, verdict);
        fb.dataset.noUndo = '1';
        showFeedback(fb, false, verdict.title, verdict.why, 'New pull ↻', () => newRound());
        return;
      }
      st.passed[i] = clock.t;
      flashVerdict(i, verdict);
      st.step = Math.min(3, i + 2);
      if(i < 2){ pill(STEP_PILL[i + 1]); instr(stepText(i + 1)); }
    }
    function liveClear(){
      st.over = true;
      stopClock();
      lock();
      renderLive();
      fb.dataset.noUndo = '1';
      // each part counts from when White Flame picks its targets, or the cleave where there is no wave
      const due = [LIVE.lock[0], LIVE.cleave[1], LIVE.lock[2]];
      const run = i => T.recapText(T.runRecap(st.track, i ? due[i - 1] : 0, due[i]), due[i]);
      showFeedback(fb, true, 'Paradeigma cleared',
        `You were in place for both waves of White Flame and clear of all three cleaves.<ul>`
        + `<li>First wave and cleave at <b>${due[0].toFixed(1)} s</b>: ${run(0)}</li>`
        + `<li>Second cleave at <b>${due[1].toFixed(1)} s</b>: on the safe side, ${run(1)}</li>`
        + `<li>Second wave and third cleave at <b>${due[2].toFixed(1)} s</b>: ${run(2)}</li></ul>`,
        'New pull ↻', () => newRound());
    }

    // The casts running right now.
    function liveRows(t = clock.t){
      const rows = [];
      const add = (from, to, who, what) => { if(t >= from && t < to) rows.push({ from, to, who, what }); };
      add(LIVE.trinity[0], LIVE.trinity[1], 'Athena', 'Trinity of Souls');
      add(LIVE.cleave[0], LIVE.cleave[1], 'Athena', 'second cleave');
      add(LIVE.cleave[1], LIVE.cleave[2], 'Athena', 'third cleave');
      return rows;
    }
    function renderLive(){
      const box = document.getElementById('p1-live');
      box.hidden = !st.live;
      if(!st.live) return;
      document.getElementById('p1-clock').innerHTML = `${clock.t.toFixed(1)}<small>s</small>`;
      const rows = liveRows();
      document.getElementById('p1-casts').innerHTML = T.castRows('p1', rows, clock.t,
        clock.t < LIVE.adds ? 'Paradeigma has gone off. Nothing to do yet.' : 'Nothing casting.', st.castSlots);
      document.getElementById('p1-liveNote').innerHTML = !clock.running && !st.over && clock.t <= LIVE.start
        ? '<span class="hint">Click to move as the fight unfolds: where you stand when each cleave and wave lands is what counts.</span>'
        : (st.lastPick ? `<span class="p1-locked">Moving to your spot</span>` : '');
    }

    function setPace(p){
      pace = p;
      try{ localStorage.setItem('twelfth-p1-pace', p); }catch(e){}
      panel.querySelectorAll('[data-pace]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.pace === p)));
      newRound();
    }
    panel.querySelectorAll('[data-pace]').forEach(b => {
      b.setAttribute('aria-pressed', String(b.dataset.pace === pace));
      b.addEventListener('click', () => { if(b.dataset.pace !== pace) setPace(b.dataset.pace); });
    });
    document.getElementById('p1-start').addEventListener('click', startClock);

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
    function lock(){
      document.querySelectorAll('#panel-para1 .hit').forEach(h => h.setAttribute('aria-disabled', 'true'));
      document.querySelectorAll('#panel-para1 .free-ghost').forEach(g => g.remove());
    }

    // The adds show up in a square on Athena's hitbox, the same square whichever half they are headed for, so
    // nothing gives their direction away until they fly out to their wall, a pair at a time: the pair that
    // fires first leaves first. Against the clock `flying` names the wall whose pair is leaving now.
    const SQUARE = 120 / Math.SQRT2;
    // the outer add of each wall parks on the corner towards its half, the inner one on the other
    const parkedAt = a => [300 + (a.wall === 'W' ? -SQUARE : SQUARE), 300 + (a.k === 0 ? 1 : -1) * dirY(st.adds) * SQUARE];
    function drawAdds(flying){
      const host = layer('p1-adds');
      if(st.live && clock.t < LIVE.adds) return;
      addSpots().forEach(a => {
        const [x, y] = a.at, first = a.wall === st.firstWall, park = parkedAt(a);
        const g = el('g', {});
        host.appendChild(g);
        if(st.live){
          if(clock.t < LIVE.fly[first ? 0 : 1]) g.setAttribute('transform', `translate(${(park[0] - x).toFixed(1)},${(park[1] - y).toFixed(1)})`);
          else if(flying === a.wall){
            T.zoomAdd(g, a.at, null, 0, park);
            g.style.setProperty('--zo', '1');
          }
        } else if(st.step === 1){
          T.zoomAdd(g, a.at, null, STEP_FLY[first ? 0 : 1], park);
          g.style.setProperty('--zo', '1');
        }
        g.appendChild(el('circle', { cx:x, cy:y, r:15, fill:'rgba(10,9,22,0.9)', stroke:'var(--aether)', 'stroke-width':2, filter:'url(#glow)' }));
        const u = el('use', { href:'#icon-add', x:x - 12, y:y - 12 });
        u.style.color = 'var(--aether)';
        g.appendChild(u);
      });
    }
    function drawPlayer(host, s, at){
      const me = s === st.me;
      const rel = !me && lpOf(s) === lpOf(st.me);
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
      }
    }
    function drawParty(){
      const host = layer('p1-players'), t = sceneNow();
      SLOTS.slice().sort((a, b) => (a === st.me) - (b === st.me)).forEach(s => drawPlayer(host, s, posAt(s, t)));
    }
    function drawCleave(host, side){
      host.appendChild(el('rect', { x: side === 'W' ? 60 : 300, y:60, width:240, height:480,
        fill:'rgba(226,82,63,0.2)', stroke:'var(--astral)', 'stroke-width':2, 'stroke-dasharray':'7 5', class:'stripe' }));
    }
    const nearest = (at, pos) => SLOTS.slice().sort((p, q) => Math.hypot(pos[p][0] - at[0], pos[p][1] - at[1]) - Math.hypot(pos[q][0] - at[0], pos[q][1] - at[1])).slice(0, 2);
    const firing = wave => addSpots().filter(a => a.wall === (wave === 0 ? st.firstWall : OTHER[st.firstWall]));
    // who each wave of White Flame goes to: the two players nearest each firing add
    function targets(wave, pos){
      const hit = [];
      firing(wave).forEach(a => nearest(a.at, pos).forEach(s => hit.push(s)));
      return hit;
    }
    function drawLasers(host, wave, pos){
      firing(wave).forEach(a => {
        nearest(a.at, pos).forEach(s => {
          const dx = pos[s][0] - a.at[0], dy = pos[s][1] - a.at[1], len = Math.hypot(dx, dy) || 1;
          const end = [a.at[0] + dx / len * 700, a.at[1] + dy / len * 700];
          host.appendChild(el('line', { x1:a.at[0], y1:a.at[1], x2:end[0], y2:end[1], stroke:'var(--aether)', 'stroke-width':14, opacity:0.22, 'stroke-linecap':'round' }));
          host.appendChild(el('line', { x1:a.at[0], y1:a.at[1], x2:end[0], y2:end[1], stroke:'var(--aether-soft)', 'stroke-width':2, opacity:0.85 }));
        });
      });
    }

    // Athena's wing pairs, first to glow at the bottom. Step by step they all glow in the first step; against
    // the clock each lights when it does in the fight, and they go dark once she starts cleaving.
    const WING_ROW_Y = [110, 78, 46];
    const WING_ORD = ['1st', '2nd', '3rd'];
    function renderWings(){
      const cleaving = st.live ? clock.t >= LIVE.cleave[0] : st.step > 1;
      const litAt = i => !cleaving && (!st.live || clock.t >= LIVE.glow[i]);
      const host = document.getElementById('p1-wingArt');
      host.innerHTML = '';
      const title = el('text', { x:300, y:18, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':10, 'letter-spacing':'0.18em', fill:'var(--mist-faint)' });
      title.textContent = 'TRINITY OF SOULS';
      host.appendChild(title);
      WING_ROW_Y.forEach((y, i) => {
        ['W', 'E'].forEach(side => {
          const on = litAt(i) && side === st.wings[i];
          const d = side === 'W'
            ? `M288,${y} L206,${y-15} Q190,${y} 206,${y+15} Z`
            : `M312,${y} L394,${y-15} Q410,${y} 394,${y+15} Z`;
          const wing = el('path', { d, fill: on ? 'var(--aether)' : 'none', stroke: on ? 'var(--aether-soft)' : 'var(--line-strong)',
            'stroke-width': on ? 2 : 1.5, opacity: on ? 0.95 : 0.35 });
          if(on) wing.setAttribute('filter', 'url(#glow)');
          // a wing that has only just lit pops in: one at a time against the clock, all three in a row step by step
          if(on && !st.litShown[i]){
            st.litShown[i] = true;
            wing.setAttribute('class', 'p1-fx-pop');
            if(!st.live) wing.style.animationDelay = (i * 0.3) + 's';
          }
          host.appendChild(wing);
        });
        const ord = el('text', { x:62, y:y + 4, 'font-family':'Space Mono, monospace', 'font-size':11, 'font-weight':700, fill:'var(--mist-faint)' });
        ord.textContent = WING_ORD[i];
        host.appendChild(ord);
      });
      const boss = el('g', { filter:'url(#glow)' });
      boss.appendChild(el('path', { d:'M0 -20 L6 -6 L20 0 L6 6 L0 20 L-6 6 L-20 0 L-6 -6 Z', fill:'var(--aether)', transform:'translate(300,78)' }));
      host.appendChild(boss);
      [['WEST', 150], ['EAST', 450]].forEach(([txt, x]) => {
        const t = el('text', { x, y:136, 'text-anchor':'middle', 'font-family':'Space Mono, monospace', 'font-size':10, 'letter-spacing':'0.12em', fill:'var(--mist-faint)' });
        t.textContent = txt;
        host.appendChild(t);
      });
      document.getElementById('p1-wingCaption').innerHTML = cleaving
        ? 'The glow has gone out: she is cleaving now.'
        : st.live && clock.t < LIVE.glow[0] ? 'Trinity of Souls is about to light her wings.' : '<span class="hint">Wings light <b>bottom to top</b>.</span>';
    }

    // Freeform pick: click anywhere on the board. A ghost of your marker follows the pointer, and the
    // arrow keys move it for keyboard play, Enter confirms. The spot is kept on the element as data-x and
    // data-y, which is also where undo and redo read it back from.
    function freePick(from, onPick){
      const host = layer('p1-hits');
      const g = el('g', { class:'hit free-pick', tabindex:'0', role:'button', 'data-free':'',
        'data-x': from[0].toFixed(1), 'data-y': from[1].toFixed(1),
        'aria-label':'Pick a spot on the arena. Arrow keys move the marker, Enter confirms.' });
      g.appendChild(el('rect', { x:60, y:60, width:480, height:480, rx:6, class:'free-area' }));
      const ghost = el('g', { class:'free-ghost', 'pointer-events':'none', visibility:'hidden' });
      ghost.appendChild(el('circle', { cx:0, cy:0, r:15, class:'free-ring' }));
      const t = el('text', { x:0, y:3.6, 'text-anchor':'middle', 'font-family':'Space Mono, monospace',
        'font-size':10, 'font-weight':700, fill:'var(--aether-soft)' });
      t.textContent = st.me;
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
      const pickIt = p => {
        if(!st.live) ghost.remove();
        g.setAttribute('data-x', p[0].toFixed(1));
        g.setAttribute('data-y', p[1].toFixed(1));
        onPick(p);
      };
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

    /* ---------- render ---------- */
    function pill(t){ document.getElementById('p1-stepPill').textContent = t; }
    function instr(h){ document.getElementById('p1-instrText').innerHTML = h; }
    const STEP_PILL = ['Step 1 · First wave', 'Step 2 · Swap', 'Step 3 · Second wave'];
    const PRE_TEXT = `Athena has cast Paradeigma: yellow adds are about to show up and Trinity of Souls is coming. The fight clock runs in real time from here. Press Start, then click to move as the fight unfolds.`;
    function stepText(i){
      if(i === 0) return `The party is stacked on Athena. Paradeigma has summoned four yellow adds for the <span class="hl">${HALF_WORD[st.adds]}</span> walls, flying out a pair at a time, and Athena's wings are lighting. The first cleave and the first wave of lasers go off together. Click where you stand for the first cleave and wave.<span class="hint"> Light party 1 lines up down the middle of the adds' half to bait, ranged by the wall and the tank next to Athena; light party 2 stacks at max melee on the far side. The first cleave hits the side of the <b>bottom</b> wing, so stand just on the other side of the middle line.</span>`;
      if(i === 1) return `The first wave and the first cleave have gone off. The second cleave is coming, with no lasers. Click where you move to for the second cleave.<span class="hint"> The light parties swap now, ready for the second wave: light party 2 lines up on the adds' half and light party 1 stacks at max melee on the far side. The second cleave lands on the side <b>opposite</b> the middle wing, so the safe side is the same as the middle wing.</span>`;
      return `The second cleave has gone off. The third cleave and the second wave of lasers go off together. Click where you stand for the third cleave and second wave.<span class="hint"> Keep your place from the swap. The third cleave hits the side of the <b>top</b> wing, so cross the middle line if you need to.</span>`;
    }

    function renderHud(){
      const slot = document.getElementById('p1-slot');
      slot.textContent = st.me;
      slot.style.color = JOB_COLOR[st.me[0]];
      document.getElementById('p1-assignText').innerHTML = `${JOB[st.me[0]]}, light party <b>${lpOf(st.me)}</b>.<span class="hint"> Your light party baits the <b>${lpOf(st.me) === 1 ? 'first' : 'second'}</b> wave.</span>`;
    }

    function render(){
      renderHud();
      renderLive();
      layer('p1-under'); layer('p1-hits'); layer('p1-target');
      fb.hidden = true;
      drawAdds();
      renderWings();
      const i = st.step - 1;
      // step by step everyone stands where this step finds them; against the clock they keep running
      if(!st.live){
        const before = i === 0 ? startPositions() : partyAt(i - 1);
        SLOTS.forEach(s => setAt(s, before[s]));
      }
      drawParty();
      // against the clock the step text keeps the height of the tallest it will show, so the arena holds still
      T.holdPrompt('para1', st.live ? [PRE_TEXT, stepText(0), stepText(1), stepText(2)] : null);
      if(st.live && clock.t <= LIVE.start && !clock.running){
        pill('Paradeigma');
        instr(PRE_TEXT);
        return;
      }
      pill(STEP_PILL[i]);
      instr(stepText(i));
      freePick(posAt(st.me, sceneNow()), pick);
    }

    /* ---------- answers ---------- */
    function stepTo(n){
      if(n > 3) return { label:'New pull ↻', fn: () => newRound() };
      return { label:'Continue → Step ' + n, fn: () => { st.step = n; render(); } };
    }

    // A click: step by step it is your answer; against the clock it only sets you running, and you can keep
    // changing your mind until the cleave lands.
    function pick(p){
      if(st.live){
        st.lastPick = p;
        moveTo(st.me, p);
        renderLive();
        return;
      }
      lock();
      layer('p1-hits');
      const i = st.step - 1;
      const verdict = judge(i, p, p, false);
      // you run to where you clicked, or straight into your own place if that is where you meant to be
      moveTo(st.me, verdict.snap ? spotFor(st.me, i) : p);
      othersTo(partyAt(i));
      // the cleave and the lasers go off once everyone has arrived
      drawVerdict(i, verdict, T.isReplaying() ? 0 : arrivalWait());
      if(verdict.ok) showFeedback(fb, true, verdict.title, verdict.why, stepTo(st.step + 1).label, stepTo(st.step + 1).fn);
      else showFeedback(fb, false, verdict.title, verdict.why, 'New pull ↻', () => newRound());
    }

    // What happens to you at cleave i, standing at pLock when White Flame picks its targets and at pCleave
    // when the cleave lands. sideOnly: the swap is still under way, so only the cleave's side counts.
    function judge(i, pLock, pCleave, sideOnly){
      const lp = lpOf(st.me), baiting = lp === baitLP(i);
      const want = spotFor(st.me, i);
      const c = st.cleave[i], w = st.wings[i];
      const cleaved = c === 'W' ? pCleave[0] < 300 : pCleave[0] > 300;
      const onAddsHalf = (pLock[1] - 300) * dirY(st.adds) > 0;
      const close = Math.hypot(pLock[0] - want[0], pLock[1] - want[1]) <= (baiting ? TOL : STACK_TOL);
      const pos = partyAt(i);
      pos[st.me] = pLock.slice();
      const wave = LASER_AT[i];
      const hit = wave !== null ? targets(wave, pos) : [];

      const wingRule = FLIP[i]
        ? `The ${ORD_WORD[i]} wing to glow was on the <b>${HALF_WORD[w]}</b>, but she spins 180° between cleaves because the wings lit bottom to top, so this cleave lands <b>${HALF_WORD[c]}</b>.`
        : `The ${ORD_WORD[i]} wing to glow was on the <b>${HALF_WORD[w]}</b>${i === 2 ? ', and she has spun back,' : ''} so the cleave lands <b>${HALF_WORD[c]}</b>.`;
      const place = { T:'next to Athena', M:'second from Athena', H:'third from Athena', R:'last, by the wall' }[st.me[0]];
      const roleRule = baiting
        ? `Light party ${lp} ${i === 0 ? 'always baits the first wave, so it lines up' : 'has swapped onto the adds\' half and lines up'} down the middle of the adds' half to bait${i === 0 ? ' it' : ' the second wave'}. As ${JOB[st.me[0]].toLowerCase()} you stand <b>${place}</b>.`
        : `Light party ${lp} ${i === 0 ? 'baits the second wave, so for now it' : 'baited the first wave and has swapped away, so it'} stacks at <b>max melee</b> on the far side of Athena, the <b>${HALF_WORD[OTHER[st.adds]]}</b>, where no add is near.`;
      const rule = `${wingRule} ${roleRule} Stand just <b>${HALF_WORD[OTHER[c]]}</b> of the middle line.`;
      const where = st.live ? ` You were there at <b>${(LIVE.lock[i] !== null ? LIVE.lock[i] : LIVE.cleave[i]).toFixed(1)} s</b>.` : '';

      const out = { ok:false, pos, hit, cleaved, snap: baiting && close && !cleaved };
      // Against the clock what counts is what the lasers actually do: each of the four baiters takes exactly
      // one and nobody else takes any, wherever exactly they stand.
      const clean = hit.length === 4 && new Set(hit).size === 4 && hit.every(s => lpOf(s) === baitLP(i));
      if(cleaved){
        out.title = 'Cleaved';
        out.why = `${st.live ? `When the cleave landed at <b>${LIVE.cleave[i].toFixed(1)} s</b> you were` : 'That spot is'} on the <b>${HALF_WORD[c]}</b> side, where it lands. ${rule}`;
      } else if(sideOnly){
        out.ok = true;
      } else if(st.live && wave !== null && clean){
        out.ok = true;
        out.title = i === 2 ? 'Paradeigma cleared' : 'First wave baited';
      } else if(st.live && wave !== null && baiting && hit.indexOf(st.me) < 0){
        out.title = 'Lasers loose';
        out.why = `When White Flame picked its targets at <b>${LIVE.lock[i].toFixed(1)} s</b> you were not among the two players nearest either firing add, so a laser meant for you went to <b>${hit.filter(s => lpOf(s) !== baitLP(i) || hit.indexOf(s) !== hit.lastIndexOf(s))[0] || 'someone else'}</b>. ${rule}`;
      } else if(st.live && wave !== null && hit.indexOf(st.me) !== hit.lastIndexOf(st.me)){
        out.title = 'Hit twice';
        out.why = `When White Flame picked its targets at <b>${LIVE.lock[i].toFixed(1)} s</b> you were among the nearest players to both firing adds, and the second laser kills you through the first one's Magic Vulnerability Up. ${rule}`;
      } else if(!baiting && hit.indexOf(st.me) >= 0){
        out.title = 'In the lasers';
        out.why = `From there you are among the two players nearest one of the firing adds, so White Flame hits you and misses someone in the line-up.${where} ${rule}`;
      } else if(baiting && !onAddsHalf){
        out.title = wave !== null ? 'Lasers loose' : 'Not in the line-up';
        out.why = `${wave !== null ? 'Your light party is baiting, and without you in the line the lasers go to whoever is nearest instead.' : 'Your light party takes the next wave, so it has to line up on the adds\' half now.'}${where} ${rule}`;
      } else if(!baiting && onAddsHalf && !st.live){
        out.title = 'On the wrong half';
        out.why = `${wave !== null ? 'That half belongs to the light party baiting this wave.' : 'The other light party is lining up there for the next wave, and you would be in its way.'}${where} ${rule}`;
      } else if(!close && !st.live){
        out.title = baiting ? 'Wrong place in the line' : 'Not in the stack';
        out.why = `${baiting ? 'The line-up only works when everyone takes their own place: ranged by the wall, then healer, melee, and the tank next to Athena, so that each add\'s two lasers land on the two players meant for it.' : 'The stack sits together at max melee on the far side of Athena.'}${where} ${rule}`;
      } else {
        out.ok = true;
        out.title = i === 2 ? 'Paradeigma cleared' : i === 0 ? 'First wave baited' : 'Swapped';
        out.why = rule + (wave !== null
          ? ` The ${i === 0 ? 'first' : 'second'} wave fires at the two players nearest each firing add: ${baiting ? 'you and your neighbour in the line' : 'the other light party\'s line-up'}.`
          : ' No lasers go off with this cleave; the second wave comes with the third.');
      }
      return out;
    }
    // The cleave and the lasers that go with it, drawn to stay (step by step, or when a pull ends)...
    // The thin laser lines come first, then the cleave sweeps its half as White Flame's wide pulse runs
    // along each line, bursting on whoever it hits; then the cleave's shading settles in.
    const LINE_LEAD = 0.5;
    // `wait` holds it all back while the party is still running into place.
    // `flashOnly`: a cleave passed against the clock just flashes its half, with no shading left behind.
    function drawVerdict(i, verdict, wait, flashOnly){
      const under = layer('p1-under');
      const lead = LASER_AT[i] !== null ? LINE_LEAD : 0;
      // a wrong answer shows where you should have stood, once the cleave and lasers have gone off
      const target = layer('p1-target');
      if(!verdict.ok) T.drawTarget(target, spotFor(st.me, i), verdict.pos[st.me]).style.animationDelay = ((wait || 0) + lead + 0.6).toFixed(2) + 's';
      if(!flashOnly){
        const g = el('g', { class:'p1-fx-settle' });
        if(wait) g.style.animationDelay = (wait + lead + 0.5).toFixed(2) + 's';
        under.appendChild(g);
        drawCleave(g, st.cleave[i]);
      }
      if(LASER_AT[i] !== null){
        const lines = el('g', { class: st.live ? 'p1-fx-brief' : 'p1-fx-late' });
        if(wait) lines.style.animationDelay = wait.toFixed(2) + 's';
        under.appendChild(lines);
        drawLasers(lines, LASER_AT[i], verdict.pos);
      }
      if(!T.isReplaying()) st.fxTimers.push(setTimeout(() => playEffects(i, verdict), ((wait || 0) + lead) * 1000));
    }
    function fxAdd(node, ms){
      if(T.isReplaying()) return;
      document.getElementById('p1-fx').appendChild(node);
      st.fxTimers.push(setTimeout(() => node.remove(), ms));
    }
    function playEffects(i, verdict){
      if(T.isReplaying()) return;
      const c = st.cleave[i];
      fxAdd(el('rect', { x: c === 'W' ? 60 : 300, y:60, width:240, height:480, fill:'rgba(255,170,140,0.5)', class:'p1-fx-flash' }), 1200);
      if(LASER_AT[i] === null) return;
      const beams = [];
      firing(LASER_AT[i]).forEach(a => nearest(a.at, verdict.pos).forEach(s => beams.push({ from:a.at, through:verdict.pos[s], who:s })));
      T.playBeams(document.getElementById('p1-beams'), beams.map(b => ({ from:b.from, through:b.through })));
      // the hits land as the pulse reaches them
      st.fxTimers.push(setTimeout(() => beams.forEach(b =>
        fxAdd(el('circle', { cx:b.through[0], cy:b.through[1], r:16, fill:'none', stroke:'var(--aether-soft)', 'stroke-width':4, class:'p1-fx-burst', filter:'url(#glow)' }), 800)), 700));
    }
    // ...or flashed and gone again as the fight carries on.
    function flashVerdict(i, verdict){
      drawVerdict(i, verdict, 0, true);
      st.fxTimers.push(setTimeout(() => { if(!st.over || st.passed.length > i) layer('p1-under'); }, 2800));
    }

    const newRound = T.trackRounds('para1', startRound);
    shared.roleListeners.push(newRound);
    newRound();
  }

  T.register({ id: 'para1', label: 'Paradeigma I', phase: 'Athena', players: 'slot', markup: MARKUP, styles: STYLES, init: initPara1 });
})(window.Twelfth);
