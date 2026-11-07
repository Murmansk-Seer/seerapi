"""Export all independently versioned Somua/dango configuration resources."""

from seerapi_models.somua import SOMUA_RESOURCES
from solaris.analyze.base import BaseDataSourceAnalyzer, DataImportConfig
from solaris.analyze.typing_ import AnalyzeResult


class SomuaAnalyzer(BaseDataSourceAnalyzer):
    @classmethod
    def get_data_import_config(cls) -> DataImportConfig:
        return DataImportConfig(unity_paths=tuple(SOMUA_RESOURCES))

    @classmethod
    def get_result_res_models(cls):
        return tuple(SOMUA_RESOURCES.values())

    def analyze(self) -> tuple[AnalyzeResult, ...]:
        results = []
        for filename, model in SOMUA_RESOURCES.items():
            source = self._get_data('unity', filename)
            if set(source) != {'data'} or not isinstance(source['data'], list):
                raise ValueError(f'Invalid Somua source: {filename}')
            rows = {}
            for row in source['data']:
                if set(row) != set(model.model_fields):
                    raise ValueError(f'Somua field drift: {filename}')
                item = model.model_validate(row, strict=True)
                if item.id in rows:
                    raise ValueError(f'Duplicate Somua ID: {filename}/{item.id}')
                rows[item.id] = item
            results.append(AnalyzeResult(model=model, data=rows))
        return tuple(results)
