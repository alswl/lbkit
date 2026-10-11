"""Domain values. Markdown spelling and glyphs belong to the format adapter."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum


class TaskState(Enum):
    TODO = "todo"
    IN_PROGRESS = "in-progress"
    DONE = "done"
    SKIPPED = "skipped"


class StageStatus(Enum):
    NOT_STARTED = "not-started"
    IN_PROGRESS = "in-progress"
    SETTLED = "settled"


class Owner(Enum):
    AGENT = "agent"
    HUMAN = "human"


class Field(Enum):
    SKILLS = "skills"
    RESOLUTION = "resolution"
    STATUS = "status"
    ARTIFACT = "artifact"
    BLOCKER = "blocker"
    HANDOFF = "handoff"
    DIRECTORIES = "directories"
    TODO = "todo"


@dataclass(frozen=True)
class TaskAnnotation:
    kind: Field
    value: str
    line: int
    label: str


@dataclass(frozen=True)
class SkillChain:
    names: tuple[str, ...]
    raw: str
    diagnostics: tuple[str, ...] = ()


@dataclass
class Task:
    stage: str
    state: str
    text: str
    line: int
    start: int
    state_at: int
    end: int
    indent: str
    resolution: dict | None = None
    resolution_error: bool = False
    status: TaskState = TaskState.TODO
    owner: Owner = Owner.AGENT
    repositories: list[str] = field(default_factory=list)
    preflight_blocker: bool = False
    action: str | None = None
    annotations: list[TaskAnnotation] = field(default_factory=list)

    @property
    def identity(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()

    @property
    def settled(self) -> bool:
        return self.status is TaskState.DONE or (
            self.status is TaskState.SKIPPED and self.resolution is not None
        )

    @property
    def human(self) -> bool:
        return self.owner is Owner.HUMAN


@dataclass
class Stage:
    title: str
    display: str
    line: int
    heading_start: int
    heading_end: int
    emoji: str | None
    is_delivery: bool
    tasks: list[Task]
    unknown_task_lines: list[int]
    marker_style: str = "emoji"


def derive_stage_status(stage: Stage) -> StageStatus | None:
    if stage.unknown_task_lines:
        return None
    if stage.tasks and all(t.settled for t in stage.tasks):
        return StageStatus.SETTLED
    states = [t.status for t in stage.tasks]
    actionable = [s for s in states if s is not TaskState.SKIPPED]
    if not actionable:
        return StageStatus.IN_PROGRESS if states else None
    if all(s is TaskState.DONE for s in actionable) and TaskState.SKIPPED not in states:
        return StageStatus.SETTLED
    if any(s in (TaskState.DONE, TaskState.IN_PROGRESS) for s in actionable):
        return StageStatus.IN_PROGRESS
    if all(s is TaskState.TODO for s in actionable):
        return StageStatus.NOT_STARTED
    return None
