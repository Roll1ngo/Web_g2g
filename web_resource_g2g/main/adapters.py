# Імпорти
import secrets  # Для генерації випадкових даних (паролів)
import string   # Для роботи з рядковими константами (літери, цифри)

# Імпорти Django
from django.contrib.auth.hashers import make_password  # Для хешування паролів (хоча тут використовується set_password)
from django.contrib.auth import get_user_model           # Найкращий спосіб отримати модель User
from django.db import transaction                          # Для управління атомарними транзакціями бази даних
from django.core.mail import send_mail                   # Для відправки електронних листів
from django.template.loader import render_to_string      # Для рендерингу HTML-шаблонів листів
from django.conf import settings                         # Доступ до налаштувань Django (наприклад, DEFAULT_FROM_EMAIL)
from django.utils import timezone                        # Для роботи з часом, що враховує часовий пояс

# Імпорти Django-allauth
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter  # Базовий адаптер для розширення логіки соціального входу
from allauth.account.models import EmailAddress                        # Модель для зберігання електронних адрес користувачів
from allauth.socialaccount.models import SocialAccount                 # Модель для зберігання інформації про соціальний акаунт

# Імпорти власного проекту
from main.utils.logger_config import logger               # Наш кастомний логер для запису подій
from main.models import TemporaryPassword                 # Модель для тимчасового зберігання пароля

# Отримання моделі користувача
User = get_user_model()


class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Кастомний адаптер для Django-allauth.
    Перевизначає стандартну поведінку для обробки соціального входу.
    """

    def pre_social_login(self, request, sociallogin):
        """
        Метод, що викликається після успішної автентифікації через
        соціальну мережу, але до того, як користувач буде створений
        або підключений в системі.

        Ця логіка призначена для запобігання дублікатів. Вона перевіряє,
        чи існує вже користувач з такою ж електронною поштою,
        і якщо так, намагається прив'язати соціальний акаунт до
        існуючого користувача.
        """
        # Логування початку процесу
        logger.info(f"pre_social_login called for {sociallogin.user.email} (Provider: {sociallogin.account.provider})")
        logger.info(f"Sociallogin initial user PK: {sociallogin.user.pk}, Email: {sociallogin.user.email}")
        logger.info(f"Socialaccount extra_data: {sociallogin.account.extra_data}")

        # Отримуємо email з даних соціального акаунта
        email = sociallogin.account.extra_data.get('email')

        if email:
            try:
                # Використовуємо атомарну транзакцію, щоб усі операції були
                # виконані разом або жодна з них. Це запобігає станам
                # непослідовності даних.
                with transaction.atomic():
                    # Шукаємо користувача за електронною поштою (без урахування регістру)
                    existing_user = User.objects.get(email__iexact=email)

                    logger.info(f"Found existing user by email: {existing_user.email} (PK: {existing_user.pk})")

                    # Перевіряємо, чи вже прив'язаний цей соціальний акаунт до знайденого користувача
                    social_account_already_linked = SocialAccount.objects.filter(
                        user=existing_user,
                        provider=sociallogin.account.provider,
                        uid=sociallogin.account.uid
                    ).exists()

                    # Перевіряємо, чи вже прив'язана електронна адреса до знайденого користувача
                    email_address_already_linked = EmailAddress.objects.filter(
                        user=existing_user,
                        email__iexact=email
                    ).exists()

                    # Якщо соціальний акаунт ще не прив'язаний
                    if not social_account_already_linked:
                        logger.info(
                            f"Social account for {sociallogin.account.provider} (UID: {sociallogin.account.uid}) NOT yet connected to existing user {existing_user.email}. Attempting to connect.")
                        # Підключаємо соціальний акаунт до існуючого користувача
                        sociallogin.connect(request, existing_user)
                        # Замінюємо тимчасовий об'єкт користувача в sociallogin на існуючий
                        sociallogin.user = existing_user
                        logger.info(f"Social account connected to existing user {existing_user.email}.")

                        # Логи для верифікації, що прив'язка пройшла успішно
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
                        # Якщо акаунт вже прив'язаний, просто встановлюємо користувача в sociallogin
                        logger.info(
                            f"Social account for {sociallogin.account.provider} (UID: {sociallogin.account.uid}) ALREADY LINKED to user {existing_user.email}. Proceeding normally.")
                        sociallogin.user = existing_user

                        # Додаткова перевірка: якщо email-адреса відсутня (хоча не повинна),
                        # створюємо її вручну.
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

            # Якщо користувача з такою поштою не знайдено, Allauth продовжить стандартний процес
            # створення нового користувача.
            except User.DoesNotExist:
                logger.info(f"No existing user found for email {email}. Allauth will proceed with new user signup.")
                pass
            # Обробка інших можливих помилок
            except Exception as e:
                logger.error(f"Critical error during pre_social_login custom logic for email {email}: {e}",
                             exc_info=True)

        # Викликаємо батьківський метод для стандартної логіки Allauth
        super().pre_social_login(request, sociallogin)

    def save_user(self, request, sociallogin, form=None):
        """
        Метод, що викликається для створення або оновлення користувача.
        Цей метод перевизначено для:
        1. Генерації та встановлення пароля для нових користувачів, які
           реєструються через соціальні мережі.
        2. Зберігання цього тимчасового пароля в моделі TemporaryPassword.
        3. Відправлення вітального листа з логіном та паролем.
        """
        logger.info(f"save_user called for {sociallogin.account.provider} for user email {sociallogin.user.email}")

        # Запам'ятовуємо стан, чи мав користувач пароль до виклику батьківського методу.
        # Це допомагає визначити, чи був користувач щойно створений.
        user_had_no_usable_password_initially = not sociallogin.user.has_usable_password()

        # Викликаємо базовий метод Allauth для створення/оновлення користувача.
        user = super().save_user(request, sociallogin, form)

        # Змінна-прапор, яка вказує, чи був користувач створений саме цим процесом
        user_was_created_by_social_login = user_had_no_usable_password_initially

        logger.info(
            f"After super().save_user: User PK: {user.pk}, Email: {user.email}, Password set: {user.has_usable_password()}")

        # Логи для верифікації, що SocialAccount та EmailAddress були створені/прив'язані
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

        # Якщо користувач був щойно створений і ще не має пароля
        if user_had_no_usable_password_initially and not user.has_usable_password():
            # Генеруємо випадковий пароль
            raw_password = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(12))
            logger.info(
                f"Setting new random password for user {user.email} in save_user. (User had no usable password originally and still doesn't)")
            # Встановлюємо хешований пароль для користувача
            user.set_password(raw_password)
            user.save()

            # Зберігаємо "сирий" (нехешований) пароль у TemporaryPassword
            # для подальшої відправки в листі.
            temp_pass_obj, created_temp_pass = TemporaryPassword.objects.update_or_create(
                user=user,
                defaults={'raw_password': raw_password}
            )
            if created_temp_pass:
                logger.info(f"TemporaryPassword record created for user {user.email}.")
            else:
                logger.info(f"TemporaryPassword record updated for user {user.email}.")
        elif user.has_usable_password():  # Якщо у користувача вже є пароль (наприклад, це повторний вхід)
            try:
                # Намагаємося отримати раніше збережений тимчасовий пароль, якщо він є
                temp_pass_obj = TemporaryPassword.objects.get(user=user)
                raw_password = temp_pass_obj.raw_password
            except TemporaryPassword.DoesNotExist:
                logger.warning(
                    f"User {user.email} has a usable password but no TemporaryPassword record. Skipping raw_password retrieval for email.")
                pass

        # --- Логіка відправки вітального листа ---
        logger.debug(
            f"Attempting to send email: user_was_created_by_social_login={user_was_created_by_social_login}, raw_password_exists={bool(raw_password)}")

        # Лист відправляється тільки якщо:
        # 1. Користувач щойно створений.
        # 2. Ми успішно згенерували для нього пароль.
        if user_was_created_by_social_login and raw_password:
            subject = 'Ласкаво просимо до Wow Service Portal!'
            template_name = 'main/email_template.html'  # Шлях до HTML-шаблону листа

            website_link = 'https://wowserviceportal.pp.ua'

            # Контекст для рендерингу шаблону
            context = {
                'user': user,
                'user_name': user.first_name or user.email, # Використовуємо ім'я, якщо є, інакше email
                'user_email': user.email,
                'user_password': raw_password,
                'website_link': website_link,
                'year': timezone.now().year,
            }

            # Рендеринг HTML-версії листа
            html_message = render_to_string(template_name, context)
            # Створення текстової версії листа (для поштових клієнтів, що не підтримують HTML)
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
                # Відправка листа
                send_mail(
                    subject,
                    plain_message,
                    from_email,
                    recipient_list,
                    html_message=html_message,
                    fail_silently=False  # Якщо виникне помилка, буде кинутий виняток
                )
                logger.info(f"Вітальний лист успішно відправлено на {user.email}.")
            except Exception as e:
                logger.error(f"Помилка при відправці вітального листа на {user.email}: {e}", exc_info=True)
        else:
            # Лог, якщо лист не був відправлений, з поясненням причин
            logger.info(
                f"Email not sent: user_was_created_by_social_login={user_was_created_by_social_login}, raw_password_exists={bool(raw_password)}. Conditions not met.")

        return user