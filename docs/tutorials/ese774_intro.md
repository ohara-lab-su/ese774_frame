# チュートリアル

このセクションでは `ese774_frame` の使い方を段階的に説明する。

## フレームに渡す制御クラスを用意する

```python
#!/usr/bin/env python
from typing import Any, Dict, List, Optional, Tuple


class SimpleCtrl:
    """フレームワークテスト用の最小 Ctrl。"""

    def __init__(self, name: str = "simple", logger: Optional[Any] = None):
        self._name = name
        self._counter = 0
        self._logger = logger

    @property
    def name(self) -> str:
        return self._name

    def ping(self) -> str:
        return "pong"

    def add(self, a: int, b: int) -> int:
        return a + b

    def echo(self, msg: str) -> str:
        return msg

    def sum_list(self, values: List[float]) -> float:
        return float(sum(values))

    def mix(
        self,
        a: int,
        b: int = 1,
        *,
        scale: float = 1.0,
        tag: Optional[str] = None,
    ) -> Dict[str, Any]:
        val = (a + b) * scale
        return {"value": val, "tag": tag}

    def make_tuple(self, a: int, b: str) -> Tuple[int, str]:
        return (a, b)

    def make_dict(self, key: str, value: Any) -> Dict[str, Any]:
        return {key: value}

    def maybe(self, x: Optional[int] = None) -> Optional[int]:
        return x

    def set_name(self, name: str) -> None:
        self._name = name

    def get_state(self) -> Dict[str, Any]:
        self._counter += 1
        return {"name": self._name, "counter": self._counter}

    def general(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {"args": list(args), "kwargs": dict(kwargs)}
```

## 公開 API を定義する

Pydantic request model と `ApiSpec` を用意する。

### spec

`ApiSpec` は、関数名、object 名、request model、HTTP method、OpenAPI 用の説明を定義する。

```python
#!/usr/bin/env python
from ese774_frame.models.api_spec import ApiSpec

from server.models import (
    AddRequest,
    EchoRequest,
    SumListRequest,
    MixRequest,
    TupleRequest,
    DictRequest,
    MaybeRequest,
    SetNameRequest,
)

simple_api_spec = [
    ApiSpec(
        name="ping",
        object_name="simple",
        request_model=None,
        response_model=None,
        method="post",
        summary="ping",
        description="return 'pong'",
    ),
    ApiSpec(
        name="add",
        object_name="simple",
        request_model=AddRequest,
        response_model=None,
        method="post",
        summary="add",
        description="a + b",
    ),
    ApiSpec(
        name="echo",
        object_name="simple",
        request_model=EchoRequest,
        response_model=None,
        method="post",
        summary="echo",
        description="echo msg",
    ),
    ApiSpec(
        name="sum_list",
        object_name="simple",
        request_model=SumListRequest,
        response_model=None,
        method="post",
        summary="sum_list",
        description="sum(values)",
    ),
    ApiSpec(
        name="mix",
        object_name="simple",
        request_model=MixRequest,
        response_model=None,
        method="post",
        summary="mix",
        description="(a+b)*scale",
    ),
    ApiSpec(
        name="make_tuple",
        object_name="simple",
        request_model=TupleRequest,
        response_model=None,
        method="post",
        summary="make_tuple",
        description="return tuple",
    ),
    ApiSpec(
        name="make_dict",
        object_name="simple",
        request_model=DictRequest,
        response_model=None,
        method="post",
        summary="make_dict",
        description="return dict",
    ),
    ApiSpec(
        name="maybe",
        object_name="simple",
        request_model=MaybeRequest,
        response_model=None,
        method="post",
        summary="maybe",
        description="optional return",
    ),
    ApiSpec(
        name="set_name",
        object_name="simple",
        request_model=SetNameRequest,
        response_model=None,
        method="post",
        summary="set_name",
        description="set name",
    ),
    ApiSpec(
        name="get_state",
        object_name="simple",
        request_model=None,
        response_model=None,
        method="post",
        summary="get_state",
        description="state dict",
    ),
    ApiSpec(
        name="name",
        object_name="simple",
        request_model=None,
        response_model=None,
        method="post",
        summary="name (property)",
        description="property access",
    ),
]
```

### model

API の引数を Pydantic model として定義する。

```python
#!/usr/bin/env python
from typing import Any, List, Optional
from pydantic import BaseModel


class AddRequest(BaseModel):
    a: int
    b: int


class EchoRequest(BaseModel):
    msg: str


class SumListRequest(BaseModel):
    values: List[float]


class MixRequest(BaseModel):
    a: int
    b: int = 1
    scale: float = 1.0
    tag: Optional[str] = None


class TupleRequest(BaseModel):
    a: int
    b: str


class DictRequest(BaseModel):
    key: str
    value: Any


class MaybeRequest(BaseModel):
    x: Optional[int] = None


class SetNameRequest(BaseModel):
    name: str
```

## サーバーを起動する

制御クラス、router、`ApiSpec` を `FastApiServer` に渡して起動する。

```python
#!/usr/bin/env python

from ese774_frame.api_server import FastApiServer
from ese774_frame.routers.device_router import DeviceRouter

from ctrl import SimpleCtrl
from server.spec import simple_api_spec
from x_logger.x_logger import XLogger

import logging

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


if __name__ == "__main__":
    logger = XLogger(log_level="debug", logger_name="SimpleServer")
    server = FastApiServer(
        device_cls=SimpleCtrl,
        router_cls=DeviceRouter,
        config=None,
        api_spec=simple_api_spec,
        device_kwargs={"name": "simple"},
        logger=logger,
        logger_name="SimpleServer",
        lifespan_msg_prefix="SIMPLE",
    )
    server.run(host="127.0.0.1", port=8000)
```

## クライアント用 pyi を生成する

client と router の `.pyi` は、フレーム側の生成関数を使って作る。

```python
#!/usr/bin/env python

from pathlib import Path

from ese774_frame.clients.make_pyi_device_client import make_pyi_device_client
from ese774_frame.routers.make_pyi_device_router import make_pyi_device_router

from server.spec import simple_api_spec


def main() -> None:
    root = Path(__file__).resolve().parent

    make_pyi_device_client(
        filename=str(root / "clients" / "async_simple_client.pyi"),
        api_spec=simple_api_spec,
        class_name="AsyncSimpleClient",
        async_mode=True,
    )

    make_pyi_device_client(
        filename=str(root / "clients" / "sync_simple_client.pyi"),
        api_spec=simple_api_spec,
        class_name="SyncSimpleClient",
        async_mode=False,
    )

    make_pyi_device_router(
        filename=str(root / "routers" / "simple_router.pyi"),
        api_spec=simple_api_spec,
        class_name="SimpleRouter",
    )


if __name__ == "__main__":
    main()
```

## DeviceProxy を登録する

機器パッケージの `server_fastapi/__init__.py` で `DeviceProxy` を登録する。

```python
from ese774_frame import DeviceProxy
from ese774_frame.clients import register_device_proxy

from server.spec import simple_api_spec
from server.clients import SyncSimpleClient, AsyncSimpleClient
from server.routers import SimpleRouter
from server.models import *

register_device_proxy(
    "SimpleCtrl",
    async_client_cls=AsyncSimpleClient,
    sync_client_cls=SyncSimpleClient,
    api_spec=simple_api_spec,
    default_async_mode=True,
    aliases=["simple"],
)

__all__ = [
    "simple_api_spec",
    "SimpleRouter",
    "SyncSimpleClient",
    "AsyncSimpleClient",
    "DeviceProxy",
]
```

`DeviceProxy` は `ese774_frame.DeviceProxy` を re-export するだけにする。デバイス固有の wrapper は作らない。

## DeviceProxy 用 pyi を生成する

`DeviceProxy()` は実行時 registry で client class を引くため、IDE は戻り型を推論できない。補完を効かせる場合は、機器パッケージ側の `server_fastapi/__init__.pyi` を生成する。

```python
from ese774_frame.clients.make_pyi_device_proxy import make_pyi_device_proxy

make_pyi_device_proxy(
    filename=str(root / "__init__.pyi"),
    import_lines=[
        "from server.spec import simple_api_spec",
        "from server.routers import SimpleRouter",
        "from server.clients import SyncSimpleClient",
        "from server.clients import AsyncSimpleClient",
    ],
    device_class="SimpleCtrl",
    aliases=["simple"],
    sync_client_class_name="SyncSimpleClient",
    async_client_class_name="AsyncSimpleClient",
    all_names=[
        "simple_api_spec",
        "SimpleRouter",
        "SyncSimpleClient",
        "AsyncSimpleClient",
        "DeviceProxy",
    ],
)
```

生成された `.pyi` により、以下の利用形で補完が効く。

```python
from server import DeviceProxy

client = DeviceProxy(
    "SimpleCtrl",
    async_mode=False,
)

client.ping()
client.add(1, 2)
```

## クライアントで制御プログラムを書く

```python
from server import DeviceProxy

client = DeviceProxy(
    "SimpleCtrl",
    async_mode=False,
)

print(client.ping())
print(client.add(1, 2))
print(client.get_state())
```

## 作者

- Kengo NAKADA
