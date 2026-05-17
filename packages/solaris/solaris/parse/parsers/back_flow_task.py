from typing import TypedDict

from ..base import BaseParser
from ..bytes_reader import BytesReader


class BackFlowTaskInfo(TypedDict):
    H5addition: list[str]
    H5jump: list[int]
    NewMsglogId: str
    describe: str
    id: int
    init: int
    num: int
    rewardinfo: list[int]
    taskparam: str
    tasktype: int
    time: int
    time2: str
    title: str
    value: str


class _BackFlowTaskData(TypedDict):
    item: list[BackFlowTaskInfo]


class BackFlowTaskParser(BaseParser[_BackFlowTaskData]):
    @classmethod
    def source_config_filename(cls) -> str:
        return 'BackFlowTask.bytes'

    @classmethod
    def parsed_config_filename(cls) -> str:
        return 'BackFlowTask.json'

    def parse(self, data: bytes) -> _BackFlowTaskData:
        reader = BytesReader(data)
        result: _BackFlowTaskData = {'item': []}
        if not reader.ReadBoolean():
            return result
        count = reader.ReadSignedInt()
        for _ in range(count):
            h5addition: list[str] = []
            if reader.ReadBoolean():
                h5c = reader.ReadSignedInt()
                h5addition = [reader.ReadUTFBytesWithLength() for _ in range(h5c)]
            h5jump: list[int] = []
            if reader.ReadBoolean():
                h5jc = reader.ReadSignedInt()
                h5jump = [reader.ReadSignedInt() for _ in range(h5jc)]
            new_msg_log_id = reader.ReadUTFBytesWithLength()
            describe = reader.ReadUTFBytesWithLength()
            id_val = reader.ReadSignedInt()
            init = reader.ReadSignedInt()
            num = reader.ReadSignedInt()
            rewardinfo: list[int] = []
            if reader.ReadBoolean():
                rc = reader.ReadSignedInt()
                rewardinfo = [reader.ReadSignedInt() for _ in range(rc)]
            taskparam = reader.ReadUTFBytesWithLength()
            tasktype = reader.ReadSignedInt()
            time = reader.ReadSignedInt()
            time2 = reader.ReadUTFBytesWithLength()
            title = reader.ReadUTFBytesWithLength()
            value = reader.ReadUTFBytesWithLength()
            item: BackFlowTaskInfo = {
                'H5addition': h5addition,
                'H5jump': h5jump,
                'NewMsglogId': new_msg_log_id,
                'describe': describe,
                'id': id_val,
                'init': init,
                'num': num,
                'rewardinfo': rewardinfo,
                'taskparam': taskparam,
                'tasktype': tasktype,
                'time': time,
                'time2': time2,
                'title': title,
                'value': value,
            }
            result['item'].append(item)
        return result
