import json
import os
import re
from dotenv import load_dotenv


from django import forms
from django.contrib.auth import authenticate, update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.urls import reverse
from django.views import View
from django.contrib.auth.views import LoginView
from django.contrib.auth import logout
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView

from main.utils.logger_config import logger
from .forms import RegisterForm
from main import crud as main_crud

load_dotenv()
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')



def profile(request):
    return render(request, 'users/profile.html')


class RegisterView(View):
    template_name = 'users/register.html'
    form_class = RegisterForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(to='/')
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(request, self.template_name, context={'form': self.form_class})

    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data['username']
            messages.success(request, f'Greetings {username}, your account has been successfully registered')
            return redirect(to='users:login')
        return render(request, self.template_name, context={'form': form})


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))

    error_messages = {
        'invalid_login': "Invalid username or password. Please try again.",
        'inactive': "This account is inactive.",
    }

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            self.user_cache = authenticate(username=username, password=password)
            if self.user_cache is None:
                raise forms.ValidationError(self.error_messages['invalid_login'], code='invalid_login')
            elif not self.user_cache.is_active:
                raise forms.ValidationError(self.error_messages['inactive'], code='inactive')

        return self.cleaned_data


class CustomLoginView(LoginView):
    template_name = 'users/login.html'
    form_class = LoginForm

    def get_success_url(self):
        return '/'


def change_password(request):
    template_name = 'users/change_password.html'
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password has been successfully changed!')
            return redirect('/accounts/profile/')
        else:
            messages.error(request, 'The old or new password is not valid.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, template_name, {'form': form})


def logout_view(request):
    logout(request)
    return redirect(reverse('users:login'))


class CustomPasswordResetView(PasswordResetView):
    template_name = 'users/reset_password.html'
    email_template_name = 'password_reset_email.html'
    subject_template_name = 'password_reset_subject.txt'
    success_url = 'reset_password_sent'


class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'users/password_reset_done.html'


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'users/password_reset_confirm.html'


class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'users/password_reset_complete.html'


def index(request):
    return render(request, 'users/index.html')

@login_required
def complete_registration(request):
    logger.info("complete_registration")
    user_id = request.user.id
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            username = data.get('username')

            # Перевірка наявності та валідності username
            if not username:
                return JsonResponse({'error': 'Ім\'я користувача є обов\'язковим.'}, status=400)

            # Валідація username: лише букви та цифри
            if not re.fullmatch(r'^[a-zA-Z0-9]+$', username):
                return JsonResponse({'error': 'Ім\'я користувача може містити лише букви та цифри.'}, status=400)

            # Перевірка на унікальність username
            bool_exist_username = main_crud.check_exist_username(user_id,username)
            if bool_exist_username:
                return JsonResponse({'error': 'Користувач з таким ім\'ям вже існує.'}, status=400)

           # Перевіряємо чи підключений telegram профіль
            bool_exist_telegram_id = main_crud.check_exist_telegram_id(user_id)
            if not bool_exist_telegram_id:
                return JsonResponse({'error': 'Для завершення реєстрації підключіть будь ласка Telegram профіль.'},
                                    status=400)
            # Ставимо позначку про завершення реєстрації
            main_crud.confirm_registration_and_delete_raw_password(user_id)

            return JsonResponse({
                'message': 'Реєстрацію успішно завершено!',
                'redirect_url': '/'  # Куди перенаправляти користувача після завершення
            }, status=200)

        except json.JSONDecodeError:
            logger.error("Недійсний JSON у тілі запиту complete_registration.")
            return JsonResponse({'error': 'Недійсний формат запиту.'}, status=400)
        except Exception as e:
            logger.exception("Помилка на бекенді під час завершення реєстрації.")
            return JsonResponse({'error': f'Виникла внутрішня помилка сервера: {e}'}, status=500)
    else:
        # Для GET-запитів рендеримо сторінку завершення реєстрації
        # Це також потрібно, якщо користувач потрапляє на цю сторінку без POST-запиту
        return render(request, 'registration_completion_page.html')

# def google_auth(request):
#     """
#     Обробляє POST-запити від Google Identity Services (GSI),
#     валідує отриманий ID-токен та витягує інформацію про користувача.
#     """
#     logger.info("Отримано запит до google_auth")
#
#     if request.method == 'POST':
#         try:
#             # Парсимо тіло запиту як JSON
#             data = json.loads(request.body)
#             token = data.get('id_token')
#
#             if not token:
#                 logger.error("Відсутній 'id_token' у тілі запиту.")
#                 return JsonResponse({'error': 'ID token missing'}, status=400)
#
#             CLIENT_ID = "689690442957-bbp48a2h58nrtud7k3s70rlu39h829k5.apps.googleusercontent.com"
#
#             try:
#                 # Валідуємо токен за допомогою Google.
#                 # Аудиторія (audience) має відповідати вашому Client ID.
#                 # idinfo міститиме перевірені дані токена.
#                 idinfo = id_token.verify_oauth2_token(token, google_requests.Request(), CLIENT_ID)
#
#                 # Отримуємо email та іншу інформацію з валідованого токена
#                 email = idinfo['email']
#                 user_id = idinfo['sub'] # Унікальний ID користувача Google
#                 user_name = idinfo.get('name', 'Невідоме ім\'я') # Ім'я користувача (якщо є)
#                 profile_picture = idinfo.get('picture', None) # URL фото профілю (якщо є)
#
#                 logger.info(f"Успішно валідовано токен. Email: {email}, User ID: {user_id}, Name: {user_name}")
#
#                 # --- Тут починається логіка реєстрації/входу користувача Django ---
#                 # Приклад:
#                 # try:
#                 #     user = User.objects.get(email=email)
#                 # except User.DoesNotExist:
#                 #     # Якщо користувача з таким email немає, створіть нового
#                 #     # Зауважте: для social login пароль може бути випадковим або None
#                 #     user = User.objects.create_user(username=email, email=email)
#                 #     # Можете також зберегти user_id або profile_picture
#                 #
#                 # # Виконати вхід користувача в Django
#                 # login(request, user)
#                 # logger.info(f"Користувач {email} успішно увійшов в Django.")
#
#                 # Після успішного входу/реєстрації, поверніть відповідь
#                 # та URL для перенаправлення на сторінку, куди користувач має потрапити.
#                 logger.info(f"Користувач {email} успішно увійшов на сервіс")
#                 return JsonResponse({'status': 'success', 'message': 'Токен успішно валідовано, email залоговано.', 'redirect_url': '/'})
#
#             except ValueError as e:
#                 # Помилки валідації токена (наприклад, недійсний підпис, закінчився термін дії, неправильний Client ID)
#                 logger.error(f"Помилка валідації токена: {e}")
#                 return JsonResponse({'error': f'Invalid token: {e}'}, status=400)
#             except Exception as e:
#                 # Інші непередбачені помилки під час обробки токена
#                 logger.exception("Невідома помилка під час обробки Google токена.")
#                 return JsonResponse({'error': f'An unexpected error occurred during token processing: {e}'}, status=500)
#
#         except json.JSONDecodeError:
#             # Помилка, якщо тіло запиту не є коректним JSON
#             logger.error("Недійсний JSON у тілі запиту.")
#             return JsonResponse({'error': 'Invalid JSON in request body'}, status=400)
#         except Exception as e:
#             # Загальна помилка обробки запиту
#             logger.exception("Загальна помилка обробки запиту.")
#             return JsonResponse({'error': f'Server error: {e}'}, status=500)
#     else:
#         # Обробка запитів, відмінних від POST
#         logger.warning(f"Отримано {request.method} запит до google_auth, очікується POST.")
#         return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)



