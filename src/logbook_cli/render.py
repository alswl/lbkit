"""CLI presentation, kept outside use cases and command declarations."""

import json
from collections import Counter

from logbook_cli.services.common import Result


def render(result: Result, as_json: bool, view: str = "default") -> None:
    value = result.value
    if as_json:
        print(json.dumps(value, ensure_ascii=False, indent=2))
    elif result.text is not None:
        print(result.text, end="")
    elif view == "list":
        assert isinstance(value, dict)
        for path in value["logbooks"]:
            print(f"{path}:1: LOGBOOK: discovered")
    elif view == "check":
        assert isinstance(value, list)
        for item in value:
            print(f"{item['path']}:{item['line']}: {item['code']}: {item['message']}")
    elif view == "tasks":
        assert isinstance(value, list)
        for row in value:
            print(f"{row['path']}:{row['line']}: [{row['state']}] {row['text']}")
    elif view == "next":
        if value is not None:
            assert isinstance(value, dict)
            print(
                f"{value['stage']}:{value['line']}: [{value['state']}] {value['text']}"
            )
    elif view == "extract":
        assert isinstance(value, dict)
        for item in value["candidates"]:
            mark = "x" if item["done"] else " "
            print(f"[{mark}] {item['action']}: {item['raw']}  ({item['source']})")
            for path in item["work_packages"]:
                print("    wp: " + path)
            for diagnostic in item["diagnostics"]:
                print("    diagnostic: " + diagnostic)
    elif view == "usage":
        assert isinstance(value, dict)
        for (skill, cwd), n in Counter(
            (e["skill"], e["cwd"]) for e in value["events"]
        ).most_common():
            print(f"{n:4} {skill}  {cwd}")
    else:
        print(json.dumps(value, ensure_ascii=False, indent=2))
