"""Filesystem containment and owner checks on citation page images."""
from types import SimpleNamespace
from unittest.mock import AsyncMock
import uuid

import pytest
from fastapi import HTTPException

from app.api.documents import get_page_image
from app.config import settings


@pytest.mark.asyncio
async def test_page_image_rejects_cache_symlink_escape(tmp_path, monkeypatch):
    root = tmp_path / 'pages'
    root.mkdir()
    outside = tmp_path / 'outside'
    outside.mkdir()
    (outside / 'page-1.png').write_bytes(b'not-public')
    doc_id = uuid.uuid4()
    (root / str(doc_id)).symlink_to(outside, target_is_directory=True)
    monkeypatch.setattr(settings, 'page_image_dir', str(root))
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
        scalar_one_or_none=lambda: SimpleNamespace(id=doc_id))))
    with pytest.raises(HTTPException) as error:
        await get_page_image(str(doc_id), 1, {'user_id': str(uuid.uuid4())}, db)
    assert error.value.status_code == 404


@pytest.mark.asyncio
async def test_page_image_unknown_or_other_owner_does_not_read_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'page_image_dir', str(tmp_path))
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(
        scalar_one_or_none=lambda: None)))
    with pytest.raises(HTTPException) as error:
        await get_page_image(str(uuid.uuid4()), 1, {'user_id': str(uuid.uuid4())}, db)
    assert error.value.status_code == 404
