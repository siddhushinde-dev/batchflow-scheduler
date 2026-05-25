"""
job.py - Job data model for the Batch Job Scheduler
"""

import uuid
from datetime import datetime


class Job:
    """Represents a single batch job with all its metadata."""

    STATUS_WAITING = "Waiting"
    STATUS_RUNNING = "Running"
    STATUS_COMPLETED = "Completed"
    STATUS_CANCELLED = "Cancelled"

    def __init__(self, name: str, execution_time: int, priority: int):
        self.id = str(uuid.uuid4())[:8]          # Short unique ID
        self.name = name
        self.execution_time = int(execution_time) # Duration in seconds
        self.priority = int(priority)             # Lower number = higher priority
        self.status = self.STATUS_WAITING
        self.created_at = datetime.now().isoformat()
        self.started_at = None
        self.completed_at = None
        self.progress = 0                         # 0–100 percent

    def to_dict(self) -> dict:
        """Serialize the job to a dictionary (for JSON storage / API response)."""
        return {
            "id": self.id,
            "name": self.name,
            "execution_time": self.execution_time,
            "priority": self.priority,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "progress": self.progress,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        """Deserialize a job from a dictionary (for loading from JSON)."""
        job = cls(data["name"], data["execution_time"], data["priority"])
        job.id = data.get("id", job.id)
        job.status = data.get("status", cls.STATUS_WAITING)
        job.created_at = data.get("created_at", job.created_at)
        job.started_at = data.get("started_at")
        job.completed_at = data.get("completed_at")
        job.progress = data.get("progress", 0)
        # Reset running jobs to waiting on reload
        if job.status == cls.STATUS_RUNNING:
            job.status = cls.STATUS_WAITING
            job.progress = 0
            job.started_at = None
        return job

    def __repr__(self):
        return f"<Job id={self.id} name={self.name} status={self.status}>"
