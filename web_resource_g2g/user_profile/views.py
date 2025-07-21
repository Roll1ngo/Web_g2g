import calendar
import datetime
import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils import timezone
from django.conf import settings

from main import crud as main_crud
from archive_payments import crud as archive_payments_crud
from main.utils.tg_bot_run import send_messages_sync
from main.utils.logger_config import logger
from user_profile.forms import WithdrawalRequestForm
from user_profile.models import WithdrawalRequest # Імпортуємо модель WithdrawalRequest

def profile_main_page(request):
    user_id = request.user.id
    ref_url = f"{settings.HOST}/login/?ref={request.user.username}"

    # Припускаємо, що main_crud.check_exist_telegram_id існує
    telegram_status = main_crud.check_exist_telegram_id(user_id)
    logger.info(f"Telegram status for user {user_id}: {telegram_status}")

    withdrawal_request_obj = None
    withdrawal_account_info = "Не вказано" # Значення за замовчуванням
    expected_completion_date = None # Ініціалізуємо для термінового виводу

    if request.user.is_authenticated:
        try:
            # Отримуємо останній запит на виведення для поточного користувача
            withdrawal_request_obj = WithdrawalRequest.objects.filter(user=request.user).order_by('-created_at').first()
            if withdrawal_request_obj and withdrawal_request_obj.payment_details:
                # Безпечно отримуємо account_info з JSONField
                withdrawal_account_info = withdrawal_request_obj.payment_details.get('account_info', 'Не вказано')

            # Розрахунок очікуваної дати завершення для термінового виводу
            if withdrawal_request_obj and withdrawal_request_obj.withdraw_type == 'custom' and withdrawal_request_obj.status == 'pending':
                if withdrawal_request_obj.created_at:
                    expected_completion_date = withdrawal_request_obj.created_at + datetime.timedelta(days=1)

        except Exception as e:
            logger.error(f"Помилка при отриманні запиту на виведення для користувача {request.user.id}: {e}")
            messages.error(request, "Виникла помилка при завантаженні інформації про виплати.")

    # Отримання балансу користувача
    user_balance_amount = "0.00"
    if request.user.is_authenticated:
        try:
            # Припускаємо, що main_crud.get_balance існує
            user_balance_amount = main_crud.get_balance(request.user.id)
        except AttributeError:
            user_balance_amount = "Продавця не додано. Зверніться до адміністратора"
        except Exception as e:
            logger.error(f"Помилка при отриманні балансу користувача {request.user.id}: {e}")
            user_balance_amount = "Помилка балансу "

    current_date = timezone.now().date()
    next_payment_date_display = "Не налаштовано"
    is_button_disabled = False

    if withdrawal_request_obj:
        # Визначаємо, чи повинна бути кнопка вимкнена
        # Кнопка неактивна 15 та 30 числа кожного місяця
        is_fixed_day_today = current_date.day in [15, 30]
        # Кнопка неактивна в разі замовлення термінового виведення коштів ('custom')
        is_custom_pending = (
            withdrawal_request_obj.withdraw_type == 'custom' and
            withdrawal_request_obj.status == 'pending'
        )
        is_button_disabled = is_fixed_day_today or is_custom_pending

        # Визначаємо дату наступної виплати для відображення
        if withdrawal_request_obj.withdraw_type == 'fixed_15_30':
            scheduled_date = withdrawal_request_obj.scheduled_withdrawal_date
            if scheduled_date:
                # Якщо запланована дата в минулому, перераховуємо наступну
                if scheduled_date < current_date:
                    if current_date.day < 15:
                        next_fixed_date = current_date.replace(day=15)
                    elif current_date.day < 30:
                        last_day_of_current_month = calendar.monthrange(current_date.year, current_date.month)[1]
                        next_fixed_date = datetime.date(current_date.year, current_date.month, min(30, last_day_of_current_month))
                    else: # current_date.day >= 30, переходимо до 15-го числа наступного місяця
                        year = current_date.year
                        month = current_date.month + 1
                        if month > 12:
                            month = 1
                            year += 1
                        next_fixed_date = datetime.date(year, month, 15)
                    next_payment_date_display = next_fixed_date.strftime("%d.%m.%Y")
                else:
                    next_payment_date_display = scheduled_date.strftime("%d.%m.%Y")
            else:
                next_payment_date_display = "Не встановлено" # Мало б не траплятися для fixed_15_30
        elif withdrawal_request_obj.withdraw_type == 'custom':
            next_payment_date_display = "Протягом 24 годин"
        elif withdrawal_request_obj.withdraw_type == 'do_not_withdraw':
            next_payment_date_display = "Виплати не здійснюються"
    else:
        # Якщо запитів на виведення немає, кнопка не вимкнена
        is_button_disabled = False
        next_payment_date_display = "Налаштуйте виплати" # Підказка користувачу

    context = {
        'telegram_status': telegram_status,
        'withdrawal_info': withdrawal_request_obj, # Передаємо об'єкт, а не словник
        'user_balance': user_balance_amount,
        'is_button_disabled': is_button_disabled, # Нова змінна контексту для кнопки
        'next_payment_date_display': next_payment_date_display, # Нова змінна контексту для дати
        'expected_completion_date': expected_completion_date, # Нова змінна для термінового виводу
        'ref_url': ref_url
    }
    logger.info(f"withdrawal_info__{withdrawal_request_obj}, is_button_disabled__{is_button_disabled}, next_payment_date_display__{next_payment_date_display}, expected_completion_date__{expected_completion_date}")
    return render(request, 'user_profile/profile_main_page.html', context)

def rules(request):
    return render(request, 'user_profile/rules.html')


@login_required
def withdraw_page(request):
    user_id = request.user.id

    if request.method == 'POST':
        # Спробуємо отримати існуючий запит на виведення для поточного користувача
        try:
            existing_withdrawal_request = WithdrawalRequest.objects.get(user=request.user)
            form = WithdrawalRequestForm(request.POST, instance=existing_withdrawal_request)
        except WithdrawalRequest.DoesNotExist:
            # Якщо запиту не існує, створюємо нову форму
            form = WithdrawalRequestForm(request.POST)

        if form.is_valid():
            withdrawal_request = form.save(commit=False)
            withdrawal_request.user = request.user  # Прив'язуємо поточного користувача

            # Логіка перевірки балансу користувача
            user_balance_amount = 0
            try:
                # Припускаємо, що get_balance повертає числове значення
                user_balance_amount = main_crud.get_balance(user_id)
            except AttributeError:
                messages.error(request, "Помилка отримання балансу. Зверніться до адміністратора.")
                context = {'form': form}
                return render(request, 'user_profile/withdraw_page.html', context)
            except Exception as e:
                logger.error(f"Помилка при отриманні балансу користувача {user_id}: {e}")
                messages.error(request, "Виникла помилка при перевірці балансу. Спробуйте ще раз.")
                context = {'form': form}
                return render(request, 'user_profile/withdraw_page.html', context)

            # Перевіряємо баланс, тільки якщо сума виведення не є None (тобто не 'do_not_withdraw')
            if withdrawal_request.amount is not None:
                if withdrawal_request.amount > user_balance_amount:
                    messages.error(request, "Недостатньо коштів на балансі. Будь ласка, поповніть рахунок.")
                    # Повертаємо ту саму форму з помилкою
                    context = {'form': form}
                    return render(request, 'user_profile/withdraw_page.html', context)

            withdrawal_request.save()  # Тепер зберігаємо об'єкт у базу даних
            logger.info(
                f"Запит на виведення успішно збережено/оновлено: {withdrawal_request.pk} від {withdrawal_request.user.username} на {withdrawal_request.amount if withdrawal_request.amount else 'N/A'}$ ({withdrawal_request.status})"
            )
            if withdrawal_request.withdraw_type == 'custom':
               # Додаємо запис у таблицю резервування
               archive_payments_crud.create_withdrawal_reserver_record(request.user, withdrawal_request)

               send_messages_sync(settings.VLAD_TG,
                                  "",
                                   message=f'Запит на виведення коштів від {withdrawal_request.user.username}'
                                           f' на {withdrawal_request.amount if withdrawal_request.amount else "N/A"}$')



            messages.success(request, 'Ваш запит на виведення коштів успішно надіслано!')
            return redirect('user_profile:profile_main_page')
        else:
            logger.error(f"Помилки валідації форми виведення: {form.errors.as_json()}")
            messages.error(request, 'Будь ласка, виправте помилки у формі.')
            context = {'form': form}
            return render(request, 'user_profile/withdraw_page.html', context)
    else:
        # При GET-запиті: спробуємо завантажити існуючий запит або створити нову форму
        try:
            existing_withdrawal_request = WithdrawalRequest.objects.get(user=request.user)
            form = WithdrawalRequestForm(instance=existing_withdrawal_request)
        except WithdrawalRequest.DoesNotExist:
            form = WithdrawalRequestForm()
    context = {
        'form': form,
    }
    return render(request, 'user_profile/withdraw_page.html', context)


def invite_friend(request):
    if request.method == 'POST':

        try:
            data = json.loads(request.body)
            friend_email = data.get('email')
            ref_url = f"{settings.HOST}/login/?ref={request.user.username}"
            inviter_user = request.user
            logger.info(f"email__{friend_email},"
                        f" ref_url__{ref_url},"
                        f" inviter_user__{inviter_user}")


            if not friend_email:
                return JsonResponse({'message': 'Email не може бути порожнім.'}, status=400)

            try:
                validate_email(friend_email)
            except ValidationError:
                return JsonResponse({'message': 'Будь ласка, введіть дійсну адресу електронної пошти.'}, status=400)

            if not inviter_user.is_authenticated:
                return JsonResponse({'message': 'Ви повинні бути авторизованим, щоб запрошувати друзів.'}, status=401)

            # Відправка повідомлення на електронну адресу

            context = {
                'inviter_name': inviter_user.username,
                'inviter_email': inviter_user.email,
                'registration_link': ref_url,
                # Замініть на реальне посилання для реєстрації
                'website_link': ref_url,  # Замініть на реальне посилання на ваш сайт
                'year': timezone.now().year,
            }
            subject = 'Ласкаво просимо до Wow Service Portal!'
            template_name = 'user_profile/invite_friend.html'  # Шлях до вашого HTML-шаблону
            html_message = render_to_string(template_name, context)
            plain_message = (
                f"Привіт!\n\n"
                f"Ваш друг, {context['inviter_name']} ({context['inviter_email']}), "
                f"запрошує вас приєднатися до Wow Service Portal.\n\n"
                f"Зареєструйтесь за посиланням: {context['registration_link']}\n\n"
                f"З повагою,\n"
                f"Команда Wow Service Portal\n"
            )
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [friend_email]

            try:
                send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message,
                          fail_silently=False)
                logger.info(f"Запрошення успішно відправлено на {friend_email} від {inviter_user.email}.")
                return JsonResponse({'message': 'Запрошення успішно надіслано!'})
            except Exception as e:
                logger.error(f"Помилка при відправці запрошення на {friend_email} від {inviter_user.email}: {e}",
                             exc_info=True)
                return JsonResponse({'message': 'Помилка при надсиланні запрошення. Спробуйте ще раз.'}, status=500)

        except json.JSONDecodeError:
            return JsonResponse({'message': 'Недійсний JSON-запит.'}, status=400)
        except Exception as e:
            logger.error(f"Неочікувана помилка у invite_friend_api: {e}", exc_info=True)
            return JsonResponse({'message': f'Внутрішня помилка сервера: {str(e)}'}, status=500)
    return JsonResponse({'message': 'Дозволено лише POST-запити.'}, status=405)



def deposit_page(request):
    return render(request, 'user_profile/deposit_page.html')

def create_order_instruction(request):
    return render(request, 'user_profile/create_order_instruction.html')

def security_and_privacy_policy(request):
    return render(request, 'user_profile/security_and_privacy_policy.html')
