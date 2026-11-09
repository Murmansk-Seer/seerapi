# Somua and dango Client Mapping

## Provenance

- ConfigPackage: `20261105230633`, bundle MD5 `55844b037e83296b14ae77b70e85a1b0`.
- DefaultPackage: `20261105235600`, GameLogic DLL MD5 `8694d8e59fd06de9fafa5895650ea25d`.
- Official package base: `https://newseer.61.com/Assets/StandaloneWindows64/`.
- Golden bytes, every decoded row, per-file SHA256, method tokens and Parse IL:
  `packages/solaris/tests/fixtures/somua/client-evidence.json` and sibling `.bytes` files.
- Layout order below is setter order in each client's `Parse` method, NOT property declaration order.
- All numeric scalars are signed little-endian int32. Strings are uint16 UTF-8 byte length + bytes.
- Nullable int32 arrays use a boolean presence flag, then signed count + elements when present.
  Null and an empty array remain distinct. Every file starts with an enabled boolean,
  followed by a signed row count only when enabled. Disabled files produce empty tables.
- Missing files, truncated data, negative lengths/counts, duplicate IDs and trailing bytes fail.
  Zero IDs and unknown numeric enum values are preserved.
- Source misspellings are intentional. API keys normalize casing only; no unverified units,
  percentages or relationships are inferred. Somua is not mapped onto a same-name pet.
- Current namespace: `module.dangoActivity`. Old dango tables are not declared deprecated.
  A missing direct call in this bounded IL scan is not proof of non-use.

## Resource names

Standard API resource lists use the first declared name field. Dango keeps its
raw client `name` as the primary label; `gene` remains an additional lookup key.
An empty primary name stays empty. If different lookup fields share an alias,
its named response includes every matching ID. These keys identify records in
the same resource; they do not associate a Dango or Somua record with a Seer pet.

标准 API 列表使用模型声明的第一个名称字段。Dango 以客户端原始 `name` 为主名称，
并保留 `gene` 作为额外查询键；主名称为空时保留空字符串，不用基因编码猜测填充。
不同字段命中同一个查询键时，名称响应保留所有匹配 ID。查询只在同一资源内匹配，
不会由名称或基因编码推断 Dango、Somua 与精灵的关系。

## Tables and Read Order

### Loading Evidence

GameLogic DLL SHA256:
`ba1112f30d8a0a5dd1543ce256ad9078a9a379587566a4df4604d9d8ecf17e1e`.
For every table below, the matching `core.config.<Class>.get_fileName`
loads its exact original asset stem at IL offset 0, and
`core.config.<Class>.Parse` calls the row-info Parse at IL offset 56.
The captured `loading_evidence` entries record both locations independently.

| Source Asset Stem | Client Loader Class |
| --- | --- |
| SomuaAchievementConfig | core.config.SomuaAchievementConfig |
| SomuaBasicAttritube | core.config.SomuaBasicAttritube |
| SomuaDispatchConfig | core.config.SomuaDispatchConfig |
| SomuaEntryConfig | core.config.SomuaEntryConfig |
| SomuaGeneConfig | core.config.SomuaGeneConfig |
| SomuaHouseConfig | core.config.SomuaHouseConfig |
| SomuaKeeperConfig | core.config.SomuaKeeperConfig |
| SomuaModelConfig | core.config.SomuaModelConfig |
| SomuaRankingConfig | core.config.SomuaRankingConfig |
| SomuaShopConfig | core.config.SomuaShopConfig |
| SomuaStatusEffectConfig | core.config.SomuaStatusEffectConfig |
| SomuaTaskConfig | core.config.SomuaTaskConfig |
| SomuaToturialConfig | core.config.SomuaToturialConfig |
| SomuaWeaponConfig | core.config.SomuaWeaponConfig |
| dango | core.config.Dango |
| dangoAction | core.config.DangoAction |
| dangoGene | core.config.DangoGene |
| dangoGold | core.config.DangoGold |
| dangoGuide | core.config.DangoGuide |
| dangoHouse | core.config.DangoHouse |
| dangoLv | core.config.DangoLv |
| dangoShop | core.config.DangoShop |
| dangoSlot | core.config.DangoSlot |
| dangoStory | core.config.DangoStory |
| dangoTask | core.config.DangoTask |
| dangochess | core.config.Dangochess |
| dangochessstage | core.config.Dangochessstage |

### SomuaAchievementConfig

Resource/table: `somua_achievement`; 40 records in this fixture (not a future limit).
Client: `core.config.ISomuaAchievementConfigInfo`, Parse token `0x6017f1e`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | condition | condition | int32 |
| 2 | desc | desc | string |
| 3 | icon | icon | int32 |
| 4 | id | id | int32 |
| 5 | name | name | string |
| 6 | type | type | int32 |

Direct field consumers in the captured scan: none found; do not infer that this table is unused.

### SomuaBasicAttritube

Resource/table: `somua_basic_attribute`; 21 records in this fixture (not a future limit).
Client: `core.config.ISomuaBasicAttritubeInfo`, Parse token `0x6017f36`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | attackRatio | attack_ratio | int32 |
| 2 | attackValue | attack_value | int32 |
| 3 | criticalChance | critical_chance | int32 |
| 4 | criticalDamageRatio | critical_damage_ratio | int32 |
| 5 | defenseRatio | defense_ratio | int32 |
| 6 | healthValue | health_value | int32 |
| 7 | id | id | int32 |
| 8 | knockRatio | knock_ratio | int32 |
| 9 | speedValue | speed_value | int32 |

Direct field consumers in the captured scan: `module.dangoActivity.DangoActivityDataMgr.GetSumoAttributes`.

### SomuaDispatchConfig

Resource/table: `somua_dispatch`; 7 records in this fixture (not a future limit).
Client: `core.config.ISomuaDispatchConfigInfo`, Parse token `0x6017f4c`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | award | award | string |
| 2 | bonus1 | bonus1 | string |
| 3 | bonus2 | bonus2 | string |
| 4 | bonus3 | bonus3 | string |
| 5 | id | id | int32 |
| 6 | name | name | string |
| 7 | tasktype | tasktype | int32 |
| 8 | value | value | int32 |

Direct field consumers in the captured scan: `module.dangoActivity.DangoActivityDataMgr.updateDispatchFlag`, `module.dangoActivity.DangoActivityDataMgr.RefreshMultDic`, `module.dangoActivity.DangoActivityDataMgr.RefreshRewardInfo`, `module.dangoActivity.DangoDispatchPanel.selectedTaskItem`, `module.dangoActivity.DangoDispatchPanel.StatLogger_Log_Complete`, `module.dangoActivity.DangoDispatchPanel.<addEvent>b__7_2`, `module.dangoActivity.DangoDispatchTaskItem.setData`.

### SomuaEntryConfig

Resource/table: `somua_entry`; 370 records in this fixture (not a future limit).
Client: `core.config.ISomuaEntryConfigInfo`, Parse token `0x6017f68`.

| Order | Client Field | API Field | Binary Type |
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

Direct field consumers in the captured scan: `module.dangoActivity.DangoActivityDataMgr.GetSumoAtk`, `module.dangoActivity.DangoActivityDataMgr.GetSumoDef`, `module.dangoActivity.DangoActivityDataMgr.GetSumoHp`, `module.dangoActivity.DangoActivityDataMgr.GetSumoCRT`, `module.dangoActivity.DangoActivityDataMgr.GetSumoSpd`, `module.dangoActivity.DangoBagItem.RefreshAblity`, `module.dangoActivity.SomuaBoxMain.updateSumoaInfo`, `module.dangoActivity.SomuaBoxMain.RefreshAblity`, `module.dangoActivity.SomuaBattleAbilityItem.SetData`, `module.dangoActivity.SomuaCombineInfoPop.RefreshSumoInfo`, `module.dangoActivity.SomuaCombineResultPopUp.refreshSumoInfo`, `module.dangoActivity.SumuaCombineItem.SetData`, `module.dangoActivity.SumuaCombineItem.RefreshAblity`, `module.dangoActivity.SomuaAbilityItem.SetData`, `module.dangoActivity.SomuaAbilityItem.ApplyConfig`, `module.dangoActivity.SomuaBattleDetailView.updateView`, `module.dangoActivity.DangoHandBookIntroducePop.RefreshEntryByTab`.

### SomuaGeneConfig

Resource/table: `somua_gene`; 15 records in this fixture (not a future limit).
Client: `core.config.ISomuaGeneConfigInfo`, Parse token `0x6017f7e`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | foodid | foodid | int32 |
| 2 | gene | gene | string |
| 3 | id | id | int32 |
| 4 | rarity | rarity | int32 |
| 5 | shopID | shop_id | int32 |
| 6 | skinbaby | skinbaby | string |
| 7 | skinteen | skinteen | string |
| 8 | sort | sort | int32 |

Direct field consumers in the captured scan: `module.dangoActivity.DangoActivityDataMgr.GetSomuaSkin`, `module.dangoActivity.DangoActivityDataMgr.GetSomuaShowGene`, `module.dangoActivity.SomuaGeneItem.ApplyGeneContent`, `module.dangoActivity.SomuaDetailChildPanel.InitFoodShopList`.

### SomuaHouseConfig

Resource/table: `somua_house`; 10 records in this fixture (not a future limit).
Client: `core.config.ISomuaHouseConfigInfo`, Parse token `0x6017f8c`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | id | id | int32 |
| 2 | limitCost | limit_cost | int32 |
| 3 | name | name | string |
| 4 | roomID | room_id | int32 |

Direct field consumers in the captured scan: `module.dangoActivity.DangoActivityDataMgr.HaveHomebaseLock`, `module.dangoActivity.SomuaBoxMain.getPlaceHouseName`, `module.dangoActivity.DangoWarehousePanel.onShow`, `module.dangoActivity.DangoWarehousePanel.OnItemClick`, `module.dangoActivity.DangoWarhouseItem.SetData`, `module.dangoActivity.DangoWarhouseItem.IsUnlock`.

### SomuaKeeperConfig

Resource/table: `somua_keeper`; 6 records in this fixture (not a future limit).
Client: `core.config.ISomuaKeeperConfigInfo`, Parse token `0x6017fb4`.

| Order | Client Field | API Field | Binary Type |
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

Direct field consumers in the captured scan: `module.dangoActivity.DangoActivityDataMgr.GetGolddropEfficiency`, `module.dangoActivity.DangoActivityDataMgr.GetMaxNotAdultDangoCount`, `module.dangoActivity.DangoActivityDataMgr.NextUnlockPrivilegeLevel`, `module.dangoActivity.DangoActivityDataMgr.IsNannyLevelRewardCanGet`, `module.dangoActivity.DangoNannyPanel.SetNannyInfo`, `module.dangoActivity.DangoNannyPanel.HaveLvupTask`, `module.dangoActivity.DangoNannyPanel.CanLevelUp`, `module.dangoActivity.DangoNannyPreviewItem.SetData`.

### SomuaModelConfig

Resource/table: `somua_model`; 68 records in this fixture (not a future limit).
Client: `core.config.ISomuaModelConfigInfo`, Parse token `0x6017fde`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | attackMode | attack_mode | int32 |
| 2 | attackModeSP | attack_mode_sp | int32 |
| 3 | describe | describe | string |
| 4 | id | id | int32 |
| 5 | isBack | is_back | int32 |
| 6 | isBody | is_body | int32 |
| 7 | isEar | is_ear | int32 |
| 8 | isExpression | is_expression | int32 |
| 9 | isHand | is_hand | int32 |
| 10 | isHead | is_head | int32 |
| 11 | isSurrounding | is_surrounding | int32 |
| 12 | isTail | is_tail | int32 |
| 13 | isTopwear | is_topwear | int32 |
| 14 | name | name | string |
| 15 | petID | pet_id | int32 |
| 16 | prefix | prefix | string |
| 17 | season | season | string |
| 18 | suffix | suffix | string |

Direct field consumers in the captured scan: `module.dangoActivity.DangoHandBookIntroducePop.RefreshEntryByTab`, `module.dangoActivity.SomaAvatarSkinUtil.BuildPartsCacheKey`, `module.dangoActivity.SomaAvatarSkinUtil.CollectSkinNames`.

### SomuaRankingConfig

Resource/table: `somua_ranking`; 16 records in this fixture (not a future limit).
Client: `core.config.ISomuaRankingConfigInfo`, Parse token `0x6017ff2`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | icon | icon | int32 |
| 2 | id | id | int32 |
| 3 | isFalling | is_falling | int32 |
| 4 | level | level | string |
| 5 | minscore | minscore | string |
| 6 | name | name | string |
| 7 | phase | phase | int32 |

Direct field consumers in the captured scan: none found; do not infer that this table is unused.

### SomuaShopConfig

Resource/table: `somua_shop`; 14 records in this fixture (not a future limit).
Client: `core.config.ISomuaShopConfigInfo`, Parse token `0x6018014`.

| Order | Client Field | API Field | Binary Type |
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

Direct field consumers in the captured scan: `module.dangoActivity.SomuaDetailChildPanel.InitFoodShopList`, `module.dangoActivity.SomuaDetailChildPanel.RefreshFoodInfo`, `module.dangoActivity.SomuaDetailChildPanel.RefreshBuyBtnState`, `module.dangoActivity.SomuaDetailChildPanel.OnClickBuy`, `module.dangoActivity.DangoShopItem.<Awake>b__14_1`.

### SomuaStatusEffectConfig

Resource/table: `somua_status_effect`; 24 records in this fixture (not a future limit).
Client: `core.config.ISomuaStatusEffectConfigInfo`, Parse token `0x601802e`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | fxOnGet | fx_on_get | string |
| 2 | fxOnTrig | fx_on_trig | string |
| 3 | icon | icon | int32 |
| 4 | id | id | int32 |
| 5 | maxStack | max_stack | int32 |
| 6 | stackRule | stack_rule | string |
| 7 | statusDesc | status_desc | string |
| 8 | statusName | status_name | string |
| 9 | type | type | int32 |
| 10 | valueRule | value_rule | string |

Direct field consumers in the captured scan: none found; do not infer that this table is unused.

### SomuaTaskConfig

Resource/table: `somua_task`; 49 records in this fixture (not a future limit).
Client: `core.config.ISomuaTaskConfigInfo`, Parse token `0x6018044`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | describe | describe | string |
| 2 | group | group | int32 |
| 3 | id | id | int32 |
| 4 | period | period | int32 |
| 5 | rewardinfo | rewardinfo | string |
| 6 | season | season | int32 |
| 7 | tasktype | tasktype | int32 |
| 8 | value | value | int32 |

Direct field consumers in the captured scan: `module.dangoActivity.SomuaArenaTaskPopUp.GetTaskItem`, `module.dangoActivity.SomuaArenaTaskPopUp.RefreshTaskInfo`, `module.dangoActivity.SomuaArenaTaskPopUp.<RefreshTaskList>b__11_0`, `module.dangoActivity.DangoNannyTaskItem.SetData`.

### SomuaToturialConfig

Resource/table: `somua_tutorial`; 9 records in this fixture (not a future limit).
Client: `core.config.ISomuaToturialConfigInfo`, Parse token `0x6018054`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | id | id | int32 |
| 2 | img | img | string |
| 3 | module | module | string |
| 4 | page | page | int32 |
| 5 | txt | txt | string |

Direct field consumers in the captured scan: none found; do not infer that this table is unused.

### SomuaWeaponConfig

Resource/table: `somua_weapon`; 73 records in this fixture (not a future limit).
Client: `core.config.ISomuaWeaponConfigInfo`, Parse token `0x6018064`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | fxOnHit | fx_on_hit | string |
| 2 | id | id | int32 |
| 3 | prefab | prefab | string |
| 4 | shape | shape | int32 |
| 5 | type | type | int32 |

Direct field consumers in the captured scan: none found; do not infer that this table is unused.

### dango

Resource/table: `dango`; 57 records in this fixture (not a future limit).
Client: `core.config.IDangoInfo`, Parse token `0x6016ea6`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | describe | describe | string |
| 2 | gene | gene | string |
| 3 | grade | grade | int32 |
| 4 | id | id | int32 |
| 5 | name | name | string |
| 6 | petID | pet_id | int32 |
| 7 | skin | skin | string |
| 8 | value | value | int32 |

Direct field consumers in the captured scan: none found; do not infer that this table is unused.

### dangoAction

Resource/table: `dango_action`; 300 records in this fixture (not a future limit).
Client: `core.config.IDangoActionInfo`, Parse token `0x6016ebc`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | action | action | string |
| 2 | actionTeam | action_team | int32 |
| 3 | dangoID | dango_id | int32[] |
| 4 | describ | describ | string |
| 5 | id | id | int32 |
| 6 | limitDango | limit_dango | int32 |
| 7 | limitType | limit_type | int32 |
| 8 | value | value | int32 |

Direct field consumers in the captured scan: `module.dangoActivity.DangoActivityDataMgr.GetRandomEmojiAction`, `module.dangoActivity.DangoActivityDataMgr.GetRandomIntervalAction`, `module.dangoActivity.DangoActivityDataMgr.InitMeetActionMap`, `module.dangoActivity.DangoActivityDataMgr.GetMeetActionByTargetId`, `module.dangoActivity.DangoModelUIDisplay.ExcuteAction`.

### dangoGene

Resource/table: `dango_gene`; 15 records in this fixture (not a future limit).
Client: `core.config.IDangoGeneInfo`, Parse token `0x6016f04`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | geneID | gene_id | int32 |
| 2 | id | id | int32 |
| 3 | name | name | string |
| 4 | skinbaby | skinbaby | string |
| 5 | skinteen | skinteen | string |
| 6 | value | value | int32 |

Direct field consumers in the captured scan: none found; do not infer that this table is unused.

### dangoGold

Resource/table: `dango_gold`; 6 records in this fixture (not a future limit).
Client: `core.config.IDangoGoldInfo`, Parse token `0x6016f12`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | dangoGold | dango_gold | int32 |
| 2 | dangoNumMax | dango_num_max | int32 |
| 3 | dangoNumMix | dango_num_mix | int32 |
| 4 | id | id | int32 |

Direct field consumers in the captured scan: none found; do not infer that this table is unused.

### dangoGuide

Resource/table: `dango_guide`; 14 records in this fixture (not a future limit).
Client: `core.config.IDangoGuideInfo`, Parse token `0x6016f24`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | dangoMovie | dango_movie | string |
| 2 | describe | describe | string |
| 3 | id | id | int32 |
| 4 | reward | reward | string |
| 5 | titile | titile | string |
| 6 | type | type | int32 |

Direct field consumers in the captured scan: `module.dangoActivity.DangoGuidePop.OnGetItemByIndex`, `module.dangoActivity.DangoGuidePop.OnClickGetReward`.

### dangoHouse

Resource/table: `dango_house`; 10 records in this fixture (not a future limit).
Client: `core.config.IDangoHouseInfo`, Parse token `0x6016f32`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | id | id | int32 |
| 2 | limitCost | limit_cost | int32 |
| 3 | name | name | string |
| 4 | roomID | room_id | int32 |

Direct field consumers in the captured scan: none found; do not infer that this table is unused.

### dangoLv

Resource/table: `dango_level`; 6 records in this fixture (not a future limit).
Client: `core.config.IDangoLvInfo`, Parse token `0x6016f4e`.

| Order | Client Field | API Field | Binary Type |
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

Direct field consumers in the captured scan: none found; do not infer that this table is unused.

### dangoShop

Resource/table: `dango_shop`; 26 records in this fixture (not a future limit).
Client: `core.config.IDangoShopInfo`, Parse token `0x6016f70`.

| Order | Client Field | API Field | Binary Type |
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

Direct field consumers in the captured scan: none found; do not infer that this table is unused.

### dangoSlot

Resource/table: `dango_slot`; 60 records in this fixture (not a future limit).
Client: `core.config.IDangoSlotInfo`, Parse token `0x6016f7e`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | id | id | int32 |
| 2 | name | name | string |
| 3 | petID | pet_id | int32 |
| 4 | value | value | int32 |

Direct field consumers in the captured scan: `module.dangoSlotMain.DangoSlotDataMgr.IsGetAllPet`.

### dangoStory

Resource/table: `dango_story`; 15 records in this fixture (not a future limit).
Client: `core.config.IDangoStoryInfo`, Parse token `0x6016f8c`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | dangoID | dango_id | int32 |
| 2 | dangoTask | dango_task | int32 |
| 3 | describe | describe | string |
| 4 | id | id | int32 |

Direct field consumers in the captured scan: none found; do not infer that this table is unused.

### dangoTask

Resource/table: `dango_task`; 27 records in this fixture (not a future limit).
Client: `core.config.IDangoTaskInfo`, Parse token `0x6016faa`.

| Order | Client Field | API Field | Binary Type |
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

Direct field consumers in the captured scan: none found; do not infer that this table is unused.

### dangochess

Resource/table: `dango_chess`; 32 records in this fixture (not a future limit).
Client: `core.config.IDangochessInfo`, Parse token `0x6016ed2`.

| Order | Client Field | API Field | Binary Type |
| --- | --- | --- | --- |
| 1 | GuideCard | guide_card | string |
| 2 | cardid | cardid | string |
| 3 | chapterid | chapterid | int32 |
| 4 | dangoID | dango_id | int32 |
| 5 | firstreward | firstreward | string |
| 6 | id | id | int32 |
| 7 | stageid | stageid | int32 |
| 8 | starttime | starttime | string |

Direct field consumers in the captured scan: none found; do not infer that this table is unused.

### dangochessstage

Resource/table: `dango_chess_stage`; 96 records in this fixture (not a future limit).
Client: `core.config.IDangochessstageInfo`, Parse token `0x6016ef2`.

| Order | Client Field | API Field | Binary Type |
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

Direct field consumers in the captured scan: none found; do not infer that this table is unused.

## Build and Release Handoff

No commit or production release is performed by this implementation.
After the feature is reviewed and committed, set organization Actions variable
`SEERAPI_TOOLING_REVISION` to that **full 40-character feature commit SHA**, visible to
both config-sources and api-data. Both pipelines install Solaris and models from that SHA.
There is deliberately no fallback to PyPI or the old pre-feature SHA.

Run config-sources refresh first. Its skip condition includes official version,
parser revision and Somua export version. All 27 tables are parsed before outputs
are written, and the workflow commits only after success. A failure leaves the
last remote publication intact. Disabled tables export empty rows rather than old data.

api-data verifies the frozen source's `.parser-revision` and `.somua-version`, and
includes parser SHA in its publication fingerprint. It generates standard JSON,
SQLite, JSON Schema and OpenAPI through the existing analyzer/output machinery.
Both intermediate and final publishers compare every Somua field/row to the frozen
source before uploading. Final SeerAPI schema requirements include these 27 ORM tables.

Python client outputs are generated with
`python packages/seerapi-python/scripts/generate_client.py`.
TypeScript generation uses the existing local OpenAPI/schema DB workflow, not the
currently deployed official service. API v1, physical contract 2 and weekly semantic
schema 8 remain unchanged. There is no new weekly-content category or HTTP server.
