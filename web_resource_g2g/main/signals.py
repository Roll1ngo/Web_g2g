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
from user_profile.models import WithdrawalRequest

User = get_user_model()


@receiver(post_save, sender=User)
def create_seller_for_user(sender, instance, created, **kwargs):
    if created and not hasattr(instance, 'seller'):
        ref = getattr(instance, 'ref', None)
        if ref:
            recruiter = User.objects.filter(username=ref).first()
            seller_recruiter = Sellers.objects.filter(auth_user=recruiter).first()
            Sellers.objects.create(auth_user=instance, recruiter=seller_recruiter)
            logger.info(f"Created Seller for {instance.email} with ref: {ref}")
        else:
            Sellers.objects.create(auth_user=instance)
            logger.info(f"Created Seller for {instance.email} without ref")

        # --- Додаємо створення запису WithdrawalRequest ---
        try:
            WithdrawalRequest.objects.create(
                user=instance,
                withdraw_type='do_not_withdraw',
                status='not_applicable'
            )
            logger.info(f"Created initial WithdrawalRequest for new user: {instance.email}")
        except Exception as e:
            logger.error(f"Failed to create WithdrawalRequest for user {instance.email}: {e}", exc_info=True)


# signals.py
@receiver(pre_social_login)
def capture_ref_from_google(request, sociallogin, **kwargs):
    # Отримуємо ref з request або сесії
    ref = getattr(request, 'ref', None) or request.session.get('ref')

    if ref:
        logger.info(f"Captured ref for {sociallogin.user.email}: {ref}")
        sociallogin.user.ref = ref
        # Очищаємо після використання
        if hasattr(request, 'ref'):
            del request.ref
        if 'ref' in request.session:
            del request.session['ref']
    else:
        logger.warning("No ref parameter found")



