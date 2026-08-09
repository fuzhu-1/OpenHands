"""Reviewer configuration loaded from .github/reviewer.yml (optional)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Optional

import yaml


@dataclass
class ReviewerConfig:
    model: str = 'deepseek-v4-flash'
    base_url: Optional[str] = None
    chunk_size_chars: int = 12000
    max_parallel_chunks: int = 4
    suggestion_score_threshold: int = 5
    template_fields: list[str] = field(
        default_factory=lambda: ['Why', 'Summary', 'How to Test', 'Type']
    )
    enabled_dimensions: list[str] = field(
        default_factory=lambda: ['security', 'quality', 'performance', 'bilingual']
    )
    max_comment_chars: int = 60000

    _KNOWN_KEYS = (
        'model',
        'base_url',
        'chunk_size_chars',
        'max_parallel_chunks',
        'suggestion_score_threshold',
        'template_fields',
        'enabled_dimensions',
        'max_comment_chars',
    )

    @classmethod
    def load(cls, path: Optional[str] = None) -> 'ReviewerConfig':
        """Load config from YAML; missing file or keys fall back to defaults."""
        cfg = cls()
        path = path or os.environ.get('REVIEWER_CONFIG', '.github/reviewer.yml')
        if os.path.exists(path):
            with open(path, encoding='utf-8') as f:
                data: dict[str, Any] = yaml.safe_load(f) or {}
            for key in cls._KNOWN_KEYS:
                if key in data:
                    setattr(cfg, key, data[key])
        return cfg
