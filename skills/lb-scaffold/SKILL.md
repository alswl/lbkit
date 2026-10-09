---
name: lb-scaffold
version: 0.1.0
description: Initialize a new logbook by fill-in from a run-instance template under workflows/<workflow>/: fill only the three mutable slots — target date, working directories, and run rulings — collected in one pass; no free drafting, no changing structural granularity; once the three essentials are complete and human-confirmed, hand off to lb-push. With no template, or when goals and structure must change, go to lb-plan instead — this skill does not apply.
---

# Initialize a run instance from a workflow template

Fill in the blanks; do not design. The precondition is that `workflows/<workflow>/` provides a run-instance template (todo manifest, front matter, goal template sentence, and established rulings); with no template, or when the human wants to change goals, scope, or structure, switch to [lb-plan](../lb-plan/SKILL.md). This skill does not dispatch execution.

## Prerequisites

1. Read the [configuration contract](../../docs/configuration.md) to resolve documents; read the [lb-plan planning workflow](../lb-plan/references/planning.md) (template-first clause), the [logbook format](../../docs/logbook-format.md), and the [document adapter workflow](../lb-update/references/document-adapters.md).
2. Locate the template: the article with the 「运行实例模板」 section under `workflows/<name>/docs/`, along with its prompt contract. If the workflow does not exist, or the template section or established rulings are missing, stop and state the gap; never ghost-write the template and never switch to free drafting.

## Required workflow

1. Resolve the mutable slots: target date (default: yesterday), working directories (checked against the on-site state), and run rulings (default: carry over all of the template's 「既定裁定」). Ask only about slots with no default or that conflict with the on-site state; collect answers with one compact numbered list instead of asking item by item.
2. Fill in and generate the main logbook: front matter, title, file naming, date placeholders, and the todo manifest are each replaced per the template — never restate the skill's own workflow, add or drop todos, adjust granularity, touch manual gates, or write wave notes (`🔀` convention follows the template and the logbook format). The goal sentence comes from the template: once the template is human-confirmed and finalized, that counts as its writing; when the human rewrites it on the instance, their wording governs.
3. Companion records: thinking records the source (workflow and `prev-run` instance), slot values, and where each ruling came from; register bindings and the project index per the document adapter.
4. After writing, run `check --json`; `LINK_UNVERIFIED` for external URLs is an expected notice, not a structural error to fix.
5. Wrap-up: show a summary of the filled slot values (not a full restatement) and ask the human for a quick confirm. Once the three essentials (working directories, stage breakdown, todo manifest) are complete and confirmed, exit is granted; advancement is handed to lb-push.

## Boundaries

- Only create new instances; modifying an existing logbook goes to lb-update, replanning to lb-plan.
- Never change the `workflows/` templates themselves; record discovered template defects in the conversation and let the human fix the template.
- For scheduling, authorization, and listener boundaries, AGENTS.md and the corresponding skills govern; the existence of a template does not exempt this skill from confirmation — it only collapses confirmation into one round of slot-value review.
