"""Tests for OpenAI-compatible embedding endpoints."""

from __future__ import annotations

import os
import sys
import types

from jdocmunch_mcp.embeddings import provider as emb_provider


_ENV_KEYS = (
    "JDOCMUNCH_EMBEDDING_PROVIDER",
    "JDOCMUNCH_OPENAI_COMPAT_URL",
    "JDOCMUNCH_OPENAI_COMPAT_MODEL",
    "JDOCMUNCH_OPENAI_COMPAT_API_KEY",
    "GOOGLE_API_KEY",
    "OPENAI_API_KEY",
)


def _clear_embedding_env(monkeypatch):
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    emb_provider._reset_provider_cache()
    emb_provider._reset_query_cache()


def _install_fake_openai(monkeypatch):
    class _FakeEmbeddings:
        def __init__(self):
            self.calls = []

        def create(self, model, input):
            batch = list(input)
            self.calls.append({"model": model, "input": batch})
            return types.SimpleNamespace(
                data=[
                    types.SimpleNamespace(embedding=[float(i + 1), float(len(text))])
                    for i, text in enumerate(batch)
                ]
            )

    class _FakeOpenAI:
        instances = []

        def __init__(self, api_key=None, base_url=None):
            self.api_key = api_key
            self.base_url = base_url
            self.embeddings = _FakeEmbeddings()
            self.instances.append(self)

    module = types.ModuleType("openai")
    module.OpenAI = _FakeOpenAI
    monkeypatch.setitem(sys.modules, "openai", module)
    return _FakeOpenAI


class _FakeSection:
    def __init__(self, content_hash="hash-a", content="alpha", title="Alpha"):
        self.content_hash = content_hash
        self.content = content
        self.title = title
        self.summary = ""
        self.embedding = []


def test_get_provider_name_accepts_openai_compatible_aliases(monkeypatch):
    for value in ("openai-compatible", "openai_compatible"):
        _clear_embedding_env(monkeypatch)
        monkeypatch.setenv("JDOCMUNCH_EMBEDDING_PROVIDER", value)
        assert emb_provider.get_provider_name() == "openai-compatible"


def test_openai_compatible_is_not_auto_detected(monkeypatch):
    _clear_embedding_env(monkeypatch)
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_MODEL", "nomic-embed-text")
    monkeypatch.setattr(emb_provider, "_sentence_transformers_available", lambda: False)

    assert emb_provider.get_provider_name() is None
    assert emb_provider.should_embed("auto") is False


def test_should_embed_auto_with_explicit_openai_compatible(monkeypatch):
    _clear_embedding_env(monkeypatch)
    monkeypatch.setenv("JDOCMUNCH_EMBEDDING_PROVIDER", "openai-compatible")

    assert emb_provider.should_embed("auto") is True


def test_openai_compatible_missing_config_fails_safely(monkeypatch):
    _clear_embedding_env(monkeypatch)
    monkeypatch.setenv("JDOCMUNCH_EMBEDDING_PROVIDER", "openai-compatible")

    assert emb_provider._get_provider() is None

    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_URL", "http://localhost:11434/v1")
    assert emb_provider._get_provider() is None


def test_openai_compatible_provider_uses_configured_endpoint(monkeypatch):
    _clear_embedding_env(monkeypatch)
    fake_openai = _install_fake_openai(monkeypatch)
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_MODEL", "nomic-embed-text")
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_API_KEY", "local-key")

    provider = emb_provider._OpenAICompatibleProvider()
    out = provider.embed_texts(["alpha", "beta"])

    assert out == [[1.0, 5.0], [2.0, 4.0]]
    instance = fake_openai.instances[0]
    assert instance.api_key == "local-key"
    assert instance.base_url == "http://localhost:11434/v1"
    assert instance.embeddings.calls == [
        {"model": "nomic-embed-text", "input": ["alpha", "beta"]}
    ]


def test_openai_compatible_ignores_openai_api_key(monkeypatch):
    _clear_embedding_env(monkeypatch)
    fake_openai = _install_fake_openai(monkeypatch)
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_MODEL", "nomic-embed-text")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-shared")

    emb_provider._OpenAICompatibleProvider()

    assert fake_openai.instances[0].api_key == "local"


def test_openai_compatible_api_key_defaults_to_local(monkeypatch):
    _clear_embedding_env(monkeypatch)
    fake_openai = _install_fake_openai(monkeypatch)
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_MODEL", "nomic-embed-text")

    emb_provider._OpenAICompatibleProvider()

    assert fake_openai.instances[0].api_key == "local"


def test_openai_compatible_signature_tracks_endpoint_and_model(monkeypatch):
    _clear_embedding_env(monkeypatch)
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_MODEL", "model-a")
    sig_a = emb_provider._provider_signature("openai-compatible")

    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_MODEL", "model-b")
    sig_b = emb_provider._provider_signature("openai-compatible")

    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_URL", "http://localhost:1234/v1")
    sig_c = emb_provider._provider_signature("openai-compatible")

    assert sig_a != sig_b
    assert sig_b != sig_c


def test_openai_compatible_identity_includes_endpoint_and_model(monkeypatch):
    _clear_embedding_env(monkeypatch)
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_MODEL", "nomic-embed-text")

    model, dim = emb_provider._provider_identity("openai-compatible")

    assert model == "http://localhost:11434/v1::nomic-embed-text"
    assert dim is None


def test_query_cache_invalidates_when_openai_compatible_model_changes(monkeypatch):
    _clear_embedding_env(monkeypatch)
    monkeypatch.setenv("JDOCMUNCH_EMBEDDING_PROVIDER", "openai-compatible")
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_MODEL", "model-a")

    class _FakeProvider:
        def __init__(self):
            self.value = 1.0 if os.environ["JDOCMUNCH_OPENAI_COMPAT_MODEL"] == "model-a" else 2.0

        def embed_texts(self, texts, task_type="retrieval_document"):
            return [[self.value] for _ in texts]

    monkeypatch.setitem(emb_provider._PROVIDER_FACTORIES, "openai-compatible", _FakeProvider)

    v1 = emb_provider.embed_query("same query")
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_MODEL", "model-b")
    v2 = emb_provider.embed_query("same query")

    assert v1 == [1.0]
    assert v2 == [2.0]


def test_section_cache_invalidates_when_openai_compatible_model_changes(tmp_path, monkeypatch):
    _clear_embedding_env(monkeypatch)
    monkeypatch.setenv("JDOCMUNCH_EMBEDDING_PROVIDER", "openai-compatible")
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_MODEL", "model-a")
    calls = {"n": 0}

    class _FakeProvider:
        def __init__(self):
            self.value = 1.0 if os.environ["JDOCMUNCH_OPENAI_COMPAT_MODEL"] == "model-a" else 2.0

        def embed_texts(self, texts, task_type="retrieval_document"):
            calls["n"] += 1
            return [[self.value] for _ in texts]

    monkeypatch.setitem(emb_provider._PROVIDER_FACTORIES, "openai-compatible", _FakeProvider)

    first = _FakeSection()
    emb_provider.embed_sections([first], owner="o", name="n", storage_path=str(tmp_path))

    second = _FakeSection()
    emb_provider.embed_sections([second], owner="o", name="n", storage_path=str(tmp_path))
    assert calls["n"] == 1
    assert second.embedding == [1.0]

    monkeypatch.setenv("JDOCMUNCH_OPENAI_COMPAT_MODEL", "model-b")
    third = _FakeSection()
    emb_provider.embed_sections([third], owner="o", name="n", storage_path=str(tmp_path))

    assert calls["n"] == 2
    assert third.embedding == [2.0]
