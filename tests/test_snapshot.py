import os
import sys
import types
import unittest
from unittest import mock

from snapshot import build_dashboard_copy


def sample_snapshot() -> dict:
    return {
        "as_of_date": "2026-03-30",
        "regime": "Contraction",
        "direction": "deteriorating",
        "composite_score": -3,
        "composite_1m_change": -2,
        "breadth": "4 risk-off / 1 risk-on / 1 neutral",
        "layers": [
            {"short": "Risk", "z_score": -2.3, "delta_1m": -2.5, "state": "Weakening"},
            {"short": "Global", "z_score": -2.2, "delta_1m": -2.3, "state": "Weakening"},
            {"short": "Stress", "z_score": 2.0, "delta_1m": 3.6, "state": "Improving"},
        ],
        "macro_context": {
            "yield_2yr": {"latest": 3.88, "change_1m_bps": -12.0, "trend": "falling"},
            "housing_starts": {"yoy_pct": -4.1, "trend": "softening"},
            "industrial_production": {"yoy_pct": 0.8, "trend": "flat"},
            "cpi": {"yoy_pct": 2.9, "trend": "softening"},
        },
        "market_vs_macro": {
            "status": "lagging",
            "note": "Official macro data still looks firmer than the equity tape.",
        },
        "fallback_summary": {
            "bottom_line": "Fallback bottom line.",
            "what_changed": "Fallback what changed.",
            "confirmation": "Fallback confirmation.",
            "watch": "Fallback watch.",
        },
    }


class FakeCompletions:
    def __init__(self, parsed=None, output_text: str = ""):
        self._parsed = parsed
        self._output_text = output_text

    def parse(self, **kwargs):
        return types.SimpleNamespace(
            output_parsed=self._parsed,
            output_text=self._output_text,
        )


class FakeOpenAI:
    def __init__(self, api_key: str, parsed=None, output_text: str = "", error: Exception = None):
        self.api_key = api_key
        if error is not None:
            def raise_error(**kwargs):
                raise error
            self.responses = types.SimpleNamespace(parse=raise_error)
        else:
            self.responses = FakeCompletions(parsed=parsed, output_text=output_text)


class SnapshotCopyTests(unittest.TestCase):
    def test_returns_fallback_when_api_key_missing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            copy = build_dashboard_copy(sample_snapshot())
        self.assertEqual(copy["source"], "rule_fallback")
        self.assertEqual(copy["bottom_line"], "Fallback bottom line.")

    def test_returns_openai_copy_when_client_returns_valid_json(self):
        parsed = types.SimpleNamespace(
            model_dump=lambda: {
                "bottom_line": "AI bottom line.",
                "what_changed": "AI changed.",
                "confirmation": "AI confirmation.",
                "watch": "AI watch.",
            }
        )
        fake_module = types.SimpleNamespace(
            OpenAI=lambda api_key: FakeOpenAI(
                api_key,
                parsed=parsed,
            )
        )
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            with mock.patch.dict(sys.modules, {"openai": fake_module}):
                copy = build_dashboard_copy(sample_snapshot())

        self.assertEqual(copy["source"], "openai")
        self.assertEqual(copy["bottom_line"], "AI bottom line.")
        self.assertEqual(copy["what_changed"], "AI changed.")
        self.assertEqual(copy["copy_error"], "")

    def test_returns_fallback_when_client_returns_unparsed_output(self):
        fake_module = types.SimpleNamespace(
            OpenAI=lambda api_key: FakeOpenAI(api_key, parsed=None, output_text="not-json")
        )
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            with mock.patch.dict(sys.modules, {"openai": fake_module}):
                copy = build_dashboard_copy(sample_snapshot())

        self.assertEqual(copy["source"], "rule_fallback")
        self.assertEqual(copy["confirmation"], "Fallback confirmation.")
        self.assertIn("OpenAI returned no parsed output", copy["copy_error"])

    def test_returns_fallback_when_openai_request_raises(self):
        fake_module = types.SimpleNamespace(
            OpenAI=lambda api_key: FakeOpenAI(api_key, error=RuntimeError("boom"))
        )
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=True):
            with mock.patch.dict(sys.modules, {"openai": fake_module}):
                copy = build_dashboard_copy(sample_snapshot())

        self.assertEqual(copy["source"], "rule_fallback")
        self.assertIn("RuntimeError: boom", copy["copy_error"])


@unittest.skipUnless(
    os.getenv("RUN_OPENAI_INTEGRATION") == "1" and os.getenv("OPENAI_API_KEY"),
    "Set RUN_OPENAI_INTEGRATION=1 and OPENAI_API_KEY to run the live OpenAI smoke test.",
)
class SnapshotCopyIntegrationTests(unittest.TestCase):
    def test_live_openai_smoke(self):
        copy = build_dashboard_copy(sample_snapshot())
        self.assertEqual(copy["source"], "openai")
        for key in ["bottom_line", "what_changed", "confirmation", "watch"]:
            self.assertTrue(isinstance(copy[key], str) and copy[key].strip())


if __name__ == "__main__":
    unittest.main()
