#Integration Tests (Flask Test Client) to test end-to-end behaviour withour a browser 
import pytest
from app import app

@pytest.fixture
def client():
    app.config["TESTING"]= True
    app.secret_key = "test-secret"
    with app.test_client() as client:
        yield client

def test_index_redirects_to_login_when_logged_out(client):
    response= client.get("/")
    assert response.status_code == 302
    assert "/login" in response.location

def test_dashboard_requires_login(client):
    response= client.get("/dashboard")
    assert response.status_code == 302

def test_set_energy_requires_login(client):
    response = client.post("/set_energy", data={"energy": 3})
    assert response.status_code == 302

def test_login_page_loads(client):
    response = client.get("/login")
    assert response.status_code == 200