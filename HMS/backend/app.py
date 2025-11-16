from flask import Flask
from flask_cors import CORS

# Package-level extensions (db, login_manager) exposed in this package's __init__
from . import db, login_manager


def create_app():
    app = Flask(__name__)
    CORS(app)

    # Configuration
    app.config['SECRET_KEY'] = 'your-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hms_v2.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Import models to register with SQLAlchemy
    from .models import app as models  # important

    # Register routes (relative imports so module works when run as package)
    from .routes.auth_routes import auth_bp
    from .routes.doctor_routes import doctor_bp
    from .routes.patient_routes import patient_bp
    from .routes.appointment_routes import appointment_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(doctor_bp, url_prefix="/doctor")
    app.register_blueprint(patient_bp, url_prefix="/patient")
    app.register_blueprint(appointment_bp, url_prefix="/appointment")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
