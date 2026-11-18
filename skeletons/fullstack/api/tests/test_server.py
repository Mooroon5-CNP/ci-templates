import json

from server import route


def test_health_endpoints():
    assert route("/healthz")[0] == 200
    assert route("/ready")[0] == 200


def test_api_info():
    status, _, body = route("/api/info")
    assert status == 200
    assert json.loads(body) == {"app": "{{APP_NAME}}", "back": "python", "front": "node"}
