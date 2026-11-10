import json
from dataclasses import replace
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from CoolProp.CoolProp import PropsSI
from streamlit.components.v2.bidi_component.main import _make_trigger_id
from streamlit.proto.WidgetStates_pb2 import WidgetStates
from streamlit.testing.v1 import AppTest

from diagnostic_rules import (
    Readings, REFRIGERANTS, StaticTestError, absolute_bar, calculate, diagnose,
    saturation_temperature,
)
# Relevés fictifs réservés aux tests du moteur.
LOW_BP = Readings(evap_sat=1, cond_sat=40, evap_out=15, liquid_out=33,
                  evap_air_in=25, cond_air_in=28, filter_in=33, filter_out=33)
EVAP_FAULT = Readings(evap_sat=1, cond_sat=41, evap_out=5, liquid_out=37,
                     evap_air_in=26, evap_air_out=23, cond_air_in=30)
HIGH_HP = Readings(evap_sat=12, cond_sat=54, evap_out=22, liquid_out=52,
                  evap_air_in=26, cond_air_in=30, cond_air_out=33)

SCENARIOS = {
    "Cas 01 · Circuit A": ("cond_fouling", HIGH_HP),
    "Cas 02 · Circuit B": (
        "undercharge", replace(LOW_BP, evap_sat=-2, evap_out=16, liquid_out=38,
                               cond_air_in=29, filter_in=None, filter_out=None),
    ),
    "Cas 03 · Circuit C": (
        "compression", Readings(evap_sat=15, cond_sat=37, evap_out=22, liquid_out=32,
                                evap_air_in=27, cond_air_in=30),
    ),
    "Cas 04 · Circuit D": (
        "noncondensables", replace(HIGH_HP, cond_sat=55, liquid_out=43,
                                   cond_air_out=None, static_temperature=30, static_pressure_bar=9.1),
    ),
    "Cas 05 · Circuit E": ("metering", LOW_BP),
    "Cas 06 · Circuit F": ("evap_airflow", replace(EVAP_FAULT, evap_air_in=25, evap_air_out=13)),
    "Cas 07 · Circuit G": (
        "liquid_restriction", replace(LOW_BP, evap_sat=-1, cond_sat=42, evap_out=16,
                                     evap_air_in=26, cond_air_in=30, liquid_out=35,
                                     filter_in=35, filter_out=25),
    ),
    "Cas 08 · Circuit H": (
        "overcharge", replace(HIGH_HP, evap_out=16, liquid_out=43, cond_air_out=38,
                              static_temperature=30, static_pressure_bar=7.7),
    ),
    "Cas 09 · Circuit I": ("evap_fouling", EVAP_FAULT),
    "Cas 10 · Circuit J": ("cond_airflow", replace(HIGH_HP, cond_air_out=43)),
}


class DiagnosticRulesTests(TestCase):
    def run_case(self, name, *, stable=True, liquid_line_checked=True, **changes):
        readings = replace(SCENARIOS[name][1], **changes)
        indicators = calculate(readings, "R134a", equilibrium_confirmed=True)
        return diagnose(indicators, stable=stable, poor_cooling=True, liquid_line_checked=liquid_line_checked)

    def test_all_training_cases(self):
        for name, (expected, _) in SCENARIOS.items():
            with self.subTest(name=name):
                result = self.run_case(name)
                self.assertEqual(result.status, "Hypothèse principale")
                self.assertEqual(result.candidates, (expected,))

    def test_missing_subcooling_retains_three_causes(self):
        result = self.run_case("Cas 05 · Circuit E", liquid_out=None)
        self.assertEqual(set(result.candidates), {"undercharge", "liquid_restriction", "metering"})
        self.assertIn("condenseur", result.next_check)

    def test_missing_filter_measurement_retains_two_causes(self):
        result = self.run_case("Cas 05 · Circuit E", filter_out=None)
        self.assertEqual(set(result.candidates), {"liquid_restriction", "metering"})

    def test_stable_filter_alone_does_not_clear_the_liquid_line(self):
        result = self.run_case("Cas 05 · Circuit E", liquid_line_checked=False)
        self.assertEqual(set(result.candidates), {"liquid_restriction", "metering"})
        self.assertIn("ligne", result.next_check)

    def test_missing_static_test_retains_two_causes(self):
        result = self.run_case("Cas 08 · Circuit H", static_pressure_bar=None)
        self.assertEqual(set(result.candidates), {"overcharge", "noncondensables"})

    def test_unconfirmed_static_test_does_not_count(self):
        readings = SCENARIOS["Cas 08 · Circuit H"][1]
        self.assertNotIn("static", calculate(readings, equilibrium_confirmed=False))

    def test_reverse_air_gradient_does_not_become_fouling(self):
        result = self.run_case("Cas 01 · Circuit A", cond_air_out=27)
        self.assertEqual(result.status, "Mesure discriminante requise")
        self.assertIn("sens", result.next_check)

    def test_transient_mode_blocks_fault_assignment(self):
        result = self.run_case("Cas 08 · Circuit H", stable=False)
        self.assertEqual(result.status, "Conditions à vérifier")
        self.assertFalse(result.candidates)

    def test_conflicting_pressure_signatures(self):
        result = self.run_case("Cas 01 · Circuit A", evap_sat=1)
        self.assertEqual(result.status, "Signature mixte")

    def test_pressure_conversion(self):
        self.assertAlmostEqual(absolute_bar(2.5, "gauge", 1.0), 3.5)
        self.assertAlmostEqual(absolute_bar(3.5, "absolute"), 3.5)
        with self.assertRaises(ValueError):
            absolute_bar(-1.2, "gauge", 1.0)

    def test_saturation_inversion_for_all_available_fluids(self):
        for fluid in REFRIGERANTS:
            for quality in (0, 1):
                with self.subTest(fluid=fluid, quality=quality):
                    pressure_bar = PropsSI("P", "T", 303.15, "Q", quality, fluid) / 100_000
                    self.assertAlmostEqual(saturation_temperature(fluid, pressure_bar, quality), 30.0, places=5)

    def test_static_test_declines_blends(self):
        with self.assertRaises(StaticTestError):
            calculate(SCENARIOS["Cas 08 · Circuit H"][1], "R404A", equilibrium_confirmed=True)


class ApplicationTests(TestCase):
    def make_app(self):
        return AppTest.from_file(str(Path(__file__).with_name("app.py"))).run(timeout=20)

    def test_home_has_no_visible_measurement_form_or_example_picker(self):
        app = self.make_app()
        self.assertFalse(app.exception)
        self.assertFalse(app.selectbox)
        self.assertFalse(app.number_input)
        self.assertEqual(len(app.get("bidi_component")), 1)
        data = json.loads(app.get("bidi_component")[0].proto.json)
        self.assertEqual(data["measureCount"], 0)
        self.assertEqual(data["context"], "R134a · Paliers en °C")

    def action(self, app, name, *, submit=False):
        # AppTest does not dispatch custom component clicks. Send the same
        # widget event that the browser sends to the Streamlit runtime.
        states = app._tree.get_widget_states() if submit else WidgetStates()
        component_id = app.get("bidi_component")[0].proto.id
        states.widgets.add(
            id=_make_trigger_id(component_id, "events"),
            json_trigger_value=json.dumps([{"event": "action", "value": name}]),
        )
        app._run(states)
        self.assertFalse(app.exception)

    def set_conditions(self, app, *, pressures=False):
        self.action(app, "settings")
        for checkbox in app.checkbox:
            if checkbox.label in {"Régime froid stabilisé", "Production de froid insuffisante"}:
                checkbox.check()
        if pressures:
            app.radio[0].set_value("Pressions en bar")
            app.radio[1].set_value("Manométrique")
        app.button[0].click()
        self.action(app, "settings", submit=True)

    def enter_readings(self, app, component, values):
        self.action(app, component)
        for key, value in values.items():
            app.number_input(key=f"field_{key}").set_value(value)
        app.button[0].click()
        self.action(app, component, submit=True)

    def test_component_readings_persist_and_feed_diagnosis(self):
        app = self.make_app()
        self.set_conditions(app)
        self.enter_readings(app, "evaporator", {"evap_sat": -2.0, "evap_out": 16.0, "evap_air_in": 25.0})
        self.enter_readings(app, "condenser", {"cond_sat": 40.0, "liquid_out": 38.0, "cond_air_in": 29.0})
        self.action(app, "evaporator")
        self.assertEqual(app.number_input(key="field_evap_out").value, 16.0)
        data = json.loads(app.get("bidi_component")[0].proto.json)
        self.assertEqual(data["measureCount"], 6)
        self.assertEqual(data["components"]["evaporator"], "T₀ -2,00 °C")
        self.action(app, "diagnosis")
        self.assertIn("Manque de charge", app.success[0].value)

    def test_calculations_and_prerequisites_render_without_dataframe(self):
        app = self.make_app()
        self.enter_readings(app, "evaporator", {"evap_sat": -1.0, "evap_out": 16.0, "evap_air_in": 26.0})
        self.enter_readings(app, "condenser", {"cond_sat": 42.0, "liquid_out": 35.0, "cond_air_in": 30.0})
        self.enter_readings(app, "filter", {"filter_in": 35.0, "filter_out": 25.0})

        with patch("streamlit.dataframe", side_effect=AttributeError("pandas unavailable")):
            self.action(app, "diagnosis")
            self.assertEqual(app.info[0].value, "Conditions à vérifier")
            self.assertTrue(any(
                "**Régime froid stabilisé** et **Production de froid insuffisante**" in item.value
                for item in app.markdown
            ))
            self.set_conditions(app)
            self.action(app, "diagnosis")
            self.assertIn("Pré-détente au déshydrateur", app.success[0].value)
            table = next(item.value for item in app.markdown if item.value.startswith("| Indicateur |"))
            self.assertIn("| Surchauffe | 17.00 K |", table)
            self.assertIn("| Sous-refroidissement | 7.00 K |", table)
            self.assertIn("| Chute au déshydrateur | 10.00 K |", table)

    def test_manual_gauge_pressures_from_the_circuit(self):
        app = self.make_app()
        self.set_conditions(app, pressures=True)
        bp = PropsSI("P", "T", 271.15, "Q", 1, "R134a") / 100_000 - 1.01325
        hp = PropsSI("P", "T", 313.15, "Q", 0, "R134a") / 100_000 - 1.01325
        self.enter_readings(app, "evaporator", {"bp_bar": bp, "evap_out": 16.0, "evap_air_in": 25.0})
        self.enter_readings(app, "condenser", {"hp_bar": hp, "liquid_out": 38.0, "cond_air_in": 29.0})
        self.action(app, "diagnosis")
        self.assertIn("Manque de charge", app.success[0].value)

