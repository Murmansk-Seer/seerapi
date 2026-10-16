from typing import Any, cast

import pytest

from seerapi_models.common import ResourceRef
from seerapi_models.skill import (
    SkillEffectParam,
    SkillEffectParamInType,
    SkillEffectType,
)
from solaris.analyze.analyzers.skill.analyzer import (
    BaseSkillEffectAnalyzer,
    SkillAnalyzer,
)
from solaris.analyze.analyzers.skill.effect_handlers import effect_handler_default


@pytest.mark.parametrize(
    ('skill_id', 'effect_id', 'count', 'template', 'positions'),
    [
        (29481, 1866, 5, '为自身随机附加{0}、{1}、{2}、{3}中的{4}种异常状态', range(4)),
        (38595, 495, 2, '若对手处于{0}状态，则{1}%概率秒杀对手', range(1)),
    ],
)
def test_official_empty_args_preserve_effect_and_template(
    monkeypatch, skill_id, effect_id, count, template, positions
) -> None:
    param = SkillEffectParam(id=1, infos=['状态A', '状态B'])
    definition = SkillEffectType(
        id=effect_id,
        args_num=count,
        info=template,
        analyze_info=template,
        skill=[],
        pve_effective=False,
        param=[
            SkillEffectParamInType(position=i, param=ResourceRef.from_model(param))
            for i in positions
        ],
    )
    analyzer = object.__new__(SkillAnalyzer)
    vars(analyzer).update(
        effect_type_map={effect_id: definition}, effect_param_map={1: param}
    )
    monkeypatch.setattr(
        BaseSkillEffectAnalyzer, 'type_combination_name_map', property(lambda _: {})
    )
    args: list[int] = []
    effects = analyzer.create_skill_effect([effect_id], args)
    skill = {'id': skill_id, 'skill_effect': effects}
    assert skill['id'] == skill_id
    assert len(effects) == 1
    assert effects[0].effect.id == effect_id
    assert effects[0].args == args == []
    assert effects[0].info == template
    assert effects[0].analyze_info == template


def test_partial_args_keep_available_mapping_and_missing_placeholder() -> None:
    param = SkillEffectParam(id=1, infos=['状态A', '状态B'])
    args = [1]
    info_args: list[object] = [1]
    first = effect_handler_default(args, param, 0, info_args, type_combination_map={})
    result = effect_handler_default(args, param, 1, first, type_combination_map={})
    assert result is info_args
    assert result == ['状态B']
    assert args == [1]


def test_unexpected_errors_still_propagate() -> None:
    with pytest.raises(KeyError, match='999'):
        effect_handler_default(
            [999], SkillEffectParam(id=22), 0, [999], type_combination_map={}
        )
    with pytest.raises(TypeError, match='indices'):
        effect_handler_default(
            cast(Any, ['bad']),
            SkillEffectParam(id=1, infos=['A']),
            0,
            ['bad'],
            type_combination_map={},
        )
