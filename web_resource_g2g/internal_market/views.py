import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from main.utils.logger_config import logger
from internal_market import crud as internal_market_crud
from main import crud as main_crud
from django.http import JsonResponse


@login_required(login_url='users:login')
def main_page(request):
    user_id = request.user.id
    password_confirmed = main_crud.password_confirmed_status(user_id)

    if not password_confirmed:
        bool_exist_username = main_crud.check_exist_username(user_id)

        e_mail, password = main_crud.get_email_password(user_id)

        return render(request, 'users/continue_registration.html', context={"e-mail": e_mail,
                                                                            'temp_password': password,
                                                                            'exist_username': bool_exist_username})
    lots_for_sale = internal_market_crud.get_lots_for_sale(request.user.id)
    logger.info(f"lots_for_sale__{lots_for_sale}")
    return render(request, 'internal_market/internal_market_main.html',
                  context={"lots_for_sale": lots_for_sale})


def create_order_from_form(request):
    user_id = request.user.id
    internal_order_data = json.loads(request.body)
    balance = main_crud.get_balance(user_id)
    permission_for_negative_balance = internal_market_crud.get_permission_for_negative_balance(user_id)
    total_amount = float(internal_order_data.get('total_amount', 0))

    logger.info(f"user_id__{user_id}, balance__{balance},"
                f" total_amount__{total_amount},"
                f" permission_for_negative_balance__{permission_for_negative_balance},"
                f"type_permission_for_negative_balance__{type(permission_for_negative_balance)}")

    # Check if balance is sufficient or negative balance is allowed
    if balance >= total_amount or permission_for_negative_balance:
        response = internal_market_crud.create_order(user_id, internal_order_data)
        return JsonResponse(response)
    else:
        return JsonResponse({
            'success': False,
            'message': 'Сума замовлення перевищує поточний баланс.'
                       ' За дозволом для цієї операції зверніться до адміністрації'
        }, status=400)

