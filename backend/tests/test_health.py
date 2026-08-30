import pytest


@pytest.mark.asyncio
async def test_liveness_does_not_depend_on_external_services(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}
