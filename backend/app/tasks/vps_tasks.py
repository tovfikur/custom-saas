from celery import Celery
from app.worker import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task
def check_vps_health():
    """Periodic task to check VPS health"""
    logger.info("Checking VPS health for all hosts")
    return {"success": True, "checked_hosts": 0}


@celery_app.task
def bootstrap_vps_task(vps_id: str):
    """Background task to bootstrap VPS"""
    logger.info(f"Bootstrapping VPS {vps_id}")
    return {"success": True, "vps_id": vps_id}