# Strict pet effect ownership

## Upstream evidence

- [SeerAPI glossary analyzer at cf5796b](https://github.com/SeerAPI/seerapi/blob/cf5796b835b4124cd531e7a512ba01269319c84b/packages/solaris/solaris/analyze/analyzers/glossary.py)
  uses the official `effectDes.monster` and `effectDes.link` fields.
- [IronsBot renderer at e42b717](https://github.com/Nattsu39/IronsBot/blob/e42b71731f1f38516b280e1fcd28e06dd702741c/ironsbot/plugins/get_seer_info/render/pet_info.py)
  collects complete red Analyze segments and queries exact glossary names.
- [Upstream Analyze parser](https://github.com/Nattsu39/IronsBot/blob/e42b71731f1f38516b280e1fcd28e06dd702741c/ironsbot/utils/analyze_parser.py)
  preserves explicit ID suffixes and official batch color-closing semantics.

The fork's former plain-text substring fallback was not an upstream ownership
rule. A unique dictionary name, a matching status icon, or another effect's
description mentioning a skill cannot independently establish pet ownership.

## Producer behavior

Official direct associations remain authoritative. Additional facts require a
complete registered Analyze label, optionally with a matching effect ID. Lists
must have explicit separators; longer unknown names cannot be split into known
short names. Unknown or contradictory marked IDs are diagnostic issues rather
than fallback name matches. Ambiguous marked names still require existing
official identity or exact description evidence to choose between candidates.

Plain text cannot create a fact or assert skill-level provenance, even when a
pet's ownership is independently established. Global reverse skill-name
references have the same restriction.
Rejected candidates go to `pet_special_effect_issue`; source text and base business
tables remain unchanged. Named statuses and icons enrich verified facts only.
One-hop glossary expansion starts from verified roots, retaining the existing
shared-child, cycle and deduplication contract.

No schema migration or consumer changes are required. New provenance rules
`soulmark_highlight_exact` uses the existing string
fields. Historical databases remain readable.

## Reproducible real-data audit

Run `scripts/audit_pet_special_effect_ownership.py DATABASE --output .cache/AUDIT`.
It opens the source read-only, replays twice on a separate diagnostic copy,
checks business-table fingerprints and all direct associations, and emits
`audit.json` and `audit.md`. The diagnostic database is not a sealed Release.

The 2026-11-21 Release at build `cded596e83279a569b27da51c2232d729dfc1b41`
has SHA256 `78b2a2f0f5f009db74a1efffb006695dca8a3dfb6e439249c08cd11a6792c6c0`.
Replay changes 996 facts to 704, removing 292 unsupported roots/dependents.
Of 286 weak associations covering 20 effect names, five have complete soulmark
markers and are retained: both protections for pet 4364, both emperor effects
for pet 4950, and the effect for pet 4956. Future singularity/instruction for pet
4600 remain in the original soulmark text and diagnostics, not inferred facts.

Pet 4012 retains glossary IDs 51-54 only. Pet 3809 retains ID 72, and pet 4861
retains IDs 420-426. The reduced real-source fixture covers these cases and the
weak-name examples; it records its source digest and configuration version.
