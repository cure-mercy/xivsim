// Loaded beside a real-time solver: watches the arena (probe.arena) every 50 ms while the fight clock runs and
// reports, per pull, how far it moved up or down the page. The layout is built to hold the arena still, so
// casts coming and going, the step text changing or Start hiding must never shift it under the pointer.
(function(){
  const pulls = [];
  let cur = null, lastT = 0;
  window.addEventListener('load', () => {
    const { panel, arena } = window.__probe;
    const P = document.getElementById(panel), A = document.getElementById(arena);
    setInterval(() => {
      const c = P.querySelector('[id$="-clock"]'), live = c && c.closest('[hidden]') === null;
      const t = live ? parseFloat(c.textContent) : 0;
      if(P.hidden || !(t > 0)) return;
      const y = Math.round(A.getBoundingClientRect().top + window.scrollY);
      if(t < lastT){ pulls.push(cur); cur = null; }
      lastT = t;
      cur = cur || { lo: y, hi: y, moves: [] };
      if(y < cur.lo || y > cur.hi) cur.moves.push(t.toFixed(1) + ' s: ' + y);
      cur.lo = Math.min(cur.lo, y);
      cur.hi = Math.max(cur.hi, y);
    }, 50);
  });
  Probe.onFinish(log => {
    if(cur) pulls.push(cur);
    const moved = pulls.some(p => p.hi > p.lo);
    log.push('ARENA ' + window.innerWidth + ' px wide, movement per pull: '
      + (pulls.length ? pulls.map(p => (p.hi - p.lo) + ' px' + (p.moves.length ? ' (' + p.moves.join(', ') + ')' : '')).join(' | ') : 'NO SAMPLES')
      + (moved || !pulls.length ? ' FAIL' : ''));
  });
})();
