"""Validated text source intake for the workspace-scoped Evidence Atlas."""
from pathlib import PurePath
from workspace_data import add_source

MAX_SOURCE_BYTES = 256 * 1024


def save_text_source(con, *, actor_id: str, workspace_id: str, filename: str, content: str):
    # Reject path-like filenames rather than silently normalizing user input.
    if not isinstance(filename, str) or not filename or len(filename) > 160:
        raise ValueError('File name must be 1–160 characters')
    if '/' in filename or '\\' in filename or filename in ('.', '..') or '\x00' in filename:
        raise ValueError('Invalid source filename')
    if not filename.lower().endswith('.txt'):
        raise ValueError('Only .txt documents are supported by this upload')
    if not isinstance(content, str) or not content.strip():
        raise ValueError('Text document cannot be empty')
    if '\x00' in content:
        raise ValueError('Document contains NUL characters and cannot be imported as text')
    if len(content.encode('utf-8')) > MAX_SOURCE_BYTES:
        raise ValueError('Text source exceeds the 256 KiB upload limit')
    result = add_source(con, actor_id=actor_id, workspace_id=workspace_id,
                        filename=filename, kind='txt', content=content)
    return {'id': result['id'], 'filename': filename, 'kind': 'txt',
            'characters': len(content), 'warning': 'Stored source text is not independent factual verification'}
