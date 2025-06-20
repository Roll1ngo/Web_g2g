from pathlib import Path
import os

from dotenv import load_dotenv

load_dotenv()

EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
 # Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
print(os.getpid())

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.1/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = ['localhost',
                 'able-above-monitor.ngrok-free.app',
                 'wowserviceportal.pp.ua']

CSRF_TRUSTED_ORIGINS = [
    'https://able-above-monitor.ngrok-free.app',
    'http://localhost:8000',
    'http://127.0.0.1:8000',
    'https://wowserviceportal.pp.ua',
    ]


# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "import_export",
    "main.apps.MainConfig",
    "users.apps.UsersConfig",
    "internal_market.apps.InternalMarketConfig",
    "user_profile.apps.UserProfileConfig",
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google', # Додаємо провайдера Google
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware"

]

ROOT_URLCONF = "web_resource_g2g.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "main.context_processors.user_balance",
            ],
        },
    },
]

WSGI_APPLICATION = "web_resource_g2g.wsgi.application"


# Database
# https://docs.djangoproject.com/en/5.1/ref/settings/#databases

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": Path("/home/roll1ng/Documents/Python_projects/Common_database_to_web_and_server/G2G.sqlite").resolve()
    }
}


# Password validation
# https://docs.djangoproject.com/en/5.1/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.1/topics/i18n/

LANGUAGE_CODE = "uk"

TIME_ZONE = 'Europe/Kiev'

USE_I18N = True

USE_TZ = False


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.1/howto/static-files/

STATIC_URL = "static/"
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'main/static'),
]

# Default primary key field type
# https://docs.djangoproject.com/en/5.1/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

EMAIL_BACKEND = os.getenv('EMAIL_BACKEND')
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = os.getenv('EMAIL_PORT')
EMAIL_STARTTLS = os.getenv('EMAIL_STARTTLS')
EMAIL_USE_SSL = os.getenv('EMAIL_USE_SSL')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD')
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER
PASSWORD_RESET_CONFIRM_URL = 'password_reset_confirm'

MEDIA_URL = '/media/'  # URL для медіа-файлів
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')  # Директорія для зберігання медіа-файлів

SITE_ID = 2



# Налаштування для allauth
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_UNIQUE_EMAIL = True           # Гарантує унікальність email
ACCOUNT_AUTHENTICATION_METHOD = 'username_email'
ACCOUNT_EMAIL_VERIFICATION = 'none' # Можете змінити на 'mandatory' або 'optional'
SOCIALACCOUNT_EMAIL_VERIFICATION = ACCOUNT_EMAIL_VERIFICATION # Використовує те ж налаштування верифікації для соціальних акаунтів
SOCIALACCOUNT_QUERY_EMAIL = ACCOUNT_EMAIL_REQUIRED
SOCIALACCOUNT_LOGIN_ON_GET = True
SOCIALACCOUNT_ADAPTER = 'main.adapters.CustomSocialAccountAdapter'
SOCIALACCOUNT_AUTO_SIGNUP = True  # Автоматична реєстрація


ACCOUNT_ALLOW_REGISTRATION = True
LOGIN_REDIRECT_URL = '/'  # Куди перенаправляти після успішного входу
LOGOUT_REDIRECT_URL = '/login' # Куди перенаправляти після виходу

# Налаштування для соціальних провайдерів
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        # Для детальніших налаштувань (наприклад, дозволи)
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        }
    }
}

# Це дозволяє allauth використовувати стандартну систему автентифікації Django
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
)

# Налаштування SMTP Ukr.net
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.ukr.net'
EMAIL_PORT = 465  # Для SSL або 2525 для TLS
EMAIL_USE_SSL = True  # True для порту 465, False для 2525
EMAIL_USE_TLS = False  # True для порту 2525
EMAIL_HOST_USER = 'fastsaleservice@ukr.net'  # Повна адреса
EMAIL_HOST_PASSWORD = EMAIL_HOST_PASSWORD  # Пароль для SMTP (не від облікового запису!)
DEFAULT_FROM_EMAIL = 'Fast Sale Service <fastsaleservice@ukr.net>'  # Відображуване ім'я
