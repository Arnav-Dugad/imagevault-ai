import pytest

from tests.conftest import create_user


@pytest.mark.asyncio
async def test_register_login_and_current_user(client):
    registered = await create_user(client)
    assert registered["user"]["email"] == "student@example.com"
    assert registered["access_token"]

    login = await client.post(
        "/api/auth/login",
        json={"email": "student@example.com", "password": "strong-password"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    current = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert current.status_code == 200
    assert current.json()["display_name"] == "Test Student"


@pytest.mark.asyncio
async def test_duplicate_email_and_bad_password_are_rejected(client):
    await create_user(client)
    duplicate = await client.post(
        "/api/auth/register",
        json={"email": "student@example.com", "display_name": "Other", "password": "another-password"},
    )
    assert duplicate.status_code == 409
    bad_login = await client.post(
        "/api/auth/login",
        json={"email": "student@example.com", "password": "wrong-password"},
    )
    assert bad_login.status_code == 401


@pytest.mark.asyncio
async def test_protected_route_requires_token(client):
    response = await client.get("/api/images")
    assert response.status_code == 401



async def test_closed_registration_still_allows_login(client, monkeypatch):
    from app.core.config import get_settings
    from tests.conftest import create_user

    await create_user(client)
    monkeypatch.setattr(get_settings(), "registration_enabled", False)
    blocked = await client.post('/api/auth/register', json={
        'email': 'new@example.com', 'display_name': 'New User', 'password': 'strong-password',
    })
    assert blocked.status_code == 403
    login = await client.post('/api/auth/login', json={
        'email': 'student@example.com', 'password': 'strong-password',
    })
    assert login.status_code == 200
