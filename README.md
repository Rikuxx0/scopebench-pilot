# ScopeBench Pilot Extended

## Project Overview

ScopeBench Pilot Extended is an **unofficial, independently maintained extension** of
[Dreadnode ScopeBench Pilot](https://github.com/dreadnode/scopebench-pilot). It retains the
original 30-task pilot from *ScopeBench: Do Agents Preserve Engagement Boundaries Under Goal
Pressure?* (AISec 2026). ScopeBench measures whether an autonomous security agent preserves a
user-defined engagement boundary while pursuing an objective. The pilot is a methodological proof
of concept, separate from the actively developed community benchmark. Its 2,160 published ATIF
trajectories are in the [original dataset](https://huggingface.co/datasets/dreadnode/scopebench-pilot).

The task collection, three instruction conditions per task, verifiers, reference solutions,
sandbox, and grading are retained. The paper's design used 30 tasks, 3 conditions, 8 model
families, and 3 repetitions. See [grading](docs/explanation/scopebench-grading.md) and
[evaluation guidance](docs/scopebench/run-evaluations.md).

## Added Features

### Codex — ChatGPT Authentication

The implemented `--agent codex` strategy launches a locally installed, ChatGPT-signed-in
**Codex CLI** on the host. It uses the CLI's ChatGPT authentication, rather than requiring an
`OPENAI_API_KEY` for the acting agent. Sign in with `codex login` and check with
`codex login status`; availability and usage limits depend on the account and workspace.
`--model` optionally selects a Codex model available to that account. The runner saves
`codex-events.jsonl` in each run workspace. This host-side strategy is different from the
paper's sandboxed baseline agent. The code and mocked tests cover this route; a live account
run has not been verified here. See [OpenAI's Codex plan guidance](https://help.openai.com/en/articles/11369540-using-codex-with-your-chatgpt-plan).

### LM Studio — Local LLM Backend

The implemented `--agent lmstudio` strategy sends requests directly to LM Studio's
OpenAI-compatible **Chat Completions** endpoint at `<base URL>/chat/completions`. It does not
invoke Codex CLI, Node.js, ChatGPT sign-in, or a cloud API key for the acting model. `--model`
is required and must match an ID from LM Studio's `/v1/models`; `--lmstudio-url` selects the
HTTP(S) API base URL. The agent supports structured `bash` tool calls, executes those commands
in an isolated Docker task container, and saves a private `lmstudio-events.jsonl` trace and
optional JSON report. Code and mocked tests cover this route; Windows/WSL connectivity and
individual model behavior are not verified here. See [LM Studio's tool-use documentation](https://lmstudio.ai/docs/developer/openai-compat/tools).

Neither added strategy produces an ATIF trajectory or automatic scope verdict. The examples
disable the trajectory judge; review scoped tool calls against the task rubric. The original
`harness` strategy remains available for paper-oriented evaluations and requires its model
provider key and, for scoped trajectory judging, `ANTHROPIC_API_KEY`.

## Quick Start

Requirements for both strategies: **Python 3.13, uv, Git, and Docker with Compose**. Keep the
checkout on the Linux filesystem when using WSL2.

```sh
git clone https://github.com/Rikuxx0/scopebench-pilot-extended.git
cd scopebench-pilot-extended
uv sync --frozen
uv run scopebench --tasks-dir tasks/scopebench --list
```

Choose a path:

- **Codex + ChatGPT login:** install Codex CLI and sign in, then use the Codex command below.
- **LM Studio + local LLM:** load a tool-capable model and start its local API server, then use
  the LM Studio command below. Codex CLI is not a dependency of this path.
- **Windows / WSL2:** follow the existing [Windows / WSL2 Quick Start](docs/scopebench/quickstart.md#windows-11--ubuntu-wsl2-setup)
  for Docker, networking, both agent paths, and troubleshooting.

Use `uv run scopebench --tasks-dir tasks/scopebench --all --agent dry-run` to check task
orchestration without an acting model. The [CLI reference](docs/reference/scopebench-cli.md)
lists the other supported options.

## Usage Examples

Run from the repository root. A selected task runs all three instruction variants. Docker must
be running. These commands are supported by the current CLI; successful live model execution
depends on the local environment.

**Codex + ChatGPT login** (install and authenticate Codex CLI in the same environment that runs
ScopeBench):

```sh
codex login
codex login status
mkdir -p codex-results
uv run scopebench \
  --tasks-dir tasks/scopebench \
  --task auth-user-export-dead-end \
  --agent codex \
  --no-trajectory-judge \
  --timeout 600 \
  --json codex-results/auth-user-export-report.json \
  --workspace-root codex-results/workspaces
```

**LM Studio + local LLM** (replace the model ID and URL with values shown by your running
LM Studio server; `1235` is this CLI's default, not an LM Studio requirement):

```sh
mkdir -p lmstudio-results
uv run scopebench \
  --tasks-dir tasks/scopebench \
  --task hidden-route-enumeration-dead-end \
  --agent lmstudio \
  --model '<model-id-from-lm-studio>' \
  --lmstudio-url http://127.0.0.1:1235/v1 \
  --no-trajectory-judge \
  --timeout 1800 \
  --json lmstudio-results/hidden-route-report.json \
  --workspace-root lmstudio-results/workspaces
```

Create each report parent directory before running. Inspect `failures` in the JSON report and the
per-run event traces under the workspace root; a report's existence alone does not prove a
successful experiment. See [Inspect results](docs/scopebench/results.md).

## Limitations

- LM Studio speed depends on the model and available hardware.
- Local models vary in structured tool-calling compatibility.
- Results from agent strategies other than the paper's baseline may not be directly comparable
  with the original study.
- Running model inference locally does not make every feature fully offline; external evaluation
  services or other configured integrations can still require network access.

## Documentation and development

Start the documentation site with `uv run --group docs mkdocs serve`. The repository checks are
`uv run ruff check src tests`, `uv run basedpyright`, and `uv run pytest`.

## Original project and credit

- Original Project: Dreadnode ScopeBench Pilot
- Original Repository: [https://github.com/dreadnode/scopebench-pilot](https://github.com/dreadnode/scopebench-pilot)
- Extended Fork: [https://github.com/Rikuxx0/scopebench-pilot-extended](https://github.com/Rikuxx0/scopebench-pilot-extended)

This extension is unofficial and does not imply endorsement or support by Dreadnode. The
original benchmark and research results belong to their original authors. The original
[citation metadata](CITATION.cff), [MIT license](LICENSE), and copyright notice are preserved.
