"""
Tests du diagnostic de correction (`rules/correction.py`).

Question inverse du moteur de scoring : « j'ai choisi CETTE culture, comment
corriger mon sol ? ». On valide qu'un sol acide pour une culture exigeant un pH
plus élevé déclenche bien une recommandation de chaulage, et qu'un sol idéal ne
déclenche aucune action.
"""

from __future__ import annotations

import unittest

from ml_model.rules.crop_catalog import CROP_CATALOG
from ml_model.rules.engine import Measurement
from ml_model.rules.correction import diagnose, diagnosis_to_prompt


def _center(crop: str) -> Measurement:
    c = CROP_CATALOG[crop]
    return Measurement(ph=sum(c.ph) / 2, humidity=sum(c.humidity) / 2,
                       temperature=sum(c.temperature) / 2, ec=sum(c.ec) / 2)


class CorrectionTest(unittest.TestCase):
    def test_acidic_soil_recommends_liming(self) -> None:
        # Olivier exige pH 6.5-8.5 ; un sol à pH 5.0 est trop acide.
        c = CROP_CATALOG["Olivier"]
        m = Measurement(ph=5.0, humidity=sum(c.humidity) / 2,
                        temperature=sum(c.temperature) / 2, ec=sum(c.ec) / 2)
        diag = diagnose(m, "Olivier")

        self.assertEqual(diag["target_crop"], "Olivier")
        self.assertFalse(diag["suitable"])
        ph_diag = next(d for d in diag["diagnostics"] if d["variable"] == "ph")
        self.assertEqual(ph_diag["status"], "low")
        self.assertIsNotNone(ph_diag["action"])
        # L'action de relèvement du pH doit mentionner un amendement calcaire.
        action = ph_diag["action"].lower()
        self.assertTrue("chaux" in action or "dolomie" in action or "chaul" in action,
                        f"action pH inattendue : {ph_diag['action']}")

    def test_optimal_soil_has_no_action(self) -> None:
        diag = diagnose(_center("Tomate"), "Tomate")
        self.assertTrue(diag["suitable"])
        self.assertEqual(diag["actions"], [])
        self.assertTrue(all(d["status"] == "ok" for d in diag["diagnostics"]))

    def test_better_suited_excludes_target_and_lists_crops(self) -> None:
        diag = diagnose(Measurement(ph=5.0, humidity=40, temperature=22, ec=3.0), "Tomate")
        crops = [b["crop"] for b in diag["better_suited"]]
        self.assertNotIn("Tomate", crops)
        self.assertTrue(all(c in CROP_CATALOG for c in crops))

    def test_diagnosis_to_prompt_is_nonempty_str(self) -> None:
        prompt = diagnosis_to_prompt(diagnose(_center("Tomate"), "Tomate"))
        self.assertIsInstance(prompt, str)
        self.assertIn("Tomate", prompt)


if __name__ == "__main__":
    unittest.main()
