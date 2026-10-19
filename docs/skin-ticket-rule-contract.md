# Lucky-window ticket deduction rules

The release builder publishes `skin_ticket_rule` as a SQLite sidecar fact table.
It requires no seerapi-models change, PyPI package, or model dependency pin update.

| Column | Contract |
| --- | --- |
| ticket_id | Integer primary key; the referenced item ID |
| diamonds_per_ticket | Positive integer diamond deduction for one ticket |
| source | `item.desc:lucky_window_per_ticket_diamonds_v1` |
| source_text | Complete, unchanged item-description evidence |

`release_config_tables.replace_config_package_tables` rebuilds the table from
the existing `item` table and ticket IDs referenced by `skin_store_price`.
Duplicate offers produce one rule. Rebuilding removes rules whose evidence is
no longer accepted. `release_contract` requires the table and includes its DDL
in the release schema fingerprint. An empty table is valid when no supported
evidence is available; missing item data fails the build instead of guessing.

## Accepted evidence

Rule version 1 accepts only this complete, unconditional description grammar:

```text
通过“<nonempty acquisition source>”获得，可在幸运橱窗中使用，每张<exact item.name>可抵扣<positive integer>钻石。
```

Matching is anchored to the complete description, with the actual item name
escaped literally. The value must fit a positive signed 64-bit SQLite integer.
No item ID or diamond amount is hardcoded. Different item IDs and values can
produce rules when their complete descriptions satisfy the same evidence rule.

This intentionally does not accept partial matches, different scopes, mismatched
names, prices, zero/negative amounts, upper bounds, probability, alternative
values, additional conditions, or surrounding text. Unsupported grammar yields
no row; it is not silently generalized. `skinStoreTicket.tickettype/para` has no
verified deduction semantics and is not used.

The inspected release item 1727935 has this complete source text:

```text
通过“风尚月历”获得，可在幸运橱窗中使用，每张风尚券可抵扣10钻石。
```

This is evidence for per-ticket deduction in the lucky window, not an item sale
price, a price floor, a stacking rule, or proof that a skin is currently sold.
Consumers compute only from a published rule; absent rules mean unknown value.

## Publication boundary

Existing published databases do not yet contain this new sidecar. A newly built,
validated and published data release is required before remote consumers can
reproduce it. Local tests or in-memory replay do not prove remote publication.
Do not pin an unpublished or fabricated model revision to activate this table.
