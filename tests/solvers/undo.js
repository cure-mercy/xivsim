// Undo in a step-by-step drill whose answers are marked spots: a seeded random walk clicks any open spot (or
// Continue), takes back each wrong answer with the feedback's undo (which must give back the page exactly),
// then steps the whole pull back with undo and forward with redo, comparing every state.
// probe.skip / probe.strip: what the snapshot leaves out (see Probe.snapshot).
Probe.run(window.__probe.panel, window.__probe.clock, async ({ P, log }) => {
  const { skip, strip } = window.__probe;
  const snap = () => Probe.snapshot(P, { skip, strip });
  let seed = 12345;
  const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
  const Ub = P.querySelector('[data-history="undo"]'), Rb = P.querySelector('[data-history="redo"]');
  for(let round = 0; round < 8; round++){
    P.querySelector('[data-history="reroll"]').click();
    const snaps = [snap()];
    let steps = 0, fbBad = 0;
    for(let k = 0; k < 40 && steps < 12; k++){
      const fbShown = !P.querySelector('.feedback').hidden;
      const btns = [...P.querySelectorAll('.feedback:not([hidden]) .btn:not([data-fb-undo])')].filter(b => /Continue/.test(b.textContent));
      const hits = [...P.querySelectorAll('.hit')].filter(h => h.getAttribute('aria-disabled') !== 'true' && h.style.pointerEvents !== 'none' && !h.closest('[visibility=hidden]'));
      const pool = fbShown ? btns : hits;
      if(!pool.length) break;
      const before = snap();
      pool[Math.floor(rnd() * pool.length)].dispatchEvent(new MouseEvent('click', { bubbles: true }));
      const fu = P.querySelector('.feedback:not([hidden]) [data-fb-undo].bad');
      if(fu){ fu.click(); if(snap() !== before) fbBad++; continue; }
      steps++;
      snaps.push(snap());
    }
    let ub = 0, rb = 0;
    for(let k = steps - 1; k >= 0; k--){
      Ub.click();
      const now = snap();
      if(now !== snaps[k] && !ub++){
        let i = 0; while(now[i] === snaps[k][i]) i++;
        log.push('  first mismatch, ' + (steps - k) + ' undos in: WANT ' + snaps[k].slice(i - 200, i + 150) + '  GOT ' + now.slice(i - 200, i + 150));
      }
    }
    for(let k = 1; k <= steps; k++){ Rb.click(); if(snap() !== snaps[k]) rb++; }
    log.push('pull ' + round + ': ' + steps + ' steps, feedback undo off ' + fbBad + ', undo off ' + ub + ', redo off ' + rb + (fbBad || ub || rb ? ' FAIL' : ''));
  }
});
