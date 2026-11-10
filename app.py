from dataclasses import fields

import streamlit as st

from circuit import render_circuit
from diagnostic_rules import (
    ATMOSPHERE_BAR, FAULTS, READING_LABELS, REFRIGERANTS, RULE_VERSION,
    Readings, StaticTestError, absolute_bar, calculate, diagnose, saturation_temperature,
)

st.set_page_config(page_title="FrigoLab · Circuit frigorifique", page_icon="❄", layout="wide")
st.html("""
<style>
[data-testid="stMainBlockContainer"] { max-width: 1110px; padding-top: 2.6rem; }
@media (max-width: 650px) {
    [data-testid="stMainBlockContainer"] { padding-top: 2.25rem; padding-left: .7rem; padding-right: .7rem; }
}
</style>
""")

DEFAULT_SETTINGS = {
    "fluid": "R134a", "mode": "Paliers en °C", "basis": "Absolue",
    "atmosphere": ATMOSPHERE_BAR, "stable": False, "poor_cooling": False,
    "equilibrium": False,
}

INDICATOR_LABELS = {
    "evap_approach": "Écart total évaporateur",
    "cond_approach": "Écart total condenseur",
    "superheat": "Surchauffe",
    "subcooling": "Sous-refroidissement",
    "evap_air": "Écart sur l’air évaporateur",
    "cond_air": "Écart sur l’air condenseur",
    "filter_drop": "Chute au déshydrateur",
    "static": "Écart de pression à l’équilibre",
}

st.session_state.setdefault("readings", {})
st.session_state.setdefault("settings", DEFAULT_SETTINGS.copy())


def read_number(name):
    label, unit = {
        "bp_bar": ("BP au point d’évaporation", "bar"),
        "hp_bar": ("HP au point de condensation", "bar"),
        "static_pressure_bar": ("Pression à l’équilibre", "bar abs."),
    }.get(name, (READING_LABELS.get(name, name), "°C"))
    return st.number_input(
        f"{label} ({unit})", key=f"field_{name}", value=st.session_state.readings.get(name),
        placeholder="Non renseigné", format="%.2f" if unit == "°C" else "%.3f",
        step=0.5 if unit == "°C" else 0.1,
        min_value=0.01 if name == "static_pressure_bar" else None,
    )


def uses_pressures():
    return st.session_state.settings["mode"] == "Pressions en bar"


def cycle_fields():
    if uses_pressures():
        return "bp_bar", "hp_bar", "BP", "HP", "bar"
    return "evap_sat", "cond_sat", "T₀", "Tₖ", "°C"


def component_summary():
    current = st.session_state.readings
    bp, hp, bp_label, hp_label, unit = cycle_fields()
    return {
        "evaporator": reading_summary(bp, bp_label, unit)
        or measure_count(*measurement_groups()["evaporator"]),
        "condenser": reading_summary(hp, hp_label, unit)
        or measure_count(*measurement_groups()["condenser"]),
        "filter": measure_count("filter_in", "filter_out"),
        "expansion": "Ligne contrôlée" if current.get("liquid_line_checked") else "",
        "compressor": "BP et HP saisies" if current.get(bp) is not None and current.get(hp) is not None else "",
    }


def reading_summary(key, label, unit):
    value = st.session_state.readings.get(key)
    return "" if value is None else f"{label} {value:.2f} {unit}".replace(".", ",")


def measure_count(*keys):
    count = sum(st.session_state.readings.get(key) is not None for key in keys)
    return f"{count} / {len(keys)} relevés" if count else ""


def measurement_groups():
    bp, hp, *_ = cycle_fields()
    return {
        "evaporator": (bp, "evap_out", "evap_air_in", "evap_air_out"),
        "condenser": (hp, "liquid_out", "cond_air_in", "cond_air_out"),
        "filter": ("filter_in", "filter_out"),
        "expansion": (),
    }


def edit_component(component):
    names = measurement_groups()[component]
    if component == "expansion":
        st.write("Le contrôle de la ligne liquide aide à distinguer une pré-détente d’un détendeur trop restrictif.")
    else:
        st.caption("Laisse un champ vide si la mesure manque.")
    with st.form(f"readings_{component}"):
        if component in ("evaporator", "condenser"):
            st.markdown("**Frigorigène**")
            updates = {key: read_number(key) for key in names[:2]}
            st.markdown("**Air à travers la batterie**")
            updates.update({key: read_number(key) for key in names[2:]})
        else:
            updates = {key: read_number(key) for key in names}
        if component == "expansion":
            updates["liquid_line_checked"] = st.checkbox(
                "Ligne liquide contrôlée jusqu’au détendeur, sans chute locale",
                value=st.session_state.readings.get("liquid_line_checked", False),
            )
        if st.form_submit_button("Enregistrer les relevés", type="primary"):
            st.session_state.readings.update(updates)
            st.rerun()


def show_compressor():
    bp, hp, bp_label, hp_label, unit = cycle_fields()
    st.write("Le diagnostic du compresseur compare la basse pression à la haute pression. "
             "Les relevés correspondants se saisissent sur l’évaporateur et le condenseur.")
    left, right = st.columns(2)
    left.metric(bp_label, reading_summary(bp, "", unit).strip() or "Non renseigné")
    right.metric(hp_label, reading_summary(hp, "", unit).strip() or "Non renseigné")


def edit_settings():
    old = st.session_state.settings
    with st.form("settings_form"):
        st.markdown("**Configuration des mesures**")
        modes = ("Paliers en °C", "Pressions en bar")
        bases = ("Absolue", "Manométrique")
        fluid = st.selectbox("Frigorigène", REFRIGERANTS, index=REFRIGERANTS.index(old["fluid"]))
        mode = st.radio("Relevés du frigorigène", modes, index=modes.index(old["mode"]), horizontal=True)
        basis = st.radio("Référence si saisie en bar", bases, index=bases.index(old["basis"]), horizontal=True)
        atmosphere = st.number_input(
            "Pression atmosphérique locale (bar abs.)", min_value=0.01,
            value=old["atmosphere"], format="%.5f", step=0.001,
            help="Utilisée pour convertir les pressions manométriques.",
        )
        st.markdown("**Conditions d’analyse**")
        stable = st.checkbox("Régime froid stabilisé", value=old["stable"])
        poor_cooling = st.checkbox("Production de froid insuffisante", value=old["poor_cooling"])
        with st.expander("Test des incondensables · à l’arrêt"):
            static_temperature = read_number("static_temperature")
            static_pressure = read_number("static_pressure_bar")
            equilibrium = st.checkbox(
                "Équilibre thermique atteint, avec liquide et vapeur présents", value=old["equilibrium"],
            )
        if st.form_submit_button("Enregistrer les paramètres", type="primary"):
            st.session_state.settings = {
                "fluid": fluid, "mode": mode, "basis": basis, "atmosphere": atmosphere,
                "stable": stable, "poor_cooling": poor_cooling, "equilibrium": equilibrium,
            }
            st.session_state.readings.update(
                static_temperature=static_temperature, static_pressure_bar=static_pressure,
            )
            st.rerun()
    if st.button("Effacer les relevés de cette inspection"):
        st.session_state.readings = {}
        st.rerun()


def resolve_readings():
    data = st.session_state.readings
    settings = st.session_state.settings
    values = {field.name: data.get(field.name) for field in fields(Readings)}
    if uses_pressures():
        reference = "gauge" if settings["basis"] == "Manométrique" else "absolute"
        atmosphere = settings["atmosphere"]
        bp, hp = (
            None if data.get(key) is None else absolute_bar(data[key], reference, atmosphere)
            for key in ("bp_bar", "hp_bar")
        )
        if bp is not None and hp is not None and hp <= bp:
            raise ValueError("La HP doit être supérieure à la BP. Vérifie les mesures et leur référence.")
        fluid = settings["fluid"]
        values["evap_sat"] = None if bp is None else saturation_temperature(fluid, bp, quality=1)
        values["cond_sat"] = None if hp is None else saturation_temperature(fluid, hp, quality=0)
    return Readings(**values)


def show_diagnosis():
    settings = st.session_state.settings
    try:
        readings = resolve_readings()
        try:
            indicators = calculate(readings, settings["fluid"], settings["equilibrium"])
        except StaticTestError as error:
            st.warning(str(error))
            indicators = calculate(readings, settings["fluid"])
    except ValueError as error:
        st.error(str(error))
        return

    result = diagnose(
        indicators, stable=settings["stable"], poor_cooling=settings["poor_cooling"],
        liquid_line_checked=st.session_state.readings.get("liquid_line_checked", False),
    )
    if len(result.candidates) == 1:
        st.success(f"{result.status} · {FAULTS[result.candidates[0]]}")
    else:
        st.info(result.status)
    st.write(result.explanation)
    missing_conditions = [
        label for key, label in (
            ("stable", "Régime froid stabilisé"),
            ("poor_cooling", "Production de froid insuffisante"),
        ) if not settings[key]
    ]
    if missing_conditions:
        labels = " et ".join(f"**{label}**" for label in missing_conditions)
        st.markdown(f"Dans **Paramètres du circuit**, coche {labels} si ces conditions sont réunies, puis clique sur **Enregistrer les paramètres**.")
    if len(result.candidates) > 1:
        st.markdown("**Hypothèses à départager**")
        for candidate in result.candidates:
            st.markdown(f"- {FAULTS[candidate]}")
    if result.next_check:
        st.markdown("**Prochain contrôle**")
        st.write(result.next_check)

    if "superheat" in indicators or "subcooling" in indicators:
        low, high = st.columns(2)
        for column, key in ((low, "superheat"), (high, "subcooling")):
            item = indicators.get(key)
            value = "—" if item is None else f"{item.value:.2f} {item.unit}"
            column.metric(INDICATOR_LABELS[key], value)

    with st.expander("Voir les calculs"):
        low, high = st.columns(2)
        for column, title, value in (
            (low, "Palier d’évaporation", readings.evap_sat),
            (high, "Palier de condensation", readings.cond_sat),
        ):
            column.metric(title, "Non renseigné" if value is None else f"{value:.2f} °C")
        pressure_labels = {
            "evap_approach": {"élevé": "BP basse", "faible": "BP haute", "normal": "BP normale"},
            "cond_approach": {"élevé": "HP haute", "faible": "HP basse", "normal": "HP normale"},
        }
        rows = [
            "| Indicateur | Valeur | Interprétation | Calcul |",
            "| --- | --- | --- | --- |",
        ]
        for key, label in INDICATOR_LABELS.items():
            item = indicators.get(key)
            state = item.status if item else "Non renseigné"
            interpretation = pressure_labels.get(key, {}).get(state, state) or "Mesuré"
            value = f"{item.value:.2f} {item.unit}" if item else "—"
            formula = item.formula if item else "—"
            rows.append(f"| {label} | {value} | {interpretation} | {formula} |")
        st.markdown("\n".join(rows))
    st.caption(f"Profil pédagogique de climatisation air-air · Règles {RULE_VERSION}")


groups = measurement_groups()
settings = st.session_state.settings
exchange_readings = groups["evaporator"] + groups["condenser"]
action = render_circuit(
    component_summary(),
    context=f"{settings['fluid']} · {settings['mode']}",
    measure_count=sum(st.session_state.readings.get(key) is not None for key in exchange_readings),
)

dialogs = {
    "compressor": ("Compresseur", show_compressor),
    "condenser": ("Condenseur", lambda: edit_component("condenser")),
    "filter": ("Déshydrateur", lambda: edit_component("filter")),
    "expansion": ("Détendeur", lambda: edit_component("expansion")),
    "evaporator": ("Évaporateur", lambda: edit_component("evaporator")),
    "settings": ("Paramètres du circuit", edit_settings),
    "diagnosis": ("Diagnostic", show_diagnosis),
}
if action in dialogs:
    title, content = dialogs[action]
    st.dialog(title, width="large" if action == "diagnosis" else "small")(content)()
