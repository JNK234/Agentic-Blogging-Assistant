import pytest
from httpx import AsyncClient, ASGITransport

@pytest.mark.asyncio
async def test_list_projects_endpoint():
    # Import app here to ensure global mocks from conftest are active
    from backend.main import app
    
    transport = ASGITransport(app=app)
    headers = {"X-API-Key": "test-api-key"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        response = await ac.get("/projects")
        assert response.status_code == 200
        assert "projects" in response.json()

@pytest.mark.asyncio
async def test_resume_project_endpoint_404():
    from backend.main import app
    
    transport = ASGITransport(app=app)
    headers = {"X-API-Key": "test-api-key"}
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        response = await ac.get("/resume/non-existent-id")
        assert response.status_code == 404