def test_login_route_is_not_mounted_in_public_mode(client):
    response = client.get("/login", follow_redirects=False)

    assert response.status_code == 404


def test_logout_route_is_not_mounted_in_public_mode(client):
    response = client.post("/logout", follow_redirects=False)

    assert response.status_code == 404


def test_home_redirects_to_imports_in_public_mode(client):
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/imports"


def test_imports_page_is_accessible_without_session(client):
    response = client.get("/imports")

    assert response.status_code == 200
    assert "/batch" in response.text
