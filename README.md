# Ese774 Frame (FastAPI Frame)

[ohara-lab-su](https://ohara-lab-su.github.io/) / [ese774_frame (doc)](https://ohara-lab-su.github.io/ese774_frame/)

`ese774_frame` は、Python で実装された機器制御クラスを FastAPI / HTTP 経由で公開し、クライアント側から元の制御クラスに近いインターフェースで利用するための通信フレームである。

サーバーとクライアントの間では JSON/HTTP を使用する。機器固有の通信処理は制御クラス側に保持し、HTTP 通信、API 公開、property 転送、型復元、client/proxy、IDE 補完用 `.pyi` の生成をフレーム側で共通化する。

主な機能は以下のとおり。

- Python 制御クラスの public method / property の自動公開
- `api_spec=None` による自動 dispatch
- `dispatch_exclude` による自動公開対象からの除外
- 機器固有 Router と自動 dispatch の併用
- read-only / read-write property の透過アクセス
- 型アノテーションを利用した dataclass 等の戻り値型の復元
- Sync / Async client
- `DeviceProxy` による機器 client の生成
- client / router / `DeviceProxy` 用 `.pyi` の生成
- Pydantic + `ApiSpec` による明示 API 定義
- FastAPI / OpenAPI

## 基本構造

```text
Python device control class
        |
        v
FastApiServer
        |
        +-- DeviceRouter / device-specific Router
        |       |
        |       +-- automatic method dispatch
        |       +-- property transport
        |       +-- explicit ApiSpec routes
        |
        v
     HTTP / JSON
        |
        v
SyncDeviceClient / AsyncDeviceClient
        |
        +-- Python method call
        +-- Python property access
        +-- return-type reconstruction
        |
        v
DeviceProxy / device package API
```

機器制御クラスは、ネットワーク通信を意識した wrapper に作り替える必要はない。通常の Python class として method、property、型アノテーションを定義し、フレームがその公開 API と通信境界を構成する。

## 自動 dispatch

`FastApiServer` に `api_spec=None` を渡すと、自動 dispatch が有効になる。

```python
from ese774_frame.api_server import FastApiServer

server = FastApiServer(
    device_cls=SimpleCtrl,
    router_cls=None,
    config=None,
    api_spec=None,
    device_kwargs={"name": "simple"},
    logger=logger,
    logger_name="SimpleServer",
    lifespan_msg_prefix="SIMPLE",
)

server.run(host="127.0.0.1", port=8000)
```

`router_cls=None` の場合はフレーム標準の `DeviceRouter` を使用する。`router_cls` を指定した場合は、その Router を使用しながら自動 dispatch を利用できる。

自動 dispatch では、制御クラスの public method と静的 property を公開対象とする。`_` で始まる名前は公開しない。

追加で公開対象から除外する API は `dispatch_exclude` で指定する。

```python
server = FastApiServer(
    device_cls=SimpleCtrl,
    router_cls=None,
    config=None,
    api_spec=None,
    dispatch_exclude=["release", "internal_reset"],
)
```

## property

制御クラスに定義された `@property` または `property()` は、method dispatch とは別の property transport で扱う。

```python
class SimpleCtrl:
    def __init__(self, name: str = "simple"):
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value: str) -> None:
        self._name = value
```

Sync client では通常の Python property と同様にアクセスできる。

```python
print(client.name)
client.name = "device1"
```

setter を持たない property は read-only として扱う。`__getattr__` によって実行時に生成される動的属性は、静的 property の自動検出対象には含めない。

## 戻り値の型復元

自動 dispatch では、サーバー側 method の戻り値アノテーションを metadata として client に伝える。

dataclass は JSON 互換の値として転送し、client 側で型情報を用いて再構築する。

```python
from dataclasses import dataclass
from typing import Optional


@dataclass
class MotorStatus:
    enabled: bool
    speed: float


class MotorCtrl:
    def get_status(self) -> Optional[MotorStatus]:
        return MotorStatus(
            enabled=True,
            speed=10.0,
        )
```

通信経路は JSON のまま維持される。

```text
MotorStatus
    -> JSON-compatible dict
    -> HTTP / JSON
    -> dict
    -> MotorStatus
```

型 descriptor は `Any`、`None`、通常の Python 型、dataclass、`Union` / `Optional`、`list`、`tuple`、`dict` を再帰的に扱う。

型情報を解決できない場合や dataclass の再構築に失敗した場合は、既存の JSON 値を保持する方向へフォールバックする。

## 機器固有 Router

自動 dispatch を使用しながら、一部の API だけを機器固有 Router で実装できる。

```python
from ese774_frame.routers.device_router import DeviceRouter


class SimpleRouter(DeviceRouter):
    async def emergency_stop(self):
        ...
```

機器固有 Router に同名の method/property が定義されている場合は Router 側の実装を優先し、それ以外は制御クラスへの自動 dispatch にフォールバックする。

これにより、通常の API は制御クラスから自動公開し、HTTP 層で特別な処理が必要な API だけを Router に記述できる。

## Pydantic + ApiSpec

HTTP API を明示的に定義する場合は、Pydantic request model と `ApiSpec` を使用する。

```python
from pydantic import BaseModel
from ese774_frame.models.api_spec import ApiSpec


class AddRequest(BaseModel):
    a: int
    b: int


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

property を `ApiSpec` で定義する場合は `kind="property"` を指定する。setter を許可する場合は `writable=True` とする。

```python
ApiSpec(
    name="name",
    object_name="simple",
    request_model=None,
    response_model=str,
    kind="property",
    writable=True,
)
```

`api_spec` を指定した場合、`FastApiServer` には `router_cls` が必要となる。

```python
server = FastApiServer(
    device_cls=SimpleCtrl,
    router_cls=DeviceRouter,
    config=None,
    api_spec=simple_api_spec,
)
```

## client

フレームは `SyncDeviceClient` と `AsyncDeviceClient` を提供する。

自動 dispatch では `api_spec=None` と `object_name` を指定する。

```python
from ese774_frame.clients import SyncDeviceClient

client = SyncDeviceClient(
    server_host="127.0.0.1",
    server_port=8000,
    api_spec=None,
    object_name="simple",
)

print(client.ping())
print(client.add(1, 2))
print(client.name)
```

Async client では method call を `await` する。

```python
from ese774_frame.clients import AsyncDeviceClient

client = AsyncDeviceClient(
    server_host="127.0.0.1",
    server_port=8000,
    api_spec=None,
    object_name="simple",
)

result = await client.add(1, 2)
```

Python の property 自体には `await` 構文がないため、Async client の property transport は内部で同期 HTTP client を使用する。

## DeviceProxy

`DeviceProxy` は、登録された device class 名から Sync / Async client を生成する。

機器パッケージの `__init__.py` などで `register_device_proxy()` を実行する。

```python
from ese774_frame import DeviceProxy
from ese774_frame.clients import register_device_proxy

register_device_proxy(
    "SimpleCtrl",
    async_client_cls=AsyncSimpleClient,
    sync_client_cls=SyncSimpleClient,
    api_spec=None,
    object_name="simple",
    default_async_mode=True,
    aliases=["simple"],
)
```

利用側では登録済みの class 名または alias を指定する。

```python
from server import DeviceProxy

client = DeviceProxy(
    "SimpleCtrl",
    async_mode=False,
)

print(client.ping())
```

機器固有 client class を登録しない場合は、フレーム標準の `SyncDeviceClient` / `AsyncDeviceClient` を使用する。

## `.pyi` 生成

実行時の自動 dispatch や `DeviceProxy` は動的に API を構成するため、そのままでは IDE が機器固有 API の型を推論できない。

`make_pyi_device_client()` は client 用 stub を生成する。

自動 dispatch の場合は `device_class` を渡す。

```python
from ese774_frame.clients.make_pyi_device_client import make_pyi_device_client

make_pyi_device_client(
    filename="sync_simple_client.pyi",
    device_class=SimpleCtrl,
    class_name="SyncSimpleClient",
    async_mode=False,
)

make_pyi_device_client(
    filename="async_simple_client.pyi",
    device_class=SimpleCtrl,
    class_name="AsyncSimpleClient",
    async_mode=True,
)
```

`device_class` から、自動 dispatch と同じ基準で public method/property を収集して stub を生成する。

`ApiSpec` モードでは `api_spec` を渡す。

```python
make_pyi_device_client(
    filename="sync_simple_client.pyi",
    api_spec=simple_api_spec,
    class_name="SyncSimpleClient",
    async_mode=False,
)
```

`api_spec` と `device_class` は同時には指定しない。

明示 `ApiSpec` モードの Router stub は `make_pyi_device_router()` で生成する。

```python
from ese774_frame.routers.make_pyi_device_router import make_pyi_device_router

make_pyi_device_router(
    filename="simple_router.pyi",
    api_spec=simple_api_spec,
    class_name="SimpleRouter",
)
```

## DeviceProxy 用 `.pyi`

`DeviceProxy()` は registry から実行時に client class を選択するため、戻り型を静的に決定できない。

機器パッケージ側の `__init__.pyi` に overload を生成し、IDE に device 固有 client 型を与える。

```python
from ese774_frame.clients.make_pyi_device_proxy import make_pyi_device_proxy

make_pyi_device_proxy(
    filename=str(root / "__init__.pyi"),
    import_lines=[
        "from server.clients import SyncSimpleClient",
        "from server.clients import AsyncSimpleClient",
    ],
    device_class="SimpleCtrl",
    aliases=["simple"],
    sync_client_class_name="SyncSimpleClient",
    async_client_class_name="AsyncSimpleClient",
    all_names=[
        "SyncSimpleClient",
        "AsyncSimpleClient",
        "DeviceProxy",
    ],
)
```

実行時には `ese774_frame.DeviceProxy` をそのまま re-export し、機器固有 wrapper は作成しない。型情報だけを `.pyi` で補う。

## チュートリアル

最小構成から server、client、`DeviceProxy`、`.pyi` 生成までの手順は [TUTORIAL.ja.md](TUTORIAL.ja.md) を参照。

## 作者

- Kengo NAKADA
