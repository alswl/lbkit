"""Markdown vocabulary and codecs; all domain decisions use models instead."""

from __future__ import annotations

import re

from logbook_cli.models import Field, Owner, SkillChain, StageStatus, Task, TaskState

CHECKBOX = {
    " ": TaskState.TODO,
    "/": TaskState.IN_PROGRESS,
    "x": TaskState.DONE,
    "-": TaskState.SKIPPED,
}
STAGE_MARKERS = {
    "emoji": {
        StageStatus.NOT_STARTED: "🛫",
        StageStatus.IN_PROGRESS: "🚧",
        StageStatus.SETTLED: "✅",
    },
    "text": {
        StageStatus.NOT_STARTED: "pending",
        StageStatus.IN_PROGRESS: "active",
        StageStatus.SETTLED: "settled",
    },
}
WARNING_MARKERS = ("⚠️", "⚠")
HUMAN_MARKER = "👱"
PREFLIGHT_MARKER = "🔮"
ALARM_MARKER = "🚨"
HUMAN_PREFIXES = ("人工验证：", "Human review:", "Human verification:")
LABELS = {
    "zh": {
        Field.SKILLS: "技能",
        Field.SOURCE: "来源",
        Field.ACCEPTANCE: "验收",
        Field.RESOLUTION: "处置",
        Field.STATUS: "状态",
        Field.ARTIFACT: "产物",
        Field.BLOCKER: "阻塞",
        Field.HANDOFF: "交接",
        Field.DIRECTORIES: "工作目录",
        Field.TODO: "待办",
        Field.LINKS: "相关链接",
    },
    "en": {
        Field.SKILLS: "Skills",
        Field.SOURCE: "Source",
        Field.ACCEPTANCE: "Acceptance",
        Field.RESOLUTION: "Resolution",
        Field.STATUS: "Status",
        Field.ARTIFACT: "Artifact",
        Field.BLOCKER: "Blocker",
        Field.HANDOFF: "Handoff",
        Field.DIRECTORIES: "Working directories",
        Field.TODO: "Todo",
        Field.LINKS: "Related links",
    },
}
ALIASES = {
    label.casefold(): key for labels in LABELS.values() for key, label in labels.items()
}
COLONS = ":："
COLON = {"zh": "：", "en": ": "}
TAIL_SEPARATOR = {"zh": "——", "en": "--"}
SUMMARY_TEXT = {
    "zh": {
        "complete": "全部交付阶段已完成",
        "settled": "全部交付阶段已收口（含取消/不适用项）",
        "pending": "待讨论 {count} 项",
        "next": "下一项：",
        "rewrite": "按裁定改写；",
    },
    "en": {
        "complete": "All delivery stages completed",
        "settled": "All delivery stages settled (including cancelled/not-applicable items)",
        "pending": "{count} pending discussions",
        "next": "Next: ",
        "rewrite": "Rewritten per decision: ",
    },
}
NOTE_FIELDS = (
    Field.ARTIFACT,
    Field.BLOCKER,
    Field.STATUS,
    Field.HANDOFF,
    Field.SOURCE,
    Field.ACCEPTANCE,
    Field.SKILLS,
)
NOTE_KINDS = tuple(
    label
    for labels in LABELS.values()
    for kind, label in labels.items()
    if kind in NOTE_FIELDS
)
MARKER_PATTERN = (
    "(?:"
    + "|".join(
        re.escape(s) for values in STAGE_MARKERS.values() for s in values.values()
    )
    + "|"
    + "|".join(map(re.escape, WARNING_MARKERS))
    + ")"
)
MARKER_RE = re.compile(r"^(" + MARKER_PATTERN + r")\s+")
STATUS_RE = re.compile(
    r"^>\s*("
    + "|".join(re.escape(labels[Field.STATUS]) for labels in LABELS.values())
    + r")([：:]\s*)",
    re.IGNORECASE,
)
PACKAGE_RE = re.compile(r"所属(?:日志与)?检查项|Task reference", re.IGNORECASE)
QUOTE_RE = re.compile(r'「([^」]+)」|"([^"]+)"')


def field_value(text: str) -> tuple[Field, str, str] | None:
    match = re.match(r"^([^:：]+)[：:]\s*(.*)$", text.strip())
    if match and (key := ALIASES.get(match[1].casefold())):
        return key, match[2], match[1]
    return None


def language(text: str) -> str:
    # Explicit metadata wins; prose is only a default for unlabelled documents.
    for line in text.splitlines():
        value = field_value(line.lstrip(" >-*+\t"))
        if value:
            return "zh" if value[2] in LABELS["zh"].values() else "en"
    return "zh" if re.search(r"[\u3400-\u9fff]", text) else "en"


def prefix(kind: Field, locale: str) -> str:
    return LABELS[locale][kind] + COLON[locale]


def marker_style(marker: str | None) -> str:
    return "text" if marker in STAGE_MARKERS["text"].values() else "emoji"


def split_marker(title: str) -> tuple[str, str | None, str]:
    match = MARKER_RE.match(title)
    if not match:
        return title, None, "emoji"
    return title[match.end() :], match[1], marker_style(match[1])


def task_metadata(task: Task) -> None:
    task.status = CHECKBOX[task.state]
    task.owner = (
        Owner.HUMAN
        if HUMAN_MARKER in task.text or task.text.startswith(HUMAN_PREFIXES)
        else Owner.AGENT
    )
    task.repositories = re.findall(r"(?<!\w)@([\w.-]+)", task.text)
    task.preflight_blocker = PREFLIGHT_MARKER in task.text
    action = re.match(r"^([^：:\s]+)[：:]", task.text)
    task.action = action[1] if action else None


def skill_chain(value: str) -> SkillChain:
    """Parse the entire value, never harvest only the recognizable fragments."""
    rest = value.strip()
    names = []
    while rest:
        match = re.match(r"(?:`/?([\w.-]+)`|/?([\w.-]+))", rest)
        if not match:
            return SkillChain((), value, ("Invalid skill name or chain syntax",))
        names.append(match[1] or match[2])
        rest = rest[match.end() :].strip()
        # A trailing parenthesized condition is commentary, not another skill.
        if re.fullmatch(r"（[^（）]*）|\([^()]*\)", rest):
            rest = ""
        if not rest:
            return SkillChain(tuple(names), value)
        sep = re.match(r"(?:、|,|，|→|->)\s*", rest)
        if not sep or not rest[sep.end() :]:
            return SkillChain(
                (), value, ("Invalid separator or incomplete skill chain",)
            )
        rest = rest[sep.end() :]
    return SkillChain((), value, ("Empty skill chain",))


def machine_group(line: str) -> dict | None:
    if not line.startswith("- "):
        return None
    raw = line.rstrip()
    if raw == "- local":
        return {"machine": "local", "machine_name": None, "group_kind": "local"}
    legacy = re.fullmatch(r"- remote `([^`]+)`", raw)
    named = re.fullmatch(r"- `([^`]+)`", raw)
    match = legacy or named
    if match and match[1].strip() == match[1] and match[1]:
        return {
            "machine": raw[2:],
            "machine_name": match[1],
            "group_kind": "remote" if legacy else "named",
        }
    return None
