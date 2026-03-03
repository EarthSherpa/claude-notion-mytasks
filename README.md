# claude-notion-mytasks

Claude Code の `/mytasks` コマンドで Notion のタスクを管理します。

## 機能

| 操作 | 例 |
|------|-----|
| タスク一覧表示 | `/mytasks` |
| 全ステータス表示 | `/mytasks all` |
| ステータスでフィルタ | `/mytasks 完了` `/mytasks archived` |
| タスク完了 | `/mytasks 1 done` `/mytasks done レポート` |
| ステータス変更 | `/mytasks status 1 アーカイブ` `/mytasks 1 → 保留` |
| タスク追加 | `/mytasks add 議事録 期限 3/10 高` |
| タスク削除 | `/mytasks delete 1` |
| 期限変更 | `/mytasks 期限変更 レポート 3/20` |

**トークン節約設計**: 操作後はテーブルを再描画せず、1行の確認メッセージのみ表示します。一覧は `/mytasks` で明示的に呼んだときのみ表示します。

## 前提条件

- **Claude Code**（デスクトップ版）がインストールされていること
- **Notion MCP** が接続済みであること
  - Claude Code → 設定 → Connections → Notion が「Connected」になっていることを確認

## インストール

### 方法1: コマンドファイルのみコピー（シンプル・推奨）

```bash
# ~/.claude/commands/ がなければ作成
mkdir -p ~/.claude/commands

# コマンドファイルをダウンロード
curl -o ~/.claude/commands/mytasks.md \
  https://raw.githubusercontent.com/EarthSherpa/claude-notion-mytasks/main/commands/mytasks.md
```

Claude Code を再起動すると `/mytasks` コマンドが使えるようになります。

### 方法2: リポジトリをクローンしてプラグインとして使用

```bash
git clone https://github.com/EarthSherpa/claude-notion-mytasks.git ~/claude-plugins/notion-mytasks
```

Claude Code の設定 → Plugins → Add Plugin からクローンしたパスを指定。

## 初期設定

### 1. データベースURLの設定

インストール後に `/mytasks` を実行すると、Notion のデータベース候補が自動表示されます。
選択後、`~/.claude/commands/mytasks.md` をテキストエディタで開き、設定セクションを編集します：

```
DATABASE_URL: SETUP_REQUIRED  ← ここを自分のDBのURLに変更
```

Notion でタスクデータベースを開いて URL をコピーします。例：
```
https://www.notion.so/My-Tasks-1234567890abcdef1234567890abcdef
```

### 2. プロパティ名の設定

Notion DB のプロパティ名が異なる場合は `PROP_*` を修正します：

```
PROP_TITLE:     タスク名        ← タイトルプロパティ名
PROP_ASSIGNEE:  担当者          ← People 型プロパティ名
PROP_STATUS:    ステータス      ← Status 型プロパティ名
PROP_DEADLINE:  期限            ← Date 型プロパティ名
PROP_PRIORITY:  優先度          ← Select 型プロパティ名
PROP_PROJECT:   プロジェクト    ← Select/Text 型プロパティ名
```

### 3. ステータス値の設定

自分の Notion DB のステータス値に合わせて設定します：

```
STATUS_ACTIVE_VALUES:   未着手, 進行中      ← デフォルトで一覧表示されるステータス
STATUS_DONE_VALUES:     完了               ← "done" コマンドで設定されるステータス
STATUS_ARCHIVED_VALUES: アーカイブ          ← アーカイブとみなすステータス
STATUS_OTHER_VALUES:    保留               ← その他のステータス
```

### 4. Notion MCP UUID の確認（通常は不要）

`/mytasks` 実行時にツールが見つからないエラーが出る場合：

1. Claude Code で `/mcp` と入力して接続中の MCP を確認
2. Notion コネクタの UUID を確認
3. `~/.claude/commands/mytasks.md` 内の UUID（`1a4cd6f2-d31d-4d15-9817-259147b769eb`）を全置換

## 使い方

```
# 一覧表示
/mytasks                              → アクティブタスク一覧（未着手・進行中）
/mytasks all                          → 全ステータスのタスク一覧
/mytasks 完了                         → 完了タスクの一覧
/mytasks archived                     → アーカイブ済みタスクの一覧

# 完了
/mytasks 1 done                       → #1 を完了
/mytasks done レポート作成             → 名前で完了
/mytasks #2 終わった                  → #2 を完了

# ステータス変更
/mytasks status 1 アーカイブ          → #1 をアーカイブ
/mytasks 1 → 保留                     → #1 を保留に変更
/mytasks move 2 to 進行中             → #2 を進行中に変更
/mytasks archived 1                   → #1 をアーカイブ
/mytasks レポート → 完了               → 名前でステータス変更

# 追加
/mytasks add 議事録作成                → タスク追加
/mytasks add 資料準備 期限 3/10 高    → 期限・優先度付きで追加
/mytasks 追加 会議準備 来週月曜       → 相対日付で期限設定

# 削除
/mytasks delete 3                     → #3 を削除（確認あり）
/mytasks 削除 古いタスク              → 名前で削除

# 期限変更
/mytasks 期限変更 レポート 3/20       → 期限を変更
```

## 注意事項

- タスク番号（`#1`, `#2`...）はセッション（会話）内でのみ有効です。次回 `/mytasks` を実行すると番号が変わる場合があります。
- Notion MCP にはページ削除 API がないため、削除操作はステータス変更で代替します。Notion 上での完全な削除は手動で行ってください。

## トラブルシューティング

**「タスクが見つかりませんでした」と表示される**
- `PROP_ASSIGNEE` の値が Notion のプロパティ名と完全一致しているか確認（大文字小文字・スペースも含む）
- Notion DB で自分が担当者として設定されているか確認
- `STATUS_ACTIVE_VALUES` に実際のステータス値が含まれているか確認

**ツールエラーが出る**
- Claude Code を再起動
- 設定 → Connections → Notion を再接続

**プロパティが見つからないエラー**
- `mytasks.md` の `PROP_*` 設定と Notion DB のプロパティ名が一致しているか確認

## ライセンス

MIT
