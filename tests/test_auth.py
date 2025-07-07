import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from auth import load_users, hash_password, User  # noqa: E402


def test_load_users_invalid_json(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{bad}", encoding="utf-8")
    assert load_users(str(path)) == {}


def test_load_users_success(tmp_path):
    path = tmp_path / "users.json"
    data = [{"nick": "bob", "password_hash": hash_password("pw") }]
    path.write_text(json.dumps(data), encoding="utf-8")
    users = load_users(str(path))
    assert list(users.keys()) == ["bob"]
    assert isinstance(users["bob"], User)
    assert users["bob"].verify("pw")

