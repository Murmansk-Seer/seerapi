from seerapi_models.source_reference import UnresolvedPetReference
from solaris.analyze.base import BaseDataSourceAnalyzer, DataImportConfig
from solaris.analyze.source_references import (
    official_pet_ids,
    partition_pet_ids,
    preserve_missing_pet_refs,
)
from solaris.analyze.typing_ import AnalyzeResult


class UnresolvedPetReferenceAnalyzer(BaseDataSourceAnalyzer):
    @classmethod
    def get_data_import_config(cls) -> DataImportConfig:
        return DataImportConfig(
            unity_paths=('monsters.json', 'effectIcon.json', 'effectDes.json')
        )

    @classmethod
    def get_result_res_models(cls):
        return (UnresolvedPetReference,)

    def analyze(self) -> tuple[AnalyzeResult, ...]:
        known = official_pet_ids(self._get_data('unity', 'monsters.json'))
        sources = (
            ('soulmark', 'effectIcon.json', 'pet_id', 'effect'),
            ('glossary_entry', 'effectDes.json', 'monster', 'item'),
        )
        records: dict[int, UnresolvedPetReference] = {}
        for resource, filename, field, container in sources:
            for row in self._get_data('unity', filename)['root'][container]:
                raw = row[field]
                ids = (
                    raw
                    if field == 'pet_id'
                    else (list(map(int, raw.split(','))) if raw and raw != '0' else [])
                )
                _, missing = partition_pet_ids(ids, known)
                for record in preserve_missing_pet_refs(
                    resource, filename, field, row, missing
                ):
                    if record.id in records and records[record.id] != record:
                        raise ValueError('Unresolved source reference ID collision')
                    records[record.id] = record
        return (AnalyzeResult(UnresolvedPetReference, records),)
