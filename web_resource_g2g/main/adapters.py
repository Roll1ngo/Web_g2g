from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth.hashers import make_password
from django.contrib.auth import get_user_model
from django.db import transaction
from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount

from main.utils.logger_config import logger

User = get_user_model()  # Отримуємо поточну модель користувача


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):

    def pre_social_login(self, request, sociallogin):
        """
        Викликається після успішного входу через соціальну мережу,
        але до створення або зв'язування користувача.

        Цей метод перевіряє, чи існує користувач з таким email,
        і якщо так, то намагається зв'язати соціальний акаунт з ним,
        запобігаючи створенню дубліката.
        """
        logger.info(f"pre_social_login called for {sociallogin.user.email} (Provider: {sociallogin.account.provider})")
        logger.info(f"Sociallogin initial user PK: {sociallogin.user.pk}, Email: {sociallogin.user.email}")
        logger.info(f"Socialaccount extra_data: {sociallogin.account.extra_data}")

        # Отримуємо email з даних соціального акаунту
        email = sociallogin.account.extra_data.get('email')

        if email:
            try:
                # Використовуємо транзакцію для безпечного зв'язування
                with transaction.atomic():
                    # Шукаємо існуючого користувача за email
                    existing_user = User.objects.get(email__iexact=email)  # __iexact для регістронезалежного порівняння

                    logger.info(f"Found existing user by email: {existing_user.email} (PK: {existing_user.pk})")

                    # Перевіряємо, чи цей соціальний обліковий запис (з цим провайдером та UID)
                    # вже прив'язаний до існуючого користувача.
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
                        # Якщо соціальний обліковий запис НЕ прив'язаний до існуючого користувача,
                        # то намагаємося його прив'язати.
                        logger.info(
                            f"Social account for {sociallogin.account.provider} (UID: {sociallogin.account.uid}) NOT yet connected to existing user {existing_user.email}. Attempting to connect.")

                        # ВИКЛИКАЄМО connect(), щоб прив'язати соціальний акаунт до існуючого користувача.
                        # Це також відповідає за створення записів SocialAccount та EmailAddress.
                        sociallogin.connect(request, existing_user)

                        # Встановлюємо sociallogin.user на існуючого користувача,
                        # щоб подальші дії allauth (наприклад, save_user) працювали з ним.
                        sociallogin.user = existing_user

                        logger.info(f"Social account connected to existing user {existing_user.email}.")

                        # Логування для верифікації після connect
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
                        # Навіть якщо вже прив'язано, переконаємось, що sociallogin.user вказує на існуючого.
                        sociallogin.user = existing_user

                        # Перевірка EmailAddress, якщо вже прив'язано, але запис відсутній
                        if not email_address_already_linked:
                            logger.warning(
                                f"EmailAddress for {email} missing for existing user {existing_user.email} even though social account is linked. This should not happen with ACCOUNT_UNIQUE_EMAIL=True. Attempting to add it.")
                            EmailAddress.objects.create(
                                user=existing_user,
                                email=email,
                                primary=True,  # Або False, якщо ви дозволяєте кілька
                                verified=True  # Вважаємо верифікованим, якщо Google вже підтвердив
                            )
                            logger.info(
                                f"EmailAddress for {email} manually created for existing user {existing_user.email}.")


            except User.DoesNotExist:
                # Користувача з таким email не знайдено, allauth продовжить процес
                # створення нового користувача, якщо це дозволено налаштуваннями.
                logger.info(f"No existing user found for email {email}. Allauth will proceed with new user signup.")
                pass  # Продовжуємо стандартний потік allauth для реєстрації
            except Exception as e:
                # Логуємо інші неочікувані помилки
                logger.error(f"Critical error during pre_social_login custom logic for email {email}: {e}",
                             exc_info=True)
                # Якщо це критична помилка, ви можете raise її або перенаправити користувача
                # raise # Розкоментуйте, щоб побачити повний трейсбек

        # Завжди викликаємо super().pre_social_login. Це дозволить DefaultSocialAccountAdapter
        # виконати свою базову логіку, яка може включати перевірку наявності акаунта в SocialApp
        # або перенаправлення на сторінку "connect account" (якщо SOCIALACCOUNT_AUTO_SIGNUP=False).
        # Це також важливо, оскільки allauth може мати подальшу внутрішню логіку після цього сигналу.
        super().pre_social_login(request, sociallogin)

    def save_user(self, request, sociallogin, form=None):
        """
        Викликається для створення або оновлення користувача.
        Цей метод перевизначений для генерації та встановлення пароля.
        """
        logger.info(f"save_user called for {sociallogin.account.provider} for user email {sociallogin.user.email}")

        # Викликаємо батьківський метод. Цей super() метод є відповідальним
        # за створення нового User, SocialAccount та EmailAddress,
        # якщо це новий користувач, або за отримання існуючого User.
        user = super().save_user(request, sociallogin, form)

        logger.info(
            f"After super().save_user: User PK: {user.pk}, Email: {user.email}, Password set: {user.has_usable_password()}")

        # Додаткові перевірки після super().save_user (важливо для діагностики)
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

        # Перевіряємо, чи користувач щойно був створений і не має пароля,
        # або якщо його пароль починається з '!' (ознака social-only акаунта).
        # Встановлюємо тимчасовий пароль, якщо він ще не встановлений або непридатний.
        if not user.has_usable_password():  # Це краща перевірка на наявність пароля
            new_password = make_password(None)  # Генеруємо випадковий пароль
            logger.info(f"Setting new random password for user {user.email} in save_user.")
            user.password = new_password
            user.save()  # Зберігаємо користувача з новим паролем

            # Логіка для TemporaryPassword (якщо потрібно)
            # from main.models import TemporaryPassword
            # TemporaryPassword.objects.update_or_create(user=user, defaults={'raw_password': raw_password_here})
        else:
            logger.info(f"User {user.email} already has a usable password. Not setting new password in save_user.")

        return user

