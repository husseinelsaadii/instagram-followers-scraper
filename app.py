"""Private localhost UI for exporting Instagram followers and following lists."""

from __future__ import annotations

import atexit
import os
import re
import secrets
import threading
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from flask import Flask, abort, jsonify, render_template, request, send_file

from instagram.client import InstagramError, InstagramFollowerScraper
from instagram.exporter import export_to_csv, export_to_json
from instagram.parser import parse_followers


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
ALLOWED_RELATIONSHIPS = {"followers", "following"}
USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")
USER_ID_RE = re.compile(r"^[0-9]{1,30}$")

app = Flask(__name__)
app.config.update(MAX_CONTENT_LENGTH=32 * 1024, SEND_FILE_MAX_AGE_DEFAULT=0)

jobs: dict[str, dict] = {}
jobs_lock = threading.Lock()
executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="instagram-export")
atexit.register(executor.shutdown, wait=False)


def _public_job(job: dict) -> dict:
    """Return only browser-safe job fields. Credentials are never stored here."""
    return {
        key: job[key]
        for key in (
            "id",
            "status",
            "username",
            "relationship",
            "max_results",
            "fetched",
            "message",
            "warning",
            "downloads",
        )
        if key in job
    }


def _same_origin_request() -> bool:
    """Reject cross-site browser posts to this local service."""
    origin = request.headers.get("Origin")
    if not origin:
        return True
    parsed = urlparse(origin)
    return parsed.netloc == request.host and parsed.scheme in {"http", "https"}


def validate_job_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("The request must be a JSON object.")

    sessionid = str(payload.get("sessionid", "")).strip()
    csrftoken = str(payload.get("csrftoken", "")).strip()
    username = str(payload.get("username", "")).strip().lstrip("@")
    user_id = str(payload.get("user_id", "")).strip()
    relationship = str(payload.get("relationship", "followers")).strip().lower()
    max_value = payload.get("max_results")

    if not sessionid:
        raise ValueError("Paste your Instagram sessionid cookie.")
    if not csrftoken:
        raise ValueError("Paste your Instagram csrftoken cookie.")
    if not USERNAME_RE.fullmatch(username):
        raise ValueError("Enter a valid Instagram username (without @).")
    if not USER_ID_RE.fullmatch(user_id):
        raise ValueError("The profile ID must contain numbers only.")
    if relationship not in ALLOWED_RELATIONSHIPS:
        raise ValueError("Choose Followers or Following.")

    if max_value in (None, ""):
        max_results = None
    else:
        try:
            max_results = int(max_value)
        except (TypeError, ValueError) as error:
            raise ValueError("Maximum results must be a whole number.") from error
        if not 1 <= max_results <= 100_000:
            raise ValueError("Maximum results must be between 1 and 100,000.")

    return {
        "sessionid": sessionid,
        "csrftoken": csrftoken,
        "username": username,
        "user_id": user_id,
        "relationship": relationship,
        "max_results": max_results,
    }


def _update_job(job_id: str, **changes) -> None:
    with jobs_lock:
        if job_id in jobs:
            jobs[job_id].update(changes)


def run_export(job_id: str, form: dict) -> None:
    """Run one export in the background without persisting login cookies."""
    username = form["username"]
    relationship = form["relationship"]
    raw_users = []
    _update_job(job_id, status="running", message="Connecting securely to Instagram…")

    try:
        scraper = InstagramFollowerScraper(
            form["sessionid"],
            csrftoken=form["csrftoken"],
        )
        scraper.warm_up()
        _update_job(job_id, message=f"Fetching {relationship}…")

        for user in scraper.iter_relationships(
            form["user_id"], relationship, form["max_results"]
        ):
            raw_users.append(user)
            _update_job(job_id, fetched=len(raw_users))

    except (InstagramError, requests.RequestException) as error:
        if not raw_users:
            _update_job(
                job_id,
                status="failed",
                message="The export could not be completed.",
                warning=str(error),
            )
            return
        warning = f"Instagram stopped the request early: {error}"
    except Exception:
        # Avoid leaking unexpected request details or credentials to the browser.
        _update_job(
            job_id,
            status="failed",
            message="Something unexpected went wrong. Try again with fresh cookies.",
            warning="No files were created.",
        )
        app.logger.exception("Unexpected export failure for job %s", job_id)
        return
    else:
        warning = ""
    finally:
        # Remove credential references as soon as the network work finishes.
        form["sessionid"] = ""
        form["csrftoken"] = ""

    rows = parse_followers(raw_users, username)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    stem = f"{username}_{relationship}_{timestamp}_{job_id[:6]}"
    json_path = export_to_json(rows, OUTPUT_DIR / f"{stem}.json")
    csv_path = export_to_csv(rows, OUTPUT_DIR / f"{stem}.csv")

    _update_job(
        job_id,
        status="completed",
        fetched=len(rows),
        message=f"Export ready — {len(rows):,} {relationship} saved.",
        warning=warning,
        downloads={"csv": csv_path.name, "json": json_path.name},
        paths={"csv": csv_path, "json": json_path},
    )


@app.after_request
def add_security_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    )
    return response


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/jobs")
def create_job():
    if not _same_origin_request():
        return jsonify(error="Cross-site requests are not allowed."), 403
    if not request.is_json:
        return jsonify(error="Send the form as JSON."), 415

    try:
        form = validate_job_payload(request.get_json(silent=True))
    except ValueError as error:
        return jsonify(error=str(error)), 400

    job_id = secrets.token_urlsafe(12)
    job = {
        "id": job_id,
        "status": "queued",
        "username": form["username"],
        "relationship": form["relationship"],
        "max_results": form["max_results"],
        "fetched": 0,
        "message": "Export queued…",
        "warning": "",
        "downloads": {},
    }
    with jobs_lock:
        jobs[job_id] = job
    executor.submit(run_export, job_id, form)
    return jsonify(_public_job(job)), 202


@app.get("/api/jobs/<job_id>")
def get_job(job_id: str):
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return jsonify(error="Export not found. It may be from an earlier app session."), 404
        public = _public_job(job)
    return jsonify(public)


@app.get("/download/<job_id>/<file_type>")
def download(job_id: str, file_type: str):
    if file_type not in {"csv", "json"}:
        abort(404)
    with jobs_lock:
        job = jobs.get(job_id)
        path = job.get("paths", {}).get(file_type) if job else None
    if not path or not Path(path).is_file():
        abort(404)
    return send_file(path, as_attachment=True, download_name=Path(path).name)


if __name__ == "__main__":
    from waitress import serve

    port = int(os.environ.get("PORT", "5000"))
    url = f"http://127.0.0.1:{port}"
    if os.environ.get("NO_BROWSER") != "1":
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    print(f"Instagram Exporter is ready at {url}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    serve(app, host="127.0.0.1", port=port, threads=4)
