from celery import Celery
from app.worker import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task
def monthly_lifecycle_check():
    """Check for monthly lifecycle actions"""
    logger.info("Checking monthly lifecycle for all Odoo instances")
    return {"success": True, "instances_checked": 0}