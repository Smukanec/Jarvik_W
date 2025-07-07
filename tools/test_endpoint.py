import argparse
import json
import os
from pathlib import Path

__all__ = [
    "get_target_url",
    "send_test_request",
    "read_log",
    "main",
]
__test__ = False

import requests

BASE_DIR = Path(__file__).resolve().parent.parent


def get_target_url() -> str:
    """Return the Jarvik server URL."""
    url = os.environ.get("JARVIK_URL")
    if url:
        return url.rstrip("/")
    config_path = BASE_DIR / "devlab_config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and "url" in data:
                return str(data["url"]).rstrip("/")
        except Exception:
            pass
    return "http://localhost:8000"


def send_test_request(url: str, message: str) -> str:
    """Send a POST request to /ask and return the response text."""
    resp = requests.post(f"{url}/ask", json={"message": message})
    resp.raise_for_status()
    return resp.text


def read_log(path: str, lines: int = 20) -> str:
    """Return the last *lines* of *path* if it exists."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return "".join(fh.readlines()[-lines:])
    except FileNotFoundError:
        return ""


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Test a running Jarvik server")
    parser.add_argument("--message", "-m", default="Hello")
    parser.add_argument("--log", help="Show last lines from the given log file")
    args = parser.parse_args(argv)

    url = get_target_url()
    print(f"POST {url}/ask")
    try:
        text = send_test_request(url, args.message)
        print(text)
    except Exception as exc:  # pragma: no cover - network dependent
        print(f"Request failed: {exc}")
        return

    if args.log:
        excerpt = read_log(args.log)
        if excerpt:
            print("\nRecent log entries:\n" + excerpt)


if __name__ == "__main__":
    main()
