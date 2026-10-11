"""Stage related-link use cases."""

from logbook_cli.edit import add_link, rewrite_links
from logbook_cli.services.common import Result, save, writable


def add(root: str, log: str, stage: str, link: str, token: str, dry_run: bool) -> Result:
    doc = writable(root, log, token)
    changed, line = add_link(doc, stage, link)
    return save(doc, changed, dry_run, line=line)


def rewrite(
    root: str, log: str, old: str, new: str, token: str, dry_run: bool
) -> Result:
    doc = writable(root, log, token)
    changed, rewritten = rewrite_links(doc, old, new)
    return save(doc, changed, dry_run, rewritten=rewritten)
