from celery_app import celery
from HMS.backend.app import create_app
from HMS.backend.models.app import Patient, Appointment
from HMS.backend.utils.exporter import export_patient_history_csv
from HMS.backend.utils.mailer import notify_user


@celery.task(name='HMS.backend.tasks.export_csv.export_patient_history')
def export_patient_history(patient_id, notify_email=None):
    app = create_app()
    with app.app_context():
        patient = Patient.query.get(patient_id)
        if not patient:
            return {"success": False, "msg": "Patient not found"}

        # fetch all appointments (history + upcoming if desired)
        appts = Appointment.query.filter_by(patient_id=patient.id).order_by(Appointment.date.desc()).all()
        out_path = export_patient_history_csv(patient, appts)

        if notify_email:
            subject = "Your appointment history export is ready"
            body = f"Your CSV export is at: {out_path}"
            notify_user(notify_email, subject, body)

    return {"success": True, "path": out_path}
