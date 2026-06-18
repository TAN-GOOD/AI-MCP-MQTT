import json
from typing import Any, Optional


def parse_json_path(data: Any, path: str) -> Optional[Any]:
    if not path or path == "$":
        return data

    if not path.startswith("$"):
        path = "$." + path

    parts = path[2:]
    if not parts:
        return data

    current = data
    for part in _tokenize(parts):
        if current is None:
            return None

        if part.endswith("]"):
            key = part[:part.index("[")]
            idx = int(part[part.index("[") + 1:-1])
            if key:
                current = current.get(key) if isinstance(current, dict) else None
            if isinstance(current, list) and 0 <= idx < len(current):
                current = current[idx]
            else:
                return None
        else:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None

    return current


def _tokenize(path_str: str) -> list:
    tokens = []
    current = ""
    i = 0
    while i < len(path_str):
        ch = path_str[i]
        if ch == ".":
            if current:
                tokens.append(current)
                current = ""
        elif ch == "[":
            if current:
                tokens.append(current)
                current = ""
            end = path_str.index("]", i)
            current = path_str[i + 1:end]
            tokens.append(f"[{current}]")
            current = ""
            i = end + 1
            continue
        else:
            current += ch
        i += 1
    if current:
        tokens.append(current)
    return tokens


def try_parse_json(text: str) -> Optional[Any]:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
