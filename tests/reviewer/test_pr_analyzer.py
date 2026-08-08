"""Tests for PR analyzer: template compliance and comment management."""

from scripts.reviewer.pr_analyzer import PRAnalyzer


def _analyzer() -> PRAnalyzer:
    return PRAnalyzer.__new__(PRAnalyzer)


def test_template_pass_with_checked_type(monkeypatch):
    a = _analyzer()
    body = (
        "## Why\nmotivation\n"
        "## Summary\n- change\n"
        "## How to Test\nsteps\n"
        "## Type\n- [x] Bug fix\n"
    )
    monkeypatch.setattr(a, "get_pr_metadata", lambda: {"body": body})
    assert a.check_template_compliance()["passed"] is True


def test_template_type_present_without_selection(monkeypatch):
    a = _analyzer()
    body = (
        "## Why\nmotivation\n"
        "## Summary\n- change\n"
        "## How to Test\nsteps\n"
        "## Type\n- [ ] Bug fix\n- [ ] Feature\n"
    )
    monkeypatch.setattr(a, "get_pr_metadata", lambda: {"body": body})
    result = a.check_template_compliance()
    assert result["passed"] is False
    assert "Type (no checkbox selected)" in result["missing"]
    assert "Type" not in result["present"]


def test_template_missing_fields(monkeypatch):
    a = _analyzer()
    monkeypatch.setattr(a, "get_pr_metadata", lambda: {"body": "no sections at all"})
    result = a.check_template_compliance()
    assert result["passed"] is False
    assert set(result["missing"]) == {"Why", "Summary", "How to Test", "Type"}


def test_get_existing_bot_comments_filters(monkeypatch):
    a = _analyzer()
    a.api_base = "https://api.github.com"
    a.repo = "owner/repo"
    a.pr_number = 42

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return [
                {"id": 1, "user": {"login": "github-actions[bot]"},
                 "body": "## 🤖 Reviewer Agent Report"},
                {"id": 2, "user": {"login": "someone-else"},
                 "body": "## 🤖 Reviewer Agent Report"},
                {"id": 3, "user": {"login": "github-actions[bot]"},
                 "body": "unrelated"},
            ]

    class FakeSession:
        def get(self, url, headers=None):
            return FakeResp()

    a.session = FakeSession()
    comments = a.get_existing_bot_comments()
    assert [c["id"] for c in comments] == [1]


def test_delete_comment_returns_true_on_204(monkeypatch):
    a = _analyzer()
    a.api_base = "https://api.github.com"
    a.repo = "owner/repo"

    class FakeResp:
        status_code = 204

    class FakeSession:
        def delete(self, url, headers=None):
            return FakeResp()

    a.session = FakeSession()
    assert a.delete_comment(1) is True
