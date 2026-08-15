"""Tests for the SOVOS dream-engine layer (no API key, no network)."""
import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from csoai_core.dream import LocalFallback, NemotronClient, governed_dream


def test_local_fallback_is_governed():
    engine = LocalFallback()
    result = governed_dream(engine, "routine MCP selection", enable_thinking=False)
    assert result.engine == "local-fast"
    assert result.depth == "shallow"
    assert "G" in result.gspc and "composite" in result.gspc
    assert 0.0 <= result.gspc["composite"] <= 1.0


def test_nemotron_requires_key():
    client = NemotronClient(api_key="")
    assert client.available is False
    with pytest.raises(RuntimeError):
        client.dream("hello")


def test_nemotron_model_constant():
    assert NemotronClient.DEFAULT_MODEL == "nvidia/nemotron-3-ultra"
    assert NemotronClient.BASE.endswith("/chat/completions")
