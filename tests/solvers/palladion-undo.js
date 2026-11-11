// Undo in Palladion, step by step: tests/solvers/undo.js's seeded random walk, except that a spot pick (the
// starting spot, or where to reposition) is answered half the time at the plan's spot, read through window.__p4,
// and half the time at a random point on the floor, which is mostly wrong and so taken back with the feedback's
// undo (which must give back the page exactly). After each pull it steps all the way back with undo and forward
// with redo, comparing every state.
Probe.run('panel-palladion', 'p4-clock', async ({ P, log, click }) => {
  const D = window.__p4, L = D.LIVE;
  const { skip, strip } = window.__probe;
  const snap = () => Probe.snapshot(P, { skip, strip });
  let seed = 12345;
  const rnd = () => { seed = (seed * 1103515245 + 12345) % 2147483648; return seed / 2147483648; };
  const Ub = P.querySelector('[data-history="undo"]'), Rb = P.querySelector('[data-history="redo"]');
  // where the plan has you for the spot asked now: the start, or the move of dash n
  const planned = () => {
    const st = D.st(), n = st.step - 1, e = n >= 1 && st.plan[st.group][n - 1];
    // 5/7 may hold on dash 3 or reposition a dash early to the dash 5 spot: having chosen Reposition, that spot
    if(e && e.early) return D.DASH[e.early];
    return D.planSpot(st.num, st.step === 1 ? 3.0 : n === 1 ? L.shock[0] + 0.2 : L.stack[n - 2] + 0.35);
  };
  for(let round = 0; round < 8; round++){
    P.querySelector('[data-history="reroll"]').click();
    const snaps = [snap()];
    let steps = 0, fbBad = 0, freeRight = 0, freeWrong = 0, stuck = {};
    for(let k = 0; k < 60 && steps < 16; k++){
      { const s = D.st(), key = `${s.num} step ${s.step}${s.sub ? ' spot' : ''} (${(s.plan[s.group][s.step - 2] || { act:'start' }).act})`; stuck[key] = (stuck[key] || 0) + 1; }
      const fbShown = !P.querySelector('.feedback').hidden;
      const btns = [...P.querySelectorAll('.feedback:not([hidden]) .btn:not([data-fb-undo])')].filter(b => /Continue/.test(b.textContent));
      const hits = [...P.querySelectorAll('.hit')].filter(h => h.getAttribute('aria-disabled') !== 'true' && h.style.pointerEvents !== 'none' && !h.closest('[visibility=hidden]'));
      const pool = fbShown ? btns : hits;
      if(!pool.length) break;
      const before = snap(), pick = pool[Math.floor(rnd() * pool.length)];
      // a spot for Reposition: a wrong one is taken back together with choosing Reposition (the drill's undo depth 2)
      const reposition = !fbShown && pick.hasAttribute('data-free') && D.st().sub;
      if(!fbShown && pick.hasAttribute('data-free')){
        const right = rnd() < 0.5;
        click(right ? planned() : [70 + rnd() * 460, 70 + rnd() * 460]);
        right ? freeRight++ : freeWrong++;
      } else pick.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      const fu = P.querySelector('.feedback:not([hidden]) [data-fb-undo].bad');
      if(fu){
        fu.click();
        // Reposition chosen where it is wrong goes back past it (two clicks); the right move to a wrong spot
        // only to the spot question (one)
        const now = snap();
        if(reposition && now !== before && snaps.length > 1 && now === snaps[snaps.length - 2]){ snaps.pop(); steps--; }
        else if(now !== before) fbBad++;
        continue;
      }
      steps++;
      snaps.push(snap());
    }
    let ub = 0, rb = 0;
    for(let k = steps - 1; k >= 0; k--){
      Ub.click();
      const now = snap();
      if(now !== snaps[k] && !ub++){
        let i = 0; while(now[i] === snaps[k][i]) i++;
        log.push('  first mismatch, ' + (steps - k) + ' undos in: WANT ' + snaps[k].slice(Math.max(0, i - 200), i + 150) + '  GOT ' + now.slice(Math.max(0, i - 200), i + 150));
      }
    }
    for(let k = 1; k <= steps; k++){ Rb.click(); if(snap() !== snaps[k]) rb++; }
    log.push('pull ' + round + ': ' + steps + ' steps (spots ' + freeRight + ' planned, ' + freeWrong + ' random), feedback undo off ' + fbBad
      + ', undo off ' + ub + ', redo off ' + rb + (fbBad || ub || rb || steps < 3 ? ' FAIL' : '')
      + (steps < 16 ? ' | most tries at ' + Object.entries(stuck).sort((a, b) => b[1] - a[1])[0].join(': ') : ''));
  }
});
