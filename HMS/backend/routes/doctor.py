from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from datetime import date, timedelta
from sqlalchemy import func

from .. import db
from ..models.app import Doctor, Patient, Appointment, Treatment, AppointmentStatus
from .auth import doctor_required

doctor_bp = Blueprint("doctor", __name__)


def _get_current_doctor():
    user_id = get_jwt_identity()
    if not user_id:
        return None
    return Doctor.query.filter_by(user_id=user_id).first()


@doctor_bp.route("/dashboard", methods=["GET"])
@doctor_required
def dashboard():
    doctor = _get_current_doctor()
    if not doctor:
        return jsonify({"success": False, "msg": "Doctor profile not found"}), 404

    today = date.today()
    # today's appointments
    today_appts = (
        Appointment.query.filter_by(doctor_id=doctor.id, date=today)
        .order_by(Appointment.time)
        .all()
    )

    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    week_appts = (
        Appointment.query.filter(
            Appointment.doctor_id == doctor.id,
            Appointment.date >= start_of_week,
            Appointment.date <= end_of_week,
        )
        .order_by(Appointment.date, Appointment.time)
        .all()
    )

    def _serialize_appt(a):
        return {
            "id": a.id,
            "patient": a.patient.name if a.patient else None,
            "time": a.time.isoformat() if a.time else None,
            "status": a.status.name if a.status else None,
            "date": a.date.isoformat() if a.date else None,
        }

    return jsonify(
        {
            "today": [_serialize_appt(a) for a in today_appts],
            "week": [_serialize_appt(a) for a in week_appts],
            "counts": {"today": len(today_appts), "week": len(week_appts)},
        }
    )


@doctor_bp.route("/patients", methods=["GET"])
@doctor_required
def list_patients():
    doctor = _get_current_doctor()
    if not doctor:
        return jsonify({"success": False, "msg": "Doctor profile not found"}), 404

    rows = (
        db.session.query(
            Patient.id,
            Patient.name,
            func.max(Appointment.date).label("last_visit"),
            func.count(Appointment.id).label("total_visits"),
        )
        .join(Appointment, Appointment.patient_id == Patient.id)
        .filter(Appointment.doctor_id == doctor.id)
        .group_by(Patient.id)
        .all()
    )

    result = [
        {
            "patient_id": r.id,
            "name": r.name,
            "last_visit_date": r.last_visit.isoformat() if r.last_visit else None,
            "total_visits": int(r.total_visits),
        }
        for r in rows
    ]

    return jsonify({"success": True, "patients": result})


@doctor_bp.route("/appointments/<int:appointment_id>/update", methods=["PUT"])
@doctor_required
def update_appointment(appointment_id):
    doctor = _get_current_doctor()
    if not doctor:
        return jsonify({"success": False, "msg": "Doctor profile not found"}), 404

    appt = Appointment.query.get(appointment_id)
    if not appt:
        return jsonify({"success": False, "msg": "Appointment not found"}), 404

    if appt.doctor_id != doctor.id:
        return jsonify({"success": False, "msg": "Forbidden - not your appointment"}), 403

    data = request.get_json() or {}
    new_status = (data.get("status") or "").strip()
    if not new_status:
        return jsonify({"success": False, "msg": "status is required"}), 400

    try:
        new_enum = AppointmentStatus(new_status)
    except Exception:
        try:
            new_enum = AppointmentStatus[new_status.upper()]
        except Exception:
            return jsonify({"success": False, "msg": "Invalid status"}), 400

    cur = appt.status
    if cur == AppointmentStatus.BOOKED:
        if new_enum in (AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED):
            appt.status = new_enum
            db.session.commit()
            return jsonify({
                "success": True,
                "appointment": {
                    "id": appt.id,
                    "date": appt.date.isoformat() if appt.date else None,
                    "time": appt.time.isoformat() if appt.time else None,
                    "status": appt.status.name,
                },
            })
        else:
            return jsonify({"success": False, "msg": "Invalid transition from Booked"}), 400
    else:
        return jsonify({"success": False, "msg": "Cannot change status once Completed/Cancelled"}), 400


@doctor_bp.route("/treatment/add", methods=["POST"])
@doctor_required
def add_treatment():
    doctor = _get_current_doctor()
    if not doctor:
        return jsonify({"success": False, "msg": "Doctor profile not found"}), 404

    data = request.get_json() or {}
    appointment_id = data.get("appointment_id")
    diagnosis = data.get("diagnosis")
    prescription = data.get("prescription")
    notes = data.get("notes")

    if not appointment_id or not diagnosis:
        return jsonify({"success": False, "msg": "appointment_id and diagnosis required"}), 400

    appt = Appointment.query.get(appointment_id)
    if not appt:
        return jsonify({"success": False, "msg": "Appointment not found"}), 404
    if appt.doctor_id != doctor.id:
        return jsonify({"success": False, "msg": "Forbidden - not your appointment"}), 403

    # create treatment
    treatment = Treatment(appointment_id=appt.id, diagnosis=diagnosis, prescription=prescription, notes=notes)
    db.session.add(treatment)
    appt.status = AppointmentStatus.COMPLETED
    db.session.commit()

    return jsonify({"success": True, "treatment_id": treatment.id, "appointment_id": appt.id})


@doctor_bp.route("/availability/update", methods=["PUT"])
@doctor_required
def update_availability():
    doctor = _get_current_doctor()
    if not doctor:
        return jsonify({"success": False, "msg": "Doctor profile not found"}), 404

    data = request.get_json() or {}
    availability = data.get("availability")
    if not isinstance(availability, dict):
        return jsonify({"success": False, "msg": "availability must be a dict of date->slots"}), 400

    doctor.availability = availability
    db.session.commit()
    return jsonify({"success": True, "msg": "Availability updated"})


@doctor_bp.route("/patient/<int:patient_id>/history", methods=["GET"])
@doctor_required
def patient_history(patient_id):
    # allow doctor to view patient history
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({"success": False, "msg": "Patient not found"}), 404

    appts = (
        Appointment.query.filter_by(patient_id=patient.id)
        .order_by(Appointment.date.desc())
        .all()
    )

    history = []
    for a in appts:
        tr = a.treatment
        history.append(
            {
                "date": a.date.isoformat() if a.date else None,
                "diagnosis": tr.diagnosis if tr else None,
                "prescription": tr.prescription if tr else None,
                "notes": tr.notes if tr else None,
                "status": a.status.name if a.status else None,
            }
        )

    return jsonify({"patient": patient.name, "history": history})
