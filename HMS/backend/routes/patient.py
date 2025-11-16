from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from datetime import datetime, date
from sqlalchemy import or_

from .. import db
from ..models.app import (
    Department,
    Specialization,
    Doctor,
    Patient,
    Appointment,
    Treatment,
    AppointmentStatus,
)
from .auth import patient_required

patient_bp = Blueprint("patient", __name__)


def _get_current_patient():
    user_id = get_jwt_identity()
    if not user_id:
        return None
    return Patient.query.filter_by(user_id=user_id).first()


@patient_bp.route("/departments", methods=["GET"])
@patient_required
def list_departments():
    deps = Department.query.all()
    result = [{"id": d.id, "name": d.name} for d in deps]
    return jsonify(result)


@patient_bp.route("/doctors/availability/<int:doctor_id>", methods=["GET"])
@patient_required
def doctor_availability(doctor_id):
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({"success": False, "msg": "Doctor not found"}), 404
    return jsonify({"doctor": doctor.name, "availability": doctor.availability or {}})


@patient_bp.route("/doctors/search", methods=["GET"])
@patient_required
def search_doctors():
    query = (request.args.get("query") or "").strip()
    if not query:
        return jsonify({"success": True, "doctors": []})

    doctors = (
        db.session.query(Doctor)
        .join(Specialization, isouter=True)
        .filter(
            or_(
                Doctor.name.ilike(f"%{query}%"),
                Specialization.name.ilike(f"%{query}%"),
            )
        )
        .all()
    )

    result = [
        {
            "id": d.id,
            "name": d.name,
            "specialization_id": d.specialization_id,
            "contact": d.contact,
            "availability": d.availability or {},
        }
        for d in doctors
    ]
    return jsonify({"success": True, "doctors": result})


def _parse_date(date_str):
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except Exception:
        return None


def _parse_time(time_str):
    try:
        return datetime.strptime(time_str, "%H:%M").time()
    except Exception:
        return None


@patient_bp.route("/appointments/book", methods=["POST"])
@patient_required
def book_appointment():
    data = request.get_json() or {}
    doctor_id = data.get("doctor_id")
    date_s = data.get("date")
    time_s = data.get("time")

    if not doctor_id or not date_s or not time_s:
        return jsonify({"success": False, "msg": "doctor_id, date and time required"}), 400

    appt_date = _parse_date(date_s)
    appt_time = _parse_time(time_s)
    if not appt_date or not appt_time:
        return jsonify({"success": False, "msg": "invalid date or time format"}), 400

    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({"success": False, "msg": "Doctor not found"}), 404

    # check availability
    availability = doctor.availability or {}
    slots = availability.get(appt_date.isoformat(), [])
    if time_s not in slots:
        return jsonify({"success": False, "msg": "Doctor not available at requested slot"}), 400

    # prevent double booking for doctor
    exists = (
        Appointment.query.filter_by(doctor_id=doctor_id, date=appt_date, time=appt_time).first()
        is not None
    )
    if exists:
        return jsonify({"success": False, "msg": "Slot already booked"}), 409

    patient = _get_current_patient()
    if not patient:
        return jsonify({"success": False, "msg": "Patient profile not found"}), 404

    appt = Appointment(doctor_id=doctor_id, patient_id=patient.id, date=appt_date, time=appt_time)
    db.session.add(appt)
    db.session.commit()

    return (
        jsonify({
            "success": True,
            "msg": "Appointment booked",
            "appointment_id": appt.id,
            "date": appt.date.isoformat(),
            "time": appt.time.isoformat(),
        }),
        201,
    )


@patient_bp.route("/appointments/<int:appointment_id>/reschedule", methods=["PUT"])
@patient_required
def reschedule_appointment(appointment_id):
    data = request.get_json() or {}
    new_date_s = data.get("new_date")
    new_time_s = data.get("new_time")
    if not new_date_s or not new_time_s:
        return jsonify({"success": False, "msg": "new_date and new_time required"}), 400

    new_date = _parse_date(new_date_s)
    new_time = _parse_time(new_time_s)
    if not new_date or not new_time:
        return jsonify({"success": False, "msg": "invalid date/time format"}), 400

    appt = Appointment.query.get(appointment_id)
    if not appt:
        return jsonify({"success": False, "msg": "Appointment not found"}), 404

    patient = _get_current_patient()
    if not patient or appt.patient_id != patient.id:
        return jsonify({"success": False, "msg": "Forbidden"}), 403

    if appt.status != AppointmentStatus.BOOKED:
        return jsonify({"success": False, "msg": "Only Booked appointments can be rescheduled"}), 400

    doctor = Doctor.query.get(appt.doctor_id)
    availability = doctor.availability or {}
    if new_time_s not in availability.get(new_date.isoformat(), []):
        return jsonify({"success": False, "msg": "Doctor not available at requested slot"}), 400

    # check double booking
    conflict = (
        Appointment.query.filter_by(doctor_id=doctor.id, date=new_date, time=new_time)
        .filter(Appointment.id != appt.id)
        .first()
    )
    if conflict:
        return jsonify({"success": False, "msg": "Requested slot already booked"}), 409

    appt.date = new_date
    appt.time = new_time
    db.session.commit()

    return jsonify({"success": True, "msg": "Appointment rescheduled", "appointment_id": appt.id})


@patient_bp.route("/appointments/<int:appointment_id>/cancel", methods=["PUT"])
@patient_required
def cancel_appointment(appointment_id):
    appt = Appointment.query.get(appointment_id)
    if not appt:
        return jsonify({"success": False, "msg": "Appointment not found"}), 404

    patient = _get_current_patient()
    if not patient or appt.patient_id != patient.id:
        return jsonify({"success": False, "msg": "Forbidden"}), 403

    if appt.status in (AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED):
        return jsonify({"success": False, "msg": "Cannot cancel Completed or Cancelled appointments"}), 400

    appt.status = AppointmentStatus.CANCELLED
    db.session.commit()
    return jsonify({"success": True, "msg": "Appointment cancelled", "appointment_id": appt.id})


@patient_bp.route("/appointments/upcoming", methods=["GET"])
@patient_required
def upcoming_appointments():
    patient = _get_current_patient()
    if not patient:
        return jsonify({"success": False, "msg": "Patient profile not found"}), 404

    today = date.today()
    appts = (
        Appointment.query.filter_by(patient_id=patient.id)
        .filter(Appointment.date >= today)
        .order_by(Appointment.date, Appointment.time)
        .all()
    )

    result = [
        {
            "id": a.id,
            "doctor": a.doctor.name if a.doctor else None,
            "date": a.date.isoformat() if a.date else None,
            "time": a.time.isoformat() if a.time else None,
            "status": a.status.name if a.status else None,
        }
        for a in appts
    ]

    return jsonify({"success": True, "upcoming": result})


@patient_bp.route("/appointments/history", methods=["GET"])
@patient_required
def appointment_history():
    patient = _get_current_patient()
    if not patient:
        return jsonify({"success": False, "msg": "Patient profile not found"}), 404

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
                "doctor": a.doctor.name if a.doctor else None,
                "diagnosis": tr.diagnosis if tr else None,
                "prescription": tr.prescription if tr else None,
                "notes": tr.notes if tr else None,
                "status": a.status.name if a.status else None,
            }
        )

    return jsonify({"success": True, "history": history})


@patient_bp.route("/profile/update", methods=["PUT"])
@patient_required
def update_profile():
    patient = _get_current_patient()
    if not patient:
        return jsonify({"success": False, "msg": "Patient profile not found"}), 404

    data = request.get_json() or {}
    allowed = ["name", "age", "gender", "address", "contact"]
    changed = False
    for key in allowed:
        if key in data:
            setattr(patient, key, data.get(key))
            changed = True

    if changed:
        db.session.commit()
        return jsonify({"success": True, "msg": "Profile updated"})
    else:
        return jsonify({"success": False, "msg": "No valid fields provided"}), 400
