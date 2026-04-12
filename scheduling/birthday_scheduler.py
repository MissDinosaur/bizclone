"""
Birthday Email Scheduler - Automated daily birthday email job.

Schedules birthday email sending to run at a specified time each day.
Uses APScheduler for task scheduling.
"""

import logging
import os
from datetime import datetime, time
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from channels.email.birthday_email_service import BirthdayEmailService
from database.orm_models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import config.config as cfg

logger = logging.getLogger(__name__)


class BirthdayEmailScheduler:
    """Manages scheduled birthday email sending."""
    
    def __init__(self, 
                 db_url: str = None,
                 birthday_email_service: BirthdayEmailService = None,
                 schedule_hour: int = 8,
                 schedule_minute: int = 0):
        """
        Initialize birthday email scheduler.
        Args:
            db_url: PostgreSQL connection URL. Defaults to DATABASE_URL env var.
            birthday_email_service: BirthdayEmailService instance.
            schedule_hour: Hour to send birthday emails (0-23, default: 8 AM)
            schedule_minute: Minute to send birthday emails (0-59, default: 0)
        """
        if db_url is None:
            db_url = os.getenv("DATABASE_URL")
        
        self.db_url = db_url
        self.engine = create_engine(db_url, echo=False)
        self.Session = sessionmaker(bind=self.engine)
        
        self.birthday_email_service = birthday_email_service or BirthdayEmailService()
        self.schedule_hour = schedule_hour
        self.schedule_minute = schedule_minute
        
        self.scheduler = BackgroundScheduler()
    
    def send_birthday_emails_job(self):
        """Job function to send birthday emails."""
        logger.info(f"[BirthdayEmailScheduler] Starting scheduled birthday email job at {datetime.now()}")
        
        try:
            session = self.Session()
            try:
                results = self.birthday_email_service.send_birthday_emails(session, days_ahead=0)
                logger.info(f"[BirthdayEmailScheduler] Job completed: {results}")
            finally:
                session.close()
        except Exception as e:
            logger.error(f"[BirthdayEmailScheduler] Job failed with error: {e}", exc_info=True)
    
    def start(self):
        """Start the birthday email scheduler."""
        logger.info(f"[BirthdayEmailScheduler] Starting scheduler to send birthday emails daily at {self.schedule_hour:02d}:{self.schedule_minute:02d} ({cfg.TIMEZONE} timezone)")
        
        # Add job to run at specified time every day in configured timezone
        # CRITICAL: Specify timezone so CronTrigger respects local time, not UTC
        self.scheduler.add_job(
            self.send_birthday_emails_job,
            CronTrigger(hour=self.schedule_hour, minute=self.schedule_minute, timezone=cfg.TIMEZONE),
            id='birthday_email_job',
            name='Send birthday emails',
            replace_existing=True,
            max_instances=1  # Ensure only one instance runs at a time
        )
        
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("[BirthdayEmailScheduler] Scheduler started successfully")
    
    def stop(self):
        """Stop the birthday email scheduler."""
        logger.info("[BirthdayEmailScheduler] Stopping scheduler...")
        
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("[BirthdayEmailScheduler] Scheduler stopped")
    
    def send_now(self):
        """Manually trigger birthday email sending (for testing)."""
        logger.info("[BirthdayEmailScheduler] Manually triggering birthday emails...")
        self.send_birthday_emails_job()
