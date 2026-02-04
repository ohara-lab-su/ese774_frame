# CHANGELOG

## 2026.02.034 v0.4.6 nakada

- make_xxx (pyi作成)
  - overload をもっと積極的に使う形に修正

## 2026.02.034 v0.4.5 nakada

bugfix

## 2026.02.034 v0.4.4 nakada

bugfix

## 2026.02.034 v0.4.3 nakada

bugfix

## 2026.02.034 v0.4.2 nakada

- log_level 記述が抜けていたのを修正(Noneでも動くように)

## 2026.02.034 v0.4.1 nakada

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