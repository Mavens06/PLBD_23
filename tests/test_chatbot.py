"""
Tests de la couche conversationnelle (chatbot Gemini).

Aucun appel réseau : le client Gemini (`_call_gemini` / `generate_expert_response`
/ `synthesize_speech`) est mocké. On valide :
  • la construction du prompt système (périmètre agronomique, langue, sanitisation) ;
  • les garde-fous d'entrée (message borné, historique borné, rôles) ;
  • le repli automatique de modèle sur quota (429) ;
  • les contrats des routes /api/chat et /api/tts (validation + codes d'erreur).
"""

from __future__ import annotations

import unittest
from unittest import mock

from fastapi.testclient import TestClient

import backend.chatbot_llm as llm
from backend.app import app


class BuildPromptTest(unittest.TestCase):
    def test_prompt_lists_target_crops_and_forbids_npk(self) -> None:
        p = llm._build_system_prompt("fr", None, None, None, None, None)
        for crop in ("Blé", "Tomate", "Olivier", "Vigne", "Pastèque"):
            self.assertIn(crop, p)
        # Interdiction explicite N/P/K dans le prompt.
        self.assertIn("N/P/K", p)
        self.assertIn("azote", p.lower())

    def test_prompt_is_conversational_with_detail_and_redirect(self) -> None:
        p = llm._build_system_prompt("fr", None, None, None, None, None).lower()
        self.assertIn("conversationnel", p)      # comprend n'importe quel message
        self.assertIn("détail", p)               # explications détaillées sur demande
        self.assertIn("réoriente", p)            # réorientation si hors-sujet
        # Mais le sol précis reste ancré sur les données mesurées.
        self.assertIn("n'invente jamais", p)

    def test_prompt_language_label(self) -> None:
        self.assertIn("français", llm._build_system_prompt("fr", None, None, None, None, None))
        self.assertIn("arabe", llm._build_system_prompt("ar", None, None, None, None, None))
        self.assertIn("darija", llm._build_system_prompt("da", None, None, None, None, None))

    def test_sensor_context_keeps_only_allowed_numeric_keys(self) -> None:
        # N/P/K et valeurs non numériques doivent être ignorés.
        ctx = llm._build_sensor_context(
            {"pH": 6.5, "humidity": 60, "N": 30, "K": 12, "temperature": "x"}
        )
        self.assertIn("6.5", ctx)
        self.assertNotIn("30", ctx)        # N filtré
        self.assertNotIn("\"N\"", ctx)
        self.assertNotIn("12", ctx)        # K filtré

    def test_prompt_injects_sensor_and_correction(self) -> None:
        p = llm._build_system_prompt(
            "fr",
            {"pH": 5.4, "humidity": 70, "temperature": 22, "salinity": 1.1},
            ml_prediction="Tomate",
            selected_zone="B2",
            selected_crop="Tomate",
            robot_state={"active_point": "B2", "measured_points": 3, "total_points": 9},
            correction_context="DIAGNOSTIC: pH trop bas, ajouter de la chaux.",
        )
        self.assertIn("5.4", p)
        self.assertIn("Tomate", p)
        self.assertIn("B2", p)
        self.assertIn("3/9", p)
        self.assertIn("chaux", p)


class GenerateResponseTest(unittest.IsolatedAsyncioTestCase):
    async def test_missing_api_key_raises(self) -> None:
        with mock.patch.object(llm, "GEMINI_API_KEY", ""):
            with self.assertRaises(RuntimeError):
                await llm.generate_expert_response("bonjour", "fr")

    async def test_empty_message_raises(self) -> None:
        with mock.patch.object(llm, "GEMINI_API_KEY", "k"):
            with self.assertRaises(RuntimeError):
                await llm.generate_expert_response("   ", "fr")

    async def test_message_and_history_are_bounded_and_roles_mapped(self) -> None:
        captured = {}

        async def fake_call(client, model, payload):
            captured["payload"] = payload
            return "OK"

        long_msg = "x" * 5000
        history = [{"role": "bot" if i % 2 else "user", "content": f"t{i}"} for i in range(20)]
        with mock.patch.object(llm, "GEMINI_API_KEY", "k"), \
             mock.patch.object(llm, "_call_gemini", fake_call):
            out = await llm.generate_expert_response(long_msg, "fr", history=history)

        self.assertEqual(out, "OK")
        contents = captured["payload"]["contents"]
        # Dernier message = la question, tronquée à la borne.
        last = contents[-1]
        self.assertEqual(last["role"], "user")
        self.assertEqual(len(last["parts"][0]["text"]), llm._MAX_MESSAGE_CHARS)
        # Historique borné : au plus _MAX_HISTORY_TURNS tours + le message courant.
        self.assertLessEqual(len(contents), llm._MAX_HISTORY_TURNS + 1)
        # Rôle "bot" → "model" pour Gemini ; jamais de rôle brut "bot".
        roles = {c["role"] for c in contents}
        self.assertTrue(roles <= {"user", "model"})

    async def test_quota_triggers_fallback_model(self) -> None:
        calls = []

        async def fake_call(client, model, payload):
            calls.append(model)
            if model == llm.GEMINI_MODEL:
                raise llm._QuotaError("429 quota")
            return "fallback-ok"

        with mock.patch.object(llm, "GEMINI_API_KEY", "k"), \
             mock.patch.object(llm, "GEMINI_FALLBACK_MODEL", "gemini-2.5-flash-lite"), \
             mock.patch.object(llm, "_call_gemini", fake_call):
            out = await llm.generate_expert_response("salut", "fr")

        self.assertEqual(out, "fallback-ok")
        self.assertEqual(calls[0], llm.GEMINI_MODEL)
        self.assertIn("gemini-2.5-flash-lite", calls)

    async def test_quota_without_fallback_raises(self) -> None:
        async def fake_call(client, model, payload):
            raise llm._QuotaError("429 quota")

        with mock.patch.object(llm, "GEMINI_API_KEY", "k"), \
             mock.patch.object(llm, "GEMINI_FALLBACK_MODEL", ""), \
             mock.patch.object(llm, "_call_gemini", fake_call):
            with self.assertRaises(RuntimeError):
                await llm.generate_expert_response("salut", "fr")


class ChatRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_unsupported_language_returns_400(self) -> None:
        r = self.client.post("/api/chat", json={"message": "bonjour", "language": "en"})
        self.assertEqual(r.status_code, 400)

    def test_empty_message_returns_400(self) -> None:
        r = self.client.post("/api/chat", json={"message": "   ", "language": "fr"})
        self.assertEqual(r.status_code, 400)

    def test_success_path_uses_llm(self) -> None:
        async def fake_generate(**kwargs):
            return "Réponse experte."
        with mock.patch("backend.app.generate_expert_response", fake_generate):
            r = self.client.post("/api/chat", json={"message": "Quelle culture ?", "language": "fr"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["response"], "Réponse experte.")

    def test_llm_failure_returns_503(self) -> None:
        async def fake_generate(**kwargs):
            raise RuntimeError("LLM indisponible")
        with mock.patch("backend.app.generate_expert_response", fake_generate):
            r = self.client.post("/api/chat", json={"message": "Bonjour", "language": "fr"})
        self.assertEqual(r.status_code, 503)


class TtsRouteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_empty_text_returns_400(self) -> None:
        r = self.client.post("/api/tts", json={"text": "  ", "language": "ar"})
        self.assertEqual(r.status_code, 400)

    def test_tts_failure_returns_503(self) -> None:
        async def fake_tts(text, language):
            raise RuntimeError("TTS indisponible")
        with mock.patch("backend.app.synthesize_speech", fake_tts):
            r = self.client.post("/api/tts", json={"text": "مرحبا", "language": "ar"})
        self.assertEqual(r.status_code, 503)

    def test_tts_success_returns_wav(self) -> None:
        async def fake_tts(text, language):
            return b"RIFF....WAVEfake"
        with mock.patch("backend.app.synthesize_speech", fake_tts):
            r = self.client.post("/api/tts", json={"text": "مرحبا", "language": "ar"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.headers["content-type"], "audio/wav")
        self.assertTrue(r.content.startswith(b"RIFF"))


if __name__ == "__main__":
    unittest.main()
