# 安装 lbkit

先安装 Python 3.11+、uv、Git 和 mind-forge（`mf`）。在本仓库的一个检出中，用一条命令安装到另一个 Git 仓库：

```sh
./bin/lbkit install --repo /path/to/logbooks --source https://github.com/alswl/lbkit.git
```

当前检出已有 `origin` 远端时可省略 `--source`。先加 `--dry-run` 可以预览全部 Git 与链接操作。

该命令会添加 `.lbkit` 子模块、按 `uv.lock` 创建 `.lbkit/.venv`、链接 CLI / 技能 / 共享文档、在缺失时复制 `lbkit-agents.template.yaml` 为 `lbkit-agents.yaml`、在缺失时生成 `AGENTS.md` 桩（内容为占位协作约定，需按本仓实际规则补充）、创建 `CLAUDE.md -> AGENTS.md` 链接，并在缺失 `minds.yaml` 时初始化 mind-forge 仓库（`minds.yaml` + `projects/`，经 `mf init` 生成；mind-forge 为必需依赖；缺少 mf 或初始化失败会停止安装，不写入共享入口），最后检查 `bin/lb --help`。它拒绝覆盖已有文件，也不会代替你提交或推送任何一个仓库。

### 不依赖单独检出

机器上没有 lbkit 检出时，先在目标仓库手动添加子模块，再从 `.lbkit` 内运行 install：

```sh
cd /path/to/logbooks
git submodule add https://github.com/alswl/lbkit.git .lbkit
./.lbkit/bin/lbkit install
```

install 检测到 `.lbkit` 已是注册的子模块后会跳过 Git 操作，刷新锁定的 CLI 环境，再补链接和模板；`--repo` 默认是当前目录，在仓库根目录运行时可省略。

使用方仓库拥有项目日志、`AGENTS.md`、`lbkit-agents.yaml` 以及可选的 `lbkit-skills.json`；lbkit 拥有共享实现与指令。安装后的链接结构：

```text
.agents/skills/lb-*  -> ../../.lbkit/skills/lb-*
.claude/skills/lb-*  -> ../../.lbkit/skills/lb-*
bin/lb               -> ../.lbkit/bin/lb
bin/lb-anywhere      -> ../.lbkit/bin/lb-anywhere
bin/lbkit            -> ../.lbkit/bin/lbkit
docs/<shared>.md     -> ../.lbkit/docs/installable/<shared>.md
```

只链接入口。CLI 实现（`src/logbook_cli/`）留在 `.lbkit` 子模块内——`bin/lb` 通过自身路径解析到它们。

### 任意目录运行

`bin/lb` 需在仓库根目录运行。若想在任意使用方仓库的任意子目录都能直接敲 `lb`，做一次链接即可：

```sh
ln -s /path/to/repo/bin/lb-anywhere ~/.local/bin/lb
```

wrapper 会向上找到最近的 `bin/lb`，切换到该仓库根目录再执行——执行的永远是该仓库钉住的 lbkit 版本。


## 升级共享文档链接

共享正文迁至 `docs/installable/`，外部入口仍为 `docs/<name>.md`。更新子模块后，先运行安装器的 `--dry-run`，再执行安装。安装器仅替换原来指向 `.lbkit/docs/` 的已知契约链接，不覆盖普通文件或其他符号链接。配置保持原样。

## CLI 依赖

CLI 改用 Click。更新子模块后须重跑安装器，同步 `.lbkit/.venv`。`bin/lb` 使用该环境；普通读取不会自动联网安装。环境缺失时会提示修复命令。安装器本身仍仅依赖 Python 标准库。

开发 lbkit 时，在其检出目录运行 `uv sync --locked`；消费仓自身的 Python 环境独立维护。
