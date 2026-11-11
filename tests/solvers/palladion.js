// Real-time solver for Palladion. It reads the pull through window.__p4, a hook run.py adds to a copy of
// mechanics/palladion.js, and plays your number's part of the plan: each of scheduleOf's moves at its time (the
// rest of the party plays the same schedule). probe.plays: 'right' clears with every pair; 'wrong' breaks one
// rule per pull, each of which must fail with its own title.
Probe.run('panel-palladion', 'p4-clock', async ({ P, log, sleep, clockT, head, until, click }) => {
  const D = window.__p4;
  const reroll = async () => { P.querySelector('[data-history="reroll"]').click(); await sleep(30); };
  async function play(mode, who){
    await reroll();
    // `who`: a pair ('13') or one number (3)
    const fits = () => !who || (typeof who === 'number' ? D.st().num === who : D.st().group === who);
    for(let k = 0; !fits() && k < 200; k++) await reroll();
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
    // 1/3 stay on dash 1's spot after it lands
    if(mode === 'puddle') moves = moves.filter(m => m.at < L.stack[0]);
    // 6/8 walk into dash 1's stack, beside the line
    if(mode === 'crowd') moves = [at(2.0, [360, 490])];
    // 5/7 bait from the very spot their partner stands on
    if(mode === 'close') moves = [at(2.0, D.planSpot(D.PARTNER[me], 3))].concat(moves.filter(m => m.at > L.flame[st.ys[0] - 1]));
    // 3 sets up for dash 3 well inside the wall, not by puddle 1
    if(mode === 'offspot') moves = moves.filter(m => m.at < L.stack[0] || m.at > L.dash[2]).concat(
      at(L.stack[0] + 0.3, [D.DASH[3][0] + (300 - D.DASH[3][0]) * 0.33, D.DASH[3][1] + (300 - D.DASH[3][1]) * 0.33])).sort((a, b) => a.at - b.at);
    // right, but each of your dashes lands 1.4 yalms clockwise of its spot (within reach), so the later puddles pack from there
    if(mode === 'nudge') moves = moves.map(m => {
      const k = st.plan[st.group].findIndex((e, i) => e.act === 'move' && e.kind === 'dash' && Math.abs(m.at - (i === 0 ? L.shock[0] + 0.15 : L.stack[i - 1] + 0.3)) < 0.01);
      if(k < 0) return m;
      return { at: m.at, spot: () => { const p = m.spot(), dx = p[0] - 300, dy = p[1] - 300, r = Math.hypot(dx, dy); return [p[0] - dy / r * 25, p[1] + dx / r * 25]; } };
    });
    for(const m of moves){
      await until(m.at + 0.05);
      if(head()) break;
      click(m.spot());
    }
    await until(40);
    return `${me} adds ${st.adds.slice(1).join('')} -> ${head().slice(0, 40)} @${clockT().toFixed(1)}`;
  }
  if(window.__probe.plays === 'right'){
    for(const g of ['13', '24', '57', '68', '13', '24', '57', '68', null, null]) log.push('right: ' + await play('right', g));
    for(const g of ['13', '24', '57', '68']) log.push('nudge: ' + await play('nudge', g));
  } else {
    for(const [m, g] of [['stay', null], ['early', '24'], ['nobait', '57'], ['greedy', '68'], ['puddle', '13'], ['crowd', '68'], ['close', '57'], ['offspot', 3]])
      log.push(m + ': ' + await play(m, g));
  }
});
