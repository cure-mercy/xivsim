// Real-time solver for Superchain I. It reads the pull through window.__sc, a hook run.py adds to a copy of
// mechanics/superchain-1.js, and clicks the spot for each beat. Variants: wrong distance, wrong laser side,
// wrong tower, stays put.
Probe.run('panel-superchain', 'sc-clock', async ({ P, log, sleep, clockT, head, until, click }) => {
  const D = window.__sc;
  async function play(mode){
    P.querySelector('[data-history="reroll"]').click(); await sleep(30);
    const st = D.st(), me = st.me;
    document.getElementById('sc-start').click();
    const tag = st.key + (st.debuffs.length > 1 ? '+flame' : '') + ' ' + st.firstDist + '/' + st.firstForm + (st.firstForm === 'purple' ? '(' + st.purpleRole + ')' : '') + ' last ' + st.a5;
    await until(2.0);
    if(mode === 'wrongdist'){
      const c = D.CPOS[st.first], p = D.spotFirst(me), k = st.firstDist === 'donut' ? 3 : 0.3;
      click([c[0] + (p[0] - c[0]) * k, c[1] + (p[1] - c[1]) * k]);
    }
    else if(mode !== 'stay') click(D.spotFirst(me));
    await until(12.6);
    if(mode === 'wrongside'){ const p = D.spotLaser(me), c = D.CPOS[st.second]; click([2 * c[0] - p[0], 2 * c[1] - p[1]]); }
    else if(mode !== 'stay') click(D.spotLaser(me));
    await until(20.4); if(mode !== 'stay') click(D.spotLast(me, 0));
    await until(24.4); if(mode !== 'stay') click(D.spotLast(me, 1));
    await until(26.3);
    if(mode === 'wrongtower'){
      const mine = { astralbright:'right', umbralbright:'left', astralstrong:'left', umbralstrong:'right' }[st.key] || 'left';
      click(D.towerSpot(mine === 'left' ? 'right' : 'left'));
    }
    else if(mode !== 'stay') click(D.spotTowers(me, false));
    await until(28.4); if(mode !== 'stay' && mode !== 'wrongtower') click(D.spotTowers(me, true));
    await until(40);
    return tag + ' -> ' + head().slice(0, 34) + ' @' + clockT().toFixed(1);
  }
  for(let i = 0; i < 6; i++) log.push('right: ' + await play('right'));
  for(const m of ['wrongdist', 'wrongside', 'wrongtower', 'stay']) log.push(m + ': ' + await play(m));
});
