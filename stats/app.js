/* P12S progress site: raid days -> groups -> players, drawn from data.json (written by build_site.py).
   Routes: #/  ·  #/day/<date>  ·  #/day/<date>/<group>  ·  #/day/<date>/<group>/<player>
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
const num = (v, d = 0) => v == null ? "–" : v.toLocaleString("en-GB", { minimumFractionDigits: d, maximumFractionDigits: d });
const dayName = d => new Date(d + "T12:00").toLocaleDateString("en-GB", { weekday: "short", day: "numeric", month: "short" });
const sum = xs => xs.reduce((a, b) => a + b, 0);
const median = xs => { const s = [...xs].sort((a, b) => a - b); return s.length ? (s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : null; };
const JOB = { Paladin: "PLD", Warrior: "WAR", DarkKnight: "DRK", Gunbreaker: "GNB", WhiteMage: "WHM", Scholar: "SCH", Astrologian: "AST", Sage: "SGE",
  Monk: "MNK", Dragoon: "DRG", Ninja: "NIN", Samurai: "SAM", Reaper: "RPR", Viper: "VPR", Bard: "BRD", Machinist: "MCH", Dancer: "DNC",
  BlackMage: "BLM", Summoner: "SMN", RedMage: "RDM", Pictomancer: "PCT" };
const ROLES = ["Tank", "Healer", "Melee", "Ranged", "Caster"];

// grades: ✓ good, ~ ok, ! focus; thresholds come from the scorecard (data.benchmark.grades)
function grade(kind, v) {
  if (v == null) return null;
  const [good, ok] = DATA.benchmark.grades[kind];
  const lowerBetter = kind === "mistakes" || kind === "wipes";
  const g = lowerBetter ? (v <= good ? "good" : v <= ok ? "ok" : "bad") : (v >= good ? "good" : v >= ok ? "ok" : "bad");
  return g;
}
function gradeChip(g) {
  if (!g) return "";
  return el("span", { class: `g ${g}`, title: { good: "good", ok: "ok", bad: "focus" }[g] }, { good: "✓", ok: "~", bad: "!" }[g]);
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
    party: withParty.length ? sum(withParty.map(r => r.party * r.clean2)) / sum(withParty.map(r => r.clean2)) : null,
    topWipe: Object.entries(wipeCauses).sort((a, b) => b[1] - a[1])[0], wipeCauses,
  };
}
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

// ---------- chart frame: a card with a title, caption, legend and a table-view twin ----------
function card(title, caption, draw, table, legend) {
  const body = el("div", { class: "chart" });
  const tbl = el("div", { class: "table-wrap", hidden: true });
  const btn = el("button", { type: "button", "aria-pressed": "false" }, "Table");
  btn.addEventListener("click", () => {
    const on = tbl.hidden; tbl.hidden = !on; body.hidden = on; btn.textContent = on ? "Chart" : "Table"; btn.setAttribute("aria-pressed", String(on));
    if (on && !tbl.firstChild) tbl.append(table());
  });
  const f = el("figure", { class: "card" }, el("div", { class: "card-head" }, el("h3", {}, title), btn), caption ? el("figcaption", {}, caption) : null, body,
    legend ? el("div", { class: "legend" }, legend) : null, tbl);
  requestAnimationFrame(() => { body.append(draw(Math.max(260, body.clientWidth || 360))); });
  return f;
}
function tableOf(head, rows, numericFrom = 1) {
  return el("table", {}, el("thead", {}, el("tr", {}, head.map((h, i) => el("th", { class: i >= numericFrom ? "num" : null }, h)))),
    el("tbody", {}, rows.map(r => el("tr", {}, r.map((c, i) => el("td", { class: i >= numericFrom ? "num" : null }, c))))));
}
const clip = (text, px) => { const n = Math.max(4, Math.floor(px / 6)); return text.length > n ? text.slice(0, n - 1) + "…" : text; };
function niceMax(v) { const p = Math.pow(10, Math.floor(Math.log10(v || 1))); for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p; return 10 * p; }
function ticks(max, n = 4) { const step = max / n; return Array.from({ length: n + 1 }, (_, i) => i * step); }

// line chart, one series over raid days (x = categories)
function lineChart(points, { yFmt = v => v, yMax, yMin = 0, invert = false, refs = [] } = {}) {
  return width => {
    const H = 170, L = 44, R = refs.length ? 64 : 16, T = 12, B = 26, w = width - L - R, h = H - T - B;
    const vals = points.map(p => p.y).filter(v => v != null);
    const top = yMax ?? niceMax(Math.max(...vals, ...refs.map(r => r.value)) * 1.1), lo = yMin;
    const X = i => L + (points.length === 1 ? w / 2 : (i * w) / (points.length - 1));
    const Y = v => invert ? T + ((v - lo) / (top - lo)) * h : T + h - ((v - lo) / (top - lo)) * h;
    const svg = sv("svg", { viewBox: `0 0 ${width} ${H}`, role: "img" });
    for (const t of ticks(top - lo)) { const v = lo + t; svg.append(sv("line", { class: "gridline", x1: L, x2: L + w, y1: Y(v), y2: Y(v) }), sv("text", { x: L - 6, y: Y(v) + 4, "text-anchor": "end" }, yFmt(v))); }
    const n = points.length;
    points.forEach((p, i) => svg.append(sv("text", { x: X(i), y: H - 6, "text-anchor": n > 1 && i === 0 ? "start" : n > 1 && i === n - 1 ? "end" : "middle" }, p.x)));
    for (const r of refs) svg.append(sv("line", { class: "ref", x1: L, x2: L + w, y1: Y(r.value), y2: Y(r.value), "stroke-opacity": 0.6 }),
      sv("text", { class: "lbl", x: L + w + 4, y: Y(r.value) + 4 }, r.label));
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
    return svg;
  };
}

// columns (one series), with optional horizontal reference lines
function columnChart(bars, { yFmt = v => v, yMax, refs = [], barTip, tickStep } = {}) {
  return width => {
    const H = 220, L = 44, R = 70, T = 12, B = 26, w = width - L - R, h = H - T - B;
    const raw = Math.max(...bars.map(b => b.value), ...refs.map(r => r.value)) * 1.05;
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
      svg.append(hit, m);
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
      hover(hit, r.label, [[fmt(r.value), r.sub || "", true]]);
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
      svg.append(sv("text", { class: "val", x: width - 4, y: y + 4, "text-anchor": "end" }, `${best.toFixed(1)}% ${{ good: "✓", ok: "~", bad: "!" }[g]}`));
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
  el("span", {}, "right: best HP · ✓ at Comfy · ~ at Clear · ! behind"),
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
  app.append(tiles([
    ["Pulls", num(all.pulls), `${all.kills} kills`],
    ["Best pull", `${all.best.toFixed(1)}% HP`, "lowest boss HP reached"],
    ["Latest day", dayName(last.day), `${last.groups.length} group${last.groups.length > 1 ? "s" : ""}, ${ls.pulls} pulls`],
    ["Clean through 2:00", pct(ls.clean2 / ls.pulls), "latest day, share of pulls"],
    ["Mistakes per pull", ls.mistakesPerPull?.toFixed(2), "latest day, per player", grade("mistakes", ls.mistakesPerPull)],
  ]));
  const series = f => ds.map(d => ({ x: dayName(d.day), y: f(stats(d.groups)) }));
  app.append(el("h2", {}, "Over time"), el("div", { class: "grid" },
    card("Best boss HP", "Lowest HP any group reached that day; lower is better.", lineChart(series(s => s.best), { yFmt: v => `${v.toFixed(0)}%`, yMax: 100, invert: true }),
      () => tableOf(["Day", "Best HP"], ds.map(d => [dayName(d.day), `${stats(d.groups).best.toFixed(1)}%`]))),
    card("Pulls clean through 2:00", "Share of pulls with no death or Damage Down before 2:00.", lineChart(series(s => s.clean2 / s.pulls), { yFmt: v => pct(v), yMax: 1 }),
      () => tableOf(["Day", "Clean"], ds.map(d => { const s = stats(d.groups); return [dayName(d.day), pct(s.clean2 / s.pulls)]; }))),
    card("Mistakes per pull", "Per player, counted until each pull was lost.", lineChart(series(s => s.mistakesPerPull), { yFmt: v => v.toFixed(2) }),
      () => tableOf(["Day", "Mistakes per pull"], ds.map(d => [dayName(d.day), stats(d.groups).mistakesPerPull.toFixed(2)]))),
    card("Party DPS 0:00–2:00", `Clean pulls. Peer clears ~${kfmt(DATA.benchmark.pools.peer.party_dps_median)}, fast clears ~${kfmt(DATA.benchmark.pools.fast.party_dps_median)}.`,
      lineChart(series(s => s.party), { yFmt: v => kfmt(v), yMin: 60000, yMax: 100000,
        refs: [{ value: DATA.benchmark.pools.peer.party_dps_median, label: "peer" }, { value: DATA.benchmark.pools.fast.party_dps_median, label: "fast" }] }), () => tableOf(["Day", "Party DPS"], ds.map(d => [dayName(d.day), kfmt(stats(d.groups).party)]))),
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
    ["Clean through 2:00", pct(s.clean2 / s.pulls), `${s.clean2} of ${s.pulls} pulls`],
    ["Mistakes per pull", s.mistakesPerPull.toFixed(2), "per player", grade("mistakes", s.mistakesPerPull)],
    ["Party DPS 0:00–2:00", kfmt(s.party), `peer clears ~${kfmt(DATA.benchmark.pools.peer.party_dps_median)}`],
  ]));
  app.append(el("h2", {}, "Groups"), el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, ["Group", "Pulls", "Best HP", "Longest", "Clean ≤2:00", "Party DPS", "Mistakes/pull", "Top wipe cause"].map((h, i) => el("th", { class: i && i < 7 ? "num" : null }, h)))),
    el("tbody", {}, d.groups.map(r => { const g = stats([r]); const tr = linkRow([r.group, String(r.pulls_total), `${r.best.toFixed(1)}%`, mmss(r.longest), pct(r.clean2 / r.pulls_total),
      kfmt(r.party), g.mistakesPerPull.toFixed(2), g.topWipe ? `${g.topWipe[0]} (${g.topWipe[1]})` : "–"], `#/day/${day}/${r.group}`); tr.lastChild.className = ""; return tr; })))));
  app.append(el("h2", {}, "Boss HP checkpoints"), el("p", { class: "lede" }, "Boss HP when each mechanic begins, as points ahead of or behind the pace for a kill at enrage (Clear). Hover a row for the exact HP."),
    el("div", { class: "grid wide" }, d.groups.map(r => card(r.group, `${r.pulls_total} pulls`, checkpointChart(r.hp), () => checkpointTable(r.hp), checkpointLegend()))));
  const cols = d.groups.map(r => ({ label: r.group, r }));
  app.append(el("h2", {}, "What went wrong"), el("div", { class: "grid wide" },
    causeMatrix("All mistakes", "Every mistake until each pull was lost, by cause and group.", cols, c => c.r.causes),
    causeMatrix("What wiped us", "The mistake that lost each pull, by cause and group.", cols, c => c.r.wipe_causes)));
}

function groupPage(day, group) {
  const r = findGroup(day, group);
  if (!r) return notFound();
  crumbs([["Raid days", "#/"], [dayName(day), `#/day/${day}`], [group, null]]);
  const s = stats([r]), app = document.getElementById("app"), b = DATA.benchmark;
  app.append(el("h1", {}, `${group} · ${dayName(day)}`), el("p", { class: "lede" }, `Report ${r.code}. Pick a player for their mistakes, damage and trend.`));
  app.append(tiles([
    ["Pulls", String(r.pulls_total), `${r.kills} kills`], ["Best pull", `${r.best.toFixed(1)}% HP`, `longest ${mmss(r.longest)}`],
    ["Clean through 2:00", pct(r.clean2 / r.pulls_total), `${r.clean2} of ${r.pulls_total}`],
    ["Mistakes per pull", s.mistakesPerPull.toFixed(2), "per player", grade("mistakes", s.mistakesPerPull)],
    ["Party DPS 0:00–2:00", kfmt(r.party), `peer ~${kfmt(b.pools.peer.party_dps_median)} · fast ~${kfmt(b.pools.fast.party_dps_median)}`],
  ]));
  // scorecard
  const head = ["Player", "Job", "Pulls", "Mistakes/pull", "Wipes", "vs Peer", "vs Fast", "Uptime"];
  const rows = [];
  for (const role of ROLES) {
    const ps = r.players.filter(p => p.role === role).sort((a, c) => a.wrate - c.wrate || a.mrate - c.mrate);
    if (!ps.length) continue;
    rows.push(el("tr", { class: "role" }, el("td", { colspan: head.length }, role)));
    for (const p of ps) {
      const fastG = p.fast ? grade("damage", p.fast[0]) : null;
      rows.push(linkRow([p.name, JOB[p.job] || p.job, String(p.pulls),
        el("span", {}, p.mrate.toFixed(2), gradeChip(grade("mistakes", p.mrate))),
        el("span", {}, pct(p.wrate), gradeChip(grade("wipes", p.wrate))),
        p.peer ? `${signed(p.peer[0])}${p.peer[1] < 3 ? "*" : ""}` : "–",
        p.fast ? el("span", {}, `${signed(p.fast[0])}${p.fast[1] < 3 ? "*" : ""}`, gradeChip(fastG)) : (p.samples ? `no ${JOB[p.job] || p.job} clears` : "no clean 2:00 pull"),
        p.uptime != null ? el("span", {}, `${p.uptime.toFixed(1)}%`, gradeChip(grade("uptime", p.uptime_diff))) : "–"], `#/day/${day}/${group}/${encodeURIComponent(p.name)}`, 2));
    }
  }
  app.append(el("h2", {}, "Player scorecard"), el("div", { class: "table-wrap" }, el("table", {},
    el("thead", {}, el("tr", {}, head.map((h, i) => el("th", { class: i >= 2 ? "num" : null }, h)))), el("tbody", {}, rows))),
    el("p", { class: "note" }, "Mistakes per pull counts every mistake until the pull was lost. Wipes: share of pulls their mistake lost. vs Peer / Fast: rDPS 0:00–2:00 (best quarter of clean pulls) against clearers on the same job; * = only 1–2 clearers. Uptime: GCD time vs clearers of the role."));
  // pulls
  const cps = b.hp_checkpoints.mechanics;
  const refs = [{ value: 55.4, label: "Para II" }, { value: 112.4, label: "SC I" }, { value: 193.9, label: "Para III" }, { value: 284, label: "Palladion" }, { value: 349, label: "SC II" }];
  const bars = r.pulls.map(p => ({ label: String(p.n), value: p.dur, p }));
  app.append(el("h2", {}, "Pulls"), el("div", { class: "grid wide" },
    card("How far each pull got", "Pull length; lines mark when each mechanic begins. Hover a pull for its first mistake and what lost it.",
      columnChart(bars, { yFmt: v => mmss(v), refs, tickStep: 60, barTip: bar => { const p = bar.p, wv = p.wipe;
        return [`Pull ${p.n} · ${mmss(p.dur)} · boss ${p.boss?.toFixed(1)}%`, [[mmss(p.first), "first death or Damage Down"],
          [wv ? wv.culprits.join(", ") || "unclear" : (p.kill ? "kill" : "unclear"), wv ? `${wv.label} at ${mmss(wv.t)}` : "", true], [String(p.mistakes.length), "mistakes counted"], [String(p.deaths), "deaths"]]]; } }),
      () => tableOf(["Pull", "Length", "Boss HP", "First mistake", "Lost by", "Cause", "Mistakes"], r.pulls.map(p => [String(p.n), mmss(p.dur), `${p.boss?.toFixed(1)}%`, mmss(p.first),
        p.wipe ? p.wipe.culprits.join(", ") : (p.kill ? "kill" : "–"), p.wipe ? p.wipe.label : "", String(p.mistakes.length)]))),
    card("Boss HP checkpoints", "Boss HP when each mechanic begins, as points ahead of or behind the pace for a kill at enrage.", checkpointChart(r.hp), () => checkpointTable(r.hp), checkpointLegend())));
  const cols = [...r.players].filter((p, i, a) => a.findIndex(q => q.name === p.name) === i)
    .sort((a, c) => ROLES.indexOf(a.role) - ROLES.indexOf(c.role)).map(p => ({ label: p.name, p }));
  app.append(el("h2", {}, "Who made which mistakes"), el("div", { class: "grid wide" },
    causeMatrix("All mistakes by player", "Every mistake until each pull was lost.", cols, c => c.p.mcauses_all),
    causeMatrix("Wipes by player", "The mistake that lost the pull.", cols, c => c.p.wcauses_all)),
    el("p", { class: "note" }, `Light parties inferred from the White Flame baits: LP1 ${r.light_parties[0].join(", ")} · LP2 ${r.light_parties[1].join(", ")}.`));
}

function playerPage(day, group, name) {
  const r = findGroup(day, group);
  const entries = r ? r.players.filter(p => p.name === name) : [];
  if (!entries.length) return notFound();
  crumbs([["Raid days", "#/"], [dayName(day), `#/day/${day}`], [group, `#/day/${day}/${group}`], [name, null]]);
  const app = document.getElementById("app"), b = DATA.benchmark, p = entries[0];
  app.append(el("h1", {}, name), el("p", { class: "lede" }, `${entries.map(e => JOB[e.job] || e.job).join(" / ")} · ${group} · ${dayName(day)} · ${p.pulls} pulls`));
  app.append(tiles([
    ["Mistakes per pull", p.mrate.toFixed(2), `${p.mistakes} in ${p.pulls} pulls`, grade("mistakes", p.mrate)],
    ["Wipes caused", pct(p.wrate), `${p.wipes} of ${p.pulls} pulls`, grade("wipes", p.wrate)],
    ...entries.map(e => [`${JOB[e.job] || e.job} vs fast clears`, e.fast ? signed(e.fast[0]) : "–", e.peer ? `vs peer ${signed(e.peer[0])}${e.peer[1] < 3 ? " · thin data" : ""}` : "no comparison", e.fast ? grade("damage", e.fast[0]) : null]),
    ["Uptime 0:00–2:00", p.uptime != null ? `${p.uptime.toFixed(1)}%` : "–", `clearers ${b.pools.peer.role_uptime[p.role].toFixed(1)}%`, grade("uptime", p.uptime_diff)],
  ]));
  const mine = r.pulls.flatMap(q => q.mistakes.filter(m => m.who === name).map(m => ({ ...m, pull: q.n })));
  const wiped = r.pulls.filter(q => q.wipe && q.wipe.culprits.includes(name));
  const causeRows = Object.entries(p.mcauses_all).sort((a, c) => c[1] - a[1]).map(([label, value]) => ({ label, value }));
  app.append(el("h2", {}, "Mistakes"), el("div", { class: "grid wide" },
    causeRows.length ? card("Mistakes by cause", `${p.mistakes} mistakes, counted until each pull was lost.`, hbarChart(causeRows), () => tableOf(["Cause", "Count"], causeRows.map(x => [x.label, String(x.value)])))
      : el("figure", { class: "card" }, el("div", { class: "card-head" }, el("h3", {}, "Mistakes by cause")), el("div", { class: "empty" }, "No mistakes recorded.")),
    ...entries.filter(e => e.clean_pulls.length).map(e => {
      const jb = b.pools, refs = [];
      if (jb.peer.jobs[e.job]) refs.push({ value: jb.peer.jobs[e.job].rdps, label: "peer avg" });
      if (jb.fast.jobs[e.job]) refs.push({ value: jb.fast.jobs[e.job].rdps, label: "fast avg" });
      const bars = e.clean_pulls.map(c => ({ label: String(c.n), value: c.rdps, c }));
      return card(`${JOB[e.job] || e.job} rDPS on clean pulls`, "0:00–2:00 of every pull with no death or Damage Down before 2:00; lines are other clearers' averages on the job.",
        columnChart(bars, { yFmt: v => kfmt(v), refs, barTip: bar => [`Pull ${bar.c.n}`, [[num(bar.c.rdps), "rDPS", true], [`${bar.c.uptime}%`, "uptime"]]] }),
        () => tableOf(["Pull", "rDPS", "Uptime"], e.clean_pulls.map(c => [String(c.n), num(c.rdps), `${c.uptime}%`])));
    })));
  app.append(el("h2", {}, "Every mistake"), el("div", { class: "table-wrap" }, mine.length ? el("table", {},
    el("thead", {}, el("tr", {}, ["Pull", "Time", "Mechanic", "What happened", ""].map((h, i) => el("th", { class: i < 2 ? "num" : null }, h)))),
    el("tbody", {}, mine.map(m => el("tr", {}, el("td", { class: "num" }, String(m.pull)), el("td", { class: "num" }, mmss(m.t)), el("td", {}, m.mechanic),
      el("td", { class: "wrap" }, m.cause), el("td", { class: "muted" }, wiped.some(q => q.n === m.pull && Math.abs(q.wipe.t - m.t) < 2.5) ? "lost the pull" : "")))))
    : el("div", { class: "empty", style: "padding:14px" }, "No mistakes recorded.")));
  // across raid days
  const hist = reports().flatMap(x => x.players.filter(q => q.name === name).map(q => ({ ...q, day: x.day, group: x.group }))).sort((a, c) => a.day.localeCompare(c.day));
  const byDay = Object.values(hist.reduce((a, q) => ((a[q.day + q.group] = a[q.day + q.group] || []).push(q), a), {}));
  app.append(el("h2", {}, "Across raid days"));
  if (byDay.length > 1) {
    const pts = f => byDay.map(es => ({ x: `${dayName(es[0].day)} ${es[0].group}`, y: f(es) }));
    app.append(el("div", { class: "grid" },
      card("Mistakes per pull", null, lineChart(pts(es => es[0].mrate), { yFmt: v => v.toFixed(2) }), () => tableOf(["Day", "Mistakes per pull"], byDay.map(es => [`${dayName(es[0].day)} ${es[0].group}`, es[0].mrate.toFixed(2)]))),
      card("Wipes caused", "Share of pulls.", lineChart(pts(es => es[0].wrate), { yFmt: v => pct(v), yMax: Math.max(0.4, ...byDay.map(es => es[0].wrate)) }), () => tableOf(["Day", "Wipes"], byDay.map(es => [`${dayName(es[0].day)} ${es[0].group}`, pct(es[0].wrate)]))),
    ));
  }
  app.append(el("div", { class: "table-wrap", style: "margin-top:12px" }, el("table", {},
    el("thead", {}, el("tr", {}, ["Day", "Group", "Job", "Pulls", "Mistakes/pull", "Wipes", "vs Peer", "vs Fast", "Uptime"].map((h, i) => el("th", { class: i >= 3 ? "num" : null }, h)))),
    el("tbody", {}, hist.map(q => linkRow([dayName(q.day), q.group, JOB[q.job] || q.job, String(q.pulls), q.mrate.toFixed(2), pct(q.wrate), q.peer ? signed(q.peer[0]) : "–", q.fast ? signed(q.fast[0]) : "–",
      q.uptime != null ? `${q.uptime.toFixed(1)}%` : "–"], `#/day/${q.day}/${q.group}/${encodeURIComponent(name)}`, 3))))));
}

function notFound() {
  crumbs([["Raid days", "#/"], ["Not found", null]]);
  document.getElementById("app").append(el("h1", {}, "Not found"), el("p", { class: "lede" }, "That day, group or player is not in the data."), el("a", { href: "#/" }, "Back to the raid days"));
}

// ---------- routing, theme, boot ----------
function route() {
  if (LOCKED) return;   // the passphrase screen stays until it is unlocked
  hideTip();
  const app = document.getElementById("app"); app.replaceChildren();
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  if (!DATA || !reports().length) { app.append(el("h1", {}, "No data yet"), el("p", { class: "lede" }, "Run build_site.py with some report links, then reload.")); return; }
  if (parts[0] === "day" && parts.length === 2) dayPage(parts[1]);
  else if (parts[0] === "day" && parts.length === 3) groupPage(parts[1], parts[2]);
  else if (parts[0] === "day" && parts.length === 4) playerPage(parts[1], parts[2], parts[3]);
  else home();
  scrollTo(0, 0);
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
    label(); route();
  });
}
let resizeTimer = null;
addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(route, 200); });
addEventListener("hashchange", route);
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
