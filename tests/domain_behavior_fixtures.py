"""Materialize synthetic model-evaluation inputs; never include grader assertions."""

import subprocess
from pathlib import Path

from click.testing import CliRunner
from test_domain_commands import DomainTest
from test_lifecycle_operations import OperationsTest


def build(root: Path, case: int):
    root.mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", str(root)], check=True)
    subject = DomainTest()
    subject.root = root
    subject.log = root / "log.md"
    subject.thinking = root / "thinking.md"
    subject.runner = CliRunner()
    subject.log.write_text(
        "# Demo\n\nGoal: Deliver the approved result.\n\n## 🛫 Stage 01 Build\n\n- [ ] Build @core\n- [ ] Review 👱\n"
    )
    subject.thinking.write_text("# Thinking\n\nHuman notes stay.\n")
    (root / "evidence").mkdir()
    (root / "evidence/result.md").write_text(
        "# Candidate report\n\ncandidate-a: required checks PASS.\n"
    )
    subject.identify()
    subject.state("active")
    if case == 2:
        subject.transition("start")
        subject.json_file(
            "result.json",
            {"candidate": "candidate-a", "evidence": ["evidence/result.md"]},
        )
        subject.transition("record-result", "--input-file", "result.json")
        subject.log.write_text(
            subject.log.read_text().replace(
                "Build @core", "Build with an additional security check @core"
            )
        )
    if case in (3, 6):
        subject.transition("start")
        subject.json_file(
            "dispatch.json",
            dict(
                id="d1",
                task_id="build",
                owner="sailor",
                scope="build",
                exclusions="publication",
                inputs="source",
                completion="checks pass",
                escalation="blocked",
            ),
        )
        subject.dispatch_call("create", "--input-file", "dispatch.json")
        if case == 3:
            for status in ("sent", "acknowledged"):
                subject.dispatch_call(
                    "set-status",
                    "d1",
                    "--status",
                    status,
                    "--basis",
                    "executor receipt",
                )
            subject.dispatch_call(
                "attempt",
                "d1",
                "a1",
                "--status",
                "started",
                "--basis",
                "executor started",
            )
            subject.state("paused")
            (root / "observation.md").write_text(
                "Sailor reports: attempt a1 interrupted after the project pause; candidate remains incomplete. Execution handed back to Captain. No new work authorized.\n"
            )
        else:
            subject.json_file(
                "binding.json",
                dict(
                    machine="local",
                    workspace_id="w1",
                    tab_id="w1:t9",
                    pane_id="w1:p7",
                    agent_id="builder",
                    session_id="previous-session",
                    observed_at="2026-01-01T00:00:00Z",
                    basis="previous verified observation",
                ),
            )
            subject.call(
                "agent",
                "bind",
                "log.md",
                "d1",
                "--thinking",
                "thinking.md",
                "--input-file",
                "binding.json",
                "--expect-version",
                subject.token("thinking.md"),
            )
            fake = root / "fake-bin"
            fake.mkdir()
            (fake / "herdr").write_text("""#!/usr/bin/env python3
import json,sys
from pathlib import Path
with (Path(__file__).parent.parent/'runtime-calls.jsonl').open('a') as f: f.write(json.dumps(sys.argv[1:])+'\\n')
args=sys.argv[1:]
if args[:2]==['pane','get']:
 print(json.dumps({'result':{'pane':{'workspace_id':'w1','tab_id':'w1:t9','pane_id':'w1:p7','agent_status':'idle'}}}))
elif args[:2]==['agent','get']:
 print(json.dumps({'result':{'agent':{'name':'builder','agent_status':'idle'}}}))
elif args[:2]==['pane','read']: print('Builder idle. No pending user input.')
else: sys.exit(4)
""")
            (fake / "herdr").chmod(0o755)
    if case == 4:
        path = OperationsTest.make_workflow(subject)
        content = path.read_text()
        for old, new in [
            ("运行实例模板", "Run-instance template"),
            ("既定裁定", "Established rulings"),
            ("槽", "Slot"),
            ("标题：", "Title:"),
            ("目标：", "Goal:"),
            ("工作目录：", "Working directories:"),
        ]:
            content = content.replace(old, new)
        path.write_text(content)
        subject.call(
            "workflow",
            "set-status",
            "example",
            "--status",
            "available",
            "--basis",
            "human reviewed template",
            "--expect-version",
            subject.call("workflow", "show", "example")["version_token"],
        )
        subject.json_file(
            "inputs.json",
            dict(
                date="2026-01-01",
                working_directories="- local\n  - `/approved/example`",
                rulings={"SUBJECT": "Report"},
            ),
        )
    if case == 5:
        for name in ("example-docs", "example-check"):
            path = root / "skills" / name / "SKILL.md"
            path.parent.mkdir(parents=True)
            path.write_text(
                f"---\nname: {name}\nversion: 1.0\ndescription: Fixture local work.\n---\nUse local files only.\n"
            )
        subject.log.write_text(
            subject.log.read_text().replace(
                "- [ ] Review",
                "    - Artifact: [Required report](https://example.invalid/report)\n- [ ] Review",
            )
        )
        subject.json_file(
            "returns.json",
            [
                dict(
                    id="u1",
                    task_id="build",
                    skill="example-docs",
                    state="declared",
                    outcome="unknown",
                    basis="Sailor planned this skill; no invocation reported",
                    at="2026-01-01T00:00:00Z",
                ),
                dict(
                    id="u2",
                    task_id="build",
                    skill="example-check",
                    state="invoked",
                    outcome="unknown",
                    basis="Sailor invoked this skill; outcome not observed",
                    at="2026-01-01T00:01:00Z",
                ),
            ],
        )
    if case == 8:
        from logbook_cli import configuration as cfg

        value = {
            "version": "0.2.0",
            "settings": {"default_agent": "local-builder"},
            "agents": {
                "local-builder": {
                    "status": "available",
                    "description": "Human description",
                    "launcher": {"command": "never-run-this-launcher", "args": []},
                    "model": "original-model",
                    "deployment": "external",
                    "suitable_for": ["documentation"],
                }
            },
        }
        (root / "lbkit-skills.yaml").write_bytes(
            cfg.encode(
                {
                    "version": "0.2.0",
                    "recipes": {
                        "documentation": {
                            "status": "available",
                            "applies_to": ["documentation"],
                            "excludes": [],
                            "steps": ["example-docs"],
                            "companions": [],
                        }
                    },
                }
            )
        )
        path = root / "lbkit.yaml"
        path.write_bytes(cfg.encode(value))
        (root / "stale-token.txt").write_text(cfg.digest(path.read_bytes()))
        path.write_text(
            path.read_text()
            + '# Human concurrent note\ncustom_extension: "Keep this quote"\n'
        )
        (root / "patch.yaml").write_text("model: revised-model\n")
    return subject


def install_entries(root: Path, candidate: Path, include_skills: bool):
    """Reproduce consumer links while keeping graders outside the subject root."""
    import shutil

    local_kit = root / '.lbkit'
    local_kit.mkdir()
    shutil.copytree(candidate / "schemas", local_kit / "schemas")
    for name in ("README.md", "VERSION", "lbkit.template.yaml"):
        shutil.copy2(candidate / name, local_kit / name)
    (local_kit / "src").symlink_to(candidate / "src", target_is_directory=True)
    shutil.copytree(candidate / 'docs/installable', local_kit / 'docs/installable')
    (local_kit / 'bin').symlink_to(candidate / 'bin', target_is_directory=True)
    (root / 'bin').mkdir()
    for name in ('lb', 'lbkit'):
        (root / 'bin' / name).symlink_to(Path('../.lbkit/bin') / name)
    if (root / "fake-bin").is_dir():
        entry = root / "bin/lb"
        entry.unlink()
        entry.write_text(
            "#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\n"
            "root=Path(__file__).resolve().parents[1]\n"
            "os.environ['PATH']=str(root/'fake-bin')+os.pathsep+os.environ.get('PATH','')\n"
            "os.environ['HERDR_ENV']='1'\n"
            f"os.execv({str(candidate / 'bin/lb')!r}, [{str(candidate / 'bin/lb')!r}, *sys.argv[1:]])\n"
        )
        entry.chmod(0o755)
    (root / 'docs').mkdir()
    for source in (local_kit / 'docs/installable').glob('*.md'):
        (root / 'docs' / source.name).symlink_to(Path('../.lbkit/docs/installable') / source.name)
    if include_skills:
        shutil.copytree(candidate / 'skills', local_kit / 'skills', ignore=shutil.ignore_patterns('evals', '__pycache__'))
        entries = root / '.agents/skills'
        entries.mkdir(parents=True)
        for source in (local_kit / 'skills').glob('lb-*'):
            (entries / source.name).symlink_to(Path('../../.lbkit/skills') / source.name, target_is_directory=True)
        # Check physical resolution, not a text match against source-relative paths.
        for source in entries.iterdir():
            (source / '../../docs/installable/configuration.md').resolve(strict=True)
        assert not list((local_kit / 'skills').rglob('evals'))
        # Reproduce the consumer's installed entry instructions, not grader hints.
        instructions = (candidate / "AGENTS.template.md").read_text()
        entries_section = instructions.split("## Entry Points by Task\n", 1)[1]
        entries_section = entries_section.split("Ordinary execution requires", 1)[0]
        host_instructions = root / "AGENTS.md"
        with host_instructions.open("a") as stream:
            stream.write("\n## Entry Points by Task\n" + entries_section)
