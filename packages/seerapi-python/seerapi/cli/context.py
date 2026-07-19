from dataclasses import dataclass, field

from hishel.httpx import AsyncCacheClient
import httpx

from seerapi import SeerAPI


@dataclass
class CliContext:
    hostname: str = 'api.seerapi.com'
    scheme: str = 'https'
    version_path: str = 'v1'
    pretty: bool = False
    transport: httpx.BaseTransport | None = field(default=None, repr=False)

    def create_client(self) -> SeerAPI:
        client = SeerAPI(
            scheme=self.scheme,
            hostname=self.hostname,
            version_path=self.version_path,
        )
        if self.transport is not None:
            client._client = AsyncCacheClient(
                base_url=client.base_url,
                transport=self.transport,
            )
        return client
