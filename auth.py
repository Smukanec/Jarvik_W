import os
import json
from dataclasses import dataclass, field
from typing import Dict
from werkzeug.security import check_password_hash, generate_password_hash

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
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
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
