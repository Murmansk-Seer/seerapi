from typing import TYPE_CHECKING, TypedDict

from seerapi_models.sign import Sign, SignSubitem
from solaris.analyze.base import BaseDataSourceAnalyzer, DataImportConfig
from solaris.analyze.typing_ import AnalyzeResult

if TYPE_CHECKING:
    from solaris.parse.parsers.sign_icon_fight import ItemItem


class _SubitemDraft(TypedDict, total=False):
    desc: str
    icon_subid: int
    name: str


def _parse_keyed_entries(entries: list[str]) -> dict[int, str]:
    result: dict[int, str] = {}
    for entry in entries:
        key_str, sep, value = entry.partition('_')
        if not sep:
            continue
        result[int(key_str)] = value
    return result


def _build_subitems(item: 'ItemItem') -> dict[int, SignSubitem]:
    drafts: dict[int, _SubitemDraft] = {}

    for subitem_id, desc in _parse_keyed_entries(item['sp_des']).items():
        drafts.setdefault(subitem_id, {})['desc'] = desc

    for subitem_id, icon_subid in _parse_keyed_entries(item['sp_icon']).items():
        drafts.setdefault(subitem_id, {})['icon_subid'] = int(icon_subid)

    for subitem_id, name in _parse_keyed_entries(item['sp_tips']).items():
        drafts.setdefault(subitem_id, {})['name'] = name

    return {
        subitem_id: SignSubitem(
            subitem_id=subitem_id,
            desc=draft.get('desc') or None,
            icon_subid=draft.get('icon_subid') or None,
            name=draft.get('name') or None,
        )
        for subitem_id, draft in sorted(drafts.items())
    }


class SignAnalyzer(BaseDataSourceAnalyzer):
    """战斗印记图标配置解析器"""

    @classmethod
    def get_data_import_config(cls) -> DataImportConfig:
        return DataImportConfig(
            unity_paths=('signIconFight.json',),
        )

    @classmethod
    def get_result_res_models(cls):
        return (Sign,)

    def analyze(self) -> tuple[AnalyzeResult, ...]:
        sign_data: list['ItemItem'] = self._get_data('unity', 'signIconFight.json')[
            'config'
        ]['item']

        sign_map: dict[int, Sign] = {}
        for item in sign_data:
            sign_id = item['id']
            is_show_num = bool(item['is_show_num'])

            sign_map[sign_id] = Sign(
                id=sign_id,
                name=item['dec'],
                desc=item['des'] or None,
                sort=item['sort'],
                is_show_num=is_show_num,
                num_des=item['num_des'] or None,
                subitem=_build_subitems(item),
            )

        return (AnalyzeResult(model=Sign, data=sign_map),)
