"""Recoverable publication of a replacement Task and its dependency graph."""

import json
import os

from logbook_cli import state, task_identity, unified
from logbook_cli.document import EXIT_REFUSED, LbError
from logbook_cli.repository import markdown_document, source_digest
from logbook_cli.services import dependencies
from logbook_cli.storage import replace_bytes_at

SUFFIX = ".dependencies-transaction.json"


def journal_for(run):
    return run.with_suffix(SUFFIX)


def present(run):
    journal = journal_for(run)
    return journal.is_symlink() or journal.exists()


def replace_file(path, after, before):
    if before == after:
        return
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        replace_bytes_at(fd, path.name, after, before)
    finally:
        os.close(fd)


def _changes(root, log, run, data, run_id):
    try:
        row = json.loads(data, object_pairs_hook=state.unique_object)
        if (
            set(row)
            != {"run_id", "document_before", "graph_before", "document", "graph"}
            or row["run_id"] != run_id
        ):
            raise ValueError("invalid dependency transaction identity or fields")
        document = row["document"].encode()
        task_ids = set(task_identity.bindings(markdown_document(document, log, root)))
        graph = unified.encode(row["graph"])
        dependencies.decode(graph, run_id, task_ids)
    except (AttributeError, TypeError, ValueError, KeyError) as exc:
        raise LbError("invalid dependency transaction", EXIT_REFUSED) from exc

    changes = []
    for target, after, expected in (
        (log, document, row["document_before"]),
        (dependencies.sidecar(run), graph, row["graph_before"]),
    ):
        current = state.read_regular(root, target)
        if current != after and source_digest(current) != expected:
            raise LbError(
                f"subsequent edit prevents recovery: {target.name}", EXIT_REFUSED
            )
        changes.append((target, after, current))
    return changes


def _finish(journal, changes):
    for target, after, before in changes:
        replace_file(target, after, before)
    directory = os.open(journal.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.unlink(journal.name, dir_fd=directory)
        os.fsync(directory)
    finally:
        os.close(directory)


def publish(doc, run, run_id, changed, graph):
    """Record both after-images before replacing either target under the Run lock."""
    journal = journal_for(run)
    data = unified.encode(
        {
            "run_id": run_id,
            "document_before": source_digest(doc.data),
            "graph_before": source_digest(
                state.read_regular(doc.root, dependencies.sidecar(run))
            ),
            "document": changed,
            "graph": dependencies.envelope(run_id, graph),
        }
    )
    changes = _changes(doc.root, doc.path, run, data, run_id)
    replace_file(journal, data, None)
    _finish(journal, changes)


def recover(root, log, expected, dry_run):
    """Recheck both images before rolling an interrupted replacement forward."""
    with unified.writer(root, log, dry_run):
        run, record = unified.locate(
            root, log, required=True, recovering_dependencies=True
        )
        if (
            state.section(log, root) != record["identity"]["log_path"]
            or "dependency_source" not in record
        ):
            raise LbError(
                "recover the dependency transaction from its Run Logbook", EXIT_REFUSED
            )
        journal = journal_for(run)
        data = state.read_regular(root, journal)
        changes = _changes(root, log, run, data, record["identity"]["run_id"])
        token = source_digest(data)
        if not dry_run:
            if expected != token:
                raise LbError(
                    "use log recover --dry-run and its version_token", EXIT_REFUSED
                )
            _finish(journal, changes)
        return {
            "version_token": token,
            "dry_run": dry_run,
            "recovered": not dry_run,
            "files": [str(target.relative_to(root)) for target, _, _ in changes],
        }
