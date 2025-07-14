#!/usr/bin/env python
"""

Kengo NAKADA:
https://github.com/shimane-dev, https://github.com/kengo-nakada
kengo.nakada@mat.shimane-u.ac.jp, kengo.nakada@gmail.com
"""
# generic_api_server.py

import sys
from fastapi import FastAPI
from contextlib import asynccontextmanager

from x_logger.x_logger import XLogger


class FastApiServer:

    def __init__(
        self,
        device_cls,
        router_cls,
        config,
        api_spec,
        device_kwargs=None,
        logger=None,
        logger_name="FastApiServer",
        lifespan_msg_prefix="DEVICE",
    ):
        self.device_cls = device_cls
        self.router_cls = router_cls
        self.config = config
        self.device_kwargs = device_kwargs or {}
        self.api_spec = api_spec
        self.logger = logger or XLogger(log_level="debug", logger_name=logger_name)
        self.lifespan_msg_prefix = lifespan_msg_prefix

        # FastAPI
        self.app = FastAPI(lifespan=self.lifespan)

        self._device = None
        self._router = None

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        try:
            self.logger.info(f"{self.lifespan_msg_prefix} 初期化中...")
            self._device = self.device_cls(**self.device_kwargs, logger=self.logger)
            self.logger.info(f"{self.lifespan_msg_prefix} 初期化完了")
        except KeyboardInterrupt as e:
            self.logger.error(e)
            sys.exit(-1)
        except Exception as e:
            self.logger.error(e)
            sys.exit(-1)

        try:
            # self._router = self.router_cls(self._device, logger=self.logger)
            self._router = self.router_cls(
                self._device, self.api_spec, logger=self.logger
            )
            app.include_router(self._router.router)
            yield  # サーバー起動中
        except KeyboardInterrupt as e:
            self.logger.error(e)
        except Exception as e:
            self.logger.error(e)
        finally:
            self.logger.info(f"{self.lifespan_msg_prefix} 解放中...")
            if self._device:
                self._device.disconnect()

    def run(self, host, port, reload=False):
        import multiprocessing
        import uvicorn

        multiprocessing.freeze_support()
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            reload=reload,
            log_config=None,
        )
