# main/signals.py
import secrets
import string

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from main.models import Sellers, TemporaryPassword
from allauth.socialaccount.signals import social_account_added, pre_social_login
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


@receiver(post_save, sender=User)
def create_seller_for_user(sender, instance, created, **kwargs):
    """Автоматичне створення Seller для нового користувача."""
    if created and not hasattr(instance, 'seller'):
        Sellers.objects.create(auth_user=instance)
        logger.info(f"Created Seller for {instance.email}")


@receiver(social_account_added)
def update_seller_on_social_connect(sender, request, socialaccount, **kwargs):
    """Створення Seller при підключенні соцмережі."""
    user = socialaccount.user
    if not hasattr(user, 'seller'):
        Sellers.objects.create(auth_user=user)
        logger.info(f"Created Seller via social for {user.email}")


@receiver(pre_social_login, dispatch_uid="hash_social_password")
def hash_social_user_password(sender, request, sociallogin, **kwargs):
    """Фінальне оновлення пароля перед збереженням."""
    user = sociallogin.user

    if user.password and user.password.startswith('!'):
        try:
            # Спочатку зберігаємо користувача
            user.save()

            # Генеруємо випадковий пароль
            raw_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))

            # Зберігаємо оригінальний пароль тимчасово
            temp_pass, created = TemporaryPassword.objects.update_or_create(
                user=user,
                defaults={'raw_password': raw_password}
            )

            # Хешуємо та оновлюємо пароль
            user.set_password(raw_password)
            user.save()

            # Оновлюємо sociallogin
            sociallogin.save(request)

            logger.info(f"Successfully hashed password for {user.email}")
            logger.info(f"Temporary password for user {user.id}: {raw_password}")

            # Тут можна додати відправку пароля користувачу

        except Exception as e:
            logger.error(f"Password handling failed for {user.email}: {str(e)}")
            raise