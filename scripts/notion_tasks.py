#!/usr/bin/env python3
"""
Fetch all Notion tasks assigned to a user via the Notion Database Query API.

Setup: Store your Notion integration token in ~/.notion_token
       (or set NOTION_TOKEN environment variable)
"""

import json
import sys
import urllib.request
import urllib.error
import os
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed


def get_token():
    token_file = Path.home() / ".notion_token"
    if token_file.exists():
        return token_file.read_text().strip()
    token = os.environ.get("NOTION_TOKEN")
    if token:
        return token
    print(
        "ERROR: Notion token not found.\n"
        "  1. Go to https://www.notion.so/my-integrations\n"
        "  2. Create an integration and copy the token\n"
        "  3. Run: echo 'secret_xxx...' > ~/.notion_token\n"
        "  4. In Notion, share your task DB with the integration",
        file=sys.stderr,
    )
    sys.exit(1)


def notion_request(path, token, body=None):
    url = f"https://api.notion.com/v1{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        msg = e.read().decode()
        print(f"ERROR: Notion API {e.code}: {msg}", file=sys.stderr)
        sys.exit(1)


def get_prop(page, prop_name, ptype):
    prop = page.get("properties", {}).get(prop_name, {})
    if ptype == "title":
        return "".join(i.get("plain_text", "") for i in prop.get("title", []))
    elif ptype == "status":
        s = prop.get("status") or {}
        return s.get("name", "")
    elif ptype == "select":
        s = prop.get("select") or {}
        return s.get("name", "")
    elif ptype == "date":
        d = prop.get("date") or {}
        return d.get("start", "")
    elif ptype == "people":
        return [p.get("id", "") for p in prop.get("people", [])]
    return ""


def query_all(db_id, token, user_id, status_filter=None):
    filter_body = {
        "property": "Assignee",
        "people": {"contains": user_id},
    }
    if status_filter and len(status_filter) == 1:
        filter_body = {
            "and": [
                {"property": "Assignee", "people": {"contains": user_id}},
                {"property": "Status", "status": {"equals": status_filter[0]}},
            ]
        }
    elif status_filter and len(status_filter) > 1:
        filter_body = {
            "and": [
                {"property": "Assignee", "people": {"contains": user_id}},
                {
                    "or": [
                        {"property": "Status", "status": {"equals": s}}
                        for s in status_filter
                    ]
                },
            ]
        }

    all_pages = []
    cursor = None
    while True:
        body = {"page_size": 100, "filter": filter_body}
        if cursor:
            body["start_cursor"] = cursor
        result = notion_request(f"/databases/{db_id}/query", token, body)
        all_pages.extend(result.get("results", []))
        if not result.get("has_more"):
            break
        cursor = result.get("next_cursor")

    return all_pages


def fetch_page_title(page_id, token):
    """GET /v1/pages/{id} してタイトルプロパティを返す"""
    result = notion_request(f"/pages/{page_id}", token)
    props = result.get("properties", {})
    for prop in props.values():
        if prop.get("type") == "title":
            return "".join(i.get("plain_text", "") for i in prop.get("title", []))
    return ""


def resolve_project_names(pages, token):
    """全タスクのプロジェクトIDを収集し、名前に解決して辞書を返す"""
    all_ids = set()
    for page in pages:
        for rel in page.get("properties", {}).get("Project", {}).get("relation", []):
            all_ids.add(rel["id"])
    id_to_name = {}
    for pid in all_ids:
        try:
            id_to_name[pid] = fetch_page_title(pid, token)
        except Exception:
            id_to_name[pid] = ""
    return id_to_name


# ── サマリー取得 ──────────────────────────────────────────────

# テキストを抽出できるブロックタイプ（優先: 段落・リスト・引用 / 低優先: 見出し）
_BODY_BLOCK_TYPES = {
    "paragraph", "bulleted_list_item", "numbered_list_item", "quote", "callout",
}
_HEADING_BLOCK_TYPES = {"heading_1", "heading_2", "heading_3"}


def _extract_block_text(block):
    """1ブロックからプレーンテキストを返す（空なら空文字）"""
    btype = block.get("type", "")
    if btype not in (_BODY_BLOCK_TYPES | _HEADING_BLOCK_TYPES):
        return ""
    rich = block.get(btype, {}).get("rich_text", [])
    return "".join(r.get("plain_text", "") for r in rich)


def fetch_page_summary(page_id, token, max_chars=150):
    """ページ本文の先頭テキストを最大 max_chars 文字で返す。内容がなければ空文字。

    段落・リスト・引用を優先し、それらがなければ見出しにフォールバック。
    「Description」のような1語の見出しは除外。
    """
    try:
        result = notion_request(f"/blocks/{page_id}/children?page_size=30", token)
    except Exception:
        return ""

    blocks = result.get("results", [])

    def collect(block_types, min_len=0):
        parts, total = [], 0
        for block in blocks:
            if block.get("type") not in block_types:
                continue
            text = _extract_block_text(block).strip()
            if not text or len(text) <= min_len:
                continue
            remaining = max_chars - total
            if remaining <= 0:
                break
            parts.append(text[:remaining])
            total += len(text)
            if total >= max_chars:
                break
        return " ".join(parts)

    # 段落・リスト・引用を優先
    summary = collect(_BODY_BLOCK_TYPES)
    # なければ20文字超の見出しにフォールバック（"Description" 等の1語ラベルを除外）
    if not summary:
        summary = collect(_HEADING_BLOCK_TYPES, min_len=20)

    if len(summary) >= max_chars:
        summary = summary[:max_chars].rstrip() + "…"
    return summary


def fetch_summaries_parallel(page_ids, token, max_workers=10):
    """複数ページのサマリーを並列取得して {page_id: summary} を返す"""
    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_id = {
            executor.submit(fetch_page_summary, pid, token): pid
            for pid in page_ids
        }
        for future in as_completed(future_to_id):
            pid = future_to_id[future]
            try:
                results[pid] = future.result()
            except Exception:
                results[pid] = ""
    return results


# ─────────────────────────────────────────────────────────────


def extract_tasks(pages, token):
    id_to_name = resolve_project_names(pages, token)
    tasks = []
    for p in pages:
        rel_ids = [r["id"] for r in p.get("properties", {}).get("Project", {}).get("relation", [])]
        project_name = ", ".join(id_to_name.get(rid, "") for rid in rel_ids)
        tasks.append({
            "id": p["id"],
            "title": get_prop(p, "Task Name", "title"),
            "status": get_prop(p, "Status", "status"),
            "deadline": get_prop(p, "締切", "date"),
            "priority": get_prop(p, "Priority", "select"),
            "project": project_name,
            "summary": "",  # --with-summary 時に後から埋める
        })
    return tasks


def main():
    parser = argparse.ArgumentParser(description="Fetch Notion tasks for a user")
    parser.add_argument("--db-id", default="173deb5fc5da80b1b650e8af4cecbeb3")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--status", nargs="*", help="Status values to include (default: all)")
    parser.add_argument("--format", choices=["json", "table"], default="json")
    parser.add_argument("--with-summary", action="store_true",
                        help="Fetch page body summaries (extra API calls, ~2-3s)")
    args = parser.parse_args()

    token = get_token()
    pages = query_all(args.db_id, token, args.user_id, args.status)
    tasks = extract_tasks(pages, token)

    # サマリーを並列取得して埋め込む
    if args.with_summary and tasks:
        summaries = fetch_summaries_parallel([t["id"] for t in tasks], token)
        for t in tasks:
            t["summary"] = summaries.get(t["id"], "")

    if args.format == "json":
        print(json.dumps(tasks, ensure_ascii=False, indent=2))
    else:
        if not tasks:
            print("該当するタスクはありませんでした。")
            return
        has_summary = args.with_summary
        print("| # | タスク | プロジェクト | 期限 | 優先度 | ステータス |")
        print("|---|--------|------------|------|-------|-----------|")
        for i, t in enumerate(tasks, 1):
            deadline = t["deadline"] or "-"
            priority = t["priority"] or "-"
            project  = t["project"]  or "-"
            print(f"| {i} | {t['title']} | {project} | {deadline} | {priority} | {t['status']} |")
            if has_summary and t.get("summary"):
                print(f"|   | 📝 {t['summary']} |  |  |  |  |")
        print("（番号はこのセッション中のみ有効です）")


if __name__ == "__main__":
    main()
