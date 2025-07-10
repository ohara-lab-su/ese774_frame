# FastAPI/Tango

## example

### api_server

```python

if __name__ == "__main__":
    from cobotta2.config import Config
    from cobotta2.cobotta_ctrl import CobottaCtrl
    from fastapi import DeviceRouter
    from cobotta2.server_fastapi.spec_state import cobotta_state_api_spec

    server = FastApiServer(
        device_cls=CobottaCtrl,
        router_cls=DeviceRouter,
        config=Config,
        api_spec=cobotta_state_api_spec,
        device_kwargs={"cobotta_ip": Config.COBOTTA1_IP},
        logger_name=Config.SERVER_LOGGER_NAME,
        lifespan_msg_prefix="COBOTTA",
    )
    server.run(host=Config.SERVER_IP, port=Config.CTRL_PORT)

```

### make_pyi(1)

```python
if __name__ == "__main__":
    # 必要なAPI_SPECとクラス名をインポートしてここで切り替えられる
    from cobotta2.server_fastapi.spec_ctrl import cobotta_ctrl_api_spec

    make_pyi_async_device_client(
        filename="async_device_client.pyi",
        api_spec=cobotta_ctrl_api_spec,
        class_name="AsyncDeviceClient",
    )

```

### make_pyh(2)

```python
if __name__ == "__main__":
    from cobotta2.server_fastapi.spec_ctrl import cobotta_ctrl_api_spec

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

    logger = XLogger(
        log_level="debug",
        logger_name=getattr(Config, "CLIENT_LOGGER_NAME", "SyncDeviceClient"),
    )
    client = SyncDeviceClient(api_spec=cobotta_ctrl_api_spec, logger=logger)
    # 例: client.take_arm() など
    print(client.busy_status())

```

### router

```python
# ===== main: 任意API_SPEC/クラス名で生成 =====
if __name__ == "__main__":
    from cobotta2.server_fastapi.spec_ctrl import cobotta_ctrl_api_spec

    make_pyi_device_router(
        filename="device_router.pyi",
        api_spec=cobotta_ctrl_api_spec,
        class_name="DeviceRouter",
    )
    # 例: make_pyi_router_ctrl("router_state.pyi", cobotta_state_api_spec, class_name="CobottaStateRouter")

```