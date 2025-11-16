from .app import create_app
from . import db
from .models.app import User, RoleType
from werkzeug.security import generate_password_hash


def create_admin(app):
    with app.app_context():
        admin = User.query.filter_by(role=RoleType.ADMIN).first()
        if admin:
            print("Admin already exists.")
            return

        admin = User(
            username="admin",
            email="admin@example.com",
            password_hash=generate_password_hash("admin123"),
            role=RoleType.ADMIN,
        )

        db.session.add(admin)
        db.session.commit()
        print("Default admin created.")


if __name__ == "__main__":
    app = create_app()
    # Ensure tables exist then create admin
    with app.app_context():
        db.create_all()
    create_admin(app)
