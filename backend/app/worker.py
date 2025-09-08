from celery import Celery
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "saas_orchestrator",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.nginx_tasks",
        "app.tasks.vps_tasks",
        "app.tasks.odoo_tasks",
        "app.tasks.monitoring_tasks",
        "app.tasks.docker_schedule_tasks"
    ]
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.TIMEZONE,
    enable_utc=True,
    task_track_started=True,
    task_routes={
        "app.tasks.nginx_tasks.*": {"queue": "nginx"},
        "app.tasks.vps_tasks.*": {"queue": "vps"},
        "app.tasks.odoo_tasks.*": {"queue": "odoo"},
        "app.tasks.monitoring_tasks.*": {"queue": "monitoring"},
        "app.tasks.docker_schedule_tasks.*": {"queue": "docker_schedule"},
    },
    beat_schedule={
        # Scheduled tasks
        'check-vps-health': {
            'task': 'app.tasks.vps_tasks.check_vps_health',
            'schedule': 300.0,  # Every 5 minutes
        },
        'monthly-lifecycle-check': {
            'task': 'app.tasks.odoo_tasks.monthly_lifecycle_check',
            'schedule': 3600.0,  # Every hour
        },
        'backup-cleanup': {
            'task': 'app.tasks.monitoring_tasks.cleanup_old_backups',
            'schedule': 86400.0,  # Daily
        },
        'process-due-docker-schedules': {
            'task': 'app.tasks.docker_schedule_tasks.process_due_schedules',
            'schedule': 60.0,  # Every minute
        },
        'cleanup-old-schedule-executions': {
            'task': 'app.tasks.docker_schedule_tasks.cleanup_old_executions',
            'schedule': 86400.0,  # Daily
        },
    }
)

if __name__ == "__main__":
    celery_app.start()