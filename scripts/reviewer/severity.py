"""
Severity level definitions for the Reviewer Agent.

Defines issue severity levels, verdict determination, and automatic
classification rules based on issue patterns.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Severity(Enum):
    CRITICAL = 'critical'
    HIGH = 'high'
    MEDIUM = 'medium'
    LOW = 'low'

    def __str__(self) -> str:
        return self.value

    @property
    def label(self) -> str:
        labels = {
            Severity.CRITICAL: '🔴 Critical',
            Severity.HIGH: '🟡 High',
            Severity.MEDIUM: '🔵 Medium',
            Severity.LOW: '⚪ Low',
        }
        return labels[self]

    @property
    def sort_order(self) -> int:
        return list(Severity).index(self)


@dataclass
class Issue:
    severity: Severity
    file: str
    line: Optional[int]
    category: str  # security, quality, performance, bilingual, template
    title: str
    description: str
    suggestion: Optional[str] = None

    @property
    def line_str(self) -> str:
        return str(self.line) if self.line is not None else '-'


@dataclass
class ReviewResult:
    template_compliance: dict  # {"passed": bool, "missing": list[str]}
    issues: list[Issue] = field(default_factory=list)
    summary: dict = field(
        default_factory=lambda: {
            'total': 0,
            'critical': 0,
            'high': 0,
            'medium': 0,
            'verdict': 'approve',
        }
    )

    def add_issue(self, issue: Issue) -> None:
        self.issues.append(issue)
        self.summary['total'] += 1
        if issue.severity == Severity.CRITICAL:
            self.summary['critical'] += 1
        elif issue.severity == Severity.HIGH:
            self.summary['high'] += 1
        elif issue.severity == Severity.MEDIUM:
            self.summary['medium'] += 1
        self._update_verdict()

    def _update_verdict(self) -> None:
        if self.summary['critical'] > 0 or self.summary['high'] > 0:
            self.summary['verdict'] = 'changes_requested'
        else:
            self.summary['verdict'] = 'approve'

    def issues_by_severity(self, severity: Severity) -> list[Issue]:
        return [i for i in self.issues if i.severity == severity]

    def issues_by_category(self, category: str) -> list[Issue]:
        return [i for i in self.issues if i.category == category]

    def merge(self, other: 'ReviewResult') -> None:
        """Merge another result's issues into this one (for chunk aggregation)."""
        for issue in other.issues:
            self.add_issue(issue)
