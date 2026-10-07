# Ese774 Frame (FastAPI Frame)

[ohara-lab-su](https://ohara-lab-su.github.io/) / [ese774_frame (doc)](https://ohara-lab-su.github.io/ese774_frame/)

`ese774_frame` is a communication frame for exposing Python device-control classes through FastAPI/HTTP while allowing clients to use an interface close to the original control class.

Communication between server and client uses JSON/HTTP. Device-specific communication remains in the control class, while the frame provides common handling for HTTP transport, API exposure, property transport, return-type reconstruction, clients/proxies, and `.pyi` generation for IDE completion.

Main features include:

- automatic exposure of public methods and properties of Python control classes
- automatic dispatch with `api_spec=None`
- exclusion from automatic exposure with `dispatch_exclude`
- combination of device-specific Routers with automatic dispatch
- transparent access to read-only and read-write properties
- reconstruction of dataclass and other return types from type annotations
- Sync and Async clients
- client creation through `DeviceProxy`
- `.pyi` generation for clients, Routers, and `DeviceProxy`
- explicit API definitions using Pydantic + `ApiSpec`
- FastAPI / OpenAPI integration

## Architecture

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

A device-control class does not need to be rewritten as a network-aware wrapper. Methods, properties, and type annotations can be defined on an ordinary Python class, and the frame constructs the exposed API and communication boundary around it.

## Automatic dispatch

Passing `api_spec=None` to `FastApiServer` enables automatic dispatch.

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

When `router_cls=None`, the standard `DeviceRouter` provided by the frame is used. When `router_cls` is specified, automatic dispatch can be used together with that Router.

Automatic dispatch exposes public methods and static properties of the control class. Names beginning with `_` are not exposed.

Additional APIs can be excluded with `dispatch_exclude`.

```python
server = FastApiServer(
    device_cls=SimpleCtrl,
    router_cls=None,
    config=None,
    api_spec=None,
    dispatch_exclude=["release", "internal_reset"],
)
```

## Properties

`@property` and `property()` definitions on the control class are handled by a property transport separate from method dispatch.

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

A Sync client can access them like normal Python properties.

```python
print(client.name)
client.name = "device1"
```

A property without a setter is treated as read-only. Dynamic attributes produced at runtime through `__getattr__` are not included in automatic static-property detection.

## Return-type reconstruction

In automatic dispatch, the server sends return-type annotations for exposed methods to the client as metadata.

Dataclass instances are transferred as JSON-compatible values and reconstructed on the client using the type information.

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

The transport itself remains JSON based.

```text
MotorStatus
    -> JSON-compatible dict
    -> HTTP / JSON
    -> dict
    -> MotorStatus
```

Type descriptors recursively support `Any`, `None`, ordinary Python types, dataclasses, `Union` / `Optional`, `list`, `tuple`, and `dict`.

If type information cannot be resolved or dataclass reconstruction fails, the client falls back toward preserving the existing JSON value.

## Device-specific Routers

A device-specific Router can implement only the APIs that require special HTTP-layer behavior while automatic dispatch remains enabled.

```python
from ese774_frame.routers.device_router import DeviceRouter


class SimpleRouter(DeviceRouter):
    async def emergency_stop(self):
        ...
```

When the device-specific Router defines a method/property with the same name, the Router implementation takes precedence. Other APIs fall back to automatic dispatch to the control class.

This allows ordinary APIs to be exposed directly from the control class while keeping only exceptional HTTP-specific behavior in the Router.

## Pydantic + ApiSpec

When an HTTP API must be defined explicitly, use Pydantic request models and `ApiSpec`.

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

For a property defined through `ApiSpec`, specify `kind="property"`. Set `writable=True` when a setter is allowed.

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

When `api_spec` is provided, `FastApiServer` requires `router_cls`.

```python
server = FastApiServer(
    device_cls=SimpleCtrl,
    router_cls=DeviceRouter,
    config=None,
    api_spec=simple_api_spec,
)
```

## Clients

The frame provides `SyncDeviceClient` and `AsyncDeviceClient`.

For automatic dispatch, specify `api_spec=None` and `object_name`.

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

Method calls on the Async client are awaited.

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

Because Python properties themselves have no `await` syntax, property transport in `AsyncDeviceClient` internally uses a synchronous HTTP client.

## DeviceProxy

`DeviceProxy` creates a Sync or Async client from a registered device-class name.

Register the device in the device package, for example in its `__init__.py`.

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

Client code can use either the registered class name or an alias.

```python
from server import DeviceProxy

client = DeviceProxy(
    "SimpleCtrl",
    async_mode=False,
)

print(client.ping())
```

If device-specific client classes are not registered, the frame falls back to its standard `SyncDeviceClient` / `AsyncDeviceClient`.

## `.pyi` generation

Automatic dispatch and `DeviceProxy` construct APIs dynamically at runtime, so an IDE cannot infer device-specific APIs without additional type information.

`make_pyi_device_client()` generates client stubs.

For automatic dispatch, pass `device_class`.

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

The generator collects public methods and properties from `device_class` using the same exposure rules as automatic dispatch.

In `ApiSpec` mode, pass `api_spec`.

```python
make_pyi_device_client(
    filename="sync_simple_client.pyi",
    api_spec=simple_api_spec,
    class_name="SyncSimpleClient",
    async_mode=False,
)
```

`api_spec` and `device_class` are mutually exclusive.

For explicit `ApiSpec` mode, Router stubs can be generated with `make_pyi_device_router()`.

```python
from ese774_frame.routers.make_pyi_device_router import make_pyi_device_router

make_pyi_device_router(
    filename="simple_router.pyi",
    api_spec=simple_api_spec,
    class_name="SimpleRouter",
)
```

## `.pyi` for DeviceProxy

`DeviceProxy()` selects a client class from the registry at runtime, so its device-specific return type cannot be determined statically by the frame alone.

Generate overloads in the device package's `__init__.pyi` to provide the IDE with the device-specific client type.

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

At runtime, re-export `ese774_frame.DeviceProxy` directly rather than creating a device-specific wrapper. Device-specific typing is supplied only by the `.pyi` file.

## Tutorial

For a step-by-step example covering the server, clients, `DeviceProxy`, and `.pyi` generation, see [TUTORIAL.md](TUTORIAL.md).

## Author

- Kengo NAKADA
