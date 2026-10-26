"""評核表內容(data/rubric.json)的讀取工具。換評核表只需改 JSON,不必改程式。"""
import json
from functools import lru_cache
from pathlib import Path

RUBRIC_PATH = Path(__file__).resolve().parent.parent / "data" / "rubric.json"


@lru_cache(maxsize=1)
def load() -> dict:
    return json.loads(RUBRIC_PATH.read_text(encoding="utf-8"))


def items() -> list[dict]:
    return load()["items"]


def item(item_id: str) -> dict:
    return next(i for i in items() if i["id"] == item_id)


def codes(item_id: str | None = None) -> list[dict]:
    cs = load()["codes"]
    return [c for c in cs if item_id is None or c["item"] == item_id]


def code(code_id: str) -> dict | None:
    return next((c for c in load()["codes"] if c["code"] == code_id), None)


def code_label(c: dict) -> str:
    return f'{c["code"]} {c["text"]}({c["mode"]} {c["unit_score"]} 分/{c["unit"]})'
