from flask import Blueprint, request, jsonify
from sqlalchemy import func, or_
from werkzeug.security import generate_password_hash
import secrets

from .. import db
from ..models.app import (
    User,
    Doctor,
    Patient,
    Appointment,
    Specialization,
    RoleType,
    AppointmentStatus,
)
from .auth import admin_required
from ..cache import invalidate_pattern, delete_cache

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/dashboard", methods=["GET"])
@admin_required
def dashboard():
    # totals
    total_patients = db.session.query(func.count(Patient.id)).scalar() or 0
    total_doctors = db.session.query(func.count(Doctor.id)).scalar() or 0

    # appointments breakdown
    total_appointments = db.session.query(func.count(Appointment.id)).scalar() or 0
    upcoming = (
        db.session.query(func.count(Appointment.id))
        .filter(Appointment.status == AppointmentStatus.BOOKED)
        .scalar()
        or 0
    )
    completed = (
        db.session.query(func.count(Appointment.id))
        .filter(Appointment.status == AppointmentStatus.COMPLETED)
        .scalar()
        or 0
    )
    cancelled = (
        db.session.query(func.count(Appointment.id))
        .filter(Appointment.status == AppointmentStatus.CANCELLED)
        .scalar()
        or 0
    )

    return jsonify(
        {
            "total_patients": total_patients,
            "total_doctors": total_doctors,
            "appointments": {
                "total": total_appointments,
                "upcoming": upcoming,
                "completed": completed,
                "cancelled": cancelled,
            },
        }
    )


# --------------------
# Manage Doctors
# --------------------
@admin_bp.route("/doctors/add", methods=["POST"])
@admin_required
def add_doctor():
    data = request.get_json() or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    specialization_id = data.get("specialization_id")
    availability = data.get("availability")
    experience = data.get("experience")
    contact = data.get("contact")

    if not name or not email or not specialization_id:
        return (
            jsonify({"success": False, "msg": "name, email and specialization_id are required"}),
            400,
        )

    # unique email/username enforcement
    if User.query.filter(or_(User.email == email, User.username == email.split("@")[0])).first():
        return jsonify({"success": False, "msg": "email/username already exists"}), 400

    # create user with generated password
    plain_password = secrets.token_urlsafe(8)
    password_hash = generate_password_hash(plain_password)

    user = User(username=email.split("@")[0], email=email, password_hash=password_hash, role=RoleType.DOCTOR)
    db.session.add(user)
    db.session.flush()  # get user.id

    doctor = Doctor(
        user_id=user.id,
        name=name,
        specialization_id=specialization_id,
        availability=availability,
        experience_years=experience,
        contact=contact,
    )
    db.session.add(doctor)
    db.session.commit()

    # Invalidate doctor search caches so new doctor appears in search results
    try:
        invalidate_pattern("doctor_search:*")
    except Exception:
        pass

    return (
        jsonify(
            {
                "success": True,
                "msg": "Doctor created",
                "doctor_id": doctor.id,
                "user_id": user.id,
                "temp_password": plain_password,
            }
        ),
        201,
    )


@admin_bp.route("/doctors/<int:doctor_id>/update", methods=["PUT"])
@admin_required
def update_doctor(doctor_id):
    data = request.get_json() or {}
    doctor = Doctor.query.get(doctor_id)
    if not doctor:
        return jsonify({"success": False, "msg": "Doctor not found"}), 404

    # allowed updates
    if "specialization_id" in data:
        doctor.specialization_id = data.get("specialization_id")
    if "availability" in data:
        doctor.availability = data.get("availability")
    if "experience" in data:
        doctor.experience_years = data.get("experience")
    if "status" in data:
        # Accept string or enum
        status_val = data.get("status")
        try:
            from ..models.app import DoctorStatus

            if isinstance(status_val, str):
                doctor.status = DoctorStatus(status_val)
            else:
                doctor.status = status_val
        except Exception:
            return jsonify({"success": False, "msg": "Invalid status value"}), 400
    if "contact" in data:
        doctor.contact = data.get("contact")
    if "name" in data:
        doctor.name = data.get("name")

    db.session.commit()
    # Invalidate doctor search caches to refresh search results after update
    try:
        invalidate_pattern("doctor_search:*")
    except Exception:
        pass

    # If specialization changed, we may need to refresh cached departments/specializations
    if "specialization_id" in data:
        try:
            delete_cache("departments_list")
        except Exception:
            pass

    return jsonify({"success": True, "msg": "Doctor updated", "doctor_id": doctor.id})


@admin_bp.route("/doctors/search", methods=["GET"])
@admin_required
def search_doctors():
    query = (request.args.get("query") or "").strip()
    if not query:
        return jsonify({"success": True, "doctors": []})

    # search by name or specialization name
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
            "experience_years": d.experience_years,
            "status": d.status.name if d.status else None,
        }
        for d in doctors
    ]

    return jsonify({"success": True, "doctors": result})


# --------------------
# Manage Patients
# --------------------
@admin_bp.route("/patients/search", methods=["GET"])
@admin_required
def search_patients():
    query = (request.args.get("query") or "").strip()
    if not query:
        return jsonify({"success": True, "patients": []})

    patients = (
        Patient.query.filter(
            or_(
                Patient.name.ilike(f"%{query}%"),
                func.cast(Patient.id, db.String).ilike(f"%{query}%"),
                Patient.contact.ilike(f"%{query}%"),
            )
        )
        .all()
    )

    result = [
        {"id": p.id, "name": p.name, "contact": p.contact, "status": p.status.name}
        for p in patients
    ]

    return jsonify({"success": True, "patients": result})


@admin_bp.route("/patients/<int:patient_id>/blacklist", methods=["PUT"])
@admin_required
def blacklist_patient(patient_id):
    patient = Patient.query.get(patient_id)
    if not patient:
        return jsonify({"success": False, "msg": "Patient not found"}), 404

    from ..models.app import PatientStatus

    patient.status = PatientStatus.BLACKLISTED
    db.session.commit()
    return jsonify({"success": True, "msg": "Patient blacklisted", "patient_id": patient.id})


# --------------------
# Appointments
# --------------------
@admin_bp.route("/appointments", methods=["GET"])
@admin_required
def list_appointments():
    appointments = (
        db.session.query(Appointment)
        .join(Doctor, Appointment.doctor_id == Doctor.id)
        .join(Patient, Appointment.patient_id == Patient.id)
        .all()
    )

    result = []
    for a in appointments:
        # resolve names
        patient_name = a.patient.name if a.patient else None
        doctor_name = a.doctor.name if a.doctor else None
        result.append(
            {
                "id": a.id,
                "patient_name": patient_name,
                "doctor_name": doctor_name,
                "date": a.date.isoformat() if a.date else None,
                "time": a.time.isoformat() if a.time else None,
                "status": a.status.name if a.status else None,
            }
        )

    return jsonify({"success": True, "appointments": result})


@admin_bp.route("/appointments/<int:appointment_id>/status", methods=["PUT"])
@admin_required
def update_appointment_status(appointment_id):
    data = request.get_json() or {}
    new_status = (data.get("status") or "").strip()
    if not new_status:
        return jsonify({"success": False, "msg": "status is required"}), 400

    appt = Appointment.query.get(appointment_id)
    if not appt:
        return jsonify({"success": False, "msg": "Appointment not found"}), 404

    # allowed transitions
    cur = appt.status
    from ..models.app import AppointmentStatus

    # If stored as Enum member, get name or value
    cur_name = cur.name if hasattr(cur, "name") else str(cur)
    try:
        new_enum = AppointmentStatus(new_status)
    except Exception:
        # try by name (case-insensitive)
        try:
            new_enum = AppointmentStatus[new_status.upper()]
        except Exception:
            return jsonify({"success": False, "msg": "Invalid status"}), 400

    # enforce transitions
    if cur == AppointmentStatus.BOOKED:
        if new_enum in (AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED):
            appt.status = new_enum
            db.session.commit()
            return jsonify({"success": True, "msg": "Appointment status updated"})
        else:
            return jsonify({"success": False, "msg": "Invalid transition from Booked"}), 400
    elif cur in (AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED):
        return jsonify({"success": False, "msg": "Cannot change status once Completed/Cancelled"}), 400
    else:
        return jsonify({"success": False, "msg": "Unknown current status"}), 400