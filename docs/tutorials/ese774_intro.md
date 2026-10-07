# チュートリアル

このセクションでは、v0.6.1 時点の `ese774_frame` の基本的な使い方を説明する。

現在は `api_spec=None` の完全自動 dispatch を基本形とする。Pydantic request model と `ApiSpec` は必須ではなく、明示的な
HTTP/OpenAPI 契約が必要な場合に使用する。

## フレームに渡す制御クラスを用意する

```python
#!/usr/bin/env python
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class SimpleStatus:
    name: str
    counter: int


class SimpleCtrl:
    """フレームワークテスト用の最小 Ctrl。"""

    def __init__(self, name: str = "simple", logger: Optional[Any] = None):
        self._name = name
        self._counter = 0
        self._logger = logger

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value

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

    def get_state(self) -> SimpleStatus:
        self._counter += 1
        return SimpleStatus(name=self._name, counter=self._counter)

    def general(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {"args": list(args), "kwargs": dict(kwargs)}
```

public method と static `property` は完全自動 dispatch の公開対象になる。`_` で始まるメンバは公開対象にしない。

`SimpleStatus` のような dataclass も、戻り値アノテーションが付いていれば通信後にクライアント側で復元できる。

## サーバーを起動する

基本形では Pydantic model、`ApiSpec`、機器固有 Router は不要である。

```python
#!/usr/bin/env python

from ese774_frame.api_server import FastApiServer

from ctrl import SimpleCtrl
from x_logger.x_logger import XLogger

import logging

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

if __name__ == "__main__":
    logger = XLogger(log_level="debug", logger_name="SimpleServer")

    server = FastApiServer(
        device_cls=SimpleCtrl,
        router_cls=None,
        config=None,
        api_spec=None,
        device_kwargs={"name": "simple"},
        logger=logger,
        logger_name="SimpleServer",
        lifespan_msg_prefix="SIMPLE",
        object_name="simple",
    )

    server.run(host="127.0.0.1", port=8000)
```

`router_cls=None` かつ `api_spec=None` の場合、Framework 標準の `DeviceRouter` が使用される。

公開したくない public API がある場合は `dispatch_exclude` を指定する。

```python
server = FastApiServer(
    device_cls=SimpleCtrl,
    router_cls=None,
    config=None,
    api_spec=None,
    object_name="simple",
    dispatch_exclude=["general"],
)
```

## クライアントから呼び出す

Sync client では通常の Python method に近い形で呼び出せる。

```python
from ese774_frame.clients import SyncDeviceClient

client = SyncDeviceClient(
    server_ip="127.0.0.1",
    server_port=8000,
    object_name="simple",
)

print(client.ping())
print(client.add(1, 2))
print(client.get_state())

print(client.name)
client.name = "renamed"
print(client.name)
```

Async client では method 呼び出しを `await` する。

```python
from ese774_frame.clients import AsyncDeviceClient

client = AsyncDeviceClient(
    server_ip="127.0.0.1",
    server_port=8000,
    object_name="simple",
)

print(await client.ping())
print(await client.add(1, 2))
print(await client.get_state())
```

Async client でも property は通常の属性アクセスとして扱う。

```python
print(client.name)
client.name = "renamed"
```

## client 用 pyi を生成する

完全自動 dispatch は実行時に API を解決するため、そのままでは IDE が device 固有 method の型を静的に推論できない。

`make_pyi_device_client()` に `device_class` を渡すと、制御クラスの public method/property から stub を生成できる。

```python
#!/usr/bin/env python

from pathlib import Path

from ese774_frame.clients.make_pyi_device_client import make_pyi_device_client

from ctrl import SimpleCtrl


def main() -> None:
    root = Path(__file__).resolve().parent

    make_pyi_device_client(
        filename=str(root / "clients" / "async_simple_client.pyi"),
        class_name="AsyncSimpleClient",
        async_mode=True,
        device_class=SimpleCtrl,
    )

    make_pyi_device_client(
        filename=str(root / "clients" / "sync_simple_client.pyi"),
        class_name="SyncSimpleClient",
        async_mode=False,
        device_class=SimpleCtrl,
    )


if __name__ == "__main__":
    main()
```

`api_spec` と `device_class` は同時には指定しない。

完全自動 dispatch では Router 自体の API は実行時に解決されるため、従来の `make_pyi_device_router()` をこの用途で生成する必要はない。
`make_pyi_device_router()` は ApiSpec モード用である。

## DeviceProxy を登録する

機器パッケージから統一的な生成入口を公開したい場合は `register_device_proxy()` を使用する。

完全自動 dispatch では `api_spec=None` とし、サーバーと同じ `object_name` を登録する。

```python
from ese774_frame import DeviceProxy
from ese774_frame.clients import register_device_proxy

register_device_proxy(
    "SimpleCtrl",
    api_spec=None,
    object_name="simple",
    default_async_mode=False,
    aliases=["simple"],
)

__all__ = [
    "DeviceProxy",
]
```

利用側では次のように生成する。

```python
from server import DeviceProxy

client = DeviceProxy(
    "SimpleCtrl",
    server_ip="127.0.0.1",
    server_port=8000,
    async_mode=False,
)

print(client.ping())
print(client.add(1, 2))
print(client.get_state())
```

機器固有の Sync / Async client class が必要な場合は、`register_device_proxy()` の `sync_client_cls` / `async_client_cls`
に登録できる。未指定の場合は Framework 標準 client が使用される。

## 機器固有 Router が必要な場合

一部 API だけサーバー側で特殊処理を行う場合は、`DeviceRouter` を継承した Router を指定する。

```python
from ese774_frame.routers import DeviceRouter


class SimpleRouter(DeviceRouter):
    pass
```

```python
server = FastApiServer(
    device_cls=SimpleCtrl,
    router_cls=SimpleRouter,
    config=None,
    api_spec=None,
    object_name="simple",
)
```

Router 側で override されていない API は device class の完全自動 dispatch にフォールバックする。

## ApiSpec / Pydantic モードを使う場合

明示的な request/response schema や OpenAPI 契約が必要な場合は、従来どおり Pydantic model と `ApiSpec` を定義する。

### model

```python
#!/usr/bin/env python
from pydantic import BaseModel


class AddRequest(BaseModel):
    a: int
    b: int
```

### spec

```python
#!/usr/bin/env python
from ese774_frame.models.api_spec import ApiSpec

from server.models import AddRequest

simple_api_spec = [
    ApiSpec(
        name="add",
        object_name="simple",
        request_model=AddRequest,
        response_model=None,
        method="post",
        summary="add",
        description="a + b",
    ),
]
```

property を ApiSpec で公開する場合は `kind="property"` を指定する。

```python
ApiSpec(
    name="name",
    object_name="simple",
    request_model=None,
    response_model=str,
    kind="property",
    writable=False,
)
```

ApiSpec モードでは `router_cls` が必要である。

```python
from ese774_frame.api_server import FastApiServer
from ese774_frame.routers.device_router import DeviceRouter

server = FastApiServer(
    device_cls=SimpleCtrl,
    router_cls=DeviceRouter,
    config=None,
    api_spec=simple_api_spec,
    object_name="simple",
)
```

client / router の `.pyi` は ApiSpec から生成できる。

```python
from ese774_frame.clients.make_pyi_device_client import make_pyi_device_client
from ese774_frame.routers.make_pyi_device_router import make_pyi_device_router

make_pyi_device_client(
    filename="sync_simple_client.pyi",
    api_spec=simple_api_spec,
    class_name="SyncSimpleClient",
    async_mode=False,
)

make_pyi_device_router(
    filename="simple_router.pyi",
    api_spec=simple_api_spec,
    class_name="SimpleRouter",
)
```

## 作者

- Kengo NAKADA
