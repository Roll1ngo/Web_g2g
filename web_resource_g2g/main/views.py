import json
import os

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse, HttpResponseNotAllowed, HttpResponse
from django.shortcuts import render, redirect
from . import crud
from .utils.logger_config import logger


def start_page(request):
    if request.method == 'GET':
        user_id = request.user.id
        all_bets = crud.get_main_data_from_table(user_id)
        logger.info(f"all_bets__{all_bets}")

        servers = crud.query_servers()
        games = set(server.game_name for server in servers)
        regions = set(server.region for server in servers)

        grouped_data_db = crud.get_grouped_data(servers)
        grouped_data = json.dumps(grouped_data_db)

        double_add = json.dumps([{'server_name': server['server_name'],
                                  'game_name': server['game_name']} for server in all_bets])

        return render(request, 'main/index.html', context={"bets_list": all_bets,
                                                           'games': games,
                                                           'regions': regions,
                                                           'servers_json': grouped_data,
                                                           'double_add': double_add
                                                           })


def update_table_data(request):
    if request.method == 'POST':
        user_id = request.user.id
        data = json.loads(request.body)
        logger.info(data)
        new_price = crud.update_price_delivery(data, user_id)
        logger.info(new_price)
        return JsonResponse({'success': True, 'new_price': new_price})
    return HttpResponseNotAllowed(['POST'])


def add_server(request):
    if request.method == 'POST':
        add_server_info = json.loads(request.body)

        add_server_info['auth_user_id'] = request.user.id
        logger.info(f"add_server_info__{add_server_info}")
        crud.add_server_to_db(add_server_info)

    return JsonResponse({'success': True})


def handle_option_change(request):
    logger.info("inside handle_option_change")
    payload = json.loads(request.body)
    offer_id = payload["row_id"]
    action = payload["action"]
    logger.info(f'Change option__{action} for__{offer_id},')
    if action == 'delete':
        crud.delete_server_from_list(offer_id)
    else:
        crud.pause_offer(offer_id, action)
    return JsonResponse({'success': True})


def show_order_info(request, server_id):
    user_id = request.user.id

    if server_id == 0:
        server_id = crud.get_server_id(user_id)
        if server_id == 'Замовлення не знайдено':
            return render(request, 'main/not_active_orders.html')
        logger.info(f"{server_id}")

    order_info = crud.get_order_info(server_id, user_id)
    if order_info is None:
        return render(request, 'main/not_found_order.html')

    sold_order_number = order_info.sold_order_number
    price_unit = order_info.earned_without_admins_commission / order_info.quantity
    return render(request, 'main/show_order_info.html', context={"order": order_info,
                                                                 "sold_order_number": sold_order_number,
                                                                 "price_unit": round(price_unit, 2)})


def upload_video(request, sold_order_number):
    logger.info(f"sold_order_number__{sold_order_number}")
    user = request.user.id

    if request.method == 'POST':
        if 'video' in request.FILES:
            video_file = request.FILES['video']
            sent_gold = int(request.POST.get('sent_gold'))

            try:
                # Збереження файлу
                filename = crud.create_video_filename(request, sold_order_number)
                filepath = os.path.join(settings.MEDIA_ROOT, 'videos', filename)  # Шлях до папки videos
                with open(filepath, 'wb+') as destination:
                    for chunk in video_file.chunks():
                        destination.write(chunk)
                logger.info(f"filepath__{filepath}")
                response = crud.update_sold_order_when_video_download(user, sold_order_number, filepath, sent_gold)
                logger.info(f"response__{response}")

                return redirect('main:start_page')
            except Exception as e:
                messages.success(request, 'Error saving video')

        else:
            messages.error(request, 'Будь ласка, виберіть файл.')


def show_history_orders(request):
    user_id = request.user.id
    orders_history = crud.get_orders_history(user_id)

    total_earned = 0  # Ініціалізуємо загальну суму
    orders_with_balance = []

    for order in orders_history:

        total_earned += order.earned_without_admins_commission if not order.paid_in_salary else 0  # Додаємо значення до загальної суми
        orders_with_balance.append({
            'order': order,
            'current_balance': total_earned  # Додаємо поточний баланс до кожного замовлення
        })
    logger.info(orders_with_balance)
    return render(request, 'main/show_history.html', context={"orders_history": orders_with_balance})


def show_balance(request):
    balance = crud.get_balance(request.user.id)

    logger.info(f"balance__{balance}")
    return render(request, 'users/base.html', context={'user_balance': balance})


def delete_server(request):
    data = json.loads(request.body)
    row_id = data.get('row_id')
    crud.delete_server_from_list(row_id)
    return JsonResponse({"success": True})
