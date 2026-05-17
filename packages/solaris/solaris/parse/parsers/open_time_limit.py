from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class TimeLimitItemDict(TypedDict):
    EndTime: str
    StartTime: str
    TID: int


class ActivityItemDict(TypedDict):
    ID: int
    TimeLimit: list[TimeLimitItemDict]


class ActivityConfigPoolDict(TypedDict):
    Activity: list[ActivityItemDict]


class _OpenTimeLimitData(TypedDict):
    ActivityConfigPool: ActivityConfigPoolDict | None


class OpenTimeLimitParser(BaseParser[_OpenTimeLimitData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'open_time_limit.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'open_time_limit.json'

    def parse(self, data: bytes) -> _OpenTimeLimitData:
        reader = BytesReader(data)
        result: _OpenTimeLimitData = {'ActivityConfigPool': None}

        if not reader.ReadBoolean():
            return result

        pool_activity: list[ActivityItemDict] = []

        if reader.ReadBoolean():
            activity_count = reader.ReadSignedInt()
            for _ in range(activity_count):
                ID = reader.ReadSignedInt()

                time_limit_list: list[TimeLimitItemDict] = []
                if reader.ReadBoolean():
                    time_limit_count = reader.ReadSignedInt()
                    for _ in range(time_limit_count):
                        EndTime = reader.ReadUTFBytesWithLength()
                        StartTime = reader.ReadUTFBytesWithLength()
                        TID = reader.ReadSignedInt()

                        time_limit_item: TimeLimitItemDict = {
                            'EndTime': EndTime,
                            'StartTime': StartTime,
                            'TID': TID,
                        }
                        time_limit_list.append(time_limit_item)

                activity_item: ActivityItemDict = {
                    'ID': ID,
                    'TimeLimit': time_limit_list,
                }
                pool_activity.append(activity_item)

        result['ActivityConfigPool'] = {'Activity': pool_activity}

        return result
