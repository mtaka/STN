# STN Core

STN AST の構造評価エンジンです。

STN Core は [STN Lexer](../lexer) が生成する AST を受け取り、型定義・変数束縛・Entity 生成・getter/setter 適用を経て、評価済みの **Document** を構築します。

## インストール

```bash
# uv workspace 内から
uv sync
```

## クイックスタート

```python
from stn_core import Document

doc = Document.loads("""
@%Person (:name :age % :sex %s(F M))
@@taro %Person(:name [山田太郎] :age 36 :sex M)
@@hanako %Person(:name [田中花子] :age 28 :sex F)
""")

doc.locals_["taro"].fields["name"]   # VText("山田太郎")
doc.get_first("@taro").get("name")   # [VText("山田太郎")]
```

---

## Document API

### Loader

```python
doc = Document.loads(src: str)   # STN テキストから評価
doc = Document.load(path)        # ファイルから読み込み・評価
```

### Document へのアクセス

```python
doc.typedefs["Person"]     # TypeDef
doc.locals_["taro"]        # VEntity  (@@name で定義された変数)
doc.symbols["R001"]        # Value    (@#name で定義された変数、キーに # は不要)
doc.results                # list[Value]  — すべての式の評価結果
doc.getval("title")        # 先頭の named entry を返す（str キー）
doc.getval(1)              # 1-origin インデックスで entry を返す
```

---

## Locator API

`locate()` は `(value, path_str)` のジェネレータを返します。  
`get()` は値のリスト、`get_first()` は最初の値または `Empty` を返します。

### パス構文

| パス | 説明 |
|---|---|
| `"name"` | フィールド名で検索 |
| `1` / `"1"` | 1-origin の位置インデックス |
| `"a.b.c"` | 階層アクセス（チェーン） |
| `"*"` | 直接の子要素をすべて yield |
| `"(a b c)"` | 複数フィールドを一括取得 |
| `"?(:key val)"` | クエリフィルタ |
| `"#sym"` | symbol-id で検索（`!( #name)` で設定） |

Document レベルのプレフィックス：

| パス | 説明 |
|---|---|
| `"#name"` | `@#name` で定義されたシンボル変数 |
| `"@name"` | `@@name` で定義されたローカル変数 |
| `"%Name"` | typedef |
| `"entry.field"` | top-level entry への階層アクセス |
| `"entry.*"` | top-level entry の子要素をすべて |
| `"entry?(:key val)"` | top-level entry へのクエリ |

### 使用例

```python
src = """
@%Person (:name :age %)
:members (
  :alice %Person(:name [Alice] :age 30)
  :bob   %Person(:name [Bob]   :age 25)
  :carol %Person(:name [Carol] :age 30)
)
"""
doc = Document.loads(src)

# フィールドアクセス
alice = doc.get_first("members.alice")
alice.get_first("name")                    # VText("Alice")

# ワイルドカード — 全メンバーを取得
doc.get("members.*")                       # [VEntity(alice), VEntity(bob), VEntity(carol)]

# ワイルドカード + チェーン — 全メンバーの name を一括取得
doc.get("members.*.name")                  # [VText("Alice"), VText("Bob"), VText("Carol")]

# クエリフィルタ
doc.get("members?(:age 30)")               # [VEntity(alice), VEntity(carol)]
doc.get("members.*.name")                  # VList のフィールドにも使用可

# locate() でパス文字列も取得
for val, path in doc.locate("members.*"):
    print(path, val)
# members.alice  VEntity(Person)
# members.bob    VEntity(Person)
# members.carol  VEntity(Person)
```

---

## DOM ナビゲーション

評価後、すべての `VEntity` / `VList` に DOM 的な参照が設定されます。

```python
entity.parent      # 親の VEntity / VList / Document
entity.document    # 所属する Document
entity.children    # 直接の子値リスト（fields + props）

lst.parent
lst.document
lst.children
```

`VEntity` と `VList` はともに `locate()` / `get()` / `get_first()` を持ちます。

---

## Projection API

### Value → Python オブジェクト / JSON / YAML

```python
entity.to_obj()    # dict（型付きなら "@type" キーを含む）
                   # 位置引数のみの場合は list

entity.to_json()   # JSON 文字列
entity.to_json(indent=2)

entity.to_yaml()   # YAML 文字列（allow_unicode=True）

lst.to_obj()       # list
lst.to_json()
lst.to_yaml()
```

**`to_obj()` の型マッピング：**

| STN 値 | Python |
|---|---|
| `VText` | `str` |
| `VNumber` | `int` または `float` |
| `VBool` | `bool` |
| `VDate` | `str`（ISO-8601） |
| `VEnum` | `str` |
| `VList` | `list` |
| `VEntity`（位置引数のみ） | `list` |
| `VEntity`（キー付き） | `dict`（型付きなら `"@type"` を含む） |
| `Empty` | `None` |

### Document → Python オブジェクト / YAML

```python
doc.to_obj()    # named entries → dict
                # 無名エントリのみ・1件 → 値をそのまま返す
                # 無名エントリのみ・複数 → list

doc.to_yaml()   # YAML 文字列
```

### dict → Document

```python
# 通常モード：keys → named entries
doc = Document.from_dict({"title": "Hello", "count": 3})

# 宣言モード：@@/@@/@ プレフィックスを宣言として解釈
doc = Document.from_dict({
    "@@name": "Alice",
    "@%Person": {"name": "text", "age": "number"},
    "title": "Hello",
}, include_defs=True)
```

---

## データモデル

| 型 | 説明 |
|---|---|
| `VText` | テキスト文字列 |
| `VNumber` | 数値（`float` で保持、整数なら `int` で表示） |
| `VDate` | 日付文字列（ISO-8601） |
| `VBool` | 真偽値 |
| `VEnum` | 選択肢付き列挙値 |
| `VList` | 値のリスト |
| `VEntity` | フィールドとプロパティを持つ Entity |
| `Empty` | 未定義参照のシングルトン（falsy） |

---

## アーキテクチャ

```
STN テキスト
  → stn.parse(text)           → ParseResult(ast, data)
  → stn_core.evaluate(result) → Document
```

**2パス評価：**

1. **Pass 1** — `@%` 定義を収集して TypeDef を登録
2. **Pass 2** — 全文を評価し、変数束縛・Entity 生成・getter/setter 適用

**主要モジュール：**

| モジュール | 役割 |
|---|---|
| `evaluator.py` | 2パス評価エンジン |
| `document.py` | Document クラス（Loader / Locator / Projection の入口） |
| `locator.py` | パスによるナビゲーション・クエリ・DOM 参照設定 |
| `projector.py` | Value ↔ Python オブジェクト の相互変換 |
| `values.py` | VText / VNumber / VEntity / VList / Empty |
| `reader.py` | トークン列 → SObject（中間表現）への変換 |
| `getter.py` / `setter.py` | フィールド/プロパティのアクセス・変更チェーン |
| `repl.py` | 対話型 REPL（`uv run stn-repl`） |

## テスト

```bash
cd STN
uv run pytest core/tests/ -v
```

詳細な仕様は [spec.md](spec.md) を参照してください。
