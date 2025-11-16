from celery_app import celery
from datetime import date

# Use absolute imports for models under package namespace
from HMS.backend.app import create_app
from HMS.backend.models.app import Appointment, AppointmentStatus, Patient, Doctor
from HMS.backend.utils.mailer import notify_user


@celery.task(name='HMS.backend.tasks.reminders.send_daily_reminders')
def send_daily_reminders():
    """Query today's Booked appointments and send reminders."""
    app = create_app()
    with app.app_context():
        today = date.today()
        appts = Appointment.query.filter(Appointment.date == today, Appointment.status == AppointmentStatus.BOOKED).all()
        for a in appts:
            patient = a.patient
            doctor = a.doctor
            if not patient:
                continue
            time_s = a.time.isoformat() if a.time else ''
            subject = 'Appointment reminder'
            body = f"Hello {patient.name},\nThis is a reminder for your appointment today at {time_s} with Dr. {doctor.name if doctor else ''}."
            # Notify patient by email (if email available via User)
            user = getattr(patient, 'user', None)
            if user and getattr(user, 'email', None):
                notify_user(user.email, subject, body)
            # Optionally, support webhook or SMS here

    return True
