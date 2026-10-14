#!/usr/bin/env python3
"""Read scoped coordination events from an existing Thinking, without writes."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

TYPES = {
    "run_start",
    "run_end",
    "run_resume",
    "scope_start",
    "scope_end",
    "wait_start",
    "wait_end",
    "interruption_start",
    "interruption_end",
    "human_turn",
    "package_first_outcome",
    "package_correction",
}
OUTCOMES = {"passed", "failed", "incomplete", "unknown"}


def time(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("event time must be a string or null")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.utcoffset() is None or parsed > datetime.now(timezone.utc):
        raise ValueError("event time must be timezone-qualified and not in the future")
    return parsed.timestamp()


def events(text):
    result = {}
    fence = None
    active = False
    comment = False
    for line in text.splitlines():
        if not fence:
            parts, position = [], 0
            while position < len(line):
                marker_text = "-->" if comment else "<!--"
                index = line.find(marker_text, position)
                if index < 0:
                    if not comment:
                        parts.append(line[position:])
                    break
                if not comment:
                    parts.append(line[position:index])
                comment = not comment
                position = index + len(marker_text)
            line = "".join(parts)

        marker = re.match(r"^\s*(`{3,}|~{3,})(.*)$", line)
        if fence:
            if (
                marker
                and marker[1][0] == fence[0]
                and len(marker[1]) >= fence[1]
                and not marker[2].strip()
            ):
                fence = None
                active = False
                continue
            if not active or not line.strip():
                continue
            item = json.loads(line)
            if not isinstance(item, dict) or any(
                not isinstance(item.get(k), str) or not item[k].strip()
                for k in ("run_id", "event_id", "type", "scope")
            ):
                raise ValueError(
                    "events require nonempty run/event/type/scope identity"
                )
            if (
                "at" not in item
                or item["type"] not in TYPES
                or not any(
                    isinstance(item.get(k), str) and item[k].strip()
                    for k in ("origin", "reference")
                )
            ):
                raise ValueError("event requires valid type, at and origin/reference")
            time(item["at"])
            if item.get("coverage", "unknown") not in (
                "complete",
                "partial",
                "unknown",
            ):
                raise ValueError("invalid coverage")
            key = (item["run_id"], item["event_id"])
            if key in result and result[key] != item:
                raise ValueError("conflicting replay of event identity")
            result[key] = item
        elif marker:
            fence = (marker[1][0], len(marker[1]))
            active = marker[2].strip() == "lb-run-events"
    if fence and active:
        raise ValueError("unterminated lb-run-events section")
    return list(result.values())


def union(intervals):
    total = 0.0
    end = None
    for start, stop in sorted(intervals):
        total += max(0, stop - max(start, end if end is not None else start))
        end = max(stop, end if end is not None else stop)
    return total


def calculate(all_events, run_id, scope):
    selected = [
        e
        for e in all_events
        if e["run_id"] == run_id and (scope == "logbook" or e["scope"] == scope)
    ]
    start_type, end_type = (
        ("run_start", "run_end") if scope == "logbook" else ("scope_start", "scope_end")
    )
    starts = [e for e in selected if e["type"] == start_type and e["scope"] == scope]
    ends = [e for e in selected if e["type"] == end_type and e["scope"] == scope]
    if len(starts) > 1 or len(ends) > 1:
        raise ValueError("multiple scope boundaries")
    start = time(starts[0]["at"]) if starts else None
    end = time(ends[0]["at"]) if ends else None
    if start is not None and end is not None and end < start:
        raise ValueError("inverted scope endpoints")
    wall = end - start if start is not None and end is not None else None
    complete = bool(
        starts
        and ends
        and starts[0].get("coverage") == ends[0].get("coverage") == "complete"
    )
    if any(e.get("coverage") in ("partial", "unknown") for e in selected):
        complete = False
    intervals = {"wait": [], "interruption": []}
    interval_complete = {"wait": True, "interruption": True}
    for kind in intervals:
        grouped = {}
        for e in selected:
            if e["type"] not in (kind + "_start", kind + "_end"):
                continue
            identity = e.get("interval_id")
            if not isinstance(identity, str) or not identity:
                raise ValueError("interval requires interval_id")
            group = grouped.setdefault(identity, {})
            if e["type"] in group:
                raise ValueError("duplicate interval endpoint")
            group[e["type"]] = time(e["at"])
        for group in grouped.values():
            a, b = group.get(kind + "_start"), group.get(kind + "_end")
            if a is None or b is None or wall is None:
                interval_complete[kind] = False
                continue
            if b < a:
                raise ValueError("inverted interval")
            a, b = max(a, start), min(b, end)
            if b > a:
                intervals[kind].append((a, b))
    known_wait, known_interruption = (
        union(intervals["wait"]),
        union(intervals["interruption"]),
    )
    known_union = union(intervals["wait"] + intervals["interruption"])
    durations_complete = (
        complete and wall is not None and all(interval_complete.values())
    )
    turns = {}
    priority = {"gate": 0, "additional": 1, "recovery": 2}
    for e in selected:
        if e["type"] != "human_turn":
            continue
        identity, category = e.get("human_turn_id"), e.get("category")
        if not isinstance(identity, str) or not identity or category not in priority:
            raise ValueError("human turn requires identity and category")
        if identity not in turns or priority[category] < priority[turns[identity]]:
            turns[identity] = category
    packages = {}
    corrections = {
        e["event_id"]: e for e in selected if e["type"] == "package_correction"
    }
    outcomes = {
        e["event_id"]: e for e in selected if e["type"] == "package_first_outcome"
    }
    for e in outcomes.values():
        package = e.get("package_id")
        if not isinstance(package, str) or not package or package in packages:
            raise ValueError("missing package identity or duplicate first outcome")
        if e.get("outcome") not in OUTCOMES or (
            e.get("first_pass") is not None and type(e["first_pass"]) is not bool
        ):
            raise ValueError("invalid first outcome")
        packages[package] = (
            e.get("first_pass") if e.get("outcome") == "passed" else False
        )
    for correction in corrections.values():
        if (
            correction.get("outcome") not in OUTCOMES
            or (
                correction.get("first_pass") is not None
                and type(correction["first_pass"]) is not bool
            )
            or not correction.get("reason")
        ):
            raise ValueError("correction requires outcome, first_pass and reason")
        chain, current = set(), correction
        while current["event_id"] in corrections:
            if current["event_id"] in chain:
                raise ValueError("cyclic correction")
            chain.add(current["event_id"])
            parent_id = current.get("corrects")
            parent = corrections.get(parent_id) or outcomes.get(parent_id)
            if not parent or parent.get("package_id") != correction.get("package_id"):
                raise ValueError("missing or mismatched correction target")
            current = parent
        package = current["package_id"]
        if (
            correction.get("outcome") != "passed"
            or correction.get("first_pass") is False
        ):
            packages[package] = False
        elif correction.get("first_pass") is None and packages[package] is not False:
            packages[package] = None
    denominator = len(packages)
    known_numerator = sum(value is True for value in packages.values())
    numerator = (
        known_numerator
        if all(value is not None for value in packages.values())
        else None
    )
    return {
        "run_id": run_id,
        "scope": scope,
        "coverage": "complete" if complete else "partial" if selected else "unknown",
        "event_count": len(selected),
        "wall_seconds": wall,
        "wait_seconds": known_wait if durations_complete else None,
        "interruption_seconds": known_interruption if durations_complete else None,
        "unavailable_union_seconds": known_union if durations_complete else None,
        "remaining_wall_seconds": wall - known_union if durations_complete else None,
        "known_interval_seconds": {
            "wait": known_wait,
            "interruption": known_interruption,
            "union": known_union,
        },
        "human_interactions": {
            "total": len(turns) if complete else None,
            "known_total": len(turns),
            "known_categories": {
                k: sum(v == k for v in turns.values()) for k in priority
            },
        },
        "first_pass": {
            "numerator": numerator,
            "denominator": denominator,
            "rate": numerator / denominator
            if complete and denominator and numerator is not None
            else None,
            **({"known_numerator": known_numerator} if numerator is None else {}),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--thinking", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--scope", default="logbook")
    args = parser.parse_args()
    try:
        root = Path(args.root).resolve(strict=True)
        relative = Path(args.thinking)
        if not root.is_dir() or relative.is_absolute():
            raise OSError("root must be a directory and Thinking path relative")
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():
            raise OSError("Thinking must be a file inside root")
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 3
    try:
        print(
            json.dumps(
                calculate(events(text), args.run_id, args.scope), ensure_ascii=False
            )
        )
    except (ValueError, TypeError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
