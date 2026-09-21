"""The settings refuse to run against a data folder that belongs to another account."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings

pytestmark = pytest.mark.skipif(os.geteuid() == 0, reason="root can write anywhere")


def load_settings(data_dir: Path) -> subprocess.CompletedProcess:
    """Start Django in a fresh process, the way manage.py would."""
    env = {
        **os.environ,
        "AVIFLY_SKIP_DOTENV": "1",
        "AVIFLY_SECRET_KEY": "test-only-secret-key",
        "AVIFLY_DATA_DIR": str(data_dir),
        "DJANGO_SETTINGS_MODULE": "config.settings",
    }
    return subprocess.run(
        [sys.executable, "-c", "import django; django.setup()"],
        cwd=settings.BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_refuses_a_data_folder_owned_by_another_account(tmp_path):
    data = tmp_path / "var"
    data.mkdir()
    data.chmod(0o500)  # readable but not writable, as the live var/ is to the developer
    try:
        result = load_settings(data)
    finally:
        data.chmod(0o700)
    assert result.returncode != 0
    assert "belongs to the account the service runs as" in result.stderr


def test_accepts_a_writable_data_folder(tmp_path):
    result = load_settings(tmp_path / "var")
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "var" / "log").is_dir()
