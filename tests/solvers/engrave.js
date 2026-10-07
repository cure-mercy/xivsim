// Free-form real-time solver for Paradeigma II: clicks spots on the floor at human-ish times. A Soul carrier
// tries each quadrant until one clears, then every pull also plays the ways of getting it wrong.
Probe.run('panel-engrave', 'eg-clock', async ({ P, log, sleep, head, until, click }) => {
  const U = P.querySelector('[data-history="undo"]');
  const TP_BASE = { N:[300,450], E:[150,300], S:[300,150], W:[450,300] }, K = 156 / Math.SQRT2;
  const towerAt = q => [300 + (q[1] === 'E' ? K : -K), 300 + (q[0] === 'S' ? K : -K)];
  const quadOf = xy => (xy[1] < 300 ? 'N' : 'S') + (xy[0] < 300 ? 'W' : 'E');
  const QUADS = ['NE', 'SE', 'SW', 'NW'];
  const laneX = () => { const red = [...document.querySelectorAll('#redAdds circle')].map(c => +c.getAttribute('cx')); return [120, 240, 360, 480].filter(x => !red.includes(x)); };
  const addOffset = d => document.getElementById('add-' + d).getAttribute('transform').match(/-?[\d.]+/g).map(Number);
  async function attempt(mode, q){
    while(!U.disabled) U.click();
    document.getElementById('eg-start').click();
    await until(10.4);
    const tp = document.querySelector('.you-ring')?.closest('g[id^="tp-"]');
    if(tp){
      const d = tp.id.slice(3), add = addOffset(d);
      const v = d === 'N' || d === 'S', off = v ? add[0] : add[1];
      const across = v ? [TP_BASE[d][0] + off, TP_BASE[d][1]] : [TP_BASE[d][0], TP_BASE[d][1] + off];
      const mq = quadOf(across);
      if(mode === 'stay'){ await until(40); return head(); }
      if(mode === 'clip'){
        const AP = { N:[300,36], E:[564,300], S:[300,564], W:[36,300] }[d], A = v ? [AP[0] + off, AP[1]] : [AP[0], AP[1] + off];
        const tw = towerAt(mq), L = Math.hypot(tw[0] - A[0], tw[1] - A[1]);
        const pt = [tw[0] + (tw[0] - A[0]) / L * 60, tw[1] + (tw[1] - A[1]) / L * 60];
        log.push('  clip: stand at ' + pt.map(x => x.toFixed(0)) + ' in ' + quadOf(pt) + ' (mine ' + mq + ')');
        click(pt);
      }
      else if(mode === 'short') click([300 + (across[0] - 300) * 0.45, 300 + (across[1] - 300) * 0.45]);
      else if(mode === 'diagonal') click(v ? [TP_BASE[d][0] - off, TP_BASE[d][1]] : [TP_BASE[d][0], TP_BASE[d][1] - off]);
      else if(mode === 'detour'){ click(v ? [TP_BASE[d][0] - off, TP_BASE[d][1]] : [TP_BASE[d][0], TP_BASE[d][1] - off]); await until(12.0); click(across); }
      else if(mode === 'late'){ await until(15.0); click(across); }
      else click(across);
      await until(18.4);
      const tq = mode === 'wrongtower' ? QUADS[(QUADS.indexOf(mq) + 1) % 4] : mq;
      click(mode === 'edge' ? [towerAt(tq)[0] + (300 - towerAt(tq)[0]) * 0.2, towerAt(tq)[1] + (300 - towerAt(tq)[1]) * 0.2] : towerAt(tq));
      await until(21.6);
      const me = towerAt(mq);
      click([laneX().sort((a, b) => Math.abs(a - me[0]) - Math.abs(b - me[0]))[0], me[1]]);
      await until(40);
      return head();
    }
    const tq = QUADS[q];
    if(mode === 'stay'){ await until(40); return head(); }
    if(mode === 'off') click([towerAt(tq)[0] + (towerAt(tq)[0] - 300) * 0.55, towerAt(tq)[1] + (towerAt(tq)[1] - 300) * 0.55]);
    else if(mode === 'detour'){ click(towerAt(QUADS[(q + 1) % 4])); await until(12.5); click(towerAt(tq)); }
    else if(mode === 'laserdrop'){
      // drop just inside the tolerance, shifted towards the nearest laser line so it stands in it
      const t = towerAt(tq); let best = null;
      for(const d of ['N', 'E', 'S', 'W']){
        const off = addOffset(d), v = d === 'N' || d === 'S';
        const dist = v ? Math.abs(t[0] - (300 + off[0])) : Math.abs(t[1] - (300 + off[1]));
        if(!best || dist < best.dist) best = { d, v, dist, line: v ? 300 + off[0] : 300 + off[1] };
      }
      const shift = best.dist - 20, sgn = Math.sign(best.line - (best.v ? t[0] : t[1]));
      click(best.v ? [t[0] + sgn * shift, t[1]] : [t[0], t[1] + sgn * shift]);
      log.push('  laserdrop: nearest line ' + best.d + ' ' + best.dist.toFixed(0) + ' away, shifted ' + shift.toFixed(0));
    }
    else click(towerAt(tq));
    await until(17.6);
    const t = towerAt(tq), aside = [300 + (t[0] - 300) * 0.7, 300 + (t[1] - 300) * 0.7];
    if(mode !== 'stayin') click(aside);
    await until(19.8);
    if(mode !== 'stayin') click([laneX().sort((a, b) => Math.abs(a - aside[0]) - Math.abs(b - aside[0]))[0], aside[1]]);
    await until(40);
    return head();
  }
  for(let pull = 0; pull < 4; pull++){
    if(pull) P.querySelector('[data-history="reroll"]').click();
    await sleep(50);
    const tethered = !!document.querySelector('.you-ring')?.closest('g[id^="tp-"]');
    let out = (tethered ? 'TETHER' : 'SOUL') + ' pull ' + pull + ':';
    let q = 0;
    if(!tethered){
      for(q = 0; q < 4; q++){ const r = await attempt('right', q); if(/^✓/.test(r)){ out += ' right(' + QUADS[q] + '): ' + r.slice(0, 24); break; } }
      if(q === 4){ log.push(out + ' NO QUADRANT CLEARS'); continue; }
    }
    else out += ' right: ' + (await attempt('right')).slice(0, 24);
    const modes = tethered ? ['clip', 'detour', 'late', 'short', 'diagonal', 'wrongtower', 'edge', 'stay'] : ['laserdrop', 'detour', 'off', 'stayin', 'wrongq', 'stay'];
    for(const m of modes){
      const r = m === 'wrongq' ? await attempt('right', (q + 1) % 4) : await attempt(m, q);
      out += ' | ' + m + ': ' + r.slice(0, 26);
    }
    log.push(out);
  }
});
