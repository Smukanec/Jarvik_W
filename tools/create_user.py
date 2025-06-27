import argparse
import getpass
import json
import os

import auth

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USERS_FILE = os.path.join(BASE_DIR, "users.json")


def load_users() -> list[dict]:
    if not os.path.exists(USERS_FILE):
        return []
    with open(USERS_FILE, "r", encoding="utf-8") as fh:
        return json.load(fh)


def save_users(users: list[dict]) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as fh:
        json.dump(users, fh, indent=2)
        fh.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Add a user to users.json")
    parser.add_argument("--nick")
    parser.add_argument("--password")
    args = parser.parse_args()

    nick = args.nick or input("Nick: ")
    password = args.password or getpass.getpass("Password: ")

    users = load_users()
    if any(u.get("nick") == nick for u in users):
        parser.error(f"User '{nick}' already exists")

    users.append({"nick": nick, "password_hash": auth.hash_password(password)})
    save_users(users)
    print(f"User '{nick}' added to {USERS_FILE}")
    print("Restart the Flask server to load updated users.")


if __name__ == "__main__":
    main()
