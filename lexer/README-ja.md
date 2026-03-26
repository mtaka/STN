# STN Lexer

STN（Structured Text Notation）の字句解析器です。STNソーステキストをトークン化・パースし、
上位レイヤーが解釈できる `Node` オブジェクトのASTを生成します。

English README → [README.md](README.md)

## インストール

```
pip install -e .
```

## 使い方

```python
from stn import parse

result = parse(text)
result.ast    # ルートNode
result.data   # データブロック → dict[str, str]
```

## Lexerが返すもの

### ParseResult

| フィールド | 型 | 説明 |
|-----------|-----|------|
| `ast` | `Node` | パース結果を格納したルートノード |
| `data` | `dict[str, str]` | データブロックの名前付きセクション |

### Node

```python
class Node:
    items: list[Token | Node]  # 順序通りのトークン・子ノードのリスト
    word_head: bool            # この '(' が語頭（直前が空白・ストリーム先頭）かどうか
    word_tail: bool            # この ')' が語末（直後が空白・ストリーム末尾）かどうか

    @property
    def children(self) -> list[Node]: ...  # 子Nodeのみ
```

### Token

```python
class Token:
    type: TokenType   # SIGIL | ATOM | NUMBER
    value: str
    line: int
    col: int
    word_head: bool   # 直前が空白・'(' またはストリーム先頭
    word_tail: bool   # 直後が空白・')' またはストリーム末尾
```

`word_head` / `word_tail` フラグにより、上位レイヤー（STN_Core等）が**膠着**（空白なしで隣接するトークン）を判定できます：

```
%Person  →  SIGIL(%, head=T, tail=F)  ATOM(Person, head=F, tail=T)
@@joe    →  SIGIL(@, head=T, tail=F)  SIGIL(@, head=F, tail=F)  ATOM(joe, head=F, tail=T)
:name    →  SIGIL(:, head=T, tail=F)  ATOM(name, head=F, tail=T)
```

## 使用例

入力：

```
@@joe (:name [Joe Smith] :age 36)
@joe.name
```

`parse(text)` 後のAST：

```
root Node
└── items:
    ├── SIGIL(@, head=T, tail=F)
    ├── SIGIL(@, head=F, tail=F)
    ├── ATOM(joe, head=F, tail=T)
    └── Node(head=T, tail=T)
        └── items:
            ├── SIGIL(:, head=T, tail=F)
            ├── ATOM(name, head=F, tail=T)
            ├── ATOM([Joe Smith], head=T, tail=T)
            ├── SIGIL(:, head=T, tail=F)
            ├── ATOM(age, head=F, tail=T)
            └── NUMBER(36, head=T, tail=T)
    ├── SIGIL(@, head=T, tail=F)
    ├── ATOM(joe, head=F, tail=F)
    ├── SIGIL(., head=F, tail=F)
    └── ATOM(name, head=F, tail=T)
```

## 構文

### トークン

| トークン | 説明 |
|---------|------|
| `( ... )` | ノード — 入れ子構造 |
| `ATOM` | 識別子（英数字・`_` など） |
| `NUMBER` | 整数または小数（`42`、`3.14`、`-5`） |
| `SIGIL` | SIGIL文字セットの1文字（下記参照） |

### SIGIL文字（1文字1トークン）

```
; , : . = + - * / % ! ? @ # $ ^ & ~ ` | \ < > { } ' "
```

注：`_`（アンダーバー）はSIGILでは**ない** — アトムの一部として使えます（`__reserved__` は有効なATOM）。

### リテラル（ATOMとして出力）

| 構文 | 説明 |
|------|------|
| `[...]` | 通常リテラル — 内部の `]` は `\]` でエスケープ |
| `` `...` `` | バッククオートリテラル — `[中身]` として出力。`` \` `` でエスケープ |
| `\n[[[[\n...\n]]]]\n` | ブロックリテラル — 4重ブラケット・改行区切り。内部に `]` を何個含んでもOK |

### コメント

```
// 行コメント
```

### データブロック

```
====data====
---- @section1
セクション1の内容
---- @section2
セクション2の内容
```

- マーカー：`====data====`（大文字小文字不問、両側4個以上の `=`）
- セクション区切り：`-+\s*@name`
- `result.data["section1"]` でアクセス
- セクションなしの場合、全内容が `_ALL` キーに格納

## 設計方針

Lexerは意味解釈を**一切行いません**：

- `;` は単なるSIGILトークン — チャンク分割は呼び出し側の責務
- `:name` は `SIGIL(:)` + `ATOM(name)` — キー検出は呼び出し側の責務
- `%Type` は `SIGIL(%)` + `ATOM(Type)` — 型インスタンス化は呼び出し側の責務

変数・型・ゲッター・セッターなどの意味解釈は **STN_Core** などの上位レイヤーが担います。

## テスト

```
python -m pytest tests/ -v
```
