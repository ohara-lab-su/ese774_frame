# Ese774 Frame (FastAPI Frame)

[ohara-lab-su](https://ohara-lab-su.github.io/) / [ese774_frame (doc)](https://ohara-lab-su.github.io/ese774_frame/)

主な特徴

- BL774 (SPring8) の互換っぽい RestAPI I/F を提供するもの (ese774_frame) 
- I/F 定義として　Pydantic を用いて、Open API には自動対応 (おそらくBL774っぽい)
- サーバー側に I/F を定義すればクライアント側では動的にdispatch自動でされる (BL774っぽい)
  - 自動ディスパッチ
  - server <--> client は透過型
- クライアント側には Pydantic オブジェクトは強制しない(元の python class を再現ん)

## 基本構造

```aiignore
Python ctrl (A: 純粋python I/F)
  ↓
Server: FastAPI + Pydantic (入力検証とJSON化のみ)
  ↓ (JSON)
Client: Pydantic で復元
  ↓
Python ctrl (Pydanticオブジェクト消して A: 純粋python I/F を再現)
```

## example

### api_server

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
    server.run(host=Config.SERVER_IP, port=Config.CTRL_PORT)

```

### make_pyi(1)

```python
if __name__ == "__main__":
    # 必要なAPI_SPECとクラス名をインポートしてここで切り替えられる
    from cobotta2.server_fastapi.spec_ctrl import cobotta_ctrl_api_spec
    from ese774_frame.clients import make_pyi_async_device_client

    make_pyi_async_device_client(
        filename="async_device_client.pyi",
        api_spec=cobotta_ctrl_api_spec,
        class_name="AsyncDeviceClient",
    )

```

### make_pyi(2)

```python
if __name__ == "__main__":
    from cobotta2.server_fastapi.spec_ctrl import cobotta_ctrl_api_spec
    from ese774_frame.clients import make_pyi_sync_device_client
    
    make_pyi_sync_device_client(
        filename="sync_device_client.pyi",
        api_spec=cobotta_ctrl_api_spec,
        class_name="SyncDeviceClient",
    )
```

### make_pyi(3)

```python
if __name__ == "__main__":
    # テスト例（API_SPEC/Loggerは実環境のものに差し替え推奨）
    from cobotta2.server_fastapi.spec_ctrl import cobotta_ctrl_api_spec
    from cobotta2.config import Config
    from ese774_frame.clients import SyncDeviceClient
    from x_logger.x_logger import XLogger

    logger = XLogger(
        log_level="debug",
        logger_name=getattr(Config, "CLIENT_LOGGER_NAME", "SyncDeviceClient"),
    )
    client = SyncDeviceClient(api_spec=cobotta_ctrl_api_spec, logger=logger)
    # 例: client.take_arm() など
    print(client.busy_status())

```

### router

サーバー側かで勝手に使われるので、機器を制御する側の人は知らなくて良い。

```python
if __name__ == "__main__":
    from cobotta2.server_fastapi.spec_ctrl import cobotta_ctrl_api_spec
    from ese774_frame.routers import make_pyi_device_router

    make_pyi_device_router(
        filename="device_router.pyi",
        api_spec=cobotta_ctrl_api_spec,
        class_name="DeviceRouter",
    )
    # 例: make_pyi_router_ctrl("router_state.pyi", cobotta_state_api_spec, class_name="CobottaStateRouter")

```

### client

```python
async def main():
    # import logging
    from cobotta2.config import Config
    from cobotta2.server_fastapi.spec_ctrl import cobotta_ctrl_api_spec
    from ese774_frame.clients import AsyncDeviceClient
    from x_logger.x_logger import XLogger
    #
    # # logging.getLogger("httpx").setLevel(logging.DEBUG)
    # logging.getLogger("httpx").setLevel(logging.WARNING)

    # from cobotta_server2.fastapi_spec_state import cobotta_state_api_spec

    logger_ = XLogger(
      log_level="debug",
      logger_name=Config.COBOTTA_CLIENT_LOGGER_NAME,
    )

    client = AsyncDeviceClient(
        server_ip=Config.SERVER_IP,
        server_port=Config.SERVER_PORT,
        api_spec=cobotta_ctrl_api_spec,
        logger=logger_,
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