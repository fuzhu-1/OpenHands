"""Tests for reviewer configuration loading."""

from scripts.reviewer.config import ReviewerConfig


def test_defaults():
    cfg = ReviewerConfig()
    assert cfg.model == "deepseek-v4-flash"
    assert cfg.chunk_size_chars == 12000
    assert cfg.suggestion_score_threshold == 5
    assert cfg.template_fields == ["Why", "Summary", "How to Test", "Type"]


def test_load_missing_file_uses_defaults(tmp_path):
    cfg = ReviewerConfig.load(str(tmp_path / "missing.yml"))
    assert cfg.model == "deepseek-v4-flash"
    assert cfg.chunk_size_chars == 12000


def test_load_overrides_known_keys(tmp_path):
    p = tmp_path / "reviewer.yml"
    p.write_text(
        "model: gpt-4o\nchunk_size_chars: 8000\nsuggestion_score_threshold: 6\n",
        encoding="utf-8",
    )
    cfg = ReviewerConfig.load(str(p))
    assert cfg.model == "gpt-4o"
    assert cfg.chunk_size_chars == 8000
    assert cfg.suggestion_score_threshold == 6


def test_load_ignores_unknown_keys(tmp_path):
    p = tmp_path / "reviewer.yml"
    p.write_text("bogus_key: 1\n", encoding="utf-8")
    cfg = ReviewerConfig.load(str(p))
    assert cfg.model == "deepseek-v4-flash"
