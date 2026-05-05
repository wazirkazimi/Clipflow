#!/usr/bin/env python3
import os
from pathlib import Path

backend_test_files = [
    'backend/test_captions.py',
    'backend/test_smart_clipping.py',
    'backend/example_batch_generation.py',
    'backend/example_youtube_batch.py',
    'backend/generate_10_clips.py',
    'backend/quick_setup.py',
    'backend/API_REFERENCE.txt',
    'backend/COMPLETION_STATUS_v2.0.txt',
    'backend/FEATURES_v2.0.txt',
    'backend/GAMEPLAY_ROTATION_GUIDE.txt',
    'backend/YOUTUBE_API_v2_REFERENCE.txt',
    'backend/YOUTUBE_BATCH_RELEASE_NOTES.txt',
    'backend/clipflow.db',
    'backend/clipflow_instagram.db'
]

root_old_files = [
    'QUICK_START_v2.0.md',
    'VERIFICATION_REPORT_v2.0.txt'
]

all_files = backend_test_files + root_old_files

print('Deleting unwanted files...\n')
deleted_count = 0
for filepath in all_files:
    p = Path(filepath)
    if p.exists():
        try:
            p.unlink()
            print(f'✓ Deleted: {filepath}')
            deleted_count += 1
        except Exception as e:
            print(f'✗ Failed to delete {filepath}: {e}')
    else:
        print(f'- Skipped (not found): {filepath}')

print(f'\nCleanup complete! {deleted_count} files deleted.')
