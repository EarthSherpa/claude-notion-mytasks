---
description: Notion タスク一覧の表示・追加・完了・ステータス変更・削除
argument-hint: [list|all|add <名前>|done <名前/番号>|status <名前/番号> <値>|delete <名前/番号>]
allowed-tools: [Bash, mcp__1a4cd6f2-d31d-4d15-9817-259147b769eb__notion-get-users, mcp__1a4cd6f2-d31d-4d15-9817-259147b769eb__notion-fetch, mcp__1a4cd6f2-d31d-4d15-9817-259147b769eb__notion-create-pages, mcp__1a4cd6f2-d31d-4d15-9817-259147b769eb__notion-update-page]
---

# /mytasks - Notion タスク管理

ユーザーの指示: $ARGUMENTS

---

## ⚙️ 設定（初回のみ編集してください）

```
DATABASE_URL: https://www.notion.so/earth-sherpa/173deb5fc5da80b1b650e8af4cecbeb3?v=191deb5fc5da80c98e0c000c439373c6&source=copy_link
DB_ID:        173deb5fc5da80b1b650e8af4cecbeb3
PROP_TITLE:     Task Name
PROP_ASSIGNEE:  Assignee
PROP_STATUS:    Status
PROP_DEADLINE:  締切
PROP_PRIORITY:  Priority
PROP_PROJECT:   Project

STATUS_ACTIVE_VALUES:   Not started, In progress
STATUS_DONE_VALUES:     Done
STATUS_ARCHIVED_VALUES: Archived
STATUS_OTHER_VALUES:    Paused, Blocked
```

> **前提条件**: `~/.claude/scripts/notion_tasks.py` が存在すること（GitHub リポジトリに同梱）。
> Notion Integration Token を `~/.notion_token` に保存しておくこと（詳細は README 参照）。
> **Notion MCP UUID**: `allowed-tools` の UUID（`1a4cd6f2-d31d-4d15-9817-259147b769eb`）が自分の環境と異なる場合はこのファイルの UUID を全て置換してください。

---

## 実行手順

### Step 1: 設定チェック

設定の `DATABASE_URL` が `SETUP_REQUIRED` のままであれば、ユーザーに設定方法を案内して終了する。

設定済みの場合は Step 2 へ進む。

### Step 2: ユーザーID取得

`notion-get-users` を `user_id: "self"` で呼び出し、現在のユーザーのIDを取得する（以降 `MY_USER_ID` と呼ぶ）。

### Step 3: 意図解析

`$ARGUMENTS` を以下の優先順位でモードを決定する。

**判定順序（上から順に評価）:**

1. **VIEW-ALL**: `all`, `すべて`, `全部` を含む
2. **ADD**: `add`, `追加`, `新規`, `create`, `new`, `作成`, `作って`, `入れて` を含む
3. **DELETE**: `delete`, `削除`, `消して`, `remove`, `消す` を含む
4. **DEADLINE**: `期限変更`, `due`, `deadline`, `〆切`, `締め切り` を含む（ただし `add` と共存する場合は ADD モードで処理）
5. **STATUS**: 以下のいずれかに該当する
   - `status`, `ステータス`, `move`, `移動` キーワードを含む
   - `→` を含む（例: `1 → 保留`）
   - 設定の全 STATUS_*_VALUES に含まれる値 + タスク名/番号の組み合わせ（例: `archived 1`, `保留 レポート`）
6. **DONE**: `done`, `完了`, `終わった`, `finish`, `finished`, `済み`, `ok`, `やった` を含み、かつタスク名または番号が続く
7. **VIEW-FILTER**: 設定の STATUS_*_VALUES に含まれる値**のみ**（タスク名/番号なし）（例: `完了`, `archived`, `保留`）
8. **VIEW**: `$ARGUMENTS` が空、または `list`, `一覧`, `show`, `表示`, `ls` を含む

---

## 各モードの処理

### VIEW / VIEW-ALL / VIEW-FILTER モード

**データ取得（Python スクリプト経由）:**

モードに応じて以下の Bash コマンドを実行する:

```bash
# VIEW（アクティブのみ）
python3 ~/.claude/scripts/notion_tasks.py \
  --db-id {DB_ID} --user-id {MY_USER_ID} \
  --status "Not started" "In progress" --format json

# VIEW-ALL（全ステータス）
python3 ~/.claude/scripts/notion_tasks.py \
  --db-id {DB_ID} --user-id {MY_USER_ID} --format json

# VIEW-FILTER（指定ステータス）
python3 ~/.claude/scripts/notion_tasks.py \
  --db-id {DB_ID} --user-id {MY_USER_ID} \
  --status {指定ステータス値...} --format json
```

スクリプトは JSON 配列を出力する。各要素の構造:
```json
{"id": "page-uuid", "title": "タスク名", "status": "In progress",
 "deadline": "2026-03-10", "priority": "High", "project": "営業"}
```

このリストを `#1`, `#2`, ... として番号付けし、後続の操作で参照できるよう保持する。

**エラー時**: `~/.notion_token` が存在しない場合、スクリプトがセットアップ手順を stderr に出力する。
その内容をユーザーに表示し終了する。

**表示フォーマット（VIEW / VIEW-FILTER）:**
```
| # | タスク | プロジェクト | 期限 | 優先度 |
|---|--------|------------|------|-------|
| 1 | レポート作成 | 営業部 | 2026/03/10 | High |
| 2 | 会議準備 | 総務 | 2026/03/15 | Medium |
| 3 | 請求書確認 | 経理 | - | - |
（番号はこのセッション中のみ有効です）
```

**VIEW-ALL の表示フォーマット（ステータス列を追加）:**
```
| # | タスク | プロジェクト | 期限 | 優先度 | ステータス |
|---|--------|------------|------|-------|-----------|
| 1 | レポート作成 | 営業部 | 2026/03/10 | High | In progress |
| 2 | 議事録 | 総務 | - | - | Done |
（番号はこのセッション中のみ有効です）
```

タスクが0件の場合: `該当するタスクはありませんでした。`

---

### タスク特定（共通ヘルパー）

DONE / STATUS / DEADLINE / DELETE モードで使用する。

```
- 数字のみ / `#N` → セッション内の番号対応（VIEW で表示済みリストの page_id を使用）
- 名前指定 → Python スクリプトを json モードで実行し、title の部分一致（大文字小文字無視）でタスクを探す
  ※ 全ステータスから検索: --status オプションなし
- 複数一致 → 候補リストを表示して選択を求める
- セッションにリストがなく番号指定の場合 → VIEW モードを実行してリストを取得してから番号を確定する
```

---

### DONE モード（差分表示）

> **トークン節約**: 操作後はテーブルを再描画せず、1行確認のみ表示する。

```
1. タスク特定（上記共通ヘルパー参照）
2. notion-update-page(
     page_id: {対象ページID},
     command: "update_properties",
     properties: { "Status": "Done" }
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
- `status 1 Archived` / `status レポート Paused`
- `1 → Archived` / `レポート → In progress`
- `move 2 to Paused`
- `Archived 1` / `1 Archived` / `Paused レポート`

**引数解析:**
- `→` の左がタスク指定、右が新ステータス
- `status` / `move` / `ステータス` の後: タスク指定 + 新ステータス値の順
- ステータス値 + タスク指定の順でも可（例: `Archived 1`）

**ステータス値の解決:**
- 入力値が STATUS_ACTIVE_VALUES / STATUS_DONE_VALUES / STATUS_ARCHIVED_VALUES / STATUS_OTHER_VALUES のいずれかに含まれる → その値を使用
- 含まれない → そのまま値として設定し、`⚠ "hoge" は設定未定義ですが更新しました` と警告を添える

```
notion-update-page(
  page_id: {対象ページID},
  command: "update_properties",
  properties: { "Status": "{解決した新ステータス値}" }
)
```

**出力（1行のみ）:**
```
🔄 "レポート作成" のステータスを "Archived" に変更しました
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

まず `notion-fetch(id=DATABASE_URL)` を実行して `<data-source url="collection://...">` から `data_source_id` を取得する。

```
notion-create-pages(
  parent: { data_source_id: "{data_source_id}" },
  pages: [{
    properties: {
      "Task Name": "{タスク名}",
      "Assignee": "{MY_USER_ID}",
      "date:締切:start": "{期限 or null}",
      "date:締切:is_datetime": 0,
      "Priority": "{優先度 or null}",
      "Project": "{プロジェクト名 or null}"
    }
  }]
)
```

**出力（1行のみ）:**
```
✅ "議事録作成" を追加しました（期限: 2026/03/10、優先度: High）
（一覧を更新するには /mytasks と入力してください）
```

---

### DELETE モード（確認あり → 差分表示）

**処理:**
```
1. タスク特定（共通ヘルパー参照）
2. 削除前に確認:
   "「レポート作成」を削除しますか？（この操作は元に戻せません）[yes/no]"
3. yes / y / はい → 処理続行
   no / n / いいえ → "キャンセルしました" で終了
4. notion-update-page でステータスを Archived に変更する
   ※ Notion MCP にはページ削除 API がないため、ステータス変更で代替。
```

**出力（1行のみ）:**
```
🗑 "レポート作成" を Archived にしました（Notion 上で直接削除する場合はブラウザから行ってください）
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
    "date:締切:start": "{新しい日付 YYYY-MM-DD}",
    "date:締切:is_datetime": 0
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
- **エラー時**: Python スクリプトがエラーを返した場合は stderr の内容をそのまま表示する。`~/.notion_token` 不足の場合はセットアップ手順を案内する。
- **People プロパティ**: 担当者フィールドはユーザーIDの文字列を直接受け付ける（notion-get-users で取得した id を使用）。

---

## 使用例

```
/mytasks                              → アクティブタスク一覧
/mytasks list                         → アクティブタスク一覧（明示的）
/mytasks all                          → 全ステータスのタスク一覧
/mytasks Done                         → 完了タスクの一覧
/mytasks Archived                     → アーカイブ済みタスクの一覧
/mytasks Paused                       → 保留タスクの一覧

/mytasks 1 done                       → #1 を完了
/mytasks done レポート作成             → 名前で完了
/mytasks #2 終わった                  → #2 を完了

/mytasks status 1 Archived            → #1 をアーカイブ
/mytasks 1 → Paused                   → #1 を保留に変更
/mytasks move 2 to In progress        → #2 を進行中に変更
/mytasks Archived 1                   → #1 をアーカイブ（STATUS モード）
/mytasks レポート → Done               → 名前でステータス変更

/mytasks add 議事録作成                → タスク追加
/mytasks add 資料準備 期限 3/10 高    → 期限・優先度付きで追加
/mytasks 追加 会議準備 来週月曜       → 相対日付で期限設定

/mytasks delete 3                     → #3 を削除（確認あり）
/mytasks 削除 古いタスク              → 名前で削除

/mytasks 期限変更 レポート 3/20       → 期限を変更
```
