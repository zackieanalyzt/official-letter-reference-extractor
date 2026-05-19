from app.i18n import normalize_lang
from app.i18n.en import LABELS as EN_LABELS
from app.i18n.th import LABELS as TH_LABELS


def test_default_language_uses_app_lang(client):
    client.app.state.settings.app_lang = "en"

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert EN_LABELS["dashboard_title"] in response.text


def test_invalid_language_falls_back_to_thai(client):
    client.app.state.settings.app_lang = "xx"

    response = client.get("/dashboard")

    assert response.status_code == 200
    assert TH_LABELS["dashboard_title"] in response.text
    assert normalize_lang("xx", default="yy") == "th"


def test_language_switch_sets_cookie_and_redirects(client):
    response = client.post(
        "/settings/language",
        data={"lang": "en", "next": "/results"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/results"
    assert response.cookies["lang"] == "en"


def test_switching_to_english_changes_labels(client):
    response = client.post(
        "/settings/language",
        data={"lang": "en", "next": "/imports"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert EN_LABELS["release_information"] in response.text
    assert EN_LABELS["release_version"] in response.text
    assert EN_LABELS["results"] in response.text


def test_switching_to_thai_changes_labels(client):
    client.cookies.set("lang", "en")

    response = client.post(
        "/settings/language",
        data={"lang": "th", "next": "/imports"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert TH_LABELS["release_information"] in response.text
    assert TH_LABELS["release_version"] in response.text
    assert TH_LABELS["results"] in response.text


def test_language_switch_replaces_external_next_url(client):
    response = client.post(
        "/settings/language",
        data={"lang": "en", "next": "https://evil.com"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/dashboard"
    assert response.cookies["lang"] == "en"


def test_existing_pages_render_with_language_cookie(client):
    client.cookies.set("lang", "en")

    for path in ["/dashboard", "/results", "/quality", "/exports", "/imports", "/batch"]:
        response = client.get(path)
        assert response.status_code == 200
        assert EN_LABELS["language"] in response.text
