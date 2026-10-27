"""
Django settings for config project.

Projet : Application de gestion des paiements des forces de l'ordre
         Perception Principale de Marovoay

Environnement : Ubuntu, Python 3.10, Django 5.2.18, SQLite (Mode Local)
"""

from pathlib import Path
import environ


# ============================================================
# CHEMINS DE BASE
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent


# ============================================================
# LECTURE DU FICHIER .env
# ============================================================

env = environ.Env(
    DEBUG=(bool, False),
)

environ.Env.read_env(BASE_DIR / '.env')


# ============================================================
# SÉCURITÉ
# ============================================================

SECRET_KEY = env('SECRET_KEY')

DEBUG = env('DEBUG')

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['127.0.0.1', 'localhost'])

CSRF_TRUSTED_ORIGINS = env.list('CSRF_TRUSTED_ORIGINS', default=[])

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


# ============================================================
# APPLICATIONS
# ============================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Applications du projet
    'core',
    'accounts',
    'audit',
    'agents',
    'missions',
    'tarifs',
    'gardes',
    'decomptes',
    'paiements',
    'rapports',
]


# ============================================================
# MIDDLEWARE
# ============================================================

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ============================================================
# URLS ET WSGI
# ============================================================

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.breadcrumb',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'


# ============================================================
# BASE DE DONNÉES (SQLITE POUR UTILISATION LOCALE)
# ============================================================
# On utilise SQLite pour que l'application soit 100% autonome 
# et facile à installer sur le PC Windows de votre supérieur.

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# ============================================================
# VALIDATION DES MOTS DE PASSE
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 10,
        },
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# ============================================================
# INTERNATIONALISATION
# ============================================================

LANGUAGE_CODE = 'fr-fr'

TIME_ZONE = 'Indian/Antananarivo'

USE_I18N = True

USE_TZ = True


# ============================================================
# FICHIERS STATIQUES ET MÉDIAS
# ============================================================

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ============================================================
# CLÉ PRIMAIRE PAR DÉFAUT
# ============================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ============================================================
# AUTHENTIFICATION
# ============================================================

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'login'


# ============================================================
# SÉCURITÉ EN PRODUCTION (à activer quand DEBUG=False)
# ============================================================

# ⚠️ ATTENTION : On a commenté les lignes de redirection HTTPS.
# Si on les laisse, l'application sur Windows sans certificat SSL 
# va faire une boucle de redirection infinie (ERR_TOO_MANY_REDIRECTS).
if not DEBUG:
    # SECURE_SSL_REDIRECT = True
    # SESSION_COOKIE_SECURE = True
    # CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    # SECURE_HSTS_SECONDS = 31536000
    # SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # SECURE_HSTS_PRELOAD = True


# ============================================================
# JOURNALISATION
# ============================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'WARNING',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'weasyprint': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
        'fontTools': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
