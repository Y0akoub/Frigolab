"""Règles pédagogiques pour un circuit de climatisation air-air stabilisé."""

from dataclasses import dataclass, fields
from math import isfinite

RULE_VERSION = "air-air-1.0"
REFRIGERANTS = ("R134a", "R22", "R32", "R410A", "R404A")
ATMOSPHERE_BAR = 1.01325
EVAP_APPROACH = (16, 20)
COND_APPROACH = (10, 20)
SUPERHEAT_RANGE = (5, 8)
SUBCOOLING_RANGE = (4, 7)
AIR_SPLIT_RANGE = (5, 10)
LINE_TOLERANCE = 2.0
STATIC_TOLERANCE = 0.3


@dataclass(frozen=True)
class Readings:
    evap_sat: float | None = None
    cond_sat: float | None = None
    evap_out: float | None = None
    liquid_out: float | None = None
    evap_air_in: float | None = None
    evap_air_out: float | None = None
    cond_air_in: float | None = None
    cond_air_out: float | None = None
    filter_in: float | None = None
    filter_out: float | None = None
    static_temperature: float | None = None
    static_pressure_bar: float | None = None


READING_LABELS = {
    "evap_sat": "Palier d’évaporation T₀",
    "cond_sat": "Palier de condensation Tₖ",
    "evap_out": "Frigorigène en sortie d’évaporateur",
    "liquid_out": "Liquide en sortie de condenseur",
    "evap_air_in": "Air à l’entrée de l’évaporateur",
    "evap_air_out": "Air à la sortie de l’évaporateur",
    "cond_air_in": "Air à l’entrée du condenseur",
    "cond_air_out": "Air à la sortie du condenseur",
    "filter_in": "Ligne liquide avant le déshydrateur",
    "filter_out": "Ligne liquide après le déshydrateur",
    "static_temperature": "Température du frigorigène à l’équilibre",
    "static_pressure_bar": "Pression à l’équilibre (bar absolus)",
}

FAULTS = {
    "undercharge": "Manque de charge",
    "liquid_restriction": "Pré-détente au déshydrateur",
    "metering": "Détendeur trop restrictif",
    "evap_airflow": "Débit d’air insuffisant à l’évaporateur",
    "evap_fouling": "Évaporateur encrassé",
    "compression": "Capacité utile du compresseur insuffisante",
    "cond_airflow": "Débit d’air insuffisant au condenseur",
    "cond_fouling": "Condenseur encrassé",
    "overcharge": "Excès de charge",
    "noncondensables": "Présence d’incondensables",
}

ACTIONS = {
    "undercharge": "Vérifier la charge de référence et rechercher des indices de fuite.",
    "liquid_restriction": "Vérifier la perte de pression aux bornes du déshydrateur.",
    "metering": "Vérifier la ligne liquide puis la capacité ou le réglage du détendeur.",
    "evap_airflow": "Contrôler le débit réel, le ventilateur et le filtre à air.",
    "evap_fouling": "Inspecter les ailettes et vérifier le débit d’air.",
    "compression": "Contrôler la commande, la vitesse et la capacité réelle du compresseur.",
    "cond_airflow": "Vérifier le ventilateur, le débit et les obstacles au passage d’air.",
    "cond_fouling": "Inspecter les ailettes et vérifier le débit d’air.",
    "overcharge": "Vérifier la charge enregistrée par rapport à la spécification constructeur.",
    "noncondensables": "Vérifier le fluide déclaré et les conditions du test à l’équilibre.",
}


@dataclass(frozen=True)
class Indicator:
    value: float
    unit: str
    formula: str
    status: str = ""


@dataclass(frozen=True)
class Diagnosis:
    status: str
    explanation: str
    candidates: tuple[str, ...] = ()
    next_check: str = ""


def absolute_bar(pressure, reference, atmosphere_bar=ATMOSPHERE_BAR):
    if reference not in ("absolute", "gauge"):
        raise ValueError("Préciser si la pression est absolue ou manométrique.")
    if not isfinite(atmosphere_bar) or atmosphere_bar <= 0:
        raise ValueError("La pression atmosphérique doit être strictement positive.")
    absolute = pressure + atmosphere_bar if reference == "gauge" else pressure
    if not isfinite(absolute) or absolute <= 0:
        raise ValueError("La pression absolue doit être strictement positive.")
    return absolute


def saturation_temperature(fluid, pressure_bar_abs, quality):
    from CoolProp.CoolProp import PropsSI

    pressure_pa = absolute_bar(pressure_bar_abs, "absolute") * 100_000
    try:
        return PropsSI("T", "P", pressure_pa, "Q", quality, fluid) - 273.15
    except ValueError as error:
        raise ValueError(f"Pression hors du domaine de saturation de {fluid}.") from error


class StaticTestError(ValueError):
    """Test pression-température non exploitable."""


def static_saturation_bar(fluid, temperature):
    from CoolProp.CoolProp import PropsSI, get_fluid_param_string

    if get_fluid_param_string(fluid, "pure").lower() != "true":
        raise StaticTestError("Le test à l’équilibre de ce prototype est réservé aux fluides purs.")
    try:
        return PropsSI("P", "T", temperature + 273.15, "Q", 0, fluid) / 100_000
    except ValueError as error:
        raise StaticTestError(f"Température hors du domaine de saturation de {fluid}.") from error


def band(value, limits):
    lower, upper = limits
    value = round(value, 6)
    if value < lower:
        return "faible"
    if value > upper:
        return "élevé"
    return "normal"


def calculate(readings, fluid="R134a", equilibrium_confirmed=False):
    """Retourne les indicateurs disponibles, avec les points utilisés."""
    for field in fields(readings):
        value = getattr(readings, field.name)
        if value is not None and not isfinite(value):
            raise ValueError(f"Valeur invalide pour {READING_LABELS[field.name]}.")
    results = {}
    for key, first, second, limits, formula in (
        ("evap_approach", "evap_air_in", "evap_sat", EVAP_APPROACH, "Air entrée évaporateur − T₀"),
        ("cond_approach", "cond_sat", "cond_air_in", COND_APPROACH, "Tₖ − air entrée condenseur"),
        ("superheat", "evap_out", "evap_sat", SUPERHEAT_RANGE, "Sortie frigorigène évaporateur − T₀ (rosée)"),
        ("subcooling", "cond_sat", "liquid_out", SUBCOOLING_RANGE, "Tₖ (bulle) − liquide sortie condenseur"),
        ("evap_air", "evap_air_in", "evap_air_out", AIR_SPLIT_RANGE, "Air entrée − air sortie évaporateur"),
        ("cond_air", "cond_air_out", "cond_air_in", AIR_SPLIT_RANGE, "Air sortie − air entrée condenseur"),
        ("filter_drop", "filter_in", "filter_out", None, "Ligne liquide amont − aval déshydrateur"),
    ):
        a, b = getattr(readings, first), getattr(readings, second)
        if a is not None and b is not None:
            value = a - b
            results[key] = Indicator(value, "K", formula, band(value, limits) if limits else "")
    if equilibrium_confirmed and readings.static_temperature is not None and readings.static_pressure_bar is not None:
        expected = static_saturation_bar(fluid, readings.static_temperature)
        measured = absolute_bar(readings.static_pressure_bar, "absolute")
        difference = measured - expected
        state = {"élevé": "positif", "normal": "négatif", "faible": "incohérent"}
        results["static"] = Indicator(
            difference, "bar", f"Pression mesurée − pression de saturation ({expected:.2f} bar abs.)",
            state[band(difference, (-STATIC_TOLERANCE, STATIC_TOLERANCE))],
        )
    return results


def likely(fault, explanation):
    return Diagnosis("Hypothèse principale", explanation, (fault,), ACTIONS[fault])


def pending(explanation, candidates, next_check):
    return Diagnosis("Mesure discriminante requise", explanation, candidates, next_check)


def exchanger(indicators, side, explanation):
    split = indicators.get(f"{side}_air")
    candidates = (f"{side}_airflow", f"{side}_fouling")
    name = "l’évaporateur" if side == "evap" else "le condenseur"
    if split is None or split.status == "normal":
        return pending(explanation, candidates, f"Contrôler le débit réel et l’état de {name}. Relever les deux températures d’air si elles manquent.")
    if split.value < 0:
        return pending(explanation, candidates, f"Vérifier le sens des points de mesure sur {name}.")
    if split.status == "élevé":
        return likely(candidates[0], f"{explanation} L’écart sur l’air est de {split.value:.1f} K, supérieur à 10 K. Le faible débit devient l’hypothèse principale.")
    return likely(candidates[1], f"{explanation} L’écart sur l’air est de {split.value:.1f} K, inférieur à 5 K. La batterie échange peu de chaleur avec l’air.")


def diagnose(indicators, *, stable, poor_cooling, liquid_line_checked=False):
    if not stable or not poor_cooling:
        return Diagnosis("Conditions à vérifier", "Les règles s’appliquent en mode froid stabilisé, lorsque la puissance frigorifique est insuffisante.")
    evap = indicators.get("evap_approach")
    cond = indicators.get("cond_approach")
    sc = indicators.get("superheat")
    sr = indicators.get("subcooling")
    if evap is None or cond is None:
        return pending("Les références BP et HP dépendent des températures d’air à l’entrée des deux échangeurs.", (),
                       "Mesurer les deux paliers ou pressions et les températures d’air à l’entrée des échangeurs.")
    if min(evap.value, cond.value) <= 0:
        return Diagnosis("Relevés à vérifier", "Un écart total air–frigorigène est nul ou de signe opposé au mode froid.",
                         next_check="Vérifier les points de mesure et le mode de fonctionnement.")
    bp_low, bp_high = evap.status == "élevé", evap.status == "faible"
    hp_high = cond.status == "élevé"
    if bp_low and hp_high:
        return Diagnosis("Signature mixte", "La BP basse et la HP haute activent des branches concurrentes de cette grille pédagogique.",
                         next_check="Reprendre les relevés synchronisés et vérifier les conditions des deux échangeurs.")
    if bp_high and not hp_high:
        return likely("compression", "BP haute avec HP normale ou basse et production de froid insuffisante. Le débit utile du compresseur peut être trop faible.")
    if bp_low:
        if sc is None or sc.value < 0:
            return pending("La BP est basse. La surchauffe départage le défaut d’alimentation en liquide du défaut d’échange côté air.", (),
                           "Vérifier la température frigorigène en sortie d’évaporateur et la BP au point correspondant.")
        if sc.status != "élevé":
            return exchanger(indicators, "evap", "La BP basse et la surchauffe faible à normale orientent vers un évaporateur recevant trop peu de chaleur.")
        candidates = ("undercharge", "liquid_restriction", "metering")
        if sr is None or sr.value < 0:
            return pending("La BP basse et la surchauffe élevée indiquent un évaporateur sous-alimenté.", candidates,
                           "Mesurer le liquide en sortie du condenseur, en amont du déshydrateur, pour établir le sous-refroidissement.")
        if sr.status == "faible":
            return likely("undercharge", "BP basse, surchauffe élevée et sous-refroidissement faible. Le manque de liquide se manifeste des deux côtés.")
        drop = indicators.get("filter_drop")
        if drop is None or drop.value < -LINE_TOLERANCE:
            return pending("La surchauffe est élevée et le sous-refroidissement est conservé.", candidates[1:],
                           "Vérifier la température de la ligne liquide avant et après le déshydrateur et le long du trajet vers le détendeur.")
        if drop.value > LINE_TOLERANCE:
            return likely("liquid_restriction", f"Le SR est conservé en amont. La ligne refroidit de {drop.value:.1f} K au passage du déshydrateur, ce qui localise la pré-détente probable.")
        if not liquid_line_checked:
            return pending("Aucune chute significative n’est mesurée au déshydrateur. Une restriction reste possible ailleurs sur la ligne liquide.",
                           candidates[1:], "Vérifier la température le long de la ligne jusqu’à l’entrée du détendeur.")
        return likely("metering", "La surchauffe est élevée, le SR est conservé et aucun refroidissement local n’est signalé sur la ligne liquide. L’alimentation au détendeur est à vérifier.")
    if hp_high:
        static = indicators.get("static")
        if static and static.status == "positif":
            return likely("noncondensables", f"À l’équilibre, la pression mesurée dépasse la saturation de {static.value:.2f} bar. La HP peut surestimer la température de condensation et le SR apparent.")
        if static and static.status == "incohérent":
            return pending("La pression à l’équilibre est inférieure à la valeur attendue pour le fluide déclaré.", (),
                           "Vérifier le fluide, la coexistence liquide-vapeur et les mesures à l’arrêt.")
        candidates = ("cond_airflow", "cond_fouling", "overcharge", "noncondensables")
        if sr is None or sr.value < 0:
            return pending("La HP est haute. Le sous-refroidissement n’est pas exploitable.", candidates,
                           "Vérifier la température du liquide en sortie du condenseur et la HP au point correspondant.")
        if sr.status == "faible":
            return exchanger(indicators, "cond", "La HP haute et le sous-refroidissement faible orientent vers un rejet de chaleur insuffisant au condenseur.")
        if sr.status == "normal":
            return pending("La HP haute et le SR dans la plage normale laissent plusieurs causes ouvertes.",
                           candidates[:-1] if static else candidates,
                           "Contrôler l’air au condenseur et réaliser le test pression-température à l’équilibre s’il manque.")
        if static:
            return likely("overcharge", "La HP et le SR sont élevés. La pression à l’équilibre correspond à la pression de saturation dans la tolérance du profil.")
        return pending("La HP et le sous-refroidissement apparent sont élevés.", candidates[2:],
                       "Comparer la pression absolue à la saturation à l’arrêt, à l’équilibre et en présence de liquide et de vapeur.")
    return Diagnosis("Signature non reconnue", "Les indicateurs disponibles ne correspondent pas à une branche du profil avec production de froid insuffisante.",
                     next_check="Vérifier le profil de référence, les mesures et les conditions d’exploitation.")
