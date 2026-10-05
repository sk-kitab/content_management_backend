from voice_pipeline.normalization.cache_store import InMemoryCache, JSONFileCache
from voice_pipeline.normalization.detectors import find_spans
from voice_pipeline.normalization.llm_normalizer import LLMNormalizer
from voice_pipeline.normalization.pipeline import NormalizationPipeline, normalize_safely


class CountingLLM(LLMNormalizer):
    def __init__(self):
        self.calls = 0

    def normalize_batch(self, items, language_hint="en"):
        self.calls += 1
        return {i["key"]: f"<{i['text']}>" for i in items}


class RaisingLLM(LLMNormalizer):
    def normalize_batch(self, items, language_hint="en"):
        raise RuntimeError("quota exceeded")


def test_detectors_find_each_category():
    text = "Dr. Smith paid $42.50 on 2024-01-01 for 30% of 5 kg"
    cats = {s.category for s in find_spans(text)}
    assert {"abbreviation", "currency", "date", "percent", "measurement"} <= cats


def test_hindi_compound_and_latin_spans():
    spans = {s.text: s.category for s in find_spans("ओमेगा-3 और विटामिन G लें")}
    assert spans["ओमेगा-3"] == "alnum_compound"
    assert spans["G"] == "latin_in_indic"


def test_cache_hit_skips_llm_and_substitution_is_offset_safe():
    llm = CountingLLM()
    pipe = NormalizationPipeline(InMemoryCache(), llm, language_hint="en")
    first = pipe.normalize("Buy 30 apples and 30 pears.")
    assert first.normalized_text == "Buy <30> apples and <30> pears."
    assert llm.calls == 1
    second = pipe.normalize("Buy 30 apples and 30 pears.")
    assert second.normalized_text == first.normalized_text
    assert llm.calls == 1
    assert second.new_terms == 0


def test_json_cache_persists(tmp_path):
    path = tmp_path / "cache.json"
    cache = JSONFileCache(path)
    cache.set("en:plain_number:7", "seven")
    cache.flush()
    assert JSONFileCache(path).get("en:plain_number:7") == "seven"


def test_normalize_safely_keeps_text_and_notes_failure():
    pipe = NormalizationPipeline(InMemoryCache(), RaisingLLM(), language_hint="en")
    notes: list[str] = []
    assert normalize_safely(pipe, "Take 3 steps.", notes) == "Take 3 steps."
    assert len(notes) == 1 and "quota exceeded" in notes[0]


def test_gemini_drops_null_and_stringifies_values():
    from types import SimpleNamespace
    from voice_pipeline.normalization.llm_normalizer import GeminiNormalizer

    class Models:
        def generate_content(self, **kw):
            return SimpleNamespace(text='{"a": 5, "b": null, "c": "x"}')

    g = GeminiNormalizer.__new__(GeminiNormalizer)
    g._client = SimpleNamespace(models=Models())
    g._model = "m"
    out = g.normalize_batch([{"key": "a", "text": "5", "category": "plain_number"}], "en")
    assert out == {"a": "5", "c": "x"}


def test_json_cache_concurrent_flushes_merge(tmp_path):
    path = tmp_path / "c.json"
    a, b = JSONFileCache(path), JSONFileCache(path)
    a.set("k1", "one")
    b.set("k2", "two")
    a.flush()
    b.flush()
    fresh = JSONFileCache(path)
    assert fresh.get("k1") == "one" and fresh.get("k2") == "two"
    assert not list(tmp_path.glob("*.tmp"))
