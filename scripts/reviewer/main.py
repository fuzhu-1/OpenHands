#!/usr/bin/env python3
"""
Reviewer Agent — Main Entry Point.

Orchestrates the full PR review workflow:
1. Parse PR info (from GitHub Actions env or CLI args)
2. Check PR template compliance (fast, pattern-based)
3. If compliant, run LLM-based multi-dimensional review
4. Post results as a PR comment
5. Optionally set PR review status (approve / changes_requested)

Usage:
  python -m scripts.reviewer.main  # in GitHub Actions
  python -m scripts.reviewer.main --pr 42 --repo owner/repo --token ghp_xxx  # local test
"""

import argparse
import json
import os
import sys
from typing import Optional

import requests

from .comment_builder import build_comment
from .config import ReviewerConfig
from .pr_analyzer import PRAnalyzer
from .review_engine import ReviewEngine, ReviewEngineError
from .severity import ReviewResult


def post_comment(token: str, repo: str, pr_number: int, comment: str) -> bool:
    """Post a comment on the PR via GitHub API."""
    url = f'https://api.github.com/repos/{repo}/issues/{pr_number}/comments'
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github.v3+json',
    }
    resp = requests.post(url, headers=headers, json={'body': comment})
    if resp.status_code not in (200, 201):
        print(
            f'[Reviewer] Failed to post comment: {resp.status_code} {resp.text[:200]}'
        )
        return False
    print(f'[Reviewer] Comment posted: {resp.json().get("html_url", "")}')
    return True


def set_review_status(
    token: str,
    repo: str,
    pr_number: int,
    verdict: str,
    commit_sha: str,
) -> bool:
    """Set the PR review status (approve or request changes).

    Requires the pull-requests: write permission.
    """
    if verdict not in ('approve', 'changes_requested'):
        return False

    event = 'APPROVE' if verdict == 'approve' else 'REQUEST_CHANGES'
    body = (
        '✅ Reviewer Agent: No blocking issues found.'
        if verdict == 'approve'
        else '⚠️ Reviewer Agent: Critical or high issues found — changes requested.'
    )

    url = f'https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews'
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/vnd.github.v3+json',
    }
    payload = {
        'commit_id': commit_sha,
        'event': event,
        'body': body,
    }
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code not in (200, 201):
        print(
            f'[Reviewer] Failed to set review status: {resp.status_code} {resp.text[:200]}'
        )
        return False
    print(f'[Reviewer] Review status set to {event}')
    return True


def run_review(
    token: str,
    repo: str,
    pr_number: int,
    llm_api_key: str,
    llm_model: Optional[str] = None,
    llm_base_url: Optional[str] = None,
    post_comment_flag: bool = True,
    set_status: bool = False,
) -> Optional[ReviewResult]:
    """Run the full review pipeline."""
    # Step 1: Analyze PR
    print(f'[Reviewer] Analyzing PR #{pr_number} in {repo}...')
    analyzer = PRAnalyzer(token=token, repo=repo, pr_number=pr_number)
    pr_meta = analyzer.get_pr_metadata()
    print(f'[Reviewer] Title: {pr_meta["title"]}')
    print(
        f'[Reviewer] Files changed: {pr_meta["changed_files"]}, '
        f'++{pr_meta["additions"]} --{pr_meta["deletions"]}'
    )

    # Step 2: Template compliance check (fast, pattern-based)
    print('[Reviewer] Checking PR template compliance...')
    template_result = analyzer.check_template_compliance()

    if not template_result['passed']:
        print(
            f'[Reviewer] Template compliance FAILED — missing: {template_result["missing"]}'
        )
        result = ReviewResult(template_compliance=template_result)
        # Add a template issue
        from .severity import Issue, Severity

        for field in template_result['missing']:
            result.add_issue(
                Issue(
                    severity=Severity.HIGH,
                    file='PR Description',
                    line=None,
                    category='template',
                    title=f'Missing template field: {field}',
                    description=f"The PR template requires a '{field}' section.",
                    suggestion=f"Add a '## {field}' section to the PR description.",
                )
            )

        if post_comment_flag:
            for old in analyzer.get_existing_bot_comments():
                analyzer.delete_comment(old['id'])
            comment = build_comment(result)
            post_comment(token, repo, pr_number, comment)
        if set_status and pr_meta.get('head_sha'):
            set_review_status(
                token, repo, pr_number, result.summary['verdict'], pr_meta['head_sha']
            )
        return result

    print('[Reviewer] Template compliance PASSED')

    # Step 3: Get diff
    print('[Reviewer] Fetching PR diff...')
    diff_text = analyzer.get_diff()
    print(f'[Reviewer] Diff size: {len(diff_text)} chars')

    # Step 4: LLM review (chunked, fail closed)
    from .diff_chunker import chunk_files

    print(f'[Reviewer] Running LLM review (model: {llm_model})...')
    try:
        cfg = ReviewerConfig.load()
        model = llm_model or cfg.model
        engine = ReviewEngine(
            api_key=llm_api_key,
            model=model,
            base_url=llm_base_url,
            refine_threshold=cfg.suggestion_score_threshold,
        )
        file_list = analyzer.get_files()
        total_patch_chars = sum(len(f.get('patch', '')) for f in file_list)
        if file_list and total_patch_chars > cfg.chunk_size_chars:
            chunks = chunk_files(file_list, chunk_size_chars=cfg.chunk_size_chars)
            print(f'[Reviewer] Diff split into {len(chunks)} chunks')
            result = ReviewResult(template_compliance={'passed': True, 'missing': []})
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=cfg.max_parallel_chunks) as pool:
                partials = list(
                    pool.map(
                        lambda chunk: engine.review(chunk['text'], pr_meta),
                        chunks,
                    )
                )
            for partial in partials:
                result.merge(partial)
        else:
            result = engine.review(diff_text, pr_meta)
    except ReviewEngineError as e:
        print(f'[Reviewer] LLM review failed: {e}')
        if post_comment_flag:
            for old in analyzer.get_existing_bot_comments():
                analyzer.delete_comment(old['id'])
            failure_comment = (
                '## ⚠️ Reviewer Agent Report\n\n'
                'Automated review could not be completed (LLM call failed). '
                'No approval status was set. Please re-trigger after resolving the issue.'
            )
            post_comment(token, repo, pr_number, failure_comment)
        return None

    print(
        f'[Reviewer] Review complete — {result.summary["total"]} issues found, '
        f'verdict: {result.summary["verdict"]}'
    )

    # Step 5: Post comment (replace previous bot comments)
    if post_comment_flag:
        for old in analyzer.get_existing_bot_comments():
            analyzer.delete_comment(old['id'])
        comment = build_comment(result)
        post_comment(token, repo, pr_number, comment)
        print(f'[Reviewer] Comment posted to PR #{pr_number}')

    # Step 6: Submit review (inline comments for validated critical/high issues)
    if set_status:
        commit_sha = pr_meta.get('head_sha', '')
        if commit_sha:
            from .severity import Severity

            event = (
                'APPROVE'
                if result.summary['verdict'] == 'approve'
                else 'REQUEST_CHANGES'
            )
            body = (
                '✅ Reviewer Agent: No blocking issues found.'
                if event == 'APPROVE'
                else '⛔️ Reviewer Agent: Critical or high issues found — changes requested.'
            )
            inline = []
            valid_ranges = analyzer.get_valid_line_ranges()
            for issue in result.issues:
                if (
                    issue.severity in (Severity.CRITICAL, Severity.HIGH)
                    and issue.file
                    and issue.line
                ):
                    ranges = valid_ranges.get(issue.file, [])
                    if any(start <= issue.line <= end for start, end in ranges):
                        inline.append(
                            {
                                'path': issue.file,
                                'line': issue.line,
                                'side': 'RIGHT',
                                'body': f'[{issue.category}] {issue.title}\n\n{issue.description[:300]}',
                            }
                        )
            if inline:
                analyzer.post_review_with_comments(commit_sha, event, body, inline)
            else:
                set_review_status(
                    token, repo, pr_number, result.summary['verdict'], commit_sha
                )

    return result


def main() -> None:
    parser = argparse.ArgumentParser(description='Reviewer Agent — automated PR review')
    parser.add_argument('--pr', type=int, help='PR number')
    parser.add_argument('--repo', help='Repository (owner/repo)')
    parser.add_argument('--token', help='GitHub token')
    parser.add_argument('--llm-api-key', help='LLM API key')
    parser.add_argument(
        '--llm-model',
        default=None,
        help='LLM model name (defaults to .github/reviewer.yml)',
    )
    parser.add_argument('--llm-base-url', help='LLM API base URL (for proxies)')
    parser.add_argument(
        '--set-status', action='store_true', help='Set PR review status'
    )
    parser.add_argument(
        '--dry-run', action='store_true', help='Print comment without posting'
    )

    args = parser.parse_args()

    # Resolve parameters (env → file → CLI)
    token = (
        args.token
        or os.environ.get('REVIEWER_GITHUB_TOKEN')
        or os.environ.get('GITHUB_TOKEN', '')
    )
    repo = args.repo or os.environ.get('GITHUB_REPOSITORY', '')
    pr_number = args.pr

    if not pr_number and os.environ.get('GITHUB_EVENT_PATH'):
        try:
            with open(os.environ['GITHUB_EVENT_PATH']) as f:
                event = json.load(f)
            pr_number = event.get('pull_request', {}).get('number') or event.get(
                'issue', {}
            ).get('number')
        except (json.JSONDecodeError, FileNotFoundError):
            pass

    if not token or not repo or not pr_number:
        print('[Reviewer] Missing required params: token, repo, and pr_number')
        print('[Reviewer] Provide via CLI args or environment variables')
        sys.exit(1)

    llm_api_key = args.llm_api_key or os.environ.get('REVIEWER_LLM_API_KEY', token)
    llm_base_url = args.llm_base_url or os.environ.get('REVIEWER_LLM_BASE_URL')

    if args.dry_run:
        # Just build and print the comment, don't post
        analyzer = PRAnalyzer(token=token, repo=repo, pr_number=pr_number)
        pr_meta = analyzer.get_pr_metadata()
        diff_text = analyzer.get_diff()
        cfg = ReviewerConfig.load()
        engine = ReviewEngine(
            api_key=llm_api_key,
            model=args.llm_model or cfg.model,
            base_url=llm_base_url,
            refine_threshold=cfg.suggestion_score_threshold,
        )
        try:
            result = engine.review(diff_text, pr_meta)
        except ReviewEngineError as e:
            print(f'[Reviewer] LLM review failed: {e}')
            sys.exit(1)
        comment = build_comment(result)
        print(comment)
        return

    outcome = run_review(
        token=token,
        repo=repo,
        pr_number=pr_number,
        llm_api_key=llm_api_key,
        llm_model=args.llm_model,
        llm_base_url=llm_base_url,
        post_comment_flag=True,
        set_status=args.set_status,
    )
    if outcome is None:
        sys.exit(1)


if __name__ == '__main__':
    main()
