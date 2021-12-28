from unittest.mock import patch

import pytest

from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_deployments_without_authentication(app, base_url):
    async with AsyncClient(app=app, base_url=base_url) as client:
        response = await client.get(app.url_path_for("get_deployments"))

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.asyncio
async def test_get_deployments(app, base_url, deployment_in_db, valid_access_token_in_db):
    async with AsyncClient(app=app, base_url=base_url) as client:
        response = await client.get(
            app.url_path_for("get_services"),
            headers={"authorization": f"Bearer {valid_access_token_in_db}"},
        )

    assert response.status_code == 200
    result = response.json()
    deployment_from_api = result[0]
    assert deployment_from_api["id"] == deployment_in_db.id


@pytest.mark.asyncio
async def test_deploy_no_access_token(app, base_url):
    async with AsyncClient(app=app, base_url=base_url) as client:
        with patch("app.routers.deployments.run_deploy"):
            test_url = app.url_path_for("start_deployment")
            response = await client.post(test_url)

    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest.mark.asyncio
async def test_deploy_invalid_access_token(app, base_url, invalid_service_token):
    headers = {"authorization": f"Bearer {invalid_service_token}"}
    async with AsyncClient(app=app, base_url=base_url) as client:
        with patch("app.routers.deployments.run_deploy"):
            test_url = app.url_path_for("start_deployment")
            response = await client.post(test_url, headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


@pytest.mark.asyncio
async def test_deploy_service_not_found(app, base_url, valid_service_token):
    headers = {"authorization": f"Bearer {valid_service_token}"}
    async with AsyncClient(app=app, base_url=base_url) as client:
        test_url = app.url_path_for("start_deployment")
        response = await client.post(test_url, headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


@pytest.mark.asyncio
async def test_deploy_service(app, base_url, repository, handler, valid_service_token_in_db, service_in_db):
    headers = {"authorization": f"Bearer {valid_service_token_in_db}"}
    async with AsyncClient(app=app, base_url=base_url) as client:
        with patch("app.routers.deployments.run_deploy"):
            test_url = app.url_path_for("start_deployment")
            response = await client.post(test_url, headers=headers)

    assert response.status_code == 200
    deployment_from_api = response.json()
    assert "id" in deployment_from_api

    # make sure added deployment was dispatched to event handlers
    assert handler.events[-3].type == "deployment"
    assert handler.last_event.type == "step"  # there's at least a default step added after deployment

    # make sure deployment was added to service in database
    deployments_by_service = await repository.get_deployments_by_service_id(service_in_db.id)
    assert len(deployments_by_service) == 1
    assert deployment_from_api["id"] == deployments_by_service[0].id


@pytest.mark.asyncio
async def test_finish_deploy_invalid_access_token(app, base_url, valid_service_token_in_db):
    headers = {"authorization": f"Bearer {valid_service_token_in_db}"}
    async with AsyncClient(app=app, base_url=base_url) as client:
        test_url = app.url_path_for("finish_deployment")
        response = await client.put(test_url, headers=headers)

    assert response.status_code == 401
    assert response.json() == {"detail": "Could not validate credentials"}


@pytest.mark.asyncio
async def test_finish_deploy(app, base_url, valid_deploy_token_in_db):
    headers = {"authorization": f"Bearer {valid_deploy_token_in_db}"}
    async with AsyncClient(app=app, base_url=base_url) as client:
        test_url = app.url_path_for("finish_deployment")
        response = await client.put(test_url, headers=headers)

    assert response.status_code == 200
    deployment_from_api = response.json()
    assert "id" in deployment_from_api

    assert "T" in deployment_from_api["finished"]
