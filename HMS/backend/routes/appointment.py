from flask import Blueprint, request, jsonify
from datetime import datetime, date

from .. import db
from ..models.app import (
    Appointment,
    Treatment,
    Patient,
    Doctor,
    AppointmentStatus,
    serialize_appointment,
    is_slot_available,
    update_appointment_status,
)
from .auth import admin_required, doctor_required, patient_required

appointment_bp = Blueprint("appointment", __name__)


def _parse_date(d):
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except Exception:
        return None


def _parse_time(t):
    try:
        return datetime.strptime(t, "%H:%M").time()
    except Exception:
        return None


# -------------------------
# Patient history
# -------------------------
@appointment_bp.route("/patient/history", methods=["GET"])
@patient_required
def patient_history():
    # show past appointments for the current patient
    from flask_jwt_extended import get_jwt_identity

    user_id = get_jwt_identity()
    patient = Patient.query.filter_by(user_id=user_id).first()
    if not patient:
        return jsonify({"success": False, "msg": "Patient profile not found"}), 404

    today = date.today()
    appts = (
        Appointment.query.filter(Appointment.patient_id == patient.id)
        .filter((Appointment.date < today) | (Appointment.status != AppointmentStatus.BOOKED))
        .order_by(Appointment.date.desc(), Appointment.time.desc())
        .all()
    )

    result = [serialize_appointment(a) for a in appts]
    return jsonify({"success": True, "history": result})


# -------------------------
# Doctor view of patient visits
# -------------------------
@appointment_bp.route("/doctor/patient/<int:patient_id>", methods=["GET"])
@doctor_required
def doctor_view_patient(patient_id):
    from flask_jwt_extended import get_jwt_identity

    user_id = get_jwt_identity()
    doctor = Doctor.query.filter_by(user_id=user_id).first()
    if not doctor:
        return jsonify({"success": False, "msg": "Doctor profile not found"}), 404

    appts = (
        Appointment.query.filter_by(doctor_id=doctor.id, patient_id=patient_id)
        .order_by(Appointment.date.desc(), Appointment.time.desc())
        .all()
    )

    result = [serialize_appointment(a) for a in appts]
    return jsonify({"success": True, "patient_id": patient_id, "visits": result})


# -------------------------
# Admin view of all appointment history with filters
# -------------------------
@appointment_bp.route("/admin/history", methods=["GET"])
@admin_required
def admin_history():
    q = Appointment.query

    doctor_id = request.args.get("doctor_id")
    patient_id = request.args.get("patient_id")
    status = request.args.get("status")
    date_from = request.args.get("date_from")
    date_to = request.args.get("date_to")

    if doctor_id:
        q = q.filter(Appointment.doctor_id == int(doctor_id))
    if patient_id:
        q = q.filter(Appointment.patient_id == int(patient_id))
    if status:
        try:
            st = AppointmentStatus(status)
        except Exception:
            try:
                st = AppointmentStatus[status.upper()]
            except Exception:
                return jsonify({"success": False, "msg": "Invalid status filter"}), 400
        q = q.filter(Appointment.status == st)
    if date_from:
        df = _parse_date(date_from)
        if not df:
            return jsonify({"success": False, "msg": "Invalid date_from"}), 400
        q = q.filter(Appointment.date >= df)
    if date_to:
        dt = _parse_date(date_to)
        if not dt:
            return jsonify({"success": False, "msg": "Invalid date_to"}), 400
        q = q.filter(Appointment.date <= dt)

    appts = q.order_by(Appointment.date.desc(), Appointment.time.desc()).all()
    result = [serialize_appointment(a) for a in appts]
    return jsonify({"success": True, "appointments": result})


# -------------------------
# Slot availability check (reusable by frontends)
# -------------------------
@appointment_bp.route("/slot_available", methods=["GET"])
def slot_available():
    doctor_id = request.args.get("doctor_id")
    date_s = request.args.get("date")
    time_s = request.args.get("time")
    if not doctor_id or not date_s or not time_s:
        return jsonify({"success": False, "msg": "doctor_id, date and time required"}), 400

    d = _parse_date(date_s)
    t = _parse_time(time_s)
    if not d or not t:
        return jsonify({"success": False, "msg": "invalid date/time format"}), 400

    available = is_slot_available(int(doctor_id), d, t)
    return jsonify({"success": True, "available": available})


# -------------------------
# Helper endpoint for updating status via API (Admin / Doctor)
# -------------------------
@appointment_bp.route("/<int:appointment_id>/status", methods=["PUT"])
def change_status(appointment_id):
    # allow admin or doctor to update statuses (doctor only if own appointment)
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    role = claims.get("role", "").lower()

    data = request.get_json() or {}
    new_status = data.get("status")
    if not new_status:
        return jsonify({"success": False, "msg": "status required"}), 400

    appt = Appointment.query.get(appointment_id)
    if not appt:
        return jsonify({"success": False, "msg": "Appointment not found"}), 404

    # doctor may only change their own appointments
    if role == "doctor":
        user_id = get_jwt()["sub"] if "sub" in get_jwt() else None
        doc = Doctor.query.filter_by(user_id=user_id).first()
        if not doc or appt.doctor_id != doc.id:
            return jsonify({"success": False, "msg": "Forbidden"}), 403

    try:
        updated = update_appointment_status(appointment_id, new_status)
    except ValueError as e:
        return jsonify({"success": False, "msg": str(e)}), 400

    return jsonify({"success": True, "appointment": serialize_appointment(updated)})
