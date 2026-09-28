# Implementation decisions

## Planning records and compilation

The first real trial requested the full EpisodePlan, including repeated opening and closing object states. Its first response took 474.39 seconds and failed the brief-duration gate (15 seconds versus required 20–30). No output was substituted or silently retimed. Bounded repair continues in the same preserved attempt.

A compact `ScriptDraft` contract and `writer-v2.txt` are available for an explicitly recorded subsequent planning attempt if the full-state contract fails. The local model supplies the initial state, actions, durations, hook, causality and payoff. The deterministic compiler derives repeated states and contiguous timestamps without inventing actions or changing durations. This reduces redundant model output while retaining the same EpisodePlan validation. It is not a different model or a mock planner.

## Controlled visual vocabulary

Actions execute sequentially within each shot. State validation covers object IDs, ownership, reach for pickup and continuity. Objects are described in `configs/render-assets.yaml`; the real character layers come from SDXL. White-background alpha keying is explicitly recorded and retains the original image. Camera and expressive animation remain limited; owner playback is required before claiming production quality.

## Review and unknown costs

No output automatically becomes approved or published. Storyboard approval binds to the generated plan hash. Asset selection records source hashes and reviewer. Final package approval binds to media, cover and metadata. Electricity remains null without a wall measurement and tariff; zero applies only to external generation spend.
