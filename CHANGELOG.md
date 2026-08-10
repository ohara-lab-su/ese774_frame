# CHANGELOG


## 2026.08.10, v0.5.0-pre4, nakada

### 完全動的ディスパッチと機器固有 Router の協調動作に対応

`api_spec=None` を使用する完全動的ディスパッチモードにおいて、機器固有の Router を併用できるように修正した。

これにより、通常の API は Framework の動的ディスパッチに任せながら、サーバー／クライアント間で処理や意味が異なる一部の API のみ、機器固有 Router で処理を差し替えることが可能となった。

### 完全動的モードで `router_cls` を選択可能に変更

完全動的モードでは、以下の2つの構成を選択できる。

機器固有のサーバー側処理を必要としない場合：

```python
server = FastApiServer(
    device_cls=DeviceCtrl,
    api_spec=None,
    router_cls=None,
    ...
)
```

`router_cls=None` の場合は、Framework 標準の `DeviceRouter` を自動的に使用する。

一方、サーバー側で機器固有の処理が必要な場合は、

```python
server = FastApiServer(
    device_cls=DeviceCtrl,
    api_spec=None,
    router_cls=DeviceRouterCtrl,
    ...
)
```

のように機器固有 Router を指定できる。

従来は `api_spec=None` の場合、指定された `router_cls` を使用せず Framework 標準 `DeviceRouter` へ強制的に切り替えていた。

v0.5.0-pre4 ではこの動作を修正し、完全動的モードでも明示的に指定された `router_cls` を使用する。

### 機器固有 Router と動的ディスパッチのフォールバック

完全動的モードで機器固有 Router を使用した場合、機器固有 Router に明示的に実装された API を優先し、それ以外の API は Device Class へ自動的にディスパッチする。

概念的には以下の順序で API を解決する。

```text
API request
    ↓
private / dispatch_exclude 判定
    ↓
機器固有 Router に override が存在するか
    ├─ Yes → Router 側の処理を実行
    │
    └─ No  → Device Class へ動的ディスパッチ
```

例えば、

```python
class DeviceRouterCtrl(DeviceRouter):

    def special_api(self, ...):
        # サーバー側で特殊な処理が必要な API のみ実装
        ...
```

とした場合、

```python
client.special_api(...)
```

は `DeviceRouterCtrl.special_api()` が処理する。

一方、Router に定義していない、

```python
client.normal_api(...)
```

については Device Class の、

```python
device.normal_api(...)
```

へ自動的にディスパッチされる。

これにより、完全動的モードのために機器の全 API を Router に記述する必要はなく、特殊処理が必要な API のみを機器側で実装すればよい。

### サーバー／クライアントで処理が異なる API への対応

機器制御では、ローカル Device とリモート Client で同じ API 名であっても、実際に必要となる処理が異なる場合がある。

例えばファイル転送では、

```text
Device側
機器 → サーバーPCへファイル保存
```

という処理を、そのままリモート Client から実行すると、保存先がサーバー側になってしまう。

このような場合、

```text
Server Router
    ↓
機器からデータを取得
    ↓
HTTPでClientへ転送
    ↓
Client側の機器固有処理
    ↓
Client PCへ保存
```

のように、サーバー側 Router と機器固有 Client の双方で処理を補う必要がある。

v0.5.0-pre4 では、このような完全自動化できない API のみを機器固有 Router で override し、それ以外の API は完全動的ディスパッチに任せる構成を可能とした。

### 機器固有 Router の記述を最小化

完全動的モードにおける機器固有 Router は、Device Class の API 一覧を記述するためのものではない。

通常の API は Framework が自動的に公開・ディスパッチするため、機器固有 Router には、サーバー側で処理を変更する必要がある API のみを記述する。

```python
class DeviceRouterCtrl(DeviceRouter):

    def special_api(self, ...):
        ...
```

これにより、

```text
自動化可能な API
    → Framework の完全動的ディスパッチ

サーバー側で特殊処理が必要な API
    → 機器固有 Router

クライアント側で特殊処理が必要な API
    → 機器固有 Client
```

という責務分離を可能とした。

### Router override の判定を改善

完全動的ディスパッチ時に、Framework 内部の helper method や `DeviceRouter` 自身の内部 member を機器固有 API と誤認しないよう、Router override の判定処理を修正した。

機器固有 Router で明示的に定義・override された member を優先対象とし、それ以外については Device Class 側へフォールバックする。

### 静的 property と機器固有 Router の協調

v0.5.0-pre3 で追加した静的 property の透過アクセスについても、機器固有 Router と協調して動作するようにした。

機器固有 Router 側で property が明示的に override されている場合は Router 側を優先し、それ以外の property は Device Class 側の静的 property へフォールバックする。

```text
機器固有 Router property
    → Router側を優先

それ以外
    → Device Class の property
```

これにより method と property の双方について、完全動的ディスパッチと機器固有処理を同じ考え方で併用できる。

### ApiSpec / Pydantic I/F モードとの後方互換性

従来の、

```python
server = FastApiServer(
    device_cls=DeviceCtrl,
    api_spec=device_api_spec,
    router_cls=DeviceRouterCtrl,
    ...
)
```

による ApiSpec / Pydantic I/F モードの動作は維持する。

v0.5.0-pre4 では、サーバー構成を以下のように整理した。

```text
api_specあり + router_clsあり
    → 従来の ApiSpec / Pydantic I/F モード

api_spec=None + router_clsあり
    → 完全動的ディスパッチ
       + 機器固有 Router による部分的 override

api_spec=None + router_cls=None
    → 完全動的ディスパッチ
       + Framework 標準 DeviceRouter
```

これにより、従来の明示的 I/F 定義を使用する構成との後方互換性を維持しながら、完全動的ディスパッチへ段階的に移行できるようにした。

### Framework と機器固有処理の責務分離

v0.5.0-pre4 では、完全動的モードにおける責務を以下のように整理した。

```text
Framework
    ├─ HTTP routing
    ├─ 動的ディスパッチ
    ├─ method / property の透過処理
    ├─ private API の除外
    ├─ dispatch_exclude
    └─ Device への自動フォールバック

機器固有 Router
    └─ サーバー側で意味・処理を変更する必要がある API のみ

機器固有 Client
    └─ クライアント側で意味・処理を変更する必要がある API のみ
```

これにより、Framework で自動化可能な処理は可能な限り自動化し、自動化できない機器固有のリモート処理のみを Router / Client の継承によって記述できる構成とした。

## 2026.08.10, v0.5.0-pre3, nakada

### 静的 property の透過アクセスに対応

Device Class に定義された静的 `property` を、リモート Client からも Python の property として透過的に利用できる機能を追加した。

これまで Device 側の property はサーバー側では取得可能であったが、Client 側では通常のメソッドと同様に扱われていた。

v0.5.0-pre3 では、Device 側が、

~~~python
class DeviceCtrl:
    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        self._value = value
~~~

の場合、Client 側でも、

~~~python
value = client.value
client.value = 10
~~~

としてアクセスできる。

Device Class の Python I/F を、リモート Client 側でもより直接的に再現できるようにした。

### `property()` による定義にも対応

デコレータ形式だけでなく、Python の `property()` を直接使用して定義された property も同様に認識する。

~~~python
class DeviceCtrl:
    def get_value(self):
        return self._value

    def set_value(self, value):
        self._value = value

    value = property(get_value, set_value)
~~~

この場合も Client 側では、

~~~python
value = client.value
client.value = 10
~~~

として利用できる。

`@property` と `property()` はともに、クラスに静的に定義された Python の property descriptor として同じように扱う。

### read-only / read-write property の自動判定

property の getter / setter 定義から、読み取り専用か読み書き可能かを判定する。

例えば、

~~~python
@property
def current_position(self):
    return self._current_position
~~~

は read-only property として扱われる。

Client 側では、

~~~python
position = client.current_position
~~~

による取得は可能だが、

~~~python
client.current_position = value
~~~

による変更は許可されない。

setter が定義されている property については、Client 側からの代入も可能となる。

### 完全動的モードでの property 自動検出

`api_spec=None` の完全動的モードでは、Device Class に静的に定義された property を Framework が自動的に検出する。

~~~python
server = FastApiServer(
    device_cls=DeviceCtrl,
    api_spec=None,
    router_cls=None,
    ...
)
~~~

この場合、機器側で property の ApiSpec や追加の I/F 定義を行う必要はない。

Framework が Device Class を introspection し、公開可能な静的 property と getter / setter の有無を Client に提供する。

これにより完全動的モードでは、

~~~text
Device method
    → 自動的に remote method として公開

Device property
    → 自動的に remote property として公開
~~~

される。

### ApiSpec / Pydantic I/F モードでの property 対応

従来の ApiSpec / Pydantic I/F モードでも property を利用できるようにした。

`ApiSpec` に API の種類を指定する `kind` を追加し、

~~~python
ApiSpec(
    name="value",
    object_name="device",
    kind="property",
    writable=True,
    ...
)
~~~

のように property を明示できる。

`kind="property"` とした API は、Client 側でもメソッドではなく property として生成される。

~~~python
value = client.value
client.value = 10
~~~

これにより、完全動的モードと ApiSpec / Pydantic I/F モードの双方で、同じ property I/F を利用できる。

### ApiSpec の後方互換性

既存の ApiSpec との後方互換性を維持する。

`kind` を指定していない既存の ApiSpec は従来どおり method として扱われる。

~~~text
kind 未指定
    → method

kind="method"
    → method

kind="property"
    → property
~~~

したがって、既存の ApiSpec 定義を変更しなくても従来のサーバー・クライアント動作を維持する。

property を利用したい API のみ、新しい property 定義へ移行できる。

### property 用通信処理の追加

method dispatch と property access を明確に分離するため、Framework に property 用の共通通信処理を追加した。

完全動的モードでは、Device Class の静的 property 情報を取得する metadata endpoint を利用し、Client 側で property の種類を認識する。

property の値取得および設定についても、method dispatch とは独立した property access として処理する。

これにより、

~~~python
client.value
client.value = 10
~~~

という Python 本来の属性アクセスを維持したまま、リモート Device の property を操作できる。

### Sync / Async Client の双方に対応

`SyncDeviceClient` および `AsyncDeviceClient` の双方で静的 property の透過アクセスに対応した。

通常の remote method は従来どおり、

~~~python
result = client.method()
~~~

または、

~~~python
result = await client.method()
~~~

として利用する。

一方 property は Sync / Async Client ともに、

~~~python
value = client.value
client.value = 10
~~~

という属性アクセス形式を使用する。

### `.pyi` 生成の property 対応

`make_pyi_device_client.py` を property に対応させた。

`kind="property"` として定義された API については、`.pyi` に property として型情報を生成する。

read-only property の例：

~~~python
@property
def value(self) -> int: ...
~~~

read-write property の例：

~~~python
@property
def value(self) -> int: ...

@value.setter
def value(self, value: int) -> None: ...
~~~

これにより、Client の実際の属性アクセスと IDE / type checker が認識する I/F を一致させる。

### 静的 property と動的属性の分離

今回の自動 property 対応は、クラス定義時点で存在する静的 property を対象とする。

以下は自動認識の対象となる。

~~~python
@property
def value(self):
    ...
~~~

および、

~~~python
value = property(get_value, set_value)
~~~

一方、

~~~python
def __getattr__(self, name):
    ...
~~~

や、

~~~python
def __setattr__(self, name, value):
    ...
~~~

によって実行時に生成される動的属性は、今回の静的 property 自動検出には含めない。

これにより、静的に定義可能な I/F と、機器固有の規則によって動的生成される I/F の責務を明確に分離した。

### 後方互換性

v0.5.0-pre3 の property 対応は既存動作との後方互換性を維持する。

- 既存 ApiSpec は `kind` 未指定のまま従来の method として動作する。
- 既存の method dispatch の動作は変更しない。
- property を使用しない既存 Device / Client には影響しない。
- 完全動的モードでは静的 property を自動認識する。
- ApiSpec / Pydantic I/F モードでは必要な property のみ明示的に指定できる。

これにより、従来の ApiSpec / Pydantic I/F ベースの構成を維持しながら、完全動的モードと明示的 I/F モードの双方で Python の property を利用できるようにした。

## 2026.08.10, v0.5.0-pre2, nakada

### 完全動的ディスパッチ機能の拡張

`ApiSpec` や機器固有の Router を用いず、Device Class の公開メソッドを直接利用する完全動的ディスパッチ機能を拡張した。

完全動的モードでは、サーバー起動時に以下のように指定できる。

~~~python
server = FastApiServer(
    device_cls=DeviceCtrl,
    router_cls=None,
    api_spec=None,
    config=Config,
    device_kwargs={...},
)
~~~

`api_spec=None` の場合、Framework 内部の汎用 `DeviceRouter` を使用して Device Class に対する動的ディスパッチを行う。

このため、完全動的モードでは機器ごとの以下の定義を必要としない。

- `ApiSpec`
- API 用 Pydantic model
- 機器固有 Router

### 動的モードでの API 公開範囲

完全動的モードでは、Device Class の public なメソッドおよび property を原則として公開する。

- `_` で始まる private member は自動的に公開対象外とする。
- `dispatch_exclude` に指定した public API は追加で公開対象外にできる。
- 公開 API を列挙するのではなく、Device Class の public API を基本として、非公開にする API のみを指定する。

例：

~~~python
server = FastApiServer(
    device_cls=DeviceCtrl,
    router_cls=None,
    api_spec=None,
    dispatch_exclude={
        "disconnect",
        "delete",
    },
    config=Config,
    device_kwargs={...},
)
~~~

### Framework 標準 Router の自動利用

`api_spec=None` かつ `router_cls=None` の場合、Framework が標準 `DeviceRouter` を自動的に使用するようにした。

これにより完全動的モードでは、機器側に動的ディスパッチのためだけの Router Class を定義する必要がない。

動的ディスパッチに必要な Router 処理は Framework 側の責務とし、機器側のサーバー記述を最小限にした。

### 既存クライアントとの互換性

完全動的モードでも、既存の機器別クライアントをそのまま利用できるようにした。

従来の `ApiSpec` を使用するクライアントが呼び出す、

~~~text
/instance/<object_name>/<api_name>
~~~

形式の API についても、`api_spec=None` のサーバー側で Framework が動的に処理する。

そのため、サーバーを完全動的モードへ変更するためだけに、機器ごとの「spec なしクライアント」を新たに作成する必要はない。

また、`api_spec=None` のクライアントからは `__dispatch__` を使用した完全動的呼び出しも利用できる。

### 従来の ApiSpec / Router モードとの後方互換性

従来の、

~~~python
server = FastApiServer(
    device_cls=DeviceCtrl,
    router_cls=DeviceRouterCtrl,
    api_spec=device_api_spec,
    ...
)
~~~

による明示的な `ApiSpec` / Router 構成はそのまま維持する。

したがって v0.5.0-pre2 では、

- 従来の `ApiSpec` / 機器固有 Router を使用するモード
- `ApiSpec` / 機器固有 Router を必要としない完全動的ディスパッチモード

の両方を利用できる。

既存の `ApiSpec` / Router ベースのサーバーおよびクライアントとの後方互換性を維持する。

### property の動的取得処理を修正

Device Class の `@property` を動的ディスパッチで取得する際の処理を修正した。

従来の存在確認処理では property の getter が複数回評価される可能性があったため、getter を一度だけ評価するよう変更した。

これにより、機器との通信や副作用を伴う property についても不要な重複アクセスを防止する。

### Framework と機器側の責務を分離

完全動的モードでは、以下を Framework 側の責務とする。

- HTTP API の受付
- 動的ディスパッチ
- Framework 標準 Router
- API 公開範囲の制御
- private member の除外
- `dispatch_exclude` による追加除外
- 従来形式の API URL との互換処理

機器側では基本的に Device Class の実装のみを必要とし、完全動的モードのためだけの `ApiSpec`、Pydantic model、機器固有 Router は不要とする。

機器固有 Client Class については従来どおり Device Client を継承する構成を維持する。

これにより、必要に応じたローカル／リモート処理の差し替えや、`make_pyi` による型情報生成など、従来の Client Class の仕組みをそのまま利用できる。

## 2026.07.14, v0.5.0 pre, nakada

### Unreleased - future branch

#### Added

- `ApiSpec` / Pydantic の定義を必要としない自動ディスパッチモードを追加。
- 自動ディスパッチモードでは、デバイス制御クラスの public method を原則としてそのまま REST 経由で公開可能とした。
- 自動ディスパッチモードの API 公開規則を追加。
  - public method は原則公開。
  - `_` で始まるメソッドは自動的に非公開。
  - `dispatch_exclude` に指定した public method は非公開。
- `ApiSpec` を持たない `SyncDeviceClient` / `AsyncDeviceClient` で動的な remote method dispatch に対応。
- 自動ディスパッチモードでも `_xxx_raw()` による remote API 呼び出しをサポート。
- `DeviceProxy` から `ApiSpec` およびデバイス専用 client class を持たない汎用 client を生成可能とした。
- `FastApiServer` に自動ディスパッチ用の `object_name` と `dispatch_exclude` を追加。
- `bytes` / `bytearray` の REST 経由転送に対応。
- tuple を含む Python オブジェクトの dispatch 経路での型復元に対応。

#### Changed

- `DeviceRouter` の `__dispatch__` を、`ApiSpec` に依存しない基本 transport として利用可能にした。
- 自動ディスパッチモードでは、device 側に存在する public API を公開対象の基準とした。
- device と同名のメソッドが Router 側に存在する場合、従来と同様に Router 側 override を優先する。
- client class に同名メソッドが定義されている場合、そのローカル実装を自動 remote dispatch より優先する。
- `adapter` の結果変換を修正し、`bytes` / `bytearray` / tuple を含む値を REST 経由で正しく転送・復元できるようにした。

#### Compatibility

- 従来の `ApiSpec` / Pydantic ベースの API 定義方式は維持する。
- 既存の `ApiSpec` モードにおける Router、client method 生成、`_xxx_raw()`、OpenAPI/Pydantic validation の動作を維持する。
- 自動ディスパッチモードは既存方式を置き換えず、別の軽量な利用方式として追加する。
- 既存のデバイス専用 Sync/Async client class によるローカル override 機構を維持する。

---

# 変更の目的

`ese774_frame` は、デバイス制御クラスをネットワーク越しでもローカル Python オブジェクトに近い形で扱う透過型プロキシを基本としている。

基本的には、デバイス制御クラス側の Python API を、そのままクライアント側の API として利用できることを目的とする。

従来の REST API 実装では、OpenAPI と入力・出力 validation を実現するために `ApiSpec` と Pydantic model を使用している。

この方式は明示的な REST API 契約として有用である一方、デバイスを追加するたびに API 定義を別途記述する必要があり、自動ディスパッチを基本とする透過型フレームとしては導入時の記述量が大きい。

今回の変更では、従来の `ApiSpec` / Pydantic 方式を完全に維持したまま、デバイス制御クラスの API を直接利用する自動ディスパッチモードを追加する。

基本構造は以下とする。

    DeviceCtrl
        ↓
    automatic dispatch
        ↓
    Sync / Async Client
        ↓
    DeviceProxy

---

# 自動ディスパッチモードの API 公開規則

自動ディスパッチモードでは、デバイス制御クラスそのものを API の基準とする。

公開規則は以下とする。

    public method        → 原則公開
    _method              → 非公開
    dispatch_exclude     → 明示的に非公開

従来のように「公開する API をすべて列挙する」のではなく、「公開したくない API だけを指定する」方式とする。

これにより、デバイス制御クラスへ新しい public method を追加した場合、フレーム側へ同じ API を再定義する必要がない。

例えば、

    def meas(self):
        ...

    def get_state(self):
        ...

    def _reset_internal(self):
        ...

の場合、

    meas()             公開
    get_state()        公開
    _reset_internal()  非公開

となる。

さらに public method であっても remote API として公開したくないものについては、

    dispatch_exclude=[
        "close",
        "disconnect",
    ]

のように明示的に除外する。

---

# 従来の ApiSpec モード

今回の変更では `ApiSpec` を廃止しない。

`ApiSpec` / Pydantic を利用する従来方式には、

- OpenAPI schema の明示的な定義
- Pydantic による入力 validation
- response model の定義
- GET / POST 等の REST API 契約
- REST API 名の明示
- 明示的な API 公開範囲の指定

という役割がある。

従来モードはそのまま維持する。

    FastApiServer(
        device_cls=DeviceCtrl,
        router_cls=DeviceRouter,
        config=Config,
        api_spec=device_api_spec,
    )

自動ディスパッチモードでは `ApiSpec` を必要としない。

    FastApiServer(
        device_cls=DeviceCtrl,
        router_cls=DeviceRouter,
        config=Config,
        object_name="device",
        dispatch_exclude=[
            "close",
            "disconnect",
        ],
    )

`ApiSpec` モードと自動ディスパッチモードは用途に応じて使い分ける。

---

# Client-side override

透過型プロキシであっても、すべての処理を単純に server 側へ送ればよいわけではない。

ネットワーク境界を越えることで実行場所や動作の意味が変化する API が存在する。

代表的なものとして、

- 画像のローカル保存
- ファイルのローカル保存
- ログ保存
- CSV 等の出力
- ローカル表示
- client-side polling
- 長時間 blocking 処理の client-side 化

などがある。

例えば、

    device.save_image("image.png")

を単純に server 側で実行すると、`image.png` は server 側へ保存される。

クライアント側への保存を目的とする場合、この動作ではローカル実行時と意味が変化する。

このため、従来から存在するデバイス専用 client class によるローカル override 機構を維持する。

    class CameraClient(SyncDeviceClient):

        def save_image(self, filename):
            data = self._get_image_raw()

            with open(filename, "wb") as f:
                f.write(data)

この場合、

    client.save_image("image.png")

は client-local で実行される。

一方、

    client._get_image_raw()

は remote API を呼び出す。

client override はファイル保存だけを目的としたものではなく、ネットワーク境界によって実行場所、blocking 特性、polling 方法などが変化する処理を client 側で補正するための一般的な機構として維持する。

---

# `_xxx_raw()` の意味

自動ディスパッチモードでも、従来からの `_xxx_raw()` の動作を維持する。

    client.foo(...)

は通常の client API である。

専用 client class に同名の `foo()` が存在する場合は、そのローカル実装を優先する。

存在しない場合は remote `foo()` を自動 dispatch する。

一方、

    client._foo_raw(...)

は client-side の同名 override を迂回して remote API `foo()` を呼び出す。

つまり、

    foo()
        client API
        local override があれば local
        なければ remote

    _foo_raw()
        client-side override を bypass
        remote foo を呼び出す

という関係を維持する。

`_raw` は Router layer を bypass して device method を直接呼ぶ機能ではない。

remote 側で Router override が存在する場合は、従来と同様に Router override を経由する。

---

# Router-side override

現行 `ese774_frame` では Router 側にも API override 機構が存在する。

従来の処理では、

    Router に同名 API が存在
            ↓
    Router method

    存在しない
            ↓
    DeviceCtrl method

という優先順位を持つ。

この機能を自動ディスパッチモードでも維持する。

公開対象そのものは device 側の API を基準とし、その API と同名の Router method が存在する場合には Router 側実装を優先する。

全体の method resolution は以下となる。

    Client API
        │
        ├─ client-side override
        │
        └─ remote dispatch
                 │
                 ▼
              Router
                 │
                 ├─ Router override
                 │
                 └─ DeviceCtrl

---

# Sync / Async

自動ディスパッチは `SyncDeviceClient` と `AsyncDeviceClient` の双方で同じ考え方を適用する。

Sync client:

    value = client.meas()

Async client:

    value = await client.meas()

専用 Sync/Async client class が存在する場合は、そのローカル override を優先する。

また、双方で `_xxx_raw()` による remote API 呼び出しを利用できる。

---

# DeviceProxy

従来 `DeviceProxy` では、専用 client class または `ApiSpec` を利用して client を生成していた。

今回の変更では、

    専用 client class なし
    ApiSpec なし

の場合でも、汎用 `SyncDeviceClient` / `AsyncDeviceClient` を利用して自動ディスパッチ client を生成可能とした。

    DeviceProxy
        ↓
    SyncDeviceClient / AsyncDeviceClient
        ↓
    automatic dispatch

client-local 処理が必要なデバイスについては、従来通り専用 client class を登録できる。

専用 client class ではすべての remote API を再定義する必要はなく、ローカル動作へ置き換える必要があるメソッドだけを定義する。

その他のメソッドは自動ディスパッチに任せる。

---

# bytes / bytearray の転送

画像やファイルのデータを server から client へ返すためには、`bytes` を REST 経由で正しく転送できる必要がある。

従来の `adapter.pack_result()` では、`bytes` を含む戻り値が最終的な `JSONResponse` の生成時に問題になる場合があった。

今回、`bytes` / `bytearray` を JSON-safe な表現へ変換し、client 側で元のデータへ復元する処理を追加した。

    bytes / bytearray
            ↓
    JSON-safe representation
            ↓
    REST
            ↓
    client
            ↓
    bytes

これにより、server で取得した画像・ファイルデータを client へ転送し、client-local で保存する処理が可能になる。

---

# tuple の保持

JSON では tuple と list の区別がないため、単純な JSON serialization では、

    (1, 2, 3)

が、

    [1, 2, 3]

へ変化する。

今回の `adapter` では tuple を識別可能な形式へ変換し、client 側で tuple として復元する。

dispatch 経路において Python API の引数・戻り値の意味を可能な限り維持する。

---

# 変更箇所

## `device_router.py`

- `api_spec=None` による自動ディスパッチモードを追加。
- `object_name` を `ApiSpec` なしでも指定可能にした。
- `dispatch_exclude` を追加。
- 自動モードの公開規則を追加。
  - public method は原則公開。
  - `_` 始まりは非公開。
  - `dispatch_exclude` 指定 API は非公開。
- device 側 API の存在を公開対象判定の基準とした。
- Router-side override を維持。
- 従来 `ApiSpec` モードの動作を維持。

## `api_server.py`

- `api_spec` を optional 化。
- `object_name` を追加。
- `dispatch_exclude` を追加。
- `ApiSpec` が存在する場合は従来方式で Router を初期化。
- `ApiSpec` が存在しない場合は自動ディスパッチ用 Router を初期化。

## `sync_device_client.py`

- `ApiSpec` がない場合の自動ディスパッチに対応。
- 動的な remote method resolution を追加。
- `foo()` から remote `foo()` を呼び出せるようにした。
- `_foo_raw()` から remote `foo()` を呼び出せるようにした。
- 専用 client class に定義された同名メソッドを優先。
- 従来 `ApiSpec` ベースの method 登録を維持。

## `async_device_client.py`

- `SyncDeviceClient` と同じ考え方で async の自動ディスパッチに対応。
- dynamic remote method resolution を追加。
- `_xxx_raw()` を維持。
- client-local override を維持。
- 従来 `ApiSpec` モードを維持。

## `device_proxy.py`

- `ApiSpec` / 専用 client class がない登録を許可。
- 専用 client class がなければ汎用 `SyncDeviceClient` / `AsyncDeviceClient` を利用。
- `ApiSpec` がある場合は従来通り利用。
- `object_name` を利用して自動ディスパッチ client を生成可能とした。

## `adapter.py`

- `bytes` / `bytearray` の JSON-safe な変換を追加。
- client 側で `bytes` を復元。
- tuple の型情報を保持して復元。
- args / kwargs / result で共通の pack/unpack 処理を利用。

---

# 維持する基本機能

今回の拡張では以下の既存機能を維持する。

- デバイス制御クラスと通信フレームの分離
- `DeviceProxy`
- Sync / Async client
- Router override
- client-local override
- `_xxx_raw()`
- `adapter`
- `ApiSpec`
- Pydantic
- OpenAPI
- FastAPI
- 従来 REST API
- device lifecycle

`ApiSpec` は廃止しない。

自動ディスパッチと明示的な API 契約は用途が異なるため、両方を維持する。

---

# 設計上の位置づけ

今回の変更では、Python device API の透過 transport をより直接的に利用できる経路を追加する。

基本経路は、

    DeviceCtrl
        ↓
    automatic dispatch
        ↓
    Sync / Async Client
        ↓
    DeviceProxy

とする。

必要な場合には従来通り、

    ApiSpec
    Pydantic
    OpenAPI

を利用する。

また、ネットワーク境界によって意味が変化する処理については、device-specific client による client-local override を利用する。

全体として、

    Device API
        +
    automatic transport
        +
    client-side override
        +
    router-side override
        +
    optional ApiSpec / OpenAPI

という構成とする。

基本原則は、

> public API は原則としてそのまま利用し、非公開にする API や特殊な処理だけを追加定義する。

とする。

## 2026.07.14, v0.4.28, nakada

- after cobotta3/4 setup
 
## 2026.07.14, v0.4.27

- 八代研引き渡し版

## 2026.07.13, v0.4.26, nakada

### Changed

- `SyncDeviceClient` を `AsyncDeviceClient` から分離し、純粋な同期クライアントとして実装し直した。
  - sync クライアントが `asyncio` や `httpx.AsyncClient` に依存しない構成へ変更。
  - API 自動生成、`dispatch()` を同期実装へ変更。
  - sync / async の実行モデルを分離し、イベントループ管理に起因する問題を解消。

- `server.py` / `__init__.py` による公開 API の簡易 import を復活。
  - 従来どおり短い import で各種クライアントおよび DeviceProxy を利用できる構成へ戻した。

## 2026.07.10, v0.4.25, nakada

## Changed

- サーバー起動時に KanjiVG ディレクトリを事前検証するように変更。
- KanjiVG ディレクトリが存在しない場合は、サーバー起動時に設定エラーとして終了するように変更。
- 起動時のエラーメッセージを整理し、設定ミスの原因が分かりやすくなるよう改善。

## 2026.06.27, v0.4.24, nakada

### Added

- `make_pyi_device_proxy()` を追加
  - デバイスモジュール用の `__init__.pyi` を自動生成できるようにした
  - `DeviceProxy()` の `@overload` を自動生成できるようにした
  - `device_class` ごとの `Literal` 型を自動生成できるようにした
  - Sync/Async クライアント型を補完できる `.pyi` を生成できるようにした

### Changed

- `DeviceProxy` の補完生成をフレーム側へ集約
  - デバイス固有の `.pyi` 生成コードを共通化した
  - 各デバイスは `make_pyi_device_proxy()` を呼び出すだけで `DeviceProxy` 用 `.pyi` を生成できる構成へ整理した
  - デバイス固有の `DeviceProxy` 実装は `create_device_proxy()` を利用し、`__init__.py` 側では最小限の記述で済む構成へ整理した

### Docs

- `DeviceProxy` の推奨実装方法を整理
- typed `DeviceProxy` の生成手順を整理
 
## 2026.06.26, v0.4.23, nakada

### Added

- `DeviceProxy` の補助関数を追加
  - `create_device_proxy()` を追加
  - 登録済み `device_class` を固定した `DeviceProxy` 関数を作成できるようにした
  - デバイス側モジュールで typed `DeviceProxy` を定義しやすい構成にした

### Changed

- デバイス側での `DeviceProxy` 定義を支援する構成へ整理
  - フレーム側の `DeviceProxy(device_class, ...)` は従来通り維持
  - デバイス側では `create_device_proxy("DeviceClassName")` を利用して device class 名をモジュール内に閉じ込められるようにした
  - `.pyi` / `@overload` による補完用 wrapper をデバイス側で最小限に書ける構成へ整理

### Docs

- typed `DeviceProxy` をデバイス側に定義するための利用方針を追記
 
## 2026.06.26 v0.4.22 nakada

### SyncDeviceClient の API 自動生成処理を修正

`SyncDeviceClient` が API spec に基づいて sync メソッドを自動生成する際、
継承先クラスで既に定義されているメソッドまで上書きしていた問題を修正した。

継承先クラスに同名メソッドが定義されている場合は、
API 自動生成メソッドで上書きしないようにした。

これにより、デバイス固有クライアント側で独自実装した同期メソッドを、
通常の同期メソッドとして利用できるようになった。


## 2026.06.25 v0.4.21 nakada

### SyncDeviceClient の event loop 管理を修正

sync クライアントが `asyncio.run()` を毎回使用していたため、
初回呼び出し後に `httpx.AsyncClient` が保持する event loop が破棄され、
2 回目以降の API 呼び出しで

- RuntimeError: Event loop is closed
- RuntimeError: cannot reuse already awaited coroutine

が発生する問題を修正した。

SyncDeviceClient が専用 event loop を保持し、
同一 `httpx.AsyncClient` を同一 event loop 上で継続利用する方式へ変更した。

この修正により、

- API_SPEC による動的生成メソッド
- dispatch()
- DeviceProxy(async_mode=False)

を含む sync クライアント全体で、複数回の API 呼び出しを正常に実行できるようになった。

本修正は従来 API との互換性を維持した内部実装の改善であり、
API 仕様の変更はない。

## 2026.05.13 v0.4.20 nakada (DeviceProxy)

### DeviceProxy 形で使えるように、クライアント登録

cobotta module 中で最初から用意しておく

### 使用例

```python
client = DeviceProxy("CobottaCtrl", config=config)
```

### cobottaモジュール中で register されているところは

例cobotta module
```aiignore
server_fastapi/__init__.py
```
```python
# spec
from cobotta2.server_fastapi.spec_ctrl import cobotta_ctrl_api_spec
from cobotta2.server_fastapi.spec_state import cobotta_state_api_spec

# client
from cobotta2.server_fastapi.clients.async_cobotta_client import AsyncCobottaClient
from cobotta2.server_fastapi.clients.async_cobotta_state_client import (
    AsyncCobottaStateClient,
)
from cobotta2.server_fastapi.clients.sync_cobotta_client import SyncCobottaClient

# motion
from cobotta2.server_fastapi.models.motion import MotionMode

# router
from cobotta2.server_fastapi.routers.cobotta_router_ctrl import CobottaRouterCtrl
from cobotta2.server_fastapi.routers.cobotta_router_state import CobottaRouterState

# device_proxy
from ese774_frame.clients import register_device_proxy

register_device_proxy(
    "CobottaCtrl",
    async_client_cls=AsyncCobottaClient,
    sync_client_cls=SyncCobottaClient,
    api_spec=cobotta_ctrl_api_spec,
    default_async_mode=True,
    aliases=["cobotta"],
)
```


## 2026.04.08 v0.4.19 nakada

- FastAPI側の デフォルトのtimeout を 5sec から 60sec へ変更

## 2026.03.26 v0.4.18 nakada

- 比較的長い処理をしていると、webサーバ側のtimeoutになるもんだいの解決
  - set_timeout() の実装

## 2026.03.26 v0.4.16 nakada

- python 3.7 

## 2026.03.15 v0.4.15 nakada
 
- 出張前 FINALバージョン(2026.03.15)
- ドキュメント調整
 
## 2026.03.09 v0.4.14 nakada

ドキュメント調整

## 2026.02.27 v0.4.13 nakada

名前空間とリポジトリ名を変更・調整

- 旧: fastapi_frame
- 新: ese774_frame

調整パッケージ

- ese774_frame: 0.4.13
- cobotta2: 0.10.3
- cobotta2_client: 0.1.0
- aandd_reader: 0.2.8
 
## 2026.02.18 v0.4.12 nakada

fix

## 2026.02.18 v0.4.11 nakada

docstring 修正

## 2026.02.18 v0.4.10 nakada

- 最低限の動作テスト(cobotta-3/server-2/hand/drive/move/get_current)

**bugfix/大改修**

- 方針の整理
  - adapter 用意するなど、基本は 0.4.x 方針ベースである
  - 0.3.x で実装されている機能のうち未実装のものを取り込み
  - pydantic は I/F 定義とそれに基づくpythonへの復元
  - binary 転送方針を廃止して、json に直す(0.3.x方式)
      - pydantic -> binary 転送(廃止)
      - pydantic -> json 転送
    - この方式で adapter.py に集約整理したルーチン系はそのまま活用する
      (最小の修正)
    - pack/unpack を修正する
    - つまりは、adapter を使うだけの 0.3.x 構造に近くなる

```
Python ctrl (純粋)
  ↓
Server: FastAPI + Pydantic (入力検証とJSON化のみ)
  ↓ (JSON)
Client: Pydanticで復元
  ↓
Python (素の値だけ返す)
```

## 2026.02.04 v0.4.9 nakada

差分marge

## 2026.02.04 v0.4.8 nakada

dispatch 復元が一方通行だったので
- list -> tuple

これを
- list <-> list
- tuple <-> tuple

に修正

## 2026.02.04 v0.4.7 nakada

jopad/server動作テスト対応完了
 
- grpc_frame: 0.3.4
- ese774_frame: 0.4.7
- cobotta2: 0.9.23
 
## 2026.02.04 v0.4.6 nakada

- make_xxx (pyi作成)
  - overload をもっと積極的に使う形に修正

## 2026.02.04 v0.4.5 nakada

bugfix

## 2026.02.04 v0.4.4 nakada

bugfix

## 2026.02.04 v0.4.3 nakada

bugfix

## 2026.02.04 v0.4.2 nakada

- log_level 記述が抜けていたのを修正(Noneでも動くように)

## 2026.02.04 v0.4.1 nakada

- device_router
  - logger 周りを修正(XLoggerがなくても動作するように)

## 2026.02.03, v0.4.0 nakada

1. pyton-local -> Server: 新旧同じ
2. Server内部
   - 旧: ctrl の戻り値を pydantic response_model に変換
   - 新: ctrl の戻り値を pack_result でバイナリ化。json or pickle 化
3. Server -> client
   - 旧: Pydantic の JSON
   - 新: adapter の payload (バイナリ) 
4. client -> python
   - 旧: pydantic の形から復元
   - 新: adapter を unpak で復元 *args, **kwargs で戻す(引数の具体的形は pyi 任せとする)

## 2026.02.03, v0.3.8 nakada

- フレームワーク大改修前の最後のバージョン

## 2025.09.07, v0.3.7 nakada

- 累計 fix
- added sphinx (pyproject.toml)
 
## 2025.10.14, v0.3.6 nakada

- added sphinx requirement
 
## 2025.09.07, v0.3.5 nakada

- sphinx test

## 2025.07.29, v0.3.4 nakada

- 名前空間の追加
 
## 2025.07.29, v0.3.3 nakada

- device.disconnect が存在しないときに自動で呼ばないようにする

## 2025.07.29, v0.3.2 nakada

- v0.3.1 後の fix を充てる

## 2025.07.23, v0.3.1 nakada

- こまかい fix
- 累計バージョンチェックのためのナンバリング(中身はほぼ変化なし)
 
## 2025.07.22, v0.3.0 nakada

- pyi 自動作成をいろいろと修正
- async/sync のクライアントを統一（async を sync では継承する)

## 2025.07.20, v0.2.3 nakada

original API の名前空間を少し変更(_api_name_raw)

## 2025.07.19, v0.2.2 nakada

巡回参照対策!!
地味だが、非常に本質的な改造

## 2025.07.19, v0.2.1 nakada

累計bugfix

## 2025.07.18, v0.2.0 nakada

- 動的ディスパッチ周りの基本機構を修正
 
## 2025.07.12, v0.1.5 nakada

logger まわりのバグ発見するために、ロガー周りを修正。
その余波で問題の区別がつきにくくなるところをシンプル化

## 2025.07.12, v0.1.3 nakada

累計の細かい fix 請けいたらバージョンに命名

## 2025.07.11 08:17, v0.1.1 nakada

call_type 廃止。これで本当に動的にディスパッチしていることになるはず。

## 2025.07.11 07:22, v0.1.0 nakada

複数引数を扱うメソッドの自動ディスパッチが、めんどくさい問題から、実はpydantic を活用できなかった問題になって、大改修？になった。model だけでの修正（基本項目だけで）対応できるようになった。これで、model でのおる独自キーは method_type だけになった。最低限cobotta側で試験

v0.1.0

## 2025.07.10 15:47, v0.0.3 nakada

- 開発中の tango frame を分離
 
## 2025.07.10 15:36, v0.0.2 nakada

- FastAPI Server での Uvicorn のロガーについての不具合解消のためのパッチ

## 2025.07.10 13:45, v0.0.1 nakada

- cobotta に依存している、起動テスト系の if __main__ を一通り削除

## 2025.07.10 13:26, v0.0.0 nakada

- cobotta 制御から分離