#!/usr/bin/env python
"""
K.NAKADA, kengo.nakada@gmail.com, kengo.nakada@mat.shimane-u.ac.jp
"""

from typing import Optional, Any, Callable

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
