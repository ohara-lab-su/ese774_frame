# Ese774 Frame 似非774 (Fast API Frame)
view on [github](https://github.com/ohara-lab-su/ese774_frame/) / [ohara-lab-su (doc)](https://ohara-lab-su.github.io/)


---
```{toctree}
:maxdepth: 2
:caption: Contents:

api/modules
tutorials/ese774_intro
```
---

BL774風味の通信を行うためのフレーム。

- サーバー側の制御Class
- I/F定義に Pydantic
- RestAPIによる通信
- I/F により動的にクライアント制御clasとして


## 透過プロキシ型の通信フレーム

- (1) 機器制御クラス
- (2) FastAPI のサーバー側
- (3) FastAPI のクラアント側クラスライブラリ
- (4) 機器制御プログラム

(2)-(3) は透過的で、どんなクラス(1)でも動的に(2)-(3)まで自動的に対応できる。
実質(4)は、(1)と同じ形して使える

### 機器ごとに用意しなくていけないもの

- 機器制御クラスライブラリ
- Paydantic 関係の定義
  - api_spec
    - 透過的に扱う(  動ティディスパッチする) method/property の名前の定義
  - models  
    - method   で使  う、引数や戻り値のタイプを定義するクラス

基本的にこれら二つを用意する必要がある。
SP8的な用語では、一種の config.tbl といえばいい。
あとは ese774_frame が勝手にやる


---
## 作者
- Kengo NAKADA
