from app import user_agent


def test_user_agent():
    assert user_agent().startswith("python-requests/")
