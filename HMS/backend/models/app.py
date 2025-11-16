"""Backend SQLAlchemy models."""

from datetime import datetime
import enum

# import the package-level db instance
from .. import db
from sqlalchemy.orm import validates


# -----------------------------
# ENUM TYPES
# -----------------------------
class RoleType(enum.Enum):
    ADMIN = "Admin"
    DOCTOR = "Doctor"
    PATIENT = "Patient"


class DoctorStatus(enum.Enum):
    ACTIVE = "active"
    BLACKLISTED = "blacklisted"


class PatientStatus(enum.Enum):
    ACTIVE = "active"
    BLACKLISTED = "blacklisted"


class AppointmentStatus(enum.Enum):
    BOOKED = "Booked"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


# -----------------------------
# BASE MIXIN FOR COMMON FIELDS
# -----------------------------
class TimestampMixin(object):
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


# -----------------------------
# USER MODEL
# -----------------------------
class User(TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    # Store hashed password here (recommended instead of plain text)
    password_hash = db.Column(db.String(255), nullable=False)

    role = db.Column(db.Enum(RoleType), nullable=False)

    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    contact = db.Column(db.String(20), nullable=True)

    # optional extras
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    # 1-1 relationships with Doctor / Patient profile
    doctor_profile = db.relationship(
        "Doctor",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    patient_profile = db.relationship(
        "Patient",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<User {self.username} ({self.role.value})>"

    @validates("role")
    def validate_role(self, key, value):
        # Accept either an Enum member or a string value.
        if isinstance(value, RoleType):
            return value
        try:
            return RoleType(value)
        except Exception:
            raise ValueError("Invalid role type")


# -----------------------------
# DEPARTMENT MODEL
# -----------------------------
class Department(TimestampMixin, db.Model):
    """
    High-level department (e.g., Cardiology, Neurology).
    """

    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)

    specializations = db.relationship(
        "Specialization",
        back_populates="department",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Department {self.name}>"


# -----------------------------
# SPECIALIZATION MODEL
# -----------------------------
class Specialization(TimestampMixin, db.Model):
    """
    More granular specialization under a department
    (e.g., Interventional Cardiology under Cardiology).
    """

    __tablename__ = "specializations"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)

    department_id = db.Column(
        db.Integer,
        db.ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    department = db.relationship("Department", back_populates="specializations")

    doctors = db.relationship(
        "Doctor",
        back_populates="specialization",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Specialization {self.name}>"


# -----------------------------
# DOCTOR MODEL
# -----------------------------
class Doctor(TimestampMixin, db.Model):
    __tablename__ = "doctors"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    name = db.Column(db.String(120), nullable=False)

    specialization_id = db.Column(
        db.Integer,
        db.ForeignKey("specializations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # JSON field to store availability for next 7 days
    # Example structure: [{"date": "2025-11-16", "slots": ["10:00", "10:30", ...]}, ...]
    availability = db.Column(db.JSON, nullable=True)

    experience_years = db.Column(db.Integer, nullable=True)
    status = db.Column(db.Enum(DoctorStatus), default=DoctorStatus.ACTIVE, nullable=False)

    user = db.relationship("User", back_populates="doctor_profile")
    specialization = db.relationship("Specialization", back_populates="doctors")
    contact = db.Column(db.String(20), nullable=True)

    appointments = db.relationship(
        "Appointment",
        back_populates="doctor",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Doctor {self.name}>"

    @validates("status")
    def validate_status(self, key, value):
        if isinstance(value, DoctorStatus):
            return value
        try:
            return DoctorStatus(value)
        except Exception:
            raise ValueError("Invalid doctor status")


# -----------------------------
# PATIENT MODEL
# -----------------------------
class Patient(TimestampMixin, db.Model):
    __tablename__ = "patients"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    name = db.Column(db.String(120), nullable=False)
    age = db.Column(db.Integer, nullable=True)
    gender = db.Column(db.String(20), nullable=True)

    address = db.Column(db.Text, nullable=True)
    contact = db.Column(db.String(20), nullable=True)

    status = db.Column(db.Enum(PatientStatus), default=PatientStatus.ACTIVE, nullable=False)

    # optional extra
    blood_group = db.Column(db.String(5), nullable=True)

    user = db.relationship("User", back_populates="patient_profile")

    appointments = db.relationship(
        "Appointment",
        back_populates="patient",
        cascade="all, delete-orphan",
        lazy="dynamic",
    )

    def __repr__(self):
        return f"<Patient {self.name}>"

    @validates("status")
    def validate_status(self, key, value):
        if isinstance(value, PatientStatus):
            return value
        try:
            return PatientStatus(value)
        except Exception:
            raise ValueError("Invalid patient status")


# -----------------------------
# APPOINTMENT MODEL
# -----------------------------
class Appointment(TimestampMixin, db.Model):
    __tablename__ = "appointments"

    id = db.Column(db.Integer, primary_key=True)

    doctor_id = db.Column(
        db.Integer,
        db.ForeignKey("doctors.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id = db.Column(
        db.Integer,
        db.ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    date = db.Column(db.Date, nullable=False, index=True)
    time = db.Column(db.Time, nullable=False)

    status = db.Column(
        db.Enum(AppointmentStatus),
        default=AppointmentStatus.BOOKED,
        nullable=False,
    )

    # Prevent double booking of same doctor at same date+time
    __table_args__ = (
        db.UniqueConstraint(
            "doctor_id", "date", "time", name="uq_appointment_doctor_datetime"
        ),
    )

    doctor = db.relationship("Doctor", back_populates="appointments")
    patient = db.relationship("Patient", back_populates="appointments")

    # One-to-one relationship with Treatment
    treatment = db.relationship(
        "Treatment",
        back_populates="appointment",
        uselist=False,
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return (
            f"<Appointment {self.id} Doctor={self.doctor_id} "
            f"Patient={self.patient_id} {self.date} {self.time}>"
        )

    @validates("status")
    def validate_status(self, key, value):
        if isinstance(value, AppointmentStatus):
            return value
        try:
            return AppointmentStatus(value)
        except Exception:
            raise ValueError("Invalid appointment status")


# -----------------------------
# TREATMENT MODEL
# -----------------------------
class Treatment(TimestampMixin, db.Model):
    __tablename__ = "treatments"

    id = db.Column(db.Integer, primary_key=True)

    appointment_id = db.Column(
        db.Integer,
        db.ForeignKey("appointments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,   # ensure 1-1 mapping: one Treatment per Appointment
        index=True,
    )

    diagnosis = db.Column(db.Text, nullable=True)
    prescription = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)

    appointment = db.relationship("Appointment", back_populates="treatment")

    def __repr__(self):
        return f"<Treatment {self.id} for Appointment {self.appointment_id}>"


# -----------------------------
# Helper functions for appointments
# -----------------------------
def is_slot_available(doctor_id, date_obj, time_obj, appointment_id=None):
    """Return True if the doctor has no appointment at the given date/time.

    If appointment_id is provided, exclude that appointment (useful for rescheduling).
    """
    q = Appointment.query.filter_by(doctor_id=doctor_id, date=date_obj, time=time_obj)
    if appointment_id:
        q = q.filter(Appointment.id != appointment_id)
    return q.first() is None


def update_appointment_status(appointment_id, new_status):
    """Validate and update appointment status according to allowed transitions.

    Raises ValueError on invalid transitions or missing Treatment when marking Completed.
    Returns the updated Appointment object on success.
    """
    appt = Appointment.query.get(appointment_id)
    if not appt:
        raise ValueError("Appointment not found")

    # normalize new_status into AppointmentStatus
    if isinstance(new_status, AppointmentStatus):
        new_enum = new_status
    else:
        try:
            new_enum = AppointmentStatus(new_status)
        except Exception:
            try:
                new_enum = AppointmentStatus[new_status.upper()]
            except Exception:
                raise ValueError("Invalid status")

    cur = appt.status
    if cur == AppointmentStatus.BOOKED:
        if new_enum in (AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED):
            if new_enum == AppointmentStatus.COMPLETED and not appt.treatment:
                raise ValueError("Cannot mark Completed without existing Treatment record")
            appt.status = new_enum
            db.session.commit()
            return appt
        else:
            raise ValueError("Invalid transition from Booked")
    elif cur in (AppointmentStatus.COMPLETED, AppointmentStatus.CANCELLED):
        raise ValueError("Cannot change status once Completed or Cancelled")
    else:
        raise ValueError("Unknown current status")


def serialize_appointment(appt):
    """Return standardized JSON shape for an Appointment."""
    treatment = None
    if appt.treatment:
        treatment = {
            "diagnosis": appt.treatment.diagnosis,
            "prescription": appt.treatment.prescription,
            "notes": appt.treatment.notes,
        }

    doctor_spec = None
    if appt.doctor and appt.doctor.specialization:
        doctor_spec = appt.doctor.specialization.name

    return {
        "id": appt.id,
        "patient": {"id": appt.patient.id, "name": appt.patient.name} if appt.patient else None,
        "doctor": {
            "id": appt.doctor.id,
            "name": appt.doctor.name,
            "specialization": doctor_spec,
        }
        if appt.doctor
        else None,
        "date": appt.date.isoformat() if appt.date else None,
        "time": appt.time.isoformat() if appt.time else None,
        "status": appt.status.name if appt.status else None,
        "treatment": treatment,
    }
