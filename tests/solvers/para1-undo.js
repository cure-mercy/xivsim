// Undo in Paradeigma I, step by step. Each step's answer is a click anywhere on the floor, so for every step
// it clicks a grid over the whole floor, taking each click back (with the feedback's own undo where there
// is one, which must give back the page exactly), then answers at the middle of the spots that passed.
// After the pull it steps all the way back with undo and forward with redo, comparing every state.
Probe.run('panel-para1', 'p1-clock', async ({ P, log, head, click }) => {
  const snap = () => Probe.snapshot(P, { skip: ['p1-fx', 'p1-beams'], unstyle: ['p1-fx-settle', 'p1-fx-late'] });
  const U = P.querySelector('[data-history="undo"]'), R = P.querySelector('[data-history="redo"]');
  const grid = [];
  for(let x = 70; x <= 530; x += 20) for(let y = 70; y <= 530; y += 20) grid.push([x, y]);
  for(let r = 0; r < 6; r++){
    if(r) P.querySelector('[data-history="reroll"]').click();
    const snaps = [snap()], parts = [];
    let fbBad = 0, failed = false;
    for(let step = 1; step <= 3; step++){
      const oks = [], titles = {};
      grid.forEach(g => {
        const before = snap();
        click(g);
        const h = head(), t = h.replace(/^\S+ /, '');
        titles[t] = (titles[t] || 0) + 1;
        if(/✓/.test(h)) oks.push(g);
        const fu = P.querySelector('.feedback:not([hidden]) [data-fb-undo]');
        if(fu){ fu.click(); if(snap() !== before) fbBad++; }
        else U.click();
      });
      if(!oks.length){ parts.push('FAIL step ' + step + ': no spot passes ' + JSON.stringify(titles)); failed = true; break; }
      const cx = oks.reduce((a, g) => a + g[0], 0) / oks.length, cy = oks.reduce((a, g) => a + g[1], 0) / oks.length;
      const spread = Math.max(...oks.map(g => Math.hypot(g[0] - cx, g[1] - cy)));
      parts.push('s' + step + ' ' + oks.length + ' spots pass around (' + cx.toFixed(0) + ',' + cy.toFixed(0) + ') r' + spread.toFixed(0));
      click([Math.round(cx), Math.round(cy)]);
      snaps.push(snap());
      if(!/✓/.test(head())){ parts.push('FAIL their middle does not: ' + head()); failed = true; break; }
      const c = [...P.querySelectorAll('.feedback:not([hidden]) .btn')].find(b => /Continue/.test(b.textContent));
      if(c){ c.click(); snaps.push(snap()); }
    }
    const steps = snaps.length - 1;
    let ub = 0, rb = 0;
    for(let k = steps - 1; k >= 0; k--){ U.click(); if(snap() !== snaps[k]) ub++; }
    for(let k = 1; k <= steps; k++){ R.click(); if(snap() !== snaps[k]) rb++; }
    const bad = fbBad || ub || rb;
    log.push('pull ' + r + ': ' + parts.join(' | ') + ' | feedback undo off ' + fbBad + ', undo off ' + ub + ', redo off ' + rb
      + (bad && !failed ? ' FAIL' : '') + ' | ' + head());
  }
});
