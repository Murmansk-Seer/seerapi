from typing import TYPE_CHECKING

from seerapi_models.common import ResourceRef
from seerapi_models.field_effect import FieldEffect, FieldEffectType
from solaris.analyze.base import BaseDataSourceAnalyzer, DataImportConfig
from solaris.analyze.typing_ import AnalyzeResult
from solaris.analyze.utils import CategoryMap

if TYPE_CHECKING:
    from solaris.parse.parsers.effect_buff import EffectBuffItem


class FieldEffectAnalyzer(BaseDataSourceAnalyzer):
    """场地效果数据解析器"""

    @classmethod
    def get_data_import_config(cls) -> DataImportConfig:
        return DataImportConfig(
            unity_paths=('effectBuff.json',),
        )

    @classmethod
    def get_result_res_models(cls):
        return (FieldEffect, FieldEffectType)

    def analyze(self) -> tuple[AnalyzeResult, ...]:
        """分析场地效果数据

        处理流程：
        1. 加载 effectBuff.json 中的场地效果数据
        2. 根据 kind 字段创建效果类型映射
        3. 遍历效果数据，构建 FieldEffect 对象并建立双向引用

        Returns:
                包含 FieldEffect、FieldEffectType 的分析结果元组
        """
        buff_data: list['EffectBuffItem'] = self._get_data('unity', 'effectBuff.json')[
            'root'
        ]['buff']

        type_map: CategoryMap[int, FieldEffectType, ResourceRef['FieldEffect']] = (
            CategoryMap('effect')
        )
        for kind in {item['kind'] for item in buff_data}:
            type_map[kind] = FieldEffectType(id=kind, effect=[])

        effect_map: dict[int, FieldEffect] = {}
        for item in buff_data:
            id_ = item['id']
            kind = item['kind']
            effect_map[id_] = FieldEffect(
                id=id_,
                name=item['name'],
                desc=item['desc'],
                type=ResourceRef.from_model(FieldEffectType, id=kind),
            )
            type_map.add_element(kind, ResourceRef.from_model(effect_map[id_]))

        return (
            AnalyzeResult(model=FieldEffect, data=effect_map),
            AnalyzeResult(model=FieldEffectType, data=type_map),
        )
