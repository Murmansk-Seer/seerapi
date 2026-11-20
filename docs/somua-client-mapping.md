# Somua and dango Client Mapping

## Provenance

- ConfigPackage: `20261119223319`, bundle MD5 `49a7b94e5dd3b515479b3245ebc276a7`.
- DefaultPackage: `20261119215136`, GameLogic DLL MD5 `7e979edf33912548cdda454a18d90e3a`.
- GameLogic DLL SHA256: `888cd5de8d4bf08513c8cf3c8a11ba23262d74922e0a9f310c9a21b6c5175b10`.
- Official base: https://newseer.61.com/Assets/StandaloneWindows64/.
- Golden bytes, complete decoded rows, per-table SHA256, Parse IL and loading evidence are in
  `packages/solaris/tests/fixtures/somua/`.
- Read order below comes from actual client Parse methods, not property declarations.
- Scalars are signed little-endian int32. Strings are uint16 UTF-8 byte length plus bytes.
- Nullable int arrays have a boolean presence flag, signed count and signed elements.
- Enabled files contain an int32 record count. Disabled files contain only their flag.
- Missing required files, invalid lengths, duplicate IDs and trailing bytes fail publication.
- Preserve zero, null, empty strings and unknown values. No unproved units or relations.
- Somua/dango identities are independent of similarly named pets and one another.
- Resource lists and name lookup use declared name fields. Numeric aliases cannot replace ID routes.
  Shared name aliases preserve every matching record; empty primary names stay empty.

## Verified current layout

The November 19 client adds model string `mainATT`, state string `fxOnLoad`,
and `SomuaFilterConfig` (46 rows). The complete 28-table fixture has 1,435 rows.
Filter `entrys`, `mutual` and `icon` remain raw strings; no inferred enums or references.
November 13 model/state bytes and November 5 incompatible bytes are retained only as
rejection fixtures, not alternate production formats. No retry-with-old-layout fallback.

## Resource tables and client read order

### SomuaAchievementConfig

Resource/table: `somua_achievement`; **40 rows** in this fixture, not a future maximum.
Client: `core.config.ISomuaAchievementConfigInfo`; Parse token: `0x6018470`.
Binary SHA256: `a7dbb5e664542b99c19255664a5a955ed84de4c3881eacb273cf0b0f1b03cd36`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | condition | condition | int32 |
| 2 | desc | desc | string |
| 3 | icon | icon | int32 |
| 4 | id | id | int32 |
| 5 | name | name | string |
| 6 | type | type | int32 |

Loader evidence:
- `core.config.SomuaAchievementConfig.get_fileName`, IL offset 0: config asset literal.
- `core.config.SomuaAchievementConfig.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### SomuaBasicAttritube

Resource/table: `somua_basic_attribute`; **21 rows** in this fixture, not a future maximum.
Client: `core.config.ISomuaBasicAttritubeInfo`; Parse token: `0x601848a`.
Binary SHA256: `e3df0261a7dc8ed6b914b9c87cde0a6ca018e7f6bb4ad883249a08ec0ca0f525`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | attackRatio | attack_ratio | int32 |
| 2 | attackValue | attack_value | int32 |
| 3 | bodyRatio | body_ratio | int32 |
| 4 | criticalChance | critical_chance | int32 |
| 5 | criticalDamageRatio | critical_damage_ratio | int32 |
| 6 | defenseRatio | defense_ratio | int32 |
| 7 | healthValue | health_value | int32 |
| 8 | id | id | int32 |
| 9 | knockRatio | knock_ratio | int32 |
| 10 | speedValue | speed_value | int32 |

Loader evidence:
- `core.config.SomuaBasicAttritube.get_fileName`, IL offset 0: config asset literal.
- `core.config.SomuaBasicAttritube.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### SomuaDispatchConfig

Resource/table: `somua_dispatch`; **7 rows** in this fixture, not a future maximum.
Client: `core.config.ISomuaDispatchConfigInfo`; Parse token: `0x60184a0`.
Binary SHA256: `6620fea1ee648507e3187cda22af8286a3b03918a25b4ca27e0fcb5e90f31d22`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | award | award | string |
| 2 | bonus1 | bonus1 | string |
| 3 | bonus2 | bonus2 | string |
| 4 | bonus3 | bonus3 | string |
| 5 | id | id | int32 |
| 6 | name | name | string |
| 7 | tasktype | tasktype | int32 |
| 8 | value | value | int32 |

Loader evidence:
- `core.config.SomuaDispatchConfig.get_fileName`, IL offset 0: config asset literal.
- `core.config.SomuaDispatchConfig.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### SomuaEntryConfig

Resource/table: `somua_entry`; **373 rows** in this fixture, not a future maximum.
Client: `core.config.ISomuaEntryConfigInfo`; Parse token: `0x60184bc`.
Binary SHA256: `9fc5b206064fdf45eaf2697c66477c9fc2ee9ee097b00d703830d7105ec0826e`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | desc | desc | string |
| 2 | id | id | int32 |
| 3 | name | name | string |
| 4 | rarity | rarity | int32 |
| 5 | type | type | int32 |
| 6 | value1 | value1 | int32 |
| 7 | value2 | value2 | int32 |
| 8 | value3 | value3 | int32 |
| 9 | value4 | value4 | int32 |
| 10 | value5 | value5 | int32 |
| 11 | value6 | value6 | int32 |

Loader evidence:
- `core.config.SomuaEntryConfig.get_fileName`, IL offset 0: config asset literal.
- `core.config.SomuaEntryConfig.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### SomuaFilterConfig

Resource/table: `somua_filter`; **46 rows** in this fixture, not a future maximum.
Client: `core.config.ISomuaFilterConfigInfo`; Parse token: `0x60184ce`.
Binary SHA256: `50774c7056caa8c93859da569372f494618a483765a4b0a1e0f94bada69f25c3`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | category | category | int32 |
| 2 | entrys | entrys | string |
| 3 | icon | icon | string |
| 4 | id | id | int32 |
| 5 | mutual | mutual | string |
| 6 | name | name | string |

Loader evidence:
- `core.config.SomuaFilterConfig.get_fileName`, IL offset 0: config asset literal.
- `core.config.SomuaFilterConfig.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### SomuaGeneConfig

Resource/table: `somua_gene`; **15 rows** in this fixture, not a future maximum.
Client: `core.config.ISomuaGeneConfigInfo`; Parse token: `0x60184e4`.
Binary SHA256: `e5ae6baea40d459376c0dd1dfa1ef5ebe023f088a8e9a7c97a301aafe64bbef6`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | foodid | foodid | int32 |
| 2 | gene | gene | string |
| 3 | id | id | int32 |
| 4 | rarity | rarity | int32 |
| 5 | shopID | shop_id | int32 |
| 6 | skinbaby | skinbaby | string |
| 7 | skinteen | skinteen | string |
| 8 | sort | sort | int32 |

Loader evidence:
- `core.config.SomuaGeneConfig.get_fileName`, IL offset 0: config asset literal.
- `core.config.SomuaGeneConfig.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### SomuaHouseConfig

Resource/table: `somua_house`; **10 rows** in this fixture, not a future maximum.
Client: `core.config.ISomuaHouseConfigInfo`; Parse token: `0x60184f2`.
Binary SHA256: `10aad71ad42bd1def88f0dac993aa832b90255d8256bdb7a53507206e51a10a4`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | id | id | int32 |
| 2 | limitCost | limit_cost | int32 |
| 3 | name | name | string |
| 4 | roomID | room_id | int32 |

Loader evidence:
- `core.config.SomuaHouseConfig.get_fileName`, IL offset 0: config asset literal.
- `core.config.SomuaHouseConfig.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### SomuaKeeperConfig

Resource/table: `somua_keeper`; **6 rows** in this fixture, not a future maximum.
Client: `core.config.ISomuaKeeperConfigInfo`; Parse token: `0x601851a`.
Binary SHA256: `1af7a05fc0d5a7b74468cab4caf4592559c909363d8fe8120b79cdc8b2c04b04`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | benefit1 | benefit1 | int32 |
| 2 | benefit2 | benefit2 | int32 |
| 3 | benefit3 | benefit3 | int32 |
| 4 | benefit4 | benefit4 | int32 |
| 5 | benefit5 | benefit5 | int32 |
| 6 | benefit6 | benefit6 | int32 |
| 7 | benefit7 | benefit7 | int32 |
| 8 | dangoGold | dango_gold | int32 |
| 9 | dangoTask | dango_task | string |
| 10 | describe1 | describe1 | string |
| 11 | describe2 | describe2 | string |
| 12 | describe3 | describe3 | string |
| 13 | id | id | int32 |
| 14 | minorNum | minor_num | int32 |
| 15 | reward | reward | string |
| 16 | storeMax | store_max | int32 |
| 17 | taskNum | task_num | int32 |

Loader evidence:
- `core.config.SomuaKeeperConfig.get_fileName`, IL offset 0: config asset literal.
- `core.config.SomuaKeeperConfig.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### SomuaModelConfig

Resource/table: `somua_model`; **68 rows** in this fixture, not a future maximum.
Client: `core.config.ISomuaModelConfigInfo`; Parse token: `0x6018548`.
Binary SHA256: `5e044890eaf2034a8f4f4de07423193eb603330b3b178b1617de3def72aae9b0`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | addonPool | addon_pool | string |
| 2 | addonPoolSP | addon_pool_sp | string |
| 3 | attackMode | attack_mode | int32 |
| 4 | attackModeSP | attack_mode_sp | int32 |
| 5 | describe | describe | string |
| 6 | id | id | int32 |
| 7 | isBack | is_back | int32 |
| 8 | isBody | is_body | int32 |
| 9 | isEar | is_ear | int32 |
| 10 | isExpression | is_expression | int32 |
| 11 | isHand | is_hand | int32 |
| 12 | isHead | is_head | int32 |
| 13 | isSurrounding | is_surrounding | int32 |
| 14 | isTail | is_tail | int32 |
| 15 | isTopwear | is_topwear | int32 |
| 16 | mainATT | main_att | string |
| 17 | name | name | string |
| 18 | naturePool | nature_pool | string |
| 19 | petID | pet_id | int32 |
| 20 | season | season | string |

Loader evidence:
- `core.config.SomuaModelConfig.get_fileName`, IL offset 0: config asset literal.
- `core.config.SomuaModelConfig.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### SomuaRankingConfig

Resource/table: `somua_ranking`; **16 rows** in this fixture, not a future maximum.
Client: `core.config.ISomuaRankingConfigInfo`; Parse token: `0x601855c`.
Binary SHA256: `f102df46ae4bee7da3fc94db4db534ad11d8f260ffe436d2ee8d0147b99355aa`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | icon | icon | int32 |
| 2 | id | id | int32 |
| 3 | isFalling | is_falling | int32 |
| 4 | level | level | string |
| 5 | minscore | minscore | string |
| 6 | name | name | string |
| 7 | phase | phase | int32 |

Loader evidence:
- `core.config.SomuaRankingConfig.get_fileName`, IL offset 0: config asset literal.
- `core.config.SomuaRankingConfig.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### SomuaShopConfig

Resource/table: `somua_shop`; **14 rows** in this fixture, not a future maximum.
Client: `core.config.ISomuaShopConfigInfo`; Parse token: `0x601857e`.
Binary SHA256: `512ba0c55b6a076349b5cf66bd7a6bffafbb8dcb66c6fef9bd8139a275dc57dd`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | NewMsglogId | new_msglog_id | int32 |
| 2 | Price | price | int32 |
| 3 | describe1 | describe1 | string |
| 4 | describe2 | describe2 | string |
| 5 | forever | forever | int32 |
| 6 | id | id | int32 |
| 7 | limit | limit | int32 |
| 8 | limitType | limit_type | int32 |
| 9 | quantity | quantity | int32 |
| 10 | rewardinfo | rewardinfo | string |
| 11 | shopType1 | shop_type1 | int32 |
| 12 | title | title | string |
| 13 | userinfo | userinfo | int32 |
| 14 | value | value | int32 |

Loader evidence:
- `core.config.SomuaShopConfig.get_fileName`, IL offset 0: config asset literal.
- `core.config.SomuaShopConfig.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### SomuaStatusEffectConfig

Resource/table: `somua_status_effect`; **24 rows** in this fixture, not a future maximum.
Client: `core.config.ISomuaStatusEffectConfigInfo`; Parse token: `0x601859a`.
Binary SHA256: `20a63ac5d65ae2509d06e24549f1c9341d1f1ca917b3fda7f14ea14825ea35ee`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | fxOnGet | fx_on_get | string |
| 2 | fxOnLoad | fx_on_load | string |
| 3 | fxOnTrig | fx_on_trig | string |
| 4 | icon | icon | int32 |
| 5 | id | id | int32 |
| 6 | maxStack | max_stack | int32 |
| 7 | stackRule | stack_rule | string |
| 8 | statusDesc | status_desc | string |
| 9 | statusName | status_name | string |
| 10 | type | type | int32 |
| 11 | valueRule | value_rule | string |

Loader evidence:
- `core.config.SomuaStatusEffectConfig.get_fileName`, IL offset 0: config asset literal.
- `core.config.SomuaStatusEffectConfig.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### SomuaTaskConfig

Resource/table: `somua_task`; **49 rows** in this fixture, not a future maximum.
Client: `core.config.ISomuaTaskConfigInfo`; Parse token: `0x60185b0`.
Binary SHA256: `7749e572be749487f6ab92a4427282340c0432e41a22c797040eab1f18c4f7bf`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | describe | describe | string |
| 2 | group | group | int32 |
| 3 | id | id | int32 |
| 4 | period | period | int32 |
| 5 | rewardinfo | rewardinfo | string |
| 6 | season | season | int32 |
| 7 | tasktype | tasktype | int32 |
| 8 | value | value | int32 |

Loader evidence:
- `core.config.SomuaTaskConfig.get_fileName`, IL offset 0: config asset literal.
- `core.config.SomuaTaskConfig.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### SomuaToturialConfig

Resource/table: `somua_tutorial`; **9 rows** in this fixture, not a future maximum.
Client: `core.config.ISomuaToturialConfigInfo`; Parse token: `0x60185c0`.
Binary SHA256: `1b47783c503b7777e6c364779c2b2c4ab0453003222c20f072ee81f9e1d6ee34`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | id | id | int32 |
| 2 | img | img | string |
| 3 | module | module | string |
| 4 | page | page | int32 |
| 5 | txt | txt | string |

Loader evidence:
- `core.config.SomuaToturialConfig.get_fileName`, IL offset 0: config asset literal.
- `core.config.SomuaToturialConfig.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### SomuaWeaponConfig

Resource/table: `somua_weapon`; **73 rows** in this fixture, not a future maximum.
Client: `core.config.ISomuaWeaponConfigInfo`; Parse token: `0x60185d0`.
Binary SHA256: `ac7f6c263c1818bde3f3f4540aaca21f7e5375e7ca9d65f0a475100cdb853e04`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | fxOnHit | fx_on_hit | string |
| 2 | id | id | int32 |
| 3 | prefab | prefab | string |
| 4 | shape | shape | int32 |
| 5 | type | type | int32 |

Loader evidence:
- `core.config.SomuaWeaponConfig.get_fileName`, IL offset 0: config asset literal.
- `core.config.SomuaWeaponConfig.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### dango

Resource/table: `dango`; **57 rows** in this fixture, not a future maximum.
Client: `core.config.IDangoInfo`; Parse token: `0x6017388`.
Binary SHA256: `4f2403c12e2fb67b757ee2dc5c5388778d80b777a2ef77a8313992ad1dda3531`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | describe | describe | string |
| 2 | gene | gene | string |
| 3 | grade | grade | int32 |
| 4 | id | id | int32 |
| 5 | name | name | string |
| 6 | petID | pet_id | int32 |
| 7 | skin | skin | string |
| 8 | value | value | int32 |

Loader evidence:
- `core.config.Dango.get_fileName`, IL offset 0: config asset literal.
- `core.config.Dango.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### dangoAction

Resource/table: `dango_action`; **300 rows** in this fixture, not a future maximum.
Client: `core.config.IDangoActionInfo`; Parse token: `0x601739e`.
Binary SHA256: `286ef2bc0012567510985252cdc54ef444e18db4c6b5d674748760f7b629edaa`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | action | action | string |
| 2 | actionTeam | action_team | int32 |
| 3 | dangoID | dango_id | int32[] |
| 4 | describ | describ | string |
| 5 | id | id | int32 |
| 6 | limitDango | limit_dango | int32 |
| 7 | limitType | limit_type | int32 |
| 8 | value | value | int32 |

Loader evidence:
- `core.config.DangoAction.get_fileName`, IL offset 0: config asset literal.
- `core.config.DangoAction.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### dangoGene

Resource/table: `dango_gene`; **15 rows** in this fixture, not a future maximum.
Client: `core.config.IDangoGeneInfo`; Parse token: `0x60173e6`.
Binary SHA256: `5771875e47bde9776f863b4703a108abe97bde5ee8689248d2f352220ffe6124`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | geneID | gene_id | int32 |
| 2 | id | id | int32 |
| 3 | name | name | string |
| 4 | skinbaby | skinbaby | string |
| 5 | skinteen | skinteen | string |
| 6 | value | value | int32 |

Loader evidence:
- `core.config.DangoGene.get_fileName`, IL offset 0: config asset literal.
- `core.config.DangoGene.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### dangoGold

Resource/table: `dango_gold`; **6 rows** in this fixture, not a future maximum.
Client: `core.config.IDangoGoldInfo`; Parse token: `0x60173f4`.
Binary SHA256: `dde5fe84b28e39ae7f9c7dc70837175c066c390f6f9c4a985a3e7d7294c737c8`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | dangoGold | dango_gold | int32 |
| 2 | dangoNumMax | dango_num_max | int32 |
| 3 | dangoNumMix | dango_num_mix | int32 |
| 4 | id | id | int32 |

Loader evidence:
- `core.config.DangoGold.get_fileName`, IL offset 0: config asset literal.
- `core.config.DangoGold.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### dangoGuide

Resource/table: `dango_guide`; **14 rows** in this fixture, not a future maximum.
Client: `core.config.IDangoGuideInfo`; Parse token: `0x6017406`.
Binary SHA256: `90ca2c4769a9fa03d7d03328ee90823551527e2c7ff03b5773b206da63561554`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | dangoMovie | dango_movie | string |
| 2 | describe | describe | string |
| 3 | id | id | int32 |
| 4 | reward | reward | string |
| 5 | titile | titile | string |
| 6 | type | type | int32 |

Loader evidence:
- `core.config.DangoGuide.get_fileName`, IL offset 0: config asset literal.
- `core.config.DangoGuide.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### dangoHouse

Resource/table: `dango_house`; **10 rows** in this fixture, not a future maximum.
Client: `core.config.IDangoHouseInfo`; Parse token: `0x6017414`.
Binary SHA256: `10aad71ad42bd1def88f0dac993aa832b90255d8256bdb7a53507206e51a10a4`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | id | id | int32 |
| 2 | limitCost | limit_cost | int32 |
| 3 | name | name | string |
| 4 | roomID | room_id | int32 |

Loader evidence:
- `core.config.DangoHouse.get_fileName`, IL offset 0: config asset literal.
- `core.config.DangoHouse.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### dangoLv

Resource/table: `dango_level`; **6 rows** in this fixture, not a future maximum.
Client: `core.config.IDangoLvInfo`; Parse token: `0x6017430`.
Binary SHA256: `89d121c3f32ffbc15769941cee3e2791451c1ed6e13dcff9a74d6ed053eb3c9b`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | benefit1 | benefit1 | int32 |
| 2 | benefit2 | benefit2 | int32 |
| 3 | benefit3 | benefit3 | int32 |
| 4 | dangoTask | dango_task | int32[] |
| 5 | describe1 | describe1 | string |
| 6 | describe2 | describe2 | string |
| 7 | describe3 | describe3 | string |
| 8 | id | id | int32 |
| 9 | minorNum | minor_num | int32 |
| 10 | reward | reward | int32 |
| 11 | taskNum | task_num | int32 |

Loader evidence:
- `core.config.DangoLv.get_fileName`, IL offset 0: config asset literal.
- `core.config.DangoLv.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### dangoShop

Resource/table: `dango_shop`; **26 rows** in this fixture, not a future maximum.
Client: `core.config.IDangoShopInfo`; Parse token: `0x6017452`.
Binary SHA256: `2c35c438717a8c4cc28a737c0d8c3d7a71a02d0b36fb40138ccede34d028561e`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | NewMsglogId | new_msglog_id | int32 |
| 2 | Price | price | int32 |
| 3 | describe1 | describe1 | string |
| 4 | describe2 | describe2 | string |
| 5 | forever | forever | int32 |
| 6 | id | id | int32 |
| 7 | limit | limit | int32 |
| 8 | quantity | quantity | int32 |
| 9 | rewardinfo | rewardinfo | string |
| 10 | shopType1 | shop_type1 | int32 |
| 11 | shopType2 | shop_type2 | int32 |
| 12 | title | title | string |
| 13 | userinfo | userinfo | int32 |
| 14 | value | value | int32 |

Loader evidence:
- `core.config.DangoShop.get_fileName`, IL offset 0: config asset literal.
- `core.config.DangoShop.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### dangoSlot

Resource/table: `dango_slot`; **60 rows** in this fixture, not a future maximum.
Client: `core.config.IDangoSlotInfo`; Parse token: `0x6017460`.
Binary SHA256: `5e8fdbbee035721246b00c112e7894cddee5608b9233f810aac88ab250029167`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | id | id | int32 |
| 2 | name | name | string |
| 3 | petID | pet_id | int32 |
| 4 | value | value | int32 |

Loader evidence:
- `core.config.DangoSlot.get_fileName`, IL offset 0: config asset literal.
- `core.config.DangoSlot.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### dangoStory

Resource/table: `dango_story`; **15 rows** in this fixture, not a future maximum.
Client: `core.config.IDangoStoryInfo`; Parse token: `0x601746e`.
Binary SHA256: `80fdce53a5e846dab97ae0117e5f054976fb824ceefc83b1028ce63414edd5ac`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | dangoID | dango_id | int32 |
| 2 | dangoTask | dango_task | int32 |
| 3 | describe | describe | string |
| 4 | id | id | int32 |

Loader evidence:
- `core.config.DangoStory.get_fileName`, IL offset 0: config asset literal.
- `core.config.DangoStory.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### dangoTask

Resource/table: `dango_task`; **27 rows** in this fixture, not a future maximum.
Client: `core.config.IDangoTaskInfo`; Parse token: `0x601748c`.
Binary SHA256: `bd42e4771920b0f6503fab6970384e1be50db57f7bdbedfedb1ba6e9ca508b06`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | NewMsglogId | new_msglog_id | int32 |
| 2 | describe | describe | string |
| 3 | id | id | int32 |
| 4 | limit | limit | int32 |
| 5 | planet | planet | string |
| 6 | rewardinfo | rewardinfo | int32 |
| 7 | taskSkin | task_skin | string |
| 8 | taskTeam | task_team | int32 |
| 9 | tasktype | tasktype | int32 |
| 10 | time | time | int32 |
| 11 | title | title | string |
| 12 | value | value | int32 |

Loader evidence:
- `core.config.DangoTask.get_fileName`, IL offset 0: config asset literal.
- `core.config.DangoTask.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### dangochess

Resource/table: `dango_chess`; **32 rows** in this fixture, not a future maximum.
Client: `core.config.IDangochessInfo`; Parse token: `0x60173b4`.
Binary SHA256: `26d5d4d99a03fc400e413eed54d0d8ed752549c4d7e986bc852468a7f43ddee4`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | GuideCard | guide_card | string |
| 2 | cardid | cardid | string |
| 3 | chapterid | chapterid | int32 |
| 4 | dangoID | dango_id | int32 |
| 5 | firstreward | firstreward | string |
| 6 | id | id | int32 |
| 7 | stageid | stageid | int32 |
| 8 | starttime | starttime | string |

Loader evidence:
- `core.config.Dangochess.get_fileName`, IL offset 0: config asset literal.
- `core.config.Dangochess.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

### dangochessstage

Resource/table: `dango_chess_stage`; **96 rows** in this fixture, not a future maximum.
Client: `core.config.IDangochessstageInfo`; Parse token: `0x60173d4`.
Binary SHA256: `c0725cb47b80e82e93abec31fb2a68a70be519cf744a3aecc8b5c20926ec9b8c`.

| Order | Client field | API field | Binary type |
| --- | --- | --- | --- |
| 1 | chapterid | chapterid | int32 |
| 2 | hangid | hangid | int32 |
| 3 | id | id | int32 |
| 4 | lieid1 | lieid1 | int32 |
| 5 | lieid2 | lieid2 | int32 |
| 6 | lieid3 | lieid3 | int32 |
| 7 | lieid4 | lieid4 | int32 |
| 8 | lieid5 | lieid5 | int32 |
| 9 | lieid6 | lieid6 | int32 |
| 10 | lieid7 | lieid7 | int32 |
| 11 | lieid8 | lieid8 | int32 |
| 12 | lieid9 | lieid9 | int32 |
| 13 | stageid | stageid | int32 |

Loader evidence:
- `core.config.Dangochessstage.get_fileName`, IL offset 0: config asset literal.
- `core.config.Dangochessstage.Parse`, IL offset 56: Parse caller.

A missing direct caller in a bounded scan is not proof of non-use.

## Complete current configuration snapshot

`solaris.parse.snapshot` is the shared production export/promotion implementation.
The frozen current bundle passes all **295 required parsers**, including gems and
all **28 Somua/dango tables**. The explicit 49 historical retired inputs remain separately
inventoried; failed downloads do not create exemptions. Missing current inputs fail.
All JSON parses and strict round-trips complete before outputs/version markers are promoted.
Fork-only historical files are retained, never substituted for failed required data.

## Release contract

API v1, physical schema contract 2 and weekly semantic schema 8 are unchanged.
This feature adds `somua_filter`, `somua_model.main_att` and
`somua_status_effect.fx_on_load`; it does not add a weekly-content category.
Pin models and Solaris in config-sources and api-data to the same complete producer SHA.
Source markers must match that SHA and official version before publishing the API database.
The final release compares every Somua row/field against the same frozen source.
Publication is verified separately from bot synchronization or deployment.
