"""Stage related-link use cases."""

from logbook_cli.edit import add_link, rewrite_links
from logbook_cli.services.common import Result, save, writable


def add(
    root: str, log: str, stage: str, link: str, token: str, dry_run: bool
) -> Result:
    doc = writable(root, log, token)
    changed, line = add_link(doc, stage, link)
    return save(doc, changed, dry_run, line=line)


def rewrite(
    root: str, log: str, old: str, new: str, token: str, dry_run: bool
) -> Result:
    doc = writable(root, log, token)
    changed, rewritten = rewrite_links(doc, old, new)
    return save(doc, changed, dry_run, rewritten=rewritten)


def verify(
    root: str,
    log: str,
    line: int,
    target: str,
    label: str,
    observed_at: str,
    observer: str,
    basis: str,
    outcome: str,
    token: str,
    dry_run: bool,
    bind_stage: str | None = None,
    bind_task: str | None = None,
    result_identity: str | None = None,
) -> Result:
    from logbook_cli.document import EXIT_REFUSED, EXIT_USAGE, LbError, links_for
    from logbook_cli.link_records import (
        OUTCOMES,
        comment_records,
        digest,
        encode,
        local_digest,
        occurrence,
        task_binding,
        timestamp,
    )

    if outcome not in OUTCOMES:
        raise LbError("invalid observation outcome", EXIT_USAGE)
    if bool(bind_stage) != bool(bind_task):
        raise LbError("--bind-stage and --bind-task are required together", EXIT_USAGE)
    values = (target, label, observed_at, observer, basis)
    if any(not v.strip() or "\n" in v or "\r" in v for v in values):
        raise LbError("observation values must be nonempty single lines", EXIT_USAGE)
    if result_identity is not None and (
        not result_identity.strip()
        or "\n" in result_identity
        or "\r" in result_identity
    ):
        raise LbError("result identity must be a nonempty single line", EXIT_USAGE)
    try:
        timestamp(observed_at)
    except ValueError as exc:
        raise LbError(str(exc), EXIT_USAGE) from exc
    doc = writable(root, log, token)
    links = links_for(doc)
    matches = [
        link
        for link in links
        if (link["line"], link["target"], link["label"]) == (line, target, label)
    ]
    if len(matches) != 1:
        raise LbError("missing or ambiguous visible link", EXIT_REFUSED)
    location = occurrence(doc, matches[0])
    if (
        sum(occurrence(doc, other)["anchor"] == location["anchor"] for other in links)
        != 1
    ):
        raise LbError("ambiguous semantic link occurrence", EXIT_REFUSED)
    bound = location["task"]
    if bind_stage and bind_task:
        explicit = {"stage": bind_stage, "text": bind_task}
        if bound and explicit != bound:
            raise LbError("cannot redirect a task-contained link", EXIT_REFUSED)
        bound = explicit
    try:
        binding = task_binding(doc, bound["stage"], bound["text"]) if bound else None
    except ValueError as exc:
        raise LbError(str(exc), EXIT_REFUSED) from exc
    old_records, _, safe_end = comment_records(doc)
    if not safe_end:
        raise LbError(
            "no safe document-level metadata insertion position", EXIT_REFUSED
        )
    record = dict(
        target=target,
        label=label,
        anchor=location["anchor"],
        binding=binding,
        bound_task=bound,
        observed_at=observed_at,
        observer=observer,
        basis=basis,
        outcome=outcome,
        result_identity=result_identity,
    )
    fingerprint = local_digest(doc, target)
    if fingerprint:
        record["local_digest"] = fingerprint
    record["record_id"] = digest(record)
    newline = "\r\n" if b"\r\n" in doc.data else "\n"
    changed = doc.text
    if not any(r["record_id"] == record["record_id"] for r in old_records):
        changed += (
            ("" if changed.endswith(("\n", "\r")) else newline)
            + newline
            + encode(record)
            + newline
        )
    return save(doc, changed, dry_run, record_id=record["record_id"])
