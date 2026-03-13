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
        # Combine with status filter using AND
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


def extract_tasks(pages):
    tasks = []
    for p in pages:
        tasks.append({
            "id": p["id"],
            "title": get_prop(p, "Task Name", "title"),
            "status": get_prop(p, "Status", "status"),
            "deadline": get_prop(p, "締切", "date"),
            "priority": get_prop(p, "Priority", "select"),
            "project": get_prop(p, "Project", "select"),
        })
    return tasks


def main():
    parser = argparse.ArgumentParser(description="Fetch Notion tasks for a user")
    parser.add_argument("--db-id", default="173deb5fc5da80b1b650e8af4cecbeb3")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--status", nargs="*", help="Status values to include (default: all)")
    parser.add_argument("--format", choices=["json", "table"], default="json")
    args = parser.parse_args()

    token = get_token()
    pages = query_all(args.db_id, token, args.user_id, args.status)
    tasks = extract_tasks(pages)

    if args.format == "json":
        print(json.dumps(tasks, ensure_ascii=False, indent=2))
    else:
        if not tasks:
            print("該当するタスクはありませんでした。")
            return
        print("| # | タスク | プロジェクト | 期限 | 優先度 | ステータス |")
        print("|---|--------|------------|------|-------|-----------|")
        for i, t in enumerate(tasks, 1):
            deadline = t["deadline"] or "-"
            priority = t["priority"] or "-"
            project = t["project"] or "-"
            print(f"| {i} | {t['title']} | {project} | {deadline} | {priority} | {t['status']} |")
        print("（番号はこのセッション中のみ有効です）")


if __name__ == "__main__":
    main()
