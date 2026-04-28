# Bypass-path audit

Generated: 2026-04-28T15:35:00
Window: last 60 days
Bypass rows found: 634

## Summary by bypass kind

| Bypass kind | Count | Mean downstream score | Example |
|---|---:|---:|---|
| `data.critique_policy.bypass_reason` | 131 | n/a | sage `1197c5e2bcd7`  plan_critiqued |
| `data.critique_policy.bypass_recorded` | 131 | n/a | sage `1197c5e2bcd7`  plan_critiqued |
| `data.critique_policy.bypass_recorded_at` | 131 | n/a | sage `1197c5e2bcd7`  plan_critiqued |
| `data.critique_policy.bypass_requested` | 131 | n/a | sage `1197c5e2bcd7`  plan_critiqued |
| `event_text` | 110 | n/a | sage `023c399a19fb`  orchestrate_run_completed |

## Examples

| Timestamp | Brand | Workflow | Version | Kind | Stage/event | What it bypassed | Actor | Score |
|---|---|---|---|---|---|---|---|---:|
| 2026-04-24T22:40:44 | sage | `023c399a19fb` |  | `event_text` | orchestrate/orchestrate_run_completed | Inspiration-readiness block: hybrid mode requires extracted inspiration, but sources are configured and unextracted. Run `bgen extract-inspiration` and `bgen consolidate-inspiration` before planning, or pass --allow-blocking to record a bypass.; inspiration: Inspiration sources are configured but not extracted yet: pentagram, pentagram-poster-house, gretel-work, koto-pairpoint; → Run: bgen extract-inspiration --category <category> --sources pentagram,pentagram-poster-house,gretel-work,koto-pairpoint |  | None |
| 2026-04-25T21:51:12 | sage | `03f3f1908b8d` |  | `event_text` | orchestrate/orchestrate_run_completed | Learnings block: hybrid mode has been underperforming for this material recently. Switch to the winning setup from learnings.json, or pass --allow-blocking to record a bypass. |  | None |
| 2026-04-27T12:04:03 | sage | `1197c5e2bcd7` |  | `data.critique_policy.bypass_requested` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:04:03 | sage | `1197c5e2bcd7` |  | `data.critique_policy.bypass_recorded` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:04:03 | sage | `1197c5e2bcd7` |  | `data.critique_policy.bypass_reason` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:04:03 | sage | `1197c5e2bcd7` |  | `data.critique_policy.bypass_recorded_at` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:04:03 | sage | `1197c5e2bcd7` |  | `event_text` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T08:33:18 | sage | `1e74a8ac1a8d` |  | `event_text` | orchestrate/orchestrate_run_completed | Learnings block: hybrid mode has been underperforming for this material recently. Switch to the winning setup from learnings.json, or pass --allow-blocking to record a bypass. |  | None |
| 2026-04-23T21:44:56 | sage | `20697de3a180` |  | `event_text` | validate/validate_run_completed | Inspiration-readiness block: hybrid mode requires extracted inspiration, but sources are configured and unextracted. Run `bgen extract-inspiration` and `bgen consolidate-inspiration` before planning, or pass --allow-blocking to record a bypass.; inspiration: Inspiration sources are configured but not extracted yet: pentagram, pentagram-poster-house, gretel-work, koto-pairpoint; → Run: bgen extract-inspiration --category <category> --sources pentagram,pentagram-poster-house,gretel-work,koto-pairpoint |  | None |
| 2026-04-24T01:47:08 | sage | `2406235af44e` |  | `event_text` | validate/validate_run_completed | Inspiration-readiness block: hybrid mode requires extracted inspiration, but sources are configured and unextracted. Run `bgen extract-inspiration` and `bgen consolidate-inspiration` before planning, or pass --allow-blocking to record a bypass.; inspiration: Inspiration sources are configured but not extracted yet: pentagram, pentagram-poster-house, gretel-work, koto-pairpoint; → Run: bgen extract-inspiration --category <category> --sources pentagram,pentagram-poster-house,gretel-work,koto-pairpoint |  | None |
| 2026-04-26T16:04:44 | sage | `2c078a5eac06` |  | `event_text` | orchestrate/orchestrate_run_completed | Learnings block: hybrid mode has been underperforming for this material recently. Switch to the winning setup from learnings.json, or pass --allow-blocking to record a bypass. |  | None |
| 2026-04-26T07:37:51 | sage | `2ea9930e8b8d` |  | `data.critique_policy.bypass_requested` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-26T07:37:51 | sage | `2ea9930e8b8d` |  | `data.critique_policy.bypass_recorded` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-26T07:37:51 | sage | `2ea9930e8b8d` |  | `data.critique_policy.bypass_reason` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-26T07:37:51 | sage | `2ea9930e8b8d` |  | `data.critique_policy.bypass_recorded_at` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-26T07:37:51 | sage | `2ea9930e8b8d` |  | `event_text` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-26T07:37:51 | sage | `2ea9930e8b8d` |  | `data.critique_policy.bypass_requested` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-26T07:37:51 | sage | `2ea9930e8b8d` |  | `data.critique_policy.bypass_recorded` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-26T07:37:51 | sage | `2ea9930e8b8d` |  | `data.critique_policy.bypass_reason` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-26T07:37:51 | sage | `2ea9930e8b8d` |  | `data.critique_policy.bypass_recorded_at` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-26T16:11:19 | sage | `329c385af683` |  | `data.critique_policy.bypass_requested` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-26T16:11:19 | sage | `329c385af683` |  | `data.critique_policy.bypass_recorded` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-26T16:11:19 | sage | `329c385af683` |  | `data.critique_policy.bypass_reason` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-26T16:11:19 | sage | `329c385af683` |  | `data.critique_policy.bypass_recorded_at` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-26T16:11:19 | sage | `329c385af683` |  | `event_text` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-26T16:11:19 | sage | `329c385af683` |  | `data.critique_policy.bypass_requested` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-26T16:11:19 | sage | `329c385af683` |  | `data.critique_policy.bypass_recorded` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-26T16:11:19 | sage | `329c385af683` |  | `data.critique_policy.bypass_reason` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-26T16:11:19 | sage | `329c385af683` |  | `data.critique_policy.bypass_recorded_at` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-24T22:41:06 | sage | `48e2dc736830` |  | `event_text` | orchestrate/orchestrate_run_completed | Inspiration-readiness block: hybrid mode requires extracted inspiration, but sources are configured and unextracted. Run `bgen extract-inspiration` and `bgen consolidate-inspiration` before planning, or pass --allow-blocking to record a bypass.; inspiration: Inspiration sources are configured but not extracted yet: pentagram, pentagram-poster-house, gretel-work, koto-pairpoint; → Run: bgen extract-inspiration --category <category> --sources pentagram,pentagram-poster-house,gretel-work,koto-pairpoint |  | None |
| 2026-04-26T16:10:02 | sage | `49eb307fe826` |  | `data.critique_policy.bypass_requested` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-26T16:10:02 | sage | `49eb307fe826` |  | `data.critique_policy.bypass_recorded` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-26T16:10:02 | sage | `49eb307fe826` |  | `data.critique_policy.bypass_reason` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-26T16:10:02 | sage | `49eb307fe826` |  | `data.critique_policy.bypass_recorded_at` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-26T16:10:02 | sage | `49eb307fe826` |  | `event_text` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-26T16:10:02 | sage | `49eb307fe826` |  | `data.critique_policy.bypass_requested` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-26T16:10:02 | sage | `49eb307fe826` |  | `data.critique_policy.bypass_recorded` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-26T16:10:02 | sage | `49eb307fe826` |  | `data.critique_policy.bypass_reason` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-26T16:10:02 | sage | `49eb307fe826` |  | `data.critique_policy.bypass_recorded_at` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-27T08:44:30 | sage | `4a529a2fb685` |  | `data.critique_policy.bypass_requested` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T08:44:30 | sage | `4a529a2fb685` |  | `data.critique_policy.bypass_recorded` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T08:44:30 | sage | `4a529a2fb685` |  | `data.critique_policy.bypass_reason` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T08:44:30 | sage | `4a529a2fb685` |  | `data.critique_policy.bypass_recorded_at` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T08:44:30 | sage | `4a529a2fb685` |  | `event_text` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T08:44:30 | sage | `4a529a2fb685` |  | `data.critique_policy.bypass_requested` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-27T08:44:30 | sage | `4a529a2fb685` |  | `data.critique_policy.bypass_recorded` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-27T08:44:30 | sage | `4a529a2fb685` |  | `data.critique_policy.bypass_reason` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-27T08:44:30 | sage | `4a529a2fb685` |  | `data.critique_policy.bypass_recorded_at` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-24T01:46:36 | sage | `50eb6551a4e6` |  | `event_text` | validate/validate_run_completed | Learnings block: reference mode has been underperforming for this material recently. Switch to the winning setup from learnings.json, or pass --allow-blocking to record a bypass. |  | None |
| 2026-04-24T02:08:14 | sage | `50eb6551a4e6` |  | `data.critique_policy.bypass_requested` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-24T02:08:14 | sage | `50eb6551a4e6` |  | `data.critique_policy.bypass_recorded` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-24T02:08:14 | sage | `50eb6551a4e6` |  | `data.critique_policy.bypass_reason` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-24T02:08:14 | sage | `50eb6551a4e6` |  | `data.critique_policy.bypass_recorded_at` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-27T12:04:54 | sage | `60f060e4d19e` |  | `data.critique_policy.bypass_requested` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:04:54 | sage | `60f060e4d19e` |  | `data.critique_policy.bypass_recorded` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:04:54 | sage | `60f060e4d19e` |  | `data.critique_policy.bypass_reason` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:04:54 | sage | `60f060e4d19e` |  | `data.critique_policy.bypass_recorded_at` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:04:54 | sage | `60f060e4d19e` |  | `event_text` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:04:54 | sage | `60f060e4d19e` |  | `event_text` | orchestrate/orchestrate_run_completed | Learnings block: hybrid mode has been underperforming for this material recently. Switch to the winning setup from learnings.json, or pass --allow-blocking to record a bypass.; HTML share-card policy block: Sage social/editorial HTML share-card variants duplicate the proof-poster template and serve no purpose; keep deterministic HTML only for explicit proof-poster proof work. Use proof-poster for deterministic proof cards, or switch this material to the native/composite path. |  | None |
| 2026-04-27T12:07:07 | sage | `6167837cbaea` |  | `data.critique_policy.bypass_requested` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:07:07 | sage | `6167837cbaea` |  | `data.critique_policy.bypass_recorded` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:07:07 | sage | `6167837cbaea` |  | `data.critique_policy.bypass_reason` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:07:07 | sage | `6167837cbaea` |  | `data.critique_policy.bypass_recorded_at` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:07:07 | sage | `6167837cbaea` |  | `event_text` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:07:07 | sage | `6167837cbaea` |  | `event_text` | orchestrate/orchestrate_run_completed | Learnings block: hybrid mode has been underperforming for this material recently. Switch to the winning setup from learnings.json, or pass --allow-blocking to record a bypass.; HTML share-card policy block: Sage social/editorial HTML share-card variants duplicate the proof-poster template and serve no purpose; keep deterministic HTML only for explicit proof-poster proof work. Use proof-poster for deterministic proof cards, or switch this material to the native/composite path.; Text-heavy material requests visible labels, CLI/footer copy, stats, captions, or card copy, but the plan does not declare a deterministic text rendering strategy. Route this through render_backend=html or a text_rendering_strategy such as html/svg/composite before native image generation. |  | None |
| 2026-04-27T12:10:32 | sage | `696e544ff247` |  | `data.critique_policy.bypass_requested` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:10:32 | sage | `696e544ff247` |  | `data.critique_policy.bypass_recorded` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:10:32 | sage | `696e544ff247` |  | `data.critique_policy.bypass_reason` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:10:32 | sage | `696e544ff247` |  | `data.critique_policy.bypass_recorded_at` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:10:32 | sage | `696e544ff247` |  | `event_text` | critique/plan_critiqued | Blocking findings remain, but an explicit bypass is recorded for downstream generation. |  | None |
| 2026-04-27T12:10:32 | sage | `696e544ff247` |  | `data.critique_policy.bypass_requested` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-27T12:10:32 | sage | `696e544ff247` |  | `data.critique_policy.bypass_recorded` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-27T12:10:32 | sage | `696e544ff247` |  | `data.critique_policy.bypass_reason` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-27T12:10:32 | sage | `696e544ff247` |  | `data.critique_policy.bypass_recorded_at` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-25T21:51:05 | sage | `6d2a0e4d3660` |  | `event_text` | orchestrate/orchestrate_run_completed | Learnings block: hybrid mode has been underperforming for this material recently. Switch to the winning setup from learnings.json, or pass --allow-blocking to record a bypass. |  | None |
| 2026-04-27T15:39:34 | sage | `6f6d0c3ead13` |  | `event_text` | orchestrate/orchestrate_run_completed | Learnings block: hybrid mode has been underperforming for this material recently. Switch to the winning setup from learnings.json, or pass --allow-blocking to record a bypass. |  | None |
| 2026-04-24T01:46:36 | sage | `6ffa74f20dd9` |  | `event_text` | validate/validate_run_completed | Learnings block: reference mode has been underperforming for this material recently. Switch to the winning setup from learnings.json, or pass --allow-blocking to record a bypass. |  | None |
| 2026-04-24T02:07:39 | sage | `6ffa74f20dd9` |  | `data.critique_policy.bypass_requested` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-24T02:07:39 | sage | `6ffa74f20dd9` |  | `data.critique_policy.bypass_recorded` | scratchpad/scratchpad_built |  |  | None |
| 2026-04-24T02:07:39 | sage | `6ffa74f20dd9` |  | `data.critique_policy.bypass_reason` | scratchpad/scratchpad_built |  |  | None |
