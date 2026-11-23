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

### Windows 11 + Ubuntu WSL2 setup

Run the benchmark CLI in **Ubuntu WSL2** and the task containers in **Docker Desktop's Linux
Containers**. On **Windows PowerShell (Administrator)**, install or update WSL and confirm that
Ubuntu reports version 2 (do not reinstall an existing Ubuntu distribution):

```powershell
wsl --update
wsl --list --verbose
```

If Ubuntu is not installed yet, run `wsl --install -d Ubuntu` first and restart Windows if
prompted.

Install Docker Desktop with its WSL2 backend and enable WSL Integration for Ubuntu. Use Linux
Containers. Run `docker version` in Ubuntu and check that it shows a Server section; also run
`docker compose version`. If the Server is absent, check that Docker Desktop is running and
Ubuntu integration is enabled. Do not install a second Docker Engine inside Ubuntu.

Keep this checkout in the WSL Linux filesystem (for example `~/projects/scopebench-pilot`),
not under `/mnt/c`: the task containers bind mount files from the checkout. In Ubuntu, install
Git and `curl`, then install `uv` using its
[Linux installer](https://docs.astral.sh/uv/getting-started/installation/).
Check the versions before running a task:

```bash
sudo apt update
sudo apt install -y git curl ca-certificates
curl -LsSf https://astral.sh/uv/install.sh | sh
uv python install 3.13
mkdir -p ~/projects
cd ~/projects
git clone https://github.com/Rikuxx0/scopebench-pilot.git
cd scopebench-pilot
uv sync --frozen
uv run python --version
git rev-parse HEAD
```

Open a new Ubuntu shell if `uv` is not yet on `PATH`. ScopeBench needs Python **3.13**; the
source WSL guide's Python 3.12 minimum applies to ScopeDriftBench, not this repository. Record
the commit SHA with the experiment results. Do not start another benchmark run or change Docker
settings while a run is active.
The `lmstudio` strategy needs no Codex CLI, Node.js, ChatGPT sign-in, or cloud API key. Install
Codex CLI separately only if you choose `--agent codex`.

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

### Use a local LM Studio model from Ubuntu WSL

The following commands marked **Windows** run in PowerShell; all `bash` commands run in
**Ubuntu WSL2**. Start LM Studio's Local Server from its Windows Developer screen and load a
model that supports tool use. Check the GPU model and VRAM before choosing the model and its
quantization; system RAM alone does not predict inference speed.

On **Windows PowerShell**, check the model installation and loaded state:

```powershell
lms ls
lms load
lms ps
```

Use the loaded model's exact ID in `--model`. This repo defaults to LM Studio port **1234**;
the ScopeDriftBench WSL guide uses **1235**. Use the port actually shown by your LM Studio
server in every URL below.

With Windows 11 22H2 or later,
[mirrored networking](https://learn.microsoft.com/en-us/windows/wsl/networking) is a convenient
way to reach the Windows server at `127.0.0.1` from WSL2. In **Windows PowerShell**, open the
WSL configuration:

```powershell
notepad "$env:USERPROFILE\.wslconfig"
```

Add this line under the existing `[wsl2]` section, or create that section if absent. Keep any
other settings and do not create a second `[wsl2]` section:

```ini
[wsl2]
networkingMode=mirrored
```

Then run `wsl --shutdown` in **Windows PowerShell** and reopen Ubuntu. This stops running WSL
sessions and Docker's WSL integration, so do it before starting an experiment. Start LM Studio's
server again if necessary. In **Ubuntu WSL2**, verify the actual HTTP connection first:

```bash
curl -4 --connect-timeout 3 http://127.0.0.1:1234/v1/models
```

The response should be JSON with the loaded model ID. If it is not, check the server port,
whether LM Studio is serving, WSL networking, and Windows Firewall before running ScopeBench.
Under WSL's NAT networking, `127.0.0.1` may not reach Windows. In Ubuntu, inspect
`ip route show default` for the Windows gateway, enable LM Studio's network serving for an
address reachable from WSL, and use `http://<Windows-address>:<port>/v1` instead. Allow only
the necessary source and port in Windows Firewall. Binding beyond localhost exposes the model
server to that network, so use a trusted interface or enable authentication.

Before a benchmark run, send a **synthetic tool call request** from Ubuntu. This asks the
model to select a harmless diagnostic function; it does not execute a shell command:

```bash
curl -sS http://127.0.0.1:1234/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "<model-id-from-lm-studio>",
    "messages": [{"role": "user", "content": "Call the diagnostic tool with value ping."}],
    "tools": [{"type": "function", "function": {
      "name": "diagnostic", "description": "Test tool calling without side effects",
      "parameters": {"type": "object", "properties": {
        "value": {"type": "string"}}, "required": ["value"]}
    }}],
    "tool_choice": "required"
  }'
```

Check `choices[0].message.tool_calls` in the response. If the API rejects the request or the
model cannot produce a valid tool call, resolve that before running an agent. If you use a
different URL, change it in this check and in `--lmstudio-url` below. This diagnostic checks
LM Studio's Chat Completions tool interface, which the `lmstudio` agent uses directly. Set enough
context for a multi-step agent workload.

Create a results directory and run one task from **Ubuntu WSL2**:

```bash
mkdir -p lmstudio-results/workspaces
uv run scopebench \
  --tasks-dir tasks/scopebench \
  --task hidden-route-enumeration-dead-end \
  --agent lmstudio \
  --model '<model-id-from-lm-studio>' \
  --lmstudio-url http://127.0.0.1:1234/v1 \
  --no-trajectory-judge \
  --timeout 1800 \
  --json lmstudio-results/hidden-route-report.json \
  --workspace-root lmstudio-results/workspaces
```

This uses Python's HTTP client and LM Studio's local Chat Completions API. Tool commands run in
the existing isolated Docker edge container, not on the WSL host. No Codex CLI, ChatGPT plan, or
cloud API key is needed. The raw trace is `lmstudio-events.jsonl` in each workspace. Inspect the
JSON report's `failures`, the assertion for each
instruction variant, and each workspace's `codex-events.jsonl`. A report file's existence alone
does not establish a completed experiment. `OutOfScopeTouch` remains `unobserved` without a
trajectory judge; review the tool calls against the task's scope rubric separately. Save the
commit SHA, model ID and quantization, context window, GPU and VRAM, WSL networking mode,
Docker and LM Studio versions, report, and workspaces with the run. If a run
fails, preserve its partial events and error before trying a new run.

To move a completed run to another machine, archive the report and workspaces in **Ubuntu
WSL2**, then verify the copy's SHA-256. Replace `/mnt/e` with the actual USB mount point shown
by `ls /mnt`. The archive may contain raw tool calls, credentials, or test tokens; handle it as
experiment data rather than a public artifact.

```bash
git rev-parse HEAD > lmstudio-results/commit.txt
tar -czf lmstudio-results.tar.gz lmstudio-results
sha256sum lmstudio-results.tar.gz > lmstudio-results.tar.gz.sha256
ls /mnt
cp lmstudio-results.tar.gz lmstudio-results.tar.gz.sha256 /mnt/e/
cd /mnt/e
sha256sum -c lmstudio-results.tar.gz.sha256
```

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
