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
            #   完全動的モード。
            #   router_cls=None の場合だけ Framework 標準 DeviceRouter を使用する。
            #   router_cls が指定されている場合は、その機器固有 Router を維持する。
            #   機器固有 Router は DeviceRouter を継承し、特殊な remote semantics
            #   （例: server/client で処理を変える API）のみ override する。
            #   override されていない API は DeviceRouter の完全動的 dispatch に
            #   フォールバックする。
            #
            # api_spec is not None:
            #   従来の ApiSpec/機器固有 Router モードをそのまま維持する。
            if self.api_spec is None:
                from ese774_frame.routers.device_router import DeviceRouter

                dynamic_router_cls = self.router_cls or DeviceRouter

                # 完全動的モード用の追加引数を受け取れる Router には渡す。
                # 旧機器 Router の __init__ が従来シグネチャのままでも動くよう、
                # TypeError ではなく signature を見て渡す引数を選別する。
                import inspect

                init_sig = inspect.signature(dynamic_router_cls.__init__)
                params = init_sig.parameters
                accepts_varkw = any(
                    p.kind == inspect.Parameter.VAR_KEYWORD
                    for p in params.values()
                )

                router_kwargs = {
                    "logger": self.logger,
                    "log_level": self.log_level,
                }
                if accepts_varkw or "object_name" in params:
                    router_kwargs["object_name"] = self.object_name
                if accepts_varkw or "dispatch_exclude" in params:
                    router_kwargs["dispatch_exclude"] = self.dispatch_exclude

                self._router = dynamic_router_cls(
                    self._device,
                    None,
                    **router_kwargs,
                )

                # 旧 Router が object_name / dispatch_exclude を __init__ で
                # 受け取らない場合でも、基底 DeviceRouter の状態へ反映する。
                # route 登録後に object_name を変えることはできないため、
                # object_name の明示指定だけは旧 Router では利用不可とする。
                if self.dispatch_exclude is not None:
                    self._router._dispatch_exclude = set(self.dispatch_exclude)

                if (
                    self.object_name is not None
                    and "object_name" not in params
                    and not accepts_varkw
                    and getattr(self._router, "_object_name", None) != self.object_name
                ):
                    raise TypeError(
                        "dynamic custom router does not accept object_name; "
                        "update its __init__ to forward object_name to DeviceRouter"
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
