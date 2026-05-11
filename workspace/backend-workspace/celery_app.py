"""
Celery Application Instance
============================
Broker: Redis
Backend: Redis (result store)

Queues:
  - scoring   : signal scoring tasks (triggered on candle close)
  - default   : general async tasks

Usage:
    celery -A celery_app worker --loglevel=info -Q scoring,default
    celery -A celery_app beat   --loglevel=info
"""

import os
from celery import Celery
from celery.schedules import crontab

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

app = Celery(
    "trading_system",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "engine.tasks",   # signal scoring tasks (Task 13)
        "trade.tasks",    # trade execution tasks (Task 04)
    ],
)

app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task routing
    task_routes={
        "engine.tasks.run_signal_scoring": {"queue": "scoring"},
    },

    # Retry policy
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_max_retries=3,

    # Beat schedule — candle-close triggers
    # These will be populated in Task 13 when engine/tasks.py is implemented
    beat_schedule={},
)


if __name__ == "__main__":
    app.start()
