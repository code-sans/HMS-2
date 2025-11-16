import json

import pytest

from HMS.backend.app import create_app
from HMS.backend import db


def test_register_and_login_flow(tmp_path):
    # create app with in-memory DB
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "JWT_SECRET_KEY": "test-secret",
    })

    client = app.test_client()

    with app.app_context():
        db.create_all()

        # register
        resp = client.post(
            "/auth/register",
            data=json.dumps({
                "username": "testuser",
                "email": "testuser@example.com",
                "password": "pass123",
                "contact": "123",
            }),
            content_type="application/json",
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["success"] is True

        # login
        resp = client.post(
            "/auth/login",
            data=json.dumps({"username": "testuser", "password": "pass123"}),
            content_type="application/json",
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert "access_token" in data

        token = data["access_token"]

        # access a protected patient route
        resp = client.get("/patient/", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        pdata = resp.get_json()
        assert "patients" in pdata
