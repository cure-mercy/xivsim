/* P12S progress site: raid days -> groups -> players, drawn from data.json (written by build_site.py).
   Routes: #/  ·  #/day/<date>  ·  #/day/<date>/<group>  ·  #/day/<date>/<group>/<player>
           #/rotations  ·  #/rotations/<job>  ·  #/rotations/<job>/<gcd>   (the optimizer's rotations, tools/rotation)
           #/gear  ·  #/gear/<job>   (the best-in-slot sets, tools/gear)
   Every name in the data is inserted with textContent, never as HTML. */
"use strict";

let DATA = null;

// ---------- small helpers ----------
function el(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k === "on") for (const [ev, fn] of Object.entries(v)) e.addEventListener(ev, fn);
    else e.setAttribute(k, v);
  }
  for (const k of kids.flat()) if (k != null && k !== false) e.append(k instanceof Node ? k : document.createTextNode(String(k)));
  return e;
}
const NS = "http://www.w3.org/2000/svg";
function sv(tag, attrs, text) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) if (v != null) e.setAttribute(k, v);
  if (text != null) e.textContent = text;
  return e;
}
const mmss = s => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
const pct = (v, d = 0) => v == null ? "–" : `${(100 * v).toFixed(d)}%`;
const signed = (v, d = 0) => v == null ? "–" : `${v >= 0 ? "+" : "−"}${Math.abs(100 * v).toFixed(d)}%`;
const kfmt = v => v == null ? "–" : `${(v / 1000).toFixed(1)}k`;
const hpfmt = v => v == null ? "–" : `${v.toFixed(v < 1 ? 2 : 1)}% HP`;
const secs = hp => hp == null ? "–" : `≈${(hp * DATA.benchmark.sec_per_hp).toFixed(1)} s of kill time`;
const times = n => n === 1 ? "once" : n === 2 ? "twice" : `${n} times`;
const num = (v, d = 0) => v == null ? "–" : v.toLocaleString("en-GB", { minimumFractionDigits: d, maximumFractionDigits: d });
const dayName = d => new Date(d + "T12:00").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
const sum = xs => xs.reduce((a, b) => a + b, 0);
const median = xs => { const s = [...xs].sort((a, b) => a - b); return s.length ? (s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : null; };
const JOB = { Paladin: "PLD", Warrior: "WAR", DarkKnight: "DRK", Gunbreaker: "GNB", WhiteMage: "WHM", Scholar: "SCH", Astrologian: "AST", Sage: "SGE",
  Monk: "MNK", Dragoon: "DRG", Ninja: "NIN", Samurai: "SAM", Reaper: "RPR", Viper: "VPR", Bard: "BRD", Machinist: "MCH", Dancer: "DNC",
  BlackMage: "BLM", Summoner: "SMN", RedMage: "RDM", Pictomancer: "PCT" };
const ROLES = ["Tank", "Healer", "Melee", "Ranged", "Caster"];

// grades: green good, yellow ok, red focus; thresholds come from the scorecard (data.benchmark.grades)
function grade(kind, v) {
  if (v == null) return null;
  const [good, ok] = DATA.benchmark.grades[kind];
  const lowerBetter = kind === "mistakes" || kind === "wipes";
  const g = lowerBetter ? (v <= good ? "good" : v <= ok ? "ok" : "bad") : (v >= good ? "good" : v >= ok ? "ok" : "bad");
  return g;
}
function gradeChip(g) {
  if (!g) return "";
  const word = { good: "good", ok: "ok", bad: "focus" }[g];   // the dot is the mark; the word is for hover and screen readers
  return el("span", { class: `g ${g}`, title: word }, el("span", { class: "sr-only" }, word));
}

// confidence: how sure the classifier's reading of the log is (shown, not discounted). share: how much of a mistake is a
// culprit's (1/n when it cannot tell n players apart, a share of a shortfall spread over the party); the rates count it
const CONF_LEVELS = ["high", "medium", "low"];
const confCell = c => c ? el("span", { class: `conf ${c}`, title: `${c} confidence: how sure the classifier's reading of the log is` }, c) : "";
const FRACTIONS = [[1 / 2, "½"], [1 / 3, "⅓"], [2 / 3, "⅔"], [1 / 4, "¼"], [3 / 4, "¾"], [1 / 5, "⅕"], [1 / 6, "⅙"], [1 / 7, "1/7"], [1 / 8, "⅛"]];
const frac = x => (FRACTIONS.find(([v]) => Math.abs(v - x) < 0.005) || [0, x.toFixed(2)])[1];
// " (½)" after a culprit whose share of the mistake is less than all of it
const shareOf = (shares, c) => shares && shares[c] != null && shares[c] < 0.999 ? ` (${frac(shares[c])})` : "";
const shareCell = x => x != null && x < 0.999 ? el("span", { class: "muted", title: "their share: the classifier could not tell the players named apart, or the shortfall was the party's" }, ` ${frac(x)} share`) : "";
// "9 high, 3 medium" from {high: 9, medium: 3}
const confText = counts => CONF_LEVELS.filter(c => (counts || {})[c]).map(c => `${counts[c]} ${c}`).join(", ");

// ---------- data shaping ----------
function reports() { return Object.values(DATA.reports || {}); }
function days() {
  const by = {};
  for (const r of reports()) (by[r.day] = by[r.day] || []).push(r);
  for (const d in by) by[d].sort((a, b) => a.group.localeCompare(b.group, "en", { numeric: true }));
  return Object.keys(by).sort().map(d => ({ day: d, groups: by[d] }));
}
// the most frequent blamed cause of the wipes (named with its mechanic), and how many wipes nobody is blamed for yet:
// a mechanic without rules, no culprit found, or the wipe called
const UNBLAMED = /^(Not blamed yet|No culprit found|Wipe called|Unclear)/;
function topWipe(rs) {
  const c = {}; let unblamed = 0;
  for (const r of rs) for (const q of r.pulls) if (q.wipe && q.wipe.label) {
    if (UNBLAMED.test(q.wipe.label)) unblamed++; else { const k = causeName(q.wipe.mechanic, q.wipe.label); c[k] = (c[k] || 0) + 1; } }
  return { topWipe: Object.entries(c).sort((a, b) => b[1] - a[1])[0], unblamed };
}
const topWipeCell = s => el("span", {}, s.topWipe ? `${s.topWipe[0]} (${s.topWipe[1]})` : "–",
  s.unblamed > (s.topWipe ? s.topWipe[1] : 0) ? el("span", { class: "muted" }, ` · ${s.unblamed} not blamed yet`) : "");
function stats(rs) {   // summary over one or more group reports
  const pulls = sum(rs.map(r => r.pulls_total));
  // a report seen as progress only has no players: build_site.progress_of counts them without names (player_pulls, m, np)
  const playerPulls = sum(rs.map(r => r.players ? sum(r.players.filter((p, i, a) => a.findIndex(q => q.name === p.name) === i).map(p => p.pulls)) : r.player_pulls || 0));
  const mistakes = sum(rs.map(r => sum(r.pulls.map(p => p.mistakes ? sum(p.mistakes.map(m => m.share ?? 1)) : p.m || 0))));   // each culprit's share, as the players' rates
  const wipeCauses = {};
  for (const r of rs) for (const [k, n] of Object.entries(r.wipe_causes || {})) wipeCauses[k] = (wipeCauses[k] || 0) + n;
  const withParty = rs.filter(r => r.party);
  return {
    // longest from the pulls' own lengths where there are some, so it reads the same as the pull it was (r.longest is unrounded)
    pulls, kills: sum(rs.map(r => r.kills)), best: Math.min(...rs.map(r => r.best)), longest: Math.max(...rs.map(r => r.pulls.length ? Math.max(...r.pulls.map(p => p.dur)) : r.longest)),
    clean2: sum(rs.map(r => r.clean2)), mistakesPerPull: playerPulls ? mistakes / playerPulls : null,
    // per player and minute of pull, up to where each pull was lost (as the mistakes are counted)
    mistakesPerMin: (() => { const m = sum(rs.map(r => sum(r.pulls.map(p => (p.players ? p.players.length : p.np || 0) * Math.min(p.dur, p.wipe ? p.wipe.t + 2 : p.dur) / 60))));
      return m ? mistakes / m : null; })(),
    party: withParty.length ? sum(withParty.map(r => r.party * r.clean2)) / sum(withParty.map(r => r.clean2)) : null,
    wipeCauses, ...topWipe(rs),
    lostPerPull: (() => { const ok = rs.filter(r => !r.echo); const n = sum(ok.map(r => r.pulls_total));   // Echo reports have nothing to value mistakes at
      return n ? sum(ok.map(r => r.lost_total || 0)) / n : null; })(),
    lostDDPerPull: (() => { const ok = rs.filter(r => !r.echo); const n = sum(ok.map(r => r.pulls_total));
      return n ? sum(ok.map(r => r.lost_dd || 0)) / n : null; })(),
  };
}
// mistake budget: the share of boss HP a group can lose to mistakes over a whole kill and still kill before enrage,
// given its 0:00-2:00 party DPS against the minimum to clear; in deaths or Damage Downs at their full cost
function budget(rs) {
  // a death or Damage Down in a kill is not cut short by a wipe: price them at full length, at the group's average
  // player DPS (party DPS / 8): dead until raised plus the raise's Weakness, and Damage Down's penalty while it lasts
  const B = DATA.benchmark, s = stats(rs), min = B.pools.clears.party_dps_min, mt = B.mistake_times || { dead_s: 10, dd_s: 6.7 };
  if (!s.party || !min) return null;
  const player = s.party / 8, boss = B.hp_checkpoints.boss_hp;
  const death = (mt.dead_s + (B.raise_s || 100) * (B.raise_penalty || { Weakness: 0.22 }).Weakness) * player / boss * 100;
  const dd = mt.dd_s * (B.dd_penalty || 0.38) * player / boss * 100;
  const hp = Math.max(0, (1 - min / s.party) * 100);
  return { hp, party: s.party, min, death, dd, deaths: hp / death, dds: hp / dd };
}
const budgetTile = rs => { const b = budget(rs);
  if (!b) return ["Mistake budget", "–", "needs a clean 0:00–2:00 pull"];
  if (b.hp <= 0) return ["Mistake budget", "none", `party DPS ${kfmt(b.party)} is below the ${kfmt(b.min)} needed to clear`];
  return ["Mistake budget", `${b.hp.toFixed(1)}% HP`, `per kill ≈ ${b.deaths != null ? b.deaths.toFixed(1) : "–"} deaths or ${b.dds != null ? Math.floor(b.dds) : "–"} Damage Downs (party DPS ${kfmt(b.party)} vs ${kfmt(b.min)} needed)`]; };

// pacing over one or more nights: time in combat against the raid time (each group's first pull to its last pull's
// end), the reset between pulls (one pull's end to the next one's start), pulls per hour and breaks of 5 minutes or more
const BREAK_S = 300;
function pacing(rs) {
  let span = 0, combat = 0, pulls = 0; const gaps = [];
  for (const r of rs) {
    const ps = r.pulls.filter(p => p.at != null).sort((a, c) => a.at - c.at);
    if (ps.length < 2) continue;
    span += (ps[ps.length - 1].at + ps[ps.length - 1].dur * 1000 - ps[0].at) / 1000; combat += sum(ps.map(p => p.dur)); pulls += ps.length;
    for (let i = 1; i < ps.length; i++) gaps.push((ps[i].at - ps[i - 1].at) / 1000 - ps[i - 1].dur);
  }
  return span ? { span, combat, share: combat / span, reset: median(gaps.filter(g => g < BREAK_S)), perHour: pulls / (span / 3600), breaks: gaps.filter(g => g >= BREAK_S).length } : null;
}
const pacingTile = rs => { const x = pacing(rs);
  return ["In combat", x ? pct(x.share) : "–", x ? `of ${(x.span / 3600).toFixed(1)} h raid time${rs.length > 1 ? ` (${rs.length} groups)` : ""} · reset ${Math.round(x.reset)} s · ${x.perHour.toFixed(1)} pulls/h · ${x.breaks} break${x.breaks === 1 ? "" : "s"} of 5+ min` : "needs pull times"]; };
// the night in thirds by pull order, per group: how long pulls last and the mistakes per player per minute in pulls
// (up to where each pull was lost, as the trend charts count them)
function nightThirds(rs) {
  const t = [0, 1, 2].map(() => ({ n: 0, dur: 0, m: 0, mins: 0, pp: 0 }));
  for (const r of rs) {
    const ps = [...r.pulls].sort((a, c) => (a.at || 0) - (c.at || 0) || a.n - c.n);
    ps.forEach((p, i) => { const x = t[Math.min(2, Math.floor(3 * i / ps.length))], np = p.players ? p.players.length : p.np || 0;
      x.n++; x.pp += np; x.dur += p.dur; x.m += p.mistakes ? sum(p.mistakes.map(m => m.share ?? 1)) : p.m || 0;
      x.mins += np * Math.min(p.dur, p.wipe ? p.wipe.t + 2 : p.dur) / 60; });
  }
  return t.map((x, i) => ({ name: ["First third", "Middle third", "Last third"][i], n: x.n, dur: x.n ? x.dur / x.n : null, perMin: x.mins ? x.m / x.mins : null,
    perPull: x.pp ? x.m / x.pp : null }));
}

// what one death of theirs costs at full length: time dead until raised (median over our reports) plus the raise's
// Weakness for its whole duration, at their own rDPS; as boss HP, kill time at the group's party DPS, and against the
// group's mistake budget (Echo pulls are already left out of avg and party)
function deathTile(r, p) {
  const b = DATA.benchmark, rdps = p.avg || null;
  if (!rdps) return ["One death costs", "–", "needs a clean 0:00–2:00 pull"];   // label below gets the explanation
  const lost = (b.mistake_times.dead_s + b.raise_s * b.raise_penalty.Weakness) * rdps, hp = 100 * lost / b.hp_checkpoints.boss_hp;
  const bud = budget([r]), fits = bud && bud.hp > 0 ? bud.hp / hp : null;
  const label = el("span", {}, "One death costs", help(`One death of theirs at full length: ${b.mistake_times.dead_s.toFixed(0)} s dead until raised (median over our reports) plus ${b.raise_s} s of Weakness (−${Math.round(100 * b.raise_penalty.Weakness)}% damage), at their average rDPS over clean 0:00–2:00 pulls. Kill time: that damage at the group's party DPS. Budget: how many such deaths fit in the group's mistake budget for a whole kill. A second death within the Weakness gives Brink of Death (−50%) and costs more.`));
  return [label, `${hp.toFixed(2)}% HP`, `≈ ${(lost / r.party).toFixed(1)} s of kill time at their ${kfmt(rdps)} rDPS${fits != null ? ` · budget fits ${fits.toFixed(1)}` : bud ? " · no mistake budget" : ""}`];
}

// potential gain against the clears as a share of their DPS: rotation checks with a cost added up; abilities net
// (casting more of one skill usually means fewer of another, so surpluses offset shortfalls). The two overlap (a GCD
// gap is also missing casts), so they are graded apart, never added
const rotGain = r => r && r.dps ? sum(r.checks.map(c => c.cost > 1 ? c.cost : 0)) / r.dps : null;
const abGain = r => r && r.dps && (r.abilities || []).length ? Math.max(0, sum(r.abilities.map(a => a.worth || 0))) / r.dps : null;
const gainGrade = v => v == null ? null : v < 0.05 ? "good" : v < 0.15 ? "ok" : "bad";
const gainTitle = (text, v) => el("span", {}, text, gradeChip(gainGrade(v)));
const gainNote = (v, what) => v == null ? "" : ` Potential gain ${(100 * v).toFixed(1)}% of their DPS (${what}; green under 5%, yellow under 15%).`;

function findGroup(day, group) { return reports().find(r => r.day === day && r.group === group); }

// ---------- tooltip ----------
const tip = () => document.getElementById("tip");
function showTip(evt, title, rows) {
  const t = tip(); t.replaceChildren();
  if (title) t.append(el("div", { class: "t-title" }, title));
  // key: true for the series line, or a mark's name ("k-box", "k-ceil", ...: style.css) drawn as the chart draws it
  for (const [value, label, key] of rows) t.append(el("div", { class: "t-row" }, key ? el("i", { class: key === true ? "t-key" : `t-key ${key}` }) : null, el("b", {}, value), label ? el("span", {}, label) : null));
  t.hidden = false;
  const x = evt.clientX + 14, y = evt.clientY + 14, w = t.offsetWidth, h = t.offsetHeight;
  t.style.left = `${Math.min(x, innerWidth - w - 8)}px`; t.style.top = `${y + h > innerHeight ? evt.clientY - h - 10 : y}px`;
}
function hideTip() { tip().hidden = true; }
function hover(node, title, rows) {
  node.setAttribute("tabindex", "0");
  const on = e => { showTip(e.clientX != null ? e : { clientX: node.getBoundingClientRect().right, clientY: node.getBoundingClientRect().top }, title, rows); };
  node.addEventListener("pointermove", on); node.addEventListener("focus", on);
  node.addEventListener("pointerleave", hideTip); node.addEventListener("blur", hideTip);
}

// ---------- explanations behind a "?" button ----------
function help(text) {
  const b = el("button", { type: "button", class: "help", "aria-label": "Explain" }, "?", el("span", { class: "sr-only" }, text));
  const show = () => { const r = b.getBoundingClientRect(); const t = tip(); t.replaceChildren(el("div", { class: "t-text" }, text)); t.hidden = false;
    const w = t.offsetWidth, h = t.offsetHeight; t.style.left = `${Math.max(8, Math.min(r.left, innerWidth - w - 8))}px`;
    t.style.top = `${r.bottom + 8 + h > innerHeight ? r.top - h - 8 : r.bottom + 8}px`; };
  b.addEventListener("pointerenter", show); b.addEventListener("focus", show); b.addEventListener("click", show);
  b.addEventListener("pointerleave", () => { if (document.activeElement !== b) hideTip(); }); b.addEventListener("blur", hideTip);
  return b;
}
const heading = (tag, title, text) => el(tag, {}, title, help(text));
const info = text => ({ info: text });     // a card caption that goes behind the card title's "?" instead of under it

// ---------- progress: burndown, where pulls end, issues over time ----------
// the mechanics a pull can reach, from the benchmark's checkpoints (name, start s)
// mechanics and phase windows no pull of ours has reached yet are left out of the charts until one does
const FURTHEST = new WeakMap();
const furthest = () => { const rs = DATA.reports || {};
  if (!FURTHEST.has(rs)) FURTHEST.set(rs, Math.max(0, ...Object.values(rs).flatMap(r => r.pulls.map(p => p.kill ? Infinity : p.dur))));
  return FURTHEST.get(rs); };
const seenCps = () => DATA.benchmark.hp_checkpoints.mechanics.filter(m => m.start_s <= furthest());
const seenWindows = () => DATA.benchmark.windows.filter(w => w.start <= furthest());
const reachMechs = () => seenCps().map(m => ({ name: m.mechanic, t: m.start_s }));
// every pull of every group, in the order they were played (groups mix players, so there is one burndown)
const allPulls = () => reports().flatMap(r => r.pulls.map(p => ({ ...p, day: r.day, group: r.group })))
  .sort((a, c) => (a.at || 0) - (c.at || 0) || a.day.localeCompare(c.day) || a.n - c.n);

// burndown: every pull's boss HP at its end (thin line) and the best so far (steps); dotted lines where a mechanic was
// first reached; pulls with The Echo are drawn but do not count for the best line
function burndownChart(pulls) {
  return width => {
    const H = 300, L = 44, R = 16, T = 26, B = 30, w = width - L - R, h = H - T - B, n = pulls.length;
    const X = i => L + (n <= 1 ? w / 2 : (i * w) / (n - 1)), Y = v => T + h - (v / 100) * h;
    const svg = sv("svg", { viewBox: `0 0 ${width} ${H}`, role: "img" });
    for (const v of [0, 25, 50, 75, 100]) svg.append(sv("line", { class: "gridline", x1: L, x2: L + w, y1: Y(v), y2: Y(v) }),
      sv("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end" }, String(v)));
    const mechs = reachMechs(), seen = new Set();
    pulls.forEach((p, i) => { for (const m of mechs) if (!seen.has(m.name) && p.dur >= m.t) { seen.add(m.name);
      svg.append(sv("line", { class: "milestone", x1: X(i), x2: X(i), y1: T, y2: T + h }), sv("text", { class: "lbl", x: X(i) + 3, y: T - 8 }, shortMech(m.name))); } });
    const hp = p => p.boss != null ? p.boss : 100;
    svg.append(sv("polyline", { class: "bd-pulls", points: pulls.map((p, i) => `${X(i)},${Y(hp(p))}`).join(" ") }));
    let best = 100; const steps = [];
    pulls.forEach((p, i) => { if (!p.echo && hp(p) < best) { if (steps.length) steps.push(`${X(i)},${Y(best)}`); best = hp(p); } steps.push(`${X(i)},${Y(best)}`); });
    svg.append(sv("polyline", { class: "bd-best", points: steps.join(" ") }));
    const step = Math.max(1, Math.round(n / 8 / 50) * 50 || Math.ceil(n / 8));
    for (let k = 0; k < n; k += step) svg.append(sv("text", { x: X(k), y: H - 8, "text-anchor": "middle" }, String(k + 1)));
    svg.append(sv("text", { x: X(n - 1), y: H - 8, "text-anchor": "end" }, String(n)));
    const band = w / Math.max(1, n);
    pulls.forEach((p, i) => { const hit = sv("rect", { class: "hit", x: X(i) - band / 2, y: T, width: Math.max(band, 3), height: h });
      hover(hit, `${dayName(p.day)} · ${p.group} · pull ${i + 1} (${p.n} in the group that night)`, [[`${hp(p).toFixed(2)}%`, p.kill ? "kill" : "boss HP left", true],
        [mmss(p.dur), p.kill ? "" : p.wipe && p.wipe.label || "wipe"], ...(p.echo ? [["Echo", "not counted for the best line"]] : [])]);
      svg.append(hit); });
    return svg;
  };
}
const shortMech = m => m.replace("Superchain II (1st)", "SC IIA").replace("Superchain II (2nd)", "SC IIB").replace("Superchain I", "SC I")
  .replace("Paradeigma ", "Para ").replace("Palladion", "Palladion");

// how far pulls got: per mechanic the pulls that reached it, and where the others ended
function reachRows(pulls) {
  const mechs = reachMechs(), n = pulls.length;
  const seg = mechs.map((m, i) => ({ name: i ? `${mechs[i - 1].name} to ${m.name}` : `Before ${m.name}`, end: 0 }));
  seg.push({ name: `${mechs[mechs.length - 1].name} onwards`, end: 0 });
  for (const p of pulls) { const k = mechs.filter(m => p.dur >= m.t).length; seg[k].end++; }
  return { reach: mechs.map(m => ({ name: m.name, n: pulls.filter(p => p.dur >= m.t).length, share: n ? pulls.filter(p => p.dur >= m.t).length / n : 0 })), seg, n };
}

// sequential heatmap (share 0..1 in each cell, printed)
function seqHeatmap(rowLabels, colLabels, cell) {
  return width => {
    const lab = Math.min(150, width * 0.28), head = 22, rh = 26, cw = Math.max(52, Math.min(96, (width - lab) / colLabels.length));
    const H = head + rowLabels.length * rh + 4, Wd = lab + cw * colLabels.length;
    const svg = sv("svg", { viewBox: `0 0 ${Math.max(width, Wd)} ${H}`, role: "img" });
    colLabels.forEach((c, k) => svg.append(sv("text", { x: lab + k * cw + cw / 2, y: 14, "text-anchor": "middle" }, c)));
    rowLabels.forEach((r, i) => {
      svg.append(sv("text", { class: "lbl", x: lab - 8, y: head + i * rh + rh / 2 + 4, "text-anchor": "end" }, r));
      colLabels.forEach((c, k) => { const x = cell(i, k); if (x == null) return;
        const a = 0.12 + 0.78 * x.v;
        const rect = sv("rect", { x: lab + k * cw + 1, y: head + i * rh + 1, width: cw - 2, height: rh - 2, rx: 3, fill: "var(--series)", "fill-opacity": a });
        hover(rect, `${r} · ${c}`, [[x.text, x.sub || "", true]]);
        // inline style: the chart stylesheet's text colour would beat a fill attribute
        svg.append(rect, sv("text", { x: lab + k * cw + cw / 2, y: head + i * rh + rh / 2 + 4, "text-anchor": "middle", "font-weight": 600,
          style: `fill:${darkTheme() ? "#ffffff" : bestInk(blend("--surface", "--series", a))}` }, x.text)); });
    });
    return svg;
  };
}

// clean through each mechanic: of the pulls that entered a phase window with nobody dead or with Damage Down,
// the share that also left it clean (first death or Damage Down after the window, and the pull lasted past it)
const shortWin = n => n.replace("Opener & ", "").replace(" & Dialogos", "").replace(" & Ultima Blade", "").replace(" & Theos's Ultima", "")
  .replace("Paradeigma ", "Para ").replace("Superchain ", "SC ");
function cleanThrough(pulls) {
  return seenWindows().map(w => {
    const entered = pulls.filter(p => p.first >= w.start && (p.dur >= w.start || p.kill));
    const left = entered.filter(p => p.first >= w.end && (p.dur >= w.end || p.kill));
    return { name: w.name, entered: entered.length, left: left.length, share: entered.length ? left.length / entered.length : null };
  });
}

// one bar per row (share 0..1), with a marker for a reference share (e.g. earlier days)
function shareBars(rows, { refName = "", barName = "" } = {}) {
  return width => {
    const H = 190, L = 36, R = 8, T = 22, B = 30, w = width - L - R, h = H - T - B;
    const band = w / rows.length, bw = Math.min(34, band * 0.6), Y = v => T + h - v * h;
    const svg = sv("svg", { viewBox: `0 0 ${width} ${H}`, role: "img" });
    for (const v of [0, 0.25, 0.5, 0.75, 1]) svg.append(sv("line", { class: "gridline", x1: L, x2: L + w, y1: Y(v), y2: Y(v) }),
      sv("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end" }, pct(v)));
    rows.forEach((r, i) => {
      const x = L + i * band + (band - bw) / 2;
      if (r.v != null) svg.append(sv("rect", { class: "mark", x, y: Y(r.v), width: bw, height: Math.max(1, Y(0) - Y(r.v)), rx: 3, fill: "var(--series)" }),
        sv("text", { class: "val", x: x + bw / 2, y: Y(r.v) - 5, "text-anchor": "middle" }, pct(r.v)));
      else svg.append(sv("text", { x: x + bw / 2, y: Y(0) - 5, "text-anchor": "middle" }, "–"));
      if (r.ref != null) svg.append(sv("line", { class: "ref-mark", x1: x - 4, x2: x + bw + 4, y1: Y(r.ref), y2: Y(r.ref) }));
      svg.append(sv("text", { x: L + i * band + band / 2, y: H - 10, "text-anchor": "middle" }, r.label));
      const hit = sv("rect", { class: "hit", x: L + i * band, y: T, width: band, height: h });
      hover(hit, r.name || r.label, r.tip || []); svg.append(hit);
    });
    svg.append(sv("rect", { x: L, y: 4, width: 12, height: 10, rx: 2, fill: "var(--series)" }), sv("text", { class: "lbl", x: L + 18, y: 13 }, barName),
      sv("line", { class: "ref-mark", x1: L + 130, x2: L + 148, y1: 9, y2: 9 }), sv("text", { class: "lbl", x: L + 154, y: 13 }, refName));
    return svg;
  };
}

// ---------- practice links and focus lists ----------
// the trainer's drills and briefs (the repository root on GitHub Pages; this site lives in stats/), open mechanics only
const DRILLS = { "Paradeigma I": "para1", "Paradeigma II": "engrave", "Superchain I": "superchain", "Paradeigma III": "para3" };
const drillLinks = mech => DRILLS[mech] ? el("span", { class: "drill" }, el("a", { href: `../index.html#${DRILLS[mech]}` }, "Drill"), " · ",
  el("a", { href: `../briefs.html#${DRILLS[mech]}` }, "Brief")) : null;
const jumpTo = (title, text) => el("button", { type: "button", class: "linklike", on: { click: () => {
  const h = [...document.querySelectorAll("h2")].find(x => x.textContent.startsWith(title)); if (h) h.scrollIntoView({ behavior: "smooth" }); } } }, text || `See ${title}`);
const secs1 = v => `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(1)} s`;
const opRef = o => o && o.source === "groups" ? { who: "our other players", whose: "our groups'", short: "groups" } : { who: "clearers", whose: "the clears'", short: "clears" };
const burstName = k => k === 1 ? "opener burst" : `${2 * (k - 1)}:00 burst`;
const checkRate = c => c.unit === "s" ? `${c.ours.toFixed(1)} s/min vs ${c.clears.toFixed(1)}` : c.unit === "times" ? `${(c.ours * 10).toFixed(1)} vs ${(c.clears * 10).toFixed(1)} per 10 min`
  : `${c.ours.toFixed(1)} vs ${c.clears.toFixed(1)} per min`;
// label -> mechanic, from the mistakes recorded in a report's pulls

function focusList(items, empty) {
  if (!items.length) return el("p", { class: "empty" }, empty);
  return el("ol", { class: "focus" }, items.map(x => el("li", {}, el("div", { class: "f-title" }, x.title),
    el("div", { class: "f-detail" }, x.detail), x.links ? el("div", { class: "f-links" }, ...[].concat(x.links).filter(Boolean)) : null)));
}

// what one player should work on, most important first
function playerFocus(r, entries, name) {
  const p = entries[0], info = causeInfo(r), items = [], mech = c => (info[c] || {}).mech;
  const counts = mistakeCounts(r, name);
  const wipes = Object.entries(wipeCounts(r, name)).sort((a, c) => c[1] - a[1]);
  // a wipe can be put on them without a recorded mistake of theirs (their tower went unsoaked), so k can be below n
  const withK = (n, k) => k >= n ? `; ${times(k)} in all.` : k ? `; ${times(k)} as a recorded mistake of theirs, the other ${n - k} put on them without one (an unsoaked tower, say).`
    : `, each put on them without a recorded mistake of theirs (an unsoaked tower, say).`;
  for (const [cause, n] of wipes.slice(0, 2)) if (n >= 2 || n / p.pulls >= 0.1)
    items.push({ title: cause, detail: `Lost ${n} pull${n > 1 ? "s" : ""} (${pct(n / p.pulls)} of theirs)${withK(n, counts[cause] || 0)}`,
      links: [drillLinks(mech(cause)), jumpTo("Every mistake", "See their mistakes")] });
  const listed = new Set(items.map(x => x.title));
  const other = Object.entries(counts).filter(([l]) => !listed.has(l)).sort((a, c) => c[1] - a[1])[0];
  if (other && other[1] >= 3) {
    const lab = (info[other[0]] || {}).label, all = (p.mcauses_all || {})[lab];   // cost is stored per label: this mechanic's share of it
    const hp = all ? ((p.lost_caused_by || {})[lab] || 0) * other[1] / all : null;
    items.push({ title: other[0], detail: `${other[1]} times (${(other[1] / p.pulls).toFixed(2)} per pull)${hp ? `; cost ${hpfmt(hp / p.pulls)} of the boss per pull` : ""}.`,
      links: [drillLinks(mech(other[0])), jumpTo("Every mistake", "See their mistakes")] });
  }
  for (const e of entries) {
    const rot = e.rotation;
    if (!rot) continue;
    for (const c of rot.checks.filter(c => c.cost >= 40).slice(0, 2))
      items.push({ title: `${JOB[e.job] || e.job}: ${c.label}`, detail: `${checkRate(c)} for clearers; worth about ${num(Math.round(c.cost))} DPS.`, links: jumpTo("Rotation") });
    const o = rot.opener;
    if (o && o.dmg && o.dmg.vs <= -0.05) {
      const miss = o.skills.filter(s => s.fewer).map(s => s.name), late = o.skills.filter(s => s.late != null && s.late > 0).map(s => s.name);
      items.push({ title: `${JOB[e.job] || e.job} opener`, detail: `${signed(o.dmg.vs)} damage against ${opRef(o).who} over 0:00–0:20${miss.length ? `; fewer ${miss.join(", ")} than ${opRef(o).whose} opener` : ""}${late.length ? `; ${late.join(", ")} late` : ""}.`, links: jumpTo("Opener") });
    }
  }
  for (const b of (r.burst ? r.burst.buffs : []).filter(b => b.player === name && ((b.delay || 0) >= 1.5 || b.skipped >= 2)))
    items.push({ title: `${b.buff} in the ${burstName(b.burst)}`, detail: [b.delay != null && b.delay >= 1.5 ? `${secs1(b.delay)} later than the clears` : null,
      b.skipped >= 2 ? `skipped ${b.skipped}× while alive` : null].filter(Boolean).join("; ") + ".", links: jumpTo("Burst", "See the group's burst") });
  return items.slice(0, 5);
}

// what a raid leader should look at first in one group's night
function groupFocus(r) {
  const info = causeInfo(r), items = [], names = [...new Set(r.players.map(p => p.name))];
  const pw = Object.fromEntries(names.map(n => [n, wipeCounts(r, n)])), pm = Object.fromEntries(names.map(n => [n, mistakeCounts(r, n)]));
  const by = (counts, cause) => names.map(n => [n, counts[n][cause] || 0]).filter(x => x[1]).sort((a, c) => c[1] - a[1]);
  // wipes nobody is blamed for yet give a raid leader nothing to act on: the two most frequent blamed causes
  const blamed = ([cause]) => !UNBLAMED.test(((info[cause] || {}).label) || cause);
  for (const [cause, n] of Object.entries(wipeCounts(r)).filter(blamed).sort((a, c) => c[1] - a[1]).slice(0, 2)) {
    const w = by(pw, cause);
    items.push({ title: cause, detail: `Ended ${n} of ${r.pulls_total} pulls${w.length ? `: ${w.slice(0, 3).map(([n2, k]) => `${n2} ${k}`).join(", ")}` : ""}.`, links: drillLinks((info[cause] || {}).mech) });
  }
  const top = Object.entries(mistakeCounts(r)).sort((a, c) => c[1] - a[1])[0];
  if (top && !items.some(x => x.title === top[0])) {
    const w = by(pm, top[0]);
    items.push({ title: `Most common mistake: ${top[0]}`, detail: `${top[1]} times${w.length ? `: ${w.slice(0, 3).map(([n2, k]) => `${n2} ${k}`).join(", ")}` : ""}.`, links: drillLinks((info[top[0]] || {}).mech) });
  }
  const rot = r.players.flatMap(p => (p.rotation ? p.rotation.checks : []).filter(c => c.cost >= 80).map(c => ({ p, c }))).sort((a, c) => c.c.cost - a.c.cost).slice(0, 3);
  if (rot.length) items.push({ title: "Biggest rotation losses", detail: rot.map(({ p, c }) => `${p.name} (${JOB[p.job] || p.job}): ${c.label}, about ${num(Math.round(c.cost))} DPS`).join("; ") + ".", links: jumpTo("Rotation") });
  const late = (r.burst ? r.burst.buffs : []).filter(b => (b.delay || 0) >= 1.5 || b.skipped >= 2).sort((a, c) => (c.delay || 0) - (a.delay || 0))[0];
  if (late) items.push({ title: "Burst alignment", detail: `${late.player}'s ${late.buff} in the ${burstName(late.burst)}: ${late.delay != null ? `${secs1(late.delay)} later than the clears` : ""}${late.skipped >= 2 ? `${late.delay != null ? ", " : ""}skipped ${late.skipped}×` : ""}.`, links: jumpTo("Burst") });
  const weak = r.players.filter(p => p.rotation && p.rotation.opener && p.rotation.opener.dmg && p.rotation.opener.dmg.vs <= -0.08);
  if (weak.length) items.push({ title: "Openers", detail: weak.map(p => `${p.name} (${JOB[p.job] || p.job}) ${signed(p.rotation.opener.dmg.vs)}${p.rotation.opener.source === "groups" ? " against our other players" : ""}`).join(", ") + " against clearers over 0:00–0:20.", links: null });
  return items;
}

// ---------- chart frame: a card with a title, caption, legend and a table-view twin ----------
function card(title, caption, draw, table, legend) {
  const body = el("div", { class: "chart" });
  const tbl = el("div", { class: "table-wrap", hidden: true });
  const btn = el("button", { type: "button", "aria-pressed": "false" }, "Table");
  btn.addEventListener("click", () => {
    const on = tbl.hidden; tbl.hidden = !on; body.hidden = on; btn.textContent = on ? "Chart" : "Table"; btn.setAttribute("aria-pressed", String(on));
    if (on && !tbl.firstChild) tbl.append(table());
  });
  const hidden = caption && caption.info;
  const f = el("figure", { class: "card" }, el("div", { class: "card-head" }, el("h3", {}, title, hidden ? help(caption.info) : null), btn),
    caption && !hidden ? el("figcaption", {}, caption) : null, body,
    legend ? el("div", { class: "legend" }, legend) : null, tbl);
  requestAnimationFrame(() => { body.append(draw(Math.max(260, body.clientWidth || 360))); });
  return f;
}
// player names, comma-separated: a table cell may break the line after a comma but never inside a name
const names = list => el("span", { class: "names" }, list.flatMap((n, i) => [i ? ", " : "", el("span", { class: "nm" }, n)]));
function tableOf(head, rows, numericFrom = 1) {   // numericFrom: first numeric column, or a list of them
  const isNum = i => Array.isArray(numericFrom) ? numericFrom.includes(i) : i >= numericFrom;
  return el("table", {}, el("thead", {}, el("tr", {}, head.map((h, i) => el("th", { class: isNum(i) ? "num" : null }, h)))),
    el("tbody", {}, rows.map(r => el("tr", {}, r.map((c, i) => el("td", { class: isNum(i) ? "num" : null }, c))))));
}
const clip = (text, px) => { const n = Math.max(4, Math.floor(px / 6)); return text.length > n ? text.slice(0, n - 1) + "…" : text; };
function niceMax(v) { const p = Math.pow(10, Math.floor(Math.log10(v || 1))); for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p; return 10 * p; }
function ticks(max, n = 4) { const step = max / n; return Array.from({ length: n + 1 }, (_, i) => i * step); }

// line chart, one series over raid days (x = categories)
// a strategy date's short note: its mechanics ("Para I/II, Glaukopis strategy"), Glaukopis / Ultima Blade as Glaukopis
const strategyLabel = s => { const ns = [...new Set(s.mechanics.map(m => shortMech(m.split(" / ")[0])))], paras = ns.filter(m => m.startsWith("Para "));
  const names = [...(paras.length > 1 ? [`Para ${paras.map(m => m.slice(5)).join("/")}`] : paras), ...ns.filter(m => !m.startsWith("Para "))];
  return `${names.join(", ")} ${s.kind === "added" ? "strategy" : "changed"}`; };
const STRATEGY_NOTE = " Dashed vertical lines: from that raid day a mechanic's strategy is blamed; before it, only standing in avoidable hits is.";
// dated: points carry their raid day (p.day), and each strategy date (DATA.strategies) between two of them gets a dashed line
function lineChart(points, { yFmt = v => v, yMax, yMin = 0, invert = false, refs = [], second = null, name = null, extra = [], dated = false } = {}) {
  return width => {
    const legend = second || extra.length;
    const H = legend ? 186 : 170, L = 44, R = second ? 44 : refs.length ? 64 : 16, T = legend ? 28 : 12, B = 26, w = width - L - R, h = H - T - B;
    const vals = points.map(p => p.y).filter(v => v != null);
    const top = yMax ?? niceMax(Math.max(...vals, ...refs.map(r => r.value), ...extra.flatMap(x => x.points.map(p => p.y)).filter(v => v != null)) * 1.1), lo = yMin;
    const X = i => L + (points.length === 1 ? w / 2 : (i * w) / (points.length - 1));
    const Y = v => invert ? T + ((v - lo) / (top - lo)) * h : T + h - ((v - lo) / (top - lo)) * h;
    const svg = sv("svg", { viewBox: `0 0 ${width} ${H}`, role: "img" });
    for (const t of ticks(top - lo)) { const v = lo + t; svg.append(sv("line", { class: "gridline", x1: L, x2: L + w, y1: Y(v), y2: Y(v) }), sv("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end" }, yFmt(v))); }
    const n = points.length;
    const room = Math.max(85, 6.5 * Math.max(...points.map(p => String(p.x).length)) + 14);   // px per label, wider for long labels
    const every = Math.max(1, Math.ceil(n * room / Math.max(1, w)));
    points.forEach((p, i) => { if (i !== n - 1 && (i % every || X(n - 1) - X(i) < room)) return;   // keep clear of the last label
      svg.append(sv("text", { x: X(i), y: H - 6, "text-anchor": n > 1 && i === 0 ? "start" : n > 1 && i === n - 1 ? "end" : "middle" }, p.x)); });
    if (dated && n > 1) {   // strategy dates, midway between the raid days around them; notes that would overlap step down a row
      let end = -Infinity, row = 0;
      for (const st of DATA.strategies || []) {
        const i = points.findIndex(p => p.day >= st.day);
        if (i < 1) continue;
        const x = (X(i - 1) + X(i)) / 2, text = strategyLabel(st), tw = text.length * 6, flip = x + 4 + tw > L + w;
        row = (flip ? x - 4 - tw : x + 4) < end + 6 ? row + 1 : 0;
        svg.append(sv("line", { class: "strategy", x1: x, x2: x, y1: T, y2: T + h }),
          sv("text", { class: "lbl strategy", x: flip ? x - 4 : x + 4, y: T + 11 + row * 12, "text-anchor": flip ? "end" : "start" }, text));
        end = flip ? x : x + 4 + tw;
        const hit = sv("rect", { class: "hit", x: x - 5, y: T, width: 10, height: h });
        hover(hit, `From ${dayName(st.day)}`, [[st.kind === "added" ? "strategy blamed" : "strategy changed", st.mechanics.join(", "), true]]);
        svg.append(hit);
      }
    }
    const placed = [];   // reference labels: nudge apart when the lines are close
    const refY = r => { let y = Y(r.value); while (placed.some(q => Math.abs(q - y) < 11)) y -= 11; placed.push(y); return y; };
    for (const r of refs) svg.append(sv("line", { class: `ref ${r.cls || ""}`, x1: L, x2: L + w, y1: Y(r.value), y2: Y(r.value), "stroke-opacity": 0.6 }),
      sv("text", { class: `lbl ${r.cls || ""}`, x: L + w + 4, y: refY(r) + 4 }, r.label));
    const pts = points.map((p, i) => p.y == null ? null : [X(i), Y(p.y)]).filter(Boolean);
    if (pts.length > 1) svg.append(sv("polyline", { points: pts.map(p => p.join(",")).join(" "), fill: "none", stroke: "var(--series)", "stroke-width": 2, "stroke-linejoin": "round", "stroke-linecap": "round" }));
    points.forEach((p, i) => {
      if (p.y == null) return;
      const c = sv("circle", { class: "mark", cx: X(i), cy: Y(p.y), r: 4.5, fill: "var(--series)", stroke: "var(--surface)", "stroke-width": 2 });
      const hit = sv("rect", { class: "hit", x: X(i) - 14, y: T, width: 28, height: h });
      hover(hit, p.x, [[yFmt(p.y), p.label || "", true]]);
      svg.append(hit, c);
    });
    const last = points.length - 1;   // label the latest value only
    if (points[last].y != null) svg.append(sv("text", { class: "val", x: X(last), y: Y(points[last].y) - 10, "text-anchor": points.length > 1 ? "end" : "middle" }, yFmt(points[last].y)));
    if (extra.length) {   // more series on the same axis: thinner, dashed, with a legend
      extra.forEach((x, k) => {
        const p2 = x.points.map((p, i) => p.y == null ? null : [X(i), Y(p.y)]).filter(Boolean);
        if (p2.length > 1) svg.append(sv("polyline", { class: `extra ${x.cls || ""}`, points: p2.map(p => p.join(",")).join(" "), ...(x.color ? { stroke: x.color } : {}) }));
        x.points.forEach((p, i) => { if (p.y == null) return; svg.append(sv("circle", { class: `mark-extra ${x.cls || ""}`, cx: X(i), cy: Y(p.y), r: 3, ...(x.color ? { fill: x.color } : {}) })); });
      });
      points.forEach((p, i) => { const hit = sv("rect", { class: "hit", x: X(i) - 14, y: T, width: 28, height: h });
        hover(hit, p.x, [[p.y != null ? yFmt(p.y) : "–", name || "", true], ...extra.map(x => [x.points[i].y != null ? yFmt(x.points[i].y) : "–", x.name])]); svg.append(hit); });
      let lx = L;
      for (const [label, cls, dashed, color] of [[name || "", "", false], ...extra.map(x => [x.name, x.cls || "", true, x.color])]) {
        svg.append(sv("line", { class: dashed ? `extra ${cls}` : null, x1: lx, x2: lx + 18, y1: 10, y2: 10, ...(dashed ? (color ? { stroke: color } : {}) : { stroke: "var(--series)", "stroke-width": 2 }) }),
          sv("text", { class: "lbl", x: lx + 24, y: 14 }, label));
        lx += 34 + label.length * 6.2;
      }
    }
    if (second) {   // a second series in other units: dashed, hollow points, its own axis on the right, and a legend
      const v2 = second.points.map(p => p.y).filter(v => v != null), top2 = niceMax(Math.max(...v2) * 1.1);
      const Y2 = v => T + h - (v / top2) * h, fmt2 = second.yFmt || (v => v);
      // the right axis shares the left one's gridlines, so its ticks can be uneven (0.125): print them without rounding
      for (const t of ticks(top2)) svg.append(sv("text", { x: L + w + 6, y: Y2(t) + 4, "text-anchor": "start", class: "second" }, String(+t.toFixed(3))));
      const p2 = second.points.map((p, i) => p.y == null ? null : [X(i), Y2(p.y)]).filter(Boolean);
      if (p2.length > 1) svg.append(sv("polyline", { class: "series2", points: p2.map(p => p.join(",")).join(" ") }));
      second.points.forEach((p, i) => { if (p.y == null) return;
        const c = sv("circle", { class: "mark2", cx: X(i), cy: Y2(p.y), r: 4 }); const hit = sv("rect", { class: "hit", x: X(i) - 14, y: T, width: 28, height: h });
        hover(hit, p.x, [[yFmt(points[i].y), name || "", true], [fmt2(p.y), second.name || ""]]); svg.append(c, hit); });
      svg.append(sv("line", { x1: L, x2: L + 18, y1: 10, y2: 10, stroke: "var(--series)", "stroke-width": 2 }), sv("text", { class: "lbl", x: L + 24, y: 14 }, name || ""),
        sv("line", { class: "series2", x1: L + 150, x2: L + 168, y1: 10, y2: 10 }), sv("text", { class: "lbl", x: L + 174, y: 14 }, `${second.name || ""} (right axis)`));
    }
    return svg;
  };
}

// columns (one series), with optional horizontal reference lines
function columnChart(bars, { yFmt = v => v, yMax, refs = [], barTip, tickStep, onBar } = {}) {
  return width => {
    const H = 220, L = 44, R = 70, T = 12, B = 26, w = width - L - R, h = H - T - B;
    const raw = Math.max(...bars.map(b => Math.max(b.value, b.mark ?? 0)), ...refs.map(r => r.value)) * 1.05;
    const top = yMax ?? (tickStep ? Math.ceil(raw / tickStep) * tickStep : niceMax(raw));
    const band = w / Math.max(1, bars.length), bw = Math.min(24, band - 2);
    const Y = v => T + h - (v / top) * h;
    const svg = sv("svg", { viewBox: `0 0 ${width} ${H}`, role: "img" });
    const tks = tickStep ? Array.from({ length: Math.round(top / tickStep) + 1 }, (_, i) => i * tickStep) : ticks(top);
    for (const v of tks) svg.append(sv("line", { class: "gridline", x1: L, x2: L + w, y1: Y(v), y2: Y(v) }), sv("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end" }, yFmt(v)));
    bars.forEach((b, i) => {
      const x = L + i * band + (band - bw) / 2, y = Y(b.value), bh = Math.max(1, T + h - y);
      const r = Math.min(4, bw / 2, bh);
      const path = `M${x},${T + h} V${y + r} Q${x},${y} ${x + r},${y} H${x + bw - r} Q${x + bw},${y} ${x + bw},${y + r} V${T + h} Z`;
      const hit = sv("rect", { class: "hit", x: L + i * band, y: T, width: band, height: h });
      const m = sv("path", { class: "mark", d: path, fill: b.color || "var(--series)" });
      if (barTip) hover(hit, ...barTip(b)); else hover(hit, b.label, [[yFmt(b.value), "", true]]);
      if (onBar) { hit.style.cursor = "pointer"; hit.addEventListener("click", () => onBar(b)); }
      svg.append(hit, m);
      if (b.mark != null) svg.append(sv("line", { class: "barmark", x1: L + i * band + 1, x2: L + (i + 1) * band - 1, y1: Y(b.mark), y2: Y(b.mark) }));   // a per-bar target
      if (bars.length <= 16 || i % Math.ceil(bars.length / 16) === 0) svg.append(sv("text", { x: x + bw / 2, y: H - 8, "text-anchor": "middle" }, b.label));
    });
    svg.append(sv("line", { class: "axisline", x1: L, x2: L + w, y1: T + h, y2: T + h }));
    for (const r of refs) {   // labelled reference lines (mechanic start times, benchmarks)
      if (r.value > top) continue;
      svg.append(sv("line", { class: "ref", x1: L, x2: L + w, y1: Y(r.value), y2: Y(r.value), "stroke-opacity": 0.6 }),
        sv("text", { class: "lbl", x: L + w + 4, y: Y(r.value) + 4 }, r.label));
    }
    return svg;
  };
}

// horizontal bars (one series), label left, value at the tip
// one stacked bar per row (rows: {label, values: [a, b, ...]}), a segment per series ({name, color}), legend on top;
// the number is the row's total, the split is in the hover
function hbarStackChart(rows, series, { fmt = v => v } = {}) {
  return width => {
    const lab = Math.min(260, width * 0.48), R = 40, row = 24, T = 22, H = T + rows.length * row + 6, w = width - lab - R, bh = 14;
    const max = Math.max(1, ...rows.map(r => sum(r.values)));
    const svg = sv("svg", { viewBox: `0 0 ${width} ${H}`, role: "img" });
    const legendW = sum(series.map(s => 30 + s.name.length * 6.5));
    let lx = Math.max(0, Math.min(lab, width - legendW));   // start over the bars, further left when narrow
    series.forEach(s => { svg.append(sv("rect", { x: lx, y: 5, width: 12, height: 10, rx: 2, fill: s.color }), sv("text", { class: "lbl", x: lx + 18, y: 14 }, s.name)); lx += 30 + s.name.length * 6.5; });
    rows.forEach((r, i) => {
      const y = T + i * row, yy = y + (row - bh) / 2, total = sum(r.values);
      svg.append(sv("text", { class: "lbl", x: lab - 8, y: y + row / 2 + 4, "text-anchor": "end" }, clip(r.label, lab - 12)));
      const hit = sv("rect", { class: "hit", x: 0, y, width, height: row });
      hover(hit, r.label, [[fmt(total), "in total", true], ...series.map((s, k) => [fmt(r.values[k]), s.name])]);
      let x = lab;
      series.forEach((s, k) => { const v = r.values[k]; if (!(v > 0)) return;
        const bw = Math.max(2, (v / max) * w);
        svg.append(sv("rect", { class: "mark", x, y: yy, width: bw, height: bh, fill: s.color })); x += bw; });
      svg.append(hit, sv("text", { class: "val", x: x + 6, y: y + row / 2 + 4 }, fmt(total)));
    });
    return svg;
  };
}
// "What happened" for a mistake or death: a chained cause (the classifier's trace) as its immediate cause, then, folded,
// the earlier deaths behind it as an indented list, each told once (a death met again says so). who: the culprit a
// column beside it already names, so a cause told with their name first ("X: did not soak ...") drops it
function whatHappened(x, who) {
  const tr = x.trace, own = s => who && s.startsWith(`${who}: `) ? s.slice(who.length + 2) : s;
  if (!tr) return own(x.cause);
  const seen = new Set();
  const by = d => d.by.length === 1 && d.by[0] === d.who ? "their own mistake" : `caused by ${d.by.join(", ")}`;
  const list = node => {
    const items = (node.parts || []).map(part => el("li", {}, part.rule, list(part)));
    for (const d of node.deaths || []) {
      if (seen.has(d.who)) { items.push(el("li", { class: "muted" }, `${d.who} died at ${mmss(d.t)} (told above)`)); continue; }
      seen.add(d.who);
      items.push(el("li", {}, el("b", {}, d.who), ` died at ${mmss(d.t)}, ${by(d)}: ${d.why.rule || `${d.why.parts.length} failures at once`}`, list(d.why)));
    }
    return items.length ? el("ul", { class: "trace" }, items) : null;
  };
  const deaths = new Set(), count = node => { (node.parts || []).forEach(count); (node.deaths || []).forEach(d => { deaths.add(d.who); count(d.why); }); };
  count(tr);
  // several causes of one hit (both towers exploding) are told in the fold, each with the earlier deaths behind it
  const head = own(tr.rule || `${tr.parts.length} failures at once`);
  // with no earlier deaths behind them (a tether laser, then Electrify), the fold holds only the failures themselves
  const fold = deaths.size || !tr.parts ? `how it came about: ${deaths.size} earlier death${deaths.size === 1 ? "" : "s"}` : `the ${tr.parts.length} failures`;
  return el("div", {}, head, el("details", { class: "trace" }, el("summary", {}, fold), list(tr)));
}
// a death in FFLogs: the Deaths view for the one who died, over the whole mechanic it happened in, on to the death when
// that came later (the whole pull when in none); null for a report built before the site kept its start time and actor ids
function deathLink(r, d) {
  const q = r.pulls.find(x => x.n === d.pull), id = (r.actors || {})[d.who];
  if (!q || r.start_ms == null || id == null) return null;
  const lo = DATA.benchmark.mech_start[d.mechanic], hi = (DATA.benchmark.mech_end || {})[d.mechanic], t0 = q.at - r.start_ms;
  const span = hi == null ? "" : `&start=${Math.round(t0 + lo * 1000)}&end=${Math.round(t0 + Math.max(hi, d.t + 5) * 1000)}`;   // d.t is the lethal hit; the death event lands up to 4 s later
  return [el("a", { href: `https://www.fflogs.com/reports/${r.code}?fight=${q.id}&type=deaths&source=${id}${span}`, target: "_blank", rel: "noopener",
    title: `${d.who}'s deaths in ${hi == null ? "the pull" : d.mechanic} on FFLogs` }, "↗"), " "];
}
const KIND_SERIES = [{ name: "Lost the pull", color: "var(--wipe, #9e1f30)" }, { name: "Other deaths", color: "var(--div-neg)" }, { name: "Damage Down", color: "#e0a03a" },
  { name: "Survived", color: "var(--muted)" }];   // deaths and DD as in Damage lost to mistakes; survived: neither (both Superchain lasers on someone who lived)

function hbarChart(rows, { fmt = v => v } = {}) {
  return width => {
    const lab = Math.min(260, width * 0.48), R = 40, row = 24, H = rows.length * row + 6, w = width - lab - R;
    const max = Math.max(1, ...rows.map(r => r.value));
    const svg = sv("svg", { viewBox: `0 0 ${width} ${H}`, role: "img" });
    rows.forEach((r, i) => {
      const y = 3 + i * row, bw = Math.max(2, (r.value / max) * w), bh = 14, yy = y + (row - bh) / 2, rad = Math.min(4, bw);
      svg.append(sv("text", { class: "lbl", x: lab - 8, y: y + row / 2 + 4, "text-anchor": "end" }, clip(r.label, lab - 12)));
      const hit = sv("rect", { class: "hit", x: 0, y, width, height: row });
      const m = sv("path", { class: "mark", fill: "var(--series)", d: `M${lab},${yy} H${lab + bw - rad} Q${lab + bw},${yy} ${lab + bw},${yy + rad} V${yy + bh - rad} Q${lab + bw},${yy + bh} ${lab + bw - rad},${yy + bh} H${lab} Z` });
      hover(hit, r.label, r.tip || [[fmt(r.value), r.sub || "", true]]);
      svg.append(hit, m, sv("text", { class: "val", x: lab + bw + 6, y: y + row / 2 + 4 }, fmt(r.value)));
    });
    return svg;
  };
}

// heatmap of counts: rows x columns, one-hue ramp, the count printed in every non-empty cell
function heatmap(rowLabels, colLabels, cell) {
  return width => {
    const lab = Math.min(300, width * 0.45), head = 26, rh = 24, cw = Math.max(34, Math.min(74, (width - lab) / colLabels.length));
    const H = head + rowLabels.length * rh + 4, Wd = lab + cw * colLabels.length;
    const vals = rowLabels.flatMap((_, r) => colLabels.map((_, c) => cell(r, c)));
    const max = Math.max(1, ...vals);
    const svg = sv("svg", { viewBox: `0 0 ${Math.max(width, Wd)} ${H}`, role: "img" });
    const cs = getComputedStyle(document.documentElement);
    const ramp = [0, 1, 2, 3, 4].map(i => cs.getPropertyValue(`--heat-${i}`).trim());
    const lightMode = cs.colorScheme === "light" || document.documentElement.dataset.theme === "light" ||
      (!document.documentElement.dataset.theme && matchMedia("(prefers-color-scheme: light)").matches);
    const fit = Math.max(3, Math.floor((cw - 4) / 6.2));
    colLabels.forEach((c, j) => { const first = c.split(" ")[0];
      svg.append(sv("text", { class: "lbl", x: lab + j * cw + cw / 2, y: 16, "text-anchor": "middle" }, first.length > fit ? first.slice(0, fit - 1) + "…" : first)); });
    rowLabels.forEach((rl, i) => {
      const y = head + i * rh;
      svg.append(sv("text", { class: "lbl", x: lab - 8, y: y + rh / 2 + 4, "text-anchor": "end" }, clip(rl, lab - 12)));
      colLabels.forEach((cl, j) => {
        const v = cell(i, j), x = lab + j * cw;
        if (!v) { svg.append(sv("rect", { x: x + 1, y: y + 1, width: cw - 2, height: rh - 2, rx: 3, fill: "var(--zone)" })); return; }
        const step = Math.min(4, Math.floor((v / max) * 4.999));
        const r = sv("rect", { class: "mark", x: x + 1, y: y + 1, width: cw - 2, height: rh - 2, rx: 3, fill: ramp[step] });
        const dark = lightMode ? step >= 2 : step <= 2;   // white text on the deep steps
        const t = sv("text", { x: x + cw / 2, y: y + rh / 2 + 4, "text-anchor": "middle", style: `fill:${dark ? "#fff" : "#0b0b0b"};font-weight:600` }, String(v));
        const hit = sv("rect", { class: "hit", x, y, width: cw, height: rh });
        hover(hit, `${rl} · ${cl}`, [[String(v), ""]]);
        svg.append(r, t, hit);
      });
    });
    return svg;
  };
}

// diverging colour for a share above/below clearers: grey at par, red below, blue above, saturating at ±limit
function divColor(v, limit = 0.15) {
  const cs = getComputedStyle(document.documentElement);
  const hex = n => cs.getPropertyValue(n).trim().replace("#", "");
  const mix = (a, b, t) => { const p = x => [0, 2, 4].map(i => parseInt(x.slice(i, i + 2), 16)); const A = p(a), B = p(b);
    return "#" + A.map((c, i) => Math.round(c + (B[i] - c) * t).toString(16).padStart(2, "0")).join(""); };
  const t = Math.min(1, Math.abs(v) / limit);
  return mix(hex("--div-mid"), hex(v < 0 ? "--div-neg" : "--div-pos"), t);
}
const inkOn = fill => { const n = parseInt(fill.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
  return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255 > 0.55 ? "#0b0b0b" : "#ffffff"; };

// dark or white text on a background colour, whichever contrasts more (WCAG relative luminance), dark on a near tie
const bestInk = hex => { const n = parseInt(hex.slice(1), 16), lin = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const Lb = 0.2126 * lin(n >> 16) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255);
  return (Lb + 0.05) / 0.0535 >= 0.8 * (1.05 / (Lb + 0.05)) ? "#0b0b0b" : "#ffffff"; };   // dark text wins near a tie: easier to read on bright fills
// dark theme: white text reads best on every fill, bright blue included
const darkTheme = () => bestInk(blend("--surface", "--surface", 0)) === "#ffffff";
// a colour from the theme blended over another, as hex (for computing text contrast on translucent fills)
const blend = (under, over, a) => { const cs = getComputedStyle(document.documentElement), hex = v => cs.getPropertyValue(v).trim().replace("#", "");
  const p = x => [0, 2, 4].map(i => parseInt(x.slice(i, i + 2), 16)), A = p(hex(under)), B = p(hex(over));
  return "#" + A.map((c, i) => Math.round(c + (B[i] - c) * a).toString(16).padStart(2, "0")).join(""); };

// horizontal bars from a zero line: share above or below clearers, one row per phase
const shortCheck = t => !t ? "–" : ({ "GCD gaps: nothing cast": "idle GCD time", "GCD gaps: weaving delayed the GCD": "clipping",
  "GCD gaps: after an interrupted cast": "interrupted casts" })[t] || t;

// one column per pull, up or down from zero, coloured on the diverging scale (invert: positive is bad)
function divColumns(points, { fmt = v => v, limit = 0.15, invert = false } = {}) {
  return width => {
    const H = 200, L = 52, R = 12, T = 10, B = 24, w = width - L - R, h = H - T - B;
    const top = Math.max(1e-9, ...points.filter(p => p.v != null).map(p => Math.abs(p.v))) * 1.1;
    const Y = v => T + h / 2 - (v / top) * (h / 2);
    const band = w / Math.max(1, points.length), bw = Math.max(2, Math.min(18, band - 2));
    const svg = sv("svg", { viewBox: `0 0 ${width} ${H}`, role: "img" });
    for (const v of [top / 1.1, 0, -top / 1.1]) svg.append(sv("line", { class: v ? "gridline" : "axisline", x1: L, x2: L + w, y1: Y(v), y2: Y(v) }),
      sv("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end" }, v ? fmt(v) : "0"));
    points.forEach((p, i) => {
      const x = L + i * band + (band - bw) / 2;
      const hit = sv("rect", { class: "hit", x: L + i * band, y: T, width: band, height: h });
      if (p.tip) hover(hit, ...p.tip);
      svg.append(hit);
      if (p.v == null) svg.append(sv("text", { class: "muted", x: x + bw / 2, y: Y(0) - 4, "text-anchor": "middle", "font-size": 9 }, "·"));
      else { const y0 = Y(0), y1 = Y(p.v); svg.append(sv("rect", { class: "mark", x, y: Math.min(y0, y1), width: bw, height: Math.max(1, Math.abs(y1 - y0)), rx: 2,
        fill: divColor(invert ? -p.v : p.v, limit) })); }
      if (points.length <= 24 || i % Math.ceil(points.length / 24) === 0) svg.append(sv("text", { x: x + bw / 2, y: H - 6, "text-anchor": "middle" }, p.label));
    });
    return svg;
  };
}

function divergingBars(rows, { limit = 0.3, fmt = signed, invert = false, ends = ["← below", "clearers", "above →"] } = {}) {
  return width => {
    const lab = Math.min(210, width * 0.42), R = 52, row = 26, H = rows.length * row + 22, w = width - lab - R;
    const max = Math.max(0.1, ...rows.filter(r => r.v != null).map(r => Math.min(limit, Math.abs(r.v))));
    const half = w / 2 - 44;   // leaves room for the value label at the end of the longest bar
    const X = v => lab + w / 2 + (Math.max(-max, Math.min(max, v)) / max) * half;
    const svg = sv("svg", { viewBox: `0 0 ${width} ${H}`, role: "img" });
    svg.append(sv("line", { class: "axisline", x1: X(0), x2: X(0), y1: 0, y2: H - 18 }),
      sv("text", { x: X(0), y: H - 4, "text-anchor": "middle" }, ends[1]), sv("text", { x: lab, y: H - 4 }, ends[0]), sv("text", { x: lab + w, y: H - 4, "text-anchor": "end" }, ends[2]));
    rows.forEach((r, i) => {
      const y = i * row;
      svg.append(sv("text", { class: "lbl", x: lab - 8, y: y + row / 2 + 4, "text-anchor": "end" }, clip(r.label, lab - 12)));
      if (r.v == null) { svg.append(sv("text", { x: X(0) + 6, y: y + row / 2 + 4 }, r.empty || "no clean sample")); return; }
      const x0 = X(0), x1 = X(r.v), bh = 14, yy = y + (row - bh) / 2;
      const m = sv("rect", { class: "mark", x: Math.min(x0, x1), y: yy, width: Math.max(2, Math.abs(x1 - x0)), height: bh, rx: 3, fill: divColor(invert ? -r.v : r.v, 0.15) });
      const hit = sv("rect", { class: "hit", x: 0, y, width, height: row });
      hover(hit, r.label, r.tip || [[fmt(r.v), "vs clearers"]]);
      svg.append(hit, m, sv("text", { class: "val", x: r.v >= 0 ? x1 + 6 : x1 - 6, y: y + row / 2 + 4, "text-anchor": r.v >= 0 ? "start" : "end" },
        `${fmt(r.v)}${r.thin ? "*" : ""}`));
    });
    return svg;
  };
}

// heatmap of shares above/below clearers: rows x columns, the value printed in every cell
function divHeatmap(rowLabels, colLabels, cell) {
  return width => {
    const lab = Math.min(170, width * 0.3), head = 34, rh = 26, cw = Math.max(46, Math.min(96, (width - lab) / colLabels.length));
    const H = head + rowLabels.length * rh + 4, Wd = lab + cw * colLabels.length;
    const svg = sv("svg", { viewBox: `0 0 ${Math.max(width, Wd)} ${H}`, role: "img" });
    colLabels.forEach((c, j) => { const words = c.split(" "), x = lab + j * cw + cw / 2, fit = Math.floor((cw - 4) / 6);
      svg.append(sv("text", { class: "lbl", x, y: 12, "text-anchor": "middle" }, clip(words[0], cw - 4)));
      if (words.length > 1) svg.append(sv("text", { class: "lbl", x, y: 26, "text-anchor": "middle" }, clip(words.slice(1).join(" "), cw - 4))); });
    rowLabels.forEach((rl, i) => {
      const y = head + i * rh;
      svg.append(sv("text", { class: "lbl", x: lab - 8, y: y + rh / 2 + 4, "text-anchor": "end" }, clip(rl, lab - 12)));
      colLabels.forEach((cl, j) => {
        const c = cell(i, j), x = lab + j * cw;
        if (!c || c.v == null) { svg.append(sv("rect", { x: x + 1, y: y + 1, width: cw - 2, height: rh - 2, rx: 3, fill: "var(--zone)" })); return; }
        const fill = divColor(c.v);
        const hit = sv("rect", { class: "hit", x, y, width: cw, height: rh });
        hover(hit, `${rl} · ${cl}`, c.tip);
        svg.append(sv("rect", { class: "mark", x: x + 1, y: y + 1, width: cw - 2, height: rh - 2, rx: 3, fill }),
          sv("text", { x: x + cw / 2, y: y + rh / 2 + 4, "text-anchor": "middle", style: `fill:${inkOn(fill)};font-weight:600` }, `${signed(c.v)}${c.thin ? "*" : ""}`), hit);
      });
    });
    return svg;
  };
}
const divLegend = () => [
  el("span", {}, el("i", { style: "width:14px;height:10px;border-radius:3px;background:var(--div-neg)" }), "below clearers"),
  el("span", {}, el("i", { style: "width:14px;height:10px;border-radius:3px;background:var(--div-mid)" }), "at par"),
  el("span", {}, el("i", { style: "width:14px;height:10px;border-radius:3px;background:var(--div-pos)" }), "above clearers"),
  el("span", {}, "* only 1–2 clearers on the job"),
];
const phaseTip = ph => [[signed(ph.vs[0]), `vs clearers (${ph.vs[1]} on the job${ph.vs[2] ? ", some with The Echo, damage ÷1.2" : ""})`],
  [num(ph.ndps), "nDPS"], [`${ph.uptime.toFixed(1)}%`, `uptime${ph.uptime_diff != null ? ` (${ph.uptime_diff >= 0 ? "+" : "−"}${Math.abs(ph.uptime_diff).toFixed(1)} vs clearers)` : ""}`],
  [String(ph.n), "clean samples"]];
// most clears skip Paradeigma I's movement with tank invulnerabilities; build_benchmark.py adjusts their first-window nDPS by role
const stratNote = () => {
  const s = (DATA.benchmark.windows[0] || {}).strategy; if (!s) return "";
  const f = Object.entries(s.factors).filter(([, v]) => Math.abs(v - 1) >= 0.005)
    .map(([r, v]) => `${r.toLowerCase()}s ${v >= 1 ? "+" : "−"}${Math.abs((v - 1) * 100).toFixed(1)}%`).join(", ");
  return ` ${s.invuln} of ${s.invuln + s.moving} clears skip Paradeigma I's movement with two tank invulnerabilities and keep casting; ` +
    `in the first phase their values are adjusted to the ${s.moving} clears that move like we do (${f}).`;
};
// the cards of what each player's mistakes cost (player page: "What their mistakes cost"; group page: "What each
// player's mistakes cost"), hidden for now; set true to bring them back
const SHOW_MISTAKE_COST = false;
const MIN_PHASE = 2;   // clean samples a phase needs before it is compared with clearers
const shortPhase = w => w.replace("Opener & Paradeigma I", "Opener & Para I").replace("Paradeigma", "Para").replace(" & Dialogos", "").replace(" & Ultima Blade", "").replace(" & Theos's Ultima", "");

// boss HP at each checkpoint, drawn as points ahead of (left) or behind (right) the Clear pace: the targets run from
// 84% to 10% HP while what matters is a point or two either side of them, so every row shares the Clear line at 0
// hp: one group's checkpoints; or groups, [{ name, hp }]: a block of rows per mechanic, one row per group
function checkpointChart(hp, groups) {
  const cps = seenCps(), list = groups || [{ name: "", hp }], multi = !!groups;
  const rows = cps.flatMap(c => list.map((g, k) => ({ c, g, k })));
  return width => {
    const lab = width < 420 ? 118 : 150, valW = width < 420 ? 70 : 88, rh = multi ? 24 : 30, gap = multi ? 10 : 0, head = 8, w = width - lab - valW;
    const H = head + rows.length * rh + (cps.length - 1) * gap + 34, rowY = i => head + i * rh + Math.floor(i / list.length) * gap + rh / 2;
    const diffs = rows.flatMap(({ c, g }) => (g.hp[c.mechanic] || []).length ? [g.hp[c.mechanic][0] - c.breakeven, median(g.hp[c.mechanic]) - c.breakeven] : []);
    const lo = -Math.max(6, Math.ceil(Math.max(...cps.map(c => c.breakeven - c.comfortable)) + 1), Math.ceil(-Math.min(0, ...diffs)) + 1);
    const hi = Math.min(20, Math.max(6, Math.ceil(Math.max(0, ...diffs)) + 1));
    const X = v => lab + ((Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo)) * w;
    const svg = sv("svg", { viewBox: `0 0 ${width} ${H}`, role: "img" });
    const step = hi - lo > 24 ? 10 : 5;
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step)
      svg.append(sv("line", { class: "gridline", x1: X(v), x2: X(v), y1: head, y2: H - 34 }),
        sv("text", { x: X(v), y: H - 20, "text-anchor": "middle" }, v === 0 ? "Clear" : `${v > 0 ? "+" : "−"}${Math.abs(v)}`));
    svg.append(sv("text", { x: lab, y: H - 4 }, w > 260 ? "← ahead of pace (HP points)" : "← ahead"), sv("text", { x: lab + w, y: H - 4, "text-anchor": "end" }, "behind →"));
    rows.forEach(({ c, g: grp, k }, i) => {
      const y = rowY(i), vals = grp.hp[c.mechanic] || [];
      if (!multi) svg.append(sv("text", { class: "lbl", x: lab - 10, y: y + 4, "text-anchor": "end" }, clip(`${c.mechanic} ${mmss(c.start_s)}`, lab - 14)));
      else {   // the mechanic on its block's first row, each row's group beside the axis
        if (!k) svg.append(sv("text", { class: "lbl", x: 0, y: y + 4 }, clip(`${shortMech(c.mechanic)} ${mmss(c.start_s)}`, lab - 44)));
        svg.append(sv("text", { x: lab - 10, y: y + 4, "text-anchor": "end" }, grp.name));
      }
      svg.append(sv("rect", { x: X(c.comfortable - c.breakeven), y: y - (multi ? 7 : 9), width: X(0) - X(c.comfortable - c.breakeven), height: multi ? 14 : 18, rx: 3, fill: "var(--zone)" }));
      svg.append(sv("line", { x1: X(0), x2: X(0), y1: y - (multi ? 9 : 11), y2: y + (multi ? 9 : 11), stroke: "var(--ink-2)", "stroke-width": 1 }));
      if (!vals.length) { svg.append(sv("text", { x: X(0) + 8, y: y + 4 }, "not reached")); return; }
      const best = vals[0], med = median(vals), db = best - c.breakeven, dm = med - c.breakeven;
      svg.append(sv("circle", { cx: X(dm), cy: y, r: 5, fill: "var(--surface)", stroke: "var(--series)", "stroke-width": 2 }));
      svg.append(sv("circle", { class: "mark", cx: X(db), cy: y, r: 5, fill: "var(--series)", stroke: "var(--surface)", "stroke-width": 2 }));
      if (dm > hi || db > hi) svg.append(sv("text", { x: X(hi) - 2, y: y - 8, "text-anchor": "end" }, `+${Math.round(Math.max(dm, db))}`));
      const g = best <= c.comfortable ? "good" : best <= c.breakeven ? "ok" : "bad";
      const dot = sv("circle", { cx: width - 6, cy: y, r: 4, fill: `var(--${{ good: "good", ok: "warn", bad: "bad" }[g]})` });
      dot.append(sv("title", {}, { good: "at Comfy or better", ok: "at Clear or better", bad: "behind" }[g]));
      svg.append(sv("text", { class: "val", x: width - 16, y: y + 4, "text-anchor": "end" }, `${best.toFixed(1)}%`), dot);
      const ahead = d => d <= 0 ? `${(-d).toFixed(1)} ahead` : `${d.toFixed(1)} behind`;
      const hit = sv("rect", { class: "hit", x: lab, y: y - rh / 2, width: w + valW, height: rh });
      hover(hit, `${multi ? `${grp.name} · ` : ""}${c.mechanic} (starts ${mmss(c.start_s)})`, [[`${best.toFixed(1)}%`, `best (${ahead(db)})`], [`${med.toFixed(1)}%`, `median (${ahead(dm)})`],
        [`${vals.length}`, "pulls got there"], [`${c.breakeven}%`, "Clear: on pace to kill at enrage"], [`${c.comfortable}%`, "Comfy: ~13 s to spare"]]);
      svg.append(hit);
    });
    return svg;
  };
}
const checkpointLegend = () => [
  el("span", {}, el("i", { style: "width:10px;height:10px;border-radius:50%;background:var(--series)" }), "best pull"),
  el("span", {}, el("i", { style: "width:10px;height:10px;border-radius:50%;border:2px solid var(--series)" }), "median"),
  el("span", {}, el("i", { style: "width:18px;height:10px;border-radius:3px;background:var(--zone)" }), "Comfy zone"),
  el("span", {}, el("i", { style: "width:1px;height:12px;background:var(--ink-2)" }), "Clear: on pace to kill at enrage"),
  el("span", {}, "right: best HP"),
  el("span", {}, el("i", { style: "width:8px;height:8px;border-radius:50%;background:var(--good)" }), "at Comfy"),
  el("span", {}, el("i", { style: "width:8px;height:8px;border-radius:50%;background:var(--warn)" }), "at Clear"),
  el("span", {}, el("i", { style: "width:8px;height:8px;border-radius:50%;background:var(--bad)" }), "behind"),
];
function checkpointTable(hp, groups) {
  const list = groups || [{ name: null, hp }];
  return tableOf(["Mechanic", ...(groups ? ["Group"] : []), "Starts", "Clear", "Comfy", "Best", "Median", "Pulls"],
    seenCps().flatMap(c => list.map(g => { const v = g.hp[c.mechanic] || []; return [c.mechanic, ...(groups ? [g.name] : []), mmss(c.start_s), `${c.breakeven}%`, `${c.comfortable}%`,
      v.length ? `${v[0].toFixed(1)}%` : "–", v.length ? `${median(v).toFixed(1)}%` : "–", String(v.length)]; })), groups ? 2 : 1);
}

// ---------- shared pieces ----------
function tiles(items) {
  return el("div", { class: "kpis" }, items.map(([label, value, sub, g]) => el("div", { class: "tile" }, el("div", { class: "label" }, label),
    el("div", { class: "value" }, value, gradeChip(g)), sub ? el("div", { class: "sub" }, sub) : null)));
}
function crumbs(parts) {
  const nav = document.getElementById("crumbs"); nav.replaceChildren();
  parts.forEach(([label, href], i) => {
    if (i) nav.append(el("span", { "aria-hidden": "true" }, "›"));
    nav.append(href ? el("a", { href }, label) : el("span", { "aria-current": "page" }, label));
  });
}
function linkRow(cells, href, numericFrom = 1) {
  const tr = el("tr", { class: "link", tabindex: "0", on: { click: () => (location.hash = href), keydown: e => { if (e.key === "Enter") location.hash = href; } } },
    cells.map((c, i) => el("td", { class: i >= numericFrom ? "num" : null }, c)));
  return tr;
}
// a mistake's name in the cause tables: the major mechanic it happened in, in the short form used for how far pulls
// got, then the mistake ("SC I: Orange cone overlap"). Labels that name a mechanic themselves ("Paradeigma II: ...",
// "... (Superchain)") lose it, so it is not said twice; one mistake in several mechanics gets a row per mechanic
function causeName(mech, label) {
  const rest = label.replace(/^(Paradeigma I{1,3}|Superchain I{1,2}[AB]?): /, "").replace(/ \(Superchain\)$/, "").replace(/^([^:]+): /, "$1, ");
  if (!mech || mech === "other") return rest;
  return `${shortMech(mech)}: ${rest.replace(new RegExp(`^${mech.split(" ")[0]} `), "")}`;   // "Superchain laser group" in SC I: "laser group"
}
const causeInfo = r => { const m = {};
  for (const q of r.pulls) { for (const x of q.mistakes || []) m[causeName(x.mechanic, x.label)] = { mech: x.mechanic, label: x.label };
    if (q.wipe) m[causeName(q.wipe.mechanic, q.wipe.label)] = m[causeName(q.wipe.mechanic, q.wipe.label)] || { mech: q.wipe.mechanic, label: q.wipe.label }; }
  return m; };
const countBy = keys => keys.reduce((a, k) => ((a[k] = (a[k] || 0) + 1), a), {});
// every mistake until each pull was lost (of one player, if given), and the mistake that lost each pull
const mistakeCounts = (r, who) => countBy(r.pulls.flatMap(q => (q.mistakes || []).filter(m => !who || m.who === who).map(m => causeName(m.mechanic, m.label))));
const wipeCounts = (r, who) => {
  const c = countBy(r.pulls.filter(q => q.wipe && q.wipe.label && (!who || q.wipe.culprits.includes(who))).map(q => causeName(q.wipe.mechanic, q.wipe.label)));
  if (!who && r.wipe_causes && r.wipe_causes.Unclear) c.Unclear = r.wipe_causes.Unclear;   // wipes nobody could be blamed for have no wipe entry on the pull
  return c;
};

function causeMatrix(title, caption, cols, getCounts) {   // causes x columns heatmap card
  const counts = cols.map(getCounts);
  const totals = {};
  counts.forEach(c => Object.entries(c).forEach(([k, n]) => (totals[k] = (totals[k] || 0) + n)));
  const rowsAll = Object.keys(totals).sort((a, b) => totals[b] - totals[a]);
  if (!rowsAll.length) return el("figure", { class: "card" }, el("div", { class: "card-head" }, el("h3", {}, title)), el("div", { class: "empty" }, "Nothing recorded."));
  // the most frequent causes first; a long tail of ones and twos waits behind a button (the table view has them all)
  let rows = rowsAll.length > CAUSE_ROWS + 3 ? rowsAll.slice(0, CAUSE_ROWS) : rowsAll;
  const draw = width => heatmap(rows, cols.map(c => c.label), (r, c) => counts[c][rows[r]] || 0)(width);
  const f = card(title, caption, draw,
    () => tableOf(["Cause", ...cols.map(c => c.label), "Total"], rowsAll.map(k => [k, ...counts.map(c => String(c[k] || 0)), String(totals[k])])));
  if (rows.length < rowsAll.length) {
    const more = el("button", { type: "button", class: "small", on: { click: () => { const body = f.querySelector(".chart");
      rows = rowsAll; body.replaceChildren(draw(Math.max(260, body.clientWidth || 360))); more.remove(); } } },
      `Show ${rowsAll.length - rows.length} more causes (${sum(rowsAll.slice(rows.length).map(k => totals[k]))} mistakes)`);
    f.querySelector(".chart").after(el("p", { class: "more" }, more));
  }
  return f;
}
const CAUSE_ROWS = 15;

// ---------- pages ----------
function home() {
  crumbs([]);   // the header link names the page
  const ds = days(), all = stats(reports());
  const app = document.getElementById("app");
  app.append(el("h1", {}, "Raid days"), el("p", { class: "lede" }, `${ds.length} raid days, ${reports().length} group reports. Pick a day to compare its groups, then a group to see its players.`));
  const last = ds[ds.length - 1], ls = stats(last.groups);
  // the longest pull of all, and the mechanic it got to (the last one that had started)
  const far = reports().flatMap(r => r.pulls.map(q => ({ ...q, day: r.day, group: r.group }))).reduce((a, q) => (!a || q.dur > a.dur ? q : a), null);
  const reached = far && Object.entries(DATA.benchmark.mech_start).filter(([m, t]) => m !== "other" && t <= far.dur).sort((a, b) => b[1] - a[1])[0];
  app.append(tiles([
    ["Pulls", num(all.pulls), all.kills ? `${all.kills} kills` : `${(sum(reports().flatMap(r => r.pulls.map(p => p.dur))) / 3600).toFixed(1)} hours in combat`],
    ["Best pull", `${all.best.toFixed(1)}% HP`, "lowest boss HP reached"],
    ["Furthest seen", far ? mmss(far.dur) : "–", far ? `${far.kill ? "kill" : reached ? reached[0] : "opener"} · ${dayName(far.day)} ${far.group}, pull ${far.n}` : ""],
    ["Latest day", dayName(last.day), `${last.groups.length} group${last.groups.length > 1 ? "s" : ""}, ${ls.pulls} pulls`],
    ["Mistakes per pull", ls.mistakesPerPull?.toFixed(2), "latest day, per player", grade("mistakes", ls.mistakesPerPull)],
  ]));
  const series = f => ds.map(d => ({ x: dayName(d.day), y: f(stats(d.groups)), day: d.day }));
  // burndown over every pull, as on tomestone.gg
  const P = allPulls(), ok = P.filter(p => !p.echo && p.boss != null), best = ok.length ? Math.min(...ok.map(p => p.boss)) : null;
  const bd = card("Burndown", info("Every pull's boss HP at its end, all groups together in the order they were played (thin line), and the best so far (steps); dotted lines mark the first pull that reached each mechanic. Hover a pull for its day, group and how it ended. Pulls with The Echo are drawn but not counted for the best line."),
    burndownChart(P), () => tableOf(["Pull", "Day", "Group", "Boss HP", "Ended"], P.map((p, i) => [String(i + 1), dayName(p.day), p.group, p.boss != null ? `${p.boss.toFixed(1)}%` : "–", p.kill ? "Kill" : p.wipe ? p.wipe.label || "wipe" : "–"])));
  bd.querySelector(".card-head").after(el("p", { class: "summary" }, `${P.length} pulls over ${new Set(P.map(p => p.day)).size} raid days · ${(P.reduce((s, p) => s + p.dur, 0) / 3600).toFixed(1)} hours in combat · best pull `,
    el("b", {}, best != null ? `${best.toFixed(1)}%` : "–"), P.some(p => p.echo) ? " (Echo pulls not counted)" : ""));
  app.append(el("h2", {}, "Burndown"), bd);
  app.append(el("h2", {}, "Over time"), el("div", { class: "grid" },
    card("How far pulls get", info("Share of each day's pulls that reached each mechanic (all groups)."),
      seqHeatmap(reachMechs().map(m => shortMech(m.name)), ds.map(d => dayName(d.day).replace(/^\w+ /, "")), (i, k) => {
        const P = ds[k].groups.flatMap(r => r.pulls), x = reachRows(P).reach[i]; return { v: x.share, text: pct(x.share), sub: `${x.n} of ${P.length} pulls` }; }),
      () => tableOf(["Mechanic", ...ds.map(d => dayName(d.day))], reachMechs().map((m, i) => [m.name, ...ds.map(d => pct(reachRows(d.groups.flatMap(r => r.pulls)).reach[i].share))]))),
    (() => { const pullsOf = d => d.groups.flatMap(r => r.pulls), latest = ds[ds.length - 1], earlier = ds.slice(0, -1);
      const now = cleanThrough(pullsOf(latest)), before = cleanThrough(earlier.flatMap(pullsOf));
      return card("Pulls clean through mechanics", info(`For each mechanic, of the pulls that entered it with nobody dead or with Damage Down, the share that also got through it clean. Bars: the latest raid day (${dayName(latest.day)}); marker: all earlier days together. The mechanic where the bar drops is where pulls start to go wrong.`),
        shareBars(now.map((x, i) => ({ label: shortWin(x.name), name: x.name, v: x.share, ref: before[i].share,
          tip: [[x.share != null ? pct(x.share) : "–", `${x.left} of ${x.entered} pulls, ${dayName(latest.day)}`, true],
            [before[i].share != null ? pct(before[i].share) : "–", `${before[i].left} of ${before[i].entered}, earlier days`]] })), { barName: dayName(latest.day), refName: "earlier days" }),
        () => tableOf(["Mechanic", ...ds.map(d => dayName(d.day))], seenWindows().map((w, i) => [w.name, ...ds.map(d => { const x = cleanThrough(pullsOf(d))[i];
          return x.share != null ? `${pct(x.share)} (${x.left}/${x.entered})` : "–"; })])));
    })(),
    card("Mistakes per pull", info("Per player, counted until each pull was lost. The dashed line divides the same mistakes by the minutes players spent in pulls (up to where each pull was lost), so longer pulls as the groups progress do not read as more mistakes." + STRATEGY_NOTE),
      lineChart(series(s => s.mistakesPerPull), { yFmt: v => v.toFixed(2), name: "per pull", dated: true, extra: [{ points: series(s => s.mistakesPerMin), name: "per minute", cls: "x-min", color: "#9b6cf2" }] }),
      () => tableOf(["Day", "Mistakes per pull", "Per minute in pulls"], ds.map(d => { const s2 = stats(d.groups); return [dayName(d.day), s2.mistakesPerPull.toFixed(2), s2.mistakesPerMin != null ? s2.mistakesPerMin.toFixed(3) : "–"]; }))),
    card("Damage lost to mistakes", info("Boss HP per pull lost to mistakes before each pull was lost, valued at the player's own rDPS in that phase. Deaths: time dead and the raise's Weakness (−22% damage for 100 s). Damage Down: −38% damage while it lasts. Both measured from players' own hits in these logs. Reports with The Echo are left out." + STRATEGY_NOTE),
      lineChart(series(s => s.lostPerPull), { yFmt: v => `${v.toFixed(1)}%`, name: "combined", dated: true,
        extra: [{ points: series(s => s.lostPerPull != null && s.lostDDPerPull != null ? s.lostPerPull - s.lostDDPerPull : null), name: "deaths", cls: "x-death" },
                { points: series(s => s.lostDDPerPull), name: "Damage Down", cls: "x-dd" }] }),
      () => tableOf(["Day", "Combined", "Deaths", "Damage Down"], ds.map(d => { const s2 = stats(d.groups);
        return [dayName(d.day), hpfmt(s2.lostPerPull), hpfmt(s2.lostPerPull != null && s2.lostDDPerPull != null ? s2.lostPerPull - s2.lostDDPerPull : null), hpfmt(s2.lostDDPerPull)]; }))),
    card("Party DPS 0:00–2:00", info(`Clean pulls. Clears ~${kfmt(DATA.benchmark.pools.clears.party_dps_median)}. Minimum to clear ~${kfmt(DATA.benchmark.pools.clears.party_dps_min)}: the 0:00–2:00 party DPS that is on pace to kill just before enrage (7:38), if the rest of the fight goes like a clear's (clears do about 11% more in their first two minutes than their fight average).`),
      lineChart(series(s => s.party), { yFmt: v => kfmt(v), yMin: 60000, yMax: 100000,
        refs: [{ value: DATA.benchmark.pools.clears.party_dps_median, label: "clears" }, { value: DATA.benchmark.pools.clears.party_dps_min, label: "min to clear", cls: "ref-min" }] }), () => tableOf(["Day", "Party DPS"], ds.map(d => [dayName(d.day), kfmt(stats(d.groups).party)]))),
    card("Pull pacing", info(`Time in combat against the raid time (each group's first pull to the end of its last), all groups of the day together. The table view adds the median reset between pulls (breaks of 5 minutes or more left out), pulls per hour and those breaks; group and day pages have them as a tile.`),
      lineChart(ds.map(d => { const x = pacing(d.groups); return { x: dayName(d.day), y: x ? x.share : null, day: d.day }; }).filter(p => p.y != null), { yFmt: v => pct(v), yMax: 1, name: "in combat" }),
      () => tableOf(["Day", "In combat", "Raid time", "Median reset", "Pulls per hour", "Breaks of 5+ min"], ds.map(d => { const x = pacing(d.groups);
        return x ? [dayName(d.day), pct(x.share), `${(x.span / 3600).toFixed(1)} h`, `${Math.round(x.reset)} s`, x.perHour.toFixed(1), String(x.breaks)] : [dayName(d.day), "–", "–", "–", "–", "–"]; }))),
    (() => { const th = nightThirds(reports());
      return card("Through the night", info("Each group's pulls of a night split into thirds by pull order, all nights together: mistakes per player per minute in pulls (up to where each pull was lost). Hover for how long the pulls lasted and mistakes per pull. The first pulls of a night are the shortest and the most error-prone."),
        hbarChart(th.map(x => ({ label: x.name, value: x.perMin || 0, tip: [[x.perMin != null ? x.perMin.toFixed(3) : "–", "mistakes per player per minute", true],
          [x.dur != null ? mmss(x.dur) : "–", "average pull"], [x.perPull != null ? x.perPull.toFixed(2) : "–", "mistakes per player per pull"], [String(x.n), "pulls"]] })), { fmt: v => v.toFixed(3) }),
        () => tableOf(["Part of the night", "Pulls", "Average pull", "Mistakes per player per pull", "Per minute"], th.map(x => [x.name, String(x.n), x.dur != null ? mmss(x.dur) : "–",
          x.perPull != null ? x.perPull.toFixed(2) : "–", x.perMin != null ? x.perMin.toFixed(3) : "–"]))); })(),
  ));
  app.append(el("h2", {}, "Days"), el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, ["Day", "Groups", "Pulls", "Best HP", "Longest", "Clean ≤2:00", "Party DPS", "Mistakes/pull", "Top wipe cause"].map((h, i) => el("th", { class: i && i < 8 ? "num" : null }, h)))),
    el("tbody", {}, [...ds].reverse().map(d => { const s = stats(d.groups); const tr = linkRow([dayName(d.day), String(d.groups.length), String(s.pulls), `${s.best.toFixed(1)}%`, mmss(s.longest),
      pct(s.clean2 / s.pulls), kfmt(s.party), s.mistakesPerPull.toFixed(2), topWipeCell(s)], `#/day/${d.day}`); tr.lastChild.className = ""; return tr; })))));
}

// "← Pull 10 · Pull 12 →": links to the neighbours that exist ([label, href] or null)
const pager = (prev, next) => el("p", { class: "lede" },
  ...(prev ? [el("a", { href: prev[1] }, `← ${prev[0]}`)] : []), ...(prev && next ? [el("span", { class: "muted" }, "  ·  ")] : []),
  ...(next ? [el("a", { href: next[1] }, `${next[0]} →`)] : []));
function dayPage(day) {
  const ds = days(), k = ds.findIndex(x => x.day === day), d = ds[k];
  if (!d) return notFound();
  crumbs([["Raid days", "#/"], [dayName(day), null]]);
  const s = stats(d.groups), app = document.getElementById("app"), prev = ds[k - 1], next = ds[k + 1];
  const ps = prev ? stats(prev.groups) : null, was = (v, f) => ps && v != null ? ` · ${f(v)} on ${dayName(prev.day)}` : "";
  app.append(el("h1", {}, dayName(day)), pager(prev && [dayName(prev.day), `#/day/${prev.day}`], next && [dayName(next.day), `#/day/${next.day}`]),
    el("p", { class: "lede" }, `${d.groups.length} group${d.groups.length > 1 ? "s" : ""}. Pick a group for its player scorecard and pulls.`));
  app.append(tiles([
    ["Pulls", num(s.pulls), s.kills ? `${s.kills} kills` : `${(sum(d.groups.flatMap(r => r.pulls.map(p => p.dur))) / 3600).toFixed(1)} hours in combat`],
    ["Best pull", `${s.best.toFixed(1)}% HP`, `longest ${mmss(s.longest)}${was(ps && ps.best, v => `${v.toFixed(1)}%`)}`],
    ["Mistakes per pull", s.mistakesPerPull.toFixed(2), `per player${was(ps && ps.mistakesPerPull, v => v.toFixed(2))}`, grade("mistakes", s.mistakesPerPull)],
    ["Party DPS 0:00–2:00", kfmt(s.party), `clears ~${kfmt(DATA.benchmark.pools.clears.party_dps_median)} · min to clear ~${kfmt(DATA.benchmark.pools.clears.party_dps_min)}${was(ps && ps.party, kfmt)}`],
    budgetTile(d.groups), pacingTile(d.groups),
  ]));
  app.append(el("h2", {}, "Groups"), el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, ["Group", "Pulls", "Best HP", "Longest", "Clean ≤2:00", "Party DPS", "Mistakes/pull", "Lost to deaths/pull", "Top wipe cause"].map((h, i) => el("th", { class: i && i < 8 ? "num" : null }, h)))),
    el("tbody", {}, d.groups.map(r => { const g = stats([r]); const tr = linkRow([r.echo ? `${r.group} (Echo)` : r.group, String(r.pulls_total), `${r.best.toFixed(1)}%`, mmss(stats([r]).longest), pct(r.clean2 / r.pulls_total),
      kfmt(r.party), g.mistakesPerPull.toFixed(2), hpfmt(g.lostPerPull), topWipeCell(g)], `#/day/${day}/${r.group}`); tr.lastChild.className = ""; return tr; })))));
  app.append(heading("h2", "Boss HP checkpoints", "Boss HP when each mechanic begins, as points ahead of or behind the pace for a kill at enrage (Clear). Hover a row for the exact HP."),
    (() => { const gs = d.groups.map(r => ({ name: r.group, hp: r.hp }));
      return card(d.groups.length > 1 ? "Groups side by side" : d.groups[0].group, `${d.groups.map(r => `${r.group} ${r.pulls_total} pulls`).join(" · ")}`,
        checkpointChart(null, gs), () => checkpointTable(null, gs), checkpointLegend()); })());
  const cols = d.groups.map(r => ({ label: r.group, r }));
  app.append(el("h2", {}, "What went wrong"), el("div", { class: "grid wide" },
    causeMatrix("All mistakes", "Every mistake until each pull was lost, by cause and group.", cols, c => mistakeCounts(c.r)),
    causeMatrix("What wiped us", "The mistake that lost each pull, by cause and group.", cols, c => wipeCounts(c.r))));
}

function groupPage(day, group) {
  const r = findGroup(day, group);
  if (!r) return notFound();
  crumbs([["Raid days", "#/"], [dayName(day), `#/day/${day}`], [group, null]]);
  const s = stats([r]), app = document.getElementById("app"), b = DATA.benchmark;
  const others = days().find(x => x.day === day).groups.filter(g => g !== r);
  app.append(el("h1", {}, `${group} · ${dayName(day)}`),
    el("p", { class: "lede" }, "Report ", el("a", { href: `https://www.fflogs.com/reports/${encodeURIComponent(r.code)}`, target: "_blank", rel: "noopener" }, `${r.code} ↗`),
      ". Pick a player for their mistakes, damage and trend.", others.length ? [" Other groups this day: ", ...others.flatMap((g, i) => [i ? " · " : "", el("a", { href: `#/day/${day}/${encodeURIComponent(g.group)}` }, g.group)])] : ""),
    echoNote(r));
  app.append(tiles([
    ["Pulls", String(r.pulls_total), r.kills ? `${r.kills} kills` : `${(sum(r.pulls.map(p => p.dur)) / 3600).toFixed(1)} hours in combat`], ["Best pull", `${r.best.toFixed(1)}% HP`, `longest ${mmss(stats([r]).longest)}`],
    ["Mistakes per pull", s.mistakesPerPull.toFixed(2), "per player", grade("mistakes", s.mistakesPerPull)],
    ["Party DPS 0:00–2:00", kfmt(r.party), `clears ~${kfmt(b.pools.clears.party_dps_median)} · min ~${kfmt(b.pools.clears.party_dps_min)}`],
    budgetTile([r]), pacingTile([r]),
  ]));
  app.append(heading("h2", "Raid leader focus", "The few things worth raising first: the mechanics that ended the most pulls and who failed them, the most common mistake, the costliest rotation issues against the clearers, the latest raid buff, and weak openers. Drill and Brief open the trainer on that mechanic."),
    el("div", { class: "focus-card" }, focusList(groupFocus(r), "Nothing stands out against the clears.")));
  // scorecard
  const head = ["Player", "Job", "Pulls", "Mistakes/pull", "Deaths/pull", "DD/pull", "Wipes", "vs Clears", "Uptime"];
  const rows = [];
  for (const role of ROLES) {
    const ps = r.players.filter(p => p.role === role).sort((a, c) => a.wrate - c.wrate || a.mrate - c.mrate);
    if (!ps.length) continue;
    rows.push(el("tr", { class: "role" }, el("td", { colspan: head.length }, role)));
    for (const p of ps) {
      const vsG = p.vs ? grade("damage", p.vs[0]) : null;
      rows.push(linkRow([p.name, JOB[p.job] || p.job, String(p.pulls),
        el("span", {}, p.mrate.toFixed(2), gradeChip(grade("mistakes", p.mrate))),
        ((p.mdeath_w ?? p.mdeath ?? 0) / p.pulls).toFixed(2), ((p.mdd_w ?? p.mdd ?? 0) / p.pulls).toFixed(2),
        el("span", {}, pct(p.wrate), gradeChip(grade("wipes", p.wrate))),
        p.vs ? el("span", {}, `${signed(p.vs[0])}${p.vs[1] < 3 ? "*" : ""}`, gradeChip(vsG)) : (p.samples ? `no ${JOB[p.job] || p.job} clears` : "no clean 2:00 pull"),
        p.uptime != null ? el("span", {}, `${p.uptime.toFixed(1)}%`, gradeChip(grade("uptime", p.uptime_diff))) : "–"], `#/day/${day}/${group}/${encodeURIComponent(p.name)}`, 2));
    }
  }
  app.append(heading("h2", "Player scorecard", `Mistakes per pull counts every mistake until the pull was lost; Deaths/pull and DD/pull split it into mistakes that killed someone and those that only gave Damage Down (one that did neither, like both Superchain I lasers on a player who lived, counts only in the total). Wipes: share of pulls their mistake lost. Both count each mistake in full, or the player's share of it where the classifier could not tell several players apart (½ between two) or the shortfall was the party's (healing / mitigation). vs Clears: rDPS 0:00–2:00 (best quarter of clean pulls) against clearers on the same job (clears without The Echo; a job with fewer than three such players also counts its Echo clears, damage divided by 1.2); * = only 1–2 clearers. Uptime: GCD time vs clearers of the role.`), el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, head.map((h, i) => el("th", { class: i >= 2 ? "num" : null }, h)))), el("tbody", {}, rows))),
    (r.light_parties || []).length === 2 ? el("p", { class: "note" }, `Light parties inferred from the White Flame baits: LP1 ${r.light_parties[0].join(", ")} · LP2 ${r.light_parties[1].join(", ")}.`) : "");
  // rotation and ability usage, per player
  const rotPlayers = r.players.filter(p => p.rotation && !p.rotation.opener_only);   // opener_only: no clears on the job, only the opener is compared
  if (rotPlayers.length) {
    const dps = v => `${num(Math.round(v))} DPS`;
    const who = p => `${p.name} ${JOB[p.job] || p.job}`;
    const rot = rotPlayers.map(p => {
      const cs = p.rotation.checks.filter(c => c.cost > 1).sort((a, c) => c.cost - a.cost);
      return { p, total: cs.reduce((s, c) => s + c.cost, 0), top: cs.slice(0, 3) };
    }).sort((a, c) => c.total - a.total);
    const abil = rotPlayers.map(p => {
      const as = (p.rotation.abilities || []).filter(a => a.worth > 1).sort((a, c) => c.worth - a.worth);
      return { p, total: as.reduce((s, a) => s + a.worth, 0), top: as.slice(0, 3) };
    }).sort((a, c) => c.total - a.total);
    const href = p => `#/day/${day}/${group}/${encodeURIComponent(p.name)}`;
    app.append(heading("h2", "Rotation", "Each player's rotation checks and skill usage against clearers on their job, over the same stretch of each pull (0:00 until they died or the pull was lost; 0:00–0:55 against clears that move through Paradeigma I), as on their own page. Rotation mistakes adds up the checks that have a cost: GCD gaps, cooldowns held, lost procs, missed DoT ticks, positionals, combos, gauge overcaps. Ability usage adds up the skills they cast less than the clearers, compared at their own GCD speed and worth their own damage per cast. The two overlap: a GCD gap shows up as missing casts too."),
      el("div", { class: "grid wide" },
        card("Rotation mistakes", info("DPS lost to the costed rotation checks against clearers; hover a player for their biggest three."),
          hbarChart(rot.filter(x => x.total > 1).map(x => ({ label: who(x.p), value: x.total,
            tip: [[dps(x.total), "against the clearers", true], ...x.top.map(c => [dps(c.cost), c.label])] })), { fmt: dps }),
          () => tableOf(["Player", "Total", "Biggest", "Second", "Third"], rot.map(x => [el("a", { href: href(x.p) }, who(x.p)), dps(x.total),
            ...[0, 1, 2].map(i => x.top[i] ? `${x.top[i].label} (${dps(x.top[i].cost)})` : "–")]), [1])),
        card("Ability usage against clearers", info("DPS worth of the skills each player cast less often than clearers on the job; hover for the biggest three."),
          hbarChart(abil.filter(x => x.total > 1).map(x => ({ label: who(x.p), value: x.total,
            tip: [[dps(x.total), "fewer casts than the clearers", true], ...x.top.map(a => [dps(a.worth), `${a.name} ${a.ours.toFixed(1)} vs ${a.clears.toFixed(1)}/min`])] })), { fmt: dps }),
          () => tableOf(["Player", "Total", "Biggest", "Second", "Third"], abil.map(x => [el("a", { href: href(x.p) }, who(x.p)), dps(x.total),
            ...[0, 1, 2].map(i => x.top[i] ? `${x.top[i].name} ${x.top[i].ours.toFixed(1)} vs ${x.top[i].clears.toFixed(1)}/min (${dps(x.top[i].worth)})` : "–")]), [1]))));
  }
  // pulls
  const cps = b.hp_checkpoints.mechanics;
  const refs = [{ value: 55.4, label: "Para II" }, { value: 112.4, label: "SC I" }, { value: 193.9, label: "Para III" }, { value: 284, label: "Palladion" }, { value: 349, label: "SC II" }];
  const bars = r.pulls.map(p => ({ label: String(p.n), value: p.dur, p }));
  app.append(el("h2", {}, "Pulls"), el("p", { class: "lede" }, el("a", { href: `#/day/${day}/${group}/pulls` }, "Every pull, player by player →")),
    el("div", { class: "grid wide" },
    card("How far each pull got", info("Pull length; lines mark when each mechanic begins. Hover a pull for its first mistake and what lost it; click it to open the pull."),
      columnChart(bars, { yFmt: v => mmss(v), refs, tickStep: 60, onBar: bar => (location.hash = `#/day/${day}/${group}/pulls/${bar.p.n}`), barTip: bar => { const p = bar.p, wv = p.wipe;
        return [`Pull ${p.n} · ${mmss(p.dur)} · boss ${p.boss?.toFixed(1)}%`, [[mmss(p.first), "first death or Damage Down"],
          [wv ? wv.culprits.join(", ") || "unclear" : (p.kill ? "kill" : "unclear"), wv ? `${wv.label} at ${mmss(wv.t)}` : "", true], [String(p.mistakes.length), "mistakes counted"], [String(p.deaths), "deaths"]]]; } }),
      () => tableOf(["Pull", "Length", "Boss HP", "First mistake", "Lost by", "Cause", "Mistakes"], r.pulls.map(p => [String(p.n), mmss(p.dur), `${p.boss?.toFixed(1)}%`, mmss(p.first),
        p.wipe ? names(p.wipe.culprits) : (p.kill ? "kill" : "–"), p.wipe ? p.wipe.label : "", String(p.mistakes.length)]))),
    (() => { const R = reachRows(r.pulls), wall = R.seg.reduce((a, s) => s.end > a.end ? s : a, R.seg[0]);
      return card("Where pulls ended", info(`How many pulls ended between each pair of mechanics (by pull length), and how many reached each mechanic. The longest bar is the wall: here ${wall.name}.`),
        hbarChart(R.seg.map(s => ({ label: s.name, value: s.end, tip: [[String(s.end), "pulls ended here", true]] })), { fmt: v => String(v) }),
        () => tableOf(["Mechanic", "Pulls reaching it", "Share"], R.reach.map(x => [x.name, String(x.n), pct(x.share)]))); })(),
    card("Boss HP checkpoints", info("Boss HP when each mechanic begins, as points ahead of or behind the pace for a kill at enrage."), checkpointChart(r.hp), () => checkpointTable(r.hp), checkpointLegend())));
  // damage lost to deaths
  const uniq = [...r.players].filter((p, i, a) => a.findIndex(q => q.name === p.name) === i);
  const costRows = uniq.map(p => ({ label: p.name, value: p.lost_caused / p.pulls, p })).sort((a, c) => c.value - a.value);
  const causeAll = Object.entries(r.lost_causes || {}).sort((a, c) => c[1] - a[1]).map(([label, v]) => ({ label, value: v / r.pulls_total }));
  const causeCost = causeAll.length > 11 ? [...causeAll.slice(0, 10), { label: `Other causes (${causeAll.length - 10})`, value: sum(causeAll.slice(10).map(x => x.value)) }] : causeAll;
  // raid buff timing per burst
  if (r.burst && r.burst.buffs.length) {
    const B = r.burst, nb = Math.max(...B.buffs.map(x => x.burst));
    const sp = Object.fromEntries((B.spread || []).map(x => [x.burst, x]));
    const label = x => `${x.buff} · ${x.player}`;
    app.append(heading("h2", "Burst", "When each raid buff landed in each 2-minute burst against the clears' median for that buff and burst (seconds; positive is later), from pulls that got through the burst. Skipped: the buff's user was alive and did not use it in that burst. Spread: seconds from the party's first raid buff to its last, against the clears."),
      el("div", { class: "grid wide" }, ...Array.from({ length: nb }, (_, i) => i + 1).map(k => {
        const xs = B.buffs.filter(x => x.burst === k);
        const s = sp[k];
        return card(k === 1 ? "Opener burst" : `${2 * (k - 1)}:00 burst`, s ? `Spread ${s.ours.toFixed(1)} s against the clears' ${s.clears != null ? s.clears.toFixed(1) : "–"} s, ${s.n} pulls.` : null,
          divergingBars(xs.map(x => ({ label: label(x), v: x.delay != null ? x.delay / 10 : null, empty: x.skipped ? `skipped ${x.skipped}×` : "no use",
            tip: [[x.delay != null ? `${x.delay >= 0 ? "+" : "−"}${Math.abs(x.delay).toFixed(1)} s` : "–", "against the clears", true],
              [String(x.n), "uses"], [String(x.skipped), "skipped while alive"]] })), { limit: 0.6, fmt: v => `${v >= 0 ? "+" : "−"}${Math.abs(v * 10).toFixed(1)} s`, invert: true, ends: ["← earlier", "clears", "later →"] }),
          () => tableOf(["Buff", "Player", "Delay", "Uses", "Skipped"], xs.map(x => [x.buff, x.player, x.delay != null ? `${x.delay >= 0 ? "+" : "−"}${Math.abs(x.delay).toFixed(1)} s` : "–",
            String(x.n), String(x.skipped)]), 2));
      })));
  }
  app.append(heading("h2", "Damage lost to mistakes",
    `Before each pull was lost, mistakes cost ${hpfmt(s.lostPerPull)} per pull (${secs(s.lostPerPull)}), of which Damage Down ${hpfmt(s.lostDDPerPull)}: time spent dead and the 100 s of Weakness after a raise (−22% damage), and Damage Down (−38% while it lasts), valued at the player's own rDPS in that phase. A mistake counts against whoever caused it. The Mistake budget tile above is how much boss HP the group can lose to mistakes over a whole kill and still kill before enrage: 1 − (minimum party DPS to clear ÷ the group's party DPS), shown as deaths (time dead until raised plus the raise's Weakness) or Damage Downs at full length and the group's average player DPS.`),
    el("div", { class: "grid wide" },
      !SHOW_MISTAKE_COST ? null : card("What each player's mistakes cost", info("Boss HP per pull lost to deaths they caused (their own or others')."),
        hbarChart(costRows, { fmt: v => `${v.toFixed(2)}%` }), () => tableOf(["Player", "Caused per pull", "Own deaths cost per pull", "Dead per pull"],
          costRows.map(x => [x.label, `${x.value.toFixed(2)}%`, `${(x.p.lost_suffered / x.p.pulls).toFixed(2)}%`, `${(x.p.dead_s / x.p.pulls).toFixed(1)} s`]))),
      causeCost.length ? card("What the losses came from", info("Boss HP per pull, by the mistake behind each death."), hbarChart(causeCost, { fmt: v => `${v.toFixed(2)}%` }),
        () => tableOf(["Cause", "Per pull", "Total"], causeAll.map(x => [x.label, `${x.value.toFixed(2)}%`, `${(x.value * r.pulls_total).toFixed(1)}%`]))) : null));
  // damage per phase
  const W = seenWindows().map(w => w.name);
  const allPh = r.players.map(p => ({ p, ph: Object.fromEntries((p.phases || []).map(x => [x.window, x])) }));
  app.append(heading("h2", "Damage by phase", "nDPS in each phase against clearers on the same job (pots removed), from pulls where the player was alive and unweakened through that phase; a phase needs two such pulls. Late phases rarely have them." + stratNote()),
    card("Players against clearers, by phase", null,
      divHeatmap(allPh.map(x => `${x.p.name} ${JOB[x.p.job] || x.p.job}`), W.map(shortPhase), (i, j) => { const ph = allPh[i].ph[W[j]];
        return ph && ph.n >= MIN_PHASE && ph.vs ? { v: ph.vs[0], thin: ph.vs[1] < 3, tip: phaseTip(ph) } : null; }),
      () => tableOf(["Player", ...W.map(shortPhase)], allPh.map(x => [`${x.p.name} ${JOB[x.p.job] || x.p.job}`, ...W.map(w => { const ph = x.ph[w];
        return ph && ph.n >= MIN_PHASE && ph.vs ? `${signed(ph.vs[0])} (n=${ph.n})` : "–"; })])), divLegend()));
  const cols = [...r.players].filter((p, i, a) => a.findIndex(q => q.name === p.name) === i)
    .sort((a, c) => ROLES.indexOf(a.role) - ROLES.indexOf(c.role)).map(p => ({ label: p.name, p }));
  app.append(el("h2", {}, "Who made which mistakes"), el("div", { class: "grid wide" },
    causeMatrix("All mistakes by player", "Every mistake until each pull was lost.", cols, c => mistakeCounts(r, c.p.name)),
    causeMatrix("Wipes by player", "The mistake that lost the pull.", cols, c => wipeCounts(r, c.p.name))));
}

// a death's place in the pull: what decided the wipe, the collapse after it, or a death that saved the pull
const wipeCell = d => d.saved && !d.when ? el("td", { class: "good" }, "saved the pull")   // not once the pull was lost
  : el("td", { class: "muted" }, d.when === "lost" ? "decided the wipe" : d.when === "after" ? "after the wipe" : "");
function playerPage(day, group, name) {
  const r = findGroup(day, group);
  const entries = r ? r.players.filter(p => p.name === name) : [];
  if (!entries.length) return notFound();
  crumbs([["Raid days", "#/"], [dayName(day), `#/day/${day}`], [group, `#/day/${day}/${group}`], [name, null]]);
  const app = document.getElementById("app"), b = DATA.benchmark, p = entries[0];
  // their other raid days, in order: the same page on the day before and after
  const nights = reports().filter(x => (x.names || (x.players || []).map(q => q.name)).includes(name)).sort((a, c) => a.day.localeCompare(c.day) || a.group.localeCompare(c.group));
  const at = nights.findIndex(x => x.code === r.code), night = x => x && [`${dayName(x.day)} (${x.group})`, `#/day/${x.day}/${encodeURIComponent(x.group)}/${encodeURIComponent(name)}`];
  app.append(el("h1", {}, name), el("p", { class: "lede" }, `${entries.map(e => JOB[e.job] || e.job).join(" / ")} · ${group} · ${dayName(day)} · ${p.pulls} pulls`),
    nights.length > 1 ? pager(night(nights[at - 1]), night(nights[at + 1])) : "", echoNote(r));
  app.append(tiles([
    ["Mistakes per pull", p.mrate.toFixed(2), `${p.mdeath || 0} deaths · ${p.mdd || 0} Damage Downs${p.mhit ? ` · ${p.mhit} survived` : ""} in ${p.pulls} pulls` +
      (p.mconf && p.mistakes ? `; by confidence: ${confText(p.mconf)}` : ""), grade("mistakes", p.mrate)],
    ["Wipes caused", pct(p.wrate), `${p.wipes} of ${p.pulls} pulls` + (p.wconf && p.wipes ? `; by confidence: ${confText(p.wconf)}` : ""), grade("wipes", p.wrate)],
    ...entries.map(e => [`${JOB[e.job] || e.job} vs clears`, e.vs ? signed(e.vs[0]) : "–", e.vs ? `${e.vs[1]} clearer${e.vs[1] > 1 ? "s" : ""} on the job${e.vs[2] ? ", some with The Echo (damage ÷1.2)" : ""}${e.vs[1] < 3 ? " · thin data" : ""}` : "no comparison", e.vs ? grade("damage", e.vs[0]) : null]),
    ["Uptime 0:00–2:00", p.uptime != null ? `${p.uptime.toFixed(1)}%` : "–", `clearers ${b.pools.clears.role_uptime[p.role].toFixed(1)}%`, grade("uptime", p.uptime_diff)],
    ...entries.map(e => { const d = e.rotation && e.rotation.opener && e.rotation.opener.dmg;
      const R = opRef(e.rotation && e.rotation.opener);
      return [`${JOB[e.job] || e.job} opener vs ${R.short}`, d ? signed(d.vs) : "–", d ? `nDPS 0:00–0:20, ${d.n} pulls${d.best ? ` · ${signed(d.vs_best)} vs ${R.whose} opener` : ""}${d.echo_corrected ? " · some clears with The Echo (÷1.2)" : ""}${d.players != null && d.players < 5 ? ` · ${d.players} other players, thin data` : ""}` : "no comparison", d ? grade("damage", d.vs) : null]; }),
    deathTile(r, p),
  ]));
  app.append(heading("h2", "Work on this", "Their most important points, in order: mechanics whose mistakes lost pulls, their most frequent other mistake, the costliest rotation issues against clearers on the job, a weak opener, and a raid buff they press late or skip. Drill and Brief open the trainer on that mechanic."),
    el("div", { class: "focus-card" }, focusList(playerFocus(r, entries, name), "Nothing stands out against the clears.")));
  const mine = r.pulls.flatMap(q => q.mistakes.filter(m => m.who === name).map(m => ({ ...m, pull: q.n })));
  const wiped = r.pulls.filter(q => q.wipe && q.wipe.culprits.includes(name));
  const lostIt = m => wiped.some(q => q.n === m.pull && Math.abs(q.wipe.t - m.t) < 2.5);   // as in the Every mistake table
  const causeRows = Object.entries(mistakeCounts(r, name)).sort((a, c) => c[1] - a[1]).map(([label, value]) => { const of = mine.filter(m => causeName(m.mechanic, m.label) === label);
    return { label, value, values: [of.filter(lostIt).length, ...["death", "DD", "hit"].map(k => of.filter(m => !lostIt(m) && m.kind === k).length)] }; });
  app.append(el("h2", {}, "Mistakes"), el("div", { class: "grid wide" },
    causeRows.length ? card("Mistakes by cause", { info: `${p.mistakes} mistakes (${p.mdeath || 0} deaths, ${p.mdd || 0} Damage Downs${p.mhit ? `, ${p.mhit} survived` : ""}), counted until each pull was lost. Lost the pull: the mistake that ended a pull (the pull's wipe names them, within 2.5 s), usually a death, sometimes a Damage Down; the rest split into other deaths, Damage Downs and mistakes they survived without either (both Superchain I lasers on one player: it leaves them low for what comes next). A wipe put on them without a recorded mistake of theirs (an unsoaked tower, say) counts in Wipes caused but has no bar here.` },
      hbarStackChart(causeRows, KIND_SERIES),
      () => tableOf(["Cause", "Lost the pull", "Other deaths", "Damage Down", "Survived", "Total"], causeRows.map(x => [x.label, ...x.values.map(String), String(x.value)])))
      : el("figure", { class: "card" }, el("div", { class: "card-head" }, el("h3", {}, "Mistakes by cause")), el("div", { class: "empty" }, "No mistakes recorded.")),
    ...entries.filter(e => e.clean_pulls.length).map(e => {
      const jb = b.pools, refs = [];
      if (jb.clears.jobs[e.job]) refs.push({ value: jb.clears.jobs[e.job].rdps, label: "clears avg" });
      // ceiling: the optimizer's best unbuffed rotation at their GCD, the same for every pull, plus what that pull's
      // raid buff (a Reaper's Arcane Circle) gave the others, which rDPS credits to them
      const top = c => e.ceiling ? e.ceiling + (c.given || 0) : null;
      const bars = e.clean_pulls.map(c => ({ label: String(c.n), value: c.rdps, mark: top(c), c }));
      const tip = bar => [`Pull ${bar.c.n}`, [[num(bar.c.rdps), "rDPS", true], [`${bar.c.uptime}%`, "uptime"],
        ...(e.ceiling ? [[num(top(bar.c)), "ceiling"], [`${Math.round(100 * bar.c.rdps / top(bar.c))}%`, "of the ceiling"]] : []),
        ...(e.ceiling && bar.c.given ? [[num(bar.c.given), "of it from buffs on others"]] : [])]];
      return card(`${JOB[e.job] || e.job} rDPS on clean pulls`, info("0:00–2:00 of every pull with no death or Damage Down before 2:00; lines are other clearers' averages on the job." +
          (e.ceiling ? " Ticks: the ceiling, the best rotation without raid buffs at their GCD (the same every pull, from the optimizer, with our strategy's runs), plus what that pull's raid buffs gave the other players, which rDPS credits to them." + offlineNote(e.job) : "")),
        columnChart(bars, { yFmt: v => kfmt(v), refs, barTip: tip }),
        () => tableOf(["Pull", "rDPS", "Uptime", ...(e.ceiling ? ["Ceiling", "Of ceiling", "Buffs on others"] : [])],
          e.clean_pulls.map(c => [String(c.n), num(c.rdps), `${c.uptime}%`,
            ...(e.ceiling ? [num(top(c)), `${Math.round(100 * c.rdps / top(c))}%`, num(c.given || 0)] : [])])));
    })));
  // damage: cost of their mistakes and damage per phase
  const costBy = Object.entries(p.lost_caused_by || {}).sort((a, c) => c[1] - a[1]).map(([label, value]) => ({ label, value }));
  app.append(el("h2", {}, "Damage"), el("div", { class: "grid wide" },
    ...entries.map(e => {
      const seen = new Set(seenWindows().map(w => w.name));
      const rows = (e.phases || []).filter(ph => seen.has(ph.window)).map(ph => ({ label: ph.window, v: ph.n >= MIN_PHASE && ph.vs ? ph.vs[0] : null, thin: ph.vs && ph.vs[1] < 3,
        empty: ph.n >= MIN_PHASE ? `no ${JOB[e.job] || e.job} clearers` : ph.n ? "1 clean sample" : "no clean sample", tip: ph.n >= MIN_PHASE && ph.vs ? phaseTip(ph) : null }));
      return card(`${JOB[e.job] || e.job} damage by phase`, info("nDPS against clearers on the job, from pulls where they were alive through the phase. The first phase is compared with clears that move through Paradeigma I."),
        divergingBars(rows), () => tableOf(["Phase", "Samples", "nDPS", "vs clearers", "Uptime", "Uptime vs clearers"],
          (e.phases || []).map(ph => [ph.window, String(ph.n), ph.n ? num(ph.ndps) : "–", ph.vs ? signed(ph.vs[0]) : "–",
            ph.n ? `${ph.uptime.toFixed(1)}%` : "–", ph.uptime_diff != null ? `${ph.uptime_diff >= 0 ? "+" : "−"}${Math.abs(ph.uptime_diff).toFixed(1)}` : "–"])), divLegend());
    }),
    ...entries.filter(e => e.ceiling).map(optCard),
    !SHOW_MISTAKE_COST ? null : costBy.length ? card("What their mistakes cost", info(`Boss HP lost to deaths they caused, all ${p.pulls} pulls together.`), hbarChart(costBy, { fmt: v => `${v.toFixed(2)}%` }),
      () => tableOf(["Cause", "Boss HP"], costBy.map(x => [x.label, `${x.value.toFixed(2)}%`])))
      : el("figure", { class: "card" }, el("div", { class: "card-head" }, el("h3", {}, "What their mistakes cost")), el("div", { class: "empty" }, "None of their mistakes caused a death."))));
  // opener in the left column, rotation and abilities stacked in the right (see the end of these sections)
  const left = el("div", { class: "col" }), right = el("div", { class: "col" });
  // opener against the best opener the clears play: what was cast and when the cooldowns went out, not the GCD order
  const opEntries = entries.filter(e => e.rotation && e.rotation.opener && e.rotation.opener.skills);
  if (opEntries.length) {
    const sec = v => v == null ? "–" : `${v >= 0 ? "+" : "−"}${Math.abs(v).toFixed(1)} s`;
    const at = t => t == null ? "–" : t < 0 ? `${t.toFixed(1)} s` : mmss(t);
    const casts = v => Number.isInteger(v) ? String(v) : v.toFixed(1);
    left.append(heading("h2", "Opener", "Their openers (casts from before the pull through as many GCDs as the clears' opener has; potions, Sprint and defensives left out) against the best opener the clears play (casts to 0:22). A job with fewer than three clears to compare with (Bard has none; White Mage now starts the pull with a Blood Lily, which every WHM clear predates) is compared within our own groups instead: every other player on the job counts like one clear, with their usual opener and median opener damage over all raid days; the player themselves is left out. With few players on a job this is thin: the reference may be one other player's opener. Openers within a few casts of each other count as one variant; the reference is the variant most clears play, unless another clearly does more opener damage (ahead by more than 1.5 standard errors, since gear and crits spread players of one opener more than most openers differ). Compared: how often each skill is cast over as many GCDs as the clears' opener has, so a slower GCD from gear does not count as a missing cast (flagged at half a cast or more per pull) and when each oGCD cooldown and raid buff first goes out (flagged at 1.5 s or more). The order of GCDs is not compared, since swapping two inside the opener changes nothing. Times are not adjusted for GCD speed. Opener damage is nDPS over 0:00–0:20 (tinctures removed) from pulls they were alive through. The dot grades it against all clears on the job (or our other players), as on the opener tile: green from −5%, yellow from −12%, red below."),
      el("div", { class: "grid wide" }, ...opEntries.map(e => {
        const o = e.rotation.opener, d = o.dmg, groups = o.source === "groups", them = groups ? "the others" : "the clears";
        const diffs = [
          ...o.skills.filter(s => s.fewer).map(s => `${s.name}: ${casts(s.theirs)} per pull, ${them} ${casts(s.clears)}`),
          ...o.skills.filter(s => s.more).map(s => `${s.name}: ${casts(s.theirs)} per pull, ${them} ${casts(s.clears)}`),
          ...o.skills.filter(s => s.late != null).map(s => `${s.name} ${sec(s.late)} ${s.late > 0 ? "later" : "earlier"} than ${them} (${at(s.t_theirs)} vs ${at(s.t_clears)})`)];
        const n = Math.max(o.best.length, o.usual.length), names = new Set(o.usual.map(u => u.name)), bestNames = new Set(o.best.map(u => u.name));
        const side = Array.from({ length: n }, (_, i) => { const b = o.best[i], u = o.usual[i];
          return [String(i + 1), b ? el("span", { class: names.has(b.name) ? null : "bad" }, b.name + (b.gcd ? "" : " ·")) : "", b ? at(b.t) : "",
            u ? el("span", { class: bestNames.has(u.name) ? null : "bad" }, u.name + (u.gcd ? "" : " ·")) : "", u ? at(u.t) : ""]; });
        const dmgText = !d ? "Opener damage: –" : `Opener damage ${num(d.ndps)} nDPS (${d.n} pulls): ${d.best ? `${signed(d.vs_best)} against the ${groups ? "players" : "clears"} playing this opener (${num(d.best)}), ` : ""}${signed(d.vs)} against ${groups ? `our other ${JOB[e.job] || e.job}s (${num(d.clears)}, ${d.players} players${d.players < 5 ? ", thin data" : ""})` : `all clears (${num(d.clears)})`}${d.echo_corrected ? "; clears with The Echo included, their damage divided by 1.2" : ""}.`;
        const body = () => el("div", { class: "opener" },
          el("p", { class: "summary" }, dmgText),
          diffs.length ? el("ul", { class: "diffs" }, ...diffs.map(x => el("li", {}, x))) : el("p", { class: "note" }, `Same skills and cooldown timings as ${groups ? "our groups'" : "the clears'"} opener; only the order differs, which does not matter.`),
          el("div", { class: "table-wrap" }, tableOf(["#", groups ? "Our groups' opener" : "Clears' opener", "At", "Their usual opener", "At"], side, [2, 4])));
        return card(el("span", {}, `${JOB[e.job] || e.job} opener`, gradeChip(d ? grade("damage", d.vs) : null)), `${groups
            ? `${o.change}, so the opener is compared within our groups: ${o.pulls} pulls against the ${o.basis === "damage" ? "highest-damage" : "most played"} opener of our other ${JOB[e.job] || e.job}s (${o.clears} of ${o.clears_all} players play it; their own left out${o.clears_all < 5 ? "; thin data" : ""}).`
            : `${o.pulls} pulls against the ${o.basis === "damage" ? "highest-damage" : "most played"} clear opener (${o.clears} of ${o.clears_all} clears play it).`} Their GCD ${e.rotation.gcd ? e.rotation.gcd.toFixed(2) : "–"} s${e.rotation.clear_gcd ? `, clears' ${e.rotation.clear_gcd.toFixed(2)} s` : ""}. · marks an oGCD; red: not in the other opener.`,
          () => body(), () => tableOf(["Skill", "Clears' casts", "Theirs", "Clears' first", "Their first"],
            o.skills.map(s => [s.name + (s.gcd ? "" : " ·"), String(s.clears), el("span", { class: s.fewer || s.more ? "bad" : null }, casts(s.theirs)),
              at(s.t_clears), el("span", { class: s.late != null ? "bad" : null }, at(s.t_theirs))]), [1, 2, 3, 4]));
      })));
  }
  // rotation checks against the clears over the same stretch of fight
  const rotEntries = entries.filter(e => e.rotation && !e.rotation.opener_only);
  if (rotEntries.length) {
    const rate = (c, v) => c.unit === "s" ? `${v.toFixed(1)} s/min` : c.unit === "ticks" || c.unit === "gcds" || c.unit === "gauge" ? `${v.toFixed(1)}/min`
      : c.unit === "per window" ? `${v.toFixed(1)} GCDs` : `${(v * 10).toFixed(2)} per 10 min`;
    const costText = c => c.cost > 1 ? `${num(Math.round(c.cost))} DPS`
      : c.key === "interrupted" && c.ours > c.clears * 1.1 ? "time counted in the gap row"
      : c.unit === "per window" ? (c.ours < c.clears - 0.3 ? `${(c.clears - c.ours).toFixed(1)} fewer (${c.windows} windows)` : "–")
      : c.ours > c.clears * 1.1 && c.cost == null ? "more, uncosted" : "–";
    right.append(heading("h2", "Rotation", "Simple rotation mistakes against clearers on the job, measured over the same stretch of each pull (0:00 until they died or the pull was lost) so mechanics that cost everyone time cancel out; 0:00–0:55 is compared with clears that move through Paradeigma I. Cost is the damage the difference is worth, from their own hits. GCD gaps are split by what filled them; burst windows count GCDs started inside their own damage buffs."),
      el("div", { class: "grid wide" }, ...rotEntries.map(e => {
        const r = e.rotation, costly = r.checks.filter(c => c.cost > 1).slice(0, 6), g = rotGain(r);
        return card(gainTitle(`${JOB[e.job] || e.job} rotation`, g), `${r.pulls} pulls, ${r.alive_min.toFixed(0)} min alive; against ${r.clears} clearers. Usual GCD ${r.gcd ? r.gcd.toFixed(2) + " s" : "–"}.${gainNote(g, "all costed checks")}`,
          costly.length ? hbarChart(costly.map(c => ({ label: c.label, value: c.cost })), { fmt: v => `${num(Math.round(v))} DPS` })
            : () => el("div", { class: "empty" }, "Nothing they do notably more often than the clearers."),
          () => tableOf(["Check", "Them", "Clearers", "Cost"], r.checks.map(c => [c.label, rate(c, c.ours), rate(c, c.clears), costText(c)])));
      })));
  }
  // abilities against clearers on the job
  const abEntries = entries.filter(e => e.rotation && (e.rotation.abilities || []).length);
  if (abEntries.length) {
    right.append(heading("h2", "Abilities", "Casts per minute of every damaging skill against clearers on the job, over the same stretch of each pull as the rotation checks (0:00–0:55 against clears that move through Paradeigma I). GCD skills are compared at the player's own GCD speed (a slower GCD from gear fits fewer casts, which is no mistake). Worth is the damage the difference in casts comes to, at their own average damage per cast (DoT ticks included); positive means fewer casts than the clearers. It overlaps with the GCD gaps above: those say when time was lost, this says which casts it cost."),
      el("div", { class: "grid wide" }, ...abEntries.map(e => {
        const A = e.rotation.abilities, short = A.filter(a => a.worth > 1).slice(0, 8), g = abGain(e.rotation);
        return card(gainTitle(`${JOB[e.job] || e.job} casts against clearers`, g), `Their GCD ${e.rotation.gcd ? e.rotation.gcd.toFixed(2) : "–"} s, clearers' ${e.rotation.clear_gcd ? e.rotation.clear_gcd.toFixed(2) : "–"} s; GCD skills compared at their speed.${gainNote(g, "worth of every skill, extra casts offsetting missing ones")}`,
          short.length ? hbarChart(short.map(a => ({ label: `${a.name} ${a.ours.toFixed(1)} vs ${a.clears.toFixed(1)}/min`, value: a.worth })), { fmt: v => `${num(Math.round(v))} DPS` })
            : () => el("div", { class: "empty" }, "They cast every skill at least as often as the clearers."),
          () => tableOf(["Skill", "", "Them /min", "Clearers /min", "Worth"], A.map(a => [a.name, a.gcd ? "GCD" : "oGCD", a.ours.toFixed(2), a.clears.toFixed(2),
            a.worth == null ? "–" : `${a.worth >= 0 ? "" : "−"}${num(Math.abs(Math.round(a.worth)))} DPS`]), 2));
      })));
  }
  // side by side when both have something, else in the page's one column
  if (left.childNodes.length && right.childNodes.length) app.append(el("div", { class: "cols" }, left, right));
  else app.append(...left.childNodes, ...right.childNodes);
  app.append(heading("h2", "Every mistake", "Confidence: how sure the classifier's reading of the log is. Mistakes per pull and Wipes count each mistake in full, or their share of it where the classifier could not tell several players apart (shown as ½ share)."),
    el("div", { class: "table-wrap" }, mine.length ? el("table", {},
    el("thead", {}, el("tr", {}, ["Pull", "Time", "Mechanic", "What happened", "Confidence", "", "Practice"].map((h, i) => el("th", { class: i < 2 ? "num" : null }, h)))),
    el("tbody", {}, mine.map(m => el("tr", {}, el("td", { class: "num" }, el("a", { href: `#/day/${day}/${group}/pulls/${m.pull}` }, String(m.pull))), el("td", { class: "num" }, mmss(m.t)), el("td", {}, shortMech(m.mechanic || "")),
      el("td", { class: "wrap" }, whatHappened(m, name)), el("td", {}, confCell(m.conf), shareCell(m.share)), el("td", { class: "muted" }, wiped.some(q => q.n === m.pull && Math.abs(q.wipe.t - m.t) < 2.5) ? "lost the pull" : ""),
      el("td", {}, drillLinks(m.mechanic) || "")))))
    : el("div", { class: "empty", style: "padding:14px" }, "No mistakes recorded.")));
  // every death of theirs: what killed them, why, and whose mistake it was
  const died = r.pulls.flatMap(q => (q.death_list || []).filter(d => d.who === name).map(d => ({ ...d, pull: q.n })));
  const before = died.filter(d => !d.when), own = before.filter(d => d.culprits.includes(name)).length,
    others = before.filter(d => d.culprits.length && !d.culprits.includes(name)).length;
  const inGroup = new Set(r.players.map(q => q.name));
  const culprit = d => !d.culprits.length ? el("span", { class: "muted" }, "none found")
    : names(d.culprits.map(c => [c === name ? "self" : inGroup.has(c) ? el("a", { href: `#/day/${day}/${group}/${encodeURIComponent(c)}` }, c) : c, shareOf(d.shares, c)]));
  app.append(heading("h2", "Deaths", "Every death of theirs, pull by pull: the hit that killed them, what the classifier says happened, and whose mistake it was (self: their own; none found: no rule explains it, often healing or mitigation, or fallout of an earlier death), with how sure it is of the culprit. Decided the wipe: the death, or the mass death, that lost the pull. After the wipe: the collapse once the pull was already lost, where deaths are forced. Saved the pull: they died holding what would otherwise have lost it (a Superchain I tower held in its Strong Soul's place)."),
    el("p", { class: "lede" }, r.pulls.some(q => q.death_list) ? `${died.length} deaths in ${p.pulls} pulls; ${before.length} before the pull was lost: ${own} their own mistake, ${others} someone else's, ${before.length - own - others} no culprit found.`
      : "Not recorded for this report yet: rebuild the site (build_site.py --reanalyse)."),
    el("div", { class: "table-wrap" }, died.length ? el("table", {},
      el("thead", {}, el("tr", {}, ["Pull", "Time", "Mechanic", "Killed by", "What happened", "Culprit", "Confidence", ""].map((h, i) => el("th", { class: i < 2 ? "num" : null }, h)))),
      el("tbody", {}, died.map(d => el("tr", { class: d.when === "after" ? "muted" : null },
        el("td", { class: "num" }, el("a", { href: `#/day/${day}/${group}/pulls/${d.pull}` }, String(d.pull))), el("td", { class: "num" }, mmss(d.t)),
        el("td", {}, shortMech(d.mechanic || "")), el("td", {}, d.ability || "?"), el("td", { class: "wrap" }, deathLink(r, d), whatHappened(d)), el("td", {}, culprit(d)),
        el("td", {}, d.culprits.length ? confCell(d.confidence) : ""),
        wipeCell(d)))))
      : el("div", { class: "empty", style: "padding:14px" }, "No deaths recorded.")));
  app.append(heading("h2", "Across raid days", "Their mistakes by mechanic over every raid day, night by night, and their trends are on their summary page."),
    el("p", { class: "lede" }, el("a", { href: playerHref(name) }, `${name} over all raid days →`)));
}

// one pull: every player's pull_detail entry for it
const inPull = (r, n) => r.players.flatMap(p => (p.pull_detail || []).filter(x => x.n === n).map(x => ({ p, x })));
const pullEnd = p => p.kill ? "Kill" : p.wipe ? `${p.wipe.label}${p.wipe.culprits.length ? ` (${p.wipe.culprits.map(c => c + shareOf(p.wipe.shares, c)).join(", ")})` : ""}` : "–";
const pullHref = (day, group, n) => `#/day/${day}/${group}/pulls/${n}`;

function pullsPage(day, group) {
  const r = findGroup(day, group);
  if (!r) return notFound();
  crumbs([["Raid days", "#/"], [dayName(day), `#/day/${day}`], [group, `#/day/${day}/${group}`], ["Pulls", null]]);
  const app = document.getElementById("app");
  const rows = r.pulls.map(p => {
    const ps = inPull(r, p.n), dm = ps.filter(q => q.x.dmg != null), rl = ps.filter(q => q.x.loss != null);
    return { p, dmg: dm.length ? dm.reduce((s, q) => s + q.x.dmg, 0) / dm.length : null,
      loss: rl.length ? rl.reduce((s, q) => s + q.x.loss, 0) : null, died: ps.filter(q => q.x.died).length };
  });
  app.append(heading("h1", `Pulls · ${group} · ${dayName(day)}`, "Pick a pull to see it player by player. Party damage is the average of the players' nDPS against clearers on their jobs over the phases they were alive through; party rotation loss adds up their rotation checks against clearers, in DPS."),
    el("p", { class: "lede" }, `${r.pulls_total} pulls.`));
  const tip = q => [`Pull ${q.p.n} · ${mmss(q.p.dur)}`, [[q.dmg != null ? signed(q.dmg) : "–", "party damage vs clearers", true],
    [q.loss != null ? `${num(q.loss)} DPS` : "–", "party rotation loss"], [pullEnd(q.p), "ended"]]];
  app.append(el("div", { class: "grid" },
    card("Party damage vs clearers per pull", info("Grey dot: nobody was alive through a whole phase."),
      divColumns(rows.map(q => ({ label: String(q.p.n), v: q.dmg, tip: tip(q) })), { fmt: v => signed(v), limit: 0.1 }),
      () => tableOf(["Pull", "Party damage"], rows.map(q => [String(q.p.n), q.dmg != null ? signed(q.dmg) : "–"]))),
    card("Party rotation loss per pull", info("Red: lost against the clearers; blue: did better."),
      divColumns(rows.map(q => ({ label: String(q.p.n), v: q.loss, tip: tip(q) })), { fmt: v => num(Math.round(v)), limit: 1500, invert: true }),
      () => tableOf(["Pull", "Party rotation loss"], rows.map(q => [String(q.p.n), q.loss != null ? `${num(q.loss)} DPS` : "–"])))));
  const go = n => (location.hash = pullHref(day, group, n));
  app.append(el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, ["Pull", "Length", "Boss HP", "Ended", "Mistakes", "Died before the wipe", "Lost to deaths", "Party damage", "Rotation loss"]
      .map((h, i) => el("th", { class: i === 3 ? null : "num" }, h)))),
    el("tbody", {}, rows.map(q => el("tr", { class: "link", tabindex: "0", on: { click: () => go(q.p.n), keydown: e => { if (e.key === "Enter") go(q.p.n); } } },
      el("td", { class: "num" }, String(q.p.n)), el("td", { class: "num" }, mmss(q.p.dur)),
      el("td", { class: "num" }, q.p.boss != null ? `${q.p.boss.toFixed(1)}%` : "–"), el("td", { class: "wrap" }, pullEnd(q.p)),
      el("td", { class: "num" }, String(q.p.mistakes.length)), el("td", { class: "num" }, String(q.died)),
      el("td", { class: "num" }, q.p.lost != null ? hpfmt(q.p.lost) : "–"), el("td", { class: "num" }, q.dmg != null ? signed(q.dmg) : "–"),
      el("td", { class: "num" }, q.loss != null ? `${num(q.loss)} DPS` : "–")))))));
}

function pullPage(day, group, n) {
  const r = findGroup(day, group), p = r && r.pulls.find(q => q.n === n);
  if (!p) return notFound();
  crumbs([["Raid days", "#/"], [dayName(day), `#/day/${day}`], [group, `#/day/${day}/${group}`], ["Pulls", `#/day/${day}/${group}/pulls`], [`Pull ${n}`, null]]);
  const app = document.getElementById("app"), ps = inPull(r, n);
  const nav = pager(r.pulls.some(q => q.n === n - 1) && [`Pull ${n - 1}`, pullHref(day, group, n - 1)], r.pulls.some(q => q.n === n + 1) && [`Pull ${n + 1}`, pullHref(day, group, n + 1)]);
  if (p.id != null) nav.append(el("span", { class: "muted" }, "  ·  "), el("a", { href: `https://www.fflogs.com/reports/${encodeURIComponent(r.code)}?fight=${p.id}`, target: "_blank", rel: "noopener" }, "This pull on FFLogs ↗"));
  app.append(el("h1", {}, `Pull ${n} · ${group} · ${dayName(day)}`), nav);
  app.append(tiles([
    ["Length", mmss(p.dur), p.kill ? "kill" : `boss at ${p.boss != null ? p.boss.toFixed(1) : "–"}%`],
    ["Ended", p.kill ? "Kill" : p.wipe ? mmss(p.wipe.t) : "–", p.wipe ? `${p.wipe.label}${p.wipe.culprits.length ? ` · ${p.wipe.culprits.map(c => c + shareOf(p.wipe.shares, c)).join(", ")}` : ""}` : ""],
    ["Mistakes", String(p.mistakes.length), "until the pull was lost"],
    ["Lost to deaths", p.lost != null ? hpfmt(p.lost) : "–", p.lost != null ? secs(p.lost) : ""],
  ]));
  ps.sort((a, c) => ROLES.indexOf(a.p.role) - ROLES.indexOf(c.p.role));
  app.append(heading("h2", "Players", "Damage: nDPS against clearers on the job over the phases they were alive through in this pull. Rotation loss: this pull's rotation checks against clearers over the same stretch, in DPS (negative: better than the clearers). Deaths are shown only when they came before the pull was lost."), el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, ["Player", "Job", "Mistakes", "Died", "Damage", "Rotation loss", "Main rotation issue"]
      .map((h, i) => el("th", { class: i === 4 || i === 5 ? "num" : null }, h)))),
    el("tbody", {}, ps.map(({ p: pl, x }) => el("tr", {},
      el("td", {}, el("a", { href: `#/day/${day}/${group}/${encodeURIComponent(pl.name)}` }, pl.name)), el("td", {}, JOB[pl.job] || pl.job),
      el("td", { class: "wrap" }, x.mistakes.join("; ") || "–"), el("td", { class: "wrap" }, x.died ? `${mmss(x.died.t)} ${x.died.how}` : "–"),
      el("td", { class: "num" }, x.dmg != null ? signed(x.dmg) : "–"), el("td", { class: "num" }, x.loss != null ? `${num(x.loss)} DPS` : "–"),
      el("td", { class: "wrap muted" }, x.loss > 0 ? shortCheck(x.top) : "–")))))));
  const ms = [...p.mistakes].sort((a, c) => a.t - c.t);
  app.append(el("h2", {}, "Mistakes in order"), el("div", { class: "table-wrap" }, ms.length ? el("table", {},
    el("thead", {}, el("tr", {}, ["Time", "Who", "Mechanic", "What happened", ""].map((h, i) => el("th", { class: i === 0 ? "num" : null }, h)))),
    el("tbody", {}, ms.map(m => el("tr", {}, el("td", { class: "num" }, mmss(m.t)), el("td", {}, m.who), el("td", {}, shortMech(m.mechanic || "")),
      el("td", { class: "wrap" }, whatHappened(m, m.who)),
      el("td", { class: "muted" }, p.wipe && Math.abs(p.wipe.t - m.t) < 0.05 && p.wipe.culprits.includes(m.who) ? "lost the pull" : "")))))
    : el("div", { class: "empty", style: "padding:14px" }, "No mistakes recorded.")));
  // every death in the pull, as on the player page
  const died = [...(p.death_list || [])].sort((a, c) => a.t - c.t), inGroup = new Set(r.players.map(q => q.name));
  const link = c => inGroup.has(c) ? el("a", { href: `#/day/${day}/${group}/${encodeURIComponent(c)}` }, c) : c;
  const culprit = d => !d.culprits.length ? el("span", { class: "muted" }, "none found") : names(d.culprits.map(c => [c === d.who ? "self" : link(c), shareOf(d.shares, c)]));
  app.append(heading("h2", "Deaths in order", "Every death in this pull: the hit that killed them, what the classifier says happened, and whose mistake it was (self: their own; none found: no rule explains it, often healing or mitigation, or fallout of an earlier death), with how sure it is of the culprit. Decided the wipe: the death, or the mass death, that lost the pull. After the wipe: the collapse once the pull was already lost, where deaths are forced. Saved the pull: they died holding what would otherwise have lost it (a Superchain I tower held in its Strong Soul's place)."),
    el("div", { class: "table-wrap" }, died.length ? el("table", {},
      el("thead", {}, el("tr", {}, ["Time", "Who", "Mechanic", "Killed by", "What happened", "Culprit", "Confidence", ""].map((h, i) => el("th", { class: i === 0 ? "num" : null }, h)))),
      el("tbody", {}, died.map(d => el("tr", { class: d.when === "after" ? "muted" : null },
        el("td", { class: "num" }, mmss(d.t)), el("td", {}, link(d.who)), el("td", {}, shortMech(d.mechanic || "")), el("td", {}, d.ability || "?"),
        el("td", { class: "wrap" }, whatHappened(d)), el("td", {}, culprit(d)), el("td", {}, d.culprits.length ? confCell(d.confidence) : ""),
        wipeCell(d)))))
      : el("div", { class: "empty", style: "padding:14px" }, p.death_list ? "No deaths recorded." : "Not recorded for this report yet: rebuild the site (build_site.py --reanalyse).")));
}

// ---------- the optimizer's rotations (tools/rotation/dps.py --site): per job, one per GCD it was searched at ----------
const rotsOf = job => ((DATA.rotations || {})[job] || {}).rotations;
const fightOf = job => ((DATA.rotations || {})[job] || {}).fight;
const jobOf = code => Object.keys(JOB).find(j => JOB[j] === code) || code;
const jobName = job => job.replace(/([a-z])([A-Z])/g, "$1 $2");
const jobIcon = (job, cls = "job-icon") => { const src = ((DATA.rotations || {})[job] || {}).job_icon;   // decorative: the name is beside it
  return src ? el("img", { class: cls, src, alt: "", draggable: "false" }) : null; };
const rotHref = (job, key) => `#/rotations${job ? `/${JOB[job] || job}` : ""}${key ? `/${key}` : ""}`;
const speedStat = job => ["BlackMage", "Summoner", "RedMage", "Pictomancer", "WhiteMage", "Scholar", "Astrologian", "Sage"].includes(job) ? "Spell Speed" : "Skill Speed";
const rotLabel = x => `${x.gcd.toFixed(2)} s GCD${x.crit != null ? ` · ${Math.round(100 * x.crit)}% crit` : ""}`;
const rotClock = t => t < 0 ? `−${Math.abs(t).toFixed(1)} s` : `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, "0")}`;   // pre-cast before the pull
// what P1 until Palladion asks of each job under our strategy, from the optimizer's findings (tools/rotation/README.md):
// a line, then [where, what, stretches] points; stretches are what the point marks on the fight timeline while hovered:
// a lane's bands ("away", "pinned") or [from, to] in seconds. "Cost" figures are the best rotation over the whole phase
// against standing still
const ROT_CHALLENGES = {
  BlackMage: ["The most running of the hard casters: 36 s of Movement before Palladion (26 s from our raidplan), each run out of Ley Lines.", [
    ["Paradeigma I", "R1 runs to the wall end of the bait line (3.1 s from 0:27), then swaps 28 y through the middle (4.7 s in the 5.3 s band from 0:37). Save instants for the swap: Paradox, with Xenoglossy or a Firestarter Fire III.", [[27.3, 42.9]]],
    ["Ley Lines", "Nearly every Movement band takes you out of it: run as late as the band allows, then Between the Lines back."],
    ["Superchain I", "Five 7–15 y runs in 28 s from 1:58: slidecasts and instants cover them.", [[118.3, 146.6]]],
    ["Cost", "~1% against standing still (R1; 0.9% in R2)."]]],
  Reaper: ["Few casts to protect: the cost is positionals and reach.", [
    ["Spot fixed", "Paradeigma I–III and Superchain I fix your spot (orange bands, 77 s): both True North charges go here, for Gibbet and Gallows.", ["pinned"]],
    ["Out of reach", "2.5 s on end between 2:53 and Paradeigma III's tethers, and 1.2 s before Palladion: Harpe, Harvest Moon or Communio fill them.", ["away"]],
    ["Cost", "~1.3% against standing still, mostly the order bending around the fixed spots."]]],
  Monk: ["Nothing reaches past melee range, so fixed spots and time out of reach are the cost.", [
    ["Spot fixed", "Paradeigma I–III and Superchain I fix your spot (orange bands, 77 s): six True Norths keep Snap Punch's flank and Demolish's rear.", ["pinned"]],
    ["Out of reach", "2.5 s on end between 2:53 and Paradeigma III's tethers, and 1.2 s before Palladion: step out right after Phantom Rush and meditate twice.", ["away"]],
    ["Burst", "Brotherhood at 0:01, 2:02 and 4:03; eight Perfect Balances by Palladion."],
    ["Crit rate", "Each GCD is searched at our players' crit rates: 5 points more crit is ~0.5–0.8% more potency through The Forbidden Chakra."],
    ["Six-Sided Star", "Only as Athena leaves (4:40); anywhere else it about ties.", [[278.4, 281.6]]],
    ["GCD", "Over the phase, 2.40–2.45 s at 23–25% crit come out within 0.5% of each other; crit decides: the best-in-slot 2.43 s at its 28% comes out best, 2.45 s at 30% ~0.4% below (within the search's noise), 2.40–2.45 s at 23–25% ~1.5–1.7% below."],
    ["Cost", "~1.3% (M1) to 1.8% (M2) against standing still, within noise of each other."]]],
  Bard: ["All instant at 25 y: R1, R2 and standing still play the same rotation.", [
    ["Songs", "The Minuet every two minutes (0:01, 2:01–2:06, 4:01–4:06) with Raging Strikes, Battle Voice and Barrage. Ballad and Paeon fill the minute between in either order, a near-tie.", [[0, 18.0], [120.8, 143.9], [241.1, 264.2]]],
    ["Radiant Finale", "Barely moves your own damage, so the searches place it anywhere; its party share isn't in the optimizer, so in a party put it with Battle Voice (as at 2.45 s)."],
    ["Palladion", "The third Minuet burst (4:01–4:06) ends before Athena leaves (4:41).", [[241.1, 281.6]]],
    ["GCD", "Over the phase, 2.50 s comes out ~0.9–1.5% above 2.45, 2.47 and 2.49 s."]]],
  Dragoon: ["Positionals are what the mechanics squeeze.", [
    ["Spot fixed", "Paradeigma I–III and Superchain I fix your spot (orange bands, 77 s): five or six True Norths (by GCD) keep the combo's positionals, with Chaotic Spring and Power Surge kept up through them.", ["pinned"]],
    ["Out of reach", "2.5 s on end between 2:53 and Paradeigma III's tethers, and 1.2 s before Palladion: Elusive Jump into an Enhanced Piercing Talon fills them.", ["away"]],
    ["Cost", "~0.6% against standing still."]]],
  RedMage: ["Paradeigma I is the hard part: a far spot and a long run while the opener's cooldowns are still away.", [
    ["Paradeigma I", "R1 runs to the wall end, 18.3 y from Athena's centre and out of melee reach (red, 0:37), then swaps 28 y (4.7 s in the 5.3 s band from 0:37.6). Swiftcast, Acceleration and Manafication are all on cooldown: run on Enchanted Reprise (two at 2.45 and 2.49 s) or Corps-a-corps.", [[27.3, 42.9]]],
    ["Corps-a-corps", "From the wall right after the bait (0:37.6) it saves ~1.3 s of the swap, room for a hard cast, if a charge is back: at 2.23 s one is, just in time (0:37.7); at 2.45–2.49 s the opener's two uses come out ahead.", [[37.6, 42.9]]],
    ["R2", "Crosses the middle first, and Displacement can't save a hard cast on the way (a backstep has to land on the platform: the edge is a drop): ~0.6% against standing still; R1 is within noise of it (the timeline shows R1)."],
    ["Superchain I", "The spread's Heavensflame corner is 21.5 y out (red, 2:25): finish the melee combo first and land Verholy, Scorch and Resolution on the way.", [[143.5, 147.9]]]]],
  Viper: ["The melee job the fight costs least: ~0.4% against standing still.", [
    ["Spot fixed", "Paradeigma I–III and Superchain I fix your spot (orange bands, 77 s): five or six True Norths cover the finishers' positionals.", ["pinned"]],
    ["Out of reach", "2.5 s on end between 2:53 and Paradeigma III's tethers, and 1.2 s before Palladion: Uncoiled Fury and the twinblades fill them, so keep a Rattling Coil for leaving.", ["away"]],
    ["Reawaken", "Keep it out of the red bands: its Generations need you within 5 y.", ["away"]]]],
  Samurai: ["Runs and fixed spots cost little; plan the time out of reach and Palladion.", [
    ["Spot fixed", "Paradeigma I–III and Superchain I fix your spot (orange bands, 77 s): True North takes Gekko's and Kasha's positionals.", ["pinned"]],
    ["Out of reach", "2.5 s on end between 2:53 and Paradeigma III's tethers, and 1.2 s before Palladion, worth ~0.5%: Enpi under Yaten fills them; Iaijutsu, Ogi Namikiri and Shoha may still land a little farther out.", ["away"]],
    ["Palladion", "Let Higanbana run out before Athena leaves (4:41) rather than refresh it into the 44 s downtime.", [[261.4, 281.6]]],
    ["Cost", "~0.8% against standing still."]]],
  Pictomancer: ["Short casts and many instants make our runs cheap; P1 costs Inspiration in Superchain I and motif time.", [
    ["Paradeigma I", "R1 runs to the wall end (3.1 s from 0:27), then swaps 28 y (4.7 s in the 5.3 s band from 0:37.6). Use the second Striking Muse's hammers and Holy in White: paint the hammer just before (Swiftcast on Hammer Motif at 2.31 and 2.49 s) so all three land in the bands.", [[27.3, 42.9]]],
    ["Smudge", "In the swap (0:38–0:39): it covers 15 y, room for a hard cast before the band ends.", [[37.6, 42.9]]],
    ["Starry Muse in Superchain I", "The second one (2:02–2:09) meets Superchain I: the 15 y run into the second doughnut (from 2:09.6) leaves its ~8 y landscape, so only one or two colour spells get Inspiration, against four at 0:02 and 4:05–4:10. Spend the stacks before that run.", [[122.3, 136.8]]],
    ["Motifs", "Spell Speed doesn't shorten them. Swiftcast goes on a motif (or a hard cast in a run); repaint pom or wings as soon as a Living Muse charge is back."],
    ["GCD", "Over the phase, 2.49 s comes out ~2.5% above 2.31 s: motifs don't speed up."],
    ["Palladion", "Spend White Paint on Holy and Comet before Athena leaves (4:41).", [[261.4, 281.6]]],
    ["Cost", "~0.5% in R1 (~1% in R2), half of it Inspiration lost in Superchain I."]]],
  Machinist: ["All instant at 25 y: R1, R2 and standing still play the same rotation. Fit the burst and the Queen around Palladion.", [
    ["Wildfire", "With a Hypercharge every two minutes: 0:08 (on Barrel Stabilizer's), ~2:10 and 4:11–4:14.", [[8.0, 18.7], [130.9, 141.6], [254.1, 264.8]]],
    ["Queen", "~24 potency per battery point, whenever she goes: send her at 50+ before overcapping, but not in the last 17 s before Palladion. The last one goes ~4:00–4:08; hold the 50 that builds after it for Athena's return.", [[264.2, 281.6]]],
    ["Palladion", "The last Reassemble goes on a tool just before Athena leaves (4:41).", [[261.4, 281.6]]],
    ["GCD", "Over the phase, 2.49 s comes out ~0.8% above 2.45 s and ~1.8% above 2.41 s."]]],
  Ninja: ["Nothing is a hard cast and ninjutsu reach 20 y: our runs cost ~0.4%, about the optimizer's noise. Keep the mudras turning and the burst inside Trick Attack.", [
    ["Opener", "Suiton at the pull, Trick Attack and Dokumori; Ten Chi Jin, Bunshin and Kassatsu into Hyosho Ranryu follow in an order that varies by GCD (near-ties), all inside Trick Attack.", [[0, 16.5]]],
    ["Spot fixed", "Paradeigma I–III and Superchain I fix your spot (orange bands, 77 s): five or six True Norths (by GCD) for Aeolian Edge, Armor Crush and Trick Attack.", ["pinned"]],
    ["Out of reach", "2.5 s on end between 2:53 and Paradeigma III's tethers, and 1.2 s before Palladion: mudras and their ninjutsu, or Phantom Kamaitachi, fill them.", ["away"]],
    ["Palladion", "The last burst (4:03–4:15) lands well before Athena leaves (4:41); end on a Raiton, and its Raiju where it fits.", [[243.0, 281.6]]],
    ["GCD", "Over the phase, 2.50 s comes out ~3% above 2.41 s."],
    ["Expected DPS", "None of ours plays Ninja: converted at the four clear Ninjas since 7.3 (three within 2%, one 13% lower, likely gear; one Echo kill divided by 1.2)."]]],
  Summoner: ["Ruin III slidecasts and the rest is instant: our runs cost next to nothing (0.05%, noise). Spend every Arcanum between demi-summons and fit the last cycle before Palladion.", [
    ["Demi-summons", "Spell Speed shortens their 60 s (58.8 s at 2.45, 55.4 s at 2.31): five by Palladion."],
    ["Primals", "Titan, Ifrit and Garuda in any order (a near-tie); summon the next only once the last one's Rites and Favor are spent."],
    ["Crimson Cyclone", "It rushes you to Athena: keep Ifrit's Favor out of Paradeigma I–III and Superchain I, where our raidplan fixes your spot.", [[27.3, 42.9], [67.6, 82.7], [118.3, 146.6], [207.2, 225.3]]],
    ["Swiftcast", "On a Ruby Rite, Slipstream or Ruin III: no Movement band needs it."],
    ["Searing Light", "On cooldown: 0:02–0:05, 2:02–2:06 and 4:04–4:07.", [[2.1, 24.7], [122.5, 146.2], [243.8, 267.0]]],
    ["Out of reach", "Crimson Strike reaches only 3 y past Athena's hitbox: not at the red bands' far spots (0:37 in R1, 2:25 in Superchain I's spread).", ["away"]],
    ["Palladion", "After the ~4:00 trance, Titan and Ifrit fit before Athena leaves (4:41) but Garuda doesn't, or only just starts (2.41 s); with its earlier demi, 2.31 s fits all three.", [[239.1, 281.6]]],
    ["GCD", "Over the phase, the best-in-slot 2.10–2.14 s come out ~0.5% above 2.49 s and ~1.7% above 2.31 s."]]],
  Dancer: ["All instant at 15–25 y: our runs cost nothing. Keep the dances turning and pour Esprit and feathers into the two-minute windows.", [
    ["Opener", "Standard Step ~14 s before the pull, the finish at the pull, then Flourish, Devilment and Technical Step; the next Standard Step goes inside the window at 0:18.", [[0, 24.5]]],
    ["Technical Step", "On cooldown: 0:04, 2:04–2:07 and 4:06–4:07. Its window brings the whole party's Esprit: Saber Dances almost back to back.", [[3.9, 30.5], [124.0, 147.0], [246.6, 268.5]]],
    ["Devilment", "Just before the Step or right after the finish ties for your own damage; after the finish is better for the party, since your partner gets it too."],
    ["Standard Step", "Every ~32 s, not quite on cooldown: eight or nine by Palladion. Each dance beats the two GCDs it takes."],
    ["Esprit", "The party's share is random; the optimizer counts its average (~0.7 a second from your partner, six times that from everyone under Technical Finish), so spend Saber Dance by your gauge, not its schedule."],
    ["Palladion", "Tillana and the last Saber Dances go before Athena leaves (4:41); in the downtime, dance the next Standard Step so its finish lands as she returns.", [[259.0, 281.6]]],
    ["GCD", "2.40, 2.45 and 2.49 s come out within 1.5%."],
    ["Raid buffs", "Technical Finish, and Standard Finish and Devilment on your partner, add to others' damage: rDPS credits that to you (the rDPS column); the rotation optimizes your own."]]],
};
// the job's points against its fight: [[key, from, to]] for the timeline to draw hidden, one key per point
function challengeFocus(job, f) {
  const c = ROT_CHALLENGES[job];
  if (!c || !f) return [];
  return c[1].flatMap(([, , at], k) => (at || []).flatMap(a => a === "away" || a === "pinned" ? f[a].map(x => [k, x[0], x[1]]) : [[k, a[0], a[1]]]));
}
// mark a point's stretches on the timeline (and the point itself) while it is hovered, focused or tapped
function focusOn(li, k) {
  const set = on => { li.classList.toggle("on", on); document.querySelectorAll(`.focus-band[data-k="${k}"]`).forEach(r => r.classList.toggle("on", on)); };
  li.addEventListener("mouseenter", () => set(true)); li.addEventListener("mouseleave", () => set(false));
  li.addEventListener("focus", () => set(true)); li.addEventListener("blur", () => set(false));
  li.addEventListener("click", () => set(!li.classList.contains("on")));
}
function rotChallenges(job, f) {
  const c = ROT_CHALLENGES[job];
  if (!c) return el("p", { class: "lede" }, "The optimizer's best rotation at each GCD it was searched at, from the pull until Palladion with our strategy's runs. Pick a GCD for its rotation.");
  const marks = new Set(challengeFocus(job, f).map(x => x[0]));
  return el("div", { class: "lede challenges" }, el("p", {}, c[0], marks.size ? " Hover or tap a point to mark it on the timeline." : ""),
    el("ul", {}, c[1].map(([where, what], k) => {
      const li = el("li", marks.has(k) ? { tabindex: "0", "data-k": k } : {}, el("strong", {}, `${where}. `), what);
      if (marks.has(k)) focusOn(li, k);
      return li;
    })));
}

// a job whose conversion came from the scorecard's cached logs while FFLogs was down (dps.py --offline)
// whose conversion a job's expected DPS is: our players', or the benchmark clears' for a job none of ours plays (dps.py)
const convWho = (job, n, code) => { const r = (DATA.rotations || {})[job] || {}, s = n > 1 ? "s" : "";
  return r.converted_from === "clears" ? `the ${n} ${code} player${s} of the benchmark clears since ${r.converted_since} (none of ours plays ${jobName(job)})` : `our ${n} ${code} player${s}`; };
const offlineNote = job => ((DATA.rotations || {})[job] || {}).offline ? " Converted from cached logs while FFLogs was down (no crit flags or buffs per hit): reads 0–3% high on Black Mage." : "";
const ROT_ABOUT = "The best rotation the optimizer finds for P12S P1 from the pull until Palladion (4:41): no raid buffs, and our raidplan's movement at its worst for the role (the Paradeigma I slot with the most running, each mechanic's heaviest variant). Expected DPS converts its potency at our players' median damage per potency and crit / direct-hit gain, each moved to the rotation's GCD (the speed comes out of their other substats, so a faster GCD converts lower). That is nDPS: your own damage, without others' buffs and without credit for yours. rDPS adds what your raid buffs and debuffs add to others' damage. Players' own 0:00–2:00 ceilings are on their pages. It is the best for your own damage; a party's buff windows can make holding a resource a little longer worth it.";

// the fight under a rotation: major mechanics' starts, the windows in which our strategy needs a run (for the seconds
// shown, somewhere in the window: the optimizer places it), a melee's stretches out of reach and spots fixed by the
// plan, the boss away, and the rotation's GCDs and oGCDs (no rotation: the fight alone, for a job's overview). `focus`,
// [[key, from, to]]: stretches drawn hidden, which a note point marks while hovered (focusOn)
const RUN_KINDS = { runs: ["Movement", "var(--series)"], away: ["Out of reach", "var(--div-neg)"], pinned: ["Spot fixed", "#e0a03a"] };
function fightTimeline(f, rot, focus = []) {
  return width => {
    const narrow = width < 520, L = narrow ? 52 : 92, R = 10, lh = 22, gap = 8, B = 24, w = width - L - R;
    const lanes = ["runs", ...(f.away.length ? ["away"] : []), ...(f.pinned.length ? ["pinned"] : []), ...(rot ? ["gcds"] : [])];
    const x0 = Math.min(0, Math.floor(rot && rot.length ? rot[0][0] : 0)), x1 = f.window;
    const X = t => L + (Math.max(x0, Math.min(x1, t)) - x0) / (x1 - x0) * w;
    // mechanic names above their start lines, each on the first row where it clears the one before (left of its line at
    // the right edge); the lanes start below the rows used
    const ends = [], marks = f.mechanics.map(([t, name]) => {
      const x = X(t), label = shortMech(name), est = label.length * 6.2, left = x + 3 + est > width - 2;
      const a = left ? x - 3 - est : x, b = left ? x : x + 3 + est;
      let row = ends.findIndex(e => a > e + 6); if (row < 0) { row = ends.length; ends.push(0); }
      ends[row] = b;
      return { x, label, left, row };
    });
    const T = 12 + Math.max(2, ends.length) * 13, H = T + lanes.length * (lh + gap) + B, Y = k => T + lanes.indexOf(k) * (lh + gap);
    const svg = sv("svg", { viewBox: `0 0 ${width} ${H}`, role: "img", "aria-label": "Fight timeline" });
    for (let t = 0, step = (x1 > 150 ? 2 : 1) * (narrow ? 30 : 15); t <= x1; t += step)
      svg.append(sv("line", { class: "gridline", x1: X(t), x2: X(t), y1: T - 4, y2: H - B }), sv("text", { x: X(t), y: H - 6, "text-anchor": "middle" }, mmss(t)));
    for (const [a, b] of f.untargetable) svg.append(sv("rect", { x: X(a), y: T - 4, width: X(b) - X(a), height: H - B - T + 4, fill: "var(--zone)" }));
    for (const k of lanes) svg.append(sv("text", { class: "lbl", x: L - 8, y: Y(k) + lh / 2 + 4, "text-anchor": "end" },
      k === "gcds" ? (narrow ? "GCDs" : "Rotation") : narrow ? RUN_KINDS[k][0].replace("Out of reach", "Away").replace("Spot fixed", "Fixed") : RUN_KINDS[k][0]));
    for (const { x, label, left, row } of marks)   // mechanics: a dotted line from each start, its name above
      svg.append(sv("line", { class: "milestone", x1: x, x2: x, y1: 16 + row * 13, y2: H - B }),
        sv("text", { class: "lbl", x: left ? x - 3 : x + 3, y: 12 + row * 13, "text-anchor": left ? "end" : "start" }, label));
    const band = (k, a, b, opacity, text, title, rows) => {
      const x = X(a) + 0.5, bw = Math.max(2, X(b) - X(a) - 1), r = sv("rect", { class: "hit", x, y: Y(k), width: bw, height: lh });
      hover(r, title, rows);
      svg.append(r, sv("rect", { class: "mark", x, y: Y(k), width: bw, height: lh, rx: 3, fill: RUN_KINDS[k][1], "fill-opacity": opacity }));
      if (text && bw > text.length * 6.5 + 6) svg.append(sv("text", { x: x + bw / 2, y: Y(k) + lh / 2 + 4, "text-anchor": "middle",
        style: `fill:${opacity > 0.6 ? "#ffffff" : "var(--ink)"};font-weight:600` }, text));
    };
    const past = hi => hi > x1 ? ` (goes on to ${mmss(hi)})` : "";
    for (const [lo, hi, need, y, mech, what, src] of f.runs)
      band("runs", lo, hi, src.startsWith("plan") ? 0.9 : 0.35, `${need.toFixed(1)} s`, `${mech}: ${what}`,
        [[`${need.toFixed(1)} s`, `of running (${y.toFixed(0)} y) somewhere in ${rotClock(lo)}–${rotClock(hi)}${past(hi)}`, true],
         [src.startsWith("plan") ? "movement" : "movement, pre-position", src.startsWith("plan") ? `our raidplan, ${src.replace("plan, ", "")}` : "between our plan's mechanics: the clears' median path"]]);
    for (const [lo, hi, need, mech] of f.away)
      band("away", lo, hi, 0.8, `${need.toFixed(1)} s`, `${mech}: out of reach`, [[`${need.toFixed(1)} s`, `on end out of melee reach, somewhere in ${rotClock(lo)}–${rotClock(hi)}`, true]]);
    for (const [lo, hi, mech] of f.pinned)
      band("pinned", lo, hi, 0.55, "", `${mech}: spot fixed`, [[`${rotClock(lo)}–${rotClock(hi)}${past(hi)}`, "positionals need True North", true]]);
    for (const [k, a, b] of focus) svg.append(sv("rect", { class: "focus-band", "data-k": k, x: X(a), y: T - 4,
      width: Math.max(3, X(b) - X(a)), height: H - B - T + 4, rx: 2 }));
    if (!rot) return svg;
    // the rotation: a full-height tick per GCD, a short one per oGCD; hover a GCD for what is woven after it
    const gs = rot.map((r, i) => [r, i]).filter(([r]) => r[2] === "g");
    for (const [t, , kind, cast, run] of rot) svg.append(sv("rect", { x: X(t) - (run ? 1.25 : 0.75), y: Y("gcds") + (kind === "g" ? 0 : lh * 0.55), width: run ? 2.5 : 1.5,
      height: kind === "g" ? lh : lh * 0.45, fill: kind !== "g" ? "var(--accent)" : !run ? "var(--ink-2)" : cast ? "var(--series)" : "var(--good)" }));
    gs.forEach(([g, i], k) => {
      const next = gs[k + 1] ? gs[k + 1][0][0] : x1, woven = rot.slice(i + 1, gs[k + 1] ? gs[k + 1][1] : rot.length).map(r => r[1]);
      const hit = sv("rect", { class: "hit", x: X(g[0]), y: Y("gcds"), width: Math.max(1, X(next) - X(g[0])), height: lh });
      hover(hit, `${rotClock(g[0])} · ${g[1]}`, [...(g[4] ? [[`${g[4].toFixed(1)} s`, g[3] ? "running in its slidecast and after it" : "running through it (instant)", true]] : []),
        [woven.length ? woven.join(" · ") : "–", "woven after it"]]); svg.append(hit);
    });
    return svg;
  };
}
// the compact rotation: each GCD's icon on the line with the oGCDs woven after it smaller and raised beside it, wrapped,
// a line for each stretch between major mechanics; a bar under a GCD cast while running, as long as the share of the room
// it leaves for running that the run takes (a dot for a sliver, the icon's width when it is all used)
const SLIDE = 0.46;   // engine.py: a hard cast's last 0.46 s may be run in
function rotationStrip(rows, f, icons) {
  const segs = [{ name: "Opener", t: -Infinity }, ...(f ? f.mechanics.map(([t, n]) => ({ name: shortMech(n), t })) : [])];
  // a GCD's room to run (dps.py placed_runs): until the next GCD starts, outside its cast bar up to the slide point
  const room = new Map(), gs = rows.filter(r => r.gcd);
  gs.forEach((r, i) => room.set(r, (gs[i + 1] ? gs[i + 1].t : f ? f.window : r.t + 2.5) - r.t - Math.max(0, r.cast - SLIDE)));
  const share = r => Math.max(0, Math.min(1, r.run / (room.get(r) || r.run)));
  const icon = (name, cls) => icons[name] ? el("img", { class: cls, src: icons[name], alt: name, draggable: "false" })
    : el("span", { class: `${cls} noicon` }, name.split(/[\s']+/).map(w => w[0]).join("").slice(0, 3));   // no icon: initials
  return el("div", { class: "rot-strip" }, segs.map((sg, i) => {
    const end = i + 1 < segs.length ? segs[i + 1].t : Infinity, mine = rows.filter(r => r.t >= sg.t && r.t < end);
    if (!mine.length) return null;
    return el("div", { class: "rot-seg" }, el("div", { class: "rot-seg-label" }, sg.name, isFinite(sg.t) ? el("span", {}, rotClock(sg.t)) : null),
      el("div", { class: "rot-icons" }, mine.map(r => {
        const g = el("div", { class: `rot-g${r.run ? r.cast ? " moving" : " moving instant" : ""}`, role: "img", "aria-label": [r.gcd, ...r.weaves].filter(Boolean).join(", "),
          style: r.run ? `--run:${share(r).toFixed(3)}` : null },
          r.gcd ? icon(r.gcd, "gcd") : null, ...r.weaves.map(w => icon(w, "ogcd")));
        hover(g, `${rotClock(r.t)} · ${r.gcd || r.weaves.join(" · ")}`, [
          ...(r.gcd ? [[r.cast ? `${r.cast.toFixed(2)} s` : "instant", r.cast ? "cast" : ""]] : []),
          ...(r.run ? [[`${r.run.toFixed(1)} s`, `${r.cast ? "running in its slidecast and after it" : "running through it"}, of ${room.get(r).toFixed(1)} s free (${Math.round(share(r) * 100)}%)`, true]] : []),
          ...(r.gcd && r.weaves.length ? [[r.weaves.join(" · "), "woven after it"]] : [])]);
        return g;
      })));
  }));
}

function fightCard(f, rot, focus) {
  const legend = [
    el("span", {}, el("i", { style: "width:14px;height:10px;border-radius:3px;background:var(--series);opacity:.9" }), "movement"),
    el("span", {}, el("i", { style: "width:14px;height:10px;border-radius:3px;background:var(--series);opacity:.35" }), "movement, pre-position"),
    ...(f.away.length ? [el("span", {}, el("i", { style: "width:14px;height:10px;border-radius:3px;background:var(--div-neg);opacity:.8" }), "out of reach")] : []),
    ...(f.pinned.length ? [el("span", {}, el("i", { style: "width:14px;height:10px;border-radius:3px;background:#e0a03a;opacity:.55" }), "spot fixed")] : []),
    ...(rot ? [el("span", {}, el("i", { style: "width:2px;height:12px;background:var(--ink-2)" }), "GCD"),
      el("span", {}, el("i", { style: "width:3px;height:12px;background:var(--good)" }), "instant GCD, run through"),
      el("span", {}, el("i", { style: "width:3px;height:12px;background:var(--series)" }), "hard cast, run after"),
      el("span", {}, el("i", { style: "width:2px;height:7px;background:var(--accent)" }), "oGCD")] : []),
  ];
  const rows = [...f.mechanics.map(([t, n]) => [rotClock(t), "", "Mechanic", "", n]),
    ...f.runs.map(([lo, hi, need, y, mech, what, src]) => [rotClock(lo), rotClock(hi), src.startsWith("plan") ? "Movement" : "Movement, pre-position", `${need.toFixed(1)} s (${y.toFixed(0)} y)`, `${mech}: ${what}`]),
    ...f.away.map(([lo, hi, need, mech]) => [rotClock(lo), rotClock(hi), "Out of reach", `${need.toFixed(1)} s`, mech]),
    ...f.pinned.map(([lo, hi, mech]) => [rotClock(lo), rotClock(hi), "Spot fixed", "", `${mech}: positionals need True North`]),
    ...f.untargetable.map(([lo, hi]) => [rotClock(lo), rotClock(hi), "Boss away", "", ""])].sort((a, c) => parseClock(a[0]) - parseClock(c[0]));
  return card("Fight timeline", info(`What the rotation${rot ? "" : "s"} play${rot ? "s" : ""} around, slot ${f.slot}. Dotted lines: mechanic starts. Movement: seconds of running our strategy needs somewhere in the band; the optimizer picks when. Dark bands are our raidplan's mechanics; light ones (pre-position) are between them, run as the clears did.${f.away.length ? " Out of reach: that long on end away from the boss, as the clears' melee were." : ""}${f.pinned.length ? " Spot fixed: the plan fixes your spot, so positionals need True North." : ""}${rot ? " Ticks: GCDs (green: instant, run through it; blue: hard cast, run after it) and oGCDs (short); hover a GCD for its running and weaves." : " Each GCD's page draws its rotation here."}`),
    fightTimeline(f, rot, focus), () => tableOf(["From", "To", "What", "Needs", "Detail"], rows, [0, 1, 3]), legend);
}
const parseClock = c => c.startsWith("−") ? -parseFloat(c.slice(1)) : +c.split(":")[0] * 60 + +c.split(":")[1];

function rotationsPage() {
  crumbs([]);   // the header link names the page
  const app = document.getElementById("app"), all = DATA.rotations || {};
  const best = j => bestRot(j).dps, rdps = {};
  const jobs = Object.keys(all).filter(j => Object.keys(rotsOf(j) || {}).length);
  for (const j of jobs) rdps[j] = expectedRdps(j).value;
  jobs.sort((a, c) => rdps[c] - rdps[a]);
  app.append(heading("h1", "Optimized rotations", ROT_ABOUT),
    el("p", { class: "lede" }, "The optimizer's best rotation per job, at our players' GCDs and a few more, grouped by role, highest rDPS to Palladion first."));
  if (!jobs.length) return app.append(el("p", { class: "empty" }, "No optimized rotations yet: run tools/rotation/dps.py --job <job> --site, then build_site.py."));
  const w = `0:00–${mmss(bestRot(jobs[0]).window)}`;
  const head = ["Job", "GCDs", "Fastest", "Slowest", "Best-in-slot GCD", `Best nDPS ${w}`, `Best rDPS ${w}`, "Best rDPS 0:00–2:00"], rows = [];
  for (const role of ROLES) {   // the role's jobs, highest expected rDPS first
    const js = jobs.filter(j => (all[j].role || "Melee") === role);
    if (!js.length) continue;
    rows.push(el("tr", { class: "role" }, el("td", { colspan: head.length }, ROT_ROLES[role] || role)));
    for (const j of js) { const xs = Object.values(rotsOf(j)), g = xs.map(x => x.gcd);
      rows.push(linkRow([[jobIcon(j), jobName(j)], String(xs.length), `${Math.min(...g).toFixed(2)} s`, `${Math.max(...g).toFixed(2)} s`,
        gearOf(j) ? `${gearOf(j).sets[0].stats.base_gcd.toFixed(2)} s` : "–", num(best(j)), num(rdps[j]), num(ceilingRdps(j).value)], rotHref(j))); }
  }
  app.append(...(LOCKED ? [] : [jobsCard(jobs)]), el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, head.map((h, i) => el("th", { class: i ? "num" : null }, h)))), el("tbody", {}, rows))));
}
const ROT_ROLES = { Melee: "Melee DPS", Ranged: "Physical Ranged DPS", Caster: "Magical Ranged DPS" };
const bestRot = job => Object.values(rotsOf(job)).reduce((a, x) => x.dps > a.dps ? x : a);   // by expected nDPS
// our players' figures on the job (build_site.py ours_by_job: clean pulls' rDPS and buffs given, players, their
// ceilings), without names; empty while the published data is locked, so the pages use the clears' instead
const oursOf = job => (DATA.ours || {})[job] || { rdps: [], given: [], players: 0, own: [] };

// the job's best rotation as rDPS: its expected nDPS (to Palladion) plus what the job's raid buffs give the others over
// that stretch. That credit is our players' median over their clean 0:00-2:00 pulls (the clears' mean for a job none
// of ours plays), scaled by how the clears' credit to Palladion compares with their 0:00-2:00 (given_ratio in the
// benchmark: three bursts against one, steady buffs, a party spread at the later bursts; the median over every clear
// player for a job without clears), all of it dealt before Athena leaves. `full`: over the whole phase instead, the
// rotation's dps_full plus the credit scaled by the clears' whole-kill rate (given_ratio_full: Palladion's downtime
// gives nothing)
function expectedRdps(job, x = bestRot(job), full = false) {   // x: one of the job's rotations (the credit is the same at every GCD)
  const cl = DATA.benchmark.pools.clears, c = (cl.jobs || {})[job] || {}, given = oursOf(job).given;
  const from = given.length ? "ours" : c.given != null ? "clears" : null, g120 = given.length ? median(given) : c.given || 0;
  if (full) {
    const ratio = c.given_ratio_full != null ? c.given_ratio_full : cl.given_ratio_full_all || 1, credit = g120 ? g120 * ratio : 0;
    return { value: x.dps_full != null ? x.dps_full + credit : null, ndps: x.dps_full, credit, g120, ratio, from, ratioAll: c.given_ratio_full == null, gcd: x.gcd, window: x.window_full };
  }
  const ratio = c.given_ratio != null ? c.given_ratio : cl.given_ratio_all || 1, credit = g120 ? g120 * ratio * (cl.given_until || x.window) / x.window : 0;
  return { value: x.dps + credit, ndps: x.dps, credit, g120, ratio, from, ratioAll: c.given_ratio == null, gcd: x.gcd, window: x.window };
}

// under a job page's table: what its rDPS columns add to the nDPS
function rdpsNote(job, w, wf) {
  const e = expectedRdps(job), f = expectedRdps(job, bestRot(job), true), who = e.from === "ours" ? "our players' median" : "the clears' mean";
  const all = x => x.ratioAll ? "; no clears of this job, so all clear players'" : "";
  return el("p", { class: "note" }, e.credit
    ? `The rDPS columns add ${jobName(job)}'s raid buffs at every GCD: ${who} credit over 0:00–2:00 (${num(e.g120)}) × the clears' credit over the window against their 0:00–2:00: ` +
      `${wf}: +${num(f.credit)} (× ${f.ratio.toFixed(2)}, Palladion's downtime gives nothing${all(f)}); ${w}: +${num(e.credit)} (× ${e.ratio.toFixed(2)}, three bursts against one${all(e)}).`
    : `${jobName(job)} gives no raid buffs, so its rDPS is its nDPS.`);
}

// the job's 0:00-2:00 ceiling as rDPS, the window our pulls and the clears' cover, plus our players' median 0:00-2:00
// credit for buffs given (the clears' for a job none of ours plays). With the gear model's result (tools/gear/ceiling.py,
// DATA.rotations[job].bis): the rotation for 0:00-2:00 with the best-in-slot set at its best GCD (gear and rotation
// optimized together), nDPS; the band where luck puts two pulls in three (lo / hi: crit and direct hit, and for a job
// whose procs are random, Monk, Bard, Dancer and Red Mage, the procs drawn too: b.procs; older data ±b.sd). Without
// it, the older ceiling: the best of the rotations' own 0:00-2:00 searches at the median conversion, the band the same
// rotation from the weakest to the strongest player's gear (each player's own ceiling against the median's at their
// GCD, for players with BAND_PULLS clean pulls or more; for a job none of ours plays, the clears' dps_lo / dps_hi)
const BAND_PULLS = 5;
function ceilingRdps(job) {
  const all = rotsOf(job), rs = Object.values(all), x = rs.reduce((a, r) => r.ceiling_2min > a.ceiling_2min ? r : a);
  const c = (DATA.benchmark.pools.clears.jobs || {})[job] || {}, { given, own } = oursOf(job);
  const credit = given.length ? median(given) : c.given || 0, from = given.length ? "ours" : "clears";
  const b = (DATA.rotations[job] || {}).bis;
  if (b) return { value: b.ceiling + credit, ndps: b.ceiling, credit, from, gcd: b.gcd, crit: null, bis: b,
    lo: (b.lo != null ? b.lo : b.ceiling - b.sd) + credit, hi: (b.hi != null ? b.hi : b.ceiling + b.sd) + credit,
    bandFrom: b.procs ? "crit, direct-hit and proc luck, two pulls in three" : "crit and direct-hit luck, one standard deviation" };
  const steady = own.filter(o => o.n >= BAND_PULLS), use = steady.length ? steady : own;
  const ends = use.length ? use.map(o => x.ceiling_2min * o.ceiling / all[o.key].ceiling_2min)
    : [x.ceiling_2min * x.dps_lo / x.dps, x.ceiling_2min * x.dps_hi / x.dps];
  return { value: x.ceiling_2min + credit, ndps: x.ceiling_2min, credit, from, gcd: x.gcd, crit: x.crit,
    lo: Math.min(...ends) + credit, hi: Math.max(...ends) + credit,
    bandFrom: use.length ? `${use.length} of our players' gear${steady.length ? ` (${BAND_PULLS}+ clean pulls)` : ""}, at this GCD` : "the clears' gear" };
}

// per job, all rDPS over 0:00-2:00 with tinctures taken out: our players' clean pulls (Echo pulls are not among them),
// the clears' players (each one's mean over their kills) and the 0:00-2:00 ceiling with its band (ceilingRdps)
function jobSpread(jobs) {
  const cl = DATA.benchmark.pools.clears.jobs || {};
  const q = (s, f) => { const i = (s.length - 1) * f, lo = Math.floor(i); return s[lo] + (s[Math.min(lo + 1, s.length - 1)] - s[lo]) * (i - lo); };
  return jobs.map(job => {
    const o = oursOf(job), s = [...o.rdps].sort((a, c) => a - c);
    let box = null;
    if (s.length >= 5) {   // Tukey's box: whiskers to the last pull within 1.5 IQR, the rest are outliers
      const q1 = q(s, 0.25), q3 = q(s, 0.75), k = 1.5 * (q3 - q1);
      box = { q1, med: q(s, 0.5), q3, lo: s.find(v => v >= q1 - k), hi: [...s].reverse().find(v => v <= q3 + k) };
      box.out = s.filter(v => v < box.lo || v > box.hi);
    }
    return { job, role: (DATA.rotations[job] || {}).role || "Melee", n: s.length, players: o.players, s, box,
      top: ceilingRdps(job),
      clears: cl[job] ? (cl[job].rdps_each || []) : [], clearsMean: cl[job] ? cl[job].rdps : null };
  });
}

function jobsCard(jobs) {
  const rows = jobSpread(jobs), lanes = [];
  for (const role of ROLES) {   // grouped like the table, each group by our players' median, highest first
    const rs = rows.filter(r => r.role === role).sort((a, c) => (c.box ? c.box.med : -1) - (a.box ? a.box.med : -1));
    if (rs.length) lanes.push({ head: ROT_ROLES[role] || role }, ...rs);
  }
  const tip = r => [   // each line keyed with its mark in the chart; "k-none" lines break down the line above
    ...(r.box ? [[num(r.box.med), "our median", "k-median"], [`${num(r.box.q1)}–${num(r.box.q3)}`, "middle half of our pulls", "k-box"],
      [`${num(r.s[0])}–${num(r.s[r.s.length - 1])}`, `all ${r.n} clean pulls, ${r.players} player${r.players > 1 ? "s" : ""}`, "k-whisker"]]
      : [r.n ? [`${r.n} pull${r.n > 1 ? "s" : ""}`, "of ours: too few for a box", "k-out"] : ["–", "none of our players plays it", "k-none"]]),
    [num(r.top.value), r.top.bis ? `ceiling 0:00–2:00 (best-in-slot gear at its best GCD, ${r.top.gcd.toFixed(2)} s${r.top.bis.hasted != null ? `, ${r.top.bis.hasted.toFixed(2)} s hasted` : ""})`
      : `ceiling 0:00–2:00 (${r.top.gcd.toFixed(2)} s GCD${r.top.crit != null ? `, ${pct(r.top.crit)} crit` : ""}, median conversion)`, "k-ceil"],
    ...(r.top.credit ? [[num(r.top.ndps), "of it nDPS", "k-none"], [`+${num(r.top.credit)}`, `buffs given: ${r.top.from === "ours" ? "our" : "the clears'"} median over 0:00–2:00`, "k-none"]] : []),
    ...(r.box ? [[pct(r.box.med / r.top.value), "of it at our median", "k-none"]] : []),
    ...(r.top.bis ? [[`${num(r.top.lo)}–${num(r.top.hi)}`, `${signed(r.top.lo / r.top.value - 1, 1)} / ${signed(r.top.hi / r.top.value - 1, 1)}: ${r.top.bandFrom}`, "k-band"],
      ...(r.top.bis.procs ? [[`±${num(r.top.bis.sd)}`, "of it crit and direct hit alone, one standard deviation", "k-none"],
        [`${signed(r.top.bis.procs.p16, 1)} / ${signed(r.top.bis.procs.p84, 1)}`, `procs alone${r.job === "Monk" ? " (with the weaponskill crits that open its chakra)" : ""}, two draws in three (mean ${signed(r.top.bis.procs.mean, 1)}; ${r.top.bis.procs.seeds} draws, played re-planning ${r.top.bis.procs.replan} s ahead)`, "k-none"]] : [])]
      : [[`${num(r.top.lo)}–${num(r.top.hi)}`, `ceiling across ${r.top.bandFrom}`, "k-band"]]),
    ...(r.clears.length ? [[num(r.clearsMean), `clears' mean, ${r.clears.length} player${r.clears.length > 1 ? "s" : ""}: ${r.clears.map(v => kfmt(v)).join(" · ")}`, "k-clear"]] : [["–", "no clears of this job in the benchmark", "k-clear"]])];
  const draw = width => {
    const vals = rows.flatMap(r => [...(r.box ? [r.box.lo, r.box.hi] : r.s), r.top.value, r.top.lo, r.top.hi, ...r.clears]);
    const lab = Math.min(150, width * 0.34), R = 16, T = 6, row = 32, headH = 24, B = 28, w = width - lab - R;
    const step = [250, 500, 1000, 2000].find(s => w / ((Math.max(...vals) - Math.min(...vals)) / s) >= 56) || 2000;
    const x0 = Math.floor(Math.min(...vals) / 250) * 250, x1 = Math.ceil(Math.max(...vals) / 250) * 250;   // ticks on the step inside
    const X = v => lab + (v - x0) / (x1 - x0) * w, inside = v => v >= x0 && v <= x1;
    const H = T + sum(lanes.map(l => l.head ? headH : row)) + B;
    const svg = sv("svg", { viewBox: `0 0 ${width} ${H}`, role: "img", "aria-label": "Our players' rDPS per job against the ceiling and the clears" });
    for (let v = Math.ceil(x0 / step) * step; v <= x1; v += step)
      svg.append(sv("line", { class: "gridline", x1: X(v), x2: X(v), y1: T, y2: H - B }),
        sv("text", { x: X(v), y: H - B + 16, "text-anchor": "middle" }, step < 1000 ? `${(v / 1000).toFixed(1)}k` : `${v / 1000}k`));
    let y = T;
    for (const l of lanes) {
      if (l.head) { svg.append(sv("text", { class: "lbl", x: 0, y: y + headH - 7 }, l.head)); y += headH; continue; }
      const r = l, cy = y + row / 2, by = cy - 4;   // ours on the upper line, the clears just under it
      const hit = sv("rect", { class: "hit link", x: 0, y, width, height: row, rx: 4 });   // first: its hover shade sits under the marks
      hover(hit, jobName(r.job), tip(r));
      hit.addEventListener("click", () => (location.hash = rotHref(r.job)));
      hit.addEventListener("keydown", e => { if (e.key === "Enter") location.hash = rotHref(r.job); });
      const icon = (DATA.rotations[r.job] || {}).job_icon;
      svg.append(hit, ...(icon ? [sv("image", { href: icon, x: 0, y: cy - 9, width: 18, height: 18 })] : []),
        sv("text", { class: "lbl", x: icon ? 24 : 0, y: cy + 4 }, clip(jobName(r.job), lab - 30)),
        sv("rect", { class: "ceil-band", x: X(Math.max(x0, r.top.lo)), y: cy - 13, width: Math.max(2, X(Math.min(x1, r.top.hi)) - X(Math.max(x0, r.top.lo))), height: 26, rx: 3 }));
      if (r.box) {
        const b = r.box;
        svg.append(sv("line", { class: "box-whisker", x1: X(b.lo), x2: X(b.hi), y1: by, y2: by }),
          ...[b.lo, b.hi].map(v => sv("line", { class: "box-whisker", x1: X(v), x2: X(v), y1: by - 4, y2: by + 4 })),
          sv("rect", { class: "box-mid", x: X(b.q1), y: by - 6, width: Math.max(2, X(b.q3) - X(b.q1)), height: 12, rx: 2 }),
          sv("line", { class: "box-med", x1: X(b.med), x2: X(b.med), y1: by - 6, y2: by + 6 }),
          ...b.out.filter(inside).map(v => sv("circle", { class: "box-out", cx: X(v), cy: by, r: 3.5 })));
      } else for (const v of r.s.filter(inside)) svg.append(sv("circle", { class: "box-out", cx: X(v), cy: by, r: 3.5 }));
      for (const v of r.clears.filter(inside)) svg.append(sv("circle", { class: "clear-dot", cx: X(v), cy: cy + 9, r: 4 }));
      if (inside(r.top.value)) svg.append(sv("line", { class: "ceil-tick", x1: X(r.top.value), x2: X(r.top.value), y1: cy - 13, y2: cy + 13 }));
      y += row;
    }
    return svg;
  };
  const anyBis = rows.some(r => r.top.bis), oldBand = rows.filter(r => !r.top.bis).map(r => jobName(r.job));
  const drawn = rows.filter(r => r.top.bis && r.top.bis.procs).map(r => jobName(r.job));
  const table = () => tableOf(["Job", "Our median", "Middle half", "Clean pulls", "Ceiling 0:00–2:00", anyBis ? "Band" : "Across gear", "Our median of it", "Clears' mean", "Clears' players"],
    lanes.filter(l => !l.head).map(r => [jobName(r.job), r.box ? num(r.box.med) : "–", r.box ? `${num(r.box.q1)}–${num(r.box.q3)}` : "–",
      `${r.n} (${r.players} player${r.players === 1 ? "" : "s"})`, num(r.top.value),
      r.top.bis ? `−${num(r.top.value - r.top.lo)} / +${num(r.top.hi - r.top.value)} (luck${r.top.bis.procs ? ", procs" : ""})` : `${num(r.top.lo)}–${num(r.top.hi)} (gear)`, r.box ? pct(r.box.med / r.top.value) : "–",
      r.clearsMean != null ? num(r.clearsMean) : "–", String(r.clears.length)]));
  const legend = [
    el("span", {}, el("i", { style: "width:16px;height:10px;border-radius:2px;background:var(--series)" }), "our players' clean pulls: middle half, median, whiskers"),
    el("span", {}, el("i", { style: "width:2px;height:14px;background:var(--ink)" }), anyBis ? "ceiling 0:00–2:00, best-in-slot gear" : "ceiling 0:00–2:00"),
    el("span", {}, el("i", { class: "ceil-band-key", style: "width:16px;height:12px;border-radius:2px" }), anyBis ? `luck, two pulls in three: crit and direct hit${drawn.length ? `, procs for ${drawn.join(", ")}` : ""}` : "ceiling across players' gear"),
    el("span", {}, el("i", { style: "width:8px;height:8px;border-radius:50%;background:var(--muted)" }), "clears' players")];
  const about = anyBis
    ? "Tick: the ceiling, the optimizer's best rotation for 0:00–2:00 with best-in-slot gear, materia and food at the GCD where gear and rotation together do best (the fight's sync: level 90, level-100 gear synced to item level 660), nDPS, plus our median credit for buffs given. Band: where luck puts about two pulls in three if played perfectly. Crit and direct hit at that set's rates, one standard deviation either side"
      + (drawn.length ? `; for ${drawn.join(", ")} the random procs too (Monk's chakra, Bard's Repertoire and Hawk's Eye, Dancer's procs, feathers and the party's Esprit, Red Mage's Verfire / Verstone), drawn hundreds of times and played by someone re-planning 20 s ahead, against the same player without them. Proc luck needn't be even, so these bands can reach further on one side of the tick than the other.` : ".")
      + (oldBand.length ? ` Not yet computed for ${oldBand.join(", ")}: there, the older ceiling at our players' median conversion, its band across our players' gear.` : "")
    : "Tick: the ceiling, the optimizer's best rotation for 0:00–2:00 at our players' median conversion and best GCD, plus our median credit for buffs given. Band: that ceiling across our players' gear (5+ clean pulls each), moved to its GCD; for a job none of ours plays, the clears' gear. The ceiling is an expected value: a lucky pull beats it by a few percent, more with random procs (Dancer, Red Mage).";
  return card("Our players against the ceiling and the clears", info(`All rDPS over 0:00–2:00, tinctures removed. Box: our players' clean pulls (no death or Damage Down before 2:00, no Echo): middle half, median, whiskers to 1.5 times the box's width, outliers as dots (one far off the scale is only in the tooltip). ${about} Grey dots: the benchmark clears' players, each one's mean. Within a role, jobs go by our median; click one for its rotations.`),
    draw, table, legend);
}

function rotationJobPage(code) {
  const job = jobOf(code), rs = rotsOf(job);
  if (!rs) return notFound();
  crumbs([["Rotations", "#/rotations"], [code, null]]);
  const app = document.getElementById("app"), keys = Object.keys(rs).sort((a, c) => rs[a].gcd - rs[c].gcd || (rs[a].crit || 0) - (rs[c].crit || 0));
  const full = x => x.dps_full != null ? x.dps_full : x.dps;   // (data written before dps_full: to Palladion)
  const best = Math.max(...keys.map(k => full(rs[k]))), crit = keys.some(k => rs[k].crit != null), n = rs[keys[0]].conv_players;
  app.append(heading("h1", [jobIcon(job, "job-icon big"), `${jobName(job)} rotations`], `${ROT_ABOUT} Here: ${keys.length} GCD${keys.length > 1 ? "s" : ""}${crit ? " and crit rates" : ""}, Paradeigma I slot ${(fightOf(job) || {}).slot || "–"}, converted at ${convWho(job, n, code)} (${speedStat(job)} costs ~${(DATA.rotations[job].speed_cost || 0.4).toFixed(2)}% damage per 0.01 s of GCD).${offlineNote(job)}`),
    rotChallenges(job, fightOf(job)));
  if (fightOf(job)) app.append(fightCard(fightOf(job), null, challengeFocus(job, fightOf(job))));
  if (gearOf(job)) app.append(gearCard(job), el("p", { class: "note" }, el("a", { href: gearHref(job) }, "Its DPS by GCD tier, and every job's gear →")));
  const w = `0:00–${mmss(rs[keys[0]].window)}`, wf = `0:00–${mmss(rs[keys[0]].window_full || rs[keys[0]].window)}`;
  const whole = `the row's rotation over the whole phase, to the clears' median kill (${wf})`, cut = `the row's rotation, optimized over the whole phase, scored ${w} (to Palladion)`;
  const head = [["GCD"], ...(crit ? [["Crit", "the crit rate the row is searched at"]] : []),
    [`nDPS ${wf}`, `${whole}: your own damage, at the median of the players it's converted at`], [`rDPS ${wf}`, `${whole}: nDPS plus the credit for your raid buffs`],
    [`nDPS ${w}`, `${cut}: your own damage`], [`rDPS ${w}`, `${cut}: nDPS plus the credit for your raid buffs`],
    [`vs best nDPS ${wf}`, `${whole}, against the row with the most nDPS ${wf}`]];
  app.append(el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, head.map(([h, title], i) => el("th", { class: i ? "num" : null, title: title || null }, h)))),
    el("tbody", {}, keys.map(k => { const x = rs[k];
      const rf = expectedRdps(job, x, true).value;
      return linkRow([[`${x.gcd.toFixed(2)} s`, bisAt(job, x) ? el("span", { class: "tag", title: "the best-in-slot set's GCD" }, "BiS") : null], ...(crit ? [x.crit != null ? pct(x.crit) : "–"] : []),
        x.dps_full != null ? num(x.dps_full) : "–", rf != null ? num(rf) : "–", num(x.dps), num(expectedRdps(job, x).value),
        full(x) === best ? "best" : signed(full(x) / best - 1, 1)], rotHref(job, k)); })))),
    rdpsNote(job, w, wf));
}

function rotationPage(code, key) {
  const job = jobOf(code), x = (rotsOf(job) || {})[key];
  if (!x) return notFound();
  crumbs([["Rotations", "#/rotations"], [code, rotHref(job)], [rotLabel(x).replace(" GCD", ""), null]]);
  const app = document.getElementById("app"), rot = x.rotation, rows = [];
  for (const [t, name, kind, cast, run] of rot) {   // one row per GCD at the time it starts, with the oGCDs woven after it
    if (kind === "g" || !rows.length) rows.push({ t, gcd: kind === "g" ? name : "", weaves: kind === "g" ? [] : [name], cast: cast || 0, run: kind === "g" ? run || 0 : 0 });
    else rows[rows.length - 1].weaves.push(name);
  }
  const nG = rot.filter(r => r[2] === "g").length, nRun = rows.filter(r => r.run).length, casts = {};
  for (const [t, name, kind] of rot) (casts[name] = casts[name] || { name, n: 0, kind, first: t }).n++;
  const castRows = Object.values(casts).sort((a, c) => c.n - a.n || a.first - c.first);
  const waste = Object.entries(x.waste || {}), f = fightOf(job), icons = ((DATA.rotations || {})[job] || {}).icons || {};
  const plan = f ? [...new Map(f.runs.filter(w => w[6].startsWith("plan")).map(w => [w[4], w[6].replace("plan, ", "")])).entries()] : [];
  app.append(heading("h1", `${jobName(job)} at ${rotLabel(x)}`, ROT_ABOUT),
    el("p", { class: "lede" }, `0:00–${mmss(x.window)}, no raid buffs${x.crit != null ? `, ${pct(x.crit)} crit` : ""}, our strategy's runs${plan.length ? ` (${plan.map(([m, v]) => `${shortMech(m)} ${v}`).join(", ")})` : ""}.`));
  if (bisAt(job, x)) app.append(el("p", { class: "note" }, "The best-in-slot set's GCD: ", el("a", { href: gearHref(job) }, "its gear →")));
  if (f) app.append(fightCard(f, rot));
  app.append(tiles([
    [el("span", {}, `nDPS 0:00–${mmss(x.window)}`, help(`nDPS: your own damage, without others' buffs and without credit for yours. The median of ${convWho(job, x.conv_players, code)}, each moved to ${x.gcd.toFixed(2)} s (~${(DATA.rotations[job].speed_cost || 0.4).toFixed(2)}% damage per 0.01 s of ${speedStat(job)}); ${num(x.dps_lo)}–${num(x.dps_hi)} across them.${offlineNote(job)}`)), num(x.dps)],
    [`Potency 0:00–${mmss(x.window)}`, num(x.potency), `${num(x.potency / x.window, 1)} per second`],
    [el("span", {}, "nDPS 0:00–2:00", help("A different rotation: the best for 0:00–2:00 alone (the scorecard's window), nDPS. Player pages and the Rotations chart add the buff credit to compare it with rDPS.")), num(x.ceiling_2min)],
    ["GCDs", String(nG), `with ${rot.length - nG} oGCDs · ${nRun} while running`],
    ["Resources wasted", waste.length ? String(waste.reduce((s2, [, v]) => s2 + v, 0)) : "none", waste.length ? waste.map(([w, v]) => `${w} ×${v}`).join(" · ") : "nothing overcapped or dropped"],
  ]));
  app.append(
    card("Rotation", { info: `${nG} GCDs, a line per stretch between mechanics, the oGCDs woven after each smaller and raised. A bar under a GCD: running before the next one (green: an instant, run through it; blue: a hard cast, run after it), as long as the share of the time free to run it takes: a dot for a sliver, the icon's width when all of it is used. Runs sit as late as their band allows, on instants where they can. Hover an icon for its time and cast; negative times are pre-pull.` },
      () => rotationStrip(rows, f, icons),
      () => { const tbl = tableOf(["Time", "GCD", "Cast", "Running", "Woven after it"], rows.map(r => [rotClock(r.t), r.run ? `▸ ${r.gcd}` : r.gcd,
          r.gcd ? r.cast ? `${r.cast.toFixed(2)} s` : "instant" : "", r.run ? `${r.run.toFixed(1)} s${r.cast ? ", after its cast" : ""}` : "", r.weaves.join(" · ")]), [0, 2, 3]);
        [...tbl.tBodies[0].rows].forEach((tr, i) => { if (rows[i].run) tr.classList.add("moving"); });
        return tbl; },
      [el("span", {}, el("i", { style: "width:16px;height:3px;border-radius:2px;background:var(--good)" }), "instant, run through it"),
       el("span", {}, el("i", { style: "width:16px;height:3px;border-radius:2px;background:var(--series)" }), "hard cast, run in its slidecast and after"),
       el("span", {}, "small, raised: oGCDs woven after the GCD")]),
    el("div", { class: "grid wide" }, card("Casts per skill", info(`Casts per skill over 0:00–${mmss(x.window)}.`),
      hbarChart(castRows.map(c => ({ label: c.name, value: c.n, sub: c.kind === "g" ? "casts (GCD)" : "casts (oGCD)" })), { fmt: v => String(v) }),
      () => tableOf(["Skill", "Casts", "Kind", "First at"], castRows.map(c => [c.name, String(c.n), c.kind === "g" ? "GCD" : "oGCD", rotClock(c.first)]), [1, 3]))));
}

// a player's clean pulls against the optimizer's ceiling at their GCD (tools/rotation), with a link to its rotation
function optCard(e) {
  const x = e.ceiling_key && (rotsOf(e.job) || {})[e.ceiling_key], j = JOB[e.job] || e.job;
  const tops = e.clean_pulls.map(c => ({ c, top: e.ceiling + (c.given || 0) })), of = tops.map(q => q.c.rdps / q.top);
  const gap = tops.length ? median(tops.map(q => q.c.rdps - q.top)) : null;
  const stat = (label, value, sub) => el("div", {}, el("div", { class: "l" }, label), el("div", { class: "v" }, value), sub ? el("div", { class: "s" }, sub) : null);
  return el("figure", { class: "card" },
    el("div", { class: "card-head" }, el("h3", {}, `${j} vs optimized rotation`, help("The ceiling: the highest-damage rotation the optimizer (tools/rotation) finds for 0:00–2:00 (the scorecard's window) at their GCD, with the runs our strategy needs and without anyone's raid buffs, converted to their own DPS (their damage per potency and crit / direct-hit gain). Each pull's share adds what its raid buffs gave the other players, which rDPS credits to them. Median and best are over their clean pulls (no death or Damage Down before 2:00). The rotation page shows the best rotation at their GCD on until Palladion."))),
    el("div", { class: "mini" },
      stat("Median pull", tops.length ? pct(median(of)) : "–", gap != null ? `${gap >= 0 ? "+" : "−"}${num(Math.abs(gap))} DPS` : "no clean pull"),
      stat("Best pull", tops.length ? pct(Math.max(...of)) : "–", tops.length ? `of ${tops.length} clean` : ""),
      stat("Ceiling", tops.length ? num(median(tops.map(q => q.top))) : num(e.ceiling),
        tops.length ? `rDPS at ${e.ceiling_gcd ? e.ceiling_gcd.toFixed(2) + " s" : "their"} GCD: ${num(e.ceiling)} nDPS + ${num(median(tops.map(q => q.c.given || 0)))} from buffs given (median)`
          : `nDPS at ${e.ceiling_gcd ? e.ceiling_gcd.toFixed(2) + " s" : "their"} GCD`)),
    el("a", { href: x ? rotHref(e.job, e.ceiling_key) : rotHref(rotsOf(e.job) ? e.job : null) }, x ? `Rotation at ${rotLabel(x)} →` : "Optimized rotations →"));
}

const echoNote = r => r.echo ? el("p", { class: "warn" }, `The Echo was on in ${r.echo.pulls === r.echo.of ? "all" : `${r.echo.pulls} of`} ${r.echo.of} pulls (+20% damage, HP and healing). Their damage figures are left out: rDPS against clearers, damage by phase, opener damage, party DPS and boss HP checkpoints. Mistakes, deaths and rotation checks still count.`) : "";   // "" appends nothing (null would print "null")

// ---------- best-in-slot gear (tools/gear/sheets.py, from bis.py --combined): the Gear pages and the rotations' job pages ----------
// a set is drawn like the game's character window: weapon and armour on the left, accessories on the right, one line
// per item (name, item level, materia, substats), its stats and food under it; hover an item for the full detail
const gearOf = job => ((DATA.gear || {}).jobs || {})[job];
const gearHref = job => `#/gear${job ? `/${JOB[job] || job}` : ""}`;
const STAT = { wd: ["WD", "Weapon damage"], crit: ["CRT", "Critical hit"], dh: ["DH", "Direct hit rate"], det: ["DET", "Determination"],
  sks: ["SKS", "Skill speed"], sps: ["SPS", "Spell speed"], str: ["STR", "Strength"], dex: ["DEX", "Dexterity"], int: ["INT", "Intelligence"] };
const statOf = (g, k) => STAT[k === "main" ? g.main : k === "speed" ? g.speed : k];   // [short, long]
const SUBS = ["crit", "dh", "det", "speed"];
const SOURCE = { SavageRaid: ["Savage", "Savage raid"], Tome: ["Tome", "Tomestone"], AugTome: ["Aug. tome", "Augmented tomestone"],
  Crafted: ["Crafted", "Crafted"], AugCrafted: ["Aug. crafted", "Augmented crafted"], AllianceRaid: ["Alliance", "Alliance raid"],
  Relic: ["Relic", "Relic weapon"], Dungeon: ["Dungeon", "Dungeon"], ExtremeTrial: ["Extreme", "Extreme trial"], Criterion: ["Criterion", "Criterion dungeon"] };
const sourceOf = i => SOURCE[i.source] || [i.source, i.source];
const DOLL = [["weapon", "head", "body", "gloves", "legs", "feet"], ["ears", "neck", "wrists", "ring"]];
const tierLabel = (g, t) => `${t[0].toFixed(2)} s${t.length > 1 ? ` (${t[1].toFixed(2)} s under ${g.haste || "haste"})` : ""}`;
const itemIcon = (id, cls) => { const src = ((DATA.gear || {}).icons || {})[id];   // decorative: the name is beside it
  return src ? el("img", { class: cls, src, alt: "", draggable: "false" }) : el("span", { class: `${cls} noicon` }); };
// a set at this rotation's GCD (and hasted GCD, where its key has one); the rotations' GCDs are before a trait's haste
const bisAt = (job, x) => { const g = gearOf(job);
  return !!g && g.sets.some(s => Math.abs(s.stats.base_gcd - x.gcd) < 0.005 && (x.hasted == null || s.tier.length < 2 || Math.abs(s.tier[1] - x.hasted) < 0.005)
    && (x.crit == null || Math.abs(s.stats.crit_rate - x.crit) < 0.005)); };   // (Monk: searched at the set's own crit rate)
const GEAR_ABOUT = "The best gear, materia and food per job for P12S phase 1, without tinctures. The fight syncs you to level 90: level-100 gear is cut to item level 660 (every stat at the slot's cap, materia off), level-90 gear keeps its stats and materia (the 665 weapons too). A set is worth what the job's whole-phase rotation deals with it, so gear and rotation are optimized together, one GCD tier at a time (tools/gear/bis.py). Relic: Mandervillous, or the synced Phantom Occultum for jobs without a Mandervillous weapon. GCD tiers within 0.4% of the best are ties (the rotation search moves that much between runs) and get a tab each.";

function matChip(g, m) {   // a materia slot: its stat's colour and short name (IX marked); dashed where the item's cap cuts it
  if (!m) return el("span", { class: "mat empty" }, "–");
  return el("span", { class: `mat m-${m.stat}${m.added < m.value ? " cut" : ""}` }, statOf(g, m.stat)[0] + (m.grade === 9 ? " IX" : ""));
}
function gearTip(g, i) {
  const rows = [[i.synced ? `${i.ilvl} → ${g.sync}` : String(i.ilvl), `item level, ${sourceOf(i)[1]}${i.synced ? ": synced, every stat cut to the slot's cap, materia off" : ""}`]];
  for (const k of ["wd", "main", ...SUBS]) {
    if (!i.final[k]) continue;
    const add = i.final[k] - (i.base[k] || 0);
    rows.push([num(i.final[k]), statOf(g, k)[1] + (add ? i.relic ? " (custom substat)" : ` (${i.base[k] || 0} + ${add} materia)` : "")]);
  }
  if (i.relic) rows.push(["custom", `substats: ${i.relic.large.map(k => statOf(g, k)[1]).join(" and ")} at the cap, ${statOf(g, i.relic.small)[1]} the small one`]);
  for (const m of i.melds) rows.push(m ? [`+${m.added}`, `${m.name}${m.added < m.value ? `: the item's cap cuts it (${m.value} otherwise)` : ""}`, `mk m-${m.stat}`] : ["–", "empty materia slot"]);
  return rows;
}
function gearRow(g, i) {
  const subs = SUBS.filter(k => i.final[k]);
  const mats = i.synced ? [el("span", { class: "gi-off" }, "materia off")]
    : i.relic ? [el("span", { class: "gi-off" }, `custom ${i.relic.large.map(k => statOf(g, k)[0]).join("/")} +${statOf(g, i.relic.small)[0]}`)]
    : i.melds.map(m => matChip(g, m));
  const row = el("div", { class: "gear-item" }, itemIcon(i.id, `gear-icon r${i.rarity}`),
    el("div", { class: "gi-body" },
      el("div", { class: "gi-top" }, el("span", { class: `gi-name r${i.rarity}` }, i.name),
        el("span", { class: "gi-ilvl" }, `${i.synced ? `${i.ilvl}→${g.sync}` : i.ilvl} · ${sourceOf(i)[0]}`)),
      el("div", { class: "gi-sub" }, el("span", { class: "gi-mats" }, mats),
        el("span", { class: "gi-stats" }, subs.map(k => `${statOf(g, k)[0]} ${i.final[k]}`).join(" · ")))));
  hover(row, i.name, gearTip(g, i));
  return row;
}
// one set: the two columns of items, the stat line, food and materia
function gearSetView(g, x) {
  const col = slots => el("div", { class: "gear-col" }, slots.flatMap(s => x.items.filter(i => i.slot === s)).map(i => gearRow(g, i)));
  const st = x.stats, stat = (label, value, sub) => el("div", { class: "gs" }, el("div", { class: "l" }, label), el("div", { class: "v" }, value), sub ? el("div", { class: "s" }, sub) : null);
  const food = el("span", { class: "gf" }, itemIcon(x.food.id, "gf-icon"), el("b", {}, x.food.name),
    Object.entries(x.food.gains).map(([k, v]) => `+${v.got} ${statOf(g, k)[0]}${v.got >= v.max ? " (max)" : ""}`).join(" · "));
  hover(food, x.food.name, Object.entries(x.food.gains).map(([k, v]) => [`+${v.got}`, `${statOf(g, k)[1]}: ${v.pct}% of gear and base, up to ${v.max}`]));
  const mats = el("span", { class: "gf" }, el("span", { class: "muted" }, "Materia"),
    x.materia.map(m => el("span", { class: "gf-m" }, `${m.n}×`, matChip(g, { stat: m.stat, grade: m.grade, added: 1, value: 1 }))));
  if (x.materia.length) hover(mats, "Materia", x.materia.map(m => [`${m.n}×`, m.name, `mk m-${m.stat}`]));
  return el("div", { class: "gear-set" },
    el("div", { class: "gear-doll" }, col(DOLL[0]), col(DOLL[1])),
    el("div", { class: "gear-stats" },
      stat(statOf(g, "main")[0], num(st.main)), stat("WD", num(st.wd)),
      stat("CRT", num(st.crit), `${pct(st.crit_rate, 1)} · ×${st.crit_dmg.toFixed(3)}`), stat("DH", num(st.dh), pct(st.dh_rate, 1)),
      stat("DET", num(st.det), `×${st.det_multi.toFixed(3)}`),
      stat(statOf(g, "speed")[0], num(st.speed), `${st.gcd.toFixed(2)} s GCD${st.hasted != null ? ` · ${st.hasted.toFixed(2)} s ${g.haste || ""}` : st.base_gcd !== st.gcd ? ` · ${st.base_gcd.toFixed(2)} s before traits` : ""}`)),
    el("div", { class: "gear-foot" }, food, x.materia.length ? mats : null));
}
// the gear card: a tab per set (ties), the set, and its table
function gearCard(job) {
  const g = gearOf(job);
  if (!g) return null;
  let cur = 0;
  const holder = el("div", {});
  const table = () => { const x = g.sets[cur];
    return tableOf(["Slot", "Item", "Item level", "Source", "Materia", statOf(g, "main")[0], "WD", ...SUBS.map(k => statOf(g, k)[0])],
      x.items.map(i => [i.slot, i.name, i.synced ? `${i.ilvl} → ${g.sync}` : String(i.ilvl), sourceOf(i)[1],
        i.synced ? "off (synced)" : i.relic ? `custom ${i.relic.large.map(k => statOf(g, k)[0]).join("/")} +${statOf(g, i.relic.small)[0]}`
          : i.melds.map(m => m ? `${statOf(g, m.stat)[0]} ${m.grade === 10 ? "X" : "IX"}${m.added < m.value ? ` (+${m.added})` : ""}` : "–").join(", "),
        ...["main", "wd", ...SUBS].map(k => i.final[k] ? num(i.final[k]) : "–")]), [2, 5, 6, 7, 8, 9, 10]); };
  const show = k => { cur = k;
    holder.replaceChildren(el("p", { class: "summary" }, `${tierLabel(g, g.sets[k].tier)} GCD: ${k ? `${signed(g.sets[k].rel, 2)} against the best, a tie` : g.sets.length > 1 ? "the best tier searched" : "the best of the tiers searched"}.`),
      gearSetView(g, g.sets[k]));
    if (tabs) [...tabs.children].forEach((b, j) => { b.classList.toggle("on", j === k); b.setAttribute("aria-selected", String(j === k)); });
    const t = holder.closest("figure") && holder.closest("figure").querySelector(".table-wrap");
    if (t && t.firstChild) t.replaceChildren(table()); };
  const tabs = g.sets.length > 1 ? el("div", { class: "tabs", role: "tablist", "aria-label": "Sets" }, g.sets.map((x, k) =>
    el("button", { type: "button", role: "tab", on: { click: () => show(k) } }, `${tierLabel(g, x.tier)}${k ? ` · ${signed(x.rel, 2)}` : " · best"}`))) : null;
  show(0);
  const f = card("Best-in-slot gear", info(`${GEAR_ABOUT} Hover an item for its stats, materia and sync. Materia chips: the stat each meld adds (dashed: the item's cap cuts it).`),
    () => holder, table);
  if (tabs) f.insertBefore(tabs, f.querySelector(".chart"));   // above the set and its table alike
  return f;
}
// DPS per GCD tier against the fitted curve's peak: the potency fitted over a grid of GCDs (every tier), the grid's own
// one-round searches and the tiers searched to the end, with the search's noise as a ribbon around the fit, so a
// searched tier off the curve reads as noise; whole phase, no raid buffs, the job's own constant multipliers left out
// (compare within the job only). The table and "best" stay against the best searched set
function tierCard(job) {
  const g = gearOf(job), best = g.sets[0].dps, fits = g.tiers.filter(t => t.fitted != null);
  const ref = fits.length ? Math.max(...fits.map(t => t.fitted)) : best, rel = v => v != null ? v / ref - 1 : null;
  const pts = g.tiers.map(t => ({ t, x: t.tier[0], f: rel(t.fitted), s: rel(t.searched), gr: rel(t.grid) }));
  const curve = pts.filter(p => p.f != null).sort((a, c) => a.x - c.x);
  const draw = width => {
    const H = 210, L = 52, R = 16, T = 30, B = 28, w = width - L - R, h = H - T - B;
    const xs = pts.map(p => p.x), ys = [...pts.flatMap(p => [p.s, p.gr]), ...curve.flatMap(p => [p.f + g.tie, p.f - g.tie])].filter(v => v != null);
    const x0 = Math.min(...xs) - 0.01, x1 = Math.max(...xs) + 0.01, step = 0.005;
    const y0 = Math.floor(Math.min(...ys, -g.tie) / step) * step, y1 = Math.max(0.001, Math.ceil(Math.max(...ys) / step) * step);
    const X = v => L + (v - x0) / (x1 - x0) * w, Y = v => T + (y1 - v) / (y1 - y0) * h;
    const svg = sv("svg", { viewBox: `0 0 ${width} ${H}`, role: "img", "aria-label": "DPS per GCD tier against the fitted curve's peak" });
    if (curve.length > 1)   // the search's noise around the fit
      svg.append(sv("polygon", { class: "ceil-band", points: [...curve.map(p => `${X(p.x)},${Y(p.f + g.tie)}`), ...[...curve].reverse().map(p => `${X(p.x)},${Y(p.f - g.tie)}`)].join(" ") }));
    else svg.append(sv("rect", { class: "ceil-band", x: L, y: Y(g.tie), width: w, height: Y(-g.tie) - Y(g.tie) }));
    for (let v = y0; v <= y1 + 1e-9; v += step)
      svg.append(sv("line", { class: "gridline", x1: L, x2: L + w, y1: Y(v), y2: Y(v) }), sv("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end" }, signed(v, 1)));
    const xstep = (x1 - x0) / 0.05 > Math.max(2, w / 70) ? 0.1 : 0.05;
    for (let v = Math.ceil(x0 / xstep) * xstep; v <= x1; v += xstep) svg.append(sv("text", { x: X(v), y: H - 8, "text-anchor": "middle" }, `${v.toFixed(2)} s`));
    for (const p of pts) {
      const hit = sv("circle", { class: "hit", cx: X(p.x), cy: Y(p.s ?? p.gr ?? p.f), r: 9 });
      hover(hit, `${tierLabel(g, p.t.tier)} GCD`, [...(p.s != null ? [[signed(p.t.searched / best - 1, 2), `searched: ${num(p.t.searched)} DPS, against the best set`, "k-tier-s"]] : []),
        ...(p.gr != null ? [[signed(p.t.grid / best - 1, 2), `grid search (one round): ${num(p.t.grid)} DPS`, "k-tier-g"]] : []),
        ...(p.f != null ? [[signed(p.t.fitted / best - 1, 2), `fitted: ${num(p.t.fitted)} DPS`, "k-tier-f"]] : [])]);
      svg.append(hit);
    }
    for (const p of pts) if (p.f != null) svg.append(sv("circle", { class: "tier-f", cx: X(p.x), cy: Y(p.f), r: 4 }));
    for (const p of pts) if (p.gr != null) svg.append(sv("circle", { class: "tier-g", cx: X(p.x), cy: Y(p.gr), r: 4.5 }));
    for (const p of pts) if (p.s != null) svg.append(sv("circle", { class: "tier-s", cx: X(p.x), cy: Y(p.s), r: 5.5 }));
    const b = pts.find(p => p.t.searched === best);
    if (b) svg.append(sv("text", { class: "lbl", x: X(b.x), y: Y(b.s) - 10, "text-anchor": X(b.x) > L + w - 30 ? "end" : "middle" }, "best"));
    return svg;
  };
  return card("DPS by GCD tier", info(`Each GCD tier's best set with its own rotation, over the whole phase without raid buffs, against the peak of the fitted curve. Grey: the rotation's potency fitted over a grid of GCDs (every tier); hollow: the grid's own searches (one round of set and rotation); blue: tiers searched to the end at their own set's GCD, speed and rates (the fit's best three, and any grid tier within ${pct(g.tie, 1)} of them or above). The band: ±${pct(g.tie, 1)} around the fit, the search's noise, so a point inside it is the curve plus noise. "best" marks the best searched set; sets within ${pct(g.tie, 1)} of it are ties. On Samurai, Viper and Black Mage a GCD can come with two hasted GCDs (hover for both).`),
    draw, () => tableOf(["GCD", "Fitted DPS", "Grid search", "Searched DPS", "Against the best set"], pts.map(p => [tierLabel(g, p.t.tier),
      p.t.fitted != null ? num(p.t.fitted) : "–", p.t.grid != null ? num(p.t.grid) : "–", p.t.searched != null ? num(p.t.searched) : "–",
      signed((p.t.searched ?? p.t.grid ?? p.t.fitted) / best - 1, 2)])),
    [el("span", {}, el("i", { style: "width:8px;height:8px;border-radius:50%;background:var(--muted)" }), "fitted"),
     el("span", {}, el("i", { style: "width:8px;height:8px;border-radius:50%;border:1.5px solid var(--series)" }), "grid search"),
     el("span", {}, el("i", { style: "width:10px;height:10px;border-radius:50%;background:var(--series)" }), "searched"),
     el("span", {}, el("i", { class: "ceil-band-key", style: "width:16px;height:10px;border-radius:2px" }), `noise: ±${pct(g.tie, 1)} around the fit`)]);
}

function gearPage() {
  crumbs([]);   // the header link names the page
  const app = document.getElementById("app"), all = (DATA.gear || {}).jobs || {};
  app.append(heading("h1", "Best-in-slot gear", GEAR_ABOUT),
    el("p", { class: "lede" }, "Each job's best gear, materia and food for P12S P1, found together with its rotation, grouped by role. Pick a job for its set."));
  const jobs = Object.keys(all).sort((a, c) => jobName(a).localeCompare(jobName(c)));
  if (!jobs.length) return app.append(el("p", { class: "empty" }, "No gear sets yet: run tools/gear/bis.py --job <job> --combined, then build_site.py."));
  const head = ["Job", "GCD", "Weapon", "Food", "Crit", "Direct hit", "Determination", "Speed", "Sets"], rows = [];
  for (const role of ROLES) {
    const js = jobs.filter(j => (all[j].role || "Melee") === role);
    if (!js.length) continue;
    rows.push(el("tr", { class: "role" }, el("td", { colspan: head.length }, ROT_ROLES[role] || role)));
    for (const j of js) { const g = all[j], x = g.sets[0], st = x.stats, wpn = x.items.find(i => i.slot === "weapon");
      rows.push(linkRow([[jobIcon(j), jobName(j)], tierLabel(g, x.tier), wpn ? wpn.name : "–", x.food.name,
        `${num(st.crit)} (${pct(st.crit_rate, 1)})`, `${num(st.dh)} (${pct(st.dh_rate, 1)})`, num(st.det), `${statOf(g, "speed")[0]} ${num(st.speed)}`,
        String(g.sets.length)], gearHref(j), 4)); }
  }
  app.append(el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, head.map((h, i) => el("th", { class: i >= 4 ? "num" : null }, h)))), el("tbody", {}, rows))));
}

function gearJobPage(code) {
  const job = jobOf(code), g = gearOf(job);
  if (!g) return notFound();
  crumbs([["Gear", gearHref()], [code, null]]);
  const app = document.getElementById("app");
  app.append(heading("h1", [jobIcon(job, "job-icon big"), `${jobName(job)} best-in-slot gear`], GEAR_ABOUT),
    el("p", { class: "lede" }, `Best at ${tierLabel(g, g.sets[0].tier)} GCD${g.sets.length > 1 ? `, tied with ${g.sets.length - 1} more tier${g.sets.length > 2 ? "s" : ""}` : ""}. `,
      rotsOf(job) ? el("a", { href: rotHref(job) }, `${jobName(job)} rotations →`) : null),
    gearCard(job), el("div", { class: "grid wide" }, tierCard(job)));
}

// every player across the raid days: their jobs, nights and pulls, mistakes and wipes per pull (their shares, as the
// scorecard counts them), overall and on their latest night, which links to their page there
function peopleOf(r) {   // a full record's players, else the progress fragment's summary (build_site.progress_of)
  if (r.players) return [...new Set(r.players.map(p => p.name))].map(n => { const es = r.players.filter(p => p.name === n);
    return { name: n, jobs: es.map(e => e.job), pulls: es[0].pulls, m: es[0].mistakes_w ?? es[0].mistakes, w: es[0].wipes_w ?? es[0].wipes }; });
  return r.people || (r.names || []).map(n => ({ name: n, jobs: [], pulls: null, m: null, w: null }));
}
// a player over every raid day: tiles, their mistakes by mechanic, and their nights one by one (#/player/<name>)
const playerHref = name => `#/player/${encodeURIComponent(name)}`;
const lostAt = q => q.kill ? Infinity : q.wipe ? q.wipe.t : q.dur;   // mistakes count until here, as everywhere
function playerSummary(name) {
  const rs = reports().filter(r => r.players && r.players.some(p => p.name === name)).sort((a, c) => a.day.localeCompare(c.day) || a.group.localeCompare(c.group));
  if (!rs.length) return notFound();
  crumbs([["Players", "#/players"], [name, null]]);
  const app = document.getElementById("app"), B = DATA.benchmark;
  const entries = rs.flatMap(r => r.players.filter(p => p.name === name).map(p => ({ ...p, r })));
  const first = rs.map(r => r.players.find(p => p.name === name));   // per night: counts are the player's, repeated on each job entry
  const pulls = rs.flatMap(r => r.pulls.filter(q => q.players.includes(name)).map(q => ({ ...q, r })));
  const mine = q => (q.mistakes || []).filter(m => m.who === name);
  const shares = q => sum(mine(q).map(m => m.share ?? 1));
  const minutes = sum(pulls.map(q => Math.min(q.dur, q.wipe ? q.wipe.t + 2 : q.dur) / 60));
  const P = sum(first.map(p => p.pulls)), M = sum(pulls.map(shares)), W = sum(first.map(p => p.wipes_w ?? p.wipes));
  const blamedWipes = pulls.filter(q => q.wipe && q.wipe.culprits && q.wipe.culprits.length).length;
  // pulls is the night's count on every job entry; pull_detail has the pulls played on that job
  const jobPulls = {}; for (const e of entries) jobPulls[e.job] = (jobPulls[e.job] || 0) + (e.pull_detail ? e.pull_detail.length : e.pulls);
  const jobs = Object.entries(jobPulls).sort((a, c) => c[1] - a[1]);
  const far = pulls.reduce((a, q) => !a || q.dur > a.dur ? q : a, null);
  const farMech = far && Object.entries(B.mech_start).filter(([m, t]) => m !== "other" && t <= far.dur).sort((a, c) => c[1] - a[1])[0];
  const last = rs[rs.length - 1];
  app.append(el("h1", {}, name), el("p", { class: "lede" }, `${jobs.map(([j]) => JOB[j] || j).join(" / ")} · ${rs.length} night${rs.length > 1 ? "s" : ""}, ${dayName(rs[0].day)} to ${dayName(last.day)}. Latest: `,
    el("a", { href: `#/day/${last.day}/${encodeURIComponent(last.group)}/${encodeURIComponent(name)}` }, `${dayName(last.day)} ${last.group}`), "."));
  app.append(tiles([
    ["Pulls", num(P), `${rs.length} night${rs.length > 1 ? "s" : ""} · ${(sum(pulls.map(q => q.dur)) / 3600).toFixed(1)} hours in combat`],
    ["Jobs", jobs.map(([j]) => JOB[j] || j).slice(0, 3).join(" / "), jobs.map(([j, n]) => `${JOB[j] || j} ${n} pulls`).join(" · ")],
    ["Furthest seen", far ? mmss(far.dur) : "–", far ? `${far.kill ? "kill" : farMech ? farMech[0] : "opener"} · ${dayName(far.r.day)} ${far.r.group}, pull ${far.n}` : ""],
    ["Mistakes per pull", P ? (M / P).toFixed(2) : "–", `${minutes ? (M / minutes).toFixed(3) : "–"} per minute in pulls, all nights`, P ? grade("mistakes", M / P) : null],
    ["Wipes caused", P ? pct(W / P) : "–", blamedWipes ? `${pct(W / blamedWipes)} of the blamed wipes in their pulls (a fair share: 12.5%)` : "of their pulls", P ? grade("wipes", W / P) : null],
  ]));
  // their mistakes by mechanic: per pull that reached it (still going when it began), clean share, pulls lost
  const mechs = Object.entries(B.mech_start).filter(([m]) => m !== "other").sort((a, c) => a[1] - c[1]);
  const trendOf = vals => { const v = vals.filter(x => x != null); if (v.length < 2 || !v.some(x => x)) return ["–", null];
    const a = v.slice(0, Math.ceil(v.length / 2)), b = v.slice(Math.floor(v.length / 2)), ma = sum(a) / a.length, mb = sum(b) / b.length;
    return mb < ma * 0.8 ? ["improving", "good"] : mb > ma * 1.2 ? ["worse", "bad"] : ["about the same", null]; };
  const rowOf = (mech, start, inMech) => {
    const reached = pulls.filter(q => lostAt(q) >= start);
    const mis = q => sum(mine(q).filter(inMech).map(m => m.share ?? 1));
    const n = sum(reached.map(mis)), clean = reached.filter(q => !mine(q).some(inMech)).length;
    const lost = pulls.filter(q => q.wipe && q.wipe.culprits && q.wipe.culprits.includes(name) && inMech(q.wipe)).length;
    const labels = countBy(pulls.flatMap(q => mine(q).filter(inMech).map(m => causeName(m.mechanic, m.label))));
    const top = Object.entries(labels).sort((a, c) => c[1] - a[1])[0];
    const perNight = rs.map(r => { const rq = reached.filter(q => q.r === r); return rq.length ? sum(rq.map(mis)) / rq.length : null; });
    return { mech, reached: reached.length, n, rate: reached.length ? n / reached.length : null, clean: reached.length ? clean / reached.length : null, lost, top, trend: trendOf(perNight) };
  };
  const all = mechs.map(([m, t]) => rowOf(m, t, x => x.mechanic === m)).filter(x => x.reached);
  const rows = all.filter(x => x.n || x.lost), spotless = all.filter(x => !x.n && !x.lost);   // the clean ones get a line, not a row
  const other = rowOf("Other", 0, x => !x.mechanic || !(x.mechanic in B.mech_start) || x.mechanic === "other");
  if (other.n || other.lost) rows.push(other);
  const worst = rows.filter(x => x.rate != null).reduce((a, x) => !a || x.rate > a.rate ? x : a, null);
  app.append(heading("h2", "Mechanics", "Their mistakes in each mechanic over all raid days, per pull that reached it (still going when the mechanic began), so getting further on later days does not read as more mistakes. Each mistake counts in full, or their share of it. Clean: the share of those pulls without a mistake of theirs in the mechanic. Pulls lost: pulls whose wipe was put on them there. Trend: their later nights against their earlier ones, 20% or more apart. The mechanic with the most mistakes per pull reaching it is marked. Drill and Brief open the trainer on the mechanic."),
    el("div", { class: "table-wrap" }, el("table", {},
      el("thead", {}, el("tr", {}, ["Mechanic", "Pulls reaching it", "Mistakes", "Per pull reaching it", "Clean", "Pulls lost", "Most common", "Trend", "Practice"].map((h, i) => el("th", { class: i >= 1 && i <= 5 ? "num" : null }, h)))),
      el("tbody", {}, rows.map(x => el("tr", { class: x === worst && x.rate > 0 ? "moving" : null },
        el("td", {}, shortMech(x.mech)), el("td", { class: "num" }, String(x.reached)), el("td", { class: "num" }, x.n ? num(x.n, x.n % 1 ? 1 : 0) : "–"),
        el("td", { class: "num" }, x.rate != null ? x.rate.toFixed(2) : "–"), el("td", { class: "num" }, pct(x.clean)), el("td", { class: "num" }, x.lost ? String(x.lost) : "–"),
        el("td", { class: "wrap" }, x.top ? `${x.top[0].replace(/^[^:]+: /, "")} (${x.top[1]})` : ""), el("td", { class: x.trend[1] || null }, x.trend[0]),
        el("td", {}, drillLinks(x.mech) || "")))))),
    spotless.length ? el("p", { class: "note" }, `No mistake of theirs in ${spotless.map(x => `${shortMech(x.mech)} (reached ${x.reached} time${x.reached > 1 ? "s" : ""})`).join(", ")}.`) : "");
  acrossNights(app, name);
}
// their nights one by one: top issues per raid day, mistakes and wipes over time, and a row per night (job)
function acrossNights(app, name) {
  const hist = reports().filter(x => x.players).flatMap(x => x.players.filter(q => q.name === name).map(q => ({ ...q, day: x.day, group: x.group }))).sort((a, c) => a.day.localeCompare(c.day));
  const byDay = Object.values(hist.reduce((a, q) => ((a[q.day + q.group] = a[q.day + q.group] || []).push(q), a), {}));
  app.append(heading("h2", "Night by night", "Their top issues: the three mistakes they made most over all raid days, each per pull that reached the mechanic it happens in (the pull not yet lost when the mechanic began), so getting further in later raid days does not read as more mistakes. Each row is one mistake in one mechanic, named as in the mistake tables (Trinity of Souls in Para I and in Dialogos are separate rows). Rotation issues: the latest raid day's costliest, per minute alive, on the same job only. Trend: the later half of their raid days against the earlier half, 20% or more apart."));
  // their top issues, raid day by raid day
  if (byDay.length > 1) {
    const reps = byDay.map(es => findGroup(es[0].day, es[0].group)), dayCounts = reps.map(x => x ? mistakeCounts(x, name) : {});
    const total = {}, mechOfCause = {};
    dayCounts.forEach(c => Object.entries(c).forEach(([l, n]) => (total[l] = (total[l] || 0) + n)));
    reps.forEach(x => x && Object.entries(causeInfo(x)).forEach(([l, i]) => (mechOfCause[l] = mechOfCause[l] || i.mech)));
    const topM = Object.entries(total).sort((a, c) => c[1] - a[1]).slice(0, 3).map(x => x[0]);
    const latestRot = (byDay[byDay.length - 1][0].rotation || { checks: [] }).checks.filter(c => c.cost > 20).slice(0, 3).map(c => c.label);
    const trend = vals => { const v = vals.filter(x => x != null); if (v.length < 2) return ["–", null];
      const first = v.slice(0, Math.ceil(v.length / 2)), last = v.slice(Math.floor(v.length / 2));
      const a = first.reduce((s, x) => s + x, 0) / first.length, b = last.reduce((s, x) => s + x, 0) / last.length;
      return b < a * 0.8 ? ["improving", "good"] : b > a * 1.2 ? ["worse", "bad"] : ["about the same", null]; };
    const rows = [
      ...topM.map(l => {   // per pull that reached the mechanic the mistake happens in
        const start = DATA.benchmark.mech_start[mechOfCause[l]] ?? 0;
        const v = reps.map((rep, i) => { if (!rep) return null;
          const chances = rep.pulls.filter(q => q.players.includes(name) && (q.kill ? Infinity : (q.wipe ? q.wipe.t : q.dur)) >= start).length;
          return chances ? (dayCounts[i][l] || 0) / chances : null; });
        return [l, "per pull reaching it", v.map(x => x == null ? "–" : x.toFixed(2)), trend(v)]; }),
      ...latestRot.map(l => { const job = byDay[byDay.length - 1][0].job;      // rotation issues only compare days on the same job
        const v = byDay.map(es => { if (es[0].job !== job) return null; const c = (es[0].rotation || { checks: [] }).checks.find(x => x.label === l); return c ? c.ours : null; });
        return [l, "per minute", v.map(x => x == null ? "–" : x.toFixed(1)), trend(v)]; })];
    if (rows.length) app.append(el("div", { class: "table-wrap", style: "margin-bottom:12px" }, el("table", {},
      el("thead", {}, el("tr", {}, ["Their top issues", "", ...byDay.map(es => `${dayName(es[0].day)} ${es[0].group}`), "Trend"].map((h, i) => el("th", { class: i >= 2 ? "num" : null }, h)))),
      el("tbody", {}, rows.map(([l, unit, vals, [t, cls]]) => el("tr", {}, el("td", { class: "wrap" }, l), el("td", { class: "muted" }, unit),
        ...vals.map(v => el("td", { class: "num" }, v)), el("td", { class: `num ${cls || ""}` }, t)))))));
  }
  if (byDay.length > 1) {
    const pts = f => byDay.map(es => ({ x: `${dayName(es[0].day)} ${es[0].group}`, y: f(es), day: es[0].day }));
    const perMin = es => { const rep = findGroup(es[0].day, es[0].group); if (!rep) return null;   // as on the overview, for one player
      const m = sum(rep.pulls.filter(q => q.players.includes(name)).map(q => Math.min(q.dur, q.wipe ? q.wipe.t + 2 : q.dur) / 60));
      return m ? es[0].mistakes / m : null; };   // mistakes are per player, repeated on each job entry
    app.append(el("div", { class: "grid" },
      card("Mistakes per pull", info("Counted until each pull was lost. The dashed line divides the same mistakes by the minutes they spent in pulls (up to where each pull was lost), so longer pulls as the groups progress do not read as more mistakes." + STRATEGY_NOTE),
        lineChart(pts(es => es[0].mrate), { yFmt: v => v.toFixed(2), name: "per pull", dated: true, extra: [{ points: pts(perMin), name: "per minute", cls: "x-min", color: "#9b6cf2" }] }),
        () => tableOf(["Day", "Mistakes per pull", "Per minute in pulls"], byDay.map(es => [`${dayName(es[0].day)} ${es[0].group}`, es[0].mrate.toFixed(2), perMin(es) != null ? perMin(es).toFixed(3) : "–"]))),
      card("Wipes caused", info("Share of pulls." + STRATEGY_NOTE), lineChart(pts(es => es[0].wrate), { yFmt: v => pct(v), dated: true, yMax: Math.max(0.4, ...byDay.map(es => es[0].wrate)) }), () => tableOf(["Day", "Wipes"], byDay.map(es => [`${dayName(es[0].day)} ${es[0].group}`, pct(es[0].wrate)]))),
    ));
  }
  // a row per night and job: each links to that night's page
  const rotLoss = q => q.rotation && q.rotation.checks && !q.rotation.opener_only ? sum(q.rotation.checks.map(c => c.cost > 1 ? c.cost : 0)) : null;
  const opener = q => q.rotation && q.rotation.opener && q.rotation.opener.dmg ? q.rotation.opener.dmg.vs : null;
  app.append(el("div", { class: "table-wrap", style: "margin-top:12px" }, el("table", {},
    el("thead", {}, el("tr", {}, ["Day", "Group", "Job", "Pulls", "Mistakes/pull", "Per minute", "Wipes", "vs Clears", "Uptime", "Rotation loss", "Opener"].map((h, i) => el("th", { class: i >= 3 ? "num" : null }, h)))),
    el("tbody", {}, [...hist].reverse().map(q => { const rep = findGroup(q.day, q.group), mins = rep ? sum(rep.pulls.filter(x => x.players.includes(name)).map(x => Math.min(x.dur, x.wipe ? x.wipe.t + 2 : x.dur) / 60)) : 0;
      return linkRow([dayName(q.day), q.group, JOB[q.job] || q.job, String(q.pulls), el("span", {}, q.mrate.toFixed(2), gradeChip(grade("mistakes", q.mrate))),
        mins ? ((q.mistakes_w ?? q.mistakes) / mins).toFixed(3) : "–", el("span", {}, pct(q.wrate), gradeChip(grade("wipes", q.wrate))),
        q.vs ? el("span", {}, signed(q.vs[0]), gradeChip(grade("damage", q.vs[0]))) : "–", q.uptime != null ? el("span", {}, `${q.uptime.toFixed(1)}%`, gradeChip(grade("uptime", q.uptime_diff))) : "–",
        rotLoss(q) != null ? `${num(Math.round(rotLoss(q)))} DPS` : "–", opener(q) != null ? signed(opener(q)) : "–"], `#/day/${q.day}/${q.group}/${encodeURIComponent(name)}`, 3); })))));
}
function playersPage() {
  crumbs([]);   // the header link names the page
  const by = {};
  for (const r of [...reports()].sort((a, c) => a.day.localeCompare(c.day) || a.group.localeCompare(c.group)))
    for (const x of peopleOf(r)) (by[x.name] = by[x.name] || []).push({ ...x, r });
  const rate = (ns, k) => { const ok = ns.filter(n => n.pulls && n[k] != null), P = sum(ok.map(n => n.pulls)); return P ? sum(ok.map(n => n[k])) / P : null; };
  const rows = Object.entries(by).map(([name, ns]) => { const last = ns[ns.length - 1];
    return { name, ns, last, jobs: [...new Set(ns.flatMap(n => n.jobs))], pulls: sum(ns.map(n => n.pulls || 0)), mr: rate(ns, "m"), wr: rate(ns, "w"), lastMr: rate([last], "m") }; })
    .sort((a, c) => c.last.r.day.localeCompare(a.last.r.day) || a.name.localeCompare(c.name));
  const app = document.getElementById("app");
  const find = el("input", { type: "search", class: "filter", placeholder: "Find a player", "aria-label": "Find a player", autocomplete: "off" });
  app.append(el("h1", {}, "Players"), el("p", { class: "lede" }, `${rows.length} players over ${days().length} raid days, the most recent first. Mistakes and wipes per pull count each mistake in full or the player's share of it, as on the scorecard. Pick a player for their summary over all raid days.`),
    el("p", {}, find));
  const body = el("tbody", {}, rows.map(x => { const tr = linkRow([x.name, x.jobs.map(j => JOB[j] || j).join(" / ") || "–", String(x.ns.length), x.pulls ? num(x.pulls) : "–",
      x.mr != null ? el("span", {}, x.mr.toFixed(2), gradeChip(grade("mistakes", x.mr))) : "–", x.wr != null ? el("span", {}, pct(x.wr), gradeChip(grade("wipes", x.wr))) : "–",
      x.lastMr != null ? x.lastMr.toFixed(2) : "–", `${dayName(x.last.r.day)} · ${x.last.r.group}`],
    playerHref(x.name), 2); tr.dataset.name = x.name.toLowerCase(); tr.lastChild.className = ""; return tr; }));
  find.addEventListener("input", () => { const q = find.value.trim().toLowerCase(); for (const tr of body.children) tr.hidden = !!q && !tr.dataset.name.includes(q); });
  app.append(el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, ["Player", "Jobs", "Nights", "Pulls", "Mistakes/pull", "Wipes", "Latest night: mistakes/pull", "Latest night"].map((h, i) => el("th", { class: i >= 2 && i < 7 ? "num" : null }, h)))), body)));
}
function notFound() {
  crumbs([["Raid days", "#/"], ["Not found", null]]);
  document.getElementById("app").append(el("h1", {}, "Not found"), el("p", { class: "lede" }, "That day, group, player or rotation is not in the data."), el("a", { href: "#/" }, "Back to the raid days"));
}

// ---------- accounts (Supabase; ACCESS_CONCEPT.md, staff only) ----------
// config.json names the project. Anyone can log in with Discord, but an account sees nothing until an admin approves
// it as staff. Staff get every report's progress (the progress table) and a report's full record (report_full) when a
// page needs it; admins also get the admin page. Row-level security in the database decides; the page only asks. Staff
// can also open the site with the passphrase instead (data.enc.json, as of the last publish; config.json says whether
// it is there).
const SUPABASE_JS = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.117.3/dist/umd/supabase.js";
const SUPABASE_SRI = "sha384-BWcjm9OdFth9TbhCxZPdm+gAOUMAzQy9nmTs12ioXdCcbVnJaPMn+fMUoQCLt60R";
let SB = null, CFG = null;
let ME = null;               // the logged-in user: { id, name, role, staff, admin }; null when logged out
let BY_PASSPHRASE = false;   // the data came from data.enc.json
const FULL = {};             // code -> the promise of its full record
const sbCheck = ({ data, error }) => { if (error) throw new Error(error.message); return data; };
function loadScript(src, integrity) {
  return new Promise((ok, fail) => { const s = el("script", { src, integrity, crossorigin: "anonymous" });
    s.onload = ok; s.onerror = () => fail(new Error("The login library could not be loaded.")); document.head.append(s); });
}
async function startAccounts(cfg) {
  CFG = cfg;
  await loadScript(SUPABASE_JS, SUPABASE_SRI);
  SB = supabase.createClient(cfg.supabase_url, cfg.anon_key, { auth: { flowType: "pkce", detectSessionInUrl: true, persistSession: true } });
  await SB.auth.getSession();   // finishes a login that came back with ?code=…
  SB.auth.onAuthStateChange(ev => { if (ev === "SIGNED_OUT") { location.hash = "#/"; location.reload(); } });
  if (new URLSearchParams(location.search).has("code") || new URLSearchParams(location.search).has("error")) {
    let back = ""; try { back = sessionStorage.getItem("p12s-return") || ""; sessionStorage.removeItem("p12s-return"); } catch (e) {}
    history.replaceState(null, "", location.pathname + (back || location.hash));
  }
  await loadMe();
  await loadProgress();
}
async function loadMe() {
  const { data: { session } } = await SB.auth.getSession();
  if (!session) { ME = null; return; }
  const u = session.user;
  const prof = await SB.from("profiles").select("display_name, role").eq("user_id", u.id).maybeSingle().then(sbCheck);
  const role = prof ? prof.role : "pending";
  ME = { id: u.id, name: (prof && prof.display_name) || u.email || "you", role, staff: role === "staff" || role === "admin", admin: role === "admin" };
}
async function loadProgress() {   // every report's progress and the private site data, for staff
  if (!ME || !ME.staff || BY_PASSPHRASE) return;
  const [prog, meta] = await Promise.all([SB.from("progress").select("doc").then(sbCheck), SB.from("site_meta").select("key, doc").then(sbCheck)]);
  DATA.reports = Object.fromEntries(prog.map(x => [x.doc.code, x.doc]));
  for (const k of Object.keys(FULL)) delete FULL[k];
  for (const x of meta) DATA[x.key] = x.doc;   // the whole benchmark replaces the public part of it
  LOCKED = false;
}
function needFull(codes) {   // the full records of these reports, merged into DATA.reports (they hold every progress field too)
  return Promise.all(codes.filter(c => DATA.reports[c] && !DATA.reports[c].players).map(c => FULL[c] = FULL[c] ||
    SB.from("report_full").select("doc").eq("code", c).maybeSingle().then(sbCheck).then(x => {
      if (!x) throw new Error("This report is no longer there for you: it was removed, or your access changed. Reload the page.");   // not looping on it
      DATA.reports[c] = x.doc; })
      .catch(e => { delete FULL[c]; throw e; })));
}
const playerCodes = name => Object.values(DATA.reports)   // the reports a player page reads (the player across raid days)
  .filter(r => (r.names || (r.players || []).map(p => p.name)).includes(name)).map(r => r.code);
function loginDiscord() {
  try { sessionStorage.setItem("p12s-return", location.hash); } catch (e) {}
  SB.auth.signInWithOAuth({ provider: "discord", options: { redirectTo: location.origin + location.pathname, scopes: "identify email" } });
}
function loginBox(msg) {
  const box = el("div", { class: "unlock" }, el("button", { type: "button", class: "primary", on: { click: loginDiscord } }, "Log in with Discord"));
  if (CFG && CFG.email_login) {   // local testing only (SCORECARD_EMAIL_LOGIN in the keys file)
    const email = el("input", { type: "email", id: "email", autocomplete: "username", placeholder: "email" });
    const pw = el("input", { type: "password", id: "pw", autocomplete: "current-password", placeholder: "password" });
    const note = el("p", { class: "note", role: "status" });
    const go = signUp => async e => { e.preventDefault(); note.textContent = "…";
      const { error } = signUp ? await SB.auth.signUp({ email: email.value, password: pw.value }) : await SB.auth.signInWithPassword({ email: email.value, password: pw.value });
      if (error) { note.textContent = error.message; return; }
      await loadMe(); await loadProgress(); header(); route(); };
    box.append(el("p", { class: "note" }, "Or, on this test setup, with an email address:"), email, pw,
      el("div", { class: "actions" }, el("button", { type: "button", on: { click: go(false) } }, "Log in"), el("button", { type: "button", on: { click: go(true) } }, "Create account")), note);
  }
  if (msg) box.append(el("p", { class: "note" }, msg));
  return el("div", {}, box, CFG && CFG.passphrase && !BY_PASSPHRASE ? [el("p", { class: "note" }, "Or open it with the staff passphrase:"), passphraseForm()] : "");
}
const openPages = () => DATA && DATA.rotations ? [" The ", el("a", { href: "#/rotations" }, "rotations"), " and ", el("a", { href: "#/gear" }, "best-in-slot gear"), " are open to everyone."] : [];
function gatePage() {   // a progress page for someone who isn't staff (yet)
  crumbs([["Raid progress", null]]);
  const app = document.getElementById("app");
  if (!ME) {
    app.append(el("h1", {}, "Raid progress"), el("p", { class: "lede" }, "Raid progress is for Syncademy staff. Log in with Discord, and an admin approves your account.", ...openPages()), loginBox());
    return;
  }
  app.append(el("h1", {}, "Raid progress"), el("p", { class: "lede" }, "Your account is waiting for an admin's approval as Syncademy staff.", ...openPages()),
    ...(CFG.passphrase ? [el("p", { class: "note" }, "Or open it with the staff passphrase:"), passphraseForm()] : []));
}
function waitPage(text) { document.getElementById("app").append(el("p", { class: "muted" }, text)); }
function failPage(e) { document.getElementById("app").replaceChildren(el("h1", {}, "Cannot load this page"), el("p", { class: "lede" }, e.message || String(e))); }
const forgetPassphrase = () => { try { for (const k of Object.keys(sessionStorage)) if (k.startsWith("p12s-key:")) sessionStorage.removeItem(k); } catch (e) {} };
function accountBody(app) {
  app.append(el("h2", {}, "Your data"), el("p", { class: "lede" }, "This site stores your Discord user id, name and email address, as Discord sends them at login, and your role. "
    + "Logins and what admins do (approving accounts, changing roles, managing reports) go into an audit log that admins read. Deleting your account removes the account and its role; the audit log keeps its entries."),
    el("div", { class: "actions" }, el("button", { type: "button", on: { click: () => { forgetPassphrase(); SB.auth.signOut(); } } }, "Log out"),
      el("button", { type: "button", class: "danger", on: { click: async () => {
        if (!confirm("Delete your account? This cannot be undone; you would start over as waiting for approval.")) return;
        try { sbCheck(await SB.rpc("delete_my_account")); } catch (e) { alert(e.message); return; }
        forgetPassphrase(); await SB.auth.signOut(); } } }, "Delete my account")));
}
const ROLE_TEXT = { admin: "Admin: you see every report and manage reports and accounts.", staff: "Staff: you see every report.",
  pending: "Waiting for an admin's approval as Syncademy staff." };
function accountPage() {
  crumbs([["Account", null]]);
  const app = document.getElementById("app");
  const lock = BY_PASSPHRASE ? el("p", {}, "Opened with the staff passphrase: the data as of the last publish. ",
    el("button", { type: "button", class: "small", on: { click: lockAgain } }, "Lock")) : "";
  if (!ME) { app.append(el("h1", {}, "Log in"), lock, el("p", { class: "lede" }, "Log in with your Discord account. Raid progress is for Syncademy staff: an admin approves new accounts.", ...openPages()), loginBox()); return; }
  app.append(el("h1", {}, ME.name), el("p", { class: "lede" }, ROLE_TEXT[ME.role] || ME.role), lock);
  accountBody(app);
}

// the admin page: the reports the worker builds (tools/scorecard/worker.py), accounts, and the audit log
let adminTimer = null;
const fflogsLink = code => el("a", { href: `https://www.fflogs.com/reports/${encodeURIComponent(code)}`, target: "_blank", rel: "noopener" }, code);
const localTime = s => s ? new Date(s).toLocaleString("en-GB", { weekday: "short", hour: "2-digit", minute: "2-digit" }) : "–";
const dateTime = s => s ? new Date(s).toLocaleString("en-GB", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "–";
const REPORT_CODE = /^[A-Za-z0-9]{16}$/;
async function adminPage() {
  crumbs([]);   // the header link names the page
  const app = document.getElementById("app");
  if (!ME || !ME.admin) { app.append(el("h1", {}, "Admin"), el("p", { class: "lede" }, "Only admins can open this page."), ME ? "" : loginBox()); return; }
  app.append(el("h1", {}, "Admin"));
  const people = el("div"), reportsBox = el("div", {}, el("p", { class: "muted" }, "Loading…"));
  // the redraw every 15 s waits while a field is being typed in (or was changed and not saved)
  const busy = box => box.contains(document.activeElement) && document.activeElement.tagName === "INPUT"
    || [...box.querySelectorAll("input[type=text], input[type=number]")].some(i => i.value !== i.defaultValue) || box.querySelector("input[type=checkbox]:checked");
  const act = fn => async () => { try { await fn(); } catch (e) { alert(e.message); return; } reportsBox.replaceChildren(); draw(); };
  const waitingNote = el("div");   // logins waiting for approval, at the top where they are seen
  app.append(waitingNote, el("h2", {}, "Reports"), el("p", { class: "lede" }, "The reports on the site. The worker builds what this list asks for within a minute; a live report is checked for new pulls every 3 minutes until its watch ends (12 hours at most)."),
    adminTabs([["The list", reportsBox], ["Find a raid day's reports on FFLogs", findBox(act)]]),
    el("h2", { id: "accounts" }, "Accounts"), people, el("h2", {}, "Audit log"), auditBox());
  let lastBuilt = null;
  async function draw() {
    if (location.hash !== "#/admin") return;
    let src, profs;
    try {
      [src, profs] = await Promise.all([SB.from("report_sources").select("*").order("day", { ascending: false, nullsFirst: true }).order("group_name").then(sbCheck),
        SB.from("profiles").select("*").order("created_at").then(sbCheck)]);
    } catch (e) { reportsBox.replaceChildren(el("p", { class: "warn" }, e.message)); return; }
    const built = src.map(r => `${r.code}:${r.built_at}`).join();   // a build finished: take the new data
    if (lastBuilt != null && built !== lastBuilt) { await loadProgress(); }
    lastBuilt = built;
    if (!busy(reportsBox)) reportsBox.replaceChildren(addReportForm(act), reportTable(src, act));
    people.replaceChildren(...peopleTables(profs, act));
    const waiting = profs.filter(p => p.role === "pending").length;
    waitingNote.replaceChildren(waiting ? el("p", { class: "warn" }, `${waiting} login${waiting > 1 ? "s" : ""} waiting for approval. `,
      el("button", { type: "button", class: "linklike", on: { click: () => document.getElementById("accounts").scrollIntoView({ behavior: "smooth" }) } }, "Go to Accounts")) : "");
    pendingBadge(waiting);
    clearTimeout(adminTimer); adminTimer = setTimeout(draw, 15000);
  }
  draw();
}
// the report list and the FFLogs search as tabs, the list first; the open tab stays across the 15-second redraws and
// for the rest of the visit
let adminTab = 0;
function adminTabs(panes) {
  const panels = panes.map(([, box]) => el("div", { class: "tabpanel", role: "tabpanel" }, box));
  const tabs = el("div", { class: "tabs", role: "tablist", "aria-label": "Reports" }, panes.map(([label], k) =>
    el("button", { type: "button", role: "tab", on: { click: () => show(k) } }, label)));
  const show = k => { adminTab = k;
    [...tabs.children].forEach((b, j) => { b.classList.toggle("on", j === k); b.setAttribute("aria-selected", String(j === k)); });
    panels.forEach((x, j) => { x.hidden = j !== k; }); };
  show(adminTab);
  return el("div", {}, tabs, ...panels);
}
function addReportForm(act) {
  const link = el("input", { type: "text", id: "rep", required: true, autocomplete: "off", placeholder: "https://www.fflogs.com/reports/… or the code" });
  const group = el("input", { type: "text", id: "grp", autocomplete: "off", placeholder: "G1, G2, … (empty: the day's next free one)", maxlength: 24 });
  const live = el("input", { type: "checkbox", id: "live" }), hours = el("input", { type: "number", id: "hours", min: 1, max: 12, value: 6 });
  const msg = el("p", { class: "note", role: "status" });
  const form = el("form", { class: "unlock wide" }, el("label", { for: "rep" }, "FFLogs report"), link, el("label", { for: "grp" }, "Group name"), group,
    el("label", { class: "check" }, live, " Live: keep checking for new pulls for ", hours, " hours"), el("button", { type: "submit", class: "primary" }, "Add report"), msg);
  form.addEventListener("submit", e => { e.preventDefault();
    const code = (link.value.trim().match(/reports\/([A-Za-z0-9]+)/) || [null, link.value.trim()])[1].split("#")[0];
    if (!REPORT_CODE.test(code)) { msg.textContent = "That is not an FFLogs report link or code (16 letters and digits)."; return; }
    act(() => addSource(code, group.value, live.checked ? hours.value : 0))(); });
  return form;
}
async function addSource(code, group, liveHours) {   // onto the list the worker builds; liveHours 0: not live
  const { error } = await SB.from("report_sources").insert({ code, group_name: group.trim() || null,
    live_until: liveHours ? new Date(Date.now() + Math.min(12, Math.max(1, +liveHours || 6)) * 3600e3).toISOString() : null });
  if (error) throw new Error(error.code === "23505" ? `${code} is on the list already: rename, rebuild or watch it there.` : error.message);
}
// a raid day's P12S reports on FFLogs, with which of our players are in each: the worker searches (worker.search) and
// answers in report_searches; the newest search shows until the next one
function findBox(act) {
  const today = new Date(Date.now() - new Date().getTimezoneOffset() * 60e3).toISOString().slice(0, 10);
  const day = el("input", { type: "date", id: "fday", required: true, value: today, max: today });
  const names = el("input", { type: "text", id: "fnames", autocomplete: "off", maxlength: 300, placeholder: "optional: First Last, First Last@World, …" });
  const msg = el("p", { class: "note", role: "status" }), out = el("div");
  const form = el("form", { class: "unlock wide" }, el("label", { for: "fday" }, "Raid day"), day, el("label", { for: "fnames" }, "Characters to look for"), names,
    el("button", { type: "submit", class: "primary" }, "Search"), msg);
  let wait = null;
  async function show(id, asked) {   // the search's answer, polled until the worker has it
    clearTimeout(wait);
    if (location.hash !== "#/admin") return;
    let q;
    try { q = sbCheck(await SB.from("report_searches").select("*").eq("id", id).single()); } catch (e) { msg.textContent = e.message; return; }
    if (q.state === "queued" || q.state === "running") {
      msg.textContent = Date.now() - asked > 60e3 ? "Still waiting for the worker. Is it running?" : "Searching…";
      wait = setTimeout(() => show(id, asked), 2000); return;
    }
    msg.textContent = q.state === "error" ? q.message : "";
    if (q.state === "done") out.replaceChildren(...foundReports(q, act));
  }
  form.addEventListener("submit", async e => { e.preventDefault(); msg.textContent = "Searching…"; out.replaceChildren();
    try { const q = sbCheck(await SB.from("report_searches").insert({ day: day.value, names: names.value.trim() }).select("id").single()); show(q.id, Date.now()); }
    catch (err) { msg.textContent = err.message; } });
  SB.from("report_searches").select("id").order("asked_at", { ascending: false }).limit(1).then(sbCheck)
    .then(r => { if (r.length) show(r[0].id, Date.now()); }).catch(() => {});
  return el("div", {}, form, out);
}
function foundReports(q, act) {
  const res = q.results, all = res.reports, ours = all.filter(r => r.ours.length || r.asked.length || r.site || r.listed);
  const out = [el("p", { class: "note" }, `${dayName(q.day)}${q.names ? `, looking for ${q.names}` : ""}: ${all.length} public P12S Savage reports on FFLogs, ${ours.length} with our players`,
    ` (searched ${localTime(q.done_at)}). Unlisted and private reports never show up here: add those by link under The list.`)];
  if (res.not_found.length) out.push(el("p", { class: "warn" }, `Not in any of them: ${res.not_found.join(", ")}.`));
  const time = ms => new Date(ms).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  const table = rows => el("div", { class: "table-wrap" }, el("table", { class: "admin" },
    el("thead", {}, el("tr", {}, ["Start", "Report", "Pulls", "Our players", ""].map((h, i) => el("th", { class: i === 2 ? "num" : null }, h)))),
    el("tbody", {}, rows.map(r => {
      const recent = Date.now() - r.end < 30 * 60e3;   // still being written, most likely
      let status;
      if (r.site) status = `on the site as ${r.site.group}`;
      else if (r.listed) status = `on the list (${r.listed})`;
      else if (r.same) status = el("span", { class: "muted" }, `same pulls as ${r.same.group || r.same.code}`);
      else {
        const g = el("input", { type: "text", maxlength: 24, size: 6, placeholder: "G?", "aria-label": `Group name for ${r.code}` });
        const live = el("input", { type: "checkbox", checked: recent, "aria-label": `Watch ${r.code} live` });
        const add = el("button", { type: "button", class: "small", on: { click: () => act(async () => {
          await addSource(r.code, g.value, live.checked ? 6 : 0); r.listed = "queued"; add.replaceWith("added: on the list"); })() } }, "Add");
        status = el("span", { class: "actions" }, g, " ", el("label", { class: "check" }, live, " live 6 h"), " ", add);
      }
      const who = [...new Set([...r.asked, ...r.ours])];
      return el("tr", { class: r.site || r.same ? "muted" : null },
        el("td", {}, time(r.start), recent ? el("div", { class: "note" }, `last pull ${time(r.end)}`) : ""),
        el("td", {}, fflogsLink(r.code), el("div", { class: "note" }, [r.title, r.owner, r.visibility !== "public" ? r.visibility : null].filter(Boolean).join(" · "))),
        el("td", { class: "num" }, `${r.pulls}`, r.kills ? el("div", { class: "note" }, `${r.kills} kill${r.kills > 1 ? "s" : ""}`) : ""),
        el("td", {}, `${r.ours.length} of ${r.players}`, who.length ? el("div", { class: "note names" }, who.map((n, i) => [i ? ", " : "", el("span", { class: "nm" }, r.asked.includes(n) ? el("b", {}, n) : n)]).flat()) : ""),
        el("td", {}, status));
    }))));
  if (ours.length) out.push(table(ours));
  const rest = all.filter(r => !ours.includes(r));
  if (rest.length) {
    const box = el("div");
    out.push(el("p", {}, el("button", { type: "button", class: "small", on: { click: e => { e.target.parentNode.remove(); box.replaceChildren(table(rest)); } } }, `Show the ${rest.length} without our players`)), box);
  }
  return out;
}
// the list's older raid days stay folded across the 15-second redraws until opened
const RECENT_DAYS = 2;
let olderOpen = false;
function reportTable(src, act) {
  const upd = (code, cols) => act(async () => sbCheck(await SB.from("report_sources").update(cols).eq("code", code)))();
  const now = Date.now();
  // the newest raid days (and reports without a day yet, still being built) show; older ones behind a button
  const recent = [...new Set(src.map(r => r.day).filter(Boolean))].sort().reverse().slice(0, RECENT_DAYS);
  const isRecent = r => !r.day || recent.includes(r.day) || r.state !== "ok";   // queued, building or failed: always in view
  const older = src.filter(r => !isRecent(r));
  const shown = olderOpen ? src : src.filter(isRecent);
  const table = el("div", { class: "table-wrap" }, el("table", { class: "admin" },
    el("thead", {}, el("tr", {}, ["Day", "Group", "Report", "Pulls", "State", ""].map((h, i) => el("th", { class: i === 3 ? "num" : null }, h)))),
    el("tbody", {}, shown.map(r => {
      const live = r.live_until && new Date(r.live_until) > now, gone = r.want === "absent";
      const g = el("input", { type: "text", value: r.group_name || "", maxlength: 24, size: 6, "aria-label": `Group name of ${r.code}`, disabled: gone });
      const save = el("button", { type: "button", class: "small", disabled: gone, on: { click: () => upd(r.code, { group_name: g.value.trim() || null }) } }, "Rename");
      const onSite = !gone && r.state === "ok" && r.day && findGroup(r.day, r.group_name);
      const state = el("td", { class: `wrap${r.state === "error" ? " bad" : r.state === "ok" ? "" : " muted"}`, title: r.message || "" }, gone ? "removing" : r.state, r.message ? el("div", { class: "note" }, r.message) : "",
        live ? el("div", { class: "note" }, `live until ${localTime(r.live_until)}${r.checked_at ? `, checked ${localTime(r.checked_at)}` : ""}`) : "");
      return el("tr", { class: gone ? "muted" : null },
        el("td", {}, r.day ? dayName(r.day) : "–"), el("td", {}, g, " ", save),
        el("td", {}, fflogsLink(r.code), onSite ? [" · ", el("a", { href: `#/day/${r.day}/${encodeURIComponent(r.group_name)}` }, "on the site")] : ""),
        el("td", { class: "num" }, r.pulls != null ? String(r.pulls) : "–"), state,
        el("td", {}, el("div", { class: "actions" },
          el("button", { type: "button", class: "small", disabled: gone, on: { click: () => upd(r.code, { live_until: live ? new Date().toISOString() : new Date(now + 6 * 3600e3).toISOString() }) } }, live ? "Stop watching" : "Watch 6 h"),
          el("button", { type: "button", class: "small", disabled: gone, on: { click: () => upd(r.code, { rebuild_at: new Date().toISOString() }) } }, "Rebuild"),
          el("button", { type: "button", class: "small danger", disabled: gone, on: { click: () => { if (confirm(`Remove ${r.group_name || r.code}${r.day ? ` of ${dayName(r.day)}` : ""} from the site?`)) upd(r.code, { want: "absent" }); } } }, "Remove"))));
    }))));
  if (!older.length) return table;
  const toggle = el("button", { type: "button", class: "small", on: { click: () => { olderOpen = !olderOpen; act(async () => {})(); } } },
    olderOpen ? "Hide older raid days" : `Show ${older.length} older report${older.length > 1 ? "s" : ""}`);
  return el("div", {}, table, el("p", {}, toggle));
}
function peopleTables(profs, act) {
  const name = p => p.display_name || p.user_id.slice(0, 8);
  const btn = (label, fn, cls = "small") => el("button", { type: "button", class: cls, on: { click: fn } }, label);
  const setRole = (p, role, ask) => () => { if (!ask || confirm(ask)) act(async () => {
    if (!sbCheck(await SB.from("profiles").update({ role }).eq("user_id", p.user_id).select("user_id")).length) throw new Error(`${name(p)}'s role was not changed.`); })(); };
  const remove = p => () => { if (confirm(`Remove the account of ${name(p)}? Logging in again makes a new account, waiting for approval.`))
    act(async () => sbCheck(await SB.rpc("remove_account", { p_user: p.user_id })))(); };
  const table = (rows, mine) => el("div", { class: "table-wrap" }, el("table", { class: "admin" }, el("tbody", {}, rows.map(p => el("tr", {},
    el("td", {}, name(p)), el("td", {}, p.role), el("td", {}, `since ${dateTime(p.created_at)}`), el("td", { class: "actions" }, p.user_id === ME.id ? el("span", { class: "muted" }, "you") : mine(p)))))));
  const waiting = profs.filter(p => p.role === "pending"), team = profs.filter(p => p.role !== "pending");
  return [el("h3", {}, `Waiting for approval (${waiting.length})`),
    el("p", { class: "note" }, "Anyone with a Discord account can log in. Approve only Syncademy staff; remove the others."),
    waiting.length ? table(waiting, p => [btn("Approve as staff", setRole(p, "staff")), " ", btn("Remove", remove(p), "small danger")]) : el("p", { class: "muted" }, "None waiting."),
    el("h3", {}, `Staff and admins (${team.length})`),
    table(team, p => [p.role === "admin" ? btn("Remove admin", setRole(p, "staff", `Take admin rights from ${name(p)}?`))
      : btn("Make admin", setRole(p, "admin", `Make ${name(p)} an admin? Admins manage reports and accounts and read the audit log.`)), " ",
      btn("Revoke", setRole(p, "pending", `Take ${name(p)}'s staff access away? Their account stays, waiting for approval.`)), " ",
      btn("Remove", remove(p), "small danger")])];
}
// the audit log (audit_log): logins, accounts, the report list, searches, and what the worker and the command line did;
// newest first, a hundred at a time. Entries with no name came in with the service key
function auditBox() {
  const body = el("tbody"), msg = el("p", { class: "note", role: "status" });
  const more = el("button", { type: "button", class: "small", hidden: true }, "Older entries"), again = el("button", { type: "button", class: "small" }, "Refresh");
  const fmt = v => Array.isArray(v) ? v.join(", ") : typeof v === "string" && /^\d{4}-\d\d-\d\dT/.test(v) ? dateTime(v) : typeof v === "object" ? JSON.stringify(v) : String(v);
  let oldest = null, ask = 0;
  async function load(fresh) {   // a newer load (Refresh, or a second click) wins; an older one's rows are dropped
    const mine = ++ask;
    if (fresh) { body.replaceChildren(); oldest = null; }
    more.disabled = true;
    let q = SB.from("audit_log").select("*").order("id", { ascending: false }).limit(100);
    if (oldest != null) q = q.lt("id", oldest);
    let rows;
    try { rows = sbCheck(await q); } catch (e) { if (mine === ask) { msg.textContent = e.message; more.disabled = false; } return; }
    if (mine !== ask) return;
    more.disabled = false;
    msg.textContent = !body.children.length && !rows.length ? "No entries yet." : "";
    for (const e of rows) body.append(el("tr", {}, el("td", {}, dateTime(e.at)), el("td", {}, e.actor_name || (e.actor ? e.actor.slice(0, 8) : el("span", { class: "muted" }, "service key"))),
      el("td", {}, e.action), el("td", {}, e.target || ""), el("td", { class: "note" }, Object.entries(e.detail || {}).map(([k, v]) => `${k} ${fmt(v)}`).join(" · "))));
    if (rows.length) oldest = rows[rows.length - 1].id;
    more.hidden = rows.length < 100;
  }
  more.addEventListener("click", () => load(false)); again.addEventListener("click", () => load(true));
  load(true);
  return el("div", {}, el("p", { class: "lede" }, "Logins, accounts and their roles, changes to the report list, FFLogs searches, and what the worker and the command line built. Opening the site with the passphrase leaves no entry: it never reaches the server."),
    el("p", {}, again), el("div", { class: "table-wrap" }, el("table", { class: "admin" },
      el("thead", {}, el("tr", {}, ["When", "Who", "What", "Target", "Details"].map(h => el("th", {}, h)))), body)), msg, el("p", {}, more));
}
function header() {   // the header's account button and admin link
  const btn = document.getElementById("lock"), adm = document.getElementById("nav-admin");
  if (SB) { btn.hidden = false; btn.textContent = ME ? "Account" : BY_PASSPHRASE ? "Lock" : "Log in"; }
  if (adm) adm.hidden = !(ME && ME.admin);
  if (ME && ME.admin) SB.from("profiles").select("user_id", { count: "exact", head: true }).eq("role", "pending")
    .then(({ count }) => pendingBadge(count || 0)).catch(() => {});
}
function pendingBadge(n) {   // the Admin link counts the logins waiting for approval
  const adm = document.getElementById("nav-admin");
  if (adm) { adm.textContent = n ? `Admin (${n})` : "Admin"; adm.title = n ? `${n} login${n > 1 ? "s" : ""} waiting for approval` : ""; }
}
function navSection(first) {   // marks the header link of the section the page is in (raid days for day pages and home)
  const s = !first || first === "day" ? "days" : first === "player" ? "players" : first;
  for (const a of document.querySelectorAll(".navlink")) a.toggleAttribute("aria-current", a.dataset.section === s);
}

// ---------- routing, theme, boot ----------
function route(keepScroll = false) {   // keepScroll: redraw the same page in place (resize, theme), not a navigation
  hideTip();
  const y = scrollY;
  const app = document.getElementById("app"); app.replaceChildren();
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  const open = (parts[0] === "rotations" || parts[0] === "gear") && DATA && DATA.rotations;   // public.json is enough for these
  navSection(parts[0]);
  if (SB && parts[0] === "account") { accountPage(); return; }
  if (SB && parts[0] === "admin") { adminPage(); return; }
  if (LOCKED && !open) { SB ? gatePage() : lockedPage(); return; }
  if (SB && parts[0] === "player" && parts.length === 2) {   // the summary reads every report the player is in
    const missing = playerCodes(parts[1]).filter(c => !DATA.reports[c].players), h = location.hash;
    if (missing.length) { waitPage("Loading their reports…"); needFull(missing).then(() => { if (location.hash === h) route(true); }).catch(failPage); return; }
  }
  if (SB && parts[0] === "day" && parts.length >= 3) {   // group, pull and player pages need the full records (a player page: all of theirs)
    const r = findGroup(parts[1], parts[2]), h = location.hash;
    const player = parts.length === 4 && parts[3] !== "pulls";
    const missing = r ? [r.code, ...(player ? playerCodes(parts[3]) : [])].filter(c => DATA.reports[c] && !DATA.reports[c].players) : [];
    if (missing.length) {
      waitPage("Loading the report…");
      needFull(missing).then(() => { if (location.hash === h) route(true); }).catch(failPage);
      return;
    }
  }
  draw();
  if (!keepScroll) scrollTo(0, 0);
  else requestAnimationFrame(() => requestAnimationFrame(() => scrollTo(0, y)));   // after the charts have drawn and set the height
}
function draw() {   // the page the hash names, from what DATA holds
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  const open = (parts[0] === "rotations" || parts[0] === "gear") && DATA && DATA.rotations, app = document.getElementById("app");
  if (!DATA || (!reports().length && !open)) { app.append(el("h1", {}, "No data yet"), el("p", { class: "lede" }, "Run build_site.py with some report links, then reload.")); return; }
  if (parts[0] === "rotations" && parts.length === 1) rotationsPage();
  else if (parts[0] === "rotations" && parts.length === 2) rotationJobPage(parts[1]);
  else if (parts[0] === "rotations" && parts.length === 3) rotationPage(parts[1], parts[2]);
  else if (parts[0] === "gear" && parts.length === 1) gearPage();
  else if (parts[0] === "gear" && parts.length === 2) gearJobPage(parts[1]);
  else if (parts[0] === "day" && parts.length === 2) dayPage(parts[1]);
  else if (parts[0] === "day" && parts.length === 3) groupPage(parts[1], parts[2]);
  else if (parts[0] === "day" && parts.length === 4 && parts[3] === "pulls") pullsPage(parts[1], parts[2]);
  else if (parts[0] === "day" && parts.length === 5 && parts[3] === "pulls") pullPage(parts[1], parts[2], +parts[4]);
  else if (parts[0] === "day" && parts.length === 4) playerPage(parts[1], parts[2], parts[3]);
  else if (parts[0] === "players" && parts.length === 1) playersPage();
  else if (parts[0] === "player" && parts.length === 2) playerSummary(parts[1]);
  else home();
  if (parts[0] === "day" && (parts.length === 3 || parts.length === 4 && parts[3] !== "pulls")) sectionLinks(app);
}
// "On this page": links to a long page's sections (its h2s), between its title and its tiles
function sectionLinks(app) {
  const hs = [...app.querySelectorAll("h2")];
  if (hs.length < 4) return;
  const links = hs.map((h, i) => { h.id = h.id || `s-${i}`;
    return el("a", { href: `#${h.id}`, on: { click: e => { e.preventDefault(); h.scrollIntoView({ behavior: "smooth" }); } } }, h.firstChild.textContent.trim()); });
  const nav = el("nav", { class: "sections", "aria-label": "On this page" }, el("span", { class: "muted" }, "On this page:"), ...links);
  const at = app.querySelector(".kpis");
  if (at) at.before(nav); else app.querySelector("h1").after(nav);
}
function setupTheme() {
  const btn = document.getElementById("theme"), root = document.documentElement;
  let saved = null; try { saved = localStorage.getItem("p12s-theme"); } catch (e) {}
  const asked = new URLSearchParams(location.search).get("theme");   // ?theme=light|dark, e.g. for a shared link
  if (asked === "light" || asked === "dark") saved = asked;
  if (saved) root.dataset.theme = saved;
  const current = () => root.dataset.theme || (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
  const label = () => (btn.textContent = current() === "dark" ? "Light" : "Dark");
  label();
  btn.addEventListener("click", () => {
    root.dataset.theme = current() === "dark" ? "light" : "dark";
    try { localStorage.setItem("p12s-theme", root.dataset.theme); } catch (e) {}
    label(); route(true);
  });
}
// redraw charts when the width changes; on phones the address bar showing or hiding while scrolling changes only the
// height, and redrawing then (with a jump to the top) made scrolling up reset the page
let resizeTimer = null, lastWidth = innerWidth;
addEventListener("resize", () => {
  if (innerWidth === lastWidth) return;
  lastWidth = innerWidth;
  clearTimeout(resizeTimer); resizeTimer = setTimeout(() => route(true), 200);
});
addEventListener("hashchange", () => route());
// ---------- data: plaintext data.json (private hosting), or public hosting: public.json (the rotation and gear
// pages, open to everyone) and data.enc.json (everything else, behind a passphrase, fetched once a page needs it) ----------
let LOCKED = false;   // public hosting, until data.enc.json is opened: only the rotation and gear pages draw
const b64d = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
const b64e = buf => btoa(String.fromCharCode(...new Uint8Array(buf)));
const sessionKeyName = env => `p12s-key:${env.salt}`;
let envelopeP = null;
function envelope() {   // data.enc.json, fetched once
  return envelopeP = envelopeP || fetch("data.enc.json", { cache: "no-store" }).then(r => {
    if (!r.ok) { envelopeP = null; throw new Error("The locked data is missing from this site."); }
    return r.json();
  });
}
async function deriveKey(pass, env) {   // must match encrypt_data.js
  const base = await crypto.subtle.importKey("raw", new TextEncoder().encode(pass), "PBKDF2", false, ["deriveKey"]);
  return crypto.subtle.deriveKey({ name: "PBKDF2", salt: b64d(env.salt), iterations: env.iterations, hash: "SHA-256" }, base,
    { name: "AES-GCM", length: 256 }, true, ["decrypt"]);
}
async function openEnvelope(env, key) {
  const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b64d(env.iv) }, key, b64d(env.data));
  let stream = new Blob([plain]).stream();
  if (env.compressed === "gzip") stream = stream.pipeThrough(new DecompressionStream("gzip"));
  return JSON.parse(await new Response(stream).text());
}
function canDecrypt(env) {
  if (!window.crypto || !crypto.subtle) throw new Error("This page has to be opened over https (or on localhost) to decrypt its data.");
  if (env.compressed === "gzip" && !window.DecompressionStream) throw new Error("This browser is too old to open the data; please update it.");
}
function opened(data) {   // the private part goes over the public one (its benchmark is the whole one)
  Object.assign(DATA, data); LOCKED = false; BY_PASSPHRASE = true;
  document.getElementById("lock").hidden = false;
  if (SB) header();
}
async function openRemembered() {   // with a key remembered earlier in this browser session, without asking
  try { if (!Object.keys(sessionStorage).some(k => k.startsWith("p12s-key:"))) return; } catch (e) { return; }
  let env = null;
  try {
    env = await envelope(); canDecrypt(env);
    const raw = sessionStorage.getItem(sessionKeyName(env));
    if (raw) opened(await openEnvelope(env, await crypto.subtle.importKey("raw", b64d(raw), "AES-GCM", true, ["decrypt"])));
  } catch (e) { try { if (env) sessionStorage.removeItem(sessionKeyName(env)); } catch (e2) {} }
}
function lockedPage() {
  crumbs([["Locked", null]]);
  const form = passphraseForm();
  const pub = DATA && DATA.rotations ? [" The ", el("a", { href: "#/rotations" }, "rotations"), " and ", el("a", { href: "#/gear" }, "best-in-slot gear"), " are open to everyone."] : [];
  document.getElementById("app").append(el("h1", {}, "Locked"),
    el("p", { class: "lede" }, "Raid progress is encrypted. Enter the passphrase to open it.", ...pub), form);
  form.querySelector("input").focus();
}
function passphraseForm() {   // opens data.enc.json
  envelope().catch(() => {});   // start the download while the passphrase is typed
  const input = el("input", { type: "password", id: "pass", autocomplete: "current-password", required: true });
  const remember = el("input", { type: "checkbox", id: "remember", checked: true });
  const msg = el("p", { class: "note", role: "status" });
  const btn = el("button", { type: "submit", class: "primary" }, "Unlock");
  const form = el("form", { class: "unlock" },
    el("label", { for: "pass" }, "Passphrase"), input,
    el("label", { class: "check" }, remember, " Remember for this browser session"), btn, msg);
  form.addEventListener("submit", async e => {
    e.preventDefault(); btn.disabled = true; msg.textContent = "Unlocking…";
    let env;
    try { env = await envelope(); canDecrypt(env); } catch (err) { msg.textContent = err.message || String(err); btn.disabled = false; return; }
    try {
      const key = await deriveKey(input.value, env), data = await openEnvelope(env, key);
      if (remember.checked) try { sessionStorage.setItem(sessionKeyName(env), b64e(await crypto.subtle.exportKey("raw", key))); } catch (e2) {}
      opened(data); route();
    } catch (err) { msg.textContent = "That passphrase does not open the data."; btn.disabled = false; input.select(); }
  });
  return form;
}
function lockAgain() { forgetPassphrase(); location.reload(); }
async function boot() {
  setupTheme();
  document.getElementById("lock").addEventListener("click", () => SB && (ME || !BY_PASSPHRASE) ? (location.hash = "#/account") : lockAgain());
  try {
    let r = await fetch("data.json", { cache: "no-store" });
    if (r.ok) DATA = await r.json();
    else {
      r = await fetch("public.json", { cache: "no-store" });
      DATA = r.ok ? await r.json() : {};
      LOCKED = true;
      const cfg = await fetch("config.json", { cache: "no-store" }).then(x => x.ok ? x.json() : null).catch(() => null);
      if (cfg && cfg.supabase_url) {   // staff accounts (ACCESS_CONCEPT.md), or the passphrase remembered in this browser session
        await startAccounts(cfg);
        if (!(ME && ME.staff) && cfg.passphrase) await openRemembered();
        header();
      }
      else {   // the passphrase
        if (!r.ok) await envelope().catch(() => { throw new Error("data.json is missing. Run tools/scorecard/build_site.py with report links, then serve this folder with python -m http.server."); });
        await openRemembered();
      }
    }
    route();
  } catch (e) {
    document.getElementById("app").replaceChildren(el("h1", {}, "Cannot open the data"), el("p", { class: "lede" }, e.message || String(e)));
  }
}
boot();
