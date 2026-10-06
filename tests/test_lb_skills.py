"""lb skills: optional lbkit-skills.json list, add and extract."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
CLI = KIT / "scripts" / "lb.py"
sys.path.insert(0, str(KIT / "src"))

from logbook_cli import skills  # noqa: E402

LOG = """# Demo

## 🛫 Stage 01 Build

- [x] 设计：写 spec。 @demo
    - 技能：`speckit-specify` → `speckit-plan` → `speckit-tasks`, `/spec-report`
- [ ] 开发：画图并改文。 @demo
    - 技能：`mf-cli`、`excalidraw-diagram`（仅重绘）
- [ ] 开发：再实现一次。 @demo
    - 技能：`speckit-implement`
- [ ] 无前缀任务
    - 技能：`ignored`

```
- [ ] 开发：围栏内不算
    - 技能：`fenced`
```
"""


class SkillsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        docs = self.root / "projects" / "demo" / "docs"
        docs.mkdir(parents=True)
        (docs / "log.md").write_text(LOG, encoding="utf-8")
        sources = self.root / "projects" / "demo" / "sources"
        sources.mkdir()
        (sources / "wp-draw.md").write_text(
            "# 画图工作包\n\n所属日志与检查项：Stage 01 · 「开发：画图并…」\n\n用 d2 重绘。\n",
            encoding="utf-8",
        )
        self.catalog = self.root / "lbkit-skills.json"

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), "--root", str(self.root), "skills", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def entries(self) -> list[dict]:
        return json.loads(self.catalog.read_text(encoding="utf-8"))["skills"]

    def test_missing_catalog_lists_nothing(self):
        result = self.run_cli("--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"skills": []})

    def add(self, name, *chain, scope="范围", **extra):
        args = ["add", "--name", name, "--scope", scope]
        for skill in chain:
            args += ["--chain", skill]
        for action in extra.get("actions", []):
            args += ["--action", action]
        for companion in extra.get("companions", []):
            args += ["--companion", companion]
        if "description" in extra:
            args += ["--description", extra["description"]]
        if extra.get("dry_run"):
            args.append("--dry-run")
        return self.run_cli(*args)

    def test_add_creates_file_and_filters_by_action_hint(self):
        self.add(
            "speckit 实现", "speckit-implement", actions=["开发"],
            companions=["comment-prune=实现完成、提交前"],
        )
        result = self.add(
            "前端页面", "frontend-design",
            scope="适用：新页面；不适用：改样式",
            description='"引号"\\ 保留',
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            self.entries(),
            [
                {
                    "name": "speckit 实现",
                    "scope": "范围",
                    "chain": ["speckit-implement"],
                    "actions": ["开发"],
                    "companions": [{"skill": "comment-prune", "when": "实现完成、提交前"}],
                },
                {
                    "name": "前端页面",
                    "scope": "适用：新页面；不适用：改样式",
                    "chain": ["frontend-design"],
                    "description": '"引号"\\ 保留',
                },
            ],
        )
        names = lambda *a: [e["name"] for e in json.loads(self.run_cli(*a, "--json").stdout)["skills"]]
        self.assertEqual(names(), ["speckit 实现", "前端页面"])
        self.assertEqual(names("--action", "开发"), ["speckit 实现"])
        raw = self.catalog.read_text(encoding="utf-8")
        self.assertIn('"chain": ["speckit-implement"],', raw)
        self.assertIn('"companions": [\n        {\n          "skill": "comment-prune",', raw)
        text = self.run_cli().stdout
        self.assertIn("范围：适用：新页面", text)
        self.assertIn("随行：comment-prune（实现完成、提交前）", text)

    def test_new_file_references_schema_and_add_keeps_it(self):
        self.add("a", "x")
        self.assertEqual(
            json.loads(self.catalog.read_text(encoding="utf-8"))["$schema"],
            ".lbkit/schemas/lbkit-skills.schema.json",
        )
        self.catalog.write_text('{"$schema": "custom.json", "skills": []}', encoding="utf-8")
        self.add("b", "y")
        self.assertEqual(json.loads(self.catalog.read_text(encoding="utf-8"))["$schema"], "custom.json")

    def test_schema_file_matches_validator(self):
        path = KIT / skills.SCHEMA_REF.removeprefix(".lbkit/")
        schema = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(set(schema["properties"]), {"$schema", "skills"})
        kind = schema["$defs"]["kind"]
        self.assertEqual(set(kind["properties"]), skills.FIELDS)
        self.assertEqual(set(kind["required"]), {*skills.REQUIRED, "chain"})
        self.assertEqual(set(kind["properties"]["companions"]["items"]["required"]), {"skill", "when"})

    def test_add_refuses_duplicate_name_and_dry_run_does_not_write(self):
        result = self.add("a", "x", dry_run=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["added"]["chain"], ["x"])
        self.assertFalse(self.catalog.exists())
        self.add("a", "x")
        before = self.catalog.read_bytes()
        self.assertEqual(self.add("a", "y").returncode, 4)
        self.assertEqual(self.catalog.read_bytes(), before)
        self.assertEqual(self.add("b", "x").returncode, 0)

    def test_invalid_catalog_is_reported(self):
        ok = {"name": "a", "scope": "s", "chain": ["x"]}
        for value in (
            {"skills": [{**ok, "extra": 1}]},
            {"skills": [{**ok, "chain": []}]},
            {"skills": [{**ok, "scope": ""}]},
            {"skills": [{**ok, "actions": "开发"}]},
            {"skills": [{**ok, "companions": [{"skill": "x"}]}]},
            {"skills": [{**ok, "companions": ["x"]}]},
            {"skills": [ok, ok]},
            {"skills": [], "other": 1},
            [],
        ):
            with self.subTest(value=value):
                self.catalog.write_text(json.dumps(value), encoding="utf-8")
                result = self.run_cli("--json")
                self.assertEqual(result.returncode, 3)
                self.assertEqual(result.stdout, "")
        self.catalog.write_text("{", encoding="utf-8")
        self.assertEqual(self.run_cli("--json").returncode, 3)

    def test_extract_keeps_raw_line_task_and_work_packages(self):
        result = self.run_cli("extract", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        found = json.loads(result.stdout)["candidates"]
        self.assertEqual(
            [(c["action"], c["chain"], c["done"]) for c in found],
            [
                ("设计", ["speckit-specify", "speckit-plan", "speckit-tasks", "spec-report"], True),
                ("开发", ["mf-cli", "excalidraw-diagram"], False),
                ("开发", ["speckit-implement"], False),
            ],
        )
        draw = found[1]
        self.assertEqual(draw["raw"], "`mf-cli`、`excalidraw-diagram`（仅重绘）")
        self.assertEqual(draw["task"], "开发：画图并改文。 @demo")
        self.assertEqual(draw["source"], "projects/demo/docs/log.md:8")
        self.assertEqual(draw["work_packages"], ["projects/demo/sources/wp-draw.md"])
        self.assertEqual(found[0]["work_packages"], [])
        self.assertFalse(self.catalog.exists())

    def test_extract_skips_chains_covered_by_an_entry(self):
        self.add("speckit 实现", "speckit-implement")
        self.add(
            "speckit 设计", "speckit-specify", "speckit-plan", "speckit-tasks", "speckit-analyze",
            companions=["spec-report=审阅时"],
        )
        self.add("配图", "excalidraw-diagram")
        found = json.loads(self.run_cli("extract", "--json").stdout)["candidates"]
        self.assertEqual([c["chain"] for c in found], [["mf-cli", "excalidraw-diagram"]])


if __name__ == "__main__":
    unittest.main()
