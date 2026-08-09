"""Tests for feedback collection."""

from scripts.reviewer.feedback import collect_feedback


def test_collect_feedback_aggregates_reactions(monkeypatch):
    captured = []

    def fake_get(url, **kw):
        captured.append(url)
        if url.endswith('comments?per_page=100'):
            return type(
                'R',
                (),
                {
                    'raise_for_status': lambda self: None,
                    'json': lambda self: [
                        {
                            'id': 1,
                            'user': {'login': 'github-actions[bot]'},
                            'body': '## 🤖 Reviewer Agent Report',
                            'created_at': '2026-01-01',
                            'html_url': 'https://example.com/c1',
                        },
                        {
                            'id': 2,
                            'user': {'login': 'human'},
                            'body': 'hello',
                            'created_at': '2026-01-01',
                            'html_url': 'https://example.com/c2',
                        },
                    ],
                },
            )()
        return type(
            'R',
            (),
            {
                'raise_for_status': lambda self: None,
                'json': lambda self: [
                    {'content': '+1'},
                    {'content': '+1'},
                    {'content': '-1'},
                ],
            },
        )()

    monkeypatch.setattr('requests.get', fake_get)
    rows = collect_feedback('token', 'owner/repo', 42)
    assert len(rows) == 1
    assert rows[0]['thumbs_up'] == 2
    assert rows[0]['thumbs_down'] == 1
