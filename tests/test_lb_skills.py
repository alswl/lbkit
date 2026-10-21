"""Extract planned skill chains against available recipes."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

KIT = Path(__file__).resolve().parents[1]
CLI = KIT / "bin" / "lb"
sys.path.insert(0, str(KIT / "src"))


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
        self.catalog = self.root / "lbkit-skills.yaml"
        self.catalog.write_bytes((KIT / "lbkit-skills.template.yaml").read_bytes())

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), "--root", str(self.root), "skill", *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )

    def entries(self) -> list[dict]:
        return json.loads(self.catalog.read_text(encoding="utf-8"))["skills"]

    def test_extracts_bare_skill_names_from_new_todo_format(self):
        log = self.root / "projects/demo/docs/log.md"
        log.write_text("# Research\n\n## 🛫 Stage 01 Research\n\n- [ ] 验证：访谈依据。\n    - 技能：interview、source-check\n")
        result = self.run_cli("extract", "--json")
        self.assertEqual(result.returncode, 0, result.stderr)
        candidates = json.loads(result.stdout)["candidates"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["chain"], ["interview", "source-check"])

    def add(self, name, *chain, **extra):
        from logbook_cli import configuration as cfg
        config = cfg.decode(self.catalog.read_bytes())
        identity = 'recipe-' + str(len(config['recipes']))
        config['recipes'][identity] = {
            'name': name, 'status': 'available', 'applies_to': [], 'excludes': [],
            'steps': list(chain), 'companions': [
                {'skill': c.partition('=')[0], 'when': c.partition('=')[2]}
                for c in extra.get('companions', [])],
        }
        self.catalog.write_bytes(cfg.encode(config))

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
        self.assertTrue(self.catalog.exists())

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
