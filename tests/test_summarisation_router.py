import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from backend.main import app
from source.database import get_session
from source.models import Summary, PipelineJob


def _make_summary(
    linear_id="SUM-TEST",
    pdf_path="books/Nature/test.pdf",
    summarisation_status=None,
):
    s = MagicMock(spec=Summary)
    s.linear_id = linear_id
    s.language = "english"
    s.title = "Test Book"
    s.author = "Author"
    s.pdf_supabase_path = pdf_path
    s.summarisation_status = summarisation_status
    s.final_summary = "The final summary."
    s.copyright_revised_summary = None
    s.copyright_report = None
    s.voice_status = "source"
    return s


def _mock_session(summary, job=None):
    results = [MagicMock(), MagicMock()]
    results[0].scalar_one_or_none.return_value = summary
    results[1].scalar_one_or_none.return_value = job
    call_count = 0

    async def execute_side_effect(*args, **kwargs):
        nonlocal call_count
        r = results[min(call_count, len(results) - 1)]
        call_count += 1
        return r

    session = AsyncMock(spec=AsyncSession)
    session.execute = AsyncMock(side_effect=execute_side_effect)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_start_404_when_summary_missing():
    session = _mock_session(None)
    app.dependency_overrides[get_session] = lambda: session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/summarisation/DOES-NOT-EXIST/start")

    app.dependency_overrides.clear()
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_start_400_when_no_pdf_path():
    s = _make_summary(pdf_path=None)
    session = _mock_session(s)
    app.dependency_overrides[get_session] = lambda: session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/summarisation/SUM-TEST/start")

    app.dependency_overrides.clear()
    assert r.status_code == 400
    assert "pdf_supabase_path" in r.json()["detail"]


@pytest.mark.asyncio
async def test_start_409_when_already_running():
    s = _make_summary(summarisation_status="summarising")
    session = _mock_session(s)
    app.dependency_overrides[get_session] = lambda: session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/summarisation/SUM-TEST/start")

    app.dependency_overrides.clear()
    assert r.status_code == 409


@pytest.mark.asyncio
async def test_start_returns_202_and_job_id():
    s = _make_summary()
    session = _mock_session(s)

    async def refresh_sets_id(job):
        job.id = 42

    session.refresh = AsyncMock(side_effect=refresh_sets_id)
    app.dependency_overrides[get_session] = lambda: session

    with patch("source.routers.summarisation._run_summarisation"):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post("/api/summarisation/SUM-TEST/start")

    app.dependency_overrides.clear()
    assert r.status_code == 202
    assert r.json()["job_id"] == 42


@pytest.mark.asyncio
async def test_status_returns_summarisation_status():
    s = _make_summary(summarisation_status="copyright_passed")
    job = MagicMock(spec=PipelineJob)
    job.id = 1
    job.status = "done"
    job.error = None
    session = _mock_session(s, job)
    app.dependency_overrides[get_session] = lambda: session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/summarisation/SUM-TEST/status")

    app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["summarisation_status"] == "copyright_passed"


@pytest.mark.asyncio
async def test_copyright_report_returns_violations():
    s = _make_summary(summarisation_status="copyright_failed")
    s.copyright_report = {
        "copyright_status": "Under Copyright",
        "violations": [
            {
                "summary_sentence": "bad sentence",
                "reference_sentence": "original",
                "suggested_rewrite": "good sentence",
                "reason": "copied",
            }
        ],
    }
    session = _mock_session(s)
    app.dependency_overrides[get_session] = lambda: session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/summarisation/SUM-TEST/copyright-report")

    app.dependency_overrides.clear()
    assert r.status_code == 200
    data = r.json()
    assert data["copyright_status"] == "Under Copyright"
    assert len(data["violations"]) == 1
    assert data["violations"][0]["suggested_rewrite"] == "good sentence"


@pytest.mark.asyncio
async def test_approve_sets_voice_status():
    s = _make_summary(summarisation_status="copyright_passed")
    session = _mock_session(s)
    app.dependency_overrides[get_session] = lambda: session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/summarisation/SUM-TEST/approve")

    app.dependency_overrides.clear()
    assert r.status_code == 200
    assert r.json()["voice_status"] == "voice_text"


@pytest.mark.asyncio
async def test_approve_409_when_not_ready():
    s = _make_summary(summarisation_status="summarising")
    session = _mock_session(s)
    app.dependency_overrides[get_session] = lambda: session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/summarisation/SUM-TEST/approve")

    app.dependency_overrides.clear()
    assert r.status_code == 409
