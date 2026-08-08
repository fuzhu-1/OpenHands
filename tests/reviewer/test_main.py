"""Tests for reviewer orchestration (fail-closed + dedup)."""

from scripts.reviewer.main import run_review
from scripts.reviewer.review_engine import ReviewEngineError
from scripts.reviewer.severity import ReviewResult


def test_llm_failure_posts_failure_comment_and_returns_none(monkeypatch):
    from scripts.reviewer import main as m

    posted = []
    monkeypatch.setattr(m, "post_comment", lambda *a, **k: posted.append(a) or True)

    class FakeAnalyzer:
        def __init__(self, *a, **k):
            pass

        def get_pr_metadata(self):
            return {
                "title": "t", "changed_files": 1, "additions": 1, "deletions": 0,
                "body": "", "head_sha": "abc123",
            }

        def check_template_compliance(self):
            return {"passed": True, "missing": []}

        def get_diff(self):
            return "diff"

        def get_existing_bot_comments(self):
            return []

    monkeypatch.setattr(m, "PRAnalyzer", FakeAnalyzer)

    class BadEngine:
        def __init__(self, **kw):
            pass

        def review(self, *a, **k):
            raise ReviewEngineError("boom")

    monkeypatch.setattr(m, "ReviewEngine", BadEngine)

    result = run_review(
        token="t", repo="r", pr_number=1, llm_api_key="k",
        post_comment_flag=True, set_status=True,
    )
    assert result is None
    assert len(posted) == 1
    assert "could not be completed" in posted[0][3]


def test_old_bot_comments_deleted_before_post(monkeypatch):
    from scripts.reviewer import main as m

    deleted = []
    monkeypatch.setattr(m, "post_comment", lambda *a, **k: True)

    class FakeAnalyzer:
        def __init__(self, *a, **k):
            pass

        def get_pr_metadata(self):
            return {
                "title": "t", "changed_files": 1, "additions": 1, "deletions": 0,
                "body": "", "head_sha": "abc123",
            }

        def check_template_compliance(self):
            return {"passed": True, "missing": []}

        def get_diff(self):
            return "diff"

        def get_existing_bot_comments(self):
            return [{"id": 11}, {"id": 12}]

        def delete_comment(self, comment_id):
            deleted.append(comment_id)
            return True

    monkeypatch.setattr(m, "PRAnalyzer", FakeAnalyzer)
    monkeypatch.setattr(m, "ReviewEngine", lambda **kw: type(
        "E", (), {"review": lambda self, *a, **k: ReviewResult(
            template_compliance={"passed": True, "missing": []},
        )}
    )())

    run_review(token="t", repo="r", pr_number=1, llm_api_key="k", post_comment_flag=True)
    assert deleted == [11, 12]
