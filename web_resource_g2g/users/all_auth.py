# URL, на який перенаправляє після входу/реєстрації
LOGIN_REDIRECT_URL = 'main:start_page' # Або '/dashboard/' або інший URL

# Деякі загальні налаштування allauth
ACCOUNT_AUTHENTICATION_METHOD = 'username_email' # Дозволяє вхід за іменем користувача або email
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False # Якщо ви хочете, щоб користувачі входили за email
ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE = True
ACCOUNT_SESSION_REMEMBER = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USERNAME_MIN_LENGTH = 4
ACCOUNT_EMAIL_VERIFICATION = 'none' # 'mandatory' для верифікації пошти, 'optional', 'none'
ACCOUNT_LOGIN_ATTEMPTS_LIMIT = 5 # Захист від брутфорсу

# Налаштування провайдерів соціальних мереж
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': '222206179817-nk1cs6tu4pafiqliklda53ksnbmc3dai.apps.googleusercontent.com', # З Google Cloud Console
            'secret': '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', # З Google Cloud Console
            'key': '' # Залишити порожнім
        },
        'SCOPE': [ # Запитувані дозволи від Google
            'profile',
            'email',
        ],
        'AUTH_PARAMS': { # Параметри автентифікації
            'access_type': 'offline', # Дозволяє отримувати refresh_token (якщо потрібно)
        },
        'PACKAGE': 'allauth.socialaccount.providers.google',
    }
}