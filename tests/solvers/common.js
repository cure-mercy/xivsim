/* Shared by the solvers. Each runs inside a probe page that tests/run.py builds from index.html, plays its
   drill against the clock, and leaves its log in a <pre id="__log"> for run.py to read back. */
window.Probe = (function(){
  const log = [], finishers = [];
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  // Every recap a pull ends with (the list in its feedback), logged once each.
  function watchRecaps(P){
    const seen = new Set();
    new MutationObserver(() => {
      const f = P.querySelector('.feedback:not([hidden])');
      const u = f && f.querySelector('ul');
      if(!u) return;
      const h = f.querySelector('.feedback-head');
      const t = (h ? h.textContent.trim() : '') + ' | ' + u.textContent.replace(/\s+/g, ' ').trim();
      if(!seen.has(t)){ seen.add(t); log.push('RECAP ' + t); }
    }).observe(P, { subtree: true, childList: true, attributes: true, attributeFilter: ['hidden'] });
  }

  function finish(){
    finishers.forEach(fn => fn(log));
    log.push('ERRORS=' + JSON.stringify(window.__errors));
    const pre = document.createElement('pre');
    pre.id = '__log';
    pre.textContent = log.join('\n');
    document.body.appendChild(pre);
  }

  // Runs `body` once the page has loaded, with the drill's panel and helpers for the fight clock:
  //   clockT() the clock, head() the title of the feedback showing (empty while the pull runs),
  //   until(t) waits for the clock to reach t or the pull to end, click(at) clicks the floor at a spot.
  function run(panelId, clockId, body){
    window.addEventListener('load', async () => {
      const P = document.getElementById(panelId);
      watchRecaps(P);
      const clockT = () => parseFloat(document.getElementById(clockId).textContent);
      const head = () => { const f = P.querySelector('.feedback:not([hidden]) .feedback-head'); return f ? f.textContent.trim() : ''; };
      const until = async t => { while(clockT() < t && !head()) await sleep(30); };
      const click = at => {
        const h = P.querySelector('.free-pick:not([aria-disabled="true"])');
        if(!h) return false;
        const ev = new MouseEvent('click', { bubbles: true });
        ev.freeAt = at;
        h.dispatchEvent(ev);
        return true;
      };
      try{
        await body({ P, log, sleep, clockT, head, until, click, probe: window.__probe || {} });
      }catch(err){ log.push('CRASH ' + err.message + ' ' + err.stack); }
      finish();
    });
  }

  // The page state undo and redo must give back exactly: a panel's markup, less the history buttons, the
  // layers `skip` names by id (passing effects), the classes `strip` names and the style of elements with a
  // class in `unstyle` (effects that animate). Hidden feedback counts as one thing whatever it holds.
  function snapshot(P, o = {}){
    const skip = o.skip || [], strip = o.strip || [], unstyle = o.unstyle || [];
    const canon = n => {
      if(n.nodeType === 3) return n.nodeValue.replace(/\s+/g, ' ');
      if(n.nodeType !== 1) return '';
      if(n.classList.contains('history-ctrls') || skip.includes(n.id)) return '';
      if(n.classList.contains('feedback') && n.hidden) return '<FB hidden>';
      const bare = unstyle.some(c => n.classList.contains(c));
      const attrs = [...n.attributes].filter(a => !(bare && a.name === 'style'))
        .map(a => a.name + '=' + (a.name === 'class' ? a.value.split(' ').filter(c => !strip.includes(c)).join(' ') : a.value));
      return '<' + n.nodeName + ' ' + attrs.sort().join(' ') + '>' + [...n.childNodes].map(canon).join('') + '</>';
    };
    return canon(P);
  }

  return { run, snapshot, onFinish: fn => finishers.push(fn) };
})();
