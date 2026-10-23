from http.client import IncompleteRead
import io
import logging

import pytest

from scripts.build_http import BuildHttpClient, BuildHttpConfig


def test_body_failure_is_within_single_retry_budget(monkeypatch, tmp_path):
    calls = []

    class Broken(io.BytesIO):
        def read(self, *args):
            raise IncompleteRead(b'partial')

    def request(*args, **kwargs):
        calls.append(1)
        return Broken() if len(calls) < 3 else io.BytesIO(b'valid')

    monkeypatch.setattr('scripts.build_http.urlopen', request)
    client = BuildHttpClient(
        BuildHttpConfig(30, 3, 0), logger=logging.getLogger(__name__)
    )
    assert client.download_bytes('https://test.invalid') == b'valid'
    assert len(calls) == 3


def test_failed_file_read_preserves_existing_database(monkeypatch, tmp_path):
    calls = []

    class Broken(io.BytesIO):
        def read1(self, *args):
            raise IncompleteRead(b'partial')

    def request(*args, **kwargs):
        calls.append(1)
        return Broken()

    monkeypatch.setattr('scripts.build_http.urlopen', request)
    file = tmp_path / 'data.sqlite'
    file.write_bytes(b'previous')
    client = BuildHttpClient(
        BuildHttpConfig(30, 3, 0), logger=logging.getLogger(__name__)
    )
    with pytest.raises(IncompleteRead):
        client.download_file('https://test.invalid', file)
    assert file.read_bytes() == b'previous'
    assert not file.with_suffix('.sqlite.tmp').exists()
    assert len(calls) == 3
