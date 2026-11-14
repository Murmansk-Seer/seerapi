# Official update timing and cost source quality

These are three independent concepts: maintenance/update announcements, preview
display windows, and peak cost quota deadlines. None is a substitute for another.

## Public metadata (JSON schema version 1)

The existing `seerapi_metadata` key/value table gains three JSON values. No DDL or
standard SDK resource changes are required. Existing update-cycle and preview
metadata retain their meanings.

- `official_update_timing`: `timezone`, `last_update`, and `next_update`.
  A missing observation is JSON `null`, not an estimated date. Each observation
  has `date`, nullable `planned_start`/`planned_end`, nullable
  `completion_announced_at`, `status`, and an `evidence` list of official source
  URLs, notice IDs and evidence kinds. Timestamps include their UTC offset.
- `peak_cost_pool_source`: `config_version`, verified bundle `source` URL,
  complete original `rows` (including cost=0), and canonical content `sha256`.
  The hash covers UTF-8 JSON rows with sorted keys, no insignificant whitespace,
  unescaped Unicode, and no non-finite numbers. Original field values are retained.
- `peak_cost_pool_time_anomalies`: source-bound `source_sha256` and `items`.
  Each `invalid_time_range` item identifies source `id`, `cost`, `subkeyMonth`,
  `time`, and the mapped offset-aware `mapped_start`/`mapped_end`.

## Official maintenance evidence

Source: <https://unity-notice.61.com/unity_notice/>.
Explicit type=3 notices provide planned maintenance windows. Their occurrence
alone does not confirm actual completion. A matching completed-update type=2
announcement confirms the update date; its publication timestamp is recorded as
`completion_announced_at`, never described as actual server opening time.
The announcement's display expiry is not an outage end.

Statuses are `maintenance_announced` or `completed_announced` for the latest
past observation, and `scheduled` for the earliest freshly announced future
window. Historical completed observations remain available when notices rotate.
Future announcements are not carried forward after withdrawal; changes are
reflected without moving an established content-batch anchor. The first verified
completed announcement on a date remains the recorded confirmation timestamp.

No date is inferred from previews, event expiry text, or weekday arithmetic.
An absent next window is displayed as “官方暂未公布”. Fetch timestamps do not enter
the semantic fingerprint, so unchanged observations do not rebuild hourly.
The shared download adapter makes at most three total attempts, with a 15-second
connection timeout and 60-second per-attempt deadline for notices. Permanent HTTP
errors, exhausted retries, malformed responses and invalid notices fail the job;
they do not write successful state or replace the existing Release.

## Cost time contradictions are retained, not corrected

Verified official ConfigPackage `20261113190033`, bundle
`08dfdb04c492b4a26d0547bae5b585d0`, has five raw cost records. Four non-zero
pools map `subkeyMonth=1020261113` to November 13 while retaining
`time="2026_10_23 10:00:00"`. The current client uses `time` in the label
“本期配额持续至……更新前”. The source key is not an independent exact start-time
field; its existing API mapping is preserved rather than guessed anew.

Under the explicitly approved policy, a parseable end-before-start or equal
boundary is an admitted **source-quality anomaly**, not a valid interval.
The existing pool datetime columns retain mapped official values; consumers
must consult the anomaly metadata before treating them as a usable interval.
No pool, pet link, or original date is removed or manufactured. Cost=0 retains
its existing non-entity behavior while its complete raw row remains available.

Only this specific semantic condition is admitted. Invalid dates, unknown fields,
malformed/trailing binary data, duplicate IDs/costs/pet assignments, inconsistent
seasons, missing pets and program errors still abort publication. Pools and
metadata are written in the same publication transaction; a corrected source
clears the previous anomaly list.

Final validation independently compares every pool, pet assignment, season, raw
row and anomaly against the pinned source JSON, its version, and the checked
official bundle manifest/cache. Missing, forged or stale anomaly metadata fails.
The same checks run against the remotely uploaded database before advancing the
publication checkpoint. SHA256, SQLite integrity, foreign-key, schema, Somua,
Autocard, skill and activity regression gates remain in force.
