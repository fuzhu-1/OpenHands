"""Collect 👍/👎 reactions on reviewer comments and print a summary."""

from __future__ import annotations

import argparse
import json
import os
from typing import Any

import requests


def collect_feedback(
    token: str, repo: str, pr_number: int, marker: str = 'Reviewer Agent Report'
) -> list[dict[str, Any]]:
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github.v3+json',
    }
    url = (
        f'https://api.github.com/repos/{repo}/issues/{pr_number}/comments?per_page=100'
    )
    comments = requests.get(url, headers=headers)
    comments.raise_for_status()

    rows = []
    for c in comments.json():
        if c['user']['login'] not in ('github-actions[bot]', 'openhands-bot'):
            continue
        if marker not in c['body']:
            continue
        reactions = requests.get(
            f'https://api.github.com/repos/{repo}/issues/comments/{c["id"]}/reactions',
            headers=headers,
        )
        reactions.raise_for_status()
        contents = [r['content'] for r in reactions.json()]
        rows.append(
            {
                'comment_id': c['id'],
                'created_at': c['created_at'],
                'url': c['html_url'],
                'thumbs_up': contents.count('+1'),
                'thumbs_down': contents.count('-1'),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description='Collect reviewer feedback')
    parser.add_argument('--repo', required=True)
    parser.add_argument('--pr', type=int, required=True)
    args = parser.parse_args()
    token = os.environ.get('GITHUB_TOKEN', '')
    rows = collect_feedback(token, args.repo, args.pr)
    print(json.dumps({'pr': args.pr, 'comments': rows}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
