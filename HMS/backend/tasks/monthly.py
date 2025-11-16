from celery_app import celery
from datetime import date, timedelta
from calendar import monthrange

from HMS.backend.app import create_app
from HMS.backend.models.app import Doctor, Appointment, AppointmentStatus
from HMS.backend.utils.reports import generate_doctor_monthly_html
from HMS.backend.utils.mailer import notify_user


@celery.task(name='HMS.backend.tasks.monthly.generate_monthly_reports')
def generate_monthly_reports():
    """Generate month report for each doctor for the previous month and store or email it."""
    app = create_app()
    with app.app_context():
        today = date.today()
        # previous month
        year = today.year
        month = today.month - 1 or 12
        if today.month == 1:
            year = today.year - 1
            month = 12

        start_day = date(year, month, 1)
        _, last_day = monthrange(year, month)
        end_day = date(year, month, last_day)

        doctors = Doctor.query.all()
        for doc in doctors:
            appts = (
                Appointment.query.filter(
                    Appointment.doctor_id == doc.id,
                    Appointment.date >= start_day,
                    Appointment.date <= end_day,
                )
                .order_by(Appointment.date)
                .all()
            )

            total = len(appts)
            completed = len([a for a in appts if a.status == AppointmentStatus.COMPLETED])
            cancelled = len([a for a in appts if a.status == AppointmentStatus.CANCELLED])

            summary = {"total": total, "completed": completed, "cancelled": cancelled}

            # generate HTML report
            report_path = generate_doctor_monthly_html(doc, year, month, summary, appts)

            # notify doctor (if linked user and email exists)
            user = getattr(doc, 'user', None)
            if user and getattr(user, 'email', None):
                subject = f"Monthly Activity Report for {start_day.strftime('%Y-%m')}"
                body = f"Report generated: {report_path}"
                notify_user(user.email, subject, body)

    return True
