# https://github.com/urllib3/urllib3/issues/3439#issuecomment-2306400349
from __future__ import annotations

import ssl
from typing import Any

from requests.adapters import HTTPAdapter
from typing_extensions import override
from urllib3 import PoolManager
from urllib3.util import create_urllib3_context


class SSLAdapter(HTTPAdapter):
    def __init__(self, ssl_context: ssl.SSLContext | None = None, **kwargs: Any) -> None:
        self.ssl_context = ssl_context
        super().__init__(**kwargs)

    @override
    def init_poolmanager(self, connections: int, maxsize: int, block: bool = False, **pool_kwargs: Any) -> None:
        kwargs = pool_kwargs
        kwargs["ssl_context"] = self.ssl_context
        super().init_poolmanager(connections=connections, maxsize=maxsize, block=block, **kwargs)

    @override
    def proxy_manager_for(self, *args: Any, **kwargs: Any) -> PoolManager:
        kwargs["ssl_context"] = self.ssl_context
        result = super().proxy_manager_for(*args, **kwargs)
        assert isinstance(result, PoolManager)
        return result


DEFAULT_CIPHERS = ":".join(
    [
        "ECDHE+AESGCM",
        "ECDHE+CHACHA20",
        "DHE+AESGCM",
        "DHE+CHACHA20",
        "ECDH+AESGCM",
        "DH+AESGCM",
        "ECDH+AES",
        "DH+AES",
        "RSA+AESGCM",
        "RSA+AES",
        "!aNULL",
        "!eNULL",
        "!MD5",
        "!DSS",
        "!AESCCM",
    ]
)

CUSTOM_SSL_CTX = create_urllib3_context()
CUSTOM_SSL_CTX.load_default_certs()
CUSTOM_SSL_CTX.set_ciphers(DEFAULT_CIPHERS)
