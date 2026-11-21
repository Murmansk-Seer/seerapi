# Official Pet Display Forms

Release SQLite publishes two additive tables from the same verified ConfigPackage:

- `pet_form_resource(pet_id, skin_id, form_index, resource_id)` is decoded from
  `pet_skin_poly.bytes`. Exactly one of `pet_id` and `skin_id` is positive.
  Alternate resources start at index 1; index 0 is the existing catalogue resource.
- `pet_form_member(canonical_pet_id, pet_id)` is decoded from
  `petCompositio.bytes`. Membership is explicit, including the canonical pet.
  It is not inferred from ID arithmetic, names, or visual similarity.

The official client's `PetSkinForm` splits a runtime skin value into
`skin_id = value % 100000` and `form_index = value // 100000`. A zero skin ID
can still carry a nonzero form. For example, `100871` selects skin 871, form 1;
the official configuration maps that form to resource 2900871.

Consumers must check skin ownership before applying its form. They may accept
the exact owner or an explicitly published shared composition family. They
must not subtract 10000 from pet IDs. Missing or out-of-range forms use the
existing base portrait, matching the client fallback, never a guessed filename.

Both head and body resources enter the immutable render asset manifest.
Old releases without either table remain readable using base portraits and
exact skin ownership. Missing source assets, malformed records, duplicate keys,
and trailing binary data fail the new release build rather than silently
publishing guessed relationships.
