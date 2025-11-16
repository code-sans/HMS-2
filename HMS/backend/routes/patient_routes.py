from flask import Blueprint, jsonify

from .auth import patient_required

patient_bp = Blueprint('patient', __name__)


@patient_bp.route('/')
@patient_required
def list_patients():
    # Example protected endpoint for patients
    return jsonify({'patients': []})
