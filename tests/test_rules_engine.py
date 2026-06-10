"""
Tests du moteur de règles agronomiques (cœur déterministe et explicable).

C'est la logique centrale du prototype (le ML n'est qu'un complément calibré
dessus). On valide : score élevé pour une mesure idéale, score bas pour une
mesure aberrante, et l'alerte de salinité au bon seuil.
"""

from __future__ import annotations

import unittest

from ml_model.rules.crop_catalog import CROP_CATALOG
from ml_model.rules.engine import (
    Measurement, salinity_alert, score_crop, top_k,
)


def _center(crop: str) -> Measurement:
    """Mesure pile au centre des plages d'une culture."""
    c = CROP_CATALOG[crop]
    return Measurement(
        ph=sum(c.ph) / 2,
        humidity=sum(c.humidity) / 2,
        temperature=sum(c.temperature) / 2,
        ec=sum(c.ec) / 2,
    )


class RulesEngineTest(unittest.TestCase):
    def test_perfect_match_scores_high_and_is_top1(self) -> None:
        m = _center("Tomate")
        score = score_crop(m, CROP_CATALOG["Tomate"]).score
        self.assertGreaterEqual(score, 90, f"score Tomate au centre = {score}")
        # La culture idéale doit figurer dans le top-3.
        self.assertIn("Tomate", [s.crop for s in top_k(m, k=3)])

    def test_aberrant_measure_scores_low_for_crop(self) -> None:
        # Sol totalement hors des plages de la Tomate (acide, sec, froid, salé).
        m = Measurement(ph=8.6, humidity=25, temperature=6, ec=6.0)
        score = score_crop(m, CROP_CATALOG["Tomate"]).score
        self.assertLess(score, 50, f"score Tomate sur sol aberrant = {score}")

    def test_salinity_alert_threshold(self) -> None:
        self.assertFalse(salinity_alert(Measurement(ph=6.5, humidity=60, temperature=22, ec=2.4)))
        self.assertFalse(salinity_alert(Measurement(ph=6.5, humidity=60, temperature=22, ec=2.5)))
        self.assertTrue(salinity_alert(Measurement(ph=6.5, humidity=60, temperature=22, ec=2.6)))

    def test_scores_are_bounded_0_100(self) -> None:
        m = _center("Blé")
        for s in top_k(m, k=10):
            self.assertGreaterEqual(s.score, 0)
            self.assertLessEqual(s.score, 100)


if __name__ == "__main__":
    unittest.main()
