from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    verify_jwt_in_request,
    jwt_required,
)
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

from .. import db
from ..models.app import User, Patient, RoleType

auth_bp = Blueprint("auth", __name__)

# -------------------------
# RBAC decorators
# -------------------------

def role_required(role_name):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            # Ensure a valid JWT exists
            try:
                verify_jwt_in_request()
            except Exception as e:
                return jsonify({"success": False, "msg": "Missing or invalid token"}), 401

            claims = get_jwt()
            role = claims.get("role")
            if not role or role.lower() != role_name.lower():
                return jsonify({"success": False, "msg": "Forbidden - insufficient privileges"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator


admin_required = role_required("admin")
doctor_required = role_required("doctor")
patient_required = role_required("patient")

# For convenience, expose a login_required alias
login_required = jwt_required()


# -------------------------
# Auth endpoints
# -------------------------
@auth_bp.route("/register", methods=["POST"])
def register():
    """Patient self-registration endpoint.

    Expected JSON body: {username, email, password, contact}
    """
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password")
    contact = data.get("contact")

    if not username or not email or not password:
        return jsonify({"success": False, "msg": "username, email and password are required"}), 400

    # Unique username/email enforcement
    if User.query.filter((User.username == username) | (User.email == email)).first():
        return (
            jsonify({"success": False, "msg": "username or email already in use"}),
            400,
        )

    password_hash = generate_password_hash(password)

    user = User(username=username, email=email, password_hash=password_hash, role=RoleType.PATIENT)
    db.session.add(user)
    db.session.commit()

    # create a patient profile
    patient = Patient(user_id=user.id, name=username, contact=contact)
    db.session.add(patient)
    db.session.commit()

    return jsonify({"success": True, "msg": "Patient registered successfully"}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    """Login endpoint. Accepts username or email and password.

    Expected JSON: { identifier (username or email), password }
    Returns: { success, role, access_token, redirect }
    """
    data = request.get_json() or {}
    identifier = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password")

    if not identifier or not password:
        return jsonify({"success": False, "msg": "identifier and password required"}), 400

    # Find user by username or email
    user = User.query.filter((User.username == identifier) | (User.email == identifier.lower())).first()
    if not user:
        return jsonify({"success": False, "msg": "Invalid credentials"}), 401

    if not check_password_hash(user.password_hash, password):
        return jsonify({"success": False, "msg": "Invalid credentials"}), 401

    # issue JWT with role claim
    role_value = user.role.value if hasattr(user.role, "value") else str(user.role)
    additional_claims = {"role": role_value}
    access_token = create_access_token(identity=user.id, additional_claims=additional_claims)

    # redirect mapping
    role_lower = role_value.lower()
    redirect_map = {
        "admin": "/admin/dashboard",
        "doctor": "/doctor/dashboard",
        "patient": "/patient/dashboard",
    }
    redirect = redirect_map.get(role_lower, "/")

    return (
        jsonify(
            {
                "success": True,
                "role": role_lower,
                "access_token": access_token,
                "redirect": redirect,
            }
        ),
        200,
    )


# Example protected route per-role (usage examples)
@auth_bp.route("/protected-admin", methods=["GET"])
@admin_required
def protected_admin():
    return jsonify({"success": True, "msg": "Hello admin"})


@auth_bp.route("/protected-doctor", methods=["GET"])
@doctor_required
def protected_doctor():
    return jsonify({"success": True, "msg": "Hello doctor"})


@auth_bp.route("/protected-patient", methods=["GET"])
@patient_required
def protected_patient():
    return jsonify({"success": True, "msg": "Hello patient"})
