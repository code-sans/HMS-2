import csv
import os
from datetime import datetime

EXPORTS_DIR = os.path.join(os.path.dirname(__file__), '..', 'exports')
if not os.path.exists(EXPORTS_DIR):
    os.makedirs(EXPORTS_DIR, exist_ok=True)


def export_patient_history_csv(patient, appointments, out_path=None):
    """Write CSV for patient appointments + treatments.

    `patient` is a Patient model or dict with id/username.
    `appointments` is a list of Appointment model objects.
    """
    if out_path is None:
        out_path = os.path.join(EXPORTS_DIR, f"treatment_{patient.id}.csv")

    with open(out_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['user_id', 'username', 'consulting_doctor', 'appointment_date', 'diagnosis', 'treatment', 'next_visit'])
        for a in appointments:
            doctor_name = a.doctor.name if a.doctor else ''
            diagnosis = a.treatment.diagnosis if a.treatment else ''
            prescription = a.treatment.prescription if a.treatment else ''
            # next_visit - not available in model; leave blank
            writer.writerow([patient.user.id if hasattr(patient, 'user') else patient.id, patient.name, doctor_name, a.date.isoformat() if a.date else '', diagnosis, prescription, ''])

    return out_path
