import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from memory import vymazat_memory_range


def test_remove_by_date_range(tmp_path):
    path = tmp_path / "mem.jsonl"
    entries = [
        {"timestamp": "2024-01-01T00:00:00", "id": 1},
        {"timestamp": "2024-01-05T00:00:00", "id": 2},
        {"timestamp": "2024-01-10T00:00:00", "id": 3},
    ]
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")

    removed = vymazat_memory_range(
        str(path),
        od="2024-01-02T00:00:00",
        do="2024-01-07T00:00:00",
    )
    assert removed == 1

    with open(path, "r", encoding="utf-8") as f:
        remaining = [json.loads(line) for line in f if line.strip()]
    assert [e["id"] for e in remaining] == [1, 3]


def test_remove_by_keyword(tmp_path):
    path = tmp_path / "mem.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"user": "remove this", "jarvik": "x"}) + "\n")
        f.write(json.dumps({"user": "keep", "jarvik": "y"}) + "\n")

    removed = vymazat_memory_range(str(path), hledat_podle="REMOVE")
    assert removed == 1

    with open(path, "r", encoding="utf-8") as f:
        remaining = [json.loads(line) for line in f if line.strip()]
    assert len(remaining) == 1
    assert remaining[0]["user"] == "keep"


def test_invalid_json_lines_kept(tmp_path):
    path = tmp_path / "mem.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"user": "delete", "jarvik": "x"}) + "\n")
        f.write("{bad json}\n")
        f.write(json.dumps({"user": "keep", "jarvik": "y"}) + "\n")

    removed = vymazat_memory_range(str(path), hledat_podle="delete")
    assert removed == 1

    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()

    assert "{bad json}" in lines
    assert len(lines) == 2
    assert all("delete" not in line for line in lines)
