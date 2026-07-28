# CHANGELOG


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