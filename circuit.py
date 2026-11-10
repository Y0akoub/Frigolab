"""Synoptique cliquable de FrigoLab, rendu avec un composant Streamlit."""

import streamlit as st

COMPONENTS = (
    ("compressor", "01", "Compresseur", "Compression", '<circle cx="12" cy="12" r="9"/><path d="m9 8 6 4-6 4zM1 12h2m18 0h2"/>'),
    ("condenser", "02", "Condenseur", "Rejet de chaleur", '<path d="M3 5h14a3 3 0 0 1 0 6H7a3 3 0 0 0 0 6h14M7 3v16m5-16v16m5-16v16"/>'),
    ("filter", "03", "Déshydrateur", "Ligne liquide", '<rect x="4" y="7" width="16" height="10" rx="4"/><path d="M1 12h3m16 0h3m-8-4v8m-3-8v8"/>'),
    ("expansion", "04", "Détendeur", "Chute de pression", '<path d="M1 12h4m14 0h4M5 7l14 10V7L5 17zm7 5V3m-4 0h8"/>'),
    ("evaporator", "05", "Évaporateur", "Absorption de chaleur", '<path d="M3 5h14a3 3 0 0 1 0 6H7a3 3 0 0 0 0 6h14M7 3v16m5-16v16m5-16v16"/>'),
)

CARDS = "".join(
    f'<button class="node {key}" type="button" data-action="{key}" aria-haspopup="dialog">'
    f'<span class="node-top"><svg viewBox="0 0 24 24" fill="none" stroke="#185ABC" stroke-width="1.6" aria-hidden="true">{icon}</svg>'
    f'<span class="number">{number}</span></span><strong>{title}</strong>'
    f'<span class="subtitle">{subtitle}</span><span class="reading" data-reading="{key}"></span></button>'
    for key, number, title, subtitle, icon in COMPONENTS
)

HTML = """
<section class="instrument" aria-labelledby="circuit-title">
  <header>
    <div class="heading">
      <span class="kicker">FRIGOLAB <span> / </span> CLIMATISATION AIR-AIR</span>
      <h1 id="circuit-title">Circuit frigorifique</h1>
      <p>Clique sur un composant pour saisir ou consulter ses relevés.</p>
    </div>
    <div class="context">
      <span>Configuration du circuit</span>
      <strong data-context>R134a · Paliers en °C</strong>
    </div>
  </header>
  <div class="map" role="group" aria-label="Composants du circuit frigorifique">
    <svg class="pipes" viewBox="0 0 1000 500" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <marker id="arrow-hot" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="10" markerHeight="10" orient="auto" markerUnits="userSpaceOnUse">
          <path fill="#FC413D" d="M0 0l10 5-10 5z"/>
        </marker>
        <marker id="arrow-cold" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="10" markerHeight="10" orient="auto" markerUnits="userSpaceOnUse">
          <path fill="#2473D4" d="M0 0l10 5-10 5z"/>
        </marker>
      </defs>
      <path class="hot" fill="none" stroke="#FC413D" stroke-width="3.5" d="M500 83H786Q810 83 810 107V366Q810 390 786 390H500"/>
      <path class="cold" fill="none" stroke="#2473D4" stroke-width="3.5" d="M500 390H214Q190 390 190 366V107Q190 83 214 83H500"/>
      <path class="hot" fill="none" stroke="#FC413D" stroke-width="3.5" d="M636 83h65m109 216v29m-153 62h-53" marker-end="url(#arrow-hot)"/>
      <path class="cold" fill="none" stroke="#2473D4" stroke-width="3.5" d="M357 390h-50M190 330v-31m114-216h60" marker-end="url(#arrow-cold)"/>
    </svg>
""" + CARDS + """
    <div class="legend" aria-label="Légende des tuyauteries">
      <span class="legend-label">Côtés du circuit</span>
      <span><i class="low"></i><b>BP</b> Basse pression</span>
      <span><i class="high"></i><b>HP</b> Haute pression</span>
    </div>
  </div>
  <footer>
    <button class="secondary" type="button" data-action="settings" aria-haspopup="dialog">Paramètres du circuit</button>
    <div class="progress">
      <label for="exchange-readings">Relevés des échangeurs</label>
      <div class="progress-value"><progress id="exchange-readings" max="8" value="0"></progress><span data-count>0 / 8</span></div>
    </div>
    <button class="primary" type="button" data-action="diagnosis" aria-haspopup="dialog">Analyser les relevés</button>
  </footer>
</section>
"""

CSS = """
:host { display: block; }
* { box-sizing: border-box; }
.instrument {
  --navy: #182844; --muted: #4D607B; --border: #DCE4F0;
  --paper: #F8FAFF; --card: #FFFFFF; --surface: #EDF4FF;
  --cold: #2473D4; --cold-deep: #185ABC; --cold-tint: #E7F5FF;
  --hot: #FC413D; --hot-ink: #B32825; --hot-tint: #FFF0EC;
  --green: #13BD60; --green-ink: #096B3B;
  --spectrum: linear-gradient(90deg, #FF5F95, #FC413D 22%, #FD831F 43%, #FEC004 58%, #13BD60 73%, #0FA3CC 87%, #388DFF);
  border: 1px solid var(--border); border-radius: 18px; overflow: hidden;
  background: var(--paper); color: var(--navy);
  font-family: var(--st-font, system-ui, sans-serif);
  box-shadow: 0 16px 44px #18284417;
}
header {
  padding: 23px 28px; background: var(--card); color: var(--navy);
  border-bottom: 1px solid var(--border); position: relative;
  display: flex; justify-content: space-between; align-items: center; gap: 22px;
}
header::before { content: ""; position: absolute; inset: 0 0 auto; height: 5px; background: var(--spectrum); }
.kicker { font-size: .69rem; font-weight: 750; letter-spacing: .12em; color: var(--cold-deep); }
.kicker span { color: #617697; padding: 0 .22rem; }
h1 { font-size: clamp(1.68rem, 4.1vw, 2.48rem); line-height: 1.1; margin: .4rem 0; }
header p { font-size: .89rem; margin: 0; color: var(--muted); }
.context {
  min-width: 161px; padding: 9px 12px; border: 1px solid #D7E4FA;
  border-radius: 9px; background: #F0F6FF;
}
.context span, .context strong { display: block; }
.context span { color: var(--muted); font-size: .69rem; }
.context strong { margin-top: 3px; color: var(--cold-deep); font-size: .82rem; white-space: nowrap; }
.map {
  position: relative; isolation: isolate; height: clamp(414px, 56vh, 505px);
  background: radial-gradient(#C9D7EB .72px, transparent .72px) 0 0 / 19px 19px, var(--paper);
}
.pipes { position: absolute; width: 100%; height: 100%; inset: 0; }
.pipes > path { fill: none; stroke-width: 3.5; vector-effect: non-scaling-stroke; }
.hot { stroke: var(--hot); }
.cold { stroke: var(--cold); }
button { font: inherit; color: inherit; cursor: pointer; }
button:focus-visible { outline: 3px solid var(--cold-deep); outline-offset: 3px; }
.node {
  --accent: #185ABC; --tint: #EAF1FF;
  position: absolute; width: min(24%, 184px); padding: 10px 12px;
  transform: translate(-50%, -50%); border: 1px solid var(--border);
  border-top: 3px solid var(--accent); border-radius: 11px;
  background: var(--card); color: var(--navy); text-align: left;
  min-height: 105px; box-shadow: 0 4px 13px #18284414;
  transition: box-shadow .16s, border-color .16s;
}
.node:hover, .node:focus-visible { border-color: var(--accent); box-shadow: 0 7px 19px #1828442B; }
.node-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 5px; }
.node-top svg {
  width: 28px; height: 28px; padding: 4px; border-radius: 7px; background: var(--tint);
  fill: none; stroke: var(--accent); stroke-width: 1.6; stroke-linecap: round; stroke-linejoin: round;
}
.number { font-size: .66rem; font-weight: 750; color: var(--muted); font-variant-numeric: tabular-nums; }
.node strong, .subtitle, .reading { display: block; }
.node strong { font-size: clamp(.77rem, 1.65vw, .97rem); line-height: 1.2; }
.subtitle { color: var(--muted); font-size: .68rem; line-height: 1.25; margin-top: 2px; }
.reading {
  color: var(--accent); font-size: .71rem; line-height: 1.25; font-weight: 750;
  font-variant-numeric: tabular-nums; margin-top: 6px;
}
.has-data .reading { color: var(--green-ink); }
.has-data .reading::before { content: ""; display: inline-block; width: 6px; height: 6px; border-radius: 50%; background: var(--green); margin-right: 5px; vertical-align: 1px; }
.compressor { top: 16.6%; left: 50%; }
.condenser { top: 43%; left: 81%; }
.filter { top: 78%; left: 81%; }
.expansion { top: 78%; left: 50%; }
.evaporator { top: 43%; left: 19%; --accent: var(--cold-deep); --tint: var(--cold-tint); }
.condenser, .filter { --accent: var(--hot-ink); --tint: var(--hot-tint); border-top-color: var(--hot); }
.expansion { --accent: #8A5900; --tint: #FFF2CE; border-top-color: #FEC004; }
.legend {
  position: absolute; left: 50%; top: 47%; transform: translate(-50%, -50%);
  display: grid; gap: .35rem; padding: .6rem .78rem; border-radius: 9px;
  border: 1px solid var(--border); color: var(--muted); background: var(--card);
  font-size: .74rem; white-space: nowrap;
}
.legend-label { color: var(--navy); font-weight: 750; }
.legend b { margin-right: 2px; color: var(--navy); }
.legend i { display: inline-block; width: 14px; height: 3px; border-radius: 4px; margin-right: 6px; vertical-align: middle; }
.low { background: var(--cold); }
.high { background: var(--hot); }
footer {
  display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px;
  border-top: 1px solid var(--border); padding: 14px 20px; background: var(--card);
}
footer button { min-height: 44px; font-size: .85rem; font-weight: 750; border: 1px solid var(--border); border-radius: 8px; padding: 9px 13px; }
.secondary { background: var(--paper); }
.secondary:hover { background: var(--surface); }
.primary { background: var(--cold-deep); border-color: var(--cold-deep); color: #FFFFFF; }
.primary:hover { background: #11489A; }
.progress { min-width: 126px; color: var(--muted); font-size: .69rem; font-weight: 680; }
.progress label { display: block; }
.progress-value { display: flex; align-items: center; gap: 7px; margin-top: 4px; }
.progress-value span { white-space: nowrap; font-variant-numeric: tabular-nums; }
progress { width: 82px; height: 6px; accent-color: var(--green-ink); }
@media (max-width: 650px) {
  header { flex-wrap: wrap; gap: 11px; padding: 17px 15px; }
  .context { display: flex; align-items: baseline; gap: 7px; min-width: 0; padding: 5px 8px; }
  .context strong { margin: 0; }
  .map { height: 400px; }
  .node { width: 29%; min-height: 86px; padding: 7px 6px; }
  .node-top svg { width: 24px; height: 24px; }
  .node strong { overflow-wrap: anywhere; }
  .subtitle { display: none; }
  .reading, .legend { font-size: .63rem; }
  .legend { top: 55%; padding: .37rem .46rem; }
  .legend b { display: none; }
  footer { padding: 10px; gap: 8px; }
  footer button { flex: 1 1 123px; padding: 7px 5px; font-size: .75rem; }
  .progress { order: -1; flex-basis: 100%; display: flex; align-items: center; justify-content: space-between; gap: 5px; padding: 0 3px; }
  .progress-value { margin: 0; }
}
@media (prefers-reduced-motion: reduce) { .node { transition: none; } }
"""

JS = """
export default function ({ parentElement, data, setTriggerValue }) {
    for (const button of parentElement.querySelectorAll("[data-action]")) {
        button.onclick = () => setTriggerValue("action", button.dataset.action);
    }
    const prompts = { compressor: "Voir les pressions", expansion: "Indiquer le contrôle" };
    for (const label of parentElement.querySelectorAll("[data-reading]")) {
        const key = label.dataset.reading;
        const reading = data?.components?.[key];
        label.textContent = reading || prompts[key] || "Saisir les relevés";
        label.closest("button").classList.toggle("has-data", Boolean(reading));
    }
    parentElement.querySelector("[data-context]").textContent = data.context;
    parentElement.querySelector("progress").value = data.measureCount;
    parentElement.querySelector("[data-count]").textContent = data.measureCount + " / 8";
}
"""


def render_circuit(summary, *, context, measure_count):
    render = st.components.v2.component("frigolab_circuit", html=HTML, css=CSS, js=JS)
    data = {"components": summary, "context": context, "measureCount": measure_count}
    return render(data=data, key="circuit", on_action_change=lambda: None).action
