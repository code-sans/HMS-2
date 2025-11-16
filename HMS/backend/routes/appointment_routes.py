from flask import Blueprint, jsonify

from .auth import login_required

appointment_bp = Blueprint('appointment', __name__)


@appointment_bp.route('/')
@login_required
def list_appointments():
    # Example protected endpoint - any authenticated user can view appointments
    return jsonify({'appointments': []})
