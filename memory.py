import json
import os
from datetime import datetime
from typing import Any, Optional


def _parse_dt(value: Any) -> Optional[datetime]:
    """Parse *value* into a ``datetime`` if possible."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return None


def vymazat_memory_range(filepath: str, od: Any = None, do: Any = None, hledat_podle: str | None = None) -> int:
    """Delete entries from *filepath* within the given time range or containing a keyword.

    Parameters
    ----------
    filepath : str
        Path to the JSONL memory file.
    od : str or datetime, optional
        Start of the time range (inclusive).
    do : str or datetime, optional
        End of the time range (inclusive).
    hledat_podle : str, optional
        Keyword to search for. Matching is case-insensitive.

    Returns
    -------
    int
        Number of removed entries.
    """
    if not os.path.exists(filepath):
        return 0

    start = _parse_dt(od)
    end = _parse_dt(do)
    key = (hledat_podle or "").lower()

    kept: list[str] = []
    removed = 0

    with open(filepath, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                kept.append(line)
                continue

            text = json.dumps(entry).lower()
            if key and key in text:
                removed += 1
                continue

            if start or end:
                t = None
                for fld in ("time", "timestamp", "date"):
                    if fld in entry:
                        t = _parse_dt(entry[fld])
                        break
                if t is not None:
                    if ((start and t < start) or (end and t > end)):
                        kept.append(json.dumps(entry))
                    else:
                        removed += 1
                    continue
            kept.append(json.dumps(entry))

    if removed:
        with open(filepath, "w", encoding="utf-8") as f:
            for line in kept:
                f.write(line + "\n")
    return removed
