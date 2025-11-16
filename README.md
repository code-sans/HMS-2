# HMS-V2 (Milestone 2) — Auth & RBAC

This repository contains a Flask backend with JWT-based authentication and role-based access control (RBAC).

Quick start

1. Create and activate a virtual environment:

```cmd
python -m venv .venv
.venv\Scripts\activate
```

2. Install dependencies:

```cmd
pip install -r requirements.txt
```

3. Initialize the database and create the default admin:

```cmd
python -m HMS.backend.init_db
```

4. Run the app:

```cmd
python -m HMS.backend.app
```

Auth endpoints

- POST /auth/register — Patient registration
  - body: {username, email, password, contact}
  - response: { success, msg }

- POST /auth/login — Login (username or email + password)
  - body: { username or email, password }
  - response: { success, role, access_token, redirect }

RBAC decorators (in `backend/routes/auth.py`):

- `admin_required`
- `doctor_required`
- `patient_required`
- `login_required` (alias to JWT login check)

Notes & recommendations

- Set a secure `JWT_SECRET_KEY` in environment or config for production.
- Use token expiry and refresh tokens for better security.
- Run tests with `pytest` (tests added as a basic smoke-test).

Commit message for milestone

`Milestone-HMS-V2 Auth-RBAC`
