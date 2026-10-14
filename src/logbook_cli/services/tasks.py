"""Task use cases; independent of the command framework."""

from logbook_cli.document import (
    EXIT_REFUSED,
    EXIT_USAGE,
    LbError,
    context,
    discover,
    find_task,
    parse,
    root_path,
    safe_path,
)
from logbook_cli.edit import add_task, append_note, resolve_task, rewrite_task
from logbook_cli.format import CHECKBOX
from logbook_cli.models import TaskState
from logbook_cli.services.common import Result, load, save, writable
from logbook_cli.views import task_rows


def list_tasks(
    root: str,
    log: str | None,
    projects_dir: str,
    stage: str | None,
    status: str | None,
    human: bool,
) -> Result:
    base = root_path(root)
    paths = [safe_path(base, log)] if log else discover(base, projects_dir)
    states = {s.value: glyph for glyph, s in CHECKBOX.items()}
    return Result(
        [
            row
            for path in paths
            for row in task_rows(
                parse(path, base),
                stage=stage,
                state=states.get(status) if status else None,
                human=human,
            )
        ]
    )


def next_task(root: str, log: str) -> Result:
    return Result(context(load(root, log))["next_task"])


def add(
    root: str,
    log: str,
    stage: str,
    text: str,
    token: str,
    dry_run: bool,
    before_line: int | None,
    before_task: str | None,
) -> Result:
    if before_line is not None and before_task is not None:
        raise LbError(
            "--before-line and --before-task are mutually exclusive", EXIT_USAGE
        )
    doc = writable(root, log, token)
    changed, line = add_task(doc, stage, text, before_line, before_task)
    return save(doc, changed, dry_run, line=line)


def update(
    root: str, log: str, stage: str, task: str, status: str, token: str, dry_run: bool
) -> Result:
    doc = writable(root, log, token)
    item = find_task(doc, stage, task)
    if item.human and not (item.status is TaskState.TODO and status == "/"):
        raise LbError(
            "refusing to change a human-owned task checkbox except from not-started to in-progress",
            EXIT_REFUSED,
        )
    if status not in CHECKBOX:
        raise LbError("--status must be one of: space, /, x, -", EXIT_USAGE)
    changed = doc.text[: item.state_at] + status + doc.text[item.state_at + 1 :]
    return save(doc, changed, dry_run, line=item.line)


def note(
    root: str,
    log: str,
    stage: str,
    task: str,
    text: str,
    kind: str | None,
    token: str,
    dry_run: bool,
    replace_line: int | None = None,
) -> Result:
    doc = writable(root, log, token)
    changed, line = append_note(
        doc, find_task(doc, stage, task), text, kind, replace_line
    )
    return save(doc, changed, dry_run, line=line)


def rewrite(
    root: str,
    log: str,
    stage: str,
    task: str,
    text: str,
    decision: str,
    token: str,
    dry_run: bool,
) -> Result:
    doc = writable(root, log, token)
    item = find_task(doc, stage, task)
    return save(doc, rewrite_task(doc, item, text, decision), dry_run, line=item.line)


def resolve(
    root: str,
    log: str,
    stage: str,
    task: str,
    disposition: str,
    decision: str,
    note: str,
    token: str,
    dry_run: bool,
) -> Result:
    doc = writable(root, log, token)
    item = find_task(doc, stage, task)
    return save(
        doc,
        resolve_task(doc, item, disposition, decision, note),
        dry_run,
        line=item.line,
    )
