# lbkit

This repository contains shared Logbook instructions, templates, and tools. When mounted as `.lbkit/`, read the consuming repository's `../AGENTS.md` for its owner, authorized working directories, project rules, and runtime configuration. Those local rules govern project work. Shared contracts are in `contracts/`, executable skill workflows in `skills/` — both are for consuming repositories. Documentation about lbkit itself is in `dev-docs/`.

Do not write project goals, change an existing task's text or order, or infer execution authorization from the presence of a template or tool. The consuming repository supplies its own `.agents/lb.yaml`; lbkit does not choose a model or deployment for it.
