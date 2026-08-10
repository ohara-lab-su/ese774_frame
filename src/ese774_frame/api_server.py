#!/usr/bin/env python
"""
FastAPI 用の汎用サーバーラッパー。

- device_cls でデバイス実体を生成
- router_cls で API ルータを生成
- FastAPI の lifespan で初期化/解放を管理

Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""

from typing import Any, Dict, Tuple, Optional

# generic_api_server.py

from fastapi import FastAPI
from contextlib import asynccontextmanager



class FastApiServer:
    """
    device/router/api_spec を束ねて FastAPI アプリを構築・実行する。

    lifecycle:
    - 起動: device 生成 -> router 生成 -> route 登録
    - 停止: device.disconnect があれば呼び出し
    """

    def __init__(
        self,
        device_cls,
        router_cls,
        config,
        api_spec=None,
        device_kwargs=None,
        logger: Optional[Any] = None,
        logger_name: str = "FastApiServer",
        log_level: Optional[str] = None,
        lifespan_msg_prefix: str = "DEVICE",
        object_name: Optional[str] = None,
        dispatch_exclude=None,
    ):

        if logger is None:
            import logging

            log_level = log_level or "INFO"
            logging.basicConfig(level=log_level.upper())
            logger = logging.getLogger(__name__)

        self.device_cls = device_cls
        self.router_cls = router_cls
        self.config = config
        self.device_kwargs = device_kwargs or {}
        self.api_spec = api_spec
        self.object_name = object_name
        self.dispatch_exclude = dispatch_exclude
        # self.logger = logger or XLogger(log_level="debug", logger_name=logger_name)
        self.logger = logger
        self.log_level = log_level
        self.lifespan_msg_prefix = lifespan_msg_prefix

        # FastAPI 本体（lifespan で初期化/解放）
        self.app = FastAPI(lifespan=self.lifespan)

        # 起動時に生成される実体
        self._device = None
        self._router = None

    @asynccontextmanager
    async def lifespan(
        self,
        app: FastAPI,
    ):
        """
        FastAPI lifespan ハンドラ。

        起動時に device/router を初期化し、終了時に disconnect を実行する。
        """
        try:
            # デバイス初期化
            self.logger.info(f"{self.lifespan_msg_prefix} 初期化中...")

            self._device = self.device_cls(
                **self.device_kwargs,
                logger=self.logger,
            )
            self.logger.info(f"{self.lifespan_msg_prefix} 初期化完了")
        except Exception as exc:
            message = "{} 初期化失敗: {}".format(
                self.lifespan_msg_prefix,
                exc,
            )
            raise RuntimeError(message) from None

        try:
            # Router 生成 → FastAPI へ登録
            #
            # api_spec is None:
            #   完全動的モード。機器固有 Router は不要で、Framework 標準の
            #   DeviceRouter を必ず使用する。router_cls=None も許可する。
            #   既存サーバーで router_cls を残したまま api_spec=None に変更しても
            #   動的モードへ移行できるよう、router_cls はこのモードでは使用しない。
            #
            # api_spec is not None:
            #   従来の ApiSpec/機器固有 Router モードをそのまま維持する。
            if self.api_spec is None:
                from ese774_frame.routers.device_router import DeviceRouter

                self._router = DeviceRouter(
                    self._device,
                    api_spec=None,
                    logger=self.logger,
                    log_level=self.log_level,
                    object_name=self.object_name,
                    dispatch_exclude=self.dispatch_exclude,
                )
            else:
                if self.router_cls is None:
                    raise ValueError(
                        "router_cls is required when api_spec is not None"
                    )

                # 既存 ApiSpec モードは従来の呼び出し形を完全維持する。
                self._router = self.router_cls(
                    self._device,
                    self.api_spec,
                    logger=self.logger,
                    log_level=self.log_level,
                )

            app.include_router(self._router.router)

            # サーバ起動中の寿命区間
            yield  # サーバー起動中

        except KeyboardInterrupt as e:
            self.logger.error(e)
        except Exception as e:
            self.logger.error(e)
        finally:
            self.logger.info(f"{self.lifespan_msg_prefix} 解放中...")
            disconnect = getattr(self._device, "disconnect", None)
            if callable(disconnect):
                disconnect()

    def run(
        self,
        host,
        port,
        reload=False,
    ):
        """
        uvicorn で FastAPI サーバを起動する。
        """
        import multiprocessing
        import uvicorn

        # Windows 実行対策
        multiprocessing.freeze_support()
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            reload=reload,
            log_config=None,
        )
