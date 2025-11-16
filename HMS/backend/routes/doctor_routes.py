from flask import Blueprint, jsonify

doctor_bp = Blueprint('doctor', __name__)

@doctor_bp.route('/')
def list_doctors():
    return jsonify({'doctors': []})
