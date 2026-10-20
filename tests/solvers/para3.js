// Real-time solver for Paradeigma III. It reads the pull through window.__p3, a hook run.py adds to a copy of
// mechanics/paradeigma-3.js, and clicks the plan's spot for each beat. Wrong plays, each of which must fail:
// stays put, another platform's tower, soaks from the centre-line side, the DPS's near platform, the partner's
// spot, the other job, the other drop, stays in its own + or X, never steps out of its tower, into the tower
// before the bright Souls' AoEs, the other tower, walks off the platform. (The + and X supports always bait:
// their yellow add stands on their own platform, so wherever they stand on it they are among its nearest two.)
Probe.run('panel-para3', 'p3-clock', async ({ P, log, sleep, clockT, head, until, click, probe }) => {
  const D = window.__p3;
  const L = D.LIVE;
  const support = 'TH'.includes(probe.slot[0]);
  // the debuffs a wrong play needs: rerolled until the pull has them
  const NEEDS = {
    wrongtower: s => true, centreline: s => s.mySoul === 'bright', stayin: s => s.mySoul === 'quartered' || s.mySoul === 'xmarked',
    wrongdrop: s => s.mySoul === 'bright', nostep: s => s.mySoul === 'bright',
    wrongjob: s => true, wrongsoak: s => s.job === 'soak', early: s => s.job === 'soak',
    near: s => true, swap: s => true, walkoff: s => true, stay: s => true, right: s => true
  };
  async function play(mode){
    P.querySelector('[data-history="reroll"]').click(); await sleep(30);
    for(let k = 0; k < 200 && !NEEDS[mode](D.st()); k++){ P.querySelector('[data-history="reroll"]').click(); await sleep(10); }
    const st = D.st(), me = st.me, plan = ph => D.plan(me, ph);
    const tag = (support ? st.mySoul : (st.straight ? 'straight' : 'crossed') + '/' + st.job) + ' zig' + st.zig;
    document.getElementById('p3-start').click();
    if(mode !== 'stay'){
      if(support){
        await until(L.enchain[0] + 0.3);
        if(mode === 'wrongtower'){ const other = st.safe.find(t => t.key !== st.home.key); click(D.supTowerSpot(other)); }
        else if(mode === 'centreline'){ const p = plan('first'); click([p[0], 2 * D.plainTower(st.home)[1] - p[1]]); }
        else click(plan('first'));
        await until(L.laserHit + 0.3);
        if(mode === 'walkoff'){ const t = st.home; click([t.cx, t.row <= 2 ? t.y + t.h + 40 : t.y - 40]); }
        else if(mode === 'wrongdrop') click(st.towerSpot === 'centre' ? D.dropSpot('soak', st.home) : D.centreCorner(st.home, 16));
        else click(plan('job'));
        if(st.mySoul !== 'bright'){
          await until(L.marks + 0.15);
          if(mode !== 'stayin') click(plan('clear'));
          if(st.mySoul === 'xmarked'){ await until(L.aoes + 0.05); if(mode !== 'stayin') click(plan('bait')); }
        } else if(mode !== 'nostep'){
          await until(L.drop + 0.3); click(plan('aside'));
        }
      } else {
        await until(L.tethers + 0.3);
        if(mode === 'near'){ const t = st.home === st.midW ? st.midE : st.midW; click([t.cx, t.cy]); }
        else if(mode === 'swap') click(D.plan(D.dpsKey(st.home, !st.straight), 'first'));
        else click(plan('first'));
        await until(L.laserHit + 0.3);
        if(mode === 'walkoff'){ const t = st.home; click([t.cx, t.row === 2 ? t.y - 40 : t.y + t.h + 40]); }
        // the wrong job: a soaker goes to bait, a baiter to its own platform's tower on the centre corner
        else if(mode === 'wrongjob') click(st.job === 'soak' ? D.baitSpotOf(me) : D.centreCorner(st.home, 40));
        // too early: straight into the tower spot, before the bright Souls' small AoEs have gone off
        else if(mode === 'early') click(plan('soak'));
        else click(plan('job'));
        if(st.job === 'soak' && mode !== 'wrongjob' && mode !== 'early'){
          await until(L.glow + 0.1);
          click(mode === 'wrongsoak' ? D.plan(D.dpsKey(st.home, !st.straight), 'soak') : plan('soak'));
        }
      }
    }
    await until(40);
    return tag + ' -> ' + head().slice(0, 36) + ' @' + clockT().toFixed(1);
  }
  // The Soul picker: supports only. Each pick must deal that Soul (and a bright one its aspect) every pull, and play.
  const picker = document.getElementById('p3-debuffPick');
  if(!support) log.push('picker ' + (picker.hidden ? 'hidden for DPS' : 'SHOWN FOR DPS FAIL'));
  else for(const id of ['quartered', 'xmarked', 'astral', 'umbral', 'random']){
    picker.querySelector(`[data-pick="${id}"]`).click(); await sleep(10);
    const seen = new Set();
    for(let k = 0; k < 20; k++){
      P.querySelector('[data-history="reroll"]').click(); await sleep(5);
      const s = D.st(); seen.add(s.mySoul === 'bright' ? s.bright : s.mySoul);
    }
    const want = id === 'random' ? null : id;
    const ok = want ? seen.size === 1 && seen.has(want) : seen.size > 1;
    const pressed = picker.querySelector('[aria-pressed="true"]').dataset.pick === id;
    log.push(`pick ${id}: dealt ${[...seen].sort().join(',')}${ok && pressed ? '' : ' FAIL'}` + (want ? ' | ' + await play('right') : ''));
  }
  for(let i = 0; i < 12; i++) log.push('right: ' + await play('right'));
  const wrong = support ? ['stay', 'wrongtower', 'centreline', 'walkoff', 'wrongdrop', 'nostep', 'stayin'] : ['stay', 'near', 'swap', 'walkoff', 'wrongjob', 'early', 'wrongsoak'];
  for(const m of wrong) log.push(m + ': ' + await play(m));
});
