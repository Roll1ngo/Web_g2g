from django.shortcuts import render
from main import crud as main_crud

def profile_main_page(request):
    user_id = request.user.id
    telegram_status = main_crud.check_exist_telegram_id(user_id)
    context = {'telegram_status': telegram_status}
    return render(request, 'user_profile/profile_main_page.html',
                  context=context)

def rules(request):
    return render(request, 'user_profile/rules.html')

def withdraw_page(request):
    return render(request, 'user_profile/withdraw_page.html')

def deposit_page(request):
    return render(request, 'user_profile/deposit_page.html')