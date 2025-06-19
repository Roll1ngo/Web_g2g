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
# Змінено сигнатуру функції для більшої стійкості
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


@receiver(pre_social_login, dispatch_uid="hash_social_password")
def hash_social_user_password(sender, request, sociallogin, **kwargs):
    """
    Цей сигнал викликається перед автентифікацією через соцмережу.
    Використовується для генерації та встановлення випадкового пароля
    для користувачів, що входять через соцмережі, якщо у них немає пароля.
    """
    user = sociallogin.user
    logger.info(f"hash_social_user_password called for {user.email}. Password usable: {user.has_usable_password()}")

    # Ця логіка тепер переважно обробляється у save_user адаптера,
    # але ми залишаємо тут перевірку, якщо потрібно забезпечити хешування
    # до save_user, хоча це може бути надлишковим.
    # Якщо user.password вже хешований або має usable_password, не чіпаємо.
    if user.password and user.password.startswith('!') or not user.has_usable_password():
        try:
            # Генеруємо випадковий пароль
            raw_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))

            # Зберігаємо оригінальний пароль тимчасово
            temp_pass, created = TemporaryPassword.objects.update_or_create(
                user=user,
                defaults={'raw_password': raw_password}
            )

            # Хешуємо та оновлюємо пароль
            user.set_password(raw_password)
            # Важливо: НЕ ЗБЕРІГАЙТЕ user тут, якщо save_user() адаптера ще не викликався,
            # оскільки allauth може перевизначити його.
            # user.save() - це має бути в адаптері save_user()

            logger.info(f"Successfully generated temporary password for {user.email} in hash_social_user_password.")
            logger.debug(f"Temporary password for user {user.id}: {raw_password}") # Використовуйте debug для чутливої інформації

            # --- Логіка відправки вітального листа ---
            # Ця логіка теж може бути перенесена в save_user адаптера
            # або окремий сигнал, який спрацьовує після остаточного збереження користувача.
            # Якщо ви відправляєте пароль, краще робити це після того, як він буде гарантовано збережений.

            # subject = 'Ласкаво просимо до FastSaleService!'
            # ... (решта логіки відправки листа) ...

        except Exception as e:
            logger.error(f"Password handling failed for {user.email} in hash_social_user_password: {str(e)}", exc_info=True)

