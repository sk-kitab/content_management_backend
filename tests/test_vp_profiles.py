from voice_pipeline.profiles import PROFILES, STEP_KEYS, anchor_for, resolve_steps


def test_defaults():
    steps = resolve_steps("en")
    assert set(steps) == set(STEP_KEYS)
    assert steps == {"normalize": False, "pronunciation": False, "overlap": True,
                     "qc_assess": True, "qc_fix": True, "pause_extension": False}


def test_overrides_apply_in_order_and_ignore_unknown_and_none():
    steps = resolve_steps("hi", {"normalize": True, "bogus": True}, {"normalize": False, "overlap": None})
    assert steps["normalize"] is False
    assert steps["overlap"] is True
    assert "bogus" not in steps


def test_fix_implies_assess():
    assert resolve_steps("en", {"qc_assess": False, "qc_fix": True})["qc_assess"] is True
    assert resolve_steps("en", {"qc_assess": False, "qc_fix": False})["qc_assess"] is False


def test_anchor_lookup():
    assert anchor_for(PROFILES["hi"].default_voice_id).name == "hi_kitab_narrator_v2.wav"
    assert anchor_for("unknown-voice") is None
