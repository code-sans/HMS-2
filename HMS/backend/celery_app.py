import os
from celery import Celery
from celery.schedules import crontab

# Broker and backend from environment or defaults
BROKER = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

celery = Celery('hms', broker=BROKER, backend=BACKEND)

# Use JSON by default
celery.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
)

# Periodic tasks (beat)
celery.conf.beat_schedule = {
    'send-daily-reminders': {
        'task': 'HMS.backend.tasks.reminders.send_daily_reminders',
        # every day at 08:00
        'schedule': crontab(hour=8, minute=0),
    },
    'monthly-doctor-reports': {
        'task': 'HMS.backend.tasks.monthly.generate_monthly_reports',
        # 1st day of month at 00:05
        'schedule': crontab(day_of_month='1', hour=0, minute=5),
    },
}

# Autodiscover tasks in the package namespace
celery.autodiscover_tasks(['HMS.backend.tasks'])
