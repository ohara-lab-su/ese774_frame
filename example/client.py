#!/usr/bin/env python
"""
K.NAKADA, kengo.nakada@gmail.com, kengo.nakada@mat.shimane-u.ac.jp
"""

import asyncio
from fastapi_frame.clients.async_device_client import AsyncDeviceClient

from server.spec import simple_api_spec

import logging

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def main():
    client = AsyncDeviceClient(
        server_ip="127.0.0.1",
        server_port=8000,
        api_spec=simple_api_spec,
        logger=None,
    )

    print("ping:", await client.ping())
    print("add:", await client.add(a=2, b=3))
    print("echo:", await client.echo(msg="hello"))
    print("sum_list:", await client.sum_list(values=[1.0, 2.0, 3.5]))
    print("mix:", await client.mix(a=2, b=3, scale=2.0, tag="x"))
    print("make_tuple:", await client.make_tuple(a=1, b="z"))
    print("make_dict:", await client.make_dict(key="k", value=123))
    print("maybe(None):", await client.maybe(x=None))
    print("maybe(7):", await client.maybe(x=7))
    print("name:", await client.name())
    await client.set_name(name="changed")
    print("name(after):", await client.name())
    print("state:", await client.get_state())
    print(
        "dispatch(general):",
        await client.dispatch("general", 1, "x", 3.5, flag=True, data=[1, 2, 3]),
    )


if __name__ == "__main__":
    asyncio.run(main())
