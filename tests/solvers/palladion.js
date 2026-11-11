// Real-time solver for Palladion. It reads the pull through window.__p4, a hook run.py adds to a copy of
// mechanics/palladion.js, and plays your number's part of the plan: each of scheduleOf's moves at its time (the
// rest of the party plays the same schedule). probe.plays: 'right' clears with every pair; 'wrong' breaks one
// rule per pull, each of which must fail with its own title.
Probe.run('panel-palladion', 'p4-clock', async ({ P, log, sleep, clockT, head, until, click }) => {
  const D = window.__p4;
  const reroll = async () => { P.querySelector('[data-history="reroll"]').click(); await sleep(30); };
  async function play(mode, who){
    await reroll();
    // `who`: a pair ('13'), one number (3) or a test of the pull
    const fits = () => !who || (typeof who === 'function' ? who(D.st()) : typeof who === 'number' ? D.st().num === who : D.st().group === who);
    for(let k = 0; !fits() && k < 600; k++) await reroll();
    const st = D.st(), me = st.num, L = D.LIVE;
    document.getElementById('p4-start').click();
    let moves = D.scheduleOf(me);
    const at = (t, spot) => ({ at: t, spot: () => spot });
    if(mode === 'stay') moves = [];
    // 2/4 into Athena's corner before dash 1 has gone through it
    if(mode === 'early') moves = [moves[0], at(3.0, D.DASH[2]), ...moves.slice(1)];
    // 5/7 wait at the wall instead of standing in for the first lasers
    if(mode === 'nobait') moves = [at(2.0, D.WALL['57'])].concat(moves.filter(m => m.at > L.flame[st.ys[0] - 1]));
    // 6/8 stand in closer to the middle than 5/7 while those have the lasers
    if(mode === 'greedy') moves = [at(2.0, [380, 330])];
    // 1/3 step off dash 2's line after dash 1 but stay in its puddle
    if(mode === 'puddle') moves = moves.filter(m => m.at < L.stack[0]).concat(at(L.stack[0] + 0.3, [D.DASH[1][0] + 2.5 * D.Y, D.DASH[1][1] - 1.1 * D.Y]));
    // 6/8 walk into dash 1's stack, beside the line
    if(mode === 'crowd') moves = [at(2.0, [360, 490])];
    // 5/7 bait from the very spot their partner stands on
    if(mode === 'close') moves = [at(2.0, D.planSpot(D.PARTNER[me], 3))].concat(moves.filter(m => m.at > L.flame[st.ys[0] - 1]));
    // 3 sets up for dash 3 four yalms too far along the wall, not just past puddle 1
    if(mode === 'offspot') moves = moves.filter(m => m.at < L.stack[0] || m.at > L.dash[2]).concat(
      at(L.stack[0] + 0.3, D.pathPt(D.alongOf(D.DASH[3]) + 4 * D.Y))).sort((a, b) => a.at - b.at);
    // right, but each of your dashes lands 1.4 yalms clockwise of its spot (within reach), so the later puddles pack from there
    if(mode === 'nudge') moves = moves.map(m => {
      const k = st.plan[st.group].findIndex((e, i) => e.act === 'move' && e.kind === 'dash' && Math.abs(m.at - (i === 0 ? L.shock[0] + 0.15 : L.stack[i - 1] + 0.3)) < 0.01);
      if(k < 0) return m;
      return { at: m.at, spot: () => { const p = m.spot(), dx = p[0] - 300, dy = p[1] - 300, r = Math.hypot(dx, dy); return [p[0] - dy / r * 25, p[1] + dx / r * 25]; } };
    });
    for(const m of moves){
      await until(m.at + 0.05);
      if(head()) break;
      // a run along the wall: click each corner on the way, then the spot
      const to = m.spot(), pts = m.ring ? D.ringVia(D.pos(me), to).concat([to]) : [to];
      for(const [i, p] of pts.entries()){
        if(head()) break;
        const d = Math.hypot(p[0] - D.pos(me)[0], p[1] - D.pos(me)[1]);
        click(p);
        if(i < pts.length - 1) await until(clockT() + d / D.SPEED);
      }
    }
    await until(40);
    return `${me} adds ${st.adds.slice(1).join('')} -> ${head().slice(0, 40)} @${clockT().toFixed(1)}`;
  }
  // every number against every order of the first four adds (48 pulls; not in a suite: scratch/palladion/sweep.py)
  if(window.__probe.plays === 'sweep'){
    for(let num = 1; num <= 8; num++) for(const first of ['YYPP', 'YPYP', 'YPPY', 'PYYP', 'PYPY', 'PPYY']){
      log.push('sweep: ' + await play('right', st => st.num === num && st.adds.slice(1, 5).join('') === first));
    }
  } else if(window.__probe.plays === 'right'){
    for(const g of ['13', '24', '57', '68', '13', '24', '57', '68', null, null]) log.push('right: ' + await play('right', g));
    for(const g of ['13', '24', '57', '68']) log.push('nudge: ' + await play('nudge', g));
  } else {
    for(const [m, g] of [['stay', null], ['early', '24'], ['nobait', '57'], ['greedy', '68'], ['puddle', '13'], ['crowd', '68'], ['close', '57'], ['offspot', 3]])
      log.push(m + ': ' + await play(m, g));
  }
});
