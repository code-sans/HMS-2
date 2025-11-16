from flask import Blueprint, jsonify

from .auth import doctor_required

doctor_bp = Blueprint('doctor', __name__)


@doctor_bp.route('/')
@doctor_required
def list_doctors():
    # Example protected endpoint for doctors
    return jsonify({'doctors': []})
