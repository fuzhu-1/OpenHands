"""Split per-file patches into LLM-sized chunks."""

from __future__ import annotations

from typing import Any


def _render(files: list[dict[str, Any]], chunk_size_chars: int) -> str:
    parts = []
    for f in files:
        patch = f.get('patch', '')
        if len(patch) > chunk_size_chars:
            patch = patch[:chunk_size_chars] + '\n... [patch truncated]'
        parts.append(f'### File: {f["filename"]}\n```diff\n{patch}\n```')
    return '\n\n'.join(parts)


def chunk_files(
    files: list[dict[str, Any]],
    chunk_size_chars: int = 12000,
) -> list[dict[str, Any]]:
    """Group files into chunks under chunk_size_chars; oversized files get one chunk."""
    chunks: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_size = 0

    for f in files:
        patch = f.get('patch', '')
        if len(patch) > chunk_size_chars:
            if current:
                chunks.append(
                    {'files': current, 'text': _render(current, chunk_size_chars)}
                )
                current, current_size = [], 0
            chunks.append({'files': [f], 'text': _render([f], chunk_size_chars)})
            continue
        if current and current_size + len(patch) > chunk_size_chars:
            chunks.append(
                {'files': current, 'text': _render(current, chunk_size_chars)}
            )
            current, current_size = [], 0
        current.append(f)
        current_size += len(patch)

    if current:
        chunks.append({'files': current, 'text': _render(current, chunk_size_chars)})
    return chunks
