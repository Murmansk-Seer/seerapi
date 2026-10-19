# Pet special-effect relationship contract audit

Audit date: 2026-10-19.

## Existing published representation

The existing build output already represents parent/related glossary facts.
No table, column, model field, package version, or dependency revision upgrade
is required for consumers to expose these relationships.

- `pet_special_effect` identifies a fact by `(pet_id, effect_key)`.
- A `pet_special_effect_source` row with `source_kind = 'glossary_link'`
  belongs to the child identified by its `effect_key`. Its `source_id` is
  the parent glossary ID, not the child ID or a status ID.
- Resolve that ID against the same pet's fact `glossary_id` to obtain the
  parent's actual `effect_key`. Consumers must not assume an effect-key prefix
  or infer relationships from names or descriptions.
- Multiple source rows preserve shared children and their multiple parents.
  Direct pet, skill, soulmark, and other provenance remains attached to the
  same fact. `primary_rule` is resolution precedence, not display-group ownership.
- The builder expands the existing official one-hop glossary links. This audit
  does not change expansion depth or introduce recursive text inference.

Consumers retain stable identities and deduplicate parent references, rather
than deduplicating by display name. Cyclic edges can be represented without
recursive traversal; self-links are excluded by the producer. Display placement
for a directly matched child or a cycle is a separate consumer policy decision.
The subsequently confirmed consumer policy follows upstream subordinate
precedence: an effect with parents is shown once in the related partition even
when it also has direct evidence. Cycles retain each fact once with its parent
references, without recursive expansion.

## Verification

`tests/test_pet_special_effect_facts.py` passes 15 tests, including a new
contract replay proving shared-child identity, both parent sources, retained
direct evidence, cyclic relations, ignored self-links, duplicate-edge
deduplication, and deterministic replacement on a second build.

Targeted Ruff, BasedPyright (zero errors and warnings), compileall, and
`git diff --check` also passed. The production algorithm and schema are unchanged;
the model change documents existing source semantics.

## Local data replay limitation

IronsBot's model dependency remains pinned to
`434667937424e73be3f6cd8f87bd942f7e135666`. No unpublished revision is required
by this change. Model dependency revision and generated data database version
are distinct evidence and must not be treated as interchangeable.

Read-only inspection of the local IronsBot `data/ironsbot-data.sqlite`
(97,943,552 bytes) found generator version `106.4.0` and database-reported
generation time `2026-07-21 03:43:35.945221`. That database has the old
`ironsbot_metadata` table, but lacks `pet_special_effect`,
`pet_special_effect_source`, and `seerapi_metadata`.

Consequently that older local copy cannot replay the current contract.

A fresh release database supplied by the parent task was subsequently replayed
at `E:/IronsBot-history-validation/IronsBot-history-backup-20260922/upstream-migration-20261019/seerapi-data.sqlite`.
It contains 63,385,600 bytes and reports generator `106.10.5`, generation time
`2026-10-16 16:47:35.193833`. The current IronsBot consumer successfully loaded
all 627 pets with effect facts: 993 facts and 76 parent references. Every effect
key was nonempty and unique within its pet; parent references were unique,
resolved within the pet, and excluded self-links. There were 27 pets with
published glossary-link sources. Salmon (3549) resolved `g:533` as the parent
of `g:534` and `g:535`, without runtime name inference.

Real-data contract replay therefore passes. The parent task downloaded the
`seerapi-data-latest` release from `Murmansk-Seer/seerapi` and matched the asset
against its published SHA256 file:
`92bb0d8f4db05d64adeae0a367bd2c2399ab407d02079c8dd1cced4b53402a6b`.
No new schema publication or dependency upgrade is an outstanding gate.

Inspection used SQLite `mode=ro` and `PRAGMA query_only=ON`; no production
database, identity records, credentials, or configuration were accessed.
