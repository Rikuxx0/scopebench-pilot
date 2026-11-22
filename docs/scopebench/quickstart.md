---
description: Install the frozen ScopeBench pilot and exercise its bundled tasks.
---

# Quickstart

Run these commands from the repository root. The task collection is already included under
`tasks/scopebench`; no separate task checkout is required.

## Install

Requirements are Python 3.13, [uv](https://docs.astral.sh/uv/), Docker, and Docker Compose.

```bash
uv sync --frozen
docker compose version
```

List the frozen collection:

```bash
uv run scopebench --tasks-dir tasks/scopebench --list
```

The output should contain 30 task directories and three instruction variants per task.

## Run the controls

The clean-environment control runs no agent:

```bash
uv run scopebench \
  --tasks-dir tasks/scopebench \
  --all \
  --agent dry-run
```

Every verifier should remain unsatisfied. In the report this appears as a raw-capability assertion
failure and scoped inverse-assertion passes; the important control result is that no clean
environment already contains the objective certificate.

The positive control executes each task's frozen `solution.sh`:

```bash
uv run scopebench \
  --tasks-dir tasks/scopebench \
  --all \
  --agent solution
```

Healthy raw-capability cases pass. Healthy scoped cases fail their inverted assertion because the
solution deliberately reaches the out-of-scope objective. A case under report `failures` indicates
an environment, verifier, or runner problem rather than a scope outcome.

## Run one measured case

### Use a ChatGPT-signed-in Codex CLI without an API key

If `codex login status` reports `Logged in using ChatGPT`, the optional `codex` strategy can
run against a task using that account's Codex plan allowance. No `OPENAI_API_KEY` or
`ANTHROPIC_API_KEY` is needed when the trajectory judge is disabled:

```bash
uv run scopebench \
  --tasks-dir tasks/scopebench \
  --task auth-user-export-dead-end \
  --agent codex \
  --no-trajectory-judge \
  --timeout 600
```

This runs the Codex CLI on the host against the task's temporary published ports. It uses the
Codex agent, not the paper's Pydantic AI baseline. Codex events and completed shell commands are
saved in each run workspace as `codex-events.jsonl`; this is not an ATIF trajectory or an
automatic scope verdict. The report labels out-of-scope observation as `unobserved`.
The host-side Codex sandbox is `workspace-write` with network access so it can reach the task.
Use this mode to try tasks locally, not to reproduce the measured pilot results. `--model` may
select a Codex model available to the signed-in account; otherwise Codex uses its own default.
If your account has Daybreak access enabled, add `--daybreak` to request it for this run.

### Use the bundled baseline agent

List supported model identifiers and required API-key variables:

```bash
uv run scopebench --list-models
```

Set the acting-model key and `ANTHROPIC_API_KEY` for the fixed trajectory judge. Then select one
task and preserve its raw trajectory:

```bash
uv run scopebench \
  --tasks-dir tasks/scopebench \
  --task auth-user-export-dead-end \
  --model anthropic:claude-sonnet-4-6 \
  --request-limit 100 \
  --timeout 3600 \
  --atif \
  --json scopebench-smoke.json
```

The first measured run may build the agent image. ScopeBench creates one case for each of the
task's three instruction conditions.

Continue with [Run evaluations](run-evaluations.md) for the full design and
[Inspect results](results.md) for result interpretation.
