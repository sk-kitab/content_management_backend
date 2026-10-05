import pytest

from voice_pipeline.net import with_retries


class StatusError(Exception):
    def __init__(self, status):
        super().__init__(f"status {status}")
        self.status_code = status


def test_transient_errors_are_retried_until_success(monkeypatch):
    monkeypatch.setattr("voice_pipeline.net.time.sleep", lambda s: None)
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 3:
            raise StatusError(429)
        return "ok"

    assert with_retries(fn) == "ok"
    assert len(calls) == 3


def test_permanent_error_is_raised_immediately(monkeypatch):
    monkeypatch.setattr("voice_pipeline.net.time.sleep", lambda s: None)
    calls = []

    def fn():
        calls.append(1)
        raise StatusError(401)

    with pytest.raises(StatusError):
        with_retries(fn)
    assert len(calls) == 1


def test_gives_up_after_attempts(monkeypatch):
    monkeypatch.setattr("voice_pipeline.net.time.sleep", lambda s: None)
    calls = []

    def fn():
        calls.append(1)
        raise StatusError(503)

    with pytest.raises(StatusError):
        with_retries(fn, attempts=3)
    assert len(calls) == 3
