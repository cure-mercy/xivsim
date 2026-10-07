/* Paradeigma II: Engravement of Souls towers and tethers, then the red-add dive. */
(function(T){

  const { shared, shuffle, showFeedback, aspectColor, aspectSoft, aspectLabel, tiltIcon, soulIcon } = T;

  const STYLES = /* css */ `
    .col-hit{ cursor: pointer; }
    .col-hit:focus{ outline: none; }
    .col-hit:focus .col-focus{ opacity: 1; }
    /* the four lanes you can move into, marked like the clickable spots of the earlier steps */
    .col-hit .lane-mark{
      fill: rgba(247,147,30,0.05); stroke: var(--aether-soft); stroke-width: 2; stroke-dasharray: 8 6;   /* 14 per repeat, one hit-march cycle */
      transition: fill 0.15s ease;
    }
    .col-hit:hover .lane-mark{ fill: rgba(247,147,30,0.16); stroke: var(--aether); }
    .col-hit[aria-disabled="true"] .lane-mark{ display: none; }
    @media (prefers-reduced-motion: no-preference){
      .col-hit:not([aria-disabled="true"]) .lane-mark{ animation: hit-march 1.4s linear infinite; }
    }

    /* Real time: the fight clock, the casts that are running and your own debuff, above the arena */
    .eg-live{ display: flex; flex-direction: column; gap: 8px; padding: 10px 12px; border: 1px solid var(--line);
      border-radius: 12px; background: var(--nebula); }
    .eg-live-head{ display: flex; align-items: center; gap: 12px; }
    .eg-clock{ font-family: var(--font-mono); font-weight: 700; font-size: 1.05rem; color: var(--mist);
      font-variant-numeric: tabular-nums; }
    .eg-clock small{ font-size: 0.7rem; color: var(--mist-faint); font-weight: 400; margin-left: 4px; }
    .eg-live-note{ flex: 1; font-size: 0.8rem; color: var(--mist-dim); }
    .eg-live-note b{ color: var(--aether-soft); }
    .eg-casts{ display: flex; flex-direction: column; gap: 6px; min-height: 58px; }
    .eg-cast{ display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 3px 10px; font-size: 0.8rem; color: var(--mist-dim); }
    .eg-cast b{ color: var(--mist); font-weight: 600; }
    .eg-cast .eg-left{ font-family: var(--font-mono); font-variant-numeric: tabular-nums; color: var(--mist); }
    .eg-cast-bar{ grid-column: 1 / -1; height: 5px; border-radius: 3px; background: var(--line); overflow: hidden; }
    .eg-cast-bar i{ display: block; height: 100%; background: var(--aether); transform-origin: left center; }
    .eg-cast.mine .eg-cast-bar i{ background: var(--brand-soft); }
    .eg-cast.mine .eg-left{ color: var(--brand-soft); }
    .eg-idle{ font-size: 0.8rem; color: var(--mist-faint); }
    .eg-locked{ font-size: 0.8rem; color: var(--good); }
    /* the arena before the debuffs land: no tethers, no aspects, nothing to click yet */
    /* players never take a click: the tower or spot under them stays reachable */
    #eg-souls, #panel-engrave [id^="tp-"]{ pointer-events: none; }
    .eg-pre #tetherLines, .eg-pre #ringHits, .eg-pre #stretchHits,
    .eg-pre [id^="tp-"] rect, .eg-pre [id$="-badge"], .eg-pre [id$="-glow"]{ visibility: hidden; }
    .eg-pre [id^="add-"] use{ color: var(--mist-dim) !important; }
    /* the tethered players only get their Tilt when their add's laser hits them: until then the tether's colour is the tell */
    .eg-untilted [id^="tp-"] rect, .eg-untilted [id^="tp-"][id$="-badge"]{ visibility: hidden; }
    .eg-noadds [id^="add-"]{ visibility: hidden; }
    .eg-pre .eg-badge{ visibility: hidden; }
    .eg-pre #eg-souls circle{ stroke: var(--line-strong); }

    /* the mechanic resolving: towers dropping in, bursts as the Souls and towers go off, the red adds' dive */
    .eg-fx-pop, .eg-fx-burst, .eg-fx-blast{ transform-box: fill-box; transform-origin: center; }
    @media (prefers-reduced-motion: no-preference){
      .eg-fx-pop{ animation: eg-pop 0.45s ease-out both; }
      .eg-fx-burst{ animation: eg-burst 0.75s ease-out forwards; }
      .eg-fx-blast{ animation: eg-blast 1.2s ease-out forwards; }
    }
    @media (prefers-reduced-motion: reduce){ .eg-fx-burst, .eg-fx-blast{ display: none; } }
    @keyframes eg-pop{ from{ transform: scale(0.3); opacity: 0; } to{ transform: scale(1); opacity: 1; } }
    @keyframes eg-burst{ from{ transform: scale(0.55); opacity: 1; } to{ transform: scale(1.8); opacity: 0; } }
    @keyframes eg-blast{ 0%{ opacity: 0; } 14%{ opacity: 0.95; } 100%{ opacity: 0; } }
    /* against the clock there is no stepping back: only a new pull */
    .layout.eg-timed .history-ctrls [data-history="undo"],
    .layout.eg-timed .history-ctrls [data-history="redo"],
    .layout.eg-timed .history-ctrls [data-history="rewind"]{ display: none; }
  `;

  const MARKUP = /* html */ `
  <div class="layout" id="panel-engrave" role="tabpanel" aria-labelledby="tabBtn-engrave">

    <section class="arena-wrap">
      <div class="step-row">
        <span class="step-pill" id="eg-stepPill">Step 1 · Place your tower</span>
      </div>

      <div class="eg-live" id="eg-live" hidden>
        <div class="eg-live-head">
          <span class="eg-clock" id="eg-clock">0.0<small>s</small></span>
          <span class="eg-live-note" id="eg-liveNote"></span>
          <button type="button" class="btn" id="eg-start">Start ▶</button>
        </div>
        <div class="eg-casts" id="eg-casts"></div>
      </div>

      <svg class="arena-svg" id="eg-arena" viewBox="0 0 600 600" role="img" aria-label="Top-down view of the Twelfth Circle arena">
        <defs>
          <!-- the adds' line AoE is untelegraphed: only a quick fade off the north edge hints at it -->
          <linearGradient id="eg-addFade" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#e2523f" stop-opacity="0.42"/>
            <stop offset="0.07" stop-color="#e2523f" stop-opacity="0.14"/>
            <stop offset="0.2" stop-color="#e2523f" stop-opacity="0"/>
          </linearGradient>
        </defs>
        <!-- floor -->
        <rect x="60" y="60" width="480" height="480" rx="6" fill="url(#floor)"/>
        <image href="assets/arena-phase1.svg" x="60" y="60" width="480" height="480" preserveAspectRatio="none" pointer-events="none"/>
        <rect x="60" y="60" width="480" height="480" rx="6" fill="none" stroke="rgba(247,147,30,0.55)" stroke-width="2" filter="url(#glow)"/>

        <!-- column dividers (visible always, faint) -->
        <g id="colDividers" stroke="var(--line)" stroke-width="1.5">
          <line x1="180" y1="60" x2="180" y2="540"/>
          <line x1="300" y1="60" x2="300" y2="540"/>
          <line x1="420" y1="60" x2="420" y2="540"/>
        </g>

        <!-- column hazard overlays (step 2 only) -->
        <g id="colHazards"></g>

        <!-- column click targets (step 2 only) -->
        <g id="colHits"></g>

        <!-- tether lines -->
        <g id="tetherLines" stroke-width="3" stroke-linecap="round" opacity="0.85">
          <line id="tl-N" x1="300" y1="95" x2="300" y2="300"/>
          <line id="tl-E" x1="505" y1="300" x2="300" y2="300"/>
          <line id="tl-S" x1="300" y1="505" x2="300" y2="300"/>
          <line id="tl-W" x1="95" y1="300" x2="300" y2="300"/>
        </g>

        <!-- the adds' lasers, shown once when the tethers resolve -->
        <g id="eg-lasers" pointer-events="none"></g>
        <!-- the rest of the mechanic resolving: towers, bursts, the dive -->
        <g id="eg-fx" pointer-events="none"></g>

        <!-- red-add markers (step 2 only) -->
        <g id="redAdds"></g>

        <!-- Athena's target circle: one column width in radius -->
        <circle cx="300" cy="300" r="120" fill="none" stroke="rgba(247,147,30,0.45)" stroke-width="1.6" stroke-dasharray="4 6"/>

        <!-- boss -->
        <g class="spin" filter="url(#glow)">
          <g transform="translate(300,300)" fill="var(--aether)">
            <path d="M0 -22 L6 -6 L22 0 L6 6 L0 22 L-6 6 L-22 0 L-6 -6 Z"/>
          </g>
        </g>
        <circle cx="300" cy="300" r="9" fill="var(--void)" stroke="var(--aether)" stroke-width="1.5"/>

        <!-- the four towers (step 2, when you are one of the tethered players) -->
        <g id="towerHits"></g>

        <!-- cardinal tether adds: a spiked-orb glyph tinted by the tether's aspect
             (each nudged along its edge; JS sets the transform per round) -->
        <g id="add-N" transform="translate(0,0)">
          <circle id="add-N-glow" cx="300" cy="36" r="22" fill="none" stroke-width="4" filter="url(#glow)" class="pulse"/>
          <circle cx="300" cy="36" r="16" fill="var(--nebula-2)" stroke="var(--line-strong)" stroke-width="1.5"/>
          <use id="add-N-icon" href="#icon-add" x="288" y="24"/>
        </g>
        <g id="add-E" transform="translate(0,0)">
          <circle id="add-E-glow" cx="564" cy="300" r="22" fill="none" stroke-width="4" filter="url(#glow)" class="pulse"/>
          <circle cx="564" cy="300" r="16" fill="var(--nebula-2)" stroke="var(--line-strong)" stroke-width="1.5"/>
          <use id="add-E-icon" href="#icon-add" x="552" y="288"/>
        </g>
        <g id="add-S" transform="translate(0,0)">
          <circle id="add-S-glow" cx="300" cy="564" r="22" fill="none" stroke-width="4" filter="url(#glow)" class="pulse"/>
          <circle cx="300" cy="564" r="16" fill="var(--nebula-2)" stroke="var(--line-strong)" stroke-width="1.5"/>
          <use id="add-S-icon" href="#icon-add" x="288" y="552"/>
        </g>
        <g id="add-W" transform="translate(0,0)">
          <circle id="add-W-glow" cx="36" cy="300" r="22" fill="none" stroke-width="4" filter="url(#glow)" class="pulse"/>
          <circle cx="36" cy="300" r="16" fill="var(--nebula-2)" stroke="var(--line-strong)" stroke-width="1.5"/>
          <use id="add-W-icon" href="#icon-add" x="24" y="288"/>
        </g>

        <!-- tethered players (opposite each add, same offset, stretched directly across).
             Role icon is flavor; the tether's colour is the real tell, and the Astral/Umbral Tilt badge
             top-right shows once their laser has hit them. -->
        <g id="tp-N" transform="translate(0,0)">
          <circle id="tp-N-glow" cx="300" cy="450" r="19" fill="none" stroke-width="3" filter="url(#glow)" class="pulse"/>
          <circle cx="300" cy="450" r="15" fill="var(--nebula-2)" stroke="var(--line-strong)" stroke-width="1.5"/>
          <use id="tp-N-icon" href="#icon-tank" x="288" y="438" width="24" height="24"/>
          <rect x="304.5" y="419.5" width="27" height="35" rx="4" fill="var(--nebula-2)" stroke="var(--line-strong)" stroke-width="1"/>
          <image id="tp-N-badge" x="306" y="421" width="24" height="32" href="assets/astral-tilt.png" preserveAspectRatio="xMidYMid meet"/>
        </g>
        <g id="tp-E" transform="translate(0,0)">
          <circle id="tp-E-glow" cx="150" cy="300" r="19" fill="none" stroke-width="3" filter="url(#glow)" class="pulse"/>
          <circle cx="150" cy="300" r="15" fill="var(--nebula-2)" stroke="var(--line-strong)" stroke-width="1.5"/>
          <use id="tp-E-icon" href="#icon-tank" x="138" y="288" width="24" height="24"/>
          <rect x="154.5" y="269.5" width="27" height="35" rx="4" fill="var(--nebula-2)" stroke="var(--line-strong)" stroke-width="1"/>
          <image id="tp-E-badge" x="156" y="271" width="24" height="32" href="assets/astral-tilt.png" preserveAspectRatio="xMidYMid meet"/>
        </g>
        <g id="tp-S" transform="translate(0,0)">
          <circle id="tp-S-glow" cx="300" cy="150" r="19" fill="none" stroke-width="3" filter="url(#glow)" class="pulse"/>
          <circle cx="300" cy="150" r="15" fill="var(--nebula-2)" stroke="var(--line-strong)" stroke-width="1.5"/>
          <use id="tp-S-icon" href="#icon-tank" x="288" y="138" width="24" height="24"/>
          <rect x="304.5" y="119.5" width="27" height="35" rx="4" fill="var(--nebula-2)" stroke="var(--line-strong)" stroke-width="1"/>
          <image id="tp-S-badge" x="306" y="121" width="24" height="32" href="assets/astral-tilt.png" preserveAspectRatio="xMidYMid meet"/>
        </g>
        <g id="tp-W" transform="translate(0,0)">
          <circle id="tp-W-glow" cx="450" cy="300" r="19" fill="none" stroke-width="3" filter="url(#glow)" class="pulse"/>
          <circle cx="450" cy="300" r="15" fill="var(--nebula-2)" stroke="var(--line-strong)" stroke-width="1.5"/>
          <use id="tp-W-icon" href="#icon-tank" x="438" y="288" width="24" height="24"/>
          <rect x="454.5" y="269.5" width="27" height="35" rx="4" fill="var(--nebula-2)" stroke="var(--line-strong)" stroke-width="1"/>
          <image id="tp-W-badge" x="456" y="271" width="24" height="32" href="assets/astral-tilt.png" preserveAspectRatio="xMidYMid meet"/>
        </g>

        <!-- the four Soul carriers; the four tethered players are the tp- groups above -->
        <g id="eg-souls"></g>

        <!-- quadrant click targets (step 1), centred in each quadrant of the floor -->
        <g id="ringHits" font-family="Archivo, sans-serif" font-size="11" font-weight="700" text-anchor="middle">
          <g class="hit" id="hit-NE" tabindex="0" role="button" aria-label="Drop tower in the northeast quadrant">
            <circle cx="420" cy="180" r="26" class="focus-ring" fill="none" stroke="var(--mist)" stroke-width="2" opacity="0"/>
            <circle cx="420" cy="180" r="22" fill="rgba(241,236,249,0.08)" stroke="var(--line-strong)" stroke-width="1.5"/>
            <text x="420" y="185" fill="var(--mist)">NE</text>
          </g>
          <g class="hit" id="hit-SE" tabindex="0" role="button" aria-label="Drop tower in the southeast quadrant">
            <circle cx="420" cy="420" r="26" class="focus-ring" fill="none" stroke="var(--mist)" stroke-width="2" opacity="0"/>
            <circle cx="420" cy="420" r="22" fill="rgba(241,236,249,0.08)" stroke="var(--line-strong)" stroke-width="1.5"/>
            <text x="420" y="425" fill="var(--mist)">SE</text>
          </g>
          <g class="hit" id="hit-SW" tabindex="0" role="button" aria-label="Drop tower in the southwest quadrant">
            <circle cx="180" cy="420" r="26" class="focus-ring" fill="none" stroke="var(--mist)" stroke-width="2" opacity="0"/>
            <circle cx="180" cy="420" r="22" fill="rgba(241,236,249,0.08)" stroke="var(--line-strong)" stroke-width="1.5"/>
            <text x="180" y="425" fill="var(--mist)">SW</text>
          </g>
          <g class="hit" id="hit-NW" tabindex="0" role="button" aria-label="Drop tower in the northwest quadrant">
            <circle cx="180" cy="180" r="26" class="focus-ring" fill="none" stroke="var(--mist)" stroke-width="2" opacity="0"/>
            <circle cx="180" cy="180" r="22" fill="rgba(241,236,249,0.08)" stroke="var(--line-strong)" stroke-width="1.5"/>
            <text x="180" y="185" fill="var(--mist)">NW</text>
          </g>
        </g>

        <!-- stretch spots (step 1, when you are one of the tethered players) -->
        <g id="stretchHits"></g>

        <!-- player marker -->
        <g id="eg-playerMarker" opacity="0">
          <circle cx="300" cy="300" r="10" fill="var(--mist)" filter="url(#glow)"/>
        </g>

        <!-- after a wrong answer: where you should have been -->
        <g id="eg-target" pointer-events="none"></g>

        <!-- against the clock: click anywhere to run there -->
        <g id="eg-freeHits"></g>
      </svg>

      <p class="arena-caption">The role icon on each tethered player is flavor; the colour of their tether is the tell for its aspect. They get the matching Astral or Umbral Tilt once their add's laser hits them.</p>

      <div class="feedback" id="eg-feedback" hidden aria-live="polite"></div>
    </section>

    <aside class="hud">
      <div class="card player-card">
        <div class="card-head">
          <h2>Pace</h2>
          <span class="info-tip">
            <button type="button" class="info-btn" aria-label="About the pace" aria-expanded="false" aria-describedby="eg-paceTip">?</button>
            <span class="info-pop" role="tooltip" id="eg-paceTip"><b>Step by step</b> pauses the fight at each step while you pick from the marked spots. <b>Real time</b> runs the fight clock from a log: click anywhere to move, and where you stand when each part resolves is what counts.</span>
          </span>
        </div>
        <div class="role-select player-select cols-2" role="group" aria-label="Choose the pace">
          <button type="button" class="role-btn" data-pace="steps"><span>Step by step</span></button>
          <button type="button" class="role-btn" data-pace="live"><span>Real time</span></button>
        </div>
      </div>

      <div class="card">
        <h2>Your assignment</h2>
        <div class="assign-row">
          <div class="badge" id="eg-debuffBadge" style="flex: 1 1 100%;"></div>
        </div>
        <p class="assign-text hint-only" id="eg-assignText"></p>
      </div>

      <div class="card">
        <h2>Objective</h2>
        <p class="instr-text" id="eg-instrText"></p>
      </div>

      <details class="card">
        <summary>How the call works</summary>
        <ol>
          <li><b>Engravement of Souls</b> marks one support and one DPS with an <span style="color:var(--astral-soft)">Astralbright</span> Soul, and one support and one DPS with an <span style="color:var(--umbral-soft)">Umbralbright</span> Soul.</li>
          <li>The four tether-adds float <b>just off the platform</b> at N/E/S/W, each carrying an Astral or Umbral tether, two of each. Four random players catch them, wherever they happen to be standing.</li>
          <li>Each one stretches <b>straight across</b> the arena, about three quarters of the way over. Because every add is offset off its edge centre, an add keeps the same side as it crosses — so it lands its player in the quadrant directly across from it, and <b>exactly one tethered player ends up in each quadrant</b>.</li>
          <li><b>Supports</b> sweep the quadrants clockwise from the NE (NE → SE → SW → NW); <b>DPS</b> sweep counter-clockwise from the NW (NW → SW → SE → NE).</li>
          <li>Stop at the first quadrant whose tethered player carries the <b>opposite</b> aspect to your own Soul. Stand at max melee on that quadrant’s intercardinal and drop your tower for them.</li>
          <li>The two sweeps run in opposite directions over the same two candidate quadrants, so the support and the DPS hunting the same colour can never land on the same player.</li>
          <li>If <b>you</b> catch a tether, stretch it straight across through Athena’s hitbox, keeping your add’s side of the centreline. When the line AoE and towers resolve together, soak the tower dropped at your feet.</li>
          <li>Towers go on the <b>intercardinals</b> at max melee, not in line with the tethers: each add fires its laser at its tethered player, and a Soul carrier caught in it dies. Every quadrant ends up with one tower in the colour <b>opposite</b> to its tether, so as a tethered player you soak the tower in your own quadrant.</li>
          <li>If you dropped a tower, <b>step out of it</b> once it lands: your Soul's AoE leaves you with Magic Vulnerability Up, and standing in a tower when it goes off kills you.</li>
          <li>Once towers resolve, two red adds fire untelegraphed line AoEs down a pair of columns — get into a clear one.</li>
        </ol>
      </details>

      <div class="card">
        <h2>Legend</h2>
        <div class="legend-list">
          <div class="legend-item"><img src="assets/astral-tilt.png" alt=""><span><b>Astral Tilt</b> — on a tethered player once their laser hits</span></div>
          <div class="legend-item"><img src="assets/umbral-tilt.png" alt=""><span><b>Umbral Tilt</b> — on a tethered player once their laser hits</span></div>
          <div class="legend-item"><img src="assets/astralbright-soul.png" alt=""><span><b>Astralbright Soul</b> — drops a tower</span></div>
          <div class="legend-item"><img src="assets/umbralbright-soul.png" alt=""><span><b>Umbralbright Soul</b> — drops a tower</span></div>
          <div class="legend-item"><svg viewBox="0 0 24 24" fill="var(--astral-soft)"><use href="#icon-add"/></svg><span><b>Tether add</b> — fires the line across the floor</span></div>
          <div class="legend-item"><svg viewBox="0 0 24 24"><use href="#icon-support"/></svg><span><b>Support</b> — role icon<span class="hint">; sweeps NE → clockwise</span></span></div>
          <div class="legend-item"><svg viewBox="0 0 24 24" fill="var(--mist)"><use href="#icon-sword"/></svg><span><b>DPS</b> — role icon<span class="hint">; sweeps NW → counter-clockwise</span></span></div>
        </div>
      </div>
    </aside>

  </div>
  `;

  function initEngrave(){
    const SVG_NS = 'http://www.w3.org/2000/svg';
    const DIRS = ['N','E','S','W'];
    const QUADS = ['NE','SE','SW','NW'];
    const OPPOSITE_ASPECT = { astral:'umbral', umbral:'astral' };
    // Tanks and healers both show the merged support icon, so the marker never suggests a job you do not play.
    const ROLE_ICON = { tank: '#icon-support', healer: '#icon-support', dps: '#icon-dps' };
    const ROLE_COLOR = { tank: 'var(--umbral-soft)', healer: 'var(--good)', dps: 'var(--astral-soft)' };
    const ADD_OFFSET = 50;
    const LEAN_SIGN = {
      cw:  { N: 1, E: 1, S: -1, W: -1 },
      ccw: { N: -1, E: -1, S: 1, W: 1 }
    };
    // Each add is pushed off its edge centre and its tethered player stands directly across the
    // arena, so the four tethered players also land one per quadrant — the opposite one.
    const PLAYER_QUADRANT = {
      cw:  { N:'SE', E:'SW', S:'NW', W:'NE' },
      ccw: { N:'SW', E:'NW', S:'NE', W:'SE' }
    };
    const SWEEP = {
      support: ['NE','SE','SW','NW'],   // clockwise from the north-east
      dps:     ['NW','SW','SE','NE']    // counter-clockwise from the north-west
    };

    let st = {
      debuff: 'astral',
      tethers: {},
      offsets: {},
      tetherRoles: {},
      scanOrder: [],
      correctDir: '',
      correctQuadrant: '',
      redCols: [],
      safeCols: [],
      step: 1
    };

    const fb = document.getElementById('eg-feedback');
    const panel = document.getElementById('panel-engrave');

    /* ---------- real time ---------- */
    // Seconds after Athena's Paradeigma cast, taken from a P12S log (FFLogs report BY6AVjCDP7ZrWRQt, pull 33).
    const LIVE = {
      start: 3.0,                  // the clock opens a little before Engravement of Souls
      engrave: [3.7, 7.7],         // Athena casts Engravement of Souls
      blueAdds: 6.4,               // the four tether adds show up off the platform
      reveal: 8.4,                 // two seconds later the red adds show up, the tethers land and the Souls go out, 9 s each
      lasers: [8.4, 17.5],         // the tether adds cast Searing Radiance / Shadowsear
      towers: 17.4,                // the Souls run out and the towers drop
      laserHit: 18.3,              // the line AoEs land, handing out the Tilts
      soak: [19.5, 21.5],          // Astral / Umbral Advance: the towers resolve
      ray: [19.5, 24.4],           // the red adds cast Ray of Light
      rayHit: 25.2                 // and it lands
    };
    let pace = 'steps';
    try{ if(localStorage.getItem('twelfth-eg-pace') === 'live') pace = 'live'; }catch(e){}
    const clock = { t: 0, running: false, raf: 0, last: 0 };

    // A plain timer rather than animation frames, about 30 times a second: smooth enough for the bars,
    // and it keeps running wherever animation frames are held back.
    const TICK_MS = 33;
    function stopClock(){
      clock.running = false;
      if(clock.raf) clearTimeout(clock.raf);
      clock.raf = 0;
    }
    function startClock(){
      if(!st.live || clock.running || st.over) return;
      clock.running = true;
      clock.last = performance.now();
      // the button keeps its room and, when the strip sits above the arena, the header its height, so the
      // arena does not move as the clock starts
      const head = document.getElementById('eg-start').parentNode;
      if(!T.leadBeside('engrave')) head.style.minHeight = head.getBoundingClientRect().height + 'px';
      document.getElementById('eg-start').style.visibility = 'hidden';
      // once the clock runs, the ask is to get ready rather than to press Start
      document.getElementById('eg-instrText').innerHTML = egText('wait');
      clock.raf = setTimeout(tick, TICK_MS);
    }
    // The clock only runs while you can see it: switching mechanic or tab pauses it.
    function tick(){
      if(!clock.running) return;
      clock.raf = setTimeout(tick, TICK_MS);
      const now = performance.now();
      const dt = Math.min(0.1, (now - clock.last) / 1000);
      clock.last = now;
      if(panel.hidden || document.hidden) return;
      clock.t += dt;
      onTime();
      if(!st.over || clock.t <= LIVE.rayHit + 3) drawParty();
      renderLive();
    }
    function onTime(){
      const t = clock.t, tethered = st.part === 'tether';
      const at = (key, time, fn) => { if(t >= time && !st.fired[key]){ st.fired[key] = true; fn(); } };
      at('blueAdds', LIVE.blueAdds, () => {
        document.getElementById('eg-arena').classList.remove('eg-noadds');
        DIRS.forEach((d, k) => {
          const offset = d === 'N' || d === 'S' ? [st.offsets[d], 0] : [0, st.offsets[d]];
          T.zoomAdd(document.getElementById('add-' + d), [ADD_POS[d][0] + offset[0], ADD_POS[d][1] + offset[1]], offset, 0);
        });
      });
      at('reveal', LIVE.reveal, () => { st.phase = 'live'; render(); others('job', REACT); });
      // everyone else: the Soul carriers head for a lane once their tower is down, the tethered players
      // step into their towers once the lasers have landed and head for a lane once they have soaked
      at('tilts', LIVE.laserHit, renderTilts);
      at('glow', LIVE.laserHit + 0.2, fxGlow);
      at('partyTowers', LIVE.laserHit + 0.2, () => { others('post', 0.3, 'tether'); others('lane', 0.3, 'soul'); });
      at('soakFx', LIVE.soak[1], fxSoak);
      at('partyLanes', LIVE.soak[1] + 0.1, () => others('lane', 0.2, 'tether'));
      // Each part resolves on where you actually are at that moment, wherever you were headed.
      if(tethered){
        at('lasers', LIVE.lasers[1], () => {
          const p = posAt(st.me, LIVE.lasers[1]);
          const where = stretchVerdict(p);
          if(where === 'across'){ st.youSpot = p; st.step = 2; render(); shootLasers(); return; }
          if(!T.runRecap(st.track, 0, LIVE.lasers[1])) return lateFail('Too slow to stretch', `The line AoE fired while you were still standing next to Athena, close to your add, and at that range it is lethal. The tethers landed at <b>${LIVE.reveal.toFixed(1)} s</b> and the laser went off at <b>${LIVE.lasers[1].toFixed(1)} s</b>: you have about <b>${(LIVE.lasers[1] - LIVE.reveal).toFixed(1)} seconds</b> to read it and run.`);
          judgeStretch({ id: where, xy: p });
        });
        at('soak', LIVE.soak[1], () => {
          const p = posAt(st.me, LIVE.soak[1]);
          const inside = towerHolding(p);
          if(inside === st.myQuad){ st.step = 3; render(); return; }
          if(inside){ drawTowers(true); return judgeTower(inside); }
          return lateFail('Tower not soaked', `Nobody stood in the tower dropped for you when it resolved at <b>${LIVE.soak[1].toFixed(1)} s</b>, so it exploded. It is the tower in your own quadrant, <b>${st.myQuad}</b>, and you have to be inside its circle. After your laser lands at ${LIVE.laserHit.toFixed(1)} s there are only about <b>${(LIVE.soak[1] - LIVE.laserHit).toFixed(1)} seconds</b> to step into it.`);
        });
      } else {
        at('towers', LIVE.towers, () => {
          // the tower drops wherever you actually are, a little short of the spot if you were still running
          const p = st.myDrop = posAt(st.me, LIVE.towers);
          const where = dropVerdict(p);
          if(where === 'ok'){ st.step = 3; render(); shootLasers(); fxTowers(); return; }
          if(!T.runRecap(st.track, 0, LIVE.towers)) return lateFail('Too slow to place your tower', `Your Soul ran out at <b>${LIVE.towers.toFixed(1)} s</b> while you were still by Athena, so your tower dropped there, away from the tethered player who needed it, and it went unsoaked. The Soul lasts <b>9 seconds</b> from the moment it lands.`);
          if(where !== 'off') return judgeStepOne(where);
          const t = towerAt(st.correctQuadrant), yalms = Math.hypot(p[0] - t[0], p[1] - t[1]) / 12;
          lateFail('Tower out of place', `Your tower dropped in the right quadrant, <b>${st.correctQuadrant}</b>, but about <b>${yalms.toFixed(0)} yalms</b> from its spot at max melee on the intercardinal, just outside Athena's target circle. There it sits in the way of the tethered player's laser or out of their reach, and it goes unsoaked. Sweep: <b>${traceExplanation()}</b>.`);
        });
        // Your Soul's AoE leaves you with Magic Vulnerability Up, so you must be out of your tower, and every
        // other one, by the time they go off.
        at('ownTower', LIVE.soak[1], () => {
          const p = posAt(st.me, LIVE.soak[1]);
          const inside = QUADS.find(q => {
            const c = (st.myDrop && q === st.correctQuadrant) ? st.myDrop : towerAt(q);
            return Math.hypot(p[0] - c[0], p[1] - c[1]) <= TOWER_R;
          });
          if(inside) lateFail('Caught in the tower', `You were still standing in ${inside === st.correctQuadrant ? 'your own tower' : `the ${inside} tower`} when the towers went off at <b>${LIVE.soak[1].toFixed(1)} s</b>. Your Soul's AoE at ${(LIVE.laserHit + 0.2).toFixed(1)} s left you with Magic Vulnerability Up, so the hit kills you. Once your tower has dropped, step out of it and leave it to the tethered player.`);
        });
      }
      // The lasers fire from each add through its tethered player and on across the platform: nobody else
      // may stand in one.
      at('caught', LIVE.lasers[1], () => {
        if(st.over) return;
        const p = posAt(st.me, LIVE.lasers[1]);
        // and your own laser, if you are tethered, must miss the other seven
        const clipped = tethered && Object.keys(st.actors).find(id => id !== st.me && inLaser(st.myDir, posAt(id, LIVE.lasers[1]), LIVE.lasers[1]));
        if(clipped){
          const a = st.actors[clipped];
          const who = a.kind === 'tether' ? `the ${DIR_NAME[a.dir]} add's tethered player` : `the ${aspectLabel(a.debuff)}bright ${a.role === 'dps' ? 'DPS' : 'support'}, standing on their tower`;
          return lateFail('Laser through a party member', `Your add's line AoE fires from the add through you and on across the platform, and when it went off at <b>${LIVE.lasers[1].toFixed(1)} s</b> ${who} was in its path. Only you may take it. Stretch straight across into your own quadrant, with the line running through Athena's hitbox, and it passes clear of everyone else.`);
        }
        const d = DIRS.find(d => !(tethered && d === st.myDir) && inLaser(d, p, LIVE.lasers[1]));
        if(!d) return;
        const holder = tethered ? 'the tethered player there' : `the ${DIR_NAME[d]} add's tethered player`;
        lateFail('Caught in a laser', `When the tether adds fired at <b>${LIVE.lasers[1].toFixed(1)} s</b> you were standing in the <b>${DIR_NAME[d]}</b> add's line AoE, which runs from the add through ${holder} and on across the platform. Only its tethered player may take it. ${tethered
          ? 'Stretch straight across into your own quadrant and nobody else\'s line runs through it.'
          : 'Drop your tower at max melee on its intercardinal, which sits between the lines, and only step off it once the lasers have landed.'}`);
      });
      at('ray', LIVE.rayHit, () => { fxRay(); resolveRay(); });
    }
    // Against the clock a click anywhere sends you running there; you can change course at any time.
    function livePick(p){
      if(st.over) return;
      moveTo(st.me, p);
      st.lockNote = 'Moving to your spot';
      renderLive();
    }
    // The click layer over the whole floor, as in Paradeigma I: a ghost marker follows the pointer, and the
    // arrow keys move it for a keyboard pick.
    function freePick(from, onPick){
      const host = document.getElementById('eg-freeHits');
      host.innerHTML = '';
      const g = svgEl('g', { class:'hit free-pick', tabindex:'0', role:'button', 'data-free':'',
        'data-x': from[0].toFixed(1), 'data-y': from[1].toFixed(1),
        'aria-label':'Pick a spot on the arena to run to. Arrow keys move the marker, Enter confirms.' });
      g.appendChild(svgEl('rect', { x:60, y:60, width:480, height:480, rx:6, class:'free-area' }));
      const ghost = svgEl('g', { class:'free-ghost', 'pointer-events':'none', visibility:'hidden' });
      ghost.appendChild(svgEl('circle', { cx:0, cy:0, r:15, class:'free-ring' }));
      const tag = svgEl('text', { x:0, y:3.4, 'text-anchor':'middle', 'font-family':'Space Mono, monospace',
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
    // once the pull is over, nothing to click and no marker following the pointer
    function endFreePick(){ document.getElementById('eg-freeHits').innerHTML = ''; }
    // Where a tethered player stands, as a stretch: across (right), short of far enough, still on the add's
    // half, or over the add's centreline into the diagonal quadrant.
    function stretchVerdict(p){
      const d = st.myDir, v = d === 'N' || d === 'S', off = st.offsets[d];
      const add = [ADD_POS[d][0] + (v ? off : 0), ADD_POS[d][1] + (v ? 0 : off)];
      const across = v ? [TP_BASE[d][0] + off, TP_BASE[d][1]] : [TP_BASE[d][0], TP_BASE[d][1] + off];
      if(quadOf(p) === st.myQuad){
        const need = Math.hypot(across[0] - add[0], across[1] - add[1]) - IN_RANGE.stretch;
        return Math.hypot(p[0] - add[0], p[1] - add[1]) >= need ? 'across' : 'short';
      }
      const past = v ? (p[1] - 300) * (d === 'N' ? 1 : -1) > 0 : (p[0] - 300) * (d === 'W' ? 1 : -1) > 0;
      return past ? 'diagonal' : 'near';
    }
    // Where a Soul carrier's tower drops: on its spot ('ok'), off it in the right quadrant ('off'), or the
    // other quadrant it landed in.
    function dropVerdict(p){
      const q = quadOf(p);
      if(q !== st.correctQuadrant) return q;
      const t = towerAt(q);
      return Math.hypot(p[0] - t[0], p[1] - t[1]) <= IN_RANGE.drop ? 'ok' : 'off';
    }
    // Each add's line AoE: from the add through its tethered player (where they stand at time t) and on to
    // the edge. You are in it if your centre is within its half-width plus a little of your own hitbox.
    const LASER_HALF = 28;
    function inLaser(d, p, t){
      const v = d === 'N' || d === 'S', off = st.offsets[d];
      const a = [ADD_POS[d][0] + (v ? off : 0), ADD_POS[d][1] + (v ? 0 : off)];
      const id = Object.keys(st.actors).find(k => st.actors[k].kind === 'tether' && st.actors[k].dir === d);
      const b = posAt(id, t), len = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
      const ux = (b[0] - a[0]) / len, uy = (b[1] - a[1]) / len;
      const along = (p[0] - a[0]) * ux + (p[1] - a[1]) * uy;
      return along > 0 && Math.abs((p[0] - a[0]) * uy - (p[1] - a[1]) * ux) <= LASER_HALF;
    }
    const towerCentre = q => (st.myDrop && q === st.correctQuadrant) ? st.myDrop : towerAt(q);
    const towerHolding = p => QUADS.find(q => { const c = towerCentre(q); return Math.hypot(p[0] - c[0], p[1] - c[1]) <= TOWER_R; });

    // Where you should have been: the right spot for the part you failed, marked from where you were.
    const youAt = () => st.live ? posAt(st.me, sceneNow()) : st.actors[st.me].move.to;
    const acrossSpot = () => stretchSpots().find(s => s.id === 'across').xy;
    function showTarget(at){
      const host = document.getElementById('eg-target');
      host.innerHTML = '';
      T.drawTarget(host, at, youAt());
    }
    // against the clock, which spot each late failure was about
    function lateTarget(title){
      const tethered = st.part === 'tether';
      if(/not soaked/i.test(title)) return towerCentre(st.myQuad);
      if(/place your tower|out of place/i.test(title)) return towerAt(st.correctQuadrant);
      if(/caught in the tower/i.test(title)) return laneSpot(asideSpot(st.correctQuadrant));
      if(/caught in a laser/i.test(title)) return tethered ? acrossSpot() : towerAt(st.correctQuadrant);
      return acrossSpot();
    }

    function lateFail(title, body){
      st.over = true;
      stopClock();
      renderLive();
      document.querySelectorAll('#panel-engrave .hit').forEach(h => h.setAttribute('aria-disabled', 'true'));
      endFreePick();
      showTarget(lateTarget(title));
      fb.dataset.noUndo = '1';
      showFeedback(fb, false, title, body, 'New pull ↻', () => newRound());
    }
    // Wrong answers against the clock end the pull straight away, without an undo.
    function liveFeedback(){
      if(!st.live) return;
      st.over = true; stopClock(); renderLive(); fb.dataset.noUndo = '1';
      endFreePick();
    }

    // The casts running right now, your own debuff among them.
    function liveRows(t = clock.t){
      const tethered = st.part === 'tether', rows = [];
      const add = (from, to, who, what, mine) => { if(t >= from && t < to) rows.push({ from, to, who, what, mine }); };
      add(LIVE.engrave[0], LIVE.engrave[1], 'Athena', 'Engravement of Souls');
      if(!tethered) add(LIVE.reveal, LIVE.towers, 'You', `${aspectLabel(st.debuff)}bright Soul`, true);
      add(LIVE.lasers[0], LIVE.lasers[1], 'Tether adds', tethered ? `${st.myAspect === 'astral' ? 'Shadowsear' : 'Searing Radiance'} on you` : 'Searing Radiance / Shadowsear', tethered);
      add(LIVE.soak[0], LIVE.soak[1], 'Towers', 'Astral / Umbral Advance');
      add(LIVE.ray[0], LIVE.ray[1], 'Red adds', 'Ray of Light');
      return rows;
    }
    function renderLive(){
      const box = document.getElementById('eg-live');
      box.hidden = !st.live;
      if(!st.live) return;
      document.getElementById('eg-clock').innerHTML = `${clock.t.toFixed(1)}<small>s</small>`;
      const rows = liveRows();
      const casts = document.getElementById('eg-casts');
      casts.innerHTML = T.castRows('eg', rows, clock.t,
        clock.t < LIVE.reveal ? 'Paradeigma has gone off. Nothing to do yet.' : 'Nothing casting.', st.castSlots);
      const note = document.getElementById('eg-liveNote');
      const locked = st.lockNote ? `<span class="eg-locked">${st.lockNote}</span>` : '';
      note.innerHTML = !clock.running && !st.over && clock.t <= LIVE.start ? '<span class="hint">Click to move as the fight unfolds: where you stand when each part resolves is what counts.</span>' : locked;
    }

    function setPace(p){
      pace = p;
      try{ localStorage.setItem('twelfth-eg-pace', p); }catch(e){}
      panel.querySelectorAll('[data-pace]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.pace === p)));
      newRound();
    }
    panel.querySelectorAll('[data-pace]').forEach(b => {
      b.setAttribute('aria-pressed', String(b.dataset.pace === pace));
      b.addEventListener('click', () => { if(b.dataset.pace !== pace) setPace(b.dataset.pace); });
    });
    document.getElementById('eg-start').addEventListener('click', startClock);

    function startRound(){
      st.debuff = Math.random() < 0.5 ? 'astral' : 'umbral';

      const colors = shuffle(['astral','astral','umbral','umbral']);
      st.tethers = { N: colors[0], E: colors[1], S: colors[2], W: colors[3] };

      st.lean = Math.random() < 0.5 ? 'cw' : 'ccw';
      const sign = LEAN_SIGN[st.lean];
      st.offsets = {
        N: sign.N * ADD_OFFSET, E: sign.E * ADD_OFFSET,
        S: sign.S * ADD_OFFSET, W: sign.W * ADD_OFFSET
      };

      const roles = shuffle(['tank','healer','dps','dps']);
      st.tetherRoles = { N: roles[0], E: roles[1], S: roles[2], W: roles[3] };

      // Read the quadrants, not the adds: what matters is the tether colour of the player
      // standing in each quadrant.
      st.quadAspect = {}; st.quadDir = {};
      DIRS.forEach(d => {
        const q = PLAYER_QUADRANT[st.lean][d];
        st.quadAspect[q] = st.tethers[d];
        st.quadDir[q] = d;
      });
      st.scanOrder = SWEEP[shared.role];
      const opp = OPPOSITE_ASPECT[st.debuff];
      st.correctQuadrant = st.scanOrder.find(q => st.quadAspect[q] === opp);
      st.correctDir = st.quadDir[st.correctQuadrant];

      // Half the party carries a Soul, the other half catches a tether: one tank, one healer
      // and two DPS. Tethered players only ever take a tether of their own role group.
      st.part = Math.random() < 0.5 ? 'soul' : 'tether';
      st.youSpot = null;
      if(st.part === 'tether'){
        const mine = DIRS.filter(d => (st.tetherRoles[d] === 'dps') === (shared.role === 'dps'));
        st.myDir = mine[Math.floor(Math.random() * mine.length)];
        st.myAspect = st.tethers[st.myDir];
        st.myQuad = PLAYER_QUADRANT[st.lean][st.myDir];
        // Whoever drops a tower on you carries the other Soul and sweeps for your colour.
        const seeker = SWEEP.support.find(q => st.quadAspect[q] === st.myAspect) === st.myQuad
          ? 'support' : 'DPS';
        st.partner = `${aspectLabel(OPPOSITE_ASPECT[st.myAspect])}bright ${seeker}`;
      }
      st.lineup = lineUpTethered();

      const oddPair = Math.random() < 0.5;
      st.redCols = oddPair ? [1,3] : [2,4];
      st.safeCols = oddPair ? [2,4] : [1,3];

      st.step = 1;
      stopClock();
      st.live = pace === 'live';
      st.phase = st.live ? 'pre' : 'live';
      st.fired = {}; st.over = false; st.lockNote = ''; st.track = [];
      document.getElementById('eg-target').innerHTML = '';
      document.getElementById('eg-freeHits').innerHTML = '';
      (st.fxTimers || []).forEach(clearTimeout);
      st.fxTimers = [];
      st.tiltPending = false;
      st.myPick = null; st.myLane = null; st.myDrop = null; st.redShown = false;
      DIRS.forEach(d => T.unzoomAdd(document.getElementById('add-' + d)));
      clearTimeout(animTimer); animTimer = 0;
      document.getElementById('eg-fx').innerHTML = '';
      clock.t = LIVE.start;
      buildParty();
      panel.classList.toggle('eg-timed', st.live);
      document.getElementById('eg-start').hidden = !st.live;
      document.getElementById('eg-start').style.visibility = '';
      document.getElementById('eg-start').parentNode.style.minHeight = '';
      // the most casts the strip ever shows at once, so it keeps that many rows throughout
      st.castSlots = Math.max(1, ...Array.from({ length: 300 }, (_, k) => liveRows(k * 0.1).length));
      render();
    }

    /* ---------- the party ---------- */
    // All eight players: the four tethered ones (the tp- groups) and the four Soul carriers. Everyone runs
    // at 7 yalms a second, 84 units here on a 40-yalm floor drawn 480 wide, and the rest of the
    // party takes a moment to react when something new lands.
    // REACT is measured from the log: the party started moving a median 2.1 s after the tethers landed.
    // SPEED is set a little above the real 6 yalms a second (72) on purpose, to 7 yalms a second: it feels
    // better to play.
    const SPEED = 84, REACT = 2.0, STEP_OFF = 0.05, SOUL_ROW_Y = 372;
    // step by step nobody is racing the clock, so everyone runs twice as fast
    const STEP_SPEED = SPEED * 2;
    // step by step, how long after the lasers fire the party sets off for the towers
    const RUN_AFTER_LASERS = 1.0;
    // How close you have to be when the game resolves, rather than having finished your run: inside the
    // tower to soak it, within about 3.75 yalms of your tower spot, about 3.5 yalms of your stretch spot, and
    // inside the lane (its half-width less your own) for the dive.
    const IN_RANGE = { drop: 45, stretch: 42, soak: 22, lane: 48 };
    const svgEl = (name, attrs) => { const n = document.createElementNS(SVG_NS, name); for(const k in attrs) n.setAttribute(k, attrs[k]); return n; };

    function buildParty(){
      st.actors = {};
      // Before anything lands the whole party stands in two rows by Athena, shuffled, so your place in
      // them says nothing about whether you will catch a tether or a Soul.
      const spots = shuffle([0, 1, 2, 3, 4, 5, 6, 7]).map(k => [LINEUP_X[k % 4], k < 4 ? LINEUP_Y : SOUL_ROW_Y]);
      DIRS.forEach((d, i) => {
        st.actors['t' + d] = { kind:'tether', dir:d, quad: PLAYER_QUADRANT[st.lean][d], line: spots[i] };
      });
      [['support','astral'], ['support','umbral'], ['dps','astral'], ['dps','umbral']].forEach(([role, debuff], i) => {
        st.actors['s' + role + debuff] = { kind:'soul', role, debuff, line: spots[4 + i],
          quad: SWEEP[role].find(q => st.quadAspect[q] === OPPOSITE_ASPECT[debuff]) };
      });
      st.me = st.part === 'tether' ? 't' + st.myDir : 's' + shared.role + st.debuff;
      Object.keys(st.actors).forEach(id => setAt(id, st.actors[id].line));
      DIRS.forEach(d => document.getElementById('tp-' + d).setAttribute('class', 'player' + ('t' + d === st.me ? ' me' : '')));
      const host = document.getElementById('eg-souls');
      host.innerHTML = '';
      Object.keys(st.actors).filter(id => st.actors[id].kind === 'soul').forEach(id => {
        const a = st.actors[id];
        const g = svgEl('g', { id:'sp-' + id, class:'player' + (id === st.me ? ' me' : '') });
        g.appendChild(svgEl('circle', { cx:0, cy:0, r:15, fill:'var(--nebula-2)', stroke: aspectSoft(a.debuff), 'stroke-width':1.8 }));
        const u = svgEl('use', { href: a.role === 'dps' ? '#icon-dps' : '#icon-support', x:-12, y:-12, width:24, height:24 });
        u.style.color = a.role === 'dps' ? 'var(--astral-soft)' : 'var(--good)';
        g.appendChild(u);
        g.appendChild(svgEl('rect', { x:4.5, y:-30.5, width:27, height:35, rx:4, fill:'var(--nebula-2)', stroke:'var(--line-strong)', 'stroke-width':1, class:'eg-badge' }));
        g.appendChild(svgEl('image', { x:6, y:-29, width:24, height:32, href: soulIcon(a.debuff), preserveAspectRatio:'xMidYMid meet', class:'eg-badge' }));
        host.appendChild(g);
      });
    }

    // Where each player stands at each point of the mechanic when everything goes to plan.
    function jobSpot(id){
      const a = st.actors[id];
      if(a.kind === 'tether'){
        if(id === st.me && st.youSpot) return st.youSpot;
        const off = st.offsets[a.dir], v = a.dir === 'N' || a.dir === 'S';
        return [TP_BASE[a.dir][0] + (v ? off : 0), TP_BASE[a.dir][1] + (v ? 0 : off)];
      }
      if(id === st.me && st.myPick) return st.myPick;
      return towerAt(a.quad);
    }
    // a Soul carrier steps in off their tower once it has dropped
    const asideSpot = q => { const t = towerAt(q); return [300 + (t[0] - 300) * 0.7, 300 + (t[1] - 300) * 0.7]; };
    // the nearest column without a red add, keeping the same row
    function laneSpot(p){
      const x = st.safeCols.map(c => colX(c) + 60).sort((a, b) => Math.abs(a - p[0]) - Math.abs(b - p[0]))[0];
      return [x, p[1]];
    }
    function settledAt(id, phase){
      const a = st.actors[id];
      if(phase === 'line') return a.line;
      if(phase === 'job') return jobSpot(id);
      if(phase === 'post') return a.kind === 'tether' ? towerCentre(a.quad) : asideSpot(a.quad);
      if(id === st.me && st.myLane) return st.myLane;
      return laneSpot(settledAt(id, 'post'));
    }

    // Movement, on the fight clock against the clock and on the wall clock step by step.
    const sceneNow = () => st.live ? clock.t : performance.now() / 1000;
    function posAt(id, t){
      const m = st.actors[id].move;
      if(t <= m.t0) return m.from;
      if(m.dur <= 0 || t >= m.t0 + m.dur) return m.to;
      const k = (t - m.t0) / m.dur;
      return [m.from[0] + (m.to[0] - m.from[0]) * k, m.from[1] + (m.to[1] - m.from[1]) * k];
    }
    function setAt(id, p){ st.actors[id].move = { from:p, to:p, t0:0, dur:0 }; }
    // Starts a run and returns when it ends.
    function moveTo(id, to, delay){
      const t0 = sceneNow() + (delay === undefined ? STEP_OFF : delay);
      const from = posAt(id, sceneNow());
      const dur = Math.hypot(to[0] - from[0], to[1] - from[1]) / (st.live ? SPEED : STEP_SPEED);
      st.actors[id].move = { from, to, t0, dur };
      if(st.live && id === st.me) st.track.push({ at: sceneNow(), t0, dur });
      kickAnim();
      return t0 + dur;
    }
    function others(phase, delay, kind){
      Object.keys(st.actors).filter(id => id !== st.me && (!kind || st.actors[id].kind === kind))
        .forEach(id => moveTo(id, settledAt(id, phase), delay));
    }
    const actorBase = id => st.actors[id].kind === 'tether' ? TP_BASE[st.actors[id].dir] : [0, 0];
    const actorEl = id => document.getElementById(st.actors[id].kind === 'tether' ? 'tp-' + st.actors[id].dir : 'sp-' + id);
    function drawParty(){
      const t = sceneNow();
      Object.keys(st.actors).forEach(id => {
        const p = posAt(id, t), b = actorBase(id), a = st.actors[id];
        actorEl(id).setAttribute('transform', `translate(${(p[0] - b[0]).toFixed(1)},${(p[1] - b[1]).toFixed(1)})`);
        if(a.kind !== 'tether') return;
        // the tether starts on the add itself, which floats just off its edge of the platform
        const vertical = a.dir === 'N' || a.dir === 'S', off = st.offsets[a.dir];
        const ax = ADD_POS[a.dir][0] + (vertical ? off : 0), ay = ADD_POS[a.dir][1] + (vertical ? 0 : off);
        const dx = p[0] - ax, dy = p[1] - ay, len = Math.hypot(dx, dy) || 1;
        const line = document.getElementById('tl-' + a.dir);
        line.setAttribute('x1', (ax + dx / len * 22).toFixed(1)); line.setAttribute('y1', (ay + dy / len * 22).toFixed(1));
        line.setAttribute('x2', (p[0] - dx / len * 20).toFixed(1)); line.setAttribute('y2', (p[1] - dy / len * 20).toFixed(1));
      });
    }
    // Step by step the runs play out on their own; against the clock the fight clock drives them.
    let animTimer = 0;
    function kickAnim(){
      if(st.live || animTimer) return;
      const step = () => {
        drawParty();
        const t = sceneNow();
        animTimer = Object.keys(st.actors).some(id => { const m = st.actors[id].move; return t < m.t0 + m.dur; }) ? setTimeout(step, TICK_MS) : 0;
      };
      animTimer = setTimeout(step, TICK_MS);
    }

    /* ---------- the mechanic resolving ---------- */
    // One-off effects, never replayed when undo or redo rebuilds a pull.
    function later(fn, ms){ if(!T.isReplaying()) st.fxTimers.push(setTimeout(fn, ms)); }
    function fxHost(){ return document.getElementById('eg-fx'); }
    function fxAdd(node, ms){ if(T.isReplaying()) return; fxHost().appendChild(node); setTimeout(() => node.remove(), ms); }
    function towerBody(q){
      const [x, y] = (st.myDrop && q === st.correctQuadrant) ? st.myDrop : towerAt(q), a = towerAspect(q);
      const g = svgEl('g', { class:'eg-fx-pop' });
      g.appendChild(svgEl('circle', { cx:x, cy:y, r:TOWER_R, fill: a === 'astral' ? 'rgba(226,82,63,0.22)' : 'rgba(74,143,224,0.22)', stroke: aspectColor(a), 'stroke-width':2.5, filter:'url(#glow)' }));
      g.appendChild(svgEl('image', { x:x - 12, y:y - 16, width:24, height:32, href: soulIcon(a), preserveAspectRatio:'xMidYMid meet' }));
      return g;
    }
    // the towers drop where the Soul carriers stand (drawn for Soul carriers; tethered players click them)
    function fxTowers(){
      if(T.isReplaying()) return;
      const g = svgEl('g', { id:'fx-towers' });
      QUADS.forEach(q => g.appendChild(towerBody(q)));
      fxHost().appendChild(g);
    }
    function burst(x, y, r, colour){
      fxAdd(svgEl('circle', { cx:x, cy:y, r, fill:'none', stroke:colour, 'stroke-width':4, class:'eg-fx-burst', filter:'url(#glow)' }), 800);
    }
    // each Soul carrier's small AoE as the Soul runs out
    function fxGlow(){
      Object.keys(st.actors).filter(id => st.actors[id].kind === 'soul').forEach(id => {
        const [x, y] = posAt(id, sceneNow());
        burst(x, y, 30, aspectSoft(st.actors[id].debuff));
      });
    }
    // the towers go off with whoever soaks them
    function fxSoak(){
      const g = document.getElementById('fx-towers');
      if(g) g.remove();
      QUADS.forEach(q => { const [x, y] = (st.myDrop && q === st.correctQuadrant) ? st.myDrop : towerAt(q); burst(x, y, TOWER_R + 6, aspectSoft(towerAspect(q))); });
    }
    // Ray of Light down the red adds' columns
    function fxRay(){
      st.redCols.forEach(c => fxAdd(svgEl('rect', { x:colX(c), y:60, width:120, height:480, fill:'rgba(255,196,160,0.55)', class:'eg-fx-blast' }), 1300));
    }

    // Where each tethered player's marker is drawn in its own group's local space.
    const TP_BASE = { N:[300,450], E:[150,300], S:[300,150], W:[450,300] };
    // Where each add floats, just off its edge of the platform (matches the markup).
    const ADD_POS = { N:[300,36], E:[564,300], S:[300,564], W:[36,300] };

    // Before the tethers are stretched, the four tethered players stand in a row just north of Athena,
    // as the supports do in Paradeigma III. The order is shuffled every pull, so the row gives nothing away.
    const LINEUP_X = [216, 272, 328, 384], LINEUP_Y = 228;
    function lineUpTethered(){
      return shuffle([0, 1, 2, 3]).map(slot => [LINEUP_X[slot], LINEUP_Y]);
    }

    // The four places a tethered player might stretch to: straight across (right), across but
    // over the centreline so the line runs diagonally through Athena, or hanging back near the add.
    const NEAR_BASE = { N:[300,150], E:[450,300], S:[300,450], W:[150,300] };
    function stretchSpots(){
      const d = st.myDir, off = st.offsets[d], vertical = d === 'N' || d === 'S';
      const at = (b, s) => vertical ? [b[0] + s, b[1]] : [b[0], b[1] + s];
      const mine = [
        { id:'across',     xy: at(TP_BASE[d], off) },
        { id:'diagonal',   xy: at(TP_BASE[d], -off) },
        { id:'near',       xy: at(NEAR_BASE[d], off) },
        { id:'nearCross',  xy: at(NEAR_BASE[d], -off) }
      ];
      // All eight spots any tethered player could take are offered, so the choice never shows which
      // add is yours. The four across the other axis would drag your tether sideways.
      const all = [];
      DIRS.forEach(e => {
        const v = e === 'N' || e === 'S';
        [-ADD_OFFSET, ADD_OFFSET].forEach(s => {
          const xy = v ? [TP_BASE[e][0] + s, TP_BASE[e][1]] : [TP_BASE[e][0], TP_BASE[e][1] + s];
          const m = mine.find(k => k.xy[0] === xy[0] && k.xy[1] === xy[1]);
          all.push(m || { id:'side', xy });
        });
      });
      return all;
    }

    function quadOf(xy){ return (xy[1] < 300 ? 'N' : 'S') + (xy[0] < 300 ? 'W' : 'E'); }

    const DIR_NAME = { N:'north', E:'east', S:'south', W:'west' };

    function drawStretchHits(){
      const host = document.getElementById('stretchHits');
      host.innerHTML = '';
      if(st.live || st.part !== 'tether' || st.step !== 1) return;
      stretchSpots().forEach(s => {
        const [x, y] = s.xy;
        const g = document.createElementNS(SVG_NS, 'g');
        g.setAttribute('class', 'hit');
        g.setAttribute('tabindex', '0');
        g.setAttribute('role', 'button');
        g.setAttribute('aria-label', `Stretch your tether to this ${quadOf(s.xy)} spot`);
        const ring = document.createElementNS(SVG_NS, 'circle');
        ring.setAttribute('cx', x); ring.setAttribute('cy', y); ring.setAttribute('r', 27);
        ring.setAttribute('class', 'focus-ring'); ring.setAttribute('fill', 'none');
        ring.setAttribute('stroke', 'var(--mist)'); ring.setAttribute('stroke-width', '2.5'); ring.setAttribute('opacity', '0');
        const dot = document.createElementNS(SVG_NS, 'circle');
        dot.setAttribute('cx', x); dot.setAttribute('cy', y); dot.setAttribute('r', 22);
        dot.setAttribute('fill', 'rgba(241,236,249,0.10)');
        dot.setAttribute('stroke', 'var(--mist)'); dot.setAttribute('stroke-width', '2');
        g.appendChild(ring); g.appendChild(dot);
        const pick = () => { if(g.getAttribute('aria-disabled') !== 'true') answerStretch(s); };
        g.addEventListener('click', pick);
        g.addEventListener('keydown', e => { if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); pick(); } });
        host.appendChild(g);
      });
    }

    // Marks which of the four tethered players is you.
    function drawYouRing(){
      document.querySelectorAll('#panel-engrave .you-ring').forEach(n => n.remove());
      const [bx, by] = actorBase(st.me);
      const ring = document.createElementNS(SVG_NS, 'circle');
      ring.setAttribute('class', 'you-ring pulse');
      ring.setAttribute('cx', bx); ring.setAttribute('cy', by); ring.setAttribute('r', 25);
      ring.setAttribute('fill', 'none'); ring.setAttribute('stroke', 'var(--mist)');
      ring.setAttribute('stroke-width', '2.5');
      const tag = document.createElementNS(SVG_NS, 'text');
      tag.setAttribute('class', 'you-ring');
      tag.setAttribute('x', bx); tag.setAttribute('y', by + 40);
      tag.setAttribute('text-anchor', 'middle');
      tag.setAttribute('font-family', 'Space Mono, monospace'); tag.setAttribute('font-size', '11');
      tag.setAttribute('font-weight', '700'); tag.setAttribute('fill', 'var(--mist)');
      tag.textContent = 'YOU';
      const grp = actorEl(st.me);
      grp.insertBefore(ring, grp.firstChild);
      grp.appendChild(tag);
    }

    function setHitsEnabled(enabled){
      QUADS.forEach(q => document.getElementById('hit-'+q).setAttribute('aria-disabled', enabled ? 'false' : 'true'));
    }

    // The step texts: before the clock starts, then each step of your part.
    function egText(key){
      const tethered = st.part === 'tether';
      if(key === 'wait') return `Athena has cast Paradeigma, and its adds are about to show up while Engravement of Souls goes out. Get ready to move as soon as the tethers and Souls land.`;
      if(key === 'pre') return `Athena has cast Paradeigma, and its adds are about to show up while Engravement of Souls goes out. The fight clock runs in real time from here. Press Start, then click to move as soon as the tethers and Souls land.`;
      if(key === 'one') return tethered
        ? `You’re tethered to the <span class="hl">${DIR_NAME[st.myDir]}</span> add, with an <span class="hl">${aspectLabel(st.myAspect)}</span> tether. The tethers have just landed and nobody has moved yet — click the spot you stretch yours to.<span class="hint"> Stretch it <b>straight across</b> through Athena's hitbox, staying on your add's side of the centreline, so it lands in the quadrant opposite your add.</span>`
        : `You carry the <span class="hl">${aspectLabel(st.debuff)}bright Soul</span>. The tethers have just landed and nobody has moved. ${st.live ? 'Click where you drop your tower, at max melee on its intercardinal.' : 'Click the quadrant you drop your tower in.'}<span class="hint"> Each tether stretches <span class="hl">straight across</span> the arena, filling one quadrant each. Take the first quadrant in your sweep whose player will hold the <span class="hl">opposite</span> aspect to yours.</span>`;
      if(key === 'two') return `Your tether is stretched into the <span class="hl">${st.myQuad}</span> quadrant. The line AoEs have gone off, giving everyone their Tilt, and the Soul carriers have dropped their towers. Click the tower you soak.<span class="hint"> Your tether leaves you with its own Tilt, so you need the tower of the <b>opposite</b> colour — the one dropped in your own quadrant.</span>`;
      return tethered
        ? `You soaked the ${st.partner}’s tower in the <span class="hl">${st.myQuad}</span> quadrant. Click the lane you move to now.${DIVE_HINT}`
        : `You dropped your tower in the <span class="hl">${st.correctQuadrant}</span> quadrant. Click the lane you move to now.<span class="hint"> Get out of your tower before it goes off: your Soul's AoE has left you with Magic Vulnerability Up.</span>${DIVE_HINT}`;
    }

    function render(){
      // against the clock the step text keeps the height of the tallest it will show, so the arena holds still
      T.holdPrompt('engrave', st.live ? (st.part === 'tether' ? ['pre', 'wait', 'one', 'two', 'three'] : ['pre', 'wait', 'one', 'three']).map(egText) : null);
      renderLive();
      document.getElementById('eg-arena').classList.toggle('eg-pre', st.phase === 'pre');
      document.getElementById('eg-arena').classList.toggle('eg-noadds', st.phase === 'pre' && clock.t < LIVE.blueAdds);
      const debuffBadge = document.getElementById('eg-debuffBadge');
      const tethered = st.part === 'tether';
      renderTilts();
      if(tethered){
        document.getElementById('eg-assignText').textContent =
          `You caught the ${DIR_NAME[st.myDir]} add’s tether. Its line AoE hurts less the further away you stand.`;
      } else {
        debuffBadge.className = 'badge ' + st.debuff;
        debuffBadge.innerHTML = `<img src="${soulIcon(st.debuff)}" alt=""><span>${aspectLabel(st.debuff)}bright Soul</span>`;
        document.getElementById('eg-assignText').textContent = shared.role === 'support'
          ? 'Sweep the quadrants clockwise from the NE: NE → SE → SW → NW.'
          : 'Sweep the quadrants counter-clockwise from the NW: NW → SW → SE → NE.';
      }

      DIRS.forEach(d => {
        const aspect = st.tethers[d];
        const off = st.offsets[d];
        const role = st.tetherRoles[d];

        const addGroup = document.getElementById('add-'+d);
        const glow = document.getElementById('add-'+d+'-glow');
        const icon = document.getElementById('add-'+d+'-icon');
        const line = document.getElementById('tl-'+d);
        const tpGroup = document.getElementById('tp-'+d);
        const tpGlow = document.getElementById('tp-'+d+'-glow');
        const tpIcon = document.getElementById('tp-'+d+'-icon');
        const tpBadge = document.getElementById('tp-'+d+'-badge');

        glow.setAttribute('stroke', aspectSoft(aspect));
        icon.style.color = aspectSoft(aspect);
        line.setAttribute('stroke', aspectColor(aspect));

        tpGlow.setAttribute('stroke', aspectSoft(aspect));
        tpIcon.setAttribute('href', ROLE_ICON[role]);
        tpIcon.style.color = ROLE_COLOR[role];
        tpBadge.setAttribute('href', tiltIcon(aspect));

        const offset = d === 'N' || d === 'S' ? [off, 0] : [0, off];
        addGroup.setAttribute('transform', `translate(${offset[0]},${offset[1]})`);
        // step by step they zoom out from Athena as the pull opens; against the clock when they show up
        if(!st.live && st.step === 1) T.zoomAdd(addGroup, [ADD_POS[d][0] + offset[0], ADD_POS[d][1] + offset[1]], offset, 0);
        else if(!st.live) T.unzoomAdd(addGroup);
      });
      // step by step everyone stands where this step finds them; against the clock they keep running
      if(!st.live){
        const phase = st.step === 1 ? 'line' : st.step === 2 ? 'job' : 'post';
        // coming on from the lasers, everyone starts where the lasers found them and runs on afterwards
        Object.keys(st.actors).forEach(id => {
          if(!st.runFrom) return setAt(id, settledAt(id, phase));
          setAt(id, settledAt(id, st.runFrom));
          moveTo(id, settledAt(id, phase), RUN_AFTER_LASERS);
        });
      }
      drawParty();
      // the tethers are gone once their lasers have fired
      document.getElementById('tetherLines').setAttribute('visibility', st.step > 1 ? 'hidden' : 'visible');
      document.getElementById('towerHits').innerHTML = '';
      document.getElementById('eg-lasers').innerHTML = '';
      document.getElementById('eg-target').innerHTML = '';
      drawYouRing();
      drawStretchHits();

      fb.hidden = true;
      document.getElementById('eg-playerMarker').setAttribute('opacity','0');
      document.getElementById('eg-playerMarker').removeAttribute('transform');
      // the quadrant buttons belong to the Soul carriers' question only
      // and only while that question is open: the reposition step picks a lane instead
      document.getElementById('ringHits').setAttribute('visibility', !st.live && !tethered && st.step === 1 ? 'visible' : 'hidden');

      // against the clock the red adds show up with the tethers, as they do in the fight
      if(st.live) st.phase === 'pre' ? (document.getElementById('redAdds').innerHTML = '') : drawRedAdds();

      if(st.phase === 'pre'){
        document.getElementById('eg-stepPill').textContent = 'Paradeigma';
        debuffBadge.className = 'badge';
        debuffBadge.innerHTML = '<span>No debuff yet</span>';
        document.getElementById('eg-assignText').textContent = 'Wait for Engravement of Souls to land.';
        document.getElementById('eg-instrText').innerHTML = egText(clock.running ? 'wait' : 'pre');
        setHitsEnabled(false);
        document.getElementById('colHits').innerHTML = '';
        document.getElementById('colHazards').innerHTML = '';
        return;
      }

      // against the clock you click anywhere and run there, from the moment the tethers land
      if(st.live && !st.over && !document.querySelector('#eg-freeHits .free-pick')) freePick(posAt(st.me, sceneNow()), livePick);

      if(st.step === 1){
        if(tethered){
          document.getElementById('eg-stepPill').textContent = 'Step 1 · Stretch your tether';
          document.getElementById('eg-instrText').innerHTML = egText('one');
          setHitsEnabled(false);
        } else {
          document.getElementById('eg-stepPill').textContent = 'Step 1 · Place your tower';
          document.getElementById('eg-instrText').innerHTML = egText('one');
          setHitsEnabled(!st.live);
        }
        document.getElementById('colHits').innerHTML = '';
        document.getElementById('colHazards').innerHTML = '';
        if(!st.live) document.getElementById('redAdds').innerHTML = '';
      } else if(st.step === 2){
        document.getElementById('eg-stepPill').textContent = 'Step 2 · Soak a tower';
        document.getElementById('eg-instrText').innerHTML = egText('two');
        setHitsEnabled(false);
        document.getElementById('colHits').innerHTML = '';
        document.getElementById('colHazards').innerHTML = '';
        if(!st.live) document.getElementById('redAdds').innerHTML = '';
        drawTowers(st.live);
      } else {
        document.getElementById('eg-stepPill').textContent = `Step ${tethered ? 3 : 2} · Reposition`;
        document.getElementById('eg-instrText').innerHTML = egText('three');
        setHitsEnabled(false);
        buildStepTwo();
      }
    }

    // Each Soul carrier drops their tower at max melee on their quadrant's intercardinal, clear of the
    // lasers from the adds to their tethered players, so every quadrant holds one tower of the colour
    // opposite its tether. Max melee is the one-column target circle plus a few yalms.
    const TOWER_R = 26, MAX_MELEE = 156;
    function towerAt(q){
      const k = MAX_MELEE / Math.SQRT2;
      return [300 + (q[1] === 'E' ? k : -k), 300 + (q[0] === 'S' ? k : -k)];
    }
    const towerAspect = q => OPPOSITE_ASPECT[st.quadAspect[q]];

    function drawTowers(answered){
      const host = document.getElementById('towerHits');
      host.innerHTML = '';
      QUADS.forEach(q => {
        const [x, y] = towerAt(q), a = towerAspect(q);
        const g = document.createElementNS(SVG_NS, 'g');
        if(!answered){
          g.setAttribute('class', 'hit eg-fx-pop');
          g.setAttribute('tabindex', '0');
          g.setAttribute('role', 'button');
          g.setAttribute('aria-label', `Soak the ${aspectLabel(a)} tower in the ${q} quadrant`);
        }
        const ring = document.createElementNS(SVG_NS, 'circle');
        ring.setAttribute('cx', x); ring.setAttribute('cy', y); ring.setAttribute('r', TOWER_R + 5);
        ring.setAttribute('class', 'focus-ring'); ring.setAttribute('fill', 'none');
        ring.setAttribute('stroke', 'var(--mist)'); ring.setAttribute('stroke-width', '2.5'); ring.setAttribute('opacity', '0');
        const body = document.createElementNS(SVG_NS, 'circle');
        body.setAttribute('cx', x); body.setAttribute('cy', y); body.setAttribute('r', TOWER_R);
        body.setAttribute('fill', a === 'astral' ? 'rgba(226,82,63,0.22)' : 'rgba(74,143,224,0.22)');
        body.setAttribute('stroke', aspectColor(a)); body.setAttribute('stroke-width', '2.5');
        body.setAttribute('filter', 'url(#glow)');
        const icon = document.createElementNS(SVG_NS, 'image');
        icon.setAttribute('x', x - 12); icon.setAttribute('y', y - 16);
        icon.setAttribute('width', 24); icon.setAttribute('height', 32);
        icon.setAttribute('href', soulIcon(a));
        icon.setAttribute('preserveAspectRatio', 'xMidYMid meet');
        g.appendChild(ring); g.appendChild(body); g.appendChild(icon);
        if(!answered){
          const pick = () => { if(g.getAttribute('aria-disabled') !== 'true') answerTower(q); };
          g.addEventListener('click', pick);
          g.addEventListener('keydown', e => { if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); pick(); } });
        }
        host.appendChild(g);
      });
    }

    // Against the clock a click only sets you running: you can change your mind until the tower resolves.
    function answerTower(q){
      moveTo(st.me, towerAt(q));
      drawTowers(true);
      others('post');
      judgeTower(q);
    }
    function judgeTower(q){
      const want = st.myQuad, mineColour = towerAspect(want), a = towerAspect(q);
      const rule = `Your <b>${aspectLabel(st.myAspect)}</b> tether leaves you with ${aspectLabel(st.myAspect)} Tilt, so you need an <b>${aspectLabel(mineColour)}</b> tower. The ${st.partner} swept for your colour and dropped theirs at max melee on the <b>${want}</b> intercardinal, your own quadrant, clear of your add’s laser.`;
      liveFeedback();
      if(q !== want) showTarget(towerCentre(want));
      if(q === want){
        showFeedback(fb, true, 'Tower soaked',
          `${rule} Soaking it swaps the colour of your Tilt.`,
          'Continue → Step 3', () => { st.step = 3; render(); fxSoak(); });
      } else if(a === st.myAspect){
        showFeedback(fb, false, 'Same colour',
          `That is an <b>${aspectLabel(a)}</b> tower, the same colour as your tether, so you cannot soak it and it explodes. ${rule}`,
          'New pull ↻', () => newRound());
      } else {
        showFeedback(fb, false, 'Someone else’s tower',
          `Right colour, but that tower in <b>${q}</b> was dropped for the tethered player there. They soak it, and yours in <b>${want}</b> goes unsoaked. ${rule}`,
          'New pull ↻', () => newRound());
      }
    }

    function colX(n){ return 60 + (n-1)*120; }

    // Before you answer the danger columns are only hinted at below their adds; afterwards the full line shows.
    function drawHazards(full){
      const hazards = document.getElementById('colHazards');
      hazards.innerHTML = '';
      st.redCols.forEach(c => {
        const rect = document.createElementNS('http://www.w3.org/2000/svg','rect');
        rect.setAttribute('x', colX(c)); rect.setAttribute('y', 60);
        rect.setAttribute('width', 120); rect.setAttribute('height', 480);
        if(full){
          rect.setAttribute('fill', 'rgba(226,82,63,0.16)');
          rect.setAttribute('stroke', 'var(--astral)');
          rect.setAttribute('stroke-width', '3');
          rect.setAttribute('stroke-dasharray', '13 11');   // 24 per repeat, one stripe cycle
          rect.setAttribute('class','stripe');
        } else {
          rect.setAttribute('fill', 'url(#eg-addFade)');
        }
        hazards.appendChild(rect);
      });
    }

    function drawRedAdds(){
      const adds = document.getElementById('redAdds');
      adds.innerHTML = '';
      // they zoom out from Athena the first time they show in a pull
      st.redCols.forEach(c => {
        const marker = document.createElementNS('http://www.w3.org/2000/svg','circle');
        // further out than the tether adds, so the north one never hides a red add
        marker.setAttribute('cx', colX(c) + 60); marker.setAttribute('cy', 16);
        marker.setAttribute('r', 11);
        if(!st.redShown) T.zoomAdd(marker, [colX(c) + 60, 16], null, 0);
        marker.setAttribute('fill', 'var(--astral)');
        marker.setAttribute('filter','url(#glow)');
        adds.appendChild(marker);
      });
      st.redShown = true;
    }

    function buildStepTwo(){
      const hazards = document.getElementById('colHazards');
      const hits = document.getElementById('colHits');
      const adds = document.getElementById('redAdds');
      hazards.innerHTML = ''; hits.innerHTML = '';
      drawRedAdds();
      drawHazards(false);
      if(st.live) return;

      for(let c=1;c<=4;c++){
        const x = colX(c);

        const hit = document.createElementNS('http://www.w3.org/2000/svg','g');
        hit.setAttribute('class','col-hit hit');
        hit.setAttribute('tabindex','0');
        hit.setAttribute('role','button');
        hit.setAttribute('aria-label', 'Move into the ' + COL_WORD[c] + ' column');
        const hrect = document.createElementNS('http://www.w3.org/2000/svg','rect');
        hrect.setAttribute('x', x); hrect.setAttribute('y', 60);
        hrect.setAttribute('width', 120); hrect.setAttribute('height', 480);
        hrect.setAttribute('fill', 'transparent');
        hit.appendChild(hrect);
        const mark = document.createElementNS('http://www.w3.org/2000/svg','rect');
        mark.setAttribute('class','lane-mark');
        mark.setAttribute('x', x+8); mark.setAttribute('y', 68);
        mark.setAttribute('width', 104); mark.setAttribute('height', 464);
        mark.setAttribute('rx', 8);
        hit.appendChild(mark);
        const focus = document.createElementNS('http://www.w3.org/2000/svg','rect');
        focus.setAttribute('class','col-focus');
        focus.setAttribute('x', x+3); focus.setAttribute('y', 63);
        focus.setAttribute('width', 114); focus.setAttribute('height', 474);
        focus.setAttribute('fill','none'); focus.setAttribute('stroke','var(--mist)');
        focus.setAttribute('stroke-width','2'); focus.setAttribute('opacity','0');
        hit.appendChild(focus);
        hit.addEventListener('click', () => answerStepTwo(c));
        hit.addEventListener('keydown', (e) => { if(e.key==='Enter'||e.key===' '){ e.preventDefault(); answerStepTwo(c); } });
        hits.appendChild(hit);
      }
    }

    function traceExplanation(){
      const opp = OPPOSITE_ASPECT[st.debuff];
      return st.scanOrder.map(q => {
        const a = st.quadAspect[q];
        return `${q}:${aspectLabel(a)}${a === opp ? ' ←match' : ''}`;
      }).join('  ');
    }

    // As the tethers resolve, each add fires its line AoE at its tethered player and on across the
    // platform. A one-off effect: it plays when you continue, never when undo or redo rebuilds the pull.
    // The Tilts land with the lasers: against the clock when they hit, step by step once the beams have run
    // (st.tiltPending holds them back while they do).
    function tilted(){ return st.live ? clock.t >= LIVE.laserHit : st.step >= 2 && !st.tiltPending; }
    function renderTilts(){
      const on = st.phase !== 'pre' && tilted();
      document.getElementById('eg-arena').classList.toggle('eg-untilted', !on);
      if(st.part !== 'tether') return;
      const badge = document.getElementById('eg-debuffBadge');
      badge.className = 'badge ' + st.myAspect;
      badge.innerHTML = on
        ? `<img src="${tiltIcon(st.myAspect)}" alt=""><span>${aspectLabel(st.myAspect)} Tilt · ${DIR_NAME[st.myDir]} add</span>`
        : `<span>${aspectLabel(st.myAspect)} tether · ${DIR_NAME[st.myDir]} add</span>`;
    }
    function shootLasers(){
      if(!st.live && !T.isReplaying()){
        st.tiltPending = true;
        renderTilts();
        later(() => { st.tiltPending = false; renderTilts(); }, 800);
      }
      T.playBeams(document.getElementById('eg-lasers'), DIRS.map(d => {
        const vertical = d === 'N' || d === 'S', off = st.offsets[d];
        const g = document.getElementById('tp-' + d).getAttribute('transform').match(/-?[\d.]+/g).map(Number);
        return {
          from: [ADD_POS[d][0] + (vertical ? off : 0), ADD_POS[d][1] + (vertical ? 0 : off)],
          through: [TP_BASE[d][0] + g[0], TP_BASE[d][1] + g[1]]
        };
      }));
    }

    function answerStepOne(quadrant){
      st.myPick = towerAt(quadrant);
      moveTo(st.me, st.myPick);
      others('job');
      judgeStepOne(quadrant);
    }
    function judgeStepOne(quadrant){
      setHitsEnabled(false);
      liveFeedback();
      if(quadrant === st.correctQuadrant){
        showFeedback(fb, true, 'Tower placed correctly',
          `Sweep: <b>${traceExplanation()}</b>. <b>${st.correctQuadrant}</b> is the first quadrant whose tethered player is opposite your ${aspectLabel(st.debuff)}bright Soul. That player is tethered to the ${st.correctDir} add across the arena.`,
          'Continue → Step 2', lasersThenTowers);
      } else {
        showTarget(towerAt(st.correctQuadrant));
        showFeedback(fb, false, 'Wrong tower',
          `Your sweep should have stopped at the <b>${st.correctQuadrant}</b> quadrant. Trace: <b>${traceExplanation()}</b>.`,
          'New pull ↻', () => newRound());
      }
    }

    // Step by step for the Soul carriers: the towers drop and the lasers fire at the tethered players where
    // they stretched, then everyone runs to the towers, which go off once the soakers are in.
    function lasersThenTowers(){
      st.step = 3;
      st.runFrom = 'job';
      render();
      st.runFrom = null;
      shootLasers(); fxTowers(); later(fxGlow, 900);
      const arrived = Math.max(...Object.keys(st.actors).map(id => st.actors[id].move.t0 + st.actors[id].move.dur)) - sceneNow();
      later(fxSoak, (arrived + 0.4) * 1000);
    }

    function answerStretch(spot){
      st.youSpot = spot.xy;
      moveTo(st.me, spot.xy);
      others('job');
      judgeStretch(spot);
    }
    function judgeStretch(spot){
      document.getElementById('stretchHits').innerHTML = '';

      const side = { N:'east', S:'west', E:'south', W:'north' };   // cw lean: which way each add sits
      const leanSide = st.lean === 'cw' ? side[st.myDir]
        : { east:'west', west:'east', north:'south', south:'north' }[side[st.myDir]];
      const why = `The ${DIR_NAME[st.myDir]} add floats just <b>${leanSide}</b> of its edge centre, so straight across through Athena’s hitbox lands you in the <b>${st.myQuad}</b> quadrant, as far from the add as the tether allows.`;

      liveFeedback();
      if(spot.id !== 'across') showTarget(acrossSpot());
      if(spot.id === 'across'){
        showFeedback(fb, true, 'Tether stretched',
          `${why} The <b>${st.partner}</b> will find you there and drop their tower at your feet for you to soak.`,
          'Continue → Step 2', () => { st.step = 2; render(); shootLasers(); later(fxGlow, 900); });
      } else if(spot.id === 'diagonal'){
        showFeedback(fb, false, 'Wrong side of the centreline',
          `Far enough, but that line runs diagonally through the centre and puts you in <b>${quadOf(spot.xy)}</b>, a quadrant that belongs to another tethered player. ${why}`,
          'New pull ↻', () => newRound());
      } else if(spot.id === 'side'){
        showFeedback(fb, false, 'Tether pulled sideways',
          `That spot is off to the side of your add, not across from it, so the tether runs sideways over the arena instead of through Athena’s hitbox${quadOf(spot.xy) === st.myQuad
            ? `. It is still in your own quadrant, <b>${st.myQuad}</b>, just not the spot straight across from your add.`
            : `, and it leaves you in <b>${quadOf(spot.xy)}</b>, another tethered player’s quadrant.`} ${why}`,
          'New pull ↻', () => newRound());
      } else if(spot.id === 'short'){
        showFeedback(fb, false, 'Tether too short',
          `You were in your own quadrant, <b>${st.myQuad}</b>, but not far enough from your add when its line AoE fired, and the closer you are the harder it hits. Stretch right to the far side of the quadrant. ${why}`,
          'New pull ↻', () => newRound());
      } else {
        showFeedback(fb, false, 'Tether not stretched',
          `You stayed on your add’s half of the arena, so its line AoE hits at close range. ${why}`,
          'New pull ↻', () => newRound());
      }
    }

    const COL_WORD = { 1:'westmost', 2:'second-from-west', 3:'second-from-east', 4:'eastmost' };
    const DIVE_HINT = `<span class="hint"> Two red adds float just north of the platform and fire straight down their own columns, so step into a column with <b>no add above it</b>.</span>`;
    function answerStepTwo(col){
      document.querySelectorAll('#panel-engrave .col-hit').forEach(h => { h.style.pointerEvents = 'none'; h.setAttribute('aria-disabled', 'true'); });
      st.myLane = [colX(col) + 60, posAt(st.me, sceneNow())[1]];
      moveTo(st.me, st.myLane);
      others('lane');
      fxRay();
      drawHazards(true);
      if(st.safeCols.includes(col)){
        showFeedback(fb, true, 'Mechanic cleared',
          `You moved into the ${COL_WORD[col]} column, clear of the dive. The two red adds north of the platform fired down the <b>${st.redCols.map(c => COL_WORD[c]).join(' and ')}</b> columns.`,
          'New pull ↻', () => newRound());
      } else {
        showTarget(laneSpot(st.myLane));
        showFeedback(fb, false, 'Caught in the dive',
          `Two red adds float just north of the platform, off the edge where they are easy to miss. They fire straight down the <b>${st.redCols.map(c => COL_WORD[c]).join(' and ')}</b> columns, so the ${COL_WORD[col]} column was not safe. Check for them after the towers and step into a column with no add above it.`,
          'New pull ↻', () => newRound());
      }
    }

    const colOf = x => Math.max(1, Math.min(4, Math.floor((x - 60) / 120) + 1));

    function resolveRay(){
      st.over = true;
      stopClock();
      endFreePick();
      document.querySelectorAll('#panel-engrave .col-hit').forEach(h => { h.style.pointerEvents = 'none'; h.setAttribute('aria-disabled', 'true'); });
      drawHazards(true);
      const tethered = st.part === 'tether';
      // a lane counts as picked if you set off after your job was done
      const job = tethered ? LIVE.soak[1] : LIVE.towers;
      const lane = T.runRecap(st.track, job, LIVE.rayHit);
      const moved = !!lane, running = moved && lane.ready === Infinity;
      const col = colOf(posAt(st.me, LIVE.rayHit)[0]);
      const safe = st.safeCols.includes(col);
      const line = (label, since, deadline, idle) => `<li>${label}: ${T.recapText(T.runRecap(st.track, since, deadline), deadline, idle)}</li>`;
      const recap = `<ul>`
        + (tethered
          ? line('Tether stretched', 0, LIVE.lasers[1]) + line('Tower soaked', LIVE.lasers[1], LIVE.soak[1])
          : line('Tower spot reached', 0, LIVE.towers))
        + line('Lane picked', job, LIVE.rayHit, 'not done') + `</ul>`;
      const cols = st.redCols.map(c => COL_WORD[c]).join(' and ');
      renderLive();
      fb.dataset.noUndo = '1';
      // only where you are when it lands counts, even mid-run
      if(safe && moved){
        showFeedback(fb, true, 'Mechanic cleared',
          `Ray of Light landed at <b>${LIVE.rayHit.toFixed(1)} s</b>, down the ${cols} columns, and you were clear in the ${COL_WORD[col]} one${running ? ', still on the move' : ''}.${recap}`,
          'New pull ↻', () => newRound());
      } else if(safe){
        showFeedback(fb, 'warn', 'Safe by luck',
          `You never picked a lane, but where you stood, in the ${COL_WORD[col]} column, happened to be clear of Ray of Light down the ${cols} columns. Next time, find the gap between the red adds as soon as your job is done.${recap}`,
          'New pull ↻', () => newRound());
      } else {
        showTarget(laneSpot(posAt(st.me, LIVE.rayHit)));
        showFeedback(fb, false, 'Caught in the dive',
          `Ray of Light landed at <b>${LIVE.rayHit.toFixed(1)} s</b> down the ${cols} columns, and you were ${running ? 'still running, in' : moved ? '' : 'still '}${running ? ' ' : 'in '}the ${COL_WORD[col]} one. Its cast starts at ${LIVE.ray[0].toFixed(1)} s, so as soon as your job is done, look north for the red adds and step into a column with none above it.${recap}`,
          'New pull ↻', () => newRound());
      }
    }

    QUADS.forEach(q => {
      const g = document.getElementById('hit-'+q);
      g.addEventListener('click', () => { if(g.getAttribute('aria-disabled') !== 'true') answerStepOne(q); });
      g.addEventListener('keydown', (e) => {
        if((e.key==='Enter'||e.key===' ') && g.getAttribute('aria-disabled') !== 'true'){ e.preventDefault(); answerStepOne(q); }
      });
    });

    const newRound = T.trackRounds('engrave', startRound);
    shared.roleListeners.push(newRound);
    newRound();
  }

  T.register({ id: 'engrave', label: 'Paradeigma II', phase: 'Athena', players: 'role', markup: MARKUP, styles: STYLES, init: initEngrave });
})(window.Twelfth);
