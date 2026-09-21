"""Settings for the automated test suite (used by pytest, see pyproject.toml)."""

import os
import tempfile
from pathlib import Path

_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="avifly-test-"))

os.environ["AVIFLY_SKIP_DOTENV"] = "1"
os.environ.setdefault("AVIFLY_SECRET_KEY", "test-only-secret-key")
os.environ["AVIFLY_DATA_DIR"] = str(_TEST_DATA_DIR)

from config.settings import *  # noqa: E402, F403
from config.settings import STORAGES  # noqa: E402

DEBUG = False
PUBLIC_MODE = False
ALLOWED_HOSTS = ["testserver", "localhost"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
AVIFLY_TURNSTILE_SITE_KEY = ""
AVIFLY_TURNSTILE_SECRET_KEY = ""
AVIFLY_CF_ACCESS_TEAM_DOMAIN = ""
AVIFLY_CF_ACCESS_AUD = ""
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_RATE_LIMITS = False
