"""
scheduler.py - Core scheduling engine for the Batch Job Scheduler.

Implements:
  - FCFS  (First Come First Served)
  - SJF   (Shortest Job First)
  - Priority Scheduling (lower number = higher priority)

Uses threading so the Flask UI remains responsive during job execution.
"""

import threading
import time
from datetime import datetime
from typing import List, Optional

from job import Job


class Scheduler:
    """Thread-safe batch job scheduler supporting multiple algorithms."""

    ALGO_FCFS = "FCFS"
    ALGO_SJF = "SJF"
    ALGO_PRIORITY = "Priority"

    def __init__(self):
        self.jobs: List[Job] = []           # All registered jobs
        self.logs: List[str] = []           # Execution log messages
        self.algorithm: str = self.ALGO_FCFS
        self.running: bool = False          # Is the scheduler loop active?
        self.paused: bool = False           # Is the scheduler paused?
        self.current_job: Optional[Job] = None
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._pause_event = threading.Event()
        self._pause_event.set()             # Not paused initially

    # ─────────────────────────── Public API ───────────────────────────────

    def add_job(self, name: str, execution_time: int, priority: int) -> Job:
        """Create and enqueue a new job."""
        job = Job(name, execution_time, priority)
        with self._lock:
            self.jobs.append(job)
        self._log(f"✚ Job added: [{job.id}] {job.name} | {job.execution_time}s | P{job.priority}")
        return job

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a waiting job by ID. Returns True if successful."""
        with self._lock:
            for job in self.jobs:
                if job.id == job_id and job.status == Job.STATUS_WAITING:
                    job.status = Job.STATUS_CANCELLED
                    self._log(f"✖ Job cancelled: [{job.id}] {job.name}")
                    return True
        return False

    def clear_all(self):
        """Remove all jobs that are not currently running."""
        with self._lock:
            self.jobs = [j for j in self.jobs if j.status == Job.STATUS_RUNNING]
        self._log("⚠ All non-running jobs cleared.")

    def start(self):
        """Start the scheduler loop in a background thread."""
        if self._thread and self._thread.is_alive():
            return  # Already running
        self.running = True
        self.paused = False
        self._pause_event.set()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._log(f"▶ Scheduler started — Algorithm: {self.algorithm}")

    def stop(self):
        """Stop the scheduler loop."""
        self.running = False
        self._pause_event.set()  # Unblock if paused
        self._log("■ Scheduler stopped.")

    def pause(self):
        """Pause the scheduler after the current job finishes its current tick."""
        self.paused = True
        self._pause_event.clear()
        self._log("⏸ Scheduler paused.")

    def resume(self):
        """Resume the scheduler."""
        self.paused = False
        self._pause_event.set()
        self._log("⏵ Scheduler resumed.")

    def set_algorithm(self, algo: str):
        """Change the scheduling algorithm."""
        if algo in (self.ALGO_FCFS, self.ALGO_SJF, self.ALGO_PRIORITY):
            self.algorithm = algo
            self._log(f"⚙ Algorithm changed to: {algo}")

    def get_state(self) -> dict:
        """Return a JSON-serialisable snapshot of the scheduler state."""
        with self._lock:
            jobs_data = [j.to_dict() for j in self.jobs]
            total = len(self.jobs)
            running_count = sum(1 for j in self.jobs if j.status == Job.STATUS_RUNNING)
            completed = sum(1 for j in self.jobs if j.status == Job.STATUS_COMPLETED)
            waiting = sum(1 for j in self.jobs if j.status == Job.STATUS_WAITING)
            cancelled = sum(1 for j in self.jobs if j.status == Job.STATUS_CANCELLED)
        return {
            "jobs": jobs_data,
            "logs": list(self.logs[-100:]),   # Last 100 log lines
            "algorithm": self.algorithm,
            "is_running": self.running,
            "is_paused": self.paused,
            "stats": {
                "total": total,
                "running": running_count,
                "completed": completed,
                "waiting": waiting,
                "cancelled": cancelled,
            },
        }

    def load_jobs(self, jobs_data: list):
        """Load jobs from serialised list (from saved JSON)."""
        with self._lock:
            self.jobs = [Job.from_dict(d) for d in jobs_data]
        self._log(f"💾 Loaded {len(self.jobs)} jobs from file.")

    def get_jobs_for_save(self) -> list:
        """Return serialised jobs list for saving."""
        with self._lock:
            return [j.to_dict() for j in self.jobs]

    # ─────────────────────────── Internal ─────────────────────────────────

    def _log(self, message: str):
        """Append a timestamped message to the log."""
        ts = datetime.now().strftime("%H:%M:%S")
        entry = f"[{ts}] {message}"
        self.logs.append(entry)
        # Trim log to last 500 entries
        if len(self.logs) > 500:
            self.logs = self.logs[-500:]

    def _get_next_job(self) -> Optional[Job]:
        """Select the next job to run according to the current algorithm."""
        with self._lock:
            waiting = [j for j in self.jobs if j.status == Job.STATUS_WAITING]
        if not waiting:
            return None

        if self.algorithm == self.ALGO_FCFS:
            # First in the list wins (insertion order = arrival order)
            return waiting[0]

        elif self.algorithm == self.ALGO_SJF:
            # Shortest execution_time wins
            return min(waiting, key=lambda j: j.execution_time)

        elif self.algorithm == self.ALGO_PRIORITY:
            # Lowest priority number wins (1 = highest priority)
            return min(waiting, key=lambda j: j.priority)

        return waiting[0]

    def _run_loop(self):
        """Main scheduler loop — runs in a background thread."""
        self._log("🔄 Scheduler loop started.")
        while self.running:
            # Honour pause
            self._pause_event.wait()
            if not self.running:
                break

            next_job = self._get_next_job()
            if next_job is None:
                time.sleep(0.5)   # Idle — wait for new jobs
                continue

            self._execute_job(next_job)

        self._log("🔄 Scheduler loop exited.")
        self.running = False

    def _execute_job(self, job: Job):
        """Simulate job execution with progress ticks."""
        with self._lock:
            job.status = Job.STATUS_RUNNING
            job.started_at = datetime.now().isoformat()
            job.progress = 0
            self.current_job = job

        self._log(f"▶ Running: [{job.id}] {job.name} (est. {job.execution_time}s)")

        tick_interval = 0.5                          # Progress update every 0.5 s
        total_ticks = int(job.execution_time / tick_interval)
        total_ticks = max(total_ticks, 1)

        for tick in range(total_ticks):
            # Respect pause mid-job
            self._pause_event.wait()
            if not self.running:
                break
            # Check if job was externally cancelled (shouldn't happen for running jobs
            # but guard anyway)
            if job.status == Job.STATUS_CANCELLED:
                self._log(f"✖ Job cancelled mid-run: [{job.id}] {job.name}")
                return

            time.sleep(tick_interval)
            with self._lock:
                job.progress = int(((tick + 1) / total_ticks) * 100)

        with self._lock:
            job.status = Job.STATUS_COMPLETED
            job.progress = 100
            job.completed_at = datetime.now().isoformat()
            self.current_job = None

        self._log(f"✔ Completed: [{job.id}] {job.name}")
