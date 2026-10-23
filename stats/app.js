/* P12S progress site: raid days -> groups -> players, drawn from data.json (written by build_site.py).
   Routes: #/  ·  #/day/<date>  ·  #/day/<date>/<group>  ·  #/day/<date>/<group>/<player>
           #/rotations  ·  #/rotations/<job>  ·  #/rotations/<job>/<gcd>   (the optimizer's rotations, tools/rotation)
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

// ---------- data shaping ----------
function reports() { return Object.values(DATA.reports); }
function days() {
  const by = {};
  for (const r of reports()) (by[r.day] = by[r.day] || []).push(r);
  for (const d in by) by[d].sort((a, b) => a.group.localeCompare(b.group, "en", { numeric: true }));
  return Object.keys(by).sort().map(d => ({ day: d, groups: by[d] }));
}
function stats(rs) {   // summary over one or more group reports
  const pulls = sum(rs.map(r => r.pulls_total));
  const playerPulls = sum(rs.map(r => sum(r.players.filter((p, i, a) => a.findIndex(q => q.name === p.name) === i).map(p => p.pulls))));
  const mistakes = sum(rs.map(r => sum(r.pulls.map(p => p.mistakes.length))));
  const wipeCauses = {};
  for (const r of rs) for (const [k, n] of Object.entries(r.wipe_causes)) wipeCauses[k] = (wipeCauses[k] || 0) + n;
  const withParty = rs.filter(r => r.party);
  return {
    pulls, kills: sum(rs.map(r => r.kills)), best: Math.min(...rs.map(r => r.best)), longest: Math.max(...rs.map(r => r.longest)),
    clean2: sum(rs.map(r => r.clean2)), mistakesPerPull: playerPulls ? mistakes / playerPulls : null,
    // per player and minute of pull, up to where each pull was lost (as the mistakes are counted)
    mistakesPerMin: (() => { const m = sum(rs.map(r => sum(r.pulls.map(p => p.players.length * Math.min(p.dur, p.wipe ? p.wipe.t + 2 : p.dur) / 60))));
      return m ? mistakes / m : null; })(),
    party: withParty.length ? sum(withParty.map(r => r.party * r.clean2)) / sum(withParty.map(r => r.clean2)) : null,
    topWipe: Object.entries(wipeCauses).sort((a, b) => b[1] - a[1])[0], wipeCauses,
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

// what one death of theirs costs at full length: time dead until raised (median over our reports) plus the raise's
// Weakness for its whole duration, at their own rDPS; as boss HP, kill time at the group's party DPS, and against the
// group's mistake budget (Echo reports: damage taken back to normal, /1.2)
function deathTile(r, p) {
  const b = DATA.benchmark, echo = r.echo ? 1.2 : 1, rdps = p.avg ? p.avg / echo : null;
  if (!rdps) return ["One death costs", "–", "needs a clean 0:00–2:00 pull"];   // label below gets the explanation
  const lost = (b.mistake_times.dead_s + b.raise_s * b.raise_penalty.Weakness) * rdps, hp = 100 * lost / b.hp_checkpoints.boss_hp;
  const bud = budget([r]), fits = bud && bud.hp > 0 ? bud.hp / hp : null;
  const label = el("span", {}, "One death costs", help(`One death of theirs at full length: ${b.mistake_times.dead_s.toFixed(0)} s dead until raised (median over our reports) plus ${b.raise_s} s of Weakness (−${Math.round(100 * b.raise_penalty.Weakness)}% damage), at their average rDPS over clean 0:00–2:00 pulls. Kill time: that damage at the group's party DPS. Budget: how many such deaths fit in the group's mistake budget for a whole kill. A second death within the Weakness gives Brink of Death (−50%) and costs more.`));
  return [label, `${hp.toFixed(2)}% HP`, `≈ ${(lost / (r.party / echo)).toFixed(1)} s of kill time at their ${kfmt(rdps)} rDPS${fits != null ? ` · budget fits ${fits.toFixed(1)}` : bud ? " · no mistake budget" : ""}`];
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
  for (const [value, label, key] of rows) t.append(el("div", { class: "t-row" }, key ? el("i", { class: "t-key" }) : null, el("b", {}, value), label ? el("span", {}, label) : null));
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
const reachMechs = () => DATA.benchmark.hp_checkpoints.mechanics.map(m => ({ name: m.mechanic, t: m.start_s }));
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
        [mmss(p.dur), p.kill ? "" : p.wipe ? p.wipe.label : "wipe"], ...(p.echo ? [["Echo", "not counted for the best line"]] : [])]);
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
  return DATA.benchmark.windows.map(w => {
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
const DRILLS = { "Paradeigma I": "para1", "Paradeigma II": "engrave", "Superchain I": "superchain" };
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
  for (const [cause, n] of wipes.slice(0, 2)) if (n >= 2 || n / p.pulls >= 0.1)
    items.push({ title: cause, detail: `Lost ${n} pull${n > 1 ? "s" : ""} (${pct(n / p.pulls)} of theirs); ${counts[cause] || n} times in all.`,
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
  for (const [cause, n] of Object.entries(wipeCounts(r)).sort((a, c) => c[1] - a[1]).slice(0, 2)) {
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
function tableOf(head, rows, numericFrom = 1) {   // numericFrom: first numeric column, or a list of them
  const isNum = i => Array.isArray(numericFrom) ? numericFrom.includes(i) : i >= numericFrom;
  return el("table", {}, el("thead", {}, el("tr", {}, head.map((h, i) => el("th", { class: isNum(i) ? "num" : null }, h)))),
    el("tbody", {}, rows.map(r => el("tr", {}, r.map((c, i) => el("td", { class: isNum(i) ? "num" : null }, c))))));
}
const clip = (text, px) => { const n = Math.max(4, Math.floor(px / 6)); return text.length > n ? text.slice(0, n - 1) + "…" : text; };
function niceMax(v) { const p = Math.pow(10, Math.floor(Math.log10(v || 1))); for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p; return 10 * p; }
function ticks(max, n = 4) { const step = max / n; return Array.from({ length: n + 1 }, (_, i) => i * step); }

// line chart, one series over raid days (x = categories)
function lineChart(points, { yFmt = v => v, yMax, yMin = 0, invert = false, refs = [], second = null, name = null, extra = [] } = {}) {
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
const KIND_SERIES = [{ name: "Lost the pull", color: "var(--wipe, #9e1f30)" }, { name: "Other deaths", color: "var(--div-neg)" }, { name: "Damage Down", color: "#e0a03a" }];   // deaths and DD as in Damage lost to mistakes

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
const MIN_PHASE = 2;   // clean samples a phase needs before it is compared with clearers
const shortPhase = w => w.replace("Opener & Paradeigma I", "Opener & Para I").replace("Paradeigma", "Para").replace(" & Dialogos", "").replace(" & Ultima Blade", "").replace(" & Theos's Ultima", "");

// boss HP at each checkpoint, drawn as points ahead of (left) or behind (right) the Clear pace: the targets run from
// 84% to 10% HP while what matters is a point or two either side of them, so every row shares the Clear line at 0
function checkpointChart(hp) {
  const cps = DATA.benchmark.hp_checkpoints.mechanics;
  return width => {
    const lab = width < 420 ? 118 : 150, valW = width < 420 ? 70 : 88, rh = 30, head = 8, H = head + cps.length * rh + 34, w = width - lab - valW;
    const diffs = cps.flatMap(c => (hp[c.mechanic] || []).length ? [hp[c.mechanic][0] - c.breakeven, median(hp[c.mechanic]) - c.breakeven] : []);
    const lo = -Math.max(6, Math.ceil(Math.max(...cps.map(c => c.breakeven - c.comfortable)) + 1), Math.ceil(-Math.min(0, ...diffs)) + 1);
    const hi = Math.min(20, Math.max(6, Math.ceil(Math.max(0, ...diffs)) + 1));
    const X = v => lab + ((Math.max(lo, Math.min(hi, v)) - lo) / (hi - lo)) * w;
    const svg = sv("svg", { viewBox: `0 0 ${width} ${H}`, role: "img" });
    const step = hi - lo > 24 ? 10 : 5;
    for (let v = Math.ceil(lo / step) * step; v <= hi; v += step)
      svg.append(sv("line", { class: "gridline", x1: X(v), x2: X(v), y1: head, y2: H - 34 }),
        sv("text", { x: X(v), y: H - 20, "text-anchor": "middle" }, v === 0 ? "Clear" : `${v > 0 ? "+" : "−"}${Math.abs(v)}`));
    svg.append(sv("text", { x: lab, y: H - 4 }, w > 260 ? "← ahead of pace (HP points)" : "← ahead"), sv("text", { x: lab + w, y: H - 4, "text-anchor": "end" }, "behind →"));
    cps.forEach((c, i) => {
      const y = head + i * rh + rh / 2, vals = hp[c.mechanic] || [];
      svg.append(sv("text", { class: "lbl", x: lab - 10, y: y + 4, "text-anchor": "end" }, clip(`${c.mechanic} ${mmss(c.start_s)}`, lab - 14)));
      svg.append(sv("rect", { x: X(c.comfortable - c.breakeven), y: y - 9, width: X(0) - X(c.comfortable - c.breakeven), height: 18, rx: 3, fill: "var(--zone)" }));
      svg.append(sv("line", { x1: X(0), x2: X(0), y1: y - 11, y2: y + 11, stroke: "var(--ink-2)", "stroke-width": 1 }));
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
      hover(hit, `${c.mechanic} (starts ${mmss(c.start_s)})`, [[`${best.toFixed(1)}%`, `best (${ahead(db)})`], [`${med.toFixed(1)}%`, `median (${ahead(dm)})`],
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
function checkpointTable(hp) {
  return tableOf(["Mechanic", "Starts", "Clear", "Comfy", "Best", "Median", "Pulls"],
    DATA.benchmark.hp_checkpoints.mechanics.map(c => { const v = hp[c.mechanic] || []; return [c.mechanic, mmss(c.start_s), `${c.breakeven}%`, `${c.comfortable}%`,
      v.length ? `${v[0].toFixed(1)}%` : "–", v.length ? `${median(v).toFixed(1)}%` : "–", String(v.length)]; }));
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
  for (const q of r.pulls) { for (const x of q.mistakes) m[causeName(x.mechanic, x.label)] = { mech: x.mechanic, label: x.label };
    if (q.wipe) m[causeName(q.wipe.mechanic, q.wipe.label)] = m[causeName(q.wipe.mechanic, q.wipe.label)] || { mech: q.wipe.mechanic, label: q.wipe.label }; }
  return m; };
const countBy = keys => keys.reduce((a, k) => ((a[k] = (a[k] || 0) + 1), a), {});
// every mistake until each pull was lost (of one player, if given), and the mistake that lost each pull
const mistakeCounts = (r, who) => countBy(r.pulls.flatMap(q => q.mistakes.filter(m => !who || m.who === who).map(m => causeName(m.mechanic, m.label))));
const wipeCounts = (r, who) => {
  const c = countBy(r.pulls.filter(q => q.wipe && (!who || q.wipe.culprits.includes(who))).map(q => causeName(q.wipe.mechanic, q.wipe.label)));
  if (!who && r.wipe_causes.Unclear) c.Unclear = r.wipe_causes.Unclear;   // wipes nobody could be blamed for have no wipe entry on the pull
  return c;
};

function causeMatrix(title, caption, cols, getCounts) {   // causes x columns heatmap card
  const counts = cols.map(getCounts);
  const totals = {};
  counts.forEach(c => Object.entries(c).forEach(([k, n]) => (totals[k] = (totals[k] || 0) + n)));
  const rowsAll = Object.keys(totals).sort((a, b) => totals[b] - totals[a]);
  if (!rowsAll.length) return el("figure", { class: "card" }, el("div", { class: "card-head" }, el("h3", {}, title)), el("div", { class: "empty" }, "Nothing recorded."));
  return card(title, caption, heatmap(rowsAll, cols.map(c => c.label), (r, c) => counts[c][rowsAll[r]] || 0),
    () => tableOf(["Cause", ...cols.map(c => c.label), "Total"], rowsAll.map(k => [k, ...counts.map(c => String(c[k] || 0)), String(totals[k])])));
}

// ---------- pages ----------
function home() {
  crumbs([["Raid days", null]]);
  const ds = days(), all = stats(reports());
  const app = document.getElementById("app");
  app.append(el("h1", {}, "Raid days"), el("p", { class: "lede" }, `${ds.length} raid days, ${reports().length} group reports. Pick a day to compare its groups, then a group to see its players.`));
  const last = ds[ds.length - 1], ls = stats(last.groups);
  // the longest pull of all, and the mechanic it got to (the last one that had started)
  const far = reports().flatMap(r => r.pulls.map(q => ({ ...q, day: r.day, group: r.group }))).reduce((a, q) => (!a || q.dur > a.dur ? q : a), null);
  const reached = far && Object.entries(DATA.benchmark.mech_start).filter(([m, t]) => m !== "other" && t <= far.dur).sort((a, b) => b[1] - a[1])[0];
  app.append(tiles([
    ["Pulls", num(all.pulls), `${all.kills} kills`],
    ["Best pull", `${all.best.toFixed(1)}% HP`, "lowest boss HP reached"],
    ["Furthest seen", far ? mmss(far.dur) : "–", far ? `${far.kill ? "kill" : reached ? reached[0] : "opener"} · ${dayName(far.day)} ${far.group}, pull ${far.n}` : ""],
    ["Latest day", dayName(last.day), `${last.groups.length} group${last.groups.length > 1 ? "s" : ""}, ${ls.pulls} pulls`],
    ["Mistakes per pull", ls.mistakesPerPull?.toFixed(2), "latest day, per player", grade("mistakes", ls.mistakesPerPull)],
  ]));
  const series = f => ds.map(d => ({ x: dayName(d.day), y: f(stats(d.groups)) }));
  // burndown over every pull, as on tomestone.gg
  const P = allPulls(), ok = P.filter(p => !p.echo && p.boss != null), best = ok.length ? Math.min(...ok.map(p => p.boss)) : null;
  const bd = card("Burndown", info("Every pull's boss HP at its end, all groups together in the order they were played (thin line), and the best so far (steps); dotted lines mark the first pull that reached each mechanic. Hover a pull for its day, group and how it ended. Pulls with The Echo are drawn but not counted for the best line."),
    burndownChart(P), () => tableOf(["Pull", "Day", "Group", "Boss HP", "Ended"], P.map((p, i) => [String(i + 1), dayName(p.day), p.group, p.boss != null ? `${p.boss.toFixed(1)}%` : "–", p.kill ? "Kill" : p.wipe ? p.wipe.label : "–"])));
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
        () => tableOf(["Mechanic", ...ds.map(d => dayName(d.day))], DATA.benchmark.windows.map((w, i) => [w.name, ...ds.map(d => { const x = cleanThrough(pullsOf(d))[i];
          return x.share != null ? `${pct(x.share)} (${x.left}/${x.entered})` : "–"; })])));
    })(),
    card("Mistakes per pull", info("Per player, counted until each pull was lost. The dashed line divides the same mistakes by the minutes players spent in pulls (up to where each pull was lost), so longer pulls as the groups progress do not read as more mistakes."),
      lineChart(series(s => s.mistakesPerPull), { yFmt: v => v.toFixed(2), name: "per pull", extra: [{ points: series(s => s.mistakesPerMin), name: "per minute", cls: "x-min", color: "#9b6cf2" }] }),
      () => tableOf(["Day", "Mistakes per pull", "Per minute in pulls"], ds.map(d => { const s2 = stats(d.groups); return [dayName(d.day), s2.mistakesPerPull.toFixed(2), s2.mistakesPerMin != null ? s2.mistakesPerMin.toFixed(3) : "–"]; }))),
    card("Damage lost to mistakes", info("Boss HP per pull lost to mistakes before each pull was lost, valued at the player's own rDPS in that phase. Deaths: time dead and the raise's Weakness (−22% damage for 100 s). Damage Down: −38% damage while it lasts. Both measured from players' own hits in these logs. Reports with The Echo are left out."),
      lineChart(series(s => s.lostPerPull), { yFmt: v => `${v.toFixed(1)}%`, name: "combined",
        extra: [{ points: series(s => s.lostPerPull != null && s.lostDDPerPull != null ? s.lostPerPull - s.lostDDPerPull : null), name: "deaths", cls: "x-death" },
                { points: series(s => s.lostDDPerPull), name: "Damage Down", cls: "x-dd" }] }),
      () => tableOf(["Day", "Combined", "Deaths", "Damage Down"], ds.map(d => { const s2 = stats(d.groups);
        return [dayName(d.day), hpfmt(s2.lostPerPull), hpfmt(s2.lostPerPull != null && s2.lostDDPerPull != null ? s2.lostPerPull - s2.lostDDPerPull : null), hpfmt(s2.lostDDPerPull)]; }))),
    card("Party DPS 0:00–2:00", info(`Clean pulls. Clears ~${kfmt(DATA.benchmark.pools.clears.party_dps_median)}. Minimum to clear ~${kfmt(DATA.benchmark.pools.clears.party_dps_min)}: the 0:00–2:00 party DPS that is on pace to kill just before enrage (7:38), if the rest of the fight goes like a clear's (clears do about 11% more in their first two minutes than their fight average).`),
      lineChart(series(s => s.party), { yFmt: v => kfmt(v), yMin: 60000, yMax: 100000,
        refs: [{ value: DATA.benchmark.pools.clears.party_dps_median, label: "clears" }, { value: DATA.benchmark.pools.clears.party_dps_min, label: "min to clear", cls: "ref-min" }] }), () => tableOf(["Day", "Party DPS"], ds.map(d => [dayName(d.day), kfmt(stats(d.groups).party)]))),
  ));
  app.append(el("h2", {}, "Days"), el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, ["Day", "Groups", "Pulls", "Best HP", "Longest", "Clean ≤2:00", "Party DPS", "Mistakes/pull", "Top wipe cause"].map((h, i) => el("th", { class: i && i < 8 ? "num" : null }, h)))),
    el("tbody", {}, [...ds].reverse().map(d => { const s = stats(d.groups); const tr = linkRow([dayName(d.day), String(d.groups.length), String(s.pulls), `${s.best.toFixed(1)}%`, mmss(s.longest),
      pct(s.clean2 / s.pulls), kfmt(s.party), s.mistakesPerPull.toFixed(2), s.topWipe ? `${s.topWipe[0]} (${s.topWipe[1]})` : "–"], `#/day/${d.day}`); tr.lastChild.className = ""; return tr; })))));
}

function dayPage(day) {
  const d = days().find(x => x.day === day);
  if (!d) return notFound();
  crumbs([["Raid days", "#/"], [dayName(day), null]]);
  const s = stats(d.groups), app = document.getElementById("app");
  app.append(el("h1", {}, dayName(day)), el("p", { class: "lede" }, `${d.groups.length} group${d.groups.length > 1 ? "s" : ""}. Pick a group for its player scorecard and pulls.`));
  app.append(tiles([
    ["Pulls", num(s.pulls), `${s.kills} kills`], ["Best pull", `${s.best.toFixed(1)}% HP`, `longest ${mmss(s.longest)}`],
    ["Mistakes per pull", s.mistakesPerPull.toFixed(2), "per player", grade("mistakes", s.mistakesPerPull)],
    ["Party DPS 0:00–2:00", kfmt(s.party), `clears ~${kfmt(DATA.benchmark.pools.clears.party_dps_median)} · min to clear ~${kfmt(DATA.benchmark.pools.clears.party_dps_min)}`],
    budgetTile(d.groups),
  ]));
  app.append(el("h2", {}, "Groups"), el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, ["Group", "Pulls", "Best HP", "Longest", "Clean ≤2:00", "Party DPS", "Mistakes/pull", "Lost to deaths/pull", "Top wipe cause"].map((h, i) => el("th", { class: i && i < 8 ? "num" : null }, h)))),
    el("tbody", {}, d.groups.map(r => { const g = stats([r]); const tr = linkRow([r.echo ? `${r.group} (Echo)` : r.group, String(r.pulls_total), `${r.best.toFixed(1)}%`, mmss(r.longest), pct(r.clean2 / r.pulls_total),
      kfmt(r.party), g.mistakesPerPull.toFixed(2), hpfmt(g.lostPerPull), g.topWipe ? `${g.topWipe[0]} (${g.topWipe[1]})` : "–"], `#/day/${day}/${r.group}`); tr.lastChild.className = ""; return tr; })))));
  app.append(heading("h2", "Boss HP checkpoints", "Boss HP when each mechanic begins, as points ahead of or behind the pace for a kill at enrage (Clear). Hover a row for the exact HP."),
    el("div", { class: "grid wide" }, d.groups.map(r => card(r.group, `${r.pulls_total} pulls`, checkpointChart(r.hp), () => checkpointTable(r.hp), checkpointLegend()))));
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
  app.append(el("h1", {}, `${group} · ${dayName(day)}`), el("p", { class: "lede" }, `Report ${r.code}. Pick a player for their mistakes, damage and trend.`), echoNote(r));
  app.append(tiles([
    ["Pulls", String(r.pulls_total), `${r.kills} kills`], ["Best pull", `${r.best.toFixed(1)}% HP`, `longest ${mmss(r.longest)}`],
    ["Mistakes per pull", s.mistakesPerPull.toFixed(2), "per player", grade("mistakes", s.mistakesPerPull)],
    ["Party DPS 0:00–2:00", kfmt(r.party), `clears ~${kfmt(b.pools.clears.party_dps_median)} · min ~${kfmt(b.pools.clears.party_dps_min)}`],
    ["Lost to mistakes", hpfmt(s.lostPerPull), s.lostPerPull != null ? `per pull: deaths ${hpfmt(s.lostPerPull - (s.lostDDPerPull || 0))} · Damage Down ${hpfmt(s.lostDDPerPull)}` : "per pull"],
    budgetTile([r]),
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
        ((p.mdeath || 0) / p.pulls).toFixed(2), ((p.mdd || 0) / p.pulls).toFixed(2),
        el("span", {}, pct(p.wrate), gradeChip(grade("wipes", p.wrate))),
        p.vs ? el("span", {}, `${signed(p.vs[0])}${p.vs[1] < 3 ? "*" : ""}`, gradeChip(vsG)) : (p.samples ? `no ${JOB[p.job] || p.job} clears` : "no clean 2:00 pull"),
        p.uptime != null ? el("span", {}, `${p.uptime.toFixed(1)}%`, gradeChip(grade("uptime", p.uptime_diff))) : "–"], `#/day/${day}/${group}/${encodeURIComponent(p.name)}`, 2));
    }
  }
  app.append(heading("h2", "Player scorecard", "Mistakes per pull counts every mistake until the pull was lost; Deaths/pull and DD/pull split it into mistakes that killed someone and those that only gave Damage Down. Wipes: share of pulls their mistake lost. vs Clears: rDPS 0:00–2:00 (best quarter of clean pulls) against clearers on the same job (clears without The Echo; a job with fewer than three such players also counts its Echo clears, damage divided by 1.2); * = only 1–2 clearers. Uptime: GCD time vs clearers of the role."), el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, head.map((h, i) => el("th", { class: i >= 2 ? "num" : null }, h)))), el("tbody", {}, rows))));
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
        p.wipe ? p.wipe.culprits.join(", ") : (p.kill ? "kill" : "–"), p.wipe ? p.wipe.label : "", String(p.mistakes.length)]))),
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
      card("What each player's mistakes cost", info("Boss HP per pull lost to deaths they caused (their own or others')."),
        hbarChart(costRows, { fmt: v => `${v.toFixed(2)}%` }), () => tableOf(["Player", "Caused per pull", "Own deaths cost per pull", "Dead per pull"],
          costRows.map(x => [x.label, `${x.value.toFixed(2)}%`, `${(x.p.lost_suffered / x.p.pulls).toFixed(2)}%`, `${(x.p.dead_s / x.p.pulls).toFixed(1)} s`]))),
      causeCost.length ? card("What the losses came from", info("Boss HP per pull, by the mistake behind each death."), hbarChart(causeCost, { fmt: v => `${v.toFixed(2)}%` }),
        () => tableOf(["Cause", "Per pull", "Total"], causeAll.map(x => [x.label, `${x.value.toFixed(2)}%`, `${(x.value * r.pulls_total).toFixed(1)}%`]))) : null));
  // damage per phase
  const W = b.windows.map(w => w.name);
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
    causeMatrix("Wipes by player", "The mistake that lost the pull.", cols, c => wipeCounts(r, c.p.name))),
    el("p", { class: "note" }, `Light parties inferred from the White Flame baits: LP1 ${r.light_parties[0].join(", ")} · LP2 ${r.light_parties[1].join(", ")}.`));
}

function playerPage(day, group, name) {
  const r = findGroup(day, group);
  const entries = r ? r.players.filter(p => p.name === name) : [];
  if (!entries.length) return notFound();
  crumbs([["Raid days", "#/"], [dayName(day), `#/day/${day}`], [group, `#/day/${day}/${group}`], [name, null]]);
  const app = document.getElementById("app"), b = DATA.benchmark, p = entries[0];
  app.append(el("h1", {}, name), el("p", { class: "lede" }, `${entries.map(e => JOB[e.job] || e.job).join(" / ")} · ${group} · ${dayName(day)} · ${p.pulls} pulls`), echoNote(r));
  app.append(tiles([
    ["Mistakes per pull", p.mrate.toFixed(2), `${p.mdeath || 0} deaths · ${p.mdd || 0} Damage Downs in ${p.pulls} pulls`, grade("mistakes", p.mrate)],
    ["Wipes caused", pct(p.wrate), `${p.wipes} of ${p.pulls} pulls`, grade("wipes", p.wrate)],
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
    return { label, value, values: [of.filter(lostIt).length, of.filter(m => !lostIt(m) && m.kind !== "DD").length, of.filter(m => !lostIt(m) && m.kind === "DD").length] }; });
  app.append(el("h2", {}, "Mistakes"), el("div", { class: "grid wide" },
    causeRows.length ? card("Mistakes by cause", { info: `${p.mistakes} mistakes (${p.mdeath || 0} deaths, ${p.mdd || 0} Damage Downs), counted until each pull was lost. Lost the pull: the mistake that ended a pull (the pull's wipe names them, within 2.5 s), usually a death, sometimes a Damage Down; the rest split into other deaths and Damage Downs. A wipe put on them without a recorded mistake of theirs (an unsoaked tower, say) counts in Wipes caused but has no bar here.` },
      hbarStackChart(causeRows, KIND_SERIES),
      () => tableOf(["Cause", "Lost the pull", "Other deaths", "Damage Down", "Total"], causeRows.map(x => [x.label, ...x.values.map(String), String(x.value)])))
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
  const SHOW_MISTAKE_COST = false;   // "What their mistakes cost" card, hidden for now; set true to bring it back
  const costBy = Object.entries(p.lost_caused_by || {}).sort((a, c) => c[1] - a[1]).map(([label, value]) => ({ label, value }));
  app.append(el("h2", {}, "Damage"), el("div", { class: "grid wide" },
    ...entries.map(e => {
      const rows = (e.phases || []).map(ph => ({ label: ph.window, v: ph.n >= MIN_PHASE && ph.vs ? ph.vs[0] : null, thin: ph.vs && ph.vs[1] < 3,
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
  app.append(el("h2", {}, "Every mistake"), el("div", { class: "table-wrap" }, mine.length ? el("table", {},
    el("thead", {}, el("tr", {}, ["Pull", "Time", "Mechanic", "What happened", "", "Practice"].map((h, i) => el("th", { class: i < 2 ? "num" : null }, h)))),
    el("tbody", {}, mine.map(m => el("tr", {}, el("td", { class: "num" }, el("a", { href: `#/day/${day}/${group}/pulls/${m.pull}` }, String(m.pull))), el("td", { class: "num" }, mmss(m.t)), el("td", {}, shortMech(m.mechanic || "")),
      el("td", { class: "wrap" }, m.cause), el("td", { class: "muted" }, wiped.some(q => q.n === m.pull && Math.abs(q.wipe.t - m.t) < 2.5) ? "lost the pull" : ""),
      el("td", {}, drillLinks(m.mechanic) || "")))))
    : el("div", { class: "empty", style: "padding:14px" }, "No mistakes recorded.")));
  // across raid days
  const hist = reports().flatMap(x => x.players.filter(q => q.name === name).map(q => ({ ...q, day: x.day, group: x.group }))).sort((a, c) => a.day.localeCompare(c.day));
  const byDay = Object.values(hist.reduce((a, q) => ((a[q.day + q.group] = a[q.day + q.group] || []).push(q), a), {}));
  app.append(heading("h2", "Across raid days", "Their top issues: the three mistakes they made most over all raid days, each per pull that reached the mechanic it happens in (the pull not yet lost when the mechanic began), so getting further in later raid days does not read as more mistakes. Each row is one mistake in one mechanic, named as in the mistake tables (Trinity of Souls in Para I and in Dialogos are separate rows). Rotation issues: the latest raid day's costliest, per minute alive, on the same job only. Trend: the later half of their raid days against the earlier half, 20% or more apart."));
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
    const pts = f => byDay.map(es => ({ x: `${dayName(es[0].day)} ${es[0].group}`, y: f(es) }));
    const perMin = es => { const rep = findGroup(es[0].day, es[0].group); if (!rep) return null;   // as on the overview, for one player
      const m = sum(rep.pulls.filter(q => q.players.includes(name)).map(q => Math.min(q.dur, q.wipe ? q.wipe.t + 2 : q.dur) / 60));
      return m ? es[0].mistakes / m : null; };   // mistakes are per player, repeated on each job entry
    app.append(el("div", { class: "grid" },
      card("Mistakes per pull", info("Counted until each pull was lost. The dashed line divides the same mistakes by the minutes they spent in pulls (up to where each pull was lost), so longer pulls as the groups progress do not read as more mistakes."),
        lineChart(pts(es => es[0].mrate), { yFmt: v => v.toFixed(2), name: "per pull", extra: [{ points: pts(perMin), name: "per minute", cls: "x-min", color: "#9b6cf2" }] }),
        () => tableOf(["Day", "Mistakes per pull", "Per minute in pulls"], byDay.map(es => [`${dayName(es[0].day)} ${es[0].group}`, es[0].mrate.toFixed(2), perMin(es) != null ? perMin(es).toFixed(3) : "–"]))),
      card("Wipes caused", info("Share of pulls."), lineChart(pts(es => es[0].wrate), { yFmt: v => pct(v), yMax: Math.max(0.4, ...byDay.map(es => es[0].wrate)) }), () => tableOf(["Day", "Wipes"], byDay.map(es => [`${dayName(es[0].day)} ${es[0].group}`, pct(es[0].wrate)]))),
    ));
  }
  app.append(el("div", { class: "table-wrap", style: "margin-top:12px" }, el("table", {},
    el("thead", {}, el("tr", {}, ["Day", "Group", "Job", "Pulls", "Mistakes/pull", "Wipes", "vs Clears", "Uptime"].map((h, i) => el("th", { class: i >= 3 ? "num" : null }, h)))),
    el("tbody", {}, hist.map(q => linkRow([dayName(q.day), q.group, JOB[q.job] || q.job, String(q.pulls), q.mrate.toFixed(2), pct(q.wrate), q.vs ? signed(q.vs[0]) : "–",
      q.uptime != null ? `${q.uptime.toFixed(1)}%` : "–"], `#/day/${q.day}/${q.group}/${encodeURIComponent(name)}`, 3))))));
}

// one pull: every player's pull_detail entry for it
const inPull = (r, n) => r.players.flatMap(p => (p.pull_detail || []).filter(x => x.n === n).map(x => ({ p, x })));
const pullEnd = p => p.kill ? "Kill" : p.wipe ? `${p.wipe.label}${p.wipe.culprits.length ? ` (${p.wipe.culprits.join(", ")})` : ""}` : "–";
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
  const nav = el("p", { class: "lede" },
    ...(r.pulls.some(q => q.n === n - 1) ? [el("a", { href: pullHref(day, group, n - 1) }, `← Pull ${n - 1}`), el("span", { class: "muted" }, "  ·  ")] : []),
    ...(r.pulls.some(q => q.n === n + 1) ? [el("a", { href: pullHref(day, group, n + 1) }, `Pull ${n + 1} →`)] : []));
  app.append(el("h1", {}, `Pull ${n} · ${group} · ${dayName(day)}`), nav);
  app.append(tiles([
    ["Length", mmss(p.dur), p.kill ? "kill" : `boss at ${p.boss != null ? p.boss.toFixed(1) : "–"}%`],
    ["Ended", p.kill ? "Kill" : p.wipe ? mmss(p.wipe.t) : "–", p.wipe ? `${p.wipe.label}${p.wipe.culprits.length ? ` · ${p.wipe.culprits.join(", ")}` : ""}` : ""],
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
      el("td", { class: "wrap" }, m.cause),
      el("td", { class: "muted" }, p.wipe && Math.abs(p.wipe.t - m.t) < 0.05 && p.wipe.culprits.includes(m.who) ? "lost the pull" : "")))))
    : el("div", { class: "empty", style: "padding:14px" }, "No mistakes recorded.")));
}

// ---------- the optimizer's rotations (tools/rotation/dps.py --site): per job, one per GCD it was searched at ----------
const rotsOf = job => ((DATA.rotations || {})[job] || {}).rotations;
const fightOf = job => ((DATA.rotations || {})[job] || {}).fight;
const jobOf = code => Object.keys(JOB).find(j => JOB[j] === code) || code;
const jobName = job => job.replace(/([a-z])([A-Z])/g, "$1 $2");
const rotHref = (job, key) => `#/rotations${job ? `/${JOB[job] || job}` : ""}${key ? `/${key}` : ""}`;
const speedStat = job => ["BlackMage", "Summoner", "RedMage", "Pictomancer", "WhiteMage", "Scholar", "Astrologian", "Sage"].includes(job) ? "Spell Speed" : "Skill Speed";
const rotLabel = x => `${x.gcd.toFixed(2)} s GCD${x.crit != null ? ` · ${Math.round(100 * x.crit)}% crit` : ""}`;
const rotClock = t => t < 0 ? `−${Math.abs(t).toFixed(1)} s` : `${Math.floor(t / 60)}:${(t % 60).toFixed(1).padStart(4, "0")}`;   // pre-cast before the pull
// what P1 until Palladion asks of each job under our strategy, from the optimizer's findings (tools/rotation/README.md):
// a line, then [where, what, stretches] points; stretches are what the point marks on the fight timeline while hovered:
// a lane's bands ("away", "pinned") or [from, to] in seconds. "Cost" figures are the best rotation over the whole phase
// against standing still
const ROT_CHALLENGES = {
  BlackMage: ["The most running of the hard-casting jobs: 36 s of Movement before Palladion, the dark bands (26 s) from our raidplan, and every run stops a hard cast and pulls you out of Ley Lines.", [
    ["Paradeigma I", "R1 runs out to the wall end of the bait line (the 3.1 s band from 0:27), then swaps 28 y through the middle: 4.7 s of running in the 5.3 s band from 0:37. The rotation saves its instants for it (Xenoglossy, Paradox, a Firestarter Fire III after Transpose, Thunder): every GCD in the swap is one.", [[27.3, 42.9]]],
    ["Ley Lines", "Its circle is 3 y, so nearly every Movement band takes you out of it. Run as late as the band allows to keep it while you can, and Between the Lines back once it's done."],
    ["Superchain I", "Five runs of 7–15 y in 28 s (spread), the row of dark bands from 1:58: slidecasts and instants cover them.", [[118.3, 146.6]]],
    ["Cost", "Only about 0.2% against standing still: nearly every run fits into instants, slidecasts and weaves."]]],
  Reaper: ["Few casts to protect, so the fight takes its toll on positionals and reach.", [
    ["Spot fixed", "Paradeigma I–III and Superchain I pin you to a spot, the four orange bands (77 s in all); Gibbet and Gallows only get their positional there under True North, so both charges go to those mechanics.", ["pinned"]],
    ["Out of reach", "The red bands: 2.5 s on end somewhere in the band from 2:53 to Paradeigma III's tethers, and 1.2 s before Palladion. Fill them with Harpe, Harvest Moon or Communio, which reach from anywhere.", ["away"]],
    ["Hard casts", "Communio, Harpe and Soulsow can't go during a Movement band's run."],
    ["Cost", "About 1.3% against standing still, mostly the order the rotation has to bend into around the fixed spots."]]],
  Monk: ["Nothing a Monk deals damage with reaches past the melee, so the fight's fixed spots and stretches out of reach are what it pays for.", [
    ["Spot fixed", "Paradeigma I–III and Superchain I pin you to a spot, the four orange bands (77 s in all); six True Norths keep Snap Punch's flank and Demolish's rear there.", ["pinned"]],
    ["Out of reach", "The red bands: 2.5 s on end somewhere in the band from 2:53 to Paradeigma III's tethers, 1.2 s before Palladion. Only the meditations (1 s recast), Form Shift and Enlightenment work from there: step out right after Phantom Rush and meditate twice.", ["away"]],
    ["Burst", "Brotherhood at 0:01, 2:02 and 4:03 with Riddle of Fire, which comes back every minute; eight Perfect Balances by Palladion turn into Elixir Field, Rising Phoenix and Phantom Rush."],
    ["Crit rate", "Chakra comes from critical hits, so each GCD is searched at our players' crit rates: five points more crit gives The Forbidden Chakra more often, about 0.5–0.8% more potency."],
    ["Six-Sided Star", "Only at the timeline's right edge, as Athena leaves (4:40): anywhere else it about ties the rotation.", [[278.4, 281.6]]],
    ["GCD", "Skill Speed buys less than it costs: expected DPS at 2.45 s comes out about 0.7% above 2.40 s at a like crit rate."],
    ["Cost", "About 1.3% against standing still in M1 and 1.8% in M2 (the two within the optimizer's noise): the fixed spots' True Norths and the stretches out of reach."]]],
  Bard: ["Every action is instant and reaches 25 y, so our runs cost a Bard nothing; what P1 asks is to keep the songs turning and the burst on the Minuet.", [
    ["Movement", "R1, R2 and standing still play the same rotation: no Movement band needs anything from it."],
    ["Songs", "The Wanderer's Minuet every two minutes (0:01, 2:01–2:05 and 4:03–4:06), with Raging Strikes, Battle Voice and Barrage (into Refulgent Arrow) on each. Mage's Ballad and Army's Paeon fill the minute between in either order: the searches at different GCDs pick each, within the optimizer's noise.", [[0, 18.0], [121.7, 139.7], [243.5, 261.5]]],
    ["Radiant Finale", "Where it goes barely changes your own damage, so the searches put it anywhere: with the Minuet at 2.45 s, in the Ballad or the Paeon at 2.49 and 2.50 s. The optimizer counts your own damage only, and what Radiant Finale gives the rest of the party isn't in it: in a party, put it with Battle Voice, as at 2.45 s."],
    ["Apex Arrow", "At 80 Soul Voice or more, then Blast Arrow right after: five of each by Palladion. Stormbite and Caustic Bite go out once in the opener; Iron Jaws keeps them up from then on."],
    ["Palladion", "The third Minuet burst (from 4:03–4:06) ends before Athena leaves at the timeline's right edge (4:41).", [[243.5, 281.6]]],
    ["GCD", "Skill Speed buys about what it costs: expected DPS at 2.45, 2.49 and 2.50 s comes out within 0.4%, the optimizer's noise."],
    ["Cost", "Nothing against standing still."]]],
  Dragoon: ["Positionals and its DoT are what the mechanics squeeze.", [
    ["Spot fixed", "Paradeigma I–III and Superchain I pin you to a spot, the four orange bands (77 s in all); the optimizer spends five or six True Norths there to keep the combo's positionals.", ["pinned"]],
    ["Chaotic Spring and Power Surge", "Both have to be kept up through those bands; the rotation alternates the two combos to do it."],
    ["Out of reach", "The red bands: 2.5 s on end somewhere in the band from 2:53 to Paradeigma III's tethers, 1.2 s before Palladion. Elusive Jump into an Enhanced Piercing Talon fills them, and the jumps reach from anywhere.", ["away"]],
    ["Cost", "About 0.9% against standing still."]]],
  RedMage: ["Uptime in Paradeigma I is the hard part: a far spot and a long run come while the opener's cooldowns are still away.", [
    ["Paradeigma I", "R1 runs out to the wall end, 18.3 y from Athena's centre, and is out of reach of the melee combo around the bait (the red band at 0:37), then swaps 28 y through the middle: 4.7 s of running in the 5.3 s band from 0:37.6. Swiftcast, Acceleration and Manafication are all still on cooldown from the opener, so nothing makes a spell instant: the rotation runs through on Enchanted Reprise (two at 2.49 s) or a Corps-a-corps it held back.", [[27.3, 42.9]]],
    ["Corps-a-corps", "From the wall right after the bait (0:37.6, where the swap's band starts) it rushes you to Athena's hitbox edge and saves about 1.3 s of the swap, room for a hard cast, but only with a charge back: at 2.45–2.49 s the opener's two uses come out ahead, at 2.23 s the optimizer holds one.", [[37.6, 42.9]]],
    ["R2", "Crosses the middle first and heads out after, so Displacement comes too late to turn a GCD into a hard cast: R2 costs about 1.3% against R1's 0.5% (the timeline shows R1)."],
    ["Superchain I", "The spread's Heavensflame corner is 21.5 y out: the red band at 2:25, 2.5 s out of reach at the end of the last Movement band. Finish the melee combo before you go and land Verholy, Scorch and Resolution (25 y) on the way.", [[143.5, 147.9]]]]],
  Viper: ["The melee job the fight costs least, about 0.4% against standing still.", [
    ["Spot fixed", "Paradeigma I–III and Superchain I pin you to a spot, the four orange bands (77 s in all); six True Norths cover all ten finisher positionals there.", ["pinned"]],
    ["Out of reach", "The red bands: 2.5 s on end somewhere in the band from 2:53 to Paradeigma III's tethers, 1.2 s before Palladion. Uncoiled Fury (20 y) and the twinblade GCDs' 3 s recast fill them, so keep a Rattling Coil for when you have to leave.", ["away"]],
    ["Reawaken", "Its Generations need you within 5 y, so line it up outside the red bands.", ["away"]]]],
  Samurai: ["Runs and fixed spots cost little; the stretches out of reach and Palladion are what to plan.", [
    ["Iaijutsu", "The 1.3 s casts fit around every Movement band of our strategy."],
    ["Spot fixed", "Paradeigma I–III and Superchain I pin you to a spot, the four orange bands (77 s in all); True North takes Gekko's and Kasha's positionals there.", ["pinned"]],
    ["Out of reach", "The red bands: 2.5 s on end somewhere in the band from 2:53 to Paradeigma III's tethers, 1.2 s before Palladion, worth about 0.5%. Enpi (20 y) fills them, enhanced by Hissatsu: Yaten. Iaijutsu, Ogi Namikiri and Shoha reach 6–10 y and may still land a little farther out.", ["away"]],
    ["Palladion", "Athena leaves at the timeline's right edge (4:41) for 44 s: let Higanbana run out before then rather than refresh it into the downtime, and spend the downtime on Tengentsu and Meditate.", [[261.4, 281.6]]],
    ["Cost", "About 0.7% against standing still."]]],
  Pictomancer: ["Short casts and plenty of instants make our runs cheap; what P1 takes from a Pictomancer is Inspiration in Superchain I, and the time its motifs need.", [
    ["Paradeigma I", "R1 runs out to the wall end (the 3.1 s band from 0:27), then swaps 28 y through the middle: 4.7 s of running in the 5.3 s band from 0:37.6. The second Striking Muse's hammers and Holy in White are the instants for it: paint the hammer just before (Swiftcast on Hammer Motif at 2.31 and 2.49 s), so its three hammers land in the bands.", [[27.3, 42.9]]],
    ["Smudge", "Dash in the swap (0:38–0:39): it covers 15 y of the run, 2.5 s, room for a hard cast before the band ends.", [[37.6, 42.9]]],
    ["Starry Muse in Superchain I", "The second one comes back at 2:02–2:09, right into Superchain I's runs. Its landscape is a circle of about 8 y around where you cast it, and the 15 y run into the second doughnut (the band from 2:09.6) takes you out of it: only one or two colour spells get Inspiration's haste there, against four at 0:02 and 4:05–4:10. Spend the stacks before that run; the hammers, Comet and the muses still get the 5%.", [[122.3, 136.8]]],
    ["Motifs", "Each is a 3 s cast on a 4 s recast that Spell Speed doesn't shorten. Swiftcast goes on a motif (or a hard cast in a run), and the next pom or wings get painted as soon as a Living Muse charge is back, so the charges never sit full."],
    ["GCD", "As motifs don't speed up, Spell Speed buys less than it costs: expected DPS at 2.49 s comes out about 2% above 2.31 s."],
    ["Palladion", "Spend White Paint on Holy in White and Comet in Black before Athena leaves at the timeline's right edge (4:41), and repaint all three canvases in the 44 s downtime.", [[261.4, 281.6]]],
    ["Cost", "About 0.5% against standing still in R1 (about 1% in R2), half of it Inspiration lost in Superchain I."]]],
  Machinist: ["Every action is instant and reaches 25 y, so our runs cost a Machinist nothing; what P1 asks is to fit the burst and the queen around Palladion.", [
    ["Movement", "R1, R2 and standing still play the same rotation: no Movement band needs anything from it."],
    ["Wildfire", "With a Hypercharge every two minutes, at 0:08 (on Barrel Stabilizer's free one), about 2:10 and 4:14: its five Blazing Shots and the next GCD make its six.", [[8.0, 18.7], [130.9, 141.6], [254.1, 264.8]]],
    ["Queen", "She fights for 17.4 s (Crowned Collider last) and makes about 24 potency of each battery point, whenever she goes out: send her at 50 or more before the battery overcaps, but not in the last 17 s before Palladion. The last one goes out around 4:00–4:08; keep what builds after it (50 by Palladion) for when Athena is back.", [[264.2, 281.6]]],
    ["Reassemble", "Only on Drill, Air Anchor or Chain Saw, starting with one pressed before the pull for the first tool."],
    ["Palladion", "Put the last Reassemble on a tool just before Athena leaves at the timeline's right edge (4:41); heat and battery keep through the downtime.", [[261.4, 281.6]]],
    ["GCD", "Skill Speed buys about what it costs: expected DPS at 2.41, 2.45 and 2.49 s comes out within 0.2%."],
    ["Cost", "Nothing against standing still."]]],
  Ninja: ["Ninjutsu and Phantom Kamaitachi reach 20 y and nothing is a hard cast, so our runs cost a Ninja almost nothing; what P1 asks is to keep the mudra charges turning and the burst inside Trick Attack.", [
    ["Opener", "Make Ten, Chi and Jin before the pull and open on Suiton: its Shadow Walker goes straight into Trick Attack, then Dokumori, Ten Chi Jin (Fuma Shuriken, Raiton, Suiton, then Meisui into Bhavacakra), Raiton, Bunshin and Kassatsu into Hyosho Ranryu, all inside Trick Attack's 15 s.", [[0, 16.5]]],
    ["Mudras", "Two charges, one back every 20 s: never let both sit full. Each Raiton gives a Raiju Ready; spend it on Fleeting Raiju before the next combo weaponskill, which ends it. Suiton goes in the 20 s before each Trick Attack, for its Shadow Walker."],
    ["Spot fixed", "Paradeigma I–III and Superchain I pin you to a spot, the four orange bands (77 s in all); six True Norths cover Aeolian Edge, Armor Crush and Trick Attack's rear there.", ["pinned"]],
    ["Out of reach", "The red bands: 2.5 s on end somewhere in the band from 2:53 to Paradeigma III's tethers, 1.2 s before Palladion. Mudras and their ninjutsu (2.5–3 s without a melee action) or Phantom Kamaitachi fill them.", ["away"]],
    ["Palladion", "The two-minute burst at 4:06–4:20 (Dokumori, Trick Attack, Kassatsu, Ten Chi Jin) lands just before Athena leaves at the timeline's right edge (4:41); end on a Raiton and its Raiju.", [[246.0, 281.6]]],
    ["GCD", "Skill Speed buys less than it costs: expected DPS at 2.50 s comes out about 2% above 2.41 s."],
    ["Expected DPS", "None of our players plays Ninja, so it converts at the four Ninjas of the benchmark clears since patch 7.3, whose damage per potency differs by up to 40% between them: read it as a rough figure. No player page links here yet."],
    ["Cost", "About 0.1% against standing still, within the optimizer's noise."]]],
  Summoner: ["Ruin III slidecasts and nearly everything else is instant, so our runs cost a Summoner nothing; what P1 asks is to spend every Arcanum between demi-summons and fit the last cycle before Palladion.", [
    ["Opener", "Pre-cast Ruin III to land at the pull, then Summon Bahamut with Searing Light and Energy Drain woven, Enkindle Bahamut and Deathflare inside the trance's six Astral Impulses.", [[0, 16.5]]],
    ["Demi-summons", "Summon Bahamut and Summon Phoenix alternate on a 60 s that Spell Speed shortens (58.8 s at 2.45 s, 57 s at 2.31 s): five by Palladion. Their four pet hits come on their own timer, so only the trance's 15 s matters, not what you cast in it."],
    ["Primals", "After each trance, Titan (four Topaz Rites, a Mountain Buster after each), Ifrit (two Ruby Rites, Crimson Cyclone into Crimson Strike) and Garuda (Slipstream, four Emerald Rites) in any order: the optimizer changes the order from cycle to cycle, a near-tie. Summon the next one only once the last one's Rites and favor are spent."],
    ["Crimson Cyclone", "It rushes you to Athena, so keep it out of Paradeigma I–III and Superchain I, where our raidplan holds you to a spot (from each mechanic's first cue to its last snapshot): every Ifrit's Favor waits for the stretch between them.", [[27.3, 42.9], [67.6, 82.7], [118.3, 146.6], [207.2, 225.3]]],
    ["Swiftcast", "On a Ruby Rite, Slipstream or Ruin III: no Movement band needs it."],
    ["Searing Light", "Every two minutes as it comes back: 0:02–0:05, 2:02–2:06 and 4:04–4:07.", [[2.1, 24.7], [122.5, 146.2], [243.8, 267.0]]],
    ["Out of reach", "Crimson Strike reaches only 3 y past Athena's hitbox: not at the red bands' far spots (0:37 in R1, 2:25 in Superchain I's spread).", ["away"]],
    ["Palladion", "After the trance that starts around 4:00, Titan and Ifrit fit before Athena leaves at the timeline's right edge (4:41) but Garuda doesn't (at 2.31 s the earlier demi fits all three): its Arcanum is lost to the next demi-summon.", [[239.1, 281.6]]],
    ["GCD", "Spell Speed buys less than it costs: expected DPS at 2.49 s comes out about 2% above 2.31 s."],
    ["Cost", "About 0.2% against standing still in R1, within the optimizer's noise; nothing in R2."]]],
  Dancer: ["Every action is instant and reaches 15–25 y, so our runs cost a Dancer nothing; what P1 asks is to keep the dances turning and pour the Esprit and feathers into the two-minute windows before Palladion.", [
    ["Opener", "Standard Step about 14 s before the pull and its two steps, Standard Finish as Athena is pulled, then Flourish, Devilment and Technical Step: Starfall Dance and Tillana follow the finish, and the next Standard Step goes inside the window at 0:18.", [[0, 24.5]]],
    ["Technical Step", "Every two minutes as it comes back: 0:04, 2:04–2:07 and 4:06–4:07. Its 20 s window brings the whole party's Esprit, so Saber Dances come almost back to back there; Tillana adds 50 more.", [[3.9, 30.5], [124.0, 147.0], [246.6, 268.5]]],
    ["Devilment", "Next to Technical Step, so Starfall Dance falls inside both. For your own damage, just before the Step or just after the finish is a near-tie (the optimizer goes either way); after the finish is what the party wants, since your partner gets it too."],
    ["Standard Step", "Every ~32 s, not quite on cooldown: nine or ten finishes before Palladion, and Standard Finish (with its Esprit) never lapses. Each dance is worth more than the two GCDs it takes."],
    ["Procs", "Reverse Cascade and Fountainfall spend Silken Symmetry and Flow before Flourish's, so Flourish wastes nothing but a held Threefold or Fourfold Fan Dance: five of them by Palladion."],
    ["Esprit", "The party's share is random (about 0.7 a second from your partner, six times that from everyone in Technical Finish's window): the optimizer counts it at its average, so spend Saber Dance at 50 when your gauge says so, not on its schedule."],
    ["Palladion", "Tillana and the last Saber Dances go before Athena leaves at the timeline's right edge (4:41); in the 44 s downtime, dance the steps of the next Standard Step so its finish lands as she returns.", [[259.0, 281.6]]],
    ["GCD", "Skill Speed buys about what it costs: expected DPS at 2.40, 2.45 and 2.49 s comes out within 1.5%."],
    ["Raid buffs", "Technical Finish, and Standard Finish and Devilment on your partner, add to the others' damage: the scorecard credits that from each pull; the rotation here is for your own."],
    ["Cost", "Nothing against standing still."]]],
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
  return el("div", { class: "lede challenges" }, el("p", {}, c[0], marks.size ? " Hover or tap a point to mark it on the timeline below." : ""),
    el("ul", {}, c[1].map(([where, what], k) => {
      const li = el("li", marks.has(k) ? { tabindex: "0", "data-k": k } : {}, el("strong", {}, `${where}. `), what);
      if (marks.has(k)) focusOn(li, k);
      return li;
    })));
}

// a job whose conversion came from the scorecard's cached logs while FFLogs was down (dps.py --offline)
// whose conversion a job's expected DPS is: our players', or the benchmark clears' for a job none of ours plays (dps.py)
const convWho = (job, n, code) => { const r = (DATA.rotations || {})[job] || {}, s = n > 1 ? "s" : "";
  return r.converted_from === "clears" ? `the ${n} ${code} player${s} of the benchmark clears since ${r.converted_since} (none of our players plays ${jobName(job)}: their gear may convert differently)` : `our ${n} ${code} player${s}`; };
const offlineNote = job => ((DATA.rotations || {})[job] || {}).offline ? " Converted from the scorecard's cached logs while FFLogs was down: they have no crit or direct-hit flags and no record of others' buffs on a hit, so hits under raid buffs are left out and crits are read from each player's damage. On Black Mage, where both are available, this reads 0–3% higher than the full logs." : "";
const ROT_ABOUT = "The highest-damage rotation the optimizer (tools/rotation) finds for P12S P1 from the pull until Palladion takes Athena away (4:41), without anyone's raid buffs, with the runs our strategy needs at their worst for the role: the Paradeigma I slot with the most running (R1 or R2 for ranged, M1 or M2 for melee) and each mechanic's variant with the most, so it holds whichever the player is given. Expected DPS converts its potency at our players' damage per potency and crit / direct-hit gain on the job (the median), each player moved to the rotation's GCD first: the Spell or Skill Speed for a faster GCD comes out of the same gear budget as critical hit, direct hit and determination, so a faster GCD converts lower; a player's own ceiling, the best over 0:00–2:00 (the scorecard's window, a search of its own) at their own conversion, is on their page. It is the best for the player's own damage; a party's buff windows may favour holding a resource a little longer.";

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
      band("pinned", lo, hi, 0.55, "", `${mech}: spot fixed`, [[`${rotClock(lo)}–${rotClock(hi)}${past(hi)}`, "the plan fixes where they stand: positionals need True North", true]]);
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
// a line for each stretch between major mechanics; a bar under a GCD cast while running
function rotationStrip(rows, f, icons) {
  const segs = [{ name: "Opener", t: -Infinity }, ...(f ? f.mechanics.map(([t, n]) => ({ name: shortMech(n), t })) : [])];
  const icon = (name, cls) => icons[name] ? el("img", { class: cls, src: icons[name], alt: name, draggable: "false" })
    : el("span", { class: `${cls} noicon` }, name.split(/[\s']+/).map(w => w[0]).join("").slice(0, 3));   // no icon: initials
  return el("div", { class: "rot-strip" }, segs.map((sg, i) => {
    const end = i + 1 < segs.length ? segs[i + 1].t : Infinity, mine = rows.filter(r => r.t >= sg.t && r.t < end);
    if (!mine.length) return null;
    return el("div", { class: "rot-seg" }, el("div", { class: "rot-seg-label" }, sg.name, isFinite(sg.t) ? el("span", {}, rotClock(sg.t)) : null),
      el("div", { class: "rot-icons" }, mine.map(r => {
        const g = el("div", { class: `rot-g${r.run ? r.cast ? " moving" : " moving instant" : ""}`, role: "img", "aria-label": [r.gcd, ...r.weaves].filter(Boolean).join(", ") },
          r.gcd ? icon(r.gcd, "gcd") : null, ...r.weaves.map(w => icon(w, "ogcd")));
        hover(g, `${rotClock(r.t)} · ${r.gcd || r.weaves.join(" · ")}`, [
          ...(r.gcd ? [[r.cast ? `${r.cast.toFixed(2)} s` : "instant", r.cast ? "cast" : ""]] : []),
          ...(r.run ? [[`${r.run.toFixed(1)} s`, r.cast ? "running in its slidecast and after it" : "running through it", true]] : []),
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
  return card("Fight timeline", info(`What the rotation${rot ? "" : "s"} play${rot ? "s" : ""} around, slot ${f.slot}. Dotted lines: each major mechanic's start (its boss cast). Movement: our strategy (the raidplan) needs the player to run for the seconds shown somewhere in the band, and the optimizer chose when; a hard cast can't be running, except for its last 0.46 s (a slidecast). Darker bands are our plan's mechanics; lighter ones (pre-position) are the stretches between them, where our plan says nothing and the player runs as the clears' players did (their median path) to get into place for what comes next.${f.away.length ? " Out of reach: that long on end away from the boss, as the clears' melee were." : ""}${f.pinned.length ? " Spot fixed: the plan says where to stand, so a positional needs True North." : ""}${rot ? " Ticks: the rotation's GCDs (tall; green for an instant one run through, blue for a hard cast with running in its slidecast and after) and oGCDs (short); hover a GCD for its running and what is woven after it." : " Each GCD's page draws its rotation on this timeline."}`),
    fightTimeline(f, rot, focus), () => tableOf(["From", "To", "What", "Needs", "Detail"], rows, [0, 1, 3]), legend);
}
const parseClock = c => c.startsWith("−") ? -parseFloat(c.slice(1)) : +c.split(":")[0] * 60 + +c.split(":")[1];

function rotationsPage() {
  crumbs([["Raid days", "#/"], ["Rotations", null]]);
  const app = document.getElementById("app"), all = DATA.rotations || {};
  const jobs = Object.keys(all).filter(j => Object.keys(rotsOf(j) || {}).length).sort((a, c) => jobName(a).localeCompare(jobName(c)));
  app.append(heading("h1", "Optimized rotations", ROT_ABOUT),
    el("p", { class: "lede" }, "The optimizer's best rotation for each job it covers, at every GCD it was searched at: our players' GCDs, plus any extra ones. Pick a job, then a GCD."));
  if (!jobs.length) return app.append(el("p", { class: "empty" }, "No optimized rotations yet: run tools/rotation/dps.py --job <job> --site, then build_site.py."));
  app.append(el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, ["Job", "GCDs", "Fastest", "Slowest", "Best expected DPS", "Our players"].map((h, i) => el("th", { class: i ? "num" : null }, h)))),
    el("tbody", {}, jobs.map(j => { const xs = Object.values(rotsOf(j)), g = xs.map(x => x.gcd);
      return linkRow([jobName(j), String(xs.length), `${Math.min(...g).toFixed(2)} s`, `${Math.max(...g).toFixed(2)} s`,
        num(Math.max(...xs.map(x => x.dps))), all[j].converted_from === "clears" ? "none" : String(xs[0].conv_players)], rotHref(j)); })))));
}

function rotationJobPage(code) {
  const job = jobOf(code), rs = rotsOf(job);
  if (!rs) return notFound();
  crumbs([["Raid days", "#/"], ["Rotations", "#/rotations"], [code, null]]);
  const app = document.getElementById("app"), keys = Object.keys(rs).sort((a, c) => rs[a].gcd - rs[c].gcd || (rs[a].crit || 0) - (rs[c].crit || 0));
  const best = Math.max(...keys.map(k => rs[k].dps)), crit = keys.some(k => rs[k].crit != null), n = rs[keys[0]].conv_players;
  app.append(heading("h1", `${jobName(job)} rotations`, `${ROT_ABOUT} Here: ${keys.length} GCD${keys.length > 1 ? "s" : ""}${crit ? " and crit rates (the job's resources come from crits)" : ""}, 0:00–${mmss(rs[keys[0]].window)}, Paradeigma I slot ${(fightOf(job) || {}).slot || "–"}; expected DPS is the median of ${convWho(job, n, code)}, each moved to the GCD (a faster GCD costs ${speedStat(job)} out of their other substats, about ${(DATA.rotations[job].speed_cost || 0.4).toFixed(2)}% damage per 0.01 s).${offlineNote(job)}`),
    rotChallenges(job, fightOf(job)));
  if (fightOf(job)) app.append(fightCard(fightOf(job), null, challengeFocus(job, fightOf(job))));
  app.append(el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, ["GCD", ...(crit ? ["Crit"] : []), `Potency 0:00–${mmss(rs[keys[0]].window)}`, "Potency/s", "Expected DPS", "vs best", "Ceiling 0:00–2:00", "Our players at it"]
      .map((h, i) => el("th", { class: i ? "num" : null }, h)))),
    el("tbody", {}, keys.map(k => { const x = rs[k];
      return linkRow([`${x.gcd.toFixed(2)} s`, ...(crit ? [x.crit != null ? pct(x.crit) : "–"] : []), num(x.potency), num(x.potency / x.window, 1),
        num(x.dps), x.dps === best ? "best" : signed(x.dps / best - 1, 1), num(x.ceiling_2min), String(x.players)], rotHref(job, k)); })))));
}

function rotationPage(code, key) {
  const job = jobOf(code), x = (rotsOf(job) || {})[key];
  if (!x) return notFound();
  crumbs([["Raid days", "#/"], ["Rotations", "#/rotations"], [code, rotHref(job)], [rotLabel(x).replace(" GCD", ""), null]]);
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
    el("p", { class: "lede" }, `0:00–${mmss(x.window)}, no raid buffs${x.crit != null ? `, ${pct(x.crit)} critical-hit rate (the chakra it opens)` : ""}, with our strategy's runs${plan.length ? ` (${plan.map(([m, v]) => `${shortMech(m)} ${v}`).join(", ")})` : ""}. ${x.players ? `${x.players} of our players ${x.players > 1 ? "play" : "plays"} at this GCD; their pages link here.` : (DATA.rotations[job] || {}).converted_from === "clears" ? `None of our players plays ${jobName(job)}: searched at the GCDs of the benchmark clears' ${code}s and extra ones.` : "Searched as an extra GCD: none of our players is at it."}`));
  if (f) app.append(fightCard(f, rot));
  app.append(tiles([
    [el("span", {}, "Expected DPS", help(`The median of ${convWho(job, x.conv_players, code)} (their damage per potency and crit / direct-hit gain), each moved to this ${x.gcd.toFixed(2)} s GCD: the ${speedStat(job)} that takes comes out of their critical hit, direct hit or determination, or goes back into them, about ${(DATA.rotations[job].speed_cost || 0.4).toFixed(2)}% damage per potency per 0.01 s (level-90 formulas; our Black Mages' gear shows the same). ${num(x.dps_lo)}–${num(x.dps_hi)} across them.${offlineNote(job)}`)), num(x.dps)],
    ["Potency", num(x.potency), `${num(x.potency / x.window, 1)} per second`],
    [el("span", {}, "Ceiling 0:00–2:00", help("DPS of the best rotation over 0:00–2:00 alone (the scorecard's window, behind players' ceilings), converted the same way.")), num(x.ceiling_2min)],
    ["GCDs", String(nG), `with ${rot.length - nG} oGCDs · ${nRun} while running`],
    ["Resources wasted", waste.length ? String(waste.reduce((s2, [, v]) => s2 + v, 0)) : "none", waste.length ? waste.map(([w, v]) => `${w} ×${v}`).join(" · ") : "nothing overcapped or dropped"],
  ]));
  app.append(
    card("Rotation", { info: `${nG} GCDs, read left to right, a line for each stretch between major mechanics. Each GCD's icon sits on the line with the oGCDs woven after it smaller and raised beside it; hover one for its time, cast and running. A bar under a GCD: the player runs between it and the next GCD (part of the runs our strategy needs). Green: the GCD is instant (a proc, Swiftcast or Triplecast, or an instant skill), so they run right through it. Blue: it is a hard cast, so the run fits only in its slidecast and the gap before the next GCD. The optimizer only makes sure each run fits outside cast bars (a hard cast's last 0.46 s, its slidecast, counts); here each is placed in its window's longest stretches outside cast bars first, as late as they allow, so it lands on instant GCDs where it can. The table has the times; there "after its cast" means the GCD is a hard cast and the run comes in its slidecast and the gap before the next GCD. A negative time is a pre-cast before the pull.` },
      () => rotationStrip(rows, f, icons),
      () => { const tbl = tableOf(["Time", "GCD", "Cast", "Running", "Woven after it"], rows.map(r => [rotClock(r.t), r.run ? `▸ ${r.gcd}` : r.gcd,
          r.gcd ? r.cast ? `${r.cast.toFixed(2)} s` : "instant" : "", r.run ? `${r.run.toFixed(1)} s${r.cast ? ", after its cast" : ""}` : "", r.weaves.join(" · ")]), [0, 2, 3]);
        [...tbl.tBodies[0].rows].forEach((tr, i) => { if (rows[i].run) tr.classList.add("moving"); });
        return tbl; },
      [el("span", {}, el("i", { style: "width:16px;height:3px;border-radius:2px;background:var(--good)" }), "instant, run through it"),
       el("span", {}, el("i", { style: "width:16px;height:3px;border-radius:2px;background:var(--series)" }), "hard cast, run in its slidecast and after"),
       el("span", {}, "small, raised: oGCDs woven after the GCD")]),
    el("div", { class: "grid wide" }, card("Casts per skill", info(`How often the rotation casts each skill over 0:00–${mmss(x.window)}; the table adds whether it is a GCD and its first use.`),
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
      stat("Ceiling", num(e.ceiling), `DPS at ${e.ceiling_gcd ? e.ceiling_gcd.toFixed(2) + " s" : "their"} GCD`)),
    el("a", { href: x ? rotHref(e.job, e.ceiling_key) : rotHref(rotsOf(e.job) ? e.job : null) }, x ? `Rotation at ${rotLabel(x)} →` : "Optimized rotations →"));
}

const echoNote = r => r.echo ? el("p", { class: "warn" }, `The Echo was on in ${r.echo.pulls === r.echo.of ? "all" : `${r.echo.pulls} of`} ${r.echo.of} pulls (+20% damage, HP and healing). Their damage figures are left out: rDPS against clearers, damage by phase, opener damage, party DPS and boss HP checkpoints. Mistakes, deaths and rotation checks still count.`) : "";   // "" appends nothing (null would print "null")

function notFound() {
  crumbs([["Raid days", "#/"], ["Not found", null]]);
  document.getElementById("app").append(el("h1", {}, "Not found"), el("p", { class: "lede" }, "That day, group, player or rotation is not in the data."), el("a", { href: "#/" }, "Back to the raid days"));
}

// ---------- routing, theme, boot ----------
function route(keepScroll = false) {   // keepScroll: redraw the same page in place (resize, theme), not a navigation
  if (LOCKED) return;   // the passphrase screen stays until it is unlocked
  hideTip();
  const y = scrollY;
  const app = document.getElementById("app"); app.replaceChildren();
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  if (!DATA || (!reports().length && parts[0] !== "rotations")) { app.append(el("h1", {}, "No data yet"), el("p", { class: "lede" }, "Run build_site.py with some report links, then reload.")); return; }
  if (parts[0] === "rotations" && parts.length === 1) rotationsPage();
  else if (parts[0] === "rotations" && parts.length === 2) rotationJobPage(parts[1]);
  else if (parts[0] === "rotations" && parts.length === 3) rotationPage(parts[1], parts[2]);
  else if (parts[0] === "day" && parts.length === 2) dayPage(parts[1]);
  else if (parts[0] === "day" && parts.length === 3) groupPage(parts[1], parts[2]);
  else if (parts[0] === "day" && parts.length === 4 && parts[3] === "pulls") pullsPage(parts[1], parts[2]);
  else if (parts[0] === "day" && parts.length === 5 && parts[3] === "pulls") pullPage(parts[1], parts[2], +parts[4]);
  else if (parts[0] === "day" && parts.length === 4) playerPage(parts[1], parts[2], parts[3]);
  else home();
  if (!keepScroll) scrollTo(0, 0);
  else requestAnimationFrame(() => requestAnimationFrame(() => scrollTo(0, y)));   // after the charts have drawn and set the height
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
// ---------- data: plaintext data.json (private hosting) or data.enc.json behind a passphrase (public hosting) ----------
let LOCKED = false;
const b64d = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
const b64e = buf => btoa(String.fromCharCode(...new Uint8Array(buf)));
const sessionKeyName = env => `p12s-key:${env.salt}`;
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
async function unlock(env) {
  if (!window.crypto || !crypto.subtle) throw new Error("This page has to be opened over https (or on localhost) to decrypt its data.");
  if (env.compressed === "gzip" && !window.DecompressionStream) throw new Error("This browser is too old to open the data; please update it.");
  try {   // a key remembered earlier in this browser session
    const raw = sessionStorage.getItem(sessionKeyName(env));
    if (raw) return await openEnvelope(env, await crypto.subtle.importKey("raw", b64d(raw), "AES-GCM", true, ["decrypt"]));
  } catch (e) { try { sessionStorage.removeItem(sessionKeyName(env)); } catch (e2) {} }
  crumbs([["Locked", null]]);
  return new Promise(resolve => {
    const input = el("input", { type: "password", id: "pass", autocomplete: "current-password", required: true });
    const remember = el("input", { type: "checkbox", id: "remember", checked: true });
    const msg = el("p", { class: "note", role: "status" });
    const btn = el("button", { type: "submit", class: "primary" }, "Unlock");
    const form = el("form", { class: "unlock" },
      el("label", { for: "pass" }, "Passphrase"), input,
      el("label", { class: "check" }, remember, " Remember for this browser session"), btn, msg);
    form.addEventListener("submit", async e => {
      e.preventDefault(); btn.disabled = true; msg.textContent = "Unlocking…";
      try {
        const key = await deriveKey(input.value, env), data = await openEnvelope(env, key);
        if (remember.checked) try { sessionStorage.setItem(sessionKeyName(env), b64e(await crypto.subtle.exportKey("raw", key))); } catch (e2) {}
        resolve(data);
      } catch (err) { msg.textContent = "That passphrase does not open the data."; btn.disabled = false; input.select(); }
    });
    document.getElementById("app").replaceChildren(el("h1", {}, "Locked"),
      el("p", { class: "lede" }, "The scorecards are encrypted. Enter the raid's passphrase to open them; it never leaves this browser."), form);
    input.focus();
  });
}
function lockAgain() {
  try { for (const k of Object.keys(sessionStorage)) if (k.startsWith("p12s-key:")) sessionStorage.removeItem(k); } catch (e) {}
  location.reload();
}
async function boot() {
  setupTheme();
  document.getElementById("lock").addEventListener("click", lockAgain);
  try {
    let r = await fetch("data.json", { cache: "no-store" });
    if (r.ok) DATA = await r.json();
    else {
      r = await fetch("data.enc.json", { cache: "no-store" });
      if (!r.ok) throw new Error("data.json is missing. Run tools/scorecard/build_site.py with report links, then serve this folder with python -m http.server.");
      LOCKED = true; DATA = await unlock(await r.json()); LOCKED = false;
      document.getElementById("lock").hidden = false;
    }
    route();
  } catch (e) {
    LOCKED = false;
    document.getElementById("app").replaceChildren(el("h1", {}, "Cannot open the data"), el("p", { class: "lede" }, e.message || String(e)));
  }
}
boot();
