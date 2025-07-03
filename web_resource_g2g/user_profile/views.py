from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from main import crud as main_crud
from main.utils.logger_config import logger
from user_profile.forms import WithdrawalRequestForm
from user_profile.models import WithdrawalRequest # Імпортуємо модель WithdrawalRequest

def profile_main_page(request):

    user_id = request.user.id
    telegram_status = main_crud.check_exist_telegram_id(user_id)

    # Fetch the latest withdrawal request for the current user
    withdrawal_request_obj = None
    withdrawal_account_info = "Не вказано" # Default value

    if request.user.is_authenticated:
        try:
            withdrawal_request_obj = WithdrawalRequest.objects.filter(user=request.user).order_by('-created_at').first()
            if withdrawal_request_obj and withdrawal_request_obj.payment_details:
                # Safely get account_info from JSONField
                withdrawal_account_info = withdrawal_request_obj.payment_details.get('account_info', 'Не вказано')
        except Exception as e:
            logger.error(f"Помилка при отриманні запиту на виведення для користувача {request.user.id}: {e}")
            messages.error(request, "Виникла помилка при завантаженні інформації про виплати.")


    # Отримання балансу користувача
    user_balance_amount = "0.00"
    if request.user.is_authenticated:
        try:
            user_balance_amount = main_crud.get_balance(request.user.id)
        except AttributeError:
            user_balance_amount = f"Продавця не додано. Зверніться до адміністратора"
        except Exception as e:
            logger.error(f"Помилка при отриманні балансу користувача {request.user.id}: {e}")
            user_balance_amount = "Помилка балансу"

    scheduled_day = getattr(withdrawal_request_obj.scheduled_withdrawal_date, "day", None)
    is_fixed_day = scheduled_day in [15, 30] if scheduled_day else False

    context = {
        'telegram_status': telegram_status,
        'withdrawal_info': withdrawal_request_obj, # Pass the object to the template
        'user_balance': user_balance_amount,
        'is_fixed_day': is_fixed_day,
    }
    return render(request, 'user_profile/profile_main_page.html',
                  context=context)

def rules(request):
    return render(request, 'user_profile/rules.html')


@login_required
def withdraw_page(request):
    # withdrawal_info = user_profile_crud.get_withdrawal_user_info(request.user.id) # Цей рядок більше не потрібен тут

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
                user_balance_amount = main_crud.get_balance(request.user.id)
            except AttributeError:
                messages.error(request, "Помилка отримання балансу. Зверніться до адміністратора.")
                context = {'form': form}
                return render(request, 'user_profile/withdraw_page.html', context)
            except Exception as e:
                logger.error(f"Помилка при отриманні балансу користувача {request.user.id}: {e}")
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
        # 'withdrawal_info': withdrawal_info # Цей рядок більше не потрібен тут
    }
    return render(request, 'user_profile/withdraw_page.html', context)

def deposit_page(request):
    return render(request, 'user_profile/deposit_page.html')
def create_order_instruction(request):
    return render(request, 'user_profile/create_order_instruction.html')
