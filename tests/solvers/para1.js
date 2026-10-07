// A player-like solver for Paradeigma I in real time: it reads the wings as they light and the adds' half,
// then clicks its spot for each phase at a human-ish moment. Variants: late starter, wrong side, stays put.
Probe.run('panel-para1', 'p1-clock', async ({ P, log, clockT, head, until, click, probe }) => {
  const ME = probe.slot;
  const wingSide = row => {
    const y = { 0:110, 1:78, 2:46 }[row];
    const lit = [...document.querySelectorAll('#p1-wingArt path')].find(p => p.getAttribute('fill') === 'var(--aether)' && (p.getAttribute('d') || '').includes(',' + y + ' L'));
    return lit ? (/^M288/.test(lit.getAttribute('d')) ? 'W' : 'E') : null;
  };
  const LINE = { T:35, M:90, H:165, R:220 }, OTHER = { W:'E', E:'W' };
  const lp = ME[1] === '1' ? 1 : 2;
  async function play(mode){
    P.querySelector('[data-history="reroll"]').click();
    document.getElementById('p1-start').click();
    await until(6.6);
    const addsN = [...document.querySelectorAll('#p1-adds circle')][0].getAttribute('cy') < 300, dir = addsN ? -1 : 1;
    const w = [wingSide(0)];
    const cleave = i => i === 1 ? OTHER[w[1]] : w[i];
    const sx = (i, o) => 300 + (cleave(i) === 'W' ? 1 : -1) * (o || 30);
    const spot = i => { const bait = (i === 0 ? 1 : 2) === lp; return bait ? [sx(i, 15), 300 + dir * LINE[ME[0]]] : [sx(i), 300 - dir * 95]; };
    if(mode === 'stay'){ await until(30); return; }
    if(mode === 'late') await until(14.2);
    if(mode === 'wrongside') click([600 - sx(0), spot(0)[1]]);
    else click(spot(0));
    await until(9.6); w[1] = wingSide(1); await until(12.6); w[2] = wingSide(2);
    await until(16.4);
    // sidestep onto the second cleave's safe side first, then run along it
    const here = [...document.querySelectorAll('#p1-players .player.me circle')][1], hy = +here.getAttribute('cy');
    if(sx(1) !== sx(0)){ click([sx(1), hy]); await until(17.2); }
    click(spot(1));
    await until(18.3); click(spot(2));
    await until(30);
  }
  for(const mode of ['right', 'right', 'right', 'late', 'wrongside', 'stay']){
    await play(mode);
    log.push(ME + ' ' + mode + ': ' + head() + ' @' + clockT().toFixed(1) + ' — ' + (P.querySelector('.feedback-body') || {}).textContent.replace(/\s+/g, ' ').slice(0, 110));
  }
});
