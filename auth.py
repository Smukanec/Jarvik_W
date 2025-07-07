import os
import json
import logging
from dataclasses import dataclass, field
from typing import Dict
try:
    from werkzeug.security import check_password_hash, generate_password_hash
except Exception:  # pragma: no cover - optional dependency
    import hashlib

    def generate_password_hash(password: str) -> str:
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def check_password_hash(hashval: str, password: str) -> bool:
        return hashlib.sha256(password.encode("utf-8")).hexdigest() == hashval

@dataclass
class User:
    nick: str
    password_hash: str
    knowledge_folders: list[str] = field(default_factory=list)
    memory_folders: list[str] = field(default_factory=list)

    def verify(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


def load_users(path: str) -> Dict[str, User]:
    """Load user definitions from *path* if it exists."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:  # pragma: no cover - invalid file
        logging.error("Failed to load users file %s: %s", path, exc)
        return {}
    if not isinstance(data, list):
        logging.error("Users file %s has unexpected format", path)
        return {}
    users: Dict[str, User] = {}
    for item in data:
        if not item.get("nick") or not item.get("password_hash"):
            continue
        users[item["nick"]] = User(
            nick=item["nick"],
            password_hash=item["password_hash"],
            knowledge_folders=item.get("knowledge_folders", []),
            memory_folders=item.get("memory_folders", []),
        )
    return users


def hash_password(password: str) -> str:
    """Return a werkzeug password hash for *password*."""
    return generate_password_hash(password)
