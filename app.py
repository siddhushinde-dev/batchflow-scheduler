"""
app.py - Flask web application for the Batch Job Scheduler.

Run with:
    pip install flask
    python app.py
"""

import json
import os
from flask import Flask, jsonify, render_template, request

from scheduler import Scheduler

# ── App & scheduler setup ────────────────────────────────────────────────
app = Flask(__name__)
scheduler = Scheduler()

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.json")


# ── Helper ────────────────────────────────────────────────────────────────
def _ok(data: dict = None, message: str = "OK"):
    payload = {"success": True, "message": message}
    if data:
        payload.update(data)
    return jsonify(payload)


def _err(message: str, status: int = 400):
    return jsonify({"success": False, "message": message}), status


# ── HTML Page ─────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


# ── Scheduler state (polled by frontend every second) ─────────────────────
@app.route("/api/state")
def api_state():
    return jsonify(scheduler.get_state())


# ── Job management ────────────────────────────────────────────────────────
@app.route("/api/jobs", methods=["POST"])
def api_add_job():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    try:
        execution_time = int(data.get("execution_time", 0))
        priority = int(data.get("priority", 1))
    except (TypeError, ValueError):
        return _err("execution_time and priority must be integers.")

    if not name:
        return _err("Job name is required.")
    if execution_time < 1 or execution_time > 120:
        return _err("Execution time must be between 1 and 120 seconds.")
    if priority < 1 or priority > 10:
        return _err("Priority must be between 1 and 10.")

    job = scheduler.add_job(name, execution_time, priority)
    return _ok({"job": job.to_dict()}, f"Job '{name}' added successfully.")


@app.route("/api/jobs/<job_id>/cancel", methods=["POST"])
def api_cancel_job(job_id):
    success = scheduler.cancel_job(job_id)
    if success:
        return _ok(message=f"Job {job_id} cancelled.")
    return _err(f"Job {job_id} not found or not cancellable.")


@app.route("/api/jobs/clear", methods=["POST"])
def api_clear_jobs():
    scheduler.clear_all()
    return _ok(message="All non-running jobs cleared.")


# ── Scheduler control ─────────────────────────────────────────────────────
@app.route("/api/scheduler/start", methods=["POST"])
def api_start():
    data = request.get_json(silent=True) or {}
    algo = data.get("algorithm", scheduler.algorithm)
    scheduler.set_algorithm(algo)
    scheduler.start()
    return _ok(message=f"Scheduler started with {algo}.")


@app.route("/api/scheduler/stop", methods=["POST"])
def api_stop():
    scheduler.stop()
    return _ok(message="Scheduler stopped.")


@app.route("/api/scheduler/pause", methods=["POST"])
def api_pause():
    scheduler.pause()
    return _ok(message="Scheduler paused.")


@app.route("/api/scheduler/resume", methods=["POST"])
def api_resume():
    scheduler.resume()
    return _ok(message="Scheduler resumed.")


@app.route("/api/scheduler/algorithm", methods=["POST"])
def api_set_algorithm():
    data = request.get_json(silent=True) or {}
    algo = data.get("algorithm", "")
    if algo not in (Scheduler.ALGO_FCFS, Scheduler.ALGO_SJF, Scheduler.ALGO_PRIORITY):
        return _err("Invalid algorithm. Choose FCFS, SJF, or Priority.")
    scheduler.set_algorithm(algo)
    return _ok(message=f"Algorithm set to {algo}.")


# ── Persistence ───────────────────────────────────────────────────────────
@app.route("/api/jobs/save", methods=["POST"])
def api_save():
    jobs = scheduler.get_jobs_for_save()
    with open(DATA_FILE, "w") as f:
        json.dump({"jobs": jobs, "algorithm": scheduler.algorithm}, f, indent=2)
    return _ok(message=f"Saved {len(jobs)} jobs to data.json.")


@app.route("/api/jobs/load", methods=["POST"])
def api_load():
    if not os.path.exists(DATA_FILE):
        return _err("No saved data found (data.json missing).")
    with open(DATA_FILE) as f:
        data = json.load(f)
    scheduler.load_jobs(data.get("jobs", []))
    scheduler.set_algorithm(data.get("algorithm", Scheduler.ALGO_FCFS))
    count = len(data.get("jobs", []))
    return _ok(message=f"Loaded {count} jobs from data.json.")


# ── Run ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 55)
    print("  Batch Job Scheduler  —  http://127.0.0.1:5000")
    print("=" * 55)
    app.run(debug=True, threaded=True, use_reloader=False)
