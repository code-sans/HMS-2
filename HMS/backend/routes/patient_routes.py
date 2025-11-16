from flask import Blueprint, jsonify

patient_bp = Blueprint('patient', __name__)

@patient_bp.route('/')
def list_patients():
    return jsonify({'patients': []})
