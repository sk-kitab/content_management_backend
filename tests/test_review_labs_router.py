import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from backend.main import app
from source.database import get_session
from source.models import Summary


def _make_summary(linear_id="SUM-TEST", audio_url="https://example.com/audio.mp3"):
    s = Summary()
    s.linear_id = linear_id
    s.language = "english"
    s.title = "Test Book"
    s.author = "Author"
    s.audio_url = audio_url
    return s


def _mock_session(summary):
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = summary
    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(return_value=mock_result)
    return session


@pytest.mark.asyncio
async def test_transcript_returns_cached(tmp_path):
    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir()
    cached = {
        "linear_id": "SUM-CACHED",
        "words": [{"word": "hello", "start": 0.0, "end": 0.5, "confidence": 0.99, "speaker": 0}],
        "duration": 2.0,
    }
    (transcript_dir / "SUM-CACHED-english.json").write_text(json.dumps(cached))

    with patch("source.routers.review_labs.TRANSCRIPT_DIR", str(transcript_dir)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/review-labs/SUM-CACHED/transcript")

    assert r.status_code == 200
    assert r.json()["words"][0]["word"] == "hello"
    assert r.json()["duration"] == 2.0


@pytest.mark.asyncio
async def test_transcript_404_when_summary_missing(tmp_path):
    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir()
    session = _mock_session(None)
    app.dependency_overrides[get_session] = lambda: session

    with patch("source.routers.review_labs.TRANSCRIPT_DIR", str(transcript_dir)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/review-labs/DOES-NOT-EXIST/transcript")

    app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_transcript_400_when_no_audio_url(tmp_path):
    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir()
    session = _mock_session(_make_summary(audio_url=None))
    app.dependency_overrides[get_session] = lambda: session

    with patch("source.routers.review_labs.TRANSCRIPT_DIR", str(transcript_dir)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/review-labs/SUM-TEST/transcript")

    app.dependency_overrides.clear()
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_transcript_calls_deepgram_and_returns_words(tmp_path):
    session = _mock_session(_make_summary())
    app.dependency_overrides[get_session] = lambda: session

    transcript_dir = tmp_path / "transcripts"
    audio_dir = tmp_path / "audio"
    transcript_dir.mkdir()
    audio_dir.mkdir()

    async def fake_download(url, dest):
        with open(dest, "wb") as f:
            f.write(b"FAKEAUDIO")
        return dest

    fake_word = MagicMock()
    fake_word.word = "hello"
    fake_word.start = 0.0
    fake_word.end = 0.5
    fake_word.confidence = 0.99
    fake_word.speaker = 0
    fake_word.model_dump.return_value = {
        "word": "hello", "start": 0.0, "end": 0.5, "confidence": 0.99, "speaker": 0,
    }

    mock_response = MagicMock()
    mock_response.results.channels = [MagicMock()]
    mock_response.results.channels[0].alternatives = [MagicMock()]
    mock_response.results.channels[0].alternatives[0].words = [fake_word]
    mock_response.metadata.duration = 1.5
    mock_response.metadata.model_dump.return_value = {"duration": 1.5}

    with (
        patch("source.routers.review_labs.TRANSCRIPT_DIR", str(transcript_dir)),
        patch("source.routers.review_labs.AUDIO_DIR", str(audio_dir)),
        patch("source.routers.review_labs._download_audio", side_effect=fake_download),
        patch("source.routers.review_labs.DeepgramClient") as mock_dg_cls,
        patch.dict("os.environ", {"deepgram_apikey": "fake-key"}),
    ):
        mock_dg_cls.return_value.listen.v1.media.transcribe_file.return_value = mock_response

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/review-labs/SUM-TEST/transcript?language=english")

    app.dependency_overrides.clear()
    assert r.status_code == 200
    data = r.json()
    assert data["linear_id"] == "SUM-TEST"
    assert len(data["words"]) == 1
    assert data["words"][0]["word"] == "hello"
    assert data["duration"] == 1.5
    assert (transcript_dir / "SUM-TEST-english.json").exists()


@pytest.mark.asyncio
async def test_export_returns_audio(tmp_path):
    session = _mock_session(_make_summary())
    app.dependency_overrides[get_session] = lambda: session

    audio_dir = tmp_path / "audio"
    export_dir = tmp_path / "exports"
    audio_dir.mkdir()
    export_dir.mkdir()
    (audio_dir / "SUM-TEST.mp3").write_bytes(b"FAKEAUDIO")
    # Pre-create output so open() succeeds after mocked ffmpeg
    (export_dir / "SUM-TEST_edited.mp3").write_bytes(b"EDITEDAUDIO")

    with (
        patch("source.routers.review_labs.AUDIO_DIR", str(audio_dir)),
        patch("source.routers.review_labs.EXPORT_DIR", str(export_dir)),
        patch("source.routers.review_labs.subprocess.check_output", return_value=b"2.5\n"),
        patch("source.routers.review_labs.subprocess.run"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/review-labs/SUM-TEST/export",
                json={"edits": [{"type": "delete", "start": 0.5, "end": 1.0}], "format": "mp3"},
            )

    app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/")
    assert r.content == b"EDITEDAUDIO"


@pytest.mark.asyncio
async def test_export_404_when_summary_missing(tmp_path):
    transcript_dir = tmp_path / "transcripts"
    transcript_dir.mkdir()
    session = _mock_session(None)
    app.dependency_overrides[get_session] = lambda: session

    with patch("source.routers.review_labs.TRANSCRIPT_DIR", str(transcript_dir)):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/api/review-labs/DOES-NOT-EXIST/export",
                json={"edits": [], "format": "mp3"},
            )

    app.dependency_overrides.clear()
    assert r.status_code == 404
