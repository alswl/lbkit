"""Thin native argv forwarding with a bounded set of managed creation forms."""

import json

import click

from logbook_cli.adapters import herdr as native
from logbook_cli.commands.common import resolve_root
from logbook_cli.document import EXIT_REFUSED, LbError, root_path
from logbook_cli.services import herdr_labels as labels


def classify(argv):
    index = 0
    while index < len(argv):
        token = argv[index]
        if token in {"--machine", "--session"}:
            if index + 1 >= len(argv) or argv[index + 1].startswith("-"):
                return None
            index += 2
        elif token.startswith(("--machine=", "--session=")):
            if not token.split("=", 1)[1]:
                return None
            index += 1
        else:
            break
    path = tuple(argv[index : index + 2])
    if path not in {("tab", "create"), ("pane", "split")}:
        return None
    kind = path[0]
    # Native help must work even when no consumer configuration exists.
    if any(t in {"--help", "-h", "--version", "-V"} for t in argv[index + 2 :]):
        return None
    values = {"--cwd", "--env"}
    flags = {"--focus", "--no-focus"}
    if kind == "tab":
        values |= {"--workspace", "--label"}
    else:
        values |= {"--pane", "--direction", "--ratio", "--right-click"}
        flags.add("--current")
    seen = set()
    positionals = 0
    label = None
    cursor = index + 2
    while cursor < len(argv):
        token = argv[cursor]
        key, equal, value = token.partition("=")
        if key in values:
            if key in seen and key != "--env":
                return (kind, None)
            seen.add(key)
            value_index = cursor
            if not equal:
                cursor += 1
                if cursor >= len(argv) or argv[cursor].startswith("-"):
                    return (kind, None)
                value, value_index = argv[cursor], cursor
            if key == "--label":
                label = (value_index, bool(equal), value)
        elif token in flags:
            if token in seen:
                return (kind, None)
            seen.add(token)
        elif not token.startswith("-") and kind == "pane":
            positionals += 1
        else:
            return (kind, None)
        cursor += 1
    if {"--focus", "--no-focus"} <= seen or positionals > 1:
        return (kind, None)
    if positionals + int("--pane" in seen) + int("--current" in seen) > 1:
        return (kind, None)
    return kind, {"selectors": argv[:index], "label": label}


def run(argv, capture=False):
    try:
        result = native.invoke_native(argv, capture=capture)
        return result
    except OSError as exc:
        click.echo("lb-herdr: native executable unavailable", err=True)
        raise click.exceptions.Exit(
            127 if isinstance(exc, FileNotFoundError) else 126
        ) from exc


def exit_code(code):
    return code if code >= 0 else 128 - code


def write(stream, data):
    stream.write(data)
    stream.flush()


@click.command(
    "herdr",
    context_settings={
        "ignore_unknown_options": True,
        "allow_interspersed_args": False,
        "help_option_names": [],
    },
)
@click.argument("argv", nargs=-1, required=True, type=click.UNPROCESSED)
def herdr(argv):
    """Forward native Herdr argv; apply consumer display policy to tab/pane creation."""
    argv = list(argv)
    classified = classify(argv)
    if classified is None or classified[1] is None:
        if classified is not None:
            click.echo(
                "lb-herdr: configuration_not_applied: arguments forwarded; label policy not applied or verified",
                err=True,
            )
        raise click.exceptions.Exit(exit_code(run(argv).returncode))
    kind, parsed = classified
    prefix = labels.prefix(root_path(resolve_root(None)))
    if not prefix:
        raise click.exceptions.Exit(exit_code(run(argv).returncode))
    explicit = parsed["label"]
    base = explicit[2] if explicit else None
    if explicit:
        index, equal, _ = explicit
        argv[index] = ("--label=" if equal else "") + labels.expected(prefix, base)
    created = run(argv, capture=True)
    write(click.get_binary_stream("stdout"), created.stdout)
    write(click.get_binary_stream("stderr"), created.stderr)
    if created.returncode:
        raise click.exceptions.Exit(exit_code(created.returncode))
    identity, owned = None, []
    try:
        value = json.loads(created.stdout)
        item = labels.resource(value, kind)
        identity = item.get(kind + "_id")
        if not isinstance(identity, str) or not identity:
            identity = None
        root_pane = labels.resource(value, "root_pane").get("pane_id")
        if isinstance(root_pane, str) and root_pane:
            owned = [root_pane]
        if kind == "pane" and identity:
            owned = [identity]
    except (ValueError, AttributeError, TypeError):
        pass

    def invoke(*args):
        try:
            result = run([*parsed["selectors"], *args], capture=True)
        except click.exceptions.Exit as exc:
            raise LbError("native label operation unavailable", EXIT_REFUSED) from exc
        if result.returncode:
            raise LbError("native label operation failed", EXIT_REFUSED)
        try:
            return json.loads(result.stdout)
        except (ValueError, TypeError) as exc:
            raise LbError("invalid native label response", EXIT_REFUSED) from exc

    try:
        labels.apply(invoke, kind, identity, prefix, base, already_named=bool(explicit))
    except labels.LabelFailure as exc:
        click.echo(
            "lb-herdr: "
            + json.dumps(
                {
                    "reason": exc.message,
                    "stage": exc.stage,
                    "resource_kind": kind,
                    "resource_id": identity,
                    "owned_panes": owned,
                    "retry_safe": False,
                }
            ),
            err=True,
        )
        raise click.exceptions.Exit(4) from exc
