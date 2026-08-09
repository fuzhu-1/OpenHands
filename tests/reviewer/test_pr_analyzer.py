"""Tests for PR analyzer: template compliance and comment management."""

from scripts.reviewer.pr_analyzer import PRAnalyzer


def _analyzer() -> PRAnalyzer:
    return PRAnalyzer.__new__(PRAnalyzer)


def test_template_pass_with_checked_type(monkeypatch):
    a = _analyzer()
    body = (
        '## Why\nmotivation\n'
        '## Summary\n- change\n'
        '## How to Test\nsteps\n'
        '## Type\n- [x] Bug fix\n'
    )
    monkeypatch.setattr(a, 'get_pr_metadata', lambda: {'body': body})
    assert a.check_template_compliance()['passed'] is True


def test_template_type_present_without_selection(monkeypatch):
    a = _analyzer()
    body = (
        '## Why\nmotivation\n'
        '## Summary\n- change\n'
        '## How to Test\nsteps\n'
        '## Type\n- [ ] Bug fix\n- [ ] Feature\n'
    )
    monkeypatch.setattr(a, 'get_pr_metadata', lambda: {'body': body})
    result = a.check_template_compliance()
    assert result['passed'] is False
    assert 'Type (no checkbox selected)' in result['missing']
    assert 'Type' not in result['present']


def test_template_missing_fields(monkeypatch):
    a = _analyzer()
    monkeypatch.setattr(a, 'get_pr_metadata', lambda: {'body': 'no sections at all'})
    result = a.check_template_compliance()
    assert result['passed'] is False
    assert set(result['missing']) == {'Why', 'Summary', 'How to Test', 'Type'}


def test_get_existing_bot_comments_filters(monkeypatch):
    a = _analyzer()
    a.api_base = 'https://api.github.com'
    a.repo = 'owner/repo'
    a.pr_number = 42

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {
                    'id': 1,
                    'user': {'login': 'github-actions[bot]'},
                    'body': '## 🤖 Reviewer Agent Report',
                },
                {
                    'id': 2,
                    'user': {'login': 'someone-else'},
                    'body': '## 🤖 Reviewer Agent Report',
                },
                {
                    'id': 3,
                    'user': {'login': 'github-actions[bot]'},
                    'body': 'unrelated',
                },
            ]

    class FakeSession:
        def get(self, url, headers=None):
            return FakeResp()

    a.session = FakeSession()
    comments = a.get_existing_bot_comments()
    assert [c['id'] for c in comments] == [1]


def test_delete_comment_returns_true_on_204(monkeypatch):
    a = _analyzer()
    a.api_base = 'https://api.github.com'
    a.repo = 'owner/repo'

    class FakeResp:
        status_code = 204

    class FakeSession:
        def delete(self, url, headers=None):
            return FakeResp()

    a.session = FakeSession()
    assert a.delete_comment(1) is True


def test_parse_new_line_ranges():
    from scripts.reviewer.pr_analyzer import parse_new_line_ranges

    patch = '@@ -10,4 +20,6 @@\n context\n+added\n@@ -50 +60 @@\n-old\n+new\n'
    assert parse_new_line_ranges(patch) == [(20, 25), (60, 60)]


def test_post_review_with_comments_posts_payload(monkeypatch):
    a = _analyzer()
    a.api_base = 'https://api.github.com'
    a.repo = 'owner/repo'
    a.pr_number = 42
    captured = {}

    class Resp:
        status_code = 200
        text = ''

        def json(self):
            return {'html_url': 'https://example.com/review'}

    class FakeSession:
        def post(self, url, headers=None, json=None):
            captured['url'] = url
            captured['json'] = json
            return Resp()

    a.session = FakeSession()
    ok = a.post_review_with_comments(
        commit_sha='sha1',
        event='APPROVE',
        body='looks good',
        comments=[{'path': 'a.py', 'line': 21, 'side': 'RIGHT', 'body': 'nit'}],
    )
    assert ok is True
    assert captured['url'].endswith('/pulls/42/reviews')
    assert captured['json']['comments'][0]['path'] == 'a.py'
