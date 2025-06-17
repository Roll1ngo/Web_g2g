from django.core.mail import send_mail
from django.conf import settings

from main.utils.logger_config import logger

from_email=settings.DEFAULT_FROM_EMAIL

def send_massage_to_email(message, email, subject):
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],  # Список адрес одержувачe,  # Адреса одержувача
        fail_silently=False,
    )
if "name" == "__main__":
    message_test =f"login: test_login, password: test_password ,telegram_bot: http:t.me/MNLalertbot"
    send_massage_to_email(message_test, "rolmf85@gmail.com")