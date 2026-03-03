---
description: Notion タスク一覧の表示・追加・完了・ステータス変更・削除
argument-hint: [list|all|add <名前>|done <名前/番号>|status <名前/番号> <値>|delete <名前/番号>]
allowed-tools: [mcp__1a4cd6f2-d31d-4d15-9817-259147b769eb__notion-get-users, mcp__1a4cd6f2-d31d-4d15-9817-259147b769eb__notion-search, mcp__1a4cd6f2-d31d-4d15-9817-259147b769eb__notion-fetch, mcp__1a4cd6f2-d31d-4d15-9817-259147b769eb__notion-create-pages, mcp__1a4cd6f2-d31d-4d15-9817-259147b769eb__notion-update-page]
---

# /mytasks - Notion タスク管理

ユーザーの指示: $ARGUMENTS

---

## ⚙️ 設定（初回のみ編集してください）

```
DATABASE_URL: https://www.notion.so/earth-sherpa/173deb5fc5da80b1b650e8af4cecbeb3?v=191deb5fc5da80c98e0c000c439373c6&source=copy_link
PROP_TITLE:     タスク名
PROP_ASSIGNEE:  担当者
PROP_STATUS:    ステータス
PROP_DEADLINE:  期限
PROP_PRIORITY:  優先度
PROP_PROJECT:   プロジェクト

STATUS_ACTIVE_VALUES:   未着手, 進行中, In Progress, Todo
STATUS_DONE_VALUES:     完了, Done, Completed
STATUS_ARCHIVED_VALUES: アーカイブ, Archived
STATUS_OTHER_VALUES:    保留, On Hold, Blocked
```

> **DATABASE_URL の設定方法**: Notion でタスクデータベースを開き、URL（例: `https://www.notion.so/...`）をコピーして `SETUP_REQUIRED` と置き換えてください。
> **プロパティ名**: 自分の Notion DB のプロパティ名と合わない場合は上記の各 PROP_* を修正してください。
> **Notion MCP UUID**: `allowed-tools` の UUID（`1a4cd6f2-d31d-4d15-9817-259147b769eb`）が自分の環境と異なる場合はこのファイルの UUID を全て置換してください。

---

## 実行手順

### Step 1: 設定チェック

設定の `DATABASE_URL` が `SETUP_REQUIRED` のままであれば初期セットアップを実行する:

1. `notion-search` で `query: "タスク"` を実行し、データベース候補を最大5件表示する
2. 「どのデータベースを使いますか？番号で選択してください」と提示する
3. ユーザーが選択したら「このファイルの `DATABASE_URL:` を選択したURLに書き換えてください」と案内して終了する

設定済みの場合は Step 2 へ進む。

### Step 2: ユーザーID取得

`notion-get-users` を `user_id: "self"` で呼び出し、現在のユーザーのIDを取得する（以降 `MY_USER_ID` と呼ぶ）。

### Step 3: 意図解析

`$ARGUMENTS` を以下の優先順位でモードを決定する。

**判定順序（上から順に評価）:**

1. **SETUP**: `$ARGUMENTS` が空 かつ `DATABASE_URL` が `SETUP_REQUIRED` → Step 1 へ
2. **VIEW-ALL**: `all`, `すべて`, `全部` を含む
3. **ADD**: `add`, `追加`, `新規`, `create`, `new`, `作成`, `作って`, `入れて` を含む
4. **DELETE**: `delete`, `削除`, `消して`, `remove`, `消す` を含む
5. **DEADLINE**: `期限変更`, `due`, `deadline`, `〆切`, `締め切り` を含む（ただし `add` と共存する場合は ADD モードで処理）
6. **STATUS**: 以下のいずれかに該当する
   - `status`, `ステータス`, `move`, `移動` キーワードを含む
   - `→` を含む（例: `1 → 保留`）
   - 設定の全 STATUS_*_VALUES に含まれる値 + タスク名/番号の組み合わせ（例: `archived 1`, `保留 レポート`）
7. **DONE**: `done`, `完了`, `終わった`, `finish`, `finished`, `済み`, `ok`, `やった` を含み、かつタスク名または番号が続く
8. **VIEW-FILTER**: 設定の STATUS_*_VALUES に含まれる値**のみ**（タスク名/番号なし）（例: `完了`, `archived`, `保留`）
9. **VIEW**: `$ARGUMENTS` が空、または `list`, `一覧`, `show`, `表示`, `ls` を含む

---

## 各モードの処理

### VIEW / VIEW-ALL / VIEW-FILTER モード

**データ取得:**
```
1. notion-fetch(id=DATABASE_URL) を実行して <data-source url="collection://..."> タグから data_source_id を取得
2. notion-search(query="", data_source_url="collection://{data_source_id}") で全ページを取得
3. 以下の条件でフィルタリング:
   - PROP_ASSIGNEE プロパティが MY_USER_ID を含む
   - ステータス条件（モードによる）:
     - VIEW:        STATUS_ACTIVE_VALUES に含まれる
     - VIEW-ALL:    フィルタなし（全ステータス）
     - VIEW-FILTER: 指定されたステータス値を含むカテゴリで絞り込む
```

**表示フォーマット（VIEW / VIEW-FILTER）:**
```
| # | タスク | プロジェクト | 期限 | 優先度 |
|---|--------|------------|------|-------|
| 1 | レポート作成 | 営業部 | 2026/03/10 | 高 |
| 2 | 会議準備 | 総務 | 2026/03/15 | 中 |
| 3 | 請求書確認 | 経理 | - | - |
（番号はこのセッション中のみ有効です）
```

**VIEW-ALL の表示フォーマット（ステータス列を追加）:**
```
| # | タスク | プロジェクト | 期限 | 優先度 | ステータス |
|---|--------|------------|------|-------|-----------|
| 1 | レポート作成 | 営業部 | 2026/03/10 | 高 | 進行中 |
| 2 | 議事録 | 総務 | - | - | 完了 |
| 3 | 確認作業 | 経理 | - | 低 | アーカイブ |
（番号はこのセッション中のみ有効です）
```

タスクが0件の場合: `該当するタスクはありませんでした。`

---

### DONE モード（差分表示）

> **トークン節約**: 操作後はテーブルを再描画せず、1行確認のみ表示する。

**タスク特定:**
- 数字のみ / `#N` → セッション内の番号対応（VIEW で表示済みリストを参照）
- 名前 → PROP_ASSIGNEE=MY_USER_ID かつ STATUS_ACTIVE_VALUES のタスクから部分一致で検索
- 複数一致 → 候補リストを表示して選択を求める
- セッションにリストがなく番号指定の場合 → 先にタスク一覧を取得して番号を確定してから処理

**処理:**
```
notion-update-page(
  page_id: {対象ページID},
  command: "update_properties",
  properties: { "{PROP_STATUS}": "{STATUS_DONE_VALUES の最初の値}" }
)
```

**出力（1行のみ）:**
```
✅ "レポート作成" を完了にしました
（一覧を更新するには /mytasks と入力してください）
```

---

### STATUS モード（差分表示）

> DONE モードの一般化。任意のステータス値へ変更できる。

**自然言語パターン例:**
- `status 1 アーカイブ` / `status レポート 保留`
- `1 → アーカイブ` / `レポート → 進行中`
- `move 2 to 保留`
- `archived 1` / `1 archived` / `保留 レポート`
- `レポートをアーカイブして` / `2を進行中に変更`

**引数解析:**
- `→` の左がタスク指定、右が新ステータス
- `status` / `move` / `ステータス` の後: タスク指定 + 新ステータス値の順
- ステータス値 + タスク指定の順でも可（例: `archived 1`）

**ステータス値の解決:**
- 入力値が STATUS_ACTIVE_VALUES / STATUS_DONE_VALUES / STATUS_ARCHIVED_VALUES / STATUS_OTHER_VALUES のいずれかに含まれる → その値を使用
- 含まれない → そのまま値として設定し、`⚠ "hoge" は設定未定義ですが更新しました` と警告を添える

**処理:**
```
notion-update-page(
  page_id: {対象ページID},
  command: "update_properties",
  properties: { "{PROP_STATUS}": "{解決した新ステータス値}" }
)
```

**出力（1行のみ）:**
```
🔄 "レポート作成" のステータスを "アーカイブ" に変更しました
（一覧を更新するには /mytasks と入力してください）
```

---

### ADD モード（差分表示）

**引数解析（$ARGUMENTS から抽出）:**
- タスク名: `add`/`追加`等のキーワードの直後のフレーズ（期限・優先度・プロジェクトキーワードの前まで）
- 期限: `期限`, `due`, `〆` 等の後の日付表現
  - 相対日付（来週月曜, 明日, 今週金曜等）は本日の日付を基準に ISO 8601 形式（YYYY-MM-DD）に変換
- 優先度: `高`, `中`, `低`, `high`, `medium`, `low`, `urgent` 等
- プロジェクト: `プロジェクト`, `proj`, `project` の後のフレーズ

必須: タスク名。不明な場合は確認を求める。

**処理:**
```
notion-create-pages(
  parent: { data_source_id: "{data_source_id}" },
  pages: [{
    properties: {
      "{PROP_TITLE}": "{タスク名}",
      "{PROP_ASSIGNEE}": "{MY_USER_ID}",
      "date:{PROP_DEADLINE}:start": "{期限 or null}",
      "date:{PROP_DEADLINE}:is_datetime": 0,
      "{PROP_PRIORITY}": "{優先度 or null}",
      "{PROP_PROJECT}": "{プロジェクト名 or null}"
    }
  }]
)
```

**出力（1行のみ）:**
```
✅ "議事録作成" を追加しました（期限: 2026/03/10、優先度: 高）
（一覧を更新するには /mytasks と入力してください）
```

---

### DELETE モード（確認あり → 差分表示）

**処理:**
```
1. タスク特定（DONE モードと同様）
2. 削除前に確認:
   "「レポート作成」を削除しますか？（この操作は元に戻せません）[yes/no]"
3. yes / y / はい → 処理続行
   no / n / いいえ → "キャンセルしました" で終了
4. notion-update-page でステータスを削除済みを示す特殊値に変更する
   ※ Notion MCP にはページ削除 API がないため、ステータス変更で代替。
     STATUS_OTHER_VALUES に "削除済み" を追加して管理するか、
     Notion 上で直接削除するよう案内する。
```

**出力（1行のみ）:**
```
🗑 "レポート作成" を削除しました（Notion 上でアーカイブ済み）
（一覧を更新するには /mytasks と入力してください）
```

---

### DEADLINE モード（差分表示）

**引数解析:** タスク名/番号 + 新しい日付（相対・絶対両対応）

**処理:**
```
notion-update-page(
  page_id: {対象ページID},
  command: "update_properties",
  properties: {
    "date:{PROP_DEADLINE}:start": "{新しい日付 YYYY-MM-DD}",
    "date:{PROP_DEADLINE}:is_datetime": 0
  }
)
```

**出力（1行のみ）:**
```
📅 "レポート作成" の期限を 2026/03/20 に変更しました
（一覧を更新するには /mytasks と入力してください）
```

---

## 重要な制約

- **差分表示厳守**: VIEW / VIEW-ALL / VIEW-FILTER 以外のモードでは絶対にタスクテーブルを再表示しない。操作確認は1行のみ。
- **番号の一時性**: `#1`, `#2` 等の番号はこのセッション（会話）内のみ有効。次回 `/mytasks` 実行時に番号が変わりうることをユーザーに認識させる。
- **エラー時**: Notion API エラーが発生した場合はエラー内容を表示し「設定のプロパティ名・DATABASE_URL を確認してください」と案内する。
- **People プロパティ**: 担当者フィールドはユーザーIDの文字列を直接受け付ける（notion-get-users で取得した id を使用）。

---

## 使用例

```
/mytasks                              → アクティブタスク一覧
/mytasks list                         → アクティブタスク一覧（明示的）
/mytasks all                          → 全ステータスのタスク一覧
/mytasks 完了                         → 完了タスクの一覧
/mytasks archived                     → アーカイブ済みタスクの一覧
/mytasks 保留                         → 保留タスクの一覧

/mytasks 1 done                       → #1 を完了
/mytasks done レポート作成             → 名前で完了
/mytasks #2 終わった                  → #2 を完了

/mytasks status 1 アーカイブ          → #1 をアーカイブ
/mytasks 1 → 保留                     → #1 を保留に変更
/mytasks move 2 to 進行中             → #2 を進行中に変更
/mytasks archived 1                   → #1 をアーカイブ（STATUS モード）
/mytasks レポート → 完了               → 名前でステータス変更

/mytasks add 議事録作成                → タスク追加
/mytasks add 資料準備 期限 3/10 高    → 期限・優先度付きで追加
/mytasks 追加 会議準備 来週月曜       → 相対日付で期限設定

/mytasks delete 3                     → #3 を削除（確認あり）
/mytasks 削除 古いタスク              → 名前で削除

/mytasks 期限変更 レポート 3/20       → 期限を変更
```
