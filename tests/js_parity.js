// Usage: node tests/js_parity.js output/knesset_2026.html
// Run the page's simulator under node with a stub DOM and compare with Python output.
const fs = require("fs");
const html = fs.readFileSync(process.argv[2], "utf8");
const data = html.match(/<script id="data" type="application\/json">([\s\S]*?)<\/script>/)[1];
const code = html.match(/<script>\n([\s\S]*?)<\/script>/)[1];
const el = () => new Proxy({ addEventListener() {}, setAttribute() {}, querySelector() { return el(); }, getBoundingClientRect() { return {}; }, style: {}, value: "0", checked: true }, { get(t, k) { return k in t ? t[k] : (k === "textContent" ? data : undefined); }, set(t, k, v) { t[k] = v; return true; } });
global.document = { getElementById: (id) => id === "data" ? { textContent: data } : el(), querySelectorAll: () => [] };
global.window = {}; global.performance = { now: () => 0 };
try { eval(code); } catch (e) { console.error("render error:", e.message); }
const D = JSON.parse(data);
const o = { arab: 53, har: 0, likud: 0, opp: 0, swing: 0, unc: 1, hfix: true, pair: true };
for (const a of ["consensus", "ch14_world"]) {
  const js = window.__sim(a, o, 20000, 7), py = D.results[a];
  for (const k of ["gov61", "gov_amcha61", "opp61", "opp_raam61", "opp_haredi61", "deadlock"]) console.log(a, k, "py", py.paths[k].toFixed(3), "js", js.paths[k].toFixed(3));
  console.log(a, "gov seats py", py.blocs.gov.mean.toFixed(2), "js", js.blocs.gov.mean.toFixed(2), "| arab py", py.blocs.arab.mean.toFixed(2), "js", js.blocs.arab.mean.toFixed(2));
}
const t = Date.now(); window.__sim("consensus", o, 6000, 1); console.log("6000 draws ms", Date.now() - t);
// a turnout scenario vs python dynamics
const a45 = window.__sim("consensus", { ...o, arab: 45 }, 20000, 7);
console.log("arab45 gov_amcha61 js", a45.paths.gov_amcha61.toFixed(3), "py", D.dynamics.results.arab_45.gov_amcha61.toFixed(3), "arab seats js", a45.blocs.arab.mean.toFixed(2), "py", D.dynamics.results.arab_45.seats_arab.toFixed(2));
const lk = window.__sim("consensus", { ...o, likud: 10 }, 20000, 7);
console.log("likud10 gov_amcha61 js", lk.paths.gov_amcha61.toFixed(3), "py", D.dynamics.results.likud_home10.gov_amcha61.toFixed(3));
