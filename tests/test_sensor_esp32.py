"""
test_sensor_esp32.py — Parseur ESP32, générateur pH/EC, capteur de sol réel.

Couvre :
  • parse_line() : extraction (température, humidité) tolérante (é/Temp,
    virgule/point, espaces, cas « Erreur »), sans matériel ;
  • SoilSynthesizer : pH + EC cohérents et CORRÉLÉS à l'humidité + température
    (EC ↑ avec l'humidité et la température ; pH plus acide en sol humide),
    bornés et stables entre deux lectures ;
  • _Esp32SoilSensor : température + humidité de l'ESP32, pH + EC synthétisés.
"""

from __future__ import annotations

import unittest

from raspberry_pi.sensors.esp32_sensor import parse_line
from raspberry_pi.sensors.soil_sensor import SoilSynthesizer, _Esp32SoilSensor


class _FakeEsp32:
    """ESP32 simulé : renvoie les (temp, hum) qu'on lui fixe, sans port série."""
    def __init__(self, temp=None, hum=None):
        self._t, self._h = temp, hum

    def latest(self):
        return self._t, self._h

    def close(self):
        pass


class TestParseLine(unittest.TestCase):
    def test_nominal_frame(self):
        t, h = parse_line("Température : 24.81 °C, Humidité : 53.16 %")
        self.assertAlmostEqual(t, 24.81)
        self.assertAlmostEqual(h, 53.16)

    def test_comma_decimal(self):
        t, h = parse_line("Temperature : 19,5 C, Humidite : 40,0 %")
        self.assertAlmostEqual(t, 19.5)
        self.assertAlmostEqual(h, 40.0)

    def test_negative_temperature(self):
        t, h = parse_line("Température : -3.50 °C, Humidité : 12.00 %")
        self.assertAlmostEqual(t, -3.5)
        self.assertAlmostEqual(h, 12.0)

    def test_sensor_error_temp_is_none(self):
        t, h = parse_line("Température : Erreur, Humidité : 50.00 %")
        self.assertIsNone(t)
        self.assertAlmostEqual(h, 50.0)

    def test_garbage_returns_none_none(self):
        t, h = parse_line("\x00\xff bruit de boot ~~~")
        self.assertIsNone(t)
        self.assertIsNone(h)


class TestSoilSynthesizer(unittest.TestCase):
    def test_values_within_physical_bounds(self):
        s = SoilSynthesizer(seed=1)
        for _ in range(200):
            ph, ec = s.synthesize(humidity=70.0, temperature=25.0)
            self.assertTrue(5.3 <= ph <= 7.9, ph)
            self.assertTrue(0.15 <= ec <= 4.5, ec)

    def test_ec_increases_with_humidity(self):
        # EC moyen plus élevé sur sol humide que sur sol sec (eau = conduction).
        dry = SoilSynthesizer(seed=2)
        wet = SoilSynthesizer(seed=2)
        ec_dry = sum(dry.synthesize(20.0, 25.0)[1] for _ in range(100)) / 100
        ec_wet = sum(wet.synthesize(90.0, 25.0)[1] for _ in range(100)) / 100
        self.assertGreater(ec_wet, ec_dry)

    def test_ec_increases_with_temperature(self):
        cold = SoilSynthesizer(seed=3)
        hot = SoilSynthesizer(seed=3)
        ec_cold = sum(cold.synthesize(60.0, 10.0)[1] for _ in range(100)) / 100
        ec_hot = sum(hot.synthesize(60.0, 40.0)[1] for _ in range(100)) / 100
        self.assertGreater(ec_hot, ec_cold)

    def test_ph_more_acidic_when_wet(self):
        dry = SoilSynthesizer(seed=4)
        wet = SoilSynthesizer(seed=4)
        ph_dry = sum(dry.synthesize(20.0, 22.0)[0] for _ in range(100)) / 100
        ph_wet = sum(wet.synthesize(95.0, 22.0)[0] for _ in range(100)) / 100
        self.assertGreater(ph_dry, ph_wet)

    def test_consecutive_reads_are_close(self):
        # Faible dérive + petit bruit → deux lectures successives proches.
        s = SoilSynthesizer(seed=5)
        ph1, ec1 = s.synthesize(60.0, 24.0)
        ph2, ec2 = s.synthesize(60.0, 24.0)
        self.assertLess(abs(ph1 - ph2), 0.3)
        self.assertLess(abs(ec1 - ec2), 0.3)

    def test_handles_none_inputs(self):
        s = SoilSynthesizer(seed=6)
        ph, ec = s.synthesize(None, None)  # avant la 1ʳᵉ trame ESP32
        self.assertTrue(5.3 <= ph <= 7.9)
        self.assertTrue(0.15 <= ec <= 4.5)


class TestEsp32SoilSensor(unittest.TestCase):
    def test_uses_real_temp_humidity_and_synthesizes_ph_ec(self):
        sensor = _Esp32SoilSensor(_FakeEsp32(temp=18.4, hum=71.2), SoilSynthesizer(seed=7))
        r = sensor.read()
        self.assertAlmostEqual(r.temperature, 18.4)
        self.assertAlmostEqual(r.humidity, 71.2)
        self.assertTrue(5.3 <= r.ph <= 7.9)
        self.assertTrue(0.15 <= r.ec <= 4.5)

    def test_keeps_last_value_when_esp32_empty(self):
        esp = _FakeEsp32(temp=None, hum=None)
        sensor = _Esp32SoilSensor(esp, SoilSynthesizer(seed=8))
        r = sensor.read()
        # Replis prudents (22 °C / 55 %) tant qu'aucune trame n'est arrivée.
        self.assertIsNotNone(r.temperature)
        self.assertIsNotNone(r.humidity)
        self.assertTrue(0.15 <= r.ec <= 4.5)

    def test_set_location_is_noop(self):
        sensor = _Esp32SoilSensor(_FakeEsp32(temp=20.0, hum=60.0), SoilSynthesizer(seed=9))
        sensor.set_location("C1", 1.0, 2.0)   # ne doit pas lever
        self.assertAlmostEqual(sensor.read().temperature, 20.0)


if __name__ == "__main__":
    unittest.main()
