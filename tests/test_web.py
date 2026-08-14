import io
import time
import zipfile

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from conftest import StubCompleter, eval_json, skill_json  # noqa: E402
from skillsmith.web import create_app  # noqa: E402


def _client(**kw) -> TestClient:
    return TestClient(create_app(completer=StubCompleter(**kw), forge_workers=2))


def _run_job(client: TestClient, files, formats="claude-code") -> dict:
    r = client.post("/api/jobs", files=files, data={"formats": formats})
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    for _ in range(100):  # poll until the background forge finishes
        job = client.get(f"/api/jobs/{job_id}").json()
        if job["status"] != "running":
            return job
        time.sleep(0.02)
    raise AssertionError("job never finished")


def test_forge_endpoint_produces_reviewable_skills():
    client = _client()
    files = [("files", ("reset.md", b"reset the password after verifying the ticket", "text/markdown"))]
    job = _run_job(client, files)

    assert job["status"] == "done"
    assert len(job["skills"]) == 1
    s = job["skills"][0]
    assert s["source"] == "reset.md"
    assert s["skill"]["name"] == "reset-user-password"
    assert s["status"] == "pass"
    assert s["decision"] == "approved"   # pass skills default to approved


def test_review_skill_needing_edits_defaults_to_pending():
    client = TestClient(create_app(
        completer=StubCompleter(evaluation=eval_json(verdict="revise", confidence="low")),
        forge_workers=2,
    ))
    files = [("files", ("thin.md", b"some thin source", "text/markdown"))]
    job = _run_job(client, files)
    s = job["skills"][0]
    assert s["status"] == "review"
    assert s["decision"] == "pending"


def test_edit_and_approve_then_download_zip():
    client = _client()
    files = [("files", ("reset.md", b"reset password sop", "text/markdown"))]
    job = _run_job(client, files)
    job_id = job["job_id"]
    idx = job["skills"][0]["index"]

    edited = job["skills"][0]["skill"]
    edited["title"] = "Edited Title"
    r = client.put(f"/api/jobs/{job_id}/skills/{idx}", json={"skill": edited, "decision": "approved"})
    assert r.status_code == 200
    assert r.json()["skill"]["title"] == "Edited Title"

    dl = client.get(f"/api/jobs/{job_id}/download")
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(dl.content))
    names = zf.namelist()
    assert any(n.endswith("SKILL.md") for n in names)
    assert any("claude-code/reset-user-password/" in n for n in names)
    assert "Edited Title" in zf.read(names[0]).decode()


def test_invalid_edit_is_rejected_422():
    client = _client()
    files = [("files", ("reset.md", b"reset password sop", "text/markdown"))]
    job = _run_job(client, files)
    job_id = job["job_id"]
    idx = job["skills"][0]["index"]

    bad = job["skills"][0]["skill"]
    bad["name"] = "not a valid kebab name!"   # validator should reject
    r = client.put(f"/api/jobs/{job_id}/skills/{idx}", json={"skill": bad})
    assert r.status_code == 422


def test_discarded_skill_excluded_from_download():
    client = _client()
    files = [("files", ("reset.md", b"reset password sop", "text/markdown"))]
    job = _run_job(client, files)
    job_id = job["job_id"]
    idx = job["skills"][0]["index"]

    client.put(f"/api/jobs/{job_id}/skills/{idx}", json={"decision": "discarded"})
    dl = client.get(f"/api/jobs/{job_id}/download")
    assert dl.status_code == 400   # nothing approved to export


def test_index_page_and_formats_served():
    client = _client()
    assert "Skillsmith" in client.get("/").text
    assert "claude-code" in client.get("/api/formats").json()["formats"]
