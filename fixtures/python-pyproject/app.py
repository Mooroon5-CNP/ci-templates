import requests


def user_agent():
    return requests.utils.default_user_agent()
