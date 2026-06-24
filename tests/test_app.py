import copy

import anyio
import pytest
from httpx2 import AsyncClient, ASGITransport

from src.app import app, activities


@pytest.fixture(scope="session")
def http_client():
    transport = ASGITransport(app=app)
    client = AsyncClient(transport=transport, base_url="http://testserver")
    yield client
    anyio.run(client.aclose)


@pytest.fixture(autouse=True)
def reset_activities():
    baseline = copy.deepcopy(activities)
    yield
    activities.clear()
    activities.update(copy.deepcopy(baseline))


def make_request(action):
    async def wrapper():
        return await action()

    return anyio.run(wrapper)


def test_root_redirects_to_index(http_client):
    # Arrange
    url = "/"

    # Act
    response = make_request(lambda: http_client.get(url, follow_redirects=False))

    # Assert
    assert response.status_code == 307
    assert response.headers["location"] == "/static/index.html"


def test_get_activities_returns_all_activities(http_client):
    # Arrange
    url = "/activities"

    # Act
    response = make_request(lambda: http_client.get(url))

    # Assert
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    assert "Chess Club" in body
    assert body["Tennis"]["max_participants"] == 8


def test_signup_for_activity_adds_participant(http_client):
    # Arrange
    activity_name = "Art Club"
    email = "newstudent@mergington.edu"
    url = f"/activities/{activity_name}/signup"

    # Act
    response = make_request(lambda: http_client.post(url, params={"email": email}))

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Signed up {email} for {activity_name}"}
    assert email in activities[activity_name]["participants"]


def test_signup_duplicate_returns_400(http_client):
    # Arrange
    activity_name = "Chess Club"
    email = "michael@mergington.edu"
    url = f"/activities/{activity_name}/signup"

    # Act
    response = make_request(lambda: http_client.post(url, params={"email": email}))

    # Assert
    assert response.status_code == 400
    assert response.json()["detail"] == "Student already signed up for this activity"


def test_signup_missing_activity_returns_404(http_client):
    # Arrange
    activity_name = "Nonexistent Club"
    url = f"/activities/{activity_name}/signup"

    # Act
    response = make_request(lambda: http_client.post(url, params={"email": "student@mergington.edu"}))

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"


def test_unregister_participant_removes_participant(http_client):
    # Arrange
    activity_name = "Basketball"
    email = "james@mergington.edu"
    url = f"/activities/{activity_name}/participants/{email}"
    assert email in activities[activity_name]["participants"]

    # Act
    response = make_request(lambda: http_client.delete(url))

    # Assert
    assert response.status_code == 200
    assert response.json() == {"message": f"Unregistered {email} from {activity_name}"}
    assert email not in activities[activity_name]["participants"]


def test_unregister_nonexistent_participant_returns_404(http_client):
    # Arrange
    activity_name = "Basketball"
    url = f"/activities/{activity_name}/participants/unknown@mergington.edu"

    # Act
    response = make_request(lambda: http_client.delete(url))

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Participant not found"


def test_unregister_missing_activity_returns_404(http_client):
    # Arrange
    activity_name = "Space Club"
    url = f"/activities/{activity_name}/participants/student@mergington.edu"

    # Act
    response = make_request(lambda: http_client.delete(url))

    # Assert
    assert response.status_code == 404
    assert response.json()["detail"] == "Activity not found"
