"""Tests for diff chunking."""

from scripts.reviewer.diff_chunker import chunk_files


def test_files_grouped_under_size_limit():
    files = [
        {'filename': 'a.py', 'patch': 'x' * 5000},
        {'filename': 'b.py', 'patch': 'y' * 5000},
    ]
    chunks = chunk_files(files, chunk_size_chars=6000)
    assert len(chunks) == 2
    assert all('patch truncated' not in c['text'] for c in chunks)


def test_small_files_batched_together():
    files = [
        {'filename': 'a.py', 'patch': 'x' * 1000},
        {'filename': 'b.py', 'patch': 'y' * 1000},
        {'filename': 'c.py', 'patch': 'z' * 1000},
    ]
    chunks = chunk_files(files, chunk_size_chars=4000)
    assert len(chunks) == 1
    assert all(f['filename'] in chunks[0]['text'] for f in files)


def test_oversized_single_file_truncated_with_marker():
    files = [{'filename': 'big.py', 'patch': 'x' * 20000}]
    chunks = chunk_files(files, chunk_size_chars=12000)
    assert len(chunks) == 1
    assert chunks[0]['files'] == [files[0]]
    assert 'patch truncated' in chunks[0]['text']
