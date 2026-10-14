"""Markdown parsing, path validation, and logbook rules."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from logbook_cli.format import (
    LABELS,
    MARKER_RE,
    PREFLIGHT_MARKER,
    STAGE_MARKERS,
    STATUS_RE,
    SUMMARY_TEXT,
    TAIL_SEPARATOR,
    field_value,
    language,
    machine_group,
    marker_style,
    prefix,
    skill_chain,
    split_marker,
    task_metadata,
)
from logbook_cli.models import (
    Field,
    Stage,
    StageStatus,
    Task,
    TaskAnnotation,
    derive_stage_status,
)

EXIT_ISSUES, EXIT_USAGE, EXIT_PATH, EXIT_REFUSED = 1, 2, 3, 4
TASK_RE = re.compile(
    r"^(?P<indent>[ \t]*)[-*+] \[(?P<state> |/|x|X|-)\] (?P<text>.*?)(?:\r?\n)?$"
)
H2_RE = re.compile(r"^##\s+(?P<title>.*?)(?:\r?\n)?$")
H1_RE = re.compile(r"^#(?!#)\s+")
FENCE_RE = re.compile(r"^[ \t]*([`~])\1{2,}")
EMOJI_RE = MARKER_RE
STAGE_RE = re.compile(r"^Stage\s+\d+[a-z]?\b", re.IGNORECASE)
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


class LbError(Exception):
    def __init__(self, message: str, code: int = EXIT_PATH) -> None:
        super().__init__(message)
        self.message, self.code = message, code


@dataclass
class Document:
    path: Path
    root: Path
    data: bytes
    text: str
    lines: list[str]
    offsets: list[int]
    stages: list[Stage]
    headings: list[tuple[int, str]]
    comment_tail_lines: list[int]
    preflight: list[dict]
    status_lines: list[dict]

    @property
    def locale(self) -> str:
        return language(
            "".join(line for _, line in visible_lines(self.lines) if line is not None)
        )

    @property
    def token(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


def root_path(value: str) -> Path:
    try:
        return Path(value).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise LbError(f"invalid --root: {exc}") from exc


def safe_path(root: Path, value: str) -> Path:
    raw = Path(value)
    candidate = raw if raw.is_absolute() else root / raw
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise LbError(f"path escapes --root or does not exist: {value}") from exc
    if not resolved.is_file():
        raise LbError(f"not a file: {value}")
    return resolved


def visible_lines(lines: list[str]):
    """Yield (line, visible prefix) outside fences/comments.

    An inline comment hides only its own suffix; parsing still retains the
    original physical line for task identity. Structure after a multi-line
    comment closes is deliberately rejected as ambiguous.
    """
    fence: tuple[str, int] | None = None
    comment = False
    for index, line in enumerate(lines):
        if fence:
            char, width = fence
            if re.match(
                rf"^[ \t]*{re.escape(char)}{{{width},}}[ \t]*(?:\r?\n)?$", line
            ):
                fence = None
            continue
        if comment:
            if "-->" in line:
                tail = line.split("-->", 1)[1]
                comment = False
                if tail.strip():
                    yield index, None
            continue
        if "<!--" in line:
            visible, after = line.split("<!--", 1)
            if "-->" not in after:
                comment = True
            if visible.strip():
                yield index, visible
            continue
        marker = FENCE_RE.match(line)
        if marker:
            fence = (marker.group(1), len(marker.group(0).lstrip()))
            continue
        yield index, line


def parse(path: Path, root: Path) -> Document:
    return parse_text(path.read_bytes(), path, root)


def parse_text(data: bytes, path: Path, root: Path) -> Document:
    """Parse an in-memory candidate with the same rules as a file on disk."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LbError(f"not UTF-8 Markdown: {path}") from exc
    lines = text.splitlines(keepends=True)
    offsets, pos = [], 0
    for line in lines:
        offsets.append(pos)
        pos += len(line)
    stages: list[Stage] = []
    headings: list[tuple[int, str]] = []
    current: Stage | None = None
    comment_tail_lines = []
    preflight = []
    status_lines = []
    for index, visible in visible_lines(lines):
        if visible is None:
            comment_tail_lines.append(index + 1)
            continue
        line = lines[index]
        if current is None and STATUS_RE.match(visible):
            status_lines.append(
                {
                    "line": index + 1,
                    "start": offsets[index],
                    "end": offsets[index] + len(line),
                    "raw": line.rstrip("\r\n"),
                }
            )
        h2 = H2_RE.match(visible)
        if h2:
            display = h2.group("title")
            title, emoji, style = split_marker(display)
            current = Stage(
                title,
                display,
                index + 1,
                offsets[index],
                offsets[index] + len(line),
                emoji,
                bool(STAGE_RE.match(title)),
                [],
                [],
            )
            stages.append(current)
            current.marker_style = style
            headings.append((index + 1, title))
            continue
        task = TASK_RE.match(line) if TASK_RE.match(visible) else None
        if task and PREFLIGHT_MARKER in task.group("text"):
            preflight.append(
                {
                    "line": index + 1,
                    "text": task.group("text"),
                    "indent": task.group("indent"),
                    "stage": current.title if current else None,
                }
            )
        if task and current and task.group("indent") == "":
            state_at = offsets[index] + line.index("[") + 1
            current.tasks.append(
                Task(
                    current.title,
                    task.group("state").lower(),
                    task.group("text"),
                    index + 1,
                    offsets[index],
                    state_at,
                    offsets[index] + len(line),
                    task.group("indent"),
                )
            )
        elif current and re.match(r"^[-*+] \[[^]]+\] ", visible):
            current.unknown_task_lines.append(index + 1)
    visibility = dict(visible_lines(lines))
    for stage in stages:
        for item in stage.tasks:
            task_metadata(item)
            records = []
            for index in range(item.line, len(lines)):
                line = lines[index]
                if line.strip() and not line.startswith((" ", "\t")):
                    break
                visible = visibility.get(index)
                if visible:
                    child = re.match(r"^ {4}[-*+] (.*)", visible)
                    value = field_value(child[1]) if child else None
                    if value:
                        kind, body, label = value
                        item.annotations.append(
                            TaskAnnotation(kind, body, index + 1, label)
                        )
                        if kind is Field.RESOLUTION:
                            records.append(body)
            if not records:
                continue
            try:
                record = json.loads(records[0])
                valid = (
                    len(records) == 1
                    and isinstance(record, dict)
                    and set(record) == {"task", "as", "decision", "note"}
                    and record["task"] == item.identity
                    and item.state == "-"
                    and record["as"] in ("human-cancelled", "not-applicable")
                    and all(
                        isinstance(record[k], str) and record[k].strip()
                        for k in ("decision", "note")
                    )
                )
            except (ValueError, TypeError):
                valid = False
            if valid:
                item.resolution = record
            else:
                item.resolution_error = True
    return Document(
        path,
        root,
        data,
        text,
        lines,
        offsets,
        stages,
        headings,
        comment_tail_lines,
        preflight,
        status_lines,
    )


def stage_state(stage: Stage) -> str | None:
    """Compatibility renderer for the public Markdown/JSON marker."""
    status = derive_stage_status(stage)
    return STAGE_MARKERS[stage.marker_style][status] if status else None


def next_task(doc: Document) -> Task | None:
    return next(
        (
            task
            for stage in doc.stages
            if stage.is_delivery
            for task in stage.tasks
            if task.state in (" ", "/")
        ),
        None,
    )


def summary_derived(
    doc: Document, locale: str | None = None, style: str | None = None
) -> str:
    locale = locale or doc.locale
    words = SUMMARY_TEXT[locale]
    in_flight = next(
        (
            s
            for s in doc.stages
            if s.is_delivery and derive_stage_status(s) is not StageStatus.SETTLED
        ),
        None,
    )
    if in_flight is None:
        status = StageStatus.SETTLED
        text = (
            words["settled"]
            if any(t.resolution for s in doc.stages if s.is_delivery for t in s.tasks)
            else words["complete"]
        )
    else:
        status = derive_stage_status(in_flight) or StageStatus.IN_PROGRESS
        text = in_flight.title
    style = style or (
        in_flight.marker_style
        if in_flight
        else next((s.marker_style for s in doc.stages if s.is_delivery), "emoji")
    )
    parts = [prefix(Field.STATUS, locale) + STAGE_MARKERS[style][status] + " " + text]
    if doc.preflight:
        parts.append(
            PREFLIGHT_MARKER + " " + words["pending"].format(count=len(doc.preflight))
        )
    incomplete = next_task(doc)
    if incomplete is not None:
        parts.append(words["next"] + incomplete.text)
    return " · ".join(parts)


def summary_lines(doc: Document) -> list[dict]:
    records = []
    for record in doc.status_lines:
        raw = record["raw"]
        match = STATUS_RE.match(raw)
        assert match is not None
        locale = "zh" if match[1] == LABELS["zh"][Field.STATUS] else "en"
        body = raw[match.end() :]
        head, separator, tail = body.partition(TAIL_SEPARATOR[locale])
        marker = MARKER_RE.match(head)
        owned = (
            bool(
                marker
                and any(
                    marker[1] in values.values() for values in STAGE_MARKERS.values()
                )
            )
            and "<!--" not in raw
        )
        item = {**record, "owned": owned, "current": raw}
        if owned and marker is not None:
            derived = summary_derived(doc, locale, marker_style(marker[1]))
            # Keep the original field spelling and colon spacing.
            derived_body = derived[len(prefix(Field.STATUS, locale)) :]
            item["target"] = (
                raw[: match.end()]
                + derived_body
                + (" " + separator + tail if separator else "")
            ).rstrip()
        records.append(item)
    return records


def workdirs(doc: Document) -> list[dict]:
    result, group = [], None
    for index, line in directory_items(doc):
        top = machine_group(line)
        child = re.match(r"^  - `([^`]+)`\s*$", line)
        if top:
            group = {**top, "paths": [], "line": index + 1}
            result.append(group)
        elif child and group:
            group["paths"].append({"path": child.group(1), "line": index + 1})
    return result


def directory_items(doc: Document):
    """Return only the contiguous list immediately following 工作目录：."""
    visible = [
        (index, line) for index, line in visible_lines(doc.lines) if line is not None
    ]
    for position, (index, _) in enumerate(visible):
        if (
            not (value := field_value(doc.lines[index]))
            or value[0] is not Field.DIRECTORIES
        ):
            continue
        started = False
        for next_index, raw_line in visible[position + 1 :]:
            line = raw_line.rstrip("\r\n")
            if re.match(r"^#{1,2}\s", line):
                return
            if not line.strip() and not started:
                continue
            if re.match(r"^(?:- |  - )", line):
                started = True
                yield next_index, line
                continue
            return
        return


def links_for(doc: Document, stage: Stage | None = None) -> list[dict]:
    start_line, end_line = 0, len(doc.lines)
    if stage:
        start_line = stage.line
        later = [s.line - 1 for s in doc.stages if s.line > stage.line]
        end_line = min(later) if later else len(doc.lines)
    links = []
    for i, line in visible_lines(doc.lines):
        if line is None:
            continue
        if not start_line <= i < end_line:
            continue
        for label, target in LINK_RE.findall(line):
            links.append({"label": label, "target": target, "line": i + 1})
    return links


def context(doc: Document) -> dict:
    from logbook_cli.link_records import observations

    verification_records, verification_errors = observations(doc, links_for(doc))
    incomplete = next_task(doc)
    records = [
        link
        for link in links_for(doc)
        if "/thinking/" in link["target"] or "/prompts/" in link["target"]
    ]
    return {
        "path": str(doc.path.relative_to(doc.root)),
        "version_token": doc.token,
        "stages": [
            {
                "title": s.title,
                "line": s.line,
                "emoji": s.emoji,
                "derived_emoji": stage_state(s),
                "delivery_stage": s.is_delivery,
                "tasks": [
                    {
                        "text": task.text,
                        "state": task.state,
                        "line": task.line,
                        "repositories": task.repositories,
                        "human": task.human,
                        "resolution": task.resolution,
                        "preflight": task.preflight_blocker,
                        "annotations": [
                            {
                                "kind": a.kind.value,
                                "value": a.value,
                                "line": a.line,
                                **(
                                    {
                                        "names": list(skill_chain(a.value).names),
                                        "diagnostics": list(
                                            skill_chain(a.value).diagnostics
                                        ),
                                    }
                                    if a.kind is Field.SKILLS
                                    else {}
                                ),
                            }
                            for a in task.annotations
                        ],
                    }
                    for task in s.tasks
                ],
            }
            for s in doc.stages
        ],
        "next_task": None
        if incomplete is None
        else {
            "stage": incomplete.stage,
            "state": incomplete.state,
            "text": incomplete.text,
            "line": incomplete.line,
            "repositories": incomplete.repositories,
            "human": incomplete.human,
            "preflight": incomplete.preflight_blocker,
        },
        "work_directories": workdirs(doc),
        "related_links": links_for(doc),
        "link_verifications": verification_records,
        "link_verification_errors": verification_errors,
        "bound_records": records,
        "preflight_blockers": doc.preflight,
        "preflight_clear": not doc.preflight,
        "notes": "bound_records contains only explicitly linked prompts/thinking paths; file names are not inferred.",
        "preflight_rule": f"a {PREFLIGHT_MARKER} preflight discussion item halts the whole logbook; all CLI writes are refused until a human resolves it in the logbook",
    }


def h1_count(doc: Document) -> int:
    return sum(
        1
        for _, line in visible_lines(doc.lines)
        if line is not None and H1_RE.match(line)
    )


def is_logbook(doc: Document) -> bool:
    return (
        h1_count(doc) == 1
        and bool(doc.stages)
        and any(s.is_delivery or s.tasks for s in doc.stages)
    )


def discover(root: Path, project_root: str = "projects") -> list[Path]:
    relative = Path(project_root)
    if relative.is_absolute() or not project_root or ".." in relative.parts:
        raise LbError(f"invalid project root: {project_root}")
    projects = contained_directory(root, root / relative)
    if projects is None:
        return []
    answer: list[Path] = []
    try:
        candidates = sorted(projects.iterdir())
    except OSError as exc:
        raise LbError(f"cannot inspect projects: {exc}") from exc
    for project in candidates:
        try:
            project_resolved = contained_directory(root, project)
            if project_resolved is None:
                continue
            docs = contained_directory(root, project_resolved / "docs")
            if docs is None:
                continue
            for path in sorted(docs.iterdir()):
                try:
                    if path.suffix != ".md":
                        continue
                    resolved = safe_path(root, str(path))
                    if is_logbook(parse(resolved, root)):
                        answer.append(resolved)
                except RuntimeError as exc:
                    raise LbError(
                        f"cannot resolve discovery path {path}: {exc}"
                    ) from exc
                except (OSError, ValueError, LbError):
                    continue
        except RuntimeError as exc:
            raise LbError(f"cannot resolve discovery path {project}: {exc}") from exc
        except (OSError, ValueError, LbError):
            # An external or looping project link is never traversed.
            continue
    return answer


def contained_directory(root: Path, candidate: Path) -> Path | None:
    """Resolve a directory before inspecting it; never traverse an escape."""
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError:
        return None
    except (OSError, RuntimeError) as exc:
        raise LbError(f"cannot resolve directory {candidate}: {exc}") from exc
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    if not resolved.is_dir():
        return None
    return resolved


def local_target(root: Path, document: Path, target: str) -> str:
    parsed = urlparse(target)
    if parsed.scheme in ("http", "https"):
        return "external"
    if parsed.scheme == "file":
        candidate = Path(parsed.path)
    elif parsed.scheme:
        return "external"
    else:
        raw = target.split("#", 1)[0]
        if raw.startswith("~"):
            candidate = Path(os.path.expanduser(raw))
        else:
            candidate = document.parent / raw
    # Reject lexical escapes before resolving a symlink or probing a target.
    lexical = Path(os.path.normpath(str(candidate)))
    try:
        lexical.relative_to(root)
    except ValueError:
        return "outside"
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
        return "ok"
    except (OSError, RuntimeError, ValueError):
        try:
            return "outside" if candidate.exists() else "missing"
        except (OSError, RuntimeError):
            return "outside"


def check(doc: Document) -> list[dict]:
    issues = []
    h1 = h1_count(doc)
    if h1 != 1:
        issues.append(issue(doc, 1, "H1_COUNT", "logbook needs exactly one H1"))
    if not is_logbook(doc):
        issues.append(
            issue(
                doc, 1, "NOT_LOGBOOK", "does not match the conservative logbook shape"
            )
        )
    for stage in doc.stages:
        if stage.is_delivery and not stage.tasks:
            issues.append(
                issue(
                    doc,
                    stage.line,
                    "EMPTY_STAGE",
                    "delivery stage has no tasks; emoji is not derived",
                )
            )
        expected = stage_state(stage)
        if stage.is_delivery and expected and stage.emoji != expected:
            issues.append(
                issue(
                    doc,
                    stage.line,
                    "STAGE_EMOJI",
                    f"expected {expected}, found {stage.emoji or 'none'}",
                )
            )
        if any(t.state == "-" and t.resolution is None for t in stage.tasks):
            issues.append(
                issue(
                    doc,
                    stage.line,
                    "SKIPPED_EXPLICIT",
                    "[-] is an explicit skipped/not-applicable record and is not auto-approved",
                )
            )
        for task in stage.tasks:
            if task.resolution_error:
                issues.append(
                    issue(
                        doc,
                        task.line,
                        "INVALID_RESOLUTION",
                        "resolution must uniquely match this skipped task and cite a decision and reason",
                    )
                )
        for line in stage.unknown_task_lines:
            issues.append(
                issue(
                    doc,
                    line,
                    "UNKNOWN_TASK_STATE",
                    "unknown top-level checkbox state is not a schedulable task",
                )
            )
    for line in doc.comment_tail_lines:
        issues.append(
            issue(
                doc,
                line,
                "COMMENT_STRUCTURE_AMBIGUOUS",
                "structure after a closing HTML comment is not parsed",
            )
        )
    for stage in doc.stages:
        seen: dict[str, list[int]] = {}
        for task in stage.tasks:
            seen.setdefault(task.text, []).append(task.line)
        for text, lines in seen.items():
            if len(lines) > 1 and any(
                task.state != "x" for task in stage.tasks if task.text == text
            ):
                issues.append(
                    issue(
                        doc,
                        lines[1],
                        "DUPLICATE_TASK_TEXT",
                        f"duplicate task text {text!r} appears {len(lines)}x (lines {lines}); CLI writes by stage+task text and will refuse these as ambiguous",
                    )
                )
    for blocker in doc.preflight:
        issues.append(
            issue(
                doc,
                blocker["line"],
                "PREFLIGHT_BLOCKER",
                f"{PREFLIGHT_MARKER} preflight discussion item halts the whole logbook; resolve by human decision before advancing",
            )
        )
    from logbook_cli.link_records import observations, verified_lines

    all_links = links_for(doc)
    verified_links = verified_lines(doc, all_links)
    _, metadata_errors = observations(doc, all_links)
    issues.extend(
        issue(doc, error["line"], "LINK_VERIFICATION_INVALID", error["reason"])
        for error in metadata_errors
    )
    for link in links_for(doc):
        state = local_target(doc.root, doc.path, link["target"])
        if (
            state == "external"
            and (link["line"], link["label"], link["target"]) not in verified_links
        ):
            issues.append(
                issue(doc, link["line"], "LINK_UNVERIFIED", "external link not fetched")
            )
        elif state == "outside":
            issues.append(
                issue(
                    doc,
                    link["line"],
                    "LOCAL_LINK_UNVERIFIED",
                    f"local link outside root: {link['target']}",
                )
            )
        elif state == "missing":
            issues.append(
                issue(
                    doc,
                    link["line"],
                    "LOCAL_LINK_MISSING",
                    f"local link missing: {link['target']}",
                )
            )
    dirs = workdirs(doc)
    for group in dirs:
        if not group["paths"]:
            issues.append(
                issue(
                    doc,
                    group["line"],
                    "DIRECTORY_EMPTY_GROUP",
                    "directory group has no paths",
                )
            )
    issues.extend(directory_issues(doc))
    return issues


def directory_issues(doc: Document) -> list[dict]:
    issues, group_seen = [], False
    for index, line in directory_items(doc):
        if machine_group(line):
            group_seen = True
            continue
        child = re.match(r"^  - `([^`]+)`\s*$", line)
        if child:
            value = child.group(1)
            if not group_seen:
                issues.append(
                    issue(
                        doc,
                        index + 1,
                        "DIRECTORY_GROUP",
                        "directory path appears before a machine group",
                    )
                )
            if not value.startswith(("/", "~/")) or value.endswith("/"):
                issues.append(
                    issue(
                        doc,
                        index + 1,
                        "DIRECTORY_PATH",
                        "directory must be absolute or ~/ path without trailing /",
                    )
                )
        else:
            issues.append(
                issue(
                    doc,
                    index + 1,
                    "DIRECTORY_FORMAT",
                    "expected named or legacy machine group or two-space indented backticked path",
                )
            )
    return issues


def issue(doc: Document, line: int, code: str, message: str) -> dict:
    return {
        "path": str(doc.path.relative_to(doc.root)),
        "line": line,
        "code": code,
        "message": message,
    }


def find_task(doc: Document, stage_name: str, task_text: str) -> Task:
    matches = [
        t
        for s in doc.stages
        if s.title == stage_name
        for t in s.tasks
        if t.text == task_text
    ]
    if len(matches) != 1:
        reason = "no task matched" if not matches else "task match is ambiguous"
        raise LbError(f"{reason}; use exact --stage and --task text", EXIT_REFUSED)
    return matches[0]


def require_token(doc: Document, token: str | None) -> None:
    if not token:
        raise LbError("write commands require --token from context", EXIT_REFUSED)
    if token != doc.token:
        raise LbError(
            "version token differs; reread context before writing", EXIT_REFUSED
        )


def require_preflight_clear(doc: Document) -> None:
    # A 🔮 preflight discussion item halts the whole logbook.  The gate is
    # lifted only by a human editing the logbook text, never by the CLI.
    if doc.preflight:
        where = ", ".join(f"line {b['line']}" for b in doc.preflight)
        raise LbError(
            f"logbook blocked by {PREFLIGHT_MARKER} preflight discussion item(s) at {where}; "
            "resolve by human decision in the logbook before writing",
            EXIT_REFUSED,
        )
