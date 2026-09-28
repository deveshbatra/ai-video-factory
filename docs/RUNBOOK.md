# Target operating runbook

These commands are the desired CLI after Codex implements it. They do not work from the planning archive alone. Implementation must document exact tested installation and container commands, with matching flags and examples.

## Environment setup

1. Open the repo on Spark through VS Code Remote SSH. The Mac need not render.
2. Record git status and existing Docker/PyTorch behaviour before changes.
3. Create an isolated project environment and separate inference image(s). Preserve the working Wan model cache. Resolve exact dependency and model revisions.
4. Copy example configs into ignored local settings and supply actual paths. Keep secrets in the environment; `HF_TOKEN` should be passed to the worker without printing or copying it into snapshots.
5. Run `svf doctor` and review the model registry/download proposal. After the user authorises a bounded download set, enable it and reuse the cache without further prompts for the same set.

Model download authentication can help access/rate limits; it does not make denoising faster. Do not restart an already-successful download just to change authentication.

## First episode — target commands

```bash
svf doctor --config configs/local.yaml
svf validate --config configs/local.yaml --brief examples/episode-brief.yaml
svf plan --config configs/local.yaml --brief examples/episode-brief.yaml
svf enqueue --config configs/local.yaml --episode ep001-the-heavy-key
svf worker --config configs/local.yaml --once
svf review export --episode ep001-the-heavy-key
svf cost report --episode ep001-the-heavy-key
```

`plan` creates a versioned plan record; `enqueue` expands its validated DAG. `worker --once` drains that episode's eligible work until complete or blocked, rather than executing only one arbitrary stage. Commands print the exact artifact path and any required review action. If assets/storyboard need approval, the output explains the concrete missing decision.

Use `svf review approve --episode <id> --stage storyboard` or `--stage assets` for those explicit stage approvals. The final command uses `--stage publish-package` and binds media/metadata hashes. Rejections use `svf review revise --episode <id> --shot <id> --reason <text>` and create a new version.

## Overnight — target commands

```bash
svf enqueue --config configs/local.yaml --brief-dir briefs/approved
svf worker --config configs/local.yaml --until-window-end
svf status
svf review export --batch latest
svf cost report --batch latest
```

Provide a documented detached Docker or user-level systemd wrapper after CLI behaviour is stable. Jobs must continue when the SSH connection closes. Use UID/GID mapping so artifacts belong to the user. Do not require `--privileged` or automatic host-driver changes. Mount only needed project/cache paths.

The scheduling timezone is `Europe/London`; store timestamps in UTC and handle daylight-saving transitions. Use both wall-clock deadlines and monotonic elapsed budgets. Bound in-flight work at the night's hard deadline, saving recoverable state where supported; models without checkpointable sampling restart only their current attempt. Do not promise continuation from an arbitrary denoising step.

## Viewing from the Mac

The finished CLI prints a portable review folder. Copy that folder from Spark with `scp -r spark:<printed-absolute-path> ./review` and open `index.html` locally. The `spark` alias is configured on the Mac; it need not resolve on Spark itself. Alternatively use a localhost server through SSH forwarding once implemented. No public web hosting is required.

## Failure handling

| Symptom | Required behaviour |
| --- | --- |
| OOM or system memory reserve breached | Stop heavy work, record stage and measurements, unload worker; permit one declared fallback within budget |
| Malformed planning JSON | Bounded repair; block with validation errors when exhausted |
| CUDA/kernel/package incompatibility | Keep baseline intact, isolate fixes, mark adapter unsupported until real smoke test |
| Download timeout | Reuse supported cache/resume; never delete all models as a generic fix |
| Disk limit | Stop new work; offer a concrete intermediate cleanup list; preserve finals and original assets |
| Process/host crash | Reconcile leases and artifacts; resume eligible stages, not the entire batch |
| Bad-looking or incoherent clip | Keep failed candidate, request targeted revision; technical success does not approve it |
| Publishing timeout | Mark outcome unknown and reconcile before retrying |

`svf resume --episode <id>` rechecks hashes and dependencies. `svf cancel --episode <id>` cancels pending work and stops active subprocesses safely. A failed stage must not block unrelated eligible episodes unless the failure is a global resource or credentials issue.

## Launch and analytics

MVP exports a package for manual upload. Human checks full playback, title/description, rights, audience designation and applicable disclosure requirements. The general-audience creative hypothesis is not an automatic legal/platform `made for kids` determination; the publisher chooses based on actual content and current guidance.

After manual upload, run `svf publication record --episode <id> --platform youtube --video-id <id>`. Import observations with `svf analytics import --source youtube-csv --file <path>`. Review `svf experiments report --window weekly`.

Only M6 adds actual upload commands. `svf publish --episode <id> --platform youtube --visibility private --dry-run` must show the exact approved package and proposed action first. A real upload/public release requires explicit operator action and credentials. Keep external publishing disabled in default config.

## Implemented M0–M2 commands (2026-09-11)

Use the project-local `.venv/bin/svf`; the earlier target commands for M3+ remain future work. CPU setup:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-cpu.lock
.venv/bin/pip install -e .
.venv/bin/svf doctor --config configs/local.yaml
.venv/bin/pytest -q
```

Authorised model downloads are reproducible with `scripts/download_models.py` inside the preserved Wan image, as described in `docs/ENVIRONMENT.md`. Do not invoke this script for a different download set without reviewing its registry and budget.

`bash scripts/reproduce.sh` enqueues/resumes the first real episode and exports its review bundle once asset selection is available. If it stops at `ASSET_SELECTION_REQUIRED`, inspect both full-video auditions before selecting:

```bash
.venv/bin/svf review select --episode ep001-the-heavy-key --style illustrated_cutout --reviewer Devesh
bash scripts/reproduce.sh
```

The style above is an example, not an owner decision. `detailed_pixel_art` is the other candidate. Final publication is not implemented or automatically invoked. `review approve` records exact package hashes; it performs no external write.

A worker crash may restart only its interrupted sampling attempt; arbitrary denoising/token-generation continuation is not supported. Completed stages are checked by hashes. A stale completion cannot commit after its lease expires. A GPU process additionally holds a kernel lock inside its container until it exits. The global GPU budget reserves runtime before launch and conservatively retains reservations after a crash until reconciled; it must never reset to grant additional unauthorised compute.
