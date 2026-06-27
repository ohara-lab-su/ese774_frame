# Ese774 Frame (FastAPI Frame)

[ohara-lab-su](https://ohara-lab-su.github.io/) / [ese774_frame (doc)](https://ohara-lab-su.github.io/ese774_frame/)

`ese774_frame` は、機器制御クラスを FastAPI 経由で透過的に公開し、クライアント側では元の Python 制御クラスに近い形で呼び出せるようにするためのフレームである。

主な特徴は以下である。

- BL774 / SPring-8 REST API 的な I/F を意識した通信フレーム
- I/F 定義に Pydantic model と `ApiSpec` を使う
- FastAPI / OpenAPI に自動対応する
- サーバー側の API 定義から router / client を構成する
- クライアント側では Pydantic model を直接意識せず、通常の Python メソッド呼び出しに近い形で利用できる
- `.pyi` を自動生成し、IDE の補完を利用できる

## 基本構造

```text
Python ctrl
  ↓
Server: FastAPI + Pydantic
  ↓ JSON / HTTP
Client: JSON を Python 引数・戻り値へ復元
  ↓
Python ctrl と同じ形のクライアント API
```

サーバー側では機器制御クラスを保持し、
router が `ApiSpec` に基づいて HTTP API を公開する。
クライアント側では `ApiSpec` に基づいて request を組み立て、
response を Python オブジェクトへ戻す。

## 機器側で用意するもの

機器ごとのパッケージでは、主に以下を用意する。

- 機器制御クラス
- Pydantic request model
- `ApiSpec`
- FastAPI router class
- Sync / Async client class
- `.pyi` 生成スクリプト
- `server_fastapi/__init__.py` での `DeviceProxy` 登録

`ese774_frame` は、これらを組み合わせて FastAPI server、router、client、`.pyi` 生成を共通化する。

## DeviceProxy

`DeviceProxy` は、登録済みの device class 名から client 実体を作成する入口である。

機器パッケージ側では、`server_fastapi/__init__.py` で `register_device_proxy()` を呼び出して device class 名と client class を登録する。

```python
from ese774_frame import DeviceProxy
from ese774_frame.clients import register_device_proxy

from xdm1000.server_fastapi.spec import xdm1000_api_spec
from xdm1000.server_fastapi.clients import (
    SyncXdm1000Client,
    AsyncXdm1000Client,
)

register_device_proxy(
    "Xdm1000Ctrl",
    async_client_cls=AsyncXdm1000Client,
    sync_client_cls=SyncXdm1000Client,
    api_spec=xdm1000_api_spec,
    default_async_mode=True,
    aliases=["xdm1000"],
)
```

利用側では、機器パッケージの `server_fastapi` を
import して登録を実行した上で、`DeviceProxy()` を使う。

```python
from ese774_frame import DeviceProxy
from xdm1000 import Config

import xdm1000.server_fastapi  # noqa: F401

config = Config("xdm1000_server1.yml")

dmm = DeviceProxy(
    "Xdm1000Ctrl",
    config=config,
    async_mode=False,
)

result = dmm.meas()
```

`DeviceProxy()` は registry を用いた動的生成であるため、フレーム本体だけではデバイス固有の戻り型を静的に決定できない。IDE 補完を有効にする場合は、機器パッケージ側で `DeviceProxy` 用の `.pyi` を生成する。

## DeviceProxy 用 pyi 生成

`make_pyi_device_proxy()` は、機器パッケージ側の `__init__.pyi` に `DeviceProxy()` の overload を生成するための関数である。

フレーム側は XDM1000 や COBOTTA などのデバイス固有情報を持たない。デバイス固有の import 行、device class 名、client class 名、alias は、各機器パッケージ側の `.pyi` 生成スクリプトから渡す。

例:

```python
from ese774_frame.clients.make_pyi_device_proxy import make_pyi_device_proxy

make_pyi_device_proxy(
    filename=str(root / "__init__.pyi"),
    import_lines=[
        "from xdm1000.server_fastapi.spec import xdm1000_api_spec",
        "from xdm1000.server_fastapi.routers import Xdm1000Router",
        "from xdm1000.server_fastapi.clients import SyncXdm1000Client",
        "from xdm1000.server_fastapi.clients import AsyncXdm1000Client",
    ],
    device_class="Xdm1000Ctrl",
    aliases=["xdm1000"],
    sync_client_class_name="SyncXdm1000Client",
    async_client_class_name="AsyncXdm1000Client",
    all_names=[
        "xdm1000_api_spec",
        "Xdm1000Router",
        "SyncXdm1000Client",
        "AsyncXdm1000Client",
        "DeviceProxy",
    ],
)
```

この `.pyi` により、
以下のようなコードで `dmm` が `SyncXdm1000Client` として補完される。

```python
from xdm1000.server_fastapi import DeviceProxy

dmm = DeviceProxy(
    "Xdm1000Ctrl",
    config=config,
    async_mode=False,
)
```

実行時の `DeviceProxy` は `ese774_frame.DeviceProxy` の
re-export であり、型情報だけを機器パッケージ側の `.pyi` で補う構成である。

## FastAPI server

```python
if __name__ == "__main__":
    from cobotta2.config import Config
    from cobotta2.cobotta_ctrl import CobottaCtrl
    from cobotta2.server_fastapi.spec_state import cobotta_state_api_spec
    from ese774_frame.routers import DeviceRouter
    from ese774_frame.api_server import FastApiServer

    server = FastApiServer(
        device_cls=CobottaCtrl,
        router_cls=DeviceRouter,
        config=Config,
        api_spec=cobotta_state_api_spec,
        device_kwargs={"cobotta_ip": Config.COBOTTA_IP},
        logger_name=Config.COBOTTA_SERVER_LOGGER_NAME,
        lifespan_msg_prefix="COBOTTA",
    )
    server.run(host=Config.SERVER_HOST, port=Config.CTRL_PORT)
```

## pyi 生成

client / router の `.pyi` は、それぞれ `make_pyi_device_client()` と `make_pyi_device_router()` で生成する。

```python
from ese774_frame.clients.make_pyi_device_client import make_pyi_device_client
from ese774_frame.routers.make_pyi_device_router import make_pyi_device_router

make_pyi_device_client(
    filename="async_device_client.pyi",
    api_spec=api_spec,
    class_name="AsyncDeviceClient",
    async_mode=True,
)

make_pyi_device_client(
    filename="sync_device_client.pyi",
    api_spec=api_spec,
    class_name="SyncDeviceClient",
    async_mode=False,
)

make_pyi_device_router(
    filename="device_router.pyi",
    api_spec=api_spec,
    class_name="DeviceRouter",
)
```

`DeviceProxy` の補完を有効にする場合は、機器パッケージ側の `__init__.pyi` も `make_pyi_device_proxy()` で生成する。

## client

```python
async def main():
    from cobotta2.config import Config
    from cobotta2.server_fastapi.spec_ctrl import cobotta_ctrl_api_spec
    from ese774_frame.clients import AsyncDeviceClient
    from x_logger.x_logger import XLogger

    logger = XLogger(
        log_level="debug",
        logger_name=Config.COBOTTA_CLIENT_LOGGER_NAME,
    )

    client = AsyncDeviceClient(
        server_host=Config.SERVER_HOST,
        server_port=Config.SERVER_PORT,
        api_spec=cobotta_ctrl_api_spec,
        logger=logger,
    )

    await client.take_arm()
    await client.turn_on_motor()
    await client.get_speed()
    await client.set_speed(100)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## 作者
- Kengo NAKADA
