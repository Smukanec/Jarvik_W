import os
import json
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR = os.getenv("MEMORY_DIR", os.path.join(BASE_DIR, "memory"))
DEFAULT_FILE = os.path.join(MEMORY_DIR, "public.jsonl")


def load_memory(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def search_entries(entries: list[dict], query: str) -> list[dict]:
    q = query.lower()
    out: list[dict] = []
    for item in entries:
        if q in item.get("user", "").lower() or q in item.get("jarvik", "").lower():
            out.append(item)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Search or display Jarvik memory logs")
    parser.add_argument("--folder", default=DEFAULT_FILE, help="Memory folder or file")
    parser.add_argument("-n", "--last", type=int, default=5, help="Show last N entries when no query is given")
    parser.add_argument("-q", "--query", help="Search for a string")
    args = parser.parse_args()

    path = args.folder
    if os.path.isdir(path):
        path = os.path.join(path, "log.jsonl")
    entries = load_memory(path)
    if args.query:
        entries = search_entries(entries, args.query)
    else:
        entries = entries[-args.last:]
    print(json.dumps(entries, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
