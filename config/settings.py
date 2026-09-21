"""Django settings for Avifly Tracker.

Every deployment-specific value comes from environment variables, or from a
``.env`` file next to ``manage.py`` (see ``.env.example``). Nothing secret lives
in this file.
"""

import os
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
if not env.bool("AVIFLY_SKIP_DOTENV", default=False):
    environ.Env.read_env(BASE_DIR / ".env")

# --------------------------------------------------------------------------------------
# Core
# --------------------------------------------------------------------------------------
DEBUG = env.bool("AVIFLY_DEBUG", default=False)

SECRET_KEY = env("AVIFLY_SECRET_KEY", default="")
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Set AVIFLY_SECRET_KEY (see .env.example).")
    SECRET_KEY = "insecure-development-key-do-not-use-in-production"

ALLOWED_HOSTS = env.list("AVIFLY_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("AVIFLY_CSRF_TRUSTED_ORIGINS", default=[])

# Where the database, uploads, cache, e-mails and logs are kept.
DATA_DIR = Path(env("AVIFLY_DATA_DIR", default=str(BASE_DIR / "var")))
if DATA_DIR.exists() and not os.access(DATA_DIR, os.W_OK):
    # The live data belongs to the service's own account (see deploy/install.sh).
    raise ImproperlyConfigured(
        f"{DATA_DIR} belongs to the account the service runs as, not to you. Run "
        "database commands as that account (make shell, make migrate, "
        'make manage cmd="..."), or against the development copy (make dev-manage).'
    )
for _sub in ("", "media", "cache", "log", "mail"):
    (DATA_DIR / _sub).mkdir(parents=True, exist_ok=True)

# --------------------------------------------------------------------------------------
# Modules
#
# Core modules are always on. Feature modules can be switched off by listing only
# the ones you want in AVIFLY_MODULES. Each module registers its own menu items,
# pages, permissions and settings — see avifly/core/registry.py.
# --------------------------------------------------------------------------------------
AVIFLY_CORE_MODULES = [
    "avifly.core",
    "avifly.accounts",
    "avifly.customers",
    "avifly.equipment",
    "avifly.jobs",
]
AVIFLY_MODULES = [
    module
    for module in env.list(
        "AVIFLY_MODULES",
        default=["avifly.money", "avifly.analytics", "avifly.imports", "avifly.docs"],
    )
    if module
]

INSTALLED_APPS = [
    # Avifly modules come first so their templates can override third-party ones.
    *AVIFLY_CORE_MODULES,
    *AVIFLY_MODULES,
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.forms",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "auditlog",
]

MIDDLEWARE = [
    "avifly.core.middleware.CloudflareRealIPMiddleware",
    "avifly.core.middleware.CloudflareAccessMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "avifly.core.middleware.SecurityHeadersMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Every page needs a signed-in user unless a view is explicitly marked public.
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.i18n",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "avifly.core.context_processors.avifly",
            ],
        },
    },
]
FORM_RENDERER = "avifly.core.forms.AviflyFormRenderer"

# --------------------------------------------------------------------------------------
# Database (SQLite in WAL mode: one file, easy to back up, plenty for this workload)
# --------------------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "db.sqlite3",
        "OPTIONS": {
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
            "init_command": (
                "PRAGMA journal_mode=WAL;PRAGMA synchronous=NORMAL;PRAGMA busy_timeout=5000;"
            ),
        },
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.filebased.FileBasedCache",
        "LOCATION": DATA_DIR / "cache",
    }
}

# --------------------------------------------------------------------------------------
# Authentication (django-allauth: open sign-up, owners approve new accounts)
# --------------------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "core:dashboard"
ACCOUNT_LOGOUT_REDIRECT_URL = "account_login"

ACCOUNT_ADAPTER = "avifly.accounts.adapter.AccountAdapter"
ACCOUNT_FORMS = {"signup": "avifly.accounts.forms.SignupForm"}
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USERNAME_MIN_LENGTH = 3
ACCOUNT_EMAIL_VERIFICATION = env("AVIFLY_EMAIL_VERIFICATION", default="optional")
ACCOUNT_SESSION_REMEMBER = None  # "Remember me" checkbox on the login form
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = False
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
MFA_TOTP_ISSUER = "Avifly"

AVIFLY_SIGNUP_OPEN = env.bool("AVIFLY_SIGNUP_OPEN", default=True)

SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # 30 days — you stay signed in on your phone
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
# Browsers share cookies between ports on the same host, so a second copy of the app
# (the development server) needs its own cookie names to not sign you out of this one.
_COOKIE_PREFIX = env("AVIFLY_COOKIE_PREFIX", default="")
SESSION_COOKIE_NAME = f"{_COOKIE_PREFIX}sessionid"
CSRF_COOKIE_NAME = f"{_COOKIE_PREFIX}csrftoken"

# --------------------------------------------------------------------------------------
# Internationalisation — English now; add ("mk", "Македонски") once translated.
# --------------------------------------------------------------------------------------
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = env("AVIFLY_TIME_ZONE", default="Europe/Skopje")
USE_I18N = True
USE_TZ = True
FORMAT_MODULE_PATH = ["config.formats"]

# --------------------------------------------------------------------------------------
# Static files and uploads (uploads are only served to signed-in users with access)
# --------------------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = DATA_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_ROOT = DATA_DIR / "media"
MEDIA_URL = "/media/"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
AVIFLY_MAX_UPLOAD_MB = 15
# Uploads (and collected static files) are readable by the service and its group only.
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o750

# --------------------------------------------------------------------------------------
# E-mail. Without AVIFLY_EMAIL_HOST, e-mails are written to var/mail/ instead of sent.
# --------------------------------------------------------------------------------------
EMAIL_HOST = env("AVIFLY_EMAIL_HOST", default="")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = env.int("AVIFLY_EMAIL_PORT", default=587)
    EMAIL_HOST_USER = env("AVIFLY_EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = env("AVIFLY_EMAIL_HOST_PASSWORD", default="")
    EMAIL_USE_TLS = env.bool("AVIFLY_EMAIL_USE_TLS", default=True)
    EMAIL_TIMEOUT = 20
else:
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    EMAIL_FILE_PATH = DATA_DIR / "mail"
DEFAULT_FROM_EMAIL = env("AVIFLY_DEFAULT_FROM_EMAIL", default="Avifly <no-reply@localhost>")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# --------------------------------------------------------------------------------------
# Security. "Public mode" = running behind Cloudflare Tunnel on a real domain.
# --------------------------------------------------------------------------------------
PUBLIC_MODE = env.bool("AVIFLY_PUBLIC_MODE", default=False)

X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"

if PUBLIC_MODE:
    # cloudflared talks plain HTTP to us on localhost and tells us the visitor used HTTPS.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env.int("AVIFLY_HSTS_SECONDS", default=60 * 60 * 24 * 365)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^healthz$"]
    # HSTS stays off for other subdomains of your domain and off the preload list, on purpose.
    SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]

# Take the visitor's real IP from Cloudflare's CF-Connecting-IP header, but only when
# the request arrives from cloudflared on this machine.
AVIFLY_TRUST_CLOUDFLARE = env.bool("AVIFLY_TRUST_CLOUDFLARE", default=PUBLIC_MODE)
AVIFLY_TRUSTED_PROXIES = env.list("AVIFLY_TRUSTED_PROXIES", default=["127.0.0.1", "::1"])

# Cloudflare Access: if both are set, every request must carry a valid Access token.
AVIFLY_CF_ACCESS_TEAM_DOMAIN = env("AVIFLY_CF_ACCESS_TEAM_DOMAIN", default="")
AVIFLY_CF_ACCESS_AUD = env("AVIFLY_CF_ACCESS_AUD", default="")

# Cloudflare Turnstile bot check on the sign-up form (optional).
AVIFLY_TURNSTILE_SITE_KEY = env("AVIFLY_TURNSTILE_SITE_KEY", default="")
AVIFLY_TURNSTILE_SECRET_KEY = env("AVIFLY_TURNSTILE_SECRET_KEY", default="")

# Map tiles: satellite imagery (Esri) and street map (OpenStreetMap).
AVIFLY_MAP_TILE_HOSTS = ["https://server.arcgisonline.com", "https://tile.openstreetmap.org"]

_turnstile = ["https://challenges.cloudflare.com"] if AVIFLY_TURNSTILE_SITE_KEY else []
AVIFLY_CONTENT_SECURITY_POLICY = {
    "default-src": ["'self'"],
    "script-src": ["'self'", *_turnstile],
    "style-src": ["'self'", "'unsafe-inline'"],  # Leaflet/ECharts set inline styles
    "img-src": ["'self'", "data:", "blob:", *AVIFLY_MAP_TILE_HOSTS],
    "font-src": ["'self'"],
    "connect-src": ["'self'", *_turnstile],
    "frame-src": _turnstile or ["'none'"],
    "frame-ancestors": ["'none'"],
    "form-action": ["'self'"],
    "base-uri": ["'self'"],
    "object-src": ["'none'"],
}

AVIFLY_ADMIN_ENABLED = env.bool("AVIFLY_ADMIN_ENABLED", default=True)

# --------------------------------------------------------------------------------------
# Business rules
# --------------------------------------------------------------------------------------
# Job amounts (rate × hectares) are rounded to this step: "1" = whole denars.
AVIFLY_MONEY_QUANTUM = env("AVIFLY_MONEY_QUANTUM", default="1")

# --------------------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "plain"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": DATA_DIR / "log" / "avifly.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "formatter": "plain",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
    "loggers": {
        "django.db.backends": {"level": "WARNING"},
    },
}
