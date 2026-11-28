# Client effect associations

## Goal and evidence

Use public client configuration as a generic display-reference source, never a
per-pet override list. Evidence is GameLogic DefaultPackage 20261127164251,
SHA256 4a587564ada47dc92e2f2a23aa1d0cde87334aaae66d2efd6b19986c3552136d.
The local investigation preserves IL offsets, source hashes and replay results.

Panel ownership is `petEffectIcon.petid`. Only independent top-level status
headings (`indent=0`, `sprite=5`) establish panel references. Exact unique names
are a documented derived association, not an official cross-table ID. Strip only
known trailing display annotations. Ambiguity and conflicting existing terms
remain issues, not aliases. Thirteen observed candidates are audit inputs, not a
required number of new cards. In particular, existing 圣诰 and panel 圣告 must not
be silently merged or duplicated.

## Producer and consumer contract

- Physical schema contract 3 enforces a paired publisher and consumer.
  API v1 and the weekly semantic schema stay unchanged.
- Effect association contract 3 publishes all verified icon references in
  `pet_special_effect_icon`, keyed by pet, effect, kind and exact asset key.
  Each reference may carry a numeric status ID and variant value. No row means
  no confirmed icon. This replaces the old single-icon columns, so the
  publisher and the IronsBot consumer must move to contract 3 together.
- `pet_effect_panel` retains official panel ID, pet ID, soulmark reference,
  original text, advance flag and frozen configuration version.
- `pet_special_effect_source.source_kind=pet_effect_panel` uses panel ID and
  `panel_heading_unique_status`. JSON detail retains heading, raw heading,
  configuration version and effecticonid. It does not assert skill application,
  permanent status or exclusive ownership.
- Persist conditional `show_monster` rows verbatim and as parsed display fields;
  do not convert them into an unconditional pet/status association.
- A validated conditional display row can establish a display reference to its
  explicit pet ID, retaining the complete rule as `client_status_display` /
  `client_conditional_display`. It never asserts that the status is always active.
  An existing exact-name fact can share this explicit display evidence; unrelated
  skill terms cannot block another panel heading. Differing terms sourced from
  the same panel soulmark require reconciliation rather than automatic aliasing.
- Explicit glossary icon IDs use abnormal assets. Confirmed status IDs use
  sign_buff assets. Only explicit positive sp_icon values form a suffix; missing
  mappings and zero suffixes use the base status icon.
- A branch name can select a variant only inside a state ID independently
  confirmed for that same pet. Distinct candidate states remain ambiguous;
  global name/description joins never establish this context. Record the state
  ID and branch value as `client_status_variant` evidence. Conditional references
  also apply the client's value threshold before selecting the displayed pet.
- Remove description similarity, lowest-ID selection and unsupported name-only
  cross-table bridging. Distinct explicit entity IDs cannot merge by text alone.
- Preserve raw status configuration including class_name, sp_des and sp_icon in
  special_effect_status_config. Match the client's literal newline rendering;
  never manufacture a state icon from a text-only heading such as 不破诛罚.

## Acceptance and delivery

### State-container presentation

Keep all state facts and evidence, but publish `display_in_pet_info` (default true)
for consumer presentation. A descriptionless state supported only by conditional
display rules can be hidden only when every applicable named branch is already a
separate, unambiguous fact with an explicit client_status_variant reference to
that state and value. Glossary identities, independent panel/skill/soulmark
evidence and nonempty descriptions always preserve the parent. Missing or
ambiguous branches preserve it and produce a diagnostic. Neither pet IDs, short
names nor equal image bytes determine visibility. Contract 3 requires the
visibility flag. Replay
audits must include retained and hidden decisions, and rendering must verify
both real forms without the redundant container.

The 2026-11-28 container replay retains all 723 facts, 1446 sources and 404
diagnostics with every preexisting field unchanged. It hides one container;
the three other published states with named variants retain independent
descriptions. Candidate SHA256:
`06b046a21fd7a73925225877e582e78a7a098dc5f9c4e7edda4de4ace8681991`.
794 tests, Ruff lint/format, basedpyright and diff checks passed. The real
consumer requests only 151_2/151_3 for the two forms, not the base 151 icon.

Freeze a real release and official sources, replay deterministically, and classify
new panel references, removed guesses, retained evidence and unresolved issues.
Cover duplicate names/descriptions, explicit references, nested text, headings,
unknown annotations, repeated panels, missing/zero/nonidentity icon suffixes and
conditional visibility. Render representative results with the existing IronsBot
main chat. Run focused and full tests, Ruff and diff checks; report baseline
failures separately. Preserve unrelated work and reserved files.

Commit with bilingual evidence and push main normally under the user's updated
authorization; automatic workflows may run. Do not rewrite history, manually
publish a release, change production pins, restart or deploy.

## Frozen replay on 2026-11-28

The release snapshot SHA256 is
`bcceeac44fb6f47454f325116307fe5050623a29de9f19e546a16a8ceefebbc1`;
the official ConfigPackage is `20261127104733`.
The verified local candidate SHA256 is
`99ed3b049d5203884dc3d0883476c3580a4411804a443578f62be8777cf0323a`.
It contains 723 facts, 1446 evidence rows and 404 unresolved diagnostics.
Unrelated business-table hashes and deterministic rebuilding were verified.

Of thirteen inspected missing-status candidates, twelve have independent panel
evidence. 圣告 remains unresolved alongside the existing 圣诰 word entry, not a
new duplicate card. 不破帝·南霜 has a structured 不破诛罚 heading, but no matching
status definition; its raw panel is retained without inventing an icon.

The replay retires 119 old icon bindings: 105 were unique-name cross-table
matches, three selected the lowest ID among equal descriptions, ten were
name/description-based branch assignments, and one is the ambiguous 支援 fact
on pet 4706. This does not prove 119 old images were wrong. It records that their
IDs are not established by the accepted evidence. Of these, 118 existing word
facts remain; the ambiguous 支援 reference remains in its original soulmark text
and diagnostics rather than as an arbitrarily selected glossary identity.
黄月英's four existing word entries remain, but the frozen configuration has no
client panel or conditional display rule establishing their old state-icon IDs.
Two other branch bindings, 151_2 and 151_3, are retained because the client's
conditional display rule independently establishes state 151 for that pet.

Consumer validation uses the same candidate bytes and unchanged 专属效果 layout,
including actual sign_buff and abnormal downloads. Code may be pushed normally
to main under the user's later authorization; automatic workflows may run. No
manual deployment or production configuration change is authorized.

Final local checks: 783 pytest cases passed, whole-repository Ruff lint and format
checks passed, basedpyright reported zero errors/warnings, and git diff --check
passed. The final threshold regression replay produced the same candidate SHA256.
