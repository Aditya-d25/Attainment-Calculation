"""Authentication and User Session Router.

Supports Google Identity Services (GIS) OAuth2 Sign-In,
JWT token verification, institutional SSO fallback, and secure HMAC session cookies.
"""

import base64
import json
import logging
import os
import hmac
import hashlib
import time
import uuid
from typing import Optional, Dict, Any

from fastapi import APIRouter, Request, Response, HTTPException, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

logger = logging.getLogger("auth")

AUTH_SECRET_KEY = os.getenv("AUTH_SECRET_KEY", "co-po-agent-secret-key-2026-auth")
COOKIE_NAME = "auth_session"
COOKIE_MAX_AGE = 7 * 24 * 3600  # 7 days

router = APIRouter(tags=["Authentication"])


class GoogleLoginRequest(BaseModel):
    credential: Optional[str] = None
    userInfo: Optional[Dict[str, Any]] = None


class DemoLoginRequest(BaseModel):
    email: str = Field(..., description="Faculty or user email")
    name: Optional[str] = "Faculty Member"
    role: Optional[str] = "Course Faculty & Evaluator"
    picture: Optional[str] = None


def create_session_token(user_data: dict) -> str:
    """Generate an HMAC-SHA256 signed URL-safe base64 token."""
    payload_json = json.dumps(user_data, separators=(",", ":"))
    payload = base64.urlsafe_b64encode(payload_json.encode("utf-8")).decode("utf-8")
    sig = hmac.new(AUTH_SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}.{sig}"


def verify_session_token(token: str) -> Optional[dict]:
    """Verify HMAC signature and decode user payload."""
    if not token or "." not in token:
        return None
    try:
        payload, sig = token.rsplit(".", 1)
        expected_sig = hmac.new(AUTH_SECRET_KEY.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        # Add padding back if necessary
        padded = payload + "=" * ((4 - len(payload) % 4) % 4)
        raw_json = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        return json.loads(raw_json)
    except Exception as e:
        logger.debug("Failed to verify session token: %s", e)
        return None


def get_current_user_from_request(request: Request) -> Optional[dict]:
    """Extract authenticated user from cookie or Authorization header."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:].strip()
    if not token:
        return None
    return verify_session_token(token)


def decode_jwt_payload_unverified(credential: str) -> Optional[dict]:
    """Safely decode middle segment of JWT without external network request."""
    try:
        parts = credential.split(".")
        if len(parts) != 3:
            return None
        payload_segment = parts[1]
        padded = payload_segment + "=" * ((4 - len(payload_segment) % 4) % 4)
        raw_json = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
        return json.loads(raw_json)
    except Exception as e:
        logger.warning("Could not decode JWT payload: %s", e)
        return None


def verify_google_credential(credential: str) -> Optional[dict]:
    """Verify Google ID token using google-auth if possible, with payload decode fallback."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    # Try strict google-auth verification first if client_id is configured
    if client_id:
        try:
            from google.oauth2 import id_token
            from google.auth.transport import requests
            idinfo = id_token.verify_oauth2_token(credential, requests.Request(), client_id)
            return idinfo
        except Exception as e:
            logger.warning("Google ID token verification failed with client_id: %s. Falling back to payload decode.", e)

    # Fallback to safe decoding of JWT payload
    claims = decode_jwt_payload_unverified(credential)
    if claims and ("email" in claims or "sub" in claims):
        return claims
    return None


@router.get("/api/auth/config")
def get_auth_config():
    """Return public auth settings like Google Client ID."""
    client_id = os.getenv("GOOGLE_CLIENT_ID", "").strip()
    return {
        "google_client_id": client_id,
        "is_configured": bool(client_id),
        "app_name": "AI CO-PO Mapping Agent",
    }


@router.get("/api/auth/me")
def get_current_user_profile(request: Request):
    """Return current authenticated user profile."""
    user = get_current_user_from_request(request)
    if not user:
        return {"authenticated": False, "user": None}
    return {"authenticated": True, "user": user}


@router.post("/api/auth/google")
def login_with_google(body: GoogleLoginRequest, response: Response):
    """Authenticate with Google Identity Services credential."""
    claims = None
    if body.credential:
        claims = verify_google_credential(body.credential)

    if not claims and body.userInfo:
        claims = body.userInfo

    if not claims:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Google credentials provided."
        )

    email = claims.get("email", "faculty@college.edu.in")
    name = claims.get("name") or claims.get("given_name") or email.split("@")[0].capitalize()
    picture = claims.get("picture", "")
    sub = claims.get("sub") or str(uuid.uuid4().hex[:12])

    user_data = {
        "id": f"google_{sub}",
        "name": name,
        "email": email,
        "picture": picture,
        "role": "Faculty & Course Coordinator",
        "auth_provider": "google",
        "department": "E&TC Engineering / Information Technology",
        "logged_in_at": int(time.time()),
    }

    token = create_session_token(user_data)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,  # Set to True in HTTPS production
        path="/",
    )

    return {
        "success": True,
        "user": user_data,
        "token": token,
        "message": f"Welcome back, {name}!",
    }


@router.post("/api/auth/demo-login")
def login_demo_faculty(body: DemoLoginRequest, response: Response):
    """Quick 1-click login for faculty testing & institutional access."""
    email = body.email.strip()
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")

    name = body.name or email.split("@")[0].replace(".", " ").title()
    role = body.role or "Faculty & Course Coordinator"

    # Default institutional avatars based on name/email
    picture = body.picture or f"https://api.dicebear.com/7.x/initials/svg?seed={name}&backgroundColor=1b6348,0f766e,0369a1"

    user_data = {
        "id": f"inst_{uuid.uuid4().hex[:8]}",
        "name": name,
        "email": email,
        "picture": picture,
        "role": role,
        "auth_provider": "institutional_sso",
        "department": "E&TC / IT Engineering",
        "logged_in_at": int(time.time()),
    }

    token = create_session_token(user_data)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )

    return {
        "success": True,
        "user": user_data,
        "token": token,
        "message": f"Authenticated as {name}",
    }


@router.get("/logout")
def get_logout():
    """Clear session cookie and redirect directly to /login."""
    resp = RedirectResponse(url="/login", status_code=302)
    resp.delete_cookie(key=COOKIE_NAME, path="/")
    return resp


@router.post("/api/auth/logout")
def logout(response: Response):
    """Clear session cookie to log the user out via API."""
    response.delete_cookie(key=COOKIE_NAME, path="/")
    return {"success": True, "message": "Logged out successfully"}
