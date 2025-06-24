            subject = 'Ласкаво просимо до Wow Service Portal!'
            template_name = 'main/welcome_social_login.html'  # Шлях до вашого HTML-шаблону

            website_link = 'https://wowserviceportal.pp.ua'

            context = {
                'user': user,
                'user_name': user.first_name or user.email,
                'user_email': user.email,
                'user_password': raw_password,
                'website_link': website_link,
                'background_image_url': background_image_url,
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