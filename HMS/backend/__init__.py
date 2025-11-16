from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

# Package-level shared extensions so other modules can import `from backend import db`
# and reuse the same SQLAlchemy instance and login manager.
db = SQLAlchemy()
login_manager = LoginManager()

__all__ = ["db", "login_manager"]
