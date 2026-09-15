from typing import TYPE_CHECKING

from seerapi_models.buff import Buff, BuffType
from seerapi_models.common import ResourceRef
from solaris.analyze.base import BaseDataSourceAnalyzer, DataImportConfig
from solaris.analyze.typing_ import AnalyzeResult
from solaris.analyze.utils import CategoryMap

if TYPE_CHECKING:
    from solaris.parse.parsers.buff import BuffInfo


class BuffAnalyzer(BaseDataSourceAnalyzer):
    """Buff 配置数据解析器"""

    @classmethod
    def get_data_import_config(cls) -> DataImportConfig:
        return DataImportConfig(
            unity_paths=('buff.json',),
        )

    @classmethod
    def get_result_res_models(cls):
        return (Buff, BuffType)

    def analyze(self) -> tuple[AnalyzeResult, ...]:
        """分析 Buff 配置数据

        处理流程：
        1. 加载 buff.json 中的 Buff 数据
        2. 根据 icontype 字段创建图标类型映射
        3. 遍历 Buff 数据，构建 Buff 对象并建立双向引用

        Returns:
                包含 Buff、BuffType 的分析结果元组
        """
        buff_data: list['BuffInfo'] = self._get_data('unity', 'buff.json')['data']

        type_map: CategoryMap[int, BuffType, ResourceRef['Buff']] = CategoryMap('buff')
        for icontype in {item['icontype'] for item in buff_data}:
            type_map[icontype] = BuffType(id=icontype, buff=[])

        buff_map: dict[int, Buff] = {}
        for item in buff_data:
            id_ = item['id']
            icontype = item['icontype']
            buff_map[id_] = Buff(
                id=id_,
                desc=item['desc'],
                tag=item['tag'],
                desc_tag=item['desc_tag'] or None,
                icon=item['icon'],
                type=ResourceRef.from_model(BuffType, id=icontype),
            )
            type_map.add_element(icontype, ResourceRef.from_model(buff_map[id_]))

        return (
            AnalyzeResult(model=Buff, data=buff_map),
            AnalyzeResult(model=BuffType, data=type_map),
        )
