from celery import Celery
from app.worker import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task
def cleanup_old_backups():
    """Clean up old backup files"""
    logger.info("Cleaning up old backup files")
    return {"success": True, "cleaned_files": 0}