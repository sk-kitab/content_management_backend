import json

from voice_pipeline.pronunciation import Pronunciation


def test_whole_word_only():
    p = Pronunciation(aliases={"Karma": "कर्मा"})
    assert p.apply("Karma and Karmas") == "कर्मा and Karmas"


def test_longest_key_wins():
    p = Pronunciation(aliases={"D. Patel": "डी पटेल", "Kamlesh D. Patel": "कमलेश डी पटेल"})
    assert p.apply("By Kamlesh D. Patel.") == "By कमलेश डी पटेल."


def test_missing_file_and_unknown_language_are_no_ops(tmp_path):
    assert Pronunciation.load("en", tmp_path / "nope.json").apply("Karma") == "Karma"
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"hi": {"aliases": {"a": "b"}}}))
    assert Pronunciation.load("en", path).aliases == {}


def test_locators_are_parsed(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps({"en": {"aliases": {}, "locators": [["dict1", "v1"]]}}))
    assert Pronunciation.load("en", path).locators == (("dict1", "v1"),)


def test_seeded_file_has_hindi_entries():
    p = Pronunciation.load("hi")
    assert p.aliases["Satguru"] == "सतगुरु"
    assert Pronunciation.load("en").aliases == {}
