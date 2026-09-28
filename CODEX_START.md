# Paste this into Codex in the repository

```text
Read AGENTS.md and PLAN.md, then the linked architecture, contracts, role, model,
experiment and runbook documents. This is the specification for implementing
Spark Video Factory on my DGX Spark.

Inspect the current repository and environment first. Preserve my existing
Wan installation, Docker GPU baseline, model cache and uncommitted work.
Work on a new branch if this is a git repository.

Implement M0 through M2 in order, including the tests and real local-AI vertical
slice required by the plan. Do not stop after scaffolding or a mock demo. Do not
build the full dashboard first. Do not rewrite the earlier simple robot animation
and call the studio complete.

Use editable YAML, typed contracts, replaceable local model adapters, a CLI,
SQLite and resumable artifact storage. Enforce zero paid API spend and no automatic
publishing. Keep only one memory-heavy GPU stage active at a time.

First show me the environment findings and the exact proposed model downloads,
their approximate disk requirements and configuration changes. Continue all
CPU implementation without waiting. Once I authorise a download set, do not ask
again for that same set within its configured disk and runtime budgets.

For supported local model execution, build on the known-working NVIDIA PyTorch
container. Resolve routine package issues within an isolated project environment.
Do not change host drivers or replace working host packages without discussing it.

Track progress in docs/PROGRESS.md. When hardware access or a user-selected asset
blocks one gate, finish independent work and provide the exact remaining command
or concrete choice. Report actual tests and samples separately from mocks.

At the end, give me one command to reproduce the first real AI-assisted episode,
its review bundle, measured stage timings, total attempts and the next milestone.
```

M0–M2 are the first implementation assignment. M3–M7 remain the roadmap. The large-download checkpoint exists because the selected revisions and their sizes have not yet been verified, and the user has not yet approved that download set. It must not block ordinary coding or repeated execution of already-authorised models.
