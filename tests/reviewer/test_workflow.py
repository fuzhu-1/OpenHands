"""Guard tests: reviewer workflow must stay label-gated and single-source."""

from pathlib import Path

import yaml

WORKFLOW = (
    Path(__file__).resolve().parents[2] / '.github' / 'workflows' / 'reviewer.yml'
)


def _load() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding='utf-8'))


def _events(data: dict) -> dict:
    # PyYAML 会把 YAML 1.1 的 `on:` 解析成布尔 True，这里兼容两种 key
    raw = data.get('on', data.get(True))
    assert isinstance(raw, dict), f'unexpected on: {raw!r}'
    return raw


def test_workflow_has_single_event_source():
    assert list(_events(_load()).keys()) == ['pull_request_target']


def test_workflow_has_label_gate():
    condition = _load()['jobs']['reviewer']['if']
    assert 'review-this' in condition


def test_workflow_does_not_trigger_on_unlabeled():
    assert 'unlabeled' not in _events(_load())['pull_request_target']['types']


def test_workflow_has_secrets_scan_job():
    assert 'secrets-scan' in _load()['jobs']


def test_secrets_scan_checks_out_pr_head():
    raw = WORKFLOW.read_text(encoding='utf-8')
    assert 'head.sha' in raw
