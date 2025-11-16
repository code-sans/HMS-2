from flask import Flask
from flask_cors import CORS

# Package-level extensions (db, login_manager) exposed in this package's __init__
from . import db, login_manager

from flask_jwt_extended import JWTManager

# JWT manager instance (initialized per-app)
jwt = JWTManager()


def create_app(config: dict = None):
    """Create and configure the Flask application.

    Optional `config` dict may be provided for test overrides (e.g., in-memory DB).
    """
    app = Flask(__name__)
    if config:
        app.config.update(config)
    CORS(app)

    # Configuration
    app.config['SECRET_KEY'] = 'your-secret-key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///hms_v2.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    # JWT configuration
    app.config.setdefault("JWT_SECRET_KEY", "change-this-secret")
    app.config.setdefault("JWT_ACCESS_TOKEN_EXPIRES", False)  # tokens won't expire for now (adjust in prod)

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    jwt.init_app(app)

    # Flask-Login user loader
    @login_manager.user_loader
    def load_user(user_id):
        try:
            # import lazily to avoid circular imports at module import time
            from .models.app import User

            return User.query.get(int(user_id))
        except Exception:
            return None

    # Import models to register with SQLAlchemy
    from .models import app as models  # important

    # Register routes (relative imports so module works when run as package)
    # Register auth blueprint (new auth implementation)
    from .routes.auth import auth_bp
    # Use new doctor blueprint for doctor-facing APIs
    from .routes.doctor import doctor_bp
    from .routes.patient import patient_bp
    from .routes.appointment_routes import appointment_bp
    from .routes.admin import admin_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(doctor_bp, url_prefix="/doctor")
    app.register_blueprint(patient_bp, url_prefix="/patient")
    app.register_blueprint(appointment_bp, url_prefix="/appointment")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
