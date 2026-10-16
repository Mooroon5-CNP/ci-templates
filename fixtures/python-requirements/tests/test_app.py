import json

from app import route


def test_health_endpoints():
    assert route("/healthz")[0] == 200
    assert route("/ready")[0] == 200


def test_root_returns_app_name():
    status, _, body = route("/")
    assert status == 200
    assert json.loads(body)["app"] == "fixture-python"


def test_unknown_path_is_404():
    assert route("/nope")[0] == 404
