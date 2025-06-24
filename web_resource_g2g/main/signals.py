# main/signals.py
import secrets
import string

from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.conf import settings
from django.template.loader import render_to_string
from main.models import Sellers, TemporaryPassword
# Додаємо імпорти для моделей Allauth, щоб перевірити їх існування
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from allauth.socialaccount.signals import social_account_added, pre_social_login # Залишаємо імпорти сигналів

from main.utils.logger_config import logger

User = get_user_model()


@receiver(post_save, sender=User)
def create_seller_for_user(sender, instance, created, **kwargs):
    """Автоматичне створення Seller для нового користувача."""
    if created and not hasattr(instance, 'seller'):
        Sellers.objects.create(auth_user=instance)
        logger.info(f"Created Seller for {instance.email}")


@receiver(social_account_added)
def update_seller_on_social_connect(sender, **kwargs):
    """Створення Seller при підключенні соцмережі."""
    request = kwargs.get('request') # Отримуємо request з kwargs, якщо потрібен
    socialaccount = kwargs.get('socialaccount') # Отримуємо socialaccount з kwargs

    # Перевіряємо, чи socialaccount є None або відсутній в kwargs
    if socialaccount is None:
        logger.error("update_seller_on_social_connect: 'socialaccount' argument is missing or None from kwargs. Cannot proceed.")
        return # Не можемо продовжити без socialaccount

    user = socialaccount.user
    if not hasattr(user, 'seller'):
        Sellers.objects.create(auth_user=user)
        logger.info(f"Created Seller via social for {user.email}")
    else:
        logger.info(f"Seller already exists for {user.email}. No new Seller created.")


