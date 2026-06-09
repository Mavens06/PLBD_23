from __future__ import annotations

import importlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd


class MLPipelineTest(unittest.TestCase):
    def test_download_without_kaggle_credentials_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            import ml_model.download_datasets as dl
            with mock.patch.object(dl, "METADATA_DIR", Path(td) / "metadata"), \
                 mock.patch.object(dl, "RAW_DIR", Path(td) / "raw"), \
                 mock.patch.object(dl, "REAL_DIR", Path(td) / "real"), \
                 mock.patch.object(dl, "EXTERNAL_DIR", Path(td) / "external"), \
                 mock.patch.object(dl, "SOURCES_PATH", Path(td) / "metadata" / "sources.json"), \
                 mock.patch.object(dl, "CROP_REAL", Path(td) / "real" / "crop_recommendation.csv"), \
                 mock.patch.object(dl, "CROP_RAW", Path(td) / "raw" / "crop_recommendation.csv"), \
                 mock.patch.object(dl, "_has_kaggle_credentials", return_value=False), \
                 mock.patch.object(dl, "PUBLIC_CROP_MIRRORS", []):
                self.assertEqual(dl.main(), 0)
                self.assertTrue((Path(td) / "metadata" / "sources.json").exists())

    def test_audit_detects_missing_full_columns(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bad.csv"
            pd.DataFrame({"temperature": [20], "humidity": [50], "label": ["Tomate"]}).to_csv(path, index=False)
            from ml_model.prepare_dataset import audit_dataset
            report = audit_dataset(path)
            self.assertEqual(report["status"], "audited")
            self.assertIn("temperature", report["detected_variables"])
            self.assertNotIn("N", report["detected_variables"])

    def test_embedded_features_never_include_npk_or_rainfall(self) -> None:
        from ml_model.model_registry import EMBEDDED_FEATURES
        self.assertEqual(EMBEDDED_FEATURES, ["temperature", "humidity", "ph"])
        self.assertTrue({"N", "P", "K", "rainfall"}.isdisjoint(EMBEDDED_FEATURES))

    def test_full_model_is_not_deployable_by_default(self) -> None:
        import ml_model.train as tr
        full = tr._disabled_full_model()
        self.assertFalse(full["trained"])
        self.assertFalse(full["deployable"])
        self.assertIn("not measured", full["reason"])

    def test_predict_returns_top3_or_rules_fallback(self) -> None:
        from ml_model.predict import predict_top_crops
        result = predict_top_crops(ph=6.6, humidity=62, temperature=23, ec=1.1, k=3)
        self.assertIn("top", result)
        self.assertGreaterEqual(len(result["top"]), 3)
        self.assertIn("recommendations", result)
        self.assertIn("score_source", result)

    def test_rules_alert_aberrant_values(self) -> None:
        from ml_model.predict import predict_top_crops
        result = predict_top_crops(ph=4.8, humidity=20, temperature=42, ec=4.0, k=3)
        self.assertGreaterEqual(len(result["alerts"]), 3)

    def test_recommendations_stay_within_crop_perimeter(self) -> None:
        """Garde-fou anti-régression : l'inférence de prod ne doit JAMAIS
        renvoyer une culture hors des 10 cultures cibles (ex. coffee, rice,
        jute du dataset Kaggle tropical). Toute fuite casse la cohérence
        agronomique et la démo."""
        from ml_model.predict import predict_top_crops
        from ml_model.rules.crop_catalog import CROP_CATALOG
        allowed = set(CROP_CATALOG)
        # Plusieurs profils de sol couvrant les 4 variables capteur.
        soils = [
            (6.7, 62, 23, 1.1),
            (5.2, 78, 18, 0.6),
            (7.8, 45, 30, 2.8),
            (6.0, 70, 25, 1.5),
        ]
        for ph, hum, temp, ec in soils:
            result = predict_top_crops(ph=ph, humidity=hum, temperature=temp, ec=ec, k=3)
            crops = {item["crop"] for item in result["top"]}
            self.assertTrue(
                crops <= allowed,
                f"Cultures hors périmètre {crops - allowed} pour le sol "
                f"(pH={ph}, hum={hum}, temp={temp}, EC={ec}). engine={result.get('engine')}",
            )

    def test_production_model_uses_four_sensor_features_incl_ec(self) -> None:
        """Le modèle de production doit consommer les 4 variables capteur,
        EC incluse : changer l'EC doit pouvoir changer la recommandation."""
        from ml_model.predict import predict_top_crops
        low_ec = predict_top_crops(ph=6.5, humidity=65, temperature=22, ec=0.4, k=3)
        high_ec = predict_top_crops(ph=6.5, humidity=65, temperature=22, ec=5.0, k=3)
        # L'EC très élevée doit au minimum déclencher une alerte de salinité.
        self.assertTrue(any("salin" in a.lower() or "EC" in a for a in high_ec["alerts"]))
        self.assertEqual(low_ec.get("model_type"), "production")

    def test_full_training_can_run_on_small_crop_dataset(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            tmp = Path(td)
            csv_path = tmp / "full.csv"
            rows = []
            for crop, base in [("rice", 20), ("maize", 70)]:
                for i in range(20):
                    rows.append({
                        "N": base + i % 3,
                        "P": base / 2 + i % 4,
                        "K": base / 3 + i % 5,
                        "temperature": 20 + i % 5,
                        "humidity": 50 + i % 10,
                        "ph": 6.0 + (i % 3) * 0.1,
                        "rainfall": 100 + i,
                        "label": crop,
                    })
            pd.DataFrame(rows).to_csv(csv_path, index=False)
            import ml_model.train as tr
            result = tr._train_one(
                "full_test",
                csv_path,
                ["N", "P", "K", "temperature", "humidity", "ph", "rainfall"],
                tmp / "model.pkl",
                tmp / "metadata.json",
                min_rows=10,
            )
            self.assertTrue(result["trained"])
            self.assertTrue((tmp / "model.pkl").exists())

    def test_important_files_still_exist(self) -> None:
        root = Path(__file__).resolve().parent.parent
        for rel in [
            "ml_model/rules/crop_catalog.py",
            "ml_model/rules/engine.py",
            "ml_model/rules/correction.py",
            "backend/app.py",
            "ml_model/predict.py",
        ]:
            self.assertTrue((root / rel).exists(), rel)


if __name__ == "__main__":
    unittest.main()
