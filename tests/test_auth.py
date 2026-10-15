import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


def test_auth_config():
    response = client.get("/api/auth/config")
    assert response.status_code == 200
    data = response.json()
    assert "google_client_id" in data
    assert "app_name" in data


def test_login_page_renders():
    response = client.get("/login", follow_redirects=False)
    assert response.status_code == 200
    assert "CO-PO Mapping Agent" in response.text
    assert "Sign in with Google" in response.text
    assert "Demo Login" in response.text
    assert "glass-card" in response.text


def test_unauthenticated_home_redirects_to_login():
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"


def test_demo_login_and_session_flow():
    # 1. Login with demo faculty profile
    payload = {
        "email": "atharv@college.edu.in",
        "name": "Dr. Atharv Kulkarni",
        "role": "Head of Department (E&TC)",
    }
    login_resp = client.post("/api/auth/demo-login", json=payload)
    assert login_resp.status_code == 200
    res_data = login_resp.json()
    assert res_data["success"] is True
    assert res_data["user"]["email"] == "atharv@college.edu.in"
    assert "auth_session" in login_resp.cookies

    # 2. Check /api/auth/me with the session cookie
    me_resp = client.get("/api/auth/me", cookies=login_resp.cookies)
    assert me_resp.status_code == 200
    me_data = me_resp.json()
    assert me_data["authenticated"] is True
    assert me_data["user"]["name"] == "Dr. Atharv Kulkarni"

    # 3. Access home page with session cookie
    home_resp = client.get("/", cookies=login_resp.cookies, follow_redirects=False)
    assert home_resp.status_code == 200
    assert "CO-PO Mapping Agent" in home_resp.text

    # 4. Logout
    logout_resp = client.post("/api/auth/logout", cookies=login_resp.cookies)
    assert logout_resp.status_code == 200
    assert logout_resp.json()["success"] is True


def test_guest_bypass_query():
    # Allows guest access if ?guest=1 is supplied
    resp = client.get("/?guest=1", follow_redirects=False)
    assert resp.status_code == 200
    assert "CO-PO Mapping Agent" in resp.text


def test_get_logout_redirects():
    resp = client.get("/logout", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/login"
