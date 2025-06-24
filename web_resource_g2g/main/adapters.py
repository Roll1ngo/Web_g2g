import secrets
import string

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.hashers import make_password
from django.contrib.auth import get_user_model
from django.db import transaction
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone

from main.utils.logger_config import logger
from main.models import TemporaryPassword

User = get_user_model()


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):

    def pre_social_login(self, request, sociallogin):
        """
        Called after successful social login, but before the user is created or connected.
        This method checks if a user with the given email already exists and attempts
        to connect the social account to it, preventing duplicates.
        """
        logger.info(f"pre_social_login called for {sociallogin.user.email} (Provider: {sociallogin.account.provider})")
        logger.info(f"Sociallogin initial user PK: {sociallogin.user.pk}, Email: {sociallogin.user.email}")
        logger.info(f"Socialaccount extra_data: {sociallogin.account.extra_data}")

        email = sociallogin.account.extra_data.get('email')

        if email:
            try:
                with transaction.atomic():
                    existing_user = User.objects.get(email__iexact=email)

                    logger.info(f"Found existing user by email: {existing_user.email} (PK: {existing_user.pk})")

                    social_account_already_linked = SocialAccount.objects.filter(
                        user=existing_user,
                        provider=sociallogin.account.provider,
                        uid=sociallogin.account.uid
                    ).exists()

                    email_address_already_linked = EmailAddress.objects.filter(
                        user=existing_user,
                        email__iexact=email
                    ).exists()

                    if not social_account_already_linked:
                        logger.info(
                            f"Social account for {sociallogin.account.provider} (UID: {sociallogin.account.uid}) NOT yet connected to existing user {existing_user.email}. Attempting to connect.")
                        sociallogin.connect(request, existing_user)
                        sociallogin.user = existing_user
                        logger.info(f"Social account connected to existing user {existing_user.email}.")

                        if SocialAccount.objects.filter(user=existing_user, provider=sociallogin.account.provider,
                                                        uid=sociallogin.account.uid).exists():
                            logger.info(
                                f"VERIFICATION: SocialAccount record for {sociallogin.account.provider} (UID: {sociallogin.account.uid}) NOW EXISTS for user {existing_user.email}.")
                        else:
                            logger.error(
                                f"VERIFICATION ERROR: SocialAccount record for {sociallogin.account.provider} (UID: {sociallogin.account.uid}) NOT found AFTER connect for user {existing_user.email}!")

                        if EmailAddress.objects.filter(user=existing_user, email__iexact=email).exists():
                            logger.info(
                                f"VERIFICATION: EmailAddress record for {email} NOW EXISTS for user {existing_user.email}.")
                        else:
                            logger.error(
                                f"VERIFICATION ERROR: EmailAddress record for {email} NOT found AFTER connect for user {existing_user.email}!")
                    else:
                        logger.info(
                            f"Social account for {sociallogin.account.provider} (UID: {sociallogin.account.uid}) ALREADY LINKED to user {existing_user.email}. Proceeding normally.")
                        sociallogin.user = existing_user

                        if not email_address_already_linked:
                            logger.warning(
                                f"EmailAddress for {email} missing for existing user {existing_user.email} even though social account is linked. This should not happen with ACCOUNT_UNIQUE_EMAIL=True. Attempting to add it.")
                            EmailAddress.objects.create(
                                user=existing_user,
                                email=email,
                                primary=True,
                                verified=True
                            )
                            logger.info(
                                f"EmailAddress for {email} manually created for existing user {existing_user.email}.")

            except User.DoesNotExist:
                logger.info(f"No existing user found for email {email}. Allauth will proceed with new user signup.")
                pass
            except Exception as e:
                logger.error(f"Critical error during pre_social_login custom logic for email {email}: {e}",
                             exc_info=True)

        super().pre_social_login(request, sociallogin)

    def save_user(self, request, sociallogin, form=None):
        """
        Called to create or update a user.
        This method is overridden to generate and set a password, store TemporaryPassword,
        and send a welcome HTML email upon initial registration via Google.
        """
        logger.info(f"save_user called for {sociallogin.account.provider} for user email {sociallogin.user.email}")

        # Determine if the user had a usable password before super().save_user
        # This accurately tells us if this is a *new* social user who needs a password generated
        user_had_no_usable_password_initially = not sociallogin.user.has_usable_password()

        user = super().save_user(request, sociallogin, form)

        # user_was_created_by_social_login is True if the user initially had no usable password
        # and now we're about to set one (or already set one in this flow).
        # This flag determines if a welcome email with a temporary password should be sent.
        user_was_created_by_social_login = user_had_no_usable_password_initially

        logger.info(
            f"After super().save_user: User PK: {user.pk}, Email: {user.email}, Password set: {user.has_usable_password()}")

        if SocialAccount.objects.filter(user=user, provider=sociallogin.account.provider,
                                        uid=sociallogin.account.uid).exists():
            logger.info(
                f"VERIFICATION (save_user): SocialAccount record for {sociallogin.account.provider} (UID: {sociallogin.account.uid}) found for user {user.email}.")
        else:
            logger.error(
                f"VERIFICATION ERROR (save_user): SocialAccount record for {sociallogin.account.provider} (UID: {sociallogin.account.uid}) NOT found after super().save_user for user {user.email}!")

        if EmailAddress.objects.filter(user=user, email__iexact=user.email).exists():
            logger.info(f"VERIFICATION (save_user): EmailAddress record for {user.email} found for user {user.email}.")
        else:
            logger.error(
                f"VERIFICATION ERROR (save_user): EmailAddress record for {user.email} NOT found after super().save_user for user {user.email}!")

        raw_password = None
        # Only generate a new password if the user didn't have one initially
        # and (importantly) still doesn't have one after super().save_user
        if user_had_no_usable_password_initially and not user.has_usable_password():
            raw_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
            logger.info(
                f"Setting new random password for user {user.email} in save_user. (User had no usable password originally and still doesn't)")
            user.set_password(raw_password)
            user.save()

            temp_pass_obj, created_temp_pass = TemporaryPassword.objects.update_or_create(
                user=user,
                defaults={'raw_password': raw_password}
            )
            if created_temp_pass:
                logger.info(f"TemporaryPassword record created for user {user.email}.")
            else:
                logger.info(f"TemporaryPassword record updated for user {user.email}.")
        elif user.has_usable_password():  # If user has a usable password (either pre-existing or set by allauth)
            try:
                temp_pass_obj = TemporaryPassword.objects.get(user=user)
                raw_password = temp_pass_obj.raw_password
            except TemporaryPassword.DoesNotExist:
                logger.warning(
                    f"User {user.email} has a usable password but no TemporaryPassword record. Skipping raw_password retrieval for email.")
                pass

        # --- Logic for sending a welcome email ---
        logger.debug(
            f"Attempting to send email: user_was_created_by_social_login={user_was_created_by_social_login}, raw_password_exists={bool(raw_password)}")

        # Send email only if the user was truly just created by this social login process
        # and we have a raw_password to send.
        if user_was_created_by_social_login and raw_password:
            subject = 'Ласкаво просимо до Wow Service Portal!'
            template_name = 'main/email_template.html'  # Шлях до вашого HTML-шаблону

            website_link = 'https://wowserviceportal.pp.ua'

            context = {
                'user': user,
                'user_name': user.first_name or user.email,
                'user_email': user.email,
                'user_password': raw_password,
                'website_link': website_link,
                'year': timezone.now().year,
            }

            html_message = render_to_string(template_name, context)
            plain_message = f"""Ласкаво просимо до FastSaleService, {user.first_name or user.email}!

Ваші дані для входу:
Логін (Email): {user.email}
Пароль: {raw_password}

Telegram_bot: http://t.me/MNLalertbot
Перейти на сайт FastSaleService: {website_link}

Після завершення реєстраційні дані будуть видалені з сервісу і залишаться тільки на вашій поштовій скринці.

З повагою,
Команда FastSaleService
{website_link}
"""
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [user.email]

            try:
                send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message,
                          fail_silently=False)
                logger.info(f"Вітальний лист успішно відправлено на {user.email}.")
            except Exception as e:
                logger.error(f"Помилка при відправці вітального листа на {user.email}: {e}", exc_info=True)
        else:
            logger.info(
                f"Email not sent: user_was_created_by_social_login={user_was_created_by_social_login}, raw_password_exists={bool(raw_password)}. Conditions not met.")

        return user
