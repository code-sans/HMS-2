from flask import Blueprint, jsonify

appointment_bp = Blueprint('appointment', __name__)

@appointment_bp.route('/')
def list_appointments():
    return jsonify({'appointments': []})
