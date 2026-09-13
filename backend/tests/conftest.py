import shutil

import pytest

from app.core.config import get_settings


@pytest.fixture
def isolated_claims_file(tmp_path, monkeypatch):
    """Copy the real mock data into a temp file so tests never mutate the
    actual data/mock_claims.json used by manual testing/demos."""
    settings = get_settings()
    src = settings.claims_db_path
    dst = tmp_path / "mock_claims.json"
    shutil.copy(src, dst)
    monkeypatch.setattr(settings, "claims_db_path", dst)
    return dst

@pytest.fixture
def auth_headers():
    from app.security.auth import create_session_token
    return {"Authorization": f"Bearer {create_session_token('usr_123')}"}
