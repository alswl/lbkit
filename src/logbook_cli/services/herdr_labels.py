"""One-operation display naming, independent of logical agent identity."""

from logbook_cli import configuration
from logbook_cli.document import EXIT_REFUSED, LbError


def prefix(root):
    try:
        settings = configuration.resolve(root)["settings"]
    except LbError as exc:
        raise LbError(exc.message, EXIT_REFUSED) from exc
    runtime = settings.get("runtime", {})
    policy = runtime.get("herdr", {})
    if not isinstance(policy, dict):
        raise LbError("settings.runtime.herdr must be a mapping", EXIT_REFUSED)
    value = policy.get("label_prefix", "")
    if not isinstance(value, str) or any(c in value for c in "\r\n\x00"):
        raise LbError(
            "settings.runtime.herdr.label_prefix must be single-line text", EXIT_REFUSED
        )
    return value


def expected(prefix, base):
    return base if base.startswith(prefix) else prefix + base


def resource(value, kind):
    result = value.get("result", {})
    item = result.get(kind, {}) if isinstance(result, dict) else {}
    return item if isinstance(item, dict) else {}


class LabelFailure(LbError):
    def __init__(self, reason, stage, policy):
        super().__init__(reason, EXIT_REFUSED)
        self.stage = stage
        self.policy = {**policy, "status": "failed", "reason": reason}


def apply(invoke, kind, identity, prefix, base=None, already_named=False):
    policy = {
        "status": "not_required",
        "resource_kind": kind,
        "resource_id": identity,
        "expected_label": None,
        "observed_label": None,
    }
    if not prefix:
        return policy
    if not isinstance(identity, str) or not identity:
        raise LabelFailure("identity_missing", "identity", policy)

    def read():
        try:
            item = resource(invoke(kind, "get", identity), kind)
            if item.get(kind + "_id") != identity:
                raise ValueError("readback identity differs")
            return item
        except (LbError, ValueError, TypeError, AttributeError) as exc:
            raise LabelFailure("label_read_failed", "verify", policy) from exc

    if base is None:
        item = read()
        fields = (
            ("label",)
            if kind == "tab"
            else ("label", "title", "terminal_title_stripped")
        )
        base = next(
            (
                item[k]
                for k in fields
                if isinstance(item.get(k), str) and (kind == "tab" or item[k])
            ),
            None,
        )
        if base is None:
            if kind == "tab":
                raise LabelFailure("label_read_failed", "verify", policy)
            base = identity
    label = expected(prefix, base)
    policy["expected_label"] = label
    if not already_named:
        try:
            invoke(kind, "rename", identity, label)
        except LbError as exc:
            raise LabelFailure("label_write_failed", "rename", policy) from exc
    item = read()
    policy["observed_label"] = item.get("label")
    if item.get("label") != label:
        raise LabelFailure("label_mismatch", "verify", policy)
    return {**policy, "status": "verified"}
