"""Explicit Claude native callbacks; no terminal or transcript fallback."""

import asyncio
import fcntl
import hashlib
import json
import os
import socket
import stat
import time
from contextlib import contextmanager
from pathlib import Path

from logbook_cli import observation, state, storage
from logbook_cli.document import EXIT_REFUSED, LbError

ENVIRONMENT = "LBKIT_CLAUDE_QUESTION_DIR"
PROTOCOL = "claude-code-hooks-v1"
WIRE_LIMIT = 64 * 1024
RECORD_LIMIT = 16 * 1024
QUESTION_LIMIT = 4096
QUESTION_RECORDS = 1024



def failure(category, detail):
    return LbError(category + ": " + detail, EXIT_REFUSED)


def digest(value):
    return hashlib.sha256(observation.encode(value)).hexdigest()


def key(*values):
    return digest(values)


def identifier(value):
    return (
        isinstance(value, str) and 0 < len(value) <= 512
        and not any(c in value for c in "\n\r\x00")
    )


@contextmanager
def runtime():
    configured = os.environ.get(ENVIRONMENT)
    if not configured:
        raise failure("capability_unavailable", "native question protocol not configured")
    path = Path(configured)
    if not path.is_absolute() or ".." in path.parts:
        raise failure("capability_unavailable", "native runtime requires an absolute directory")
    directory = None
    try:
        directory = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        info = os.fstat(directory)
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise failure("capability_unavailable", "native runtime must be owner-only")
        if len(os.fsencode(path / ("0" * 64 + ".sock"))) >= 104:
            raise failure("capability_unavailable", "native runtime path is too long")
        yield path, directory
    except OSError as exc:
        raise failure("capability_unavailable", "native runtime directory unavailable") from exc
    finally:
        if directory is not None:
            os.close(directory)


def capabilities():
    if not os.environ.get(ENVIRONMENT):
        return None
    try:
        with runtime():
            pass
    except LbError:
        return {"available": False, "reason": "unsafe_native_question_runtime"}
    return {
        "available": True, "protocol": PROTOCOL, "runtimes": ["claude"],
        "confirmation": "native_PostToolUse", "transport_fallback": False,
    }


def raw(directory, name):
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise failure("capability_unavailable", "unsafe native runtime record") from exc
    with os.fdopen(fd, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise failure("capability_unavailable", "unsafe native runtime record")
        value = handle.read(RECORD_LIMIT + 1)
    if len(value) > RECORD_LIMIT:
        raise failure("capacity_exceeded", "native runtime record exceeds bound")
    return value


def record(directory, name):
    value = raw(directory, name)
    if value is None:
        return None
    try:
        result = json.loads(value, object_pairs_hook=state.unique_object)
        if not isinstance(result, dict):
            raise ValueError("object required")
        return result
    except ValueError as exc:
        raise failure("capability_unavailable", "invalid native runtime record") from exc


@contextmanager
def locked(directory, name, *, nonblocking=False):
    flags = os.O_RDWR | os.O_NOFOLLOW
    try:
        fd = os.open(name, flags | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=directory)
    except FileExistsError:
        fd = os.open(name, flags, dir_fd=directory)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise failure("capability_unavailable", "unsafe native runtime lock")
        deadline = time.monotonic() + (0 if nonblocking else 2)
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError as exc:
                if time.monotonic() >= deadline:
                    raise failure("capability_unavailable", "native runtime lock busy") from exc
                time.sleep(0.01)
        yield
    finally:
        os.close(fd)


def save(directory, name, value):
    data = observation.encode(value)
    if len(data) > RECORD_LIMIT:
        raise failure("capacity_exceeded", "native runtime record exceeds bound")
    with locked(directory, "records.lock"):
        previous = raw(directory, name)
        if previous == data:
            return
        if previous is None and name.startswith("m-"):
            # Every metadata record reserves one eventual native receipt.
            count = sum(n.startswith("m-") and n.endswith(".json") for n in os.listdir(directory))
            if count >= QUESTION_RECORDS:
                raise failure("capacity_exceeded", "native runtime receipt capacity exhausted")
        storage.replace_bytes_at(directory, name, data, previous)


def current_binding(session_id, pane_id=None):
    from logbook_cli.adapters import herdr

    pane_id = pane_id or os.environ.get("HERDR_PANE_ID")
    if not pane_id:
        raise failure("identity_missing", "native hook requires its actual caller pane")
    scope = herdr.invoke("local", "status", "--json")["server"]
    pane = herdr.invoke("local", "pane", "get", pane_id)["result"]["pane"]
    agent = herdr.invoke("local", "agent", "get", pane_id)["result"]["agent"]
    if agent.get("agent") != "claude":
        raise failure("capability_unavailable", "worker has no Claude native callback")
    observed = herdr.binding_observation(
        {"machine": "local", "server": scope.get("session") or "default"}, pane, agent
    )["binding"]
    if observed["session_id"] != session_id:
        raise failure("identity_changed", "native session differs from its live binding")
    return observed


def question(payload, event):
    if (
        payload.get("hook_event_name") != event
        or payload.get("tool_name") != "AskUserQuestion"
        or not identifier(payload.get("tool_use_id"))
        or not identifier(payload.get("session_id"))
    ):
        raise failure("identity_missing", "matching native question callback required")
    tool_input = payload.get("tool_input")
    values = tool_input.get("questions") if isinstance(tool_input, dict) else None
    return validate_questions(values)


def validate_questions(values):
    if (
        not isinstance(values, list) or not 1 <= len(values) <= 4
        or any(not isinstance(q, dict) or not identifier(q.get("question")) for q in values)
        or len({q["question"] for q in values}) != len(values)
        or len(observation.encode(values)) > QUESTION_LIMIT
    ):
        raise failure("capability_unavailable", "native question shape or bound unsupported")
    return values


def revision(question_id, values):
    return digest({"question_id": question_id, "questions": values})


def answers(value, values):
    if isinstance(value, str) and len(values) == 1:
        value = {values[0]["question"]: value}
    if (
        not isinstance(value, dict) or set(value) != {q["question"] for q in values}
        or any(not isinstance(v, str) or not v.strip() for v in value.values())
        or len(observation.encode(value)) > RECORD_LIMIT
    ):
        raise failure("invalid_transition", "answer must match native question text")
    return value


def receive(connection):
    data = bytearray()
    deadline = time.monotonic() + 1
    while len(data) <= WIRE_LIMIT:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise failure("capability_unavailable", "native callback frame timed out")
        connection.settimeout(remaining)
        part = connection.recv(min(4096, WIRE_LIMIT + 1 - len(data)))
        if not part:
            break
        data.extend(part)
        if b"\n" in part:
            break
    try:
        if len(data) > WIRE_LIMIT or not data.endswith(b"\n"):
            raise ValueError("bounded newline frame required")
        value = json.loads(data, object_pairs_hook=state.unique_object)
        if not isinstance(value, dict):
            raise ValueError("object required")
        return value
    except ValueError as exc:
        raise failure("invalid_transition", "invalid native callback frame") from exc


def rpc(path, binding, request):
    endpoint = path / (key(binding) + ".sock")
    try:
        info = endpoint.lstat()
        if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
            raise failure("capability_unavailable", "unsafe native callback endpoint")
        data = observation.encode({**request, "binding": binding})
        if len(data) > WIRE_LIMIT:
            raise failure("capacity_exceeded", "native callback request exceeds bound")
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(2)
            connection.connect(str(endpoint))
            connection.sendall(data)
            value = receive(connection)
    except OSError as exc:
        raise failure("capability_unavailable", "native question callback unavailable") from exc
    if "error" in value:
        allowed = {"identity_changed", "invalid_transition", "capacity_exceeded", "capability_unavailable"}
        category = value["error"] if isinstance(value["error"], str) and value["error"] in allowed else "capability_unavailable"
        raise failure(category, "native question callback refused")
    return value


def verify_live(binding):
    if binding.get("machine") != "local":
        raise failure("capability_unavailable", "native callback supports local workers only")
    if current_binding(binding["session_id"], pane_id=binding["pane_id"]) != binding:
        raise failure("identity_changed", "native worker binding changed")


async def observe_native(binding, deadline):
    """Read a live native wait without blocking the event loop or extending its budget."""
    if not os.environ.get(ENVIRONMENT) or binding.get("machine") != "local":
        return None
    writer = None
    try:
        with runtime() as (path, _):
            endpoint = path / (key(binding) + ".sock")
            info = endpoint.lstat()
            if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                return None
            async with asyncio.timeout(max(0, min(1, deadline - time.monotonic()))):
                reader, writer = await asyncio.open_unix_connection(str(endpoint), limit=WIRE_LIMIT + 1)
                writer.write(observation.encode({"binding": binding, "action": "inspect"}))
                await writer.drain()
                data = await reader.readline()
                if len(data) > WIRE_LIMIT:
                    return None
                value = json.loads(data, object_pairs_hook=state.unique_object)
                validate_description(binding, value)
                return {
                    "id": value["question_id"], "revision": value["revision"],
                    "questions": value["questions"], "protocol": PROTOCOL,
                }
    except (LbError, OSError, ValueError, TimeoutError):
        return None
    finally:
        if writer is not None:
            writer.close()


def validate_description(binding, value):
    if not isinstance(value, dict) or value.get("binding") != binding or value.get("protocol") != PROTOCOL:
        raise failure("identity_changed", "native question belongs to another binding")
    values = validate_questions(value.get("questions"))
    if not identifier(value.get("question_id")) or value.get("revision") != revision(value["question_id"], values):
        raise failure("identity_changed", "native question description is invalid")


def inspect(binding, request):
    with runtime() as (path, _):
        verify_live(binding)
        value = rpc(path, binding, {"action": "inspect"})
    validate_description(binding, value)
    for field in ("question_id", "revision"):
        if field in request and request[field] != value[field]:
            raise failure("identity_changed", "native question or revision changed")
    if "answer" in request:
        answers(request["answer"], value["questions"])
    return value


def submit(binding, request):
    with runtime() as (path, _):
        verify_live(binding)
        response = rpc(path, binding, {"action": "answer", **request})
    if response != {"accepted": True}:
        raise failure("delivery_unresolved", "native answer acceptance is unknown")
    # Callback acceptance is not proof that the native tool has executed.


def confirm(binding, answer, timeout=2):
    deadline = time.monotonic() + timeout
    with runtime() as (_, directory):
        if not all(identifier(answer.get(field)) for field in ("question_id", "id", "answer_digest")):
            raise failure("invalid_transition", "native confirmation requires a complete intent")
        name = "r-" + key(binding, answer["question_id"], answer["id"]) + ".json"
        while True:
            value = record(directory, name)
            if value is not None:
                receipt = value.get("receipt")
                if (
                    value.get("binding") != binding
                    or value.get("operation_id") != answer["id"]
                    or value.get("protocol") != PROTOCOL or value.get("source") != "PostToolUse"
                    or not isinstance(receipt, dict)
                    or receipt.get("question_id") != answer["question_id"]
                    or receipt.get("answer_digest") != answer["answer_digest"]
                ):
                    raise failure("identity_changed", "native confirmation differs from intent")
                return receipt
            if time.monotonic() >= deadline:
                raise failure("delivery_unresolved", "native confirmation not yet available")
            time.sleep(0.025)


def pre_tool(payload, timeout=120):
    values = question(payload, "PreToolUse")
    if payload["tool_input"].get("answers"):
        return {}
    with runtime() as (path, directory):
        binding = current_binding(payload["session_id"])
        # Keep publication bound to the callback even if the binding reader changes.
        if binding["session_id"] != payload["session_id"]:
            raise failure("identity_changed", "native hook session changed")
        question_id = payload["tool_use_id"]
        rev = revision(question_id, values)
        endpoint = path / (key(binding) + ".sock")
        bound = False
        with locked(directory, key(binding) + ".lock", nonblocking=True):
            try:
                if endpoint.exists():
                    info = endpoint.lstat()
                    if not stat.S_ISSOCK(info.st_mode) or info.st_uid != os.getuid():
                        raise failure("capability_unavailable", "unsafe native callback endpoint")
                    endpoint.unlink()
                with socket.socket(socket.AF_UNIX) as server:
                    server.bind(str(endpoint))
                    bound = True
                    os.chmod(endpoint, 0o600)
                    server.listen(2)
                    server.settimeout(0.1)
                    deadline = time.monotonic() + min(timeout, 600)
                    while time.monotonic() < deadline:
                        try:
                            connection, _ = server.accept()
                        except TimeoutError:
                            continue
                        with connection:
                            connection.settimeout(1)
                            try:
                                request = receive(connection)
                                if request.get("binding") != binding or current_binding(payload["session_id"]) != binding:
                                    raise failure("identity_changed", "native binding changed")
                                if request.get("action") == "inspect":
                                    connection.sendall(observation.encode({
                                        "binding": binding, "question_id": question_id,
                                        "revision": rev, "questions": values, "protocol": PROTOCOL,
                                        "live_verified": True, "confirmation_supported": True,
                                    }))
                                    continue
                                if set(request) != {
                                    "action", "binding", "question_id", "revision",
                                    "operation_id", "answer", "answer_digest",
                                }:
                                    raise failure("invalid_transition", "invalid native answer request")
                                if request["action"] != "answer" or request["question_id"] != question_id or request["revision"] != rev:
                                    raise failure("identity_changed", "native question or revision changed")
                                if not identifier(request["operation_id"]) or request["answer_digest"] != digest(request["answer"]):
                                    raise failure("invalid_transition", "native operation or answer digest differs")
                                selected = answers(request["answer"], values)
                                save(directory, "m-" + key(binding, question_id) + ".json", {
                                    "binding": binding, "question_id": question_id,
                                    "revision": rev, "operation_id": request["operation_id"],
                                    "answer_digest": request["answer_digest"],
                                    "answers_digest": digest(selected), "protocol": PROTOCOL,
                                })
                                connection.sendall(observation.encode({"accepted": True}))
                                return {"hookSpecificOutput": {
                                    "hookEventName": "PreToolUse", "permissionDecision": "allow",
                                    "permissionDecisionReason": "Matching explicitly configured native question operation",
                                    "updatedInput": {"questions": values, "answers": selected},
                                }}
                            except LbError as exc:
                                connection.sendall(observation.encode({"error": exc.message.split(":", 1)[0]}))
            finally:
                if bound:
                    endpoint.unlink(missing_ok=True)
    return {}


def post_tool(payload):
    values = question(payload, "PostToolUse")
    with runtime() as (_, directory):
        binding = current_binding(payload["session_id"])
        if binding["session_id"] != payload["session_id"]:
            raise failure("identity_changed", "native hook session changed")
        question_id = payload["tool_use_id"]
        metadata = record(directory, "m-" + key(binding, question_id) + ".json")
        if metadata is None:
            return {}
        response = payload.get("tool_response", {})
        if (
            metadata.get("binding") != binding or metadata.get("question_id") != question_id
            or metadata.get("revision") != revision(question_id, values)
            or metadata.get("protocol") != PROTOCOL
            or not isinstance(response, dict) or response.get("questions") != values
            or digest(response.get("answers")) != metadata.get("answers_digest")
            or digest(payload["tool_input"].get("answers")) != metadata.get("answers_digest")
        ):
            raise failure("identity_changed", "native tool result does not match answer intent")
        receipt = {
            "receipt_id": "claude-native-" + key(binding, question_id, metadata["operation_id"]),
            "outcome": "confirmed", "question_id": question_id,
            "answer_digest": metadata["answer_digest"],
            "evidence": ["claude-hooks:PostToolUse:" + question_id],
        }
        save(directory, "r-" + key(binding, question_id, metadata["operation_id"]) + ".json", {
            "binding": binding, "operation_id": metadata["operation_id"],
            "protocol": PROTOCOL, "source": "PostToolUse", "receipt": receipt,
        })
    return {}
