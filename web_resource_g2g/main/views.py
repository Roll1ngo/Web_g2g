import os
from collections import defaultdict
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import redirect, render, get_object_or_404 # Added get_object_or_404
import json

from main import crud
from main import calculate_commissions_crud as commissions_crud
from .utils.logger_config import logger
from main.models import SoldOrders
from internal_market.models import InternalOrder


@login_required(login_url='users:login')
def start_page(request):
    if request.method == 'GET':
        user_id = request.user.id
        password_confirmed = crud.password_confirmed_status(user_id)

        if not password_confirmed:
            bool_exist_username = crud.check_exist_username(user_id)

            e_mail, password = crud.get_email_password(user_id)

            return render(request, 'users/continue_registration.html', context={"e-mail": e_mail,
                                                                         'temp_password': password,
                                                                         'exist_username': bool_exist_username})

        all_bets = crud.get_main_data_from_table(user_id)

        count_orders = crud.get_count_orders(user_id)
        logger.info(f"count_orders__{count_orders}")


        servers = crud.query_servers()
        games = set(server.game_name for server in servers)
        regions = set(server.region for server in servers)

        grouped_data_db = crud.get_grouped_data(servers)
        grouped_data = json.dumps(grouped_data_db)

        # Перевірка, чи all_bets не є порожнім
        if all_bets:
            double_add = [{'server_name': server.get('server_name', ''),
                           'game_name': server.get('game_name', '')} for server in all_bets]
        else:
            double_add = []  # Якщо all_bets порожній, double_add також буде порожнім

        context = {
            "bets_list": all_bets if all_bets else [],  # Перевірка на порожній all_bets
            'games': games,
            'regions': regions,
            'servers_json': grouped_data,
            'double_add': double_add,
            'count_orders': count_orders
        }

        return render(request, 'main/index.html', context)


def update_table_data(request):
    if request.method == 'POST':
        user_id = request.user.id
        data = json.loads(request.body)
        logger.info(f"Received data for update_table_data: {data}")

        row_id = data.get('row_id')
        field_name = data.get('field_name')
        new_value = data.get('new_value')

        if field_name == 'stock':
            logger.info(f"Server-side validation for 'stock' field. Row ID: {row_id}, Value: '{new_value}'")
            try:
                stock_value_float = float(new_value)
            except ValueError:
                logger.warning(f"Validation failed: Stock value '{new_value}' is not a valid number.")
                return JsonResponse({'success': False, 'error': 'Значення "Запас" повинно бути дійсним числом.'})

            if stock_value_float < 0:
                logger.warning(f"Validation failed: Stock value {stock_value_float} is negative.")
                return JsonResponse({'success': False, 'error': 'Значення "Запас" повинно бути позитивним числом.'})

            # Fetch game_name for specific validation
            # You MUST implement crud.get_game_name_for_offer(row_id) in your crud.py
            # This function should query your Django model (e.g., Offer.objects.get(id=row_id).game_name)
            game_name = crud.get_game_name_for_offer(row_id)

            if game_name is None:
                logger.error(f"Could not retrieve game_name for offer_id {row_id}. Aborting validation.")
                return JsonResponse({'success': False, 'error': 'Не вдалося отримати інформацію про гру для валідації.'})

            game_name_lower = game_name.strip().lower()
            logger.info(f"Server-side: Game Name for row {row_id}: '{game_name_lower}'")

            if game_name_lower == 'cataclysm':
                logger.info(f"Server-side: Applying Cataclysm specific validation for stock: {stock_value_float}")
                # Check for integer and range 0-999
                if not stock_value_float.is_integer() or stock_value_float < 0 or stock_value_float > 999:
                    logger.warning(f"Validation failed: Cataclysm stock {stock_value_float}"
                                   f" is not an integer between 0 and 999.")
                    return JsonResponse({'success': False, 'error': 'Для гри Cataclysm,'
                                                                    ' у поле "Запас" вводиться кількість тисяч.'
                                                                    ' Наприклад 25000 = 25, 5489 = 5.'})
            else:
                logger.info(f"Server-side: Applying general validation for stock: {stock_value_float} (Game: '{game_name_lower}')")
                # For non-Cataclysm, the float conversion and non-negative check above are sufficient.
                # If you need to restrict decimals for other games, add more logic here.
                pass

        # If validation passes (or if not 'stock' field), proceed with update
        new_price = crud.update_price_delivery(data, user_id)
        logger.info(f"Update successful. New price: {new_price}")
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


@login_required(login_url='users:login')
def show_order_info(request):
    user_id = request.user.id

    order_info = crud.get_order_info(user_id)
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
        try:
            total_chunks = int(request.POST.get('total_chunks'))
            chunk = request.FILES.get('video_chunk')
            chunk_number = int(request.POST.get('chunk_number'))
            temp_filename = request.POST.get('filename')
            sent_gold = int(request.POST.get('sent_gold'))

            logger.info(f"chunk__{chunk}")
            logger.info(f"chunk_number__{chunk_number}")
            logger.info(f"total_chunks__{total_chunks}")
            logger.info(f"filename__{temp_filename}")
            logger.info(f"sent_gold__{sent_gold}")

            temp_dir = os.path.join(settings.MEDIA_ROOT, 'videos', f'tmp_{sold_order_number}')
            os.makedirs(temp_dir, exist_ok=True)

            chunk_path = os.path.join(temp_dir, f"{temp_filename}.part{chunk_number}")
            with open(chunk_path, 'wb+') as destination:
                for data in chunk.chunks():
                    destination.write(data)

            # Якщо це останній chunk
            if chunk_number + 1 == total_chunks:
                server_filename, sold_order = crud.create_video_filename(request, sold_order_number)
                final_path = os.path.join(settings.MEDIA_ROOT, 'videos', server_filename)

                with open(final_path, 'wb+') as final_file:
                    for i in range(total_chunks):
                        part_path = os.path.join(temp_dir, f"{temp_filename}.part{i}")
                        with open(part_path, 'rb') as part_file:
                            final_file.write(part_file.read())

                # Очистка тимчасових файлів
                for i in range(total_chunks):
                    os.remove(os.path.join(temp_dir, f"{temp_filename}.part{i}"))
                os.rmdir(temp_dir)

                # Оновлення замовлення
                response = crud.update_sold_order_when_video_download(user, sold_order, final_path, sent_gold)
                logger.info(f"response__{response}")

                return JsonResponse({'status': 'complete'})  # повідомити фронт що все ок

            return JsonResponse({'status': f'chunk {chunk_number + 1}/{total_chunks} received'})

        except Exception as e:
            logger.error(f"Error uploading video chunk: {e}")
            return JsonResponse({'error': 'Помилка при збереженні відео'}, status=500)

    return JsonResponse({'error': 'Неправильний метод'}, status=400)




@login_required(login_url='users:login')
def show_history_orders(request):
    user_id = request.user.id
    payment_status = request.GET.get('payment_status', '')  # Отримуємо параметр фільтрації

    # Отримуємо замовлення з урахуванням фільтрації
    sold_orders = crud.get_sold_orders_for_history(user_id)
    internal_orders = crud.get_internal_orders_for_history(user_id)
    orders_with_balance = crud.get_orders_with_balance(user_id, sold_orders, internal_orders)
    logger.info(f"orders_with_balance__{orders_with_balance}")

    # Фільтрація за статусом виплати
    if payment_status:
        if payment_status == "charged_to_payment":
            orders_with_balance = [order for order in orders_with_balance if order['order'].charged_to_payment
                                   and not order['order'].paid_in_salary]
        elif payment_status == "paid_in_salary":
            orders_with_balance = [order for order in orders_with_balance if order['order'].charged_to_payment
                                   and order['order'].paid_in_salary]
        elif payment_status == "cancelled":
            orders_with_balance = [order for order in orders_with_balance
                                   if order['order'].status == "CANCEL_REQUESTED"]
        elif payment_status == "no_info":
            orders_with_balance = [order for order in orders_with_balance
                                   if not order['order'].charged_to_payment and not order['order'].paid_in_salary]

    return render(request, 'main/show_history.html', context={"orders_history": orders_with_balance})


def show_balance(request):
    balance = crud.get_balance(request.user.id)
    logger.info(f"balance__{balance}")
    return render(request, 'users/base.html', context={'user_balance': round(balance, 3)})


def delete_server(request):
    data = json.loads(request.body)
    row_id = data.get('row_id')
    crud.delete_server_from_list(row_id)
    return JsonResponse({"success": True})


@login_required(login_url='users:login')
def my_services(request):
    try:
        max_progress_value = Decimal(str(settings.MAX_PROGRESS_VALUE))
    except Exception as e:
        logger.error(f"Error converting settings.MAX_PROGRESS_VALUE to Decimal: {e}")
        max_progress_value = Decimal('100.00')

    user_id = request.user.id
    my_service_commission_list = commissions_crud.get_my_service_list(user_id)
    logger.info(f"my_service_commission_list__{my_service_commission_list}")

    # Define content types for your order models
    sold_order_ct = ContentType.objects.get_for_model(SoldOrders)
    internal_order_ct = ContentType.objects.get_for_model(InternalOrder)

    my_clients_provide_service = crud.get_clients_provide_service(user_id)
    logger.info(f"my_clients_provide_service__{my_clients_provide_service}")

    client_total_commissions = defaultdict(Decimal)

    # Sum commissions for each client from the my_service_commission_list
    for service in my_service_commission_list:
        client_username = None
        # Check the content type of the related order
        if service.content_type == sold_order_ct:
            # Assuming SoldOrder has a 'seller' field
            if hasattr(service.order, 'seller') and service.order.seller and hasattr(service.order.seller, 'auth_user'):
                client_username = service.order.seller.auth_user.username
            else:
                logger.warning(f"SoldOrder for CommissionBreakdown ID {service.id} missing 'seller' or 'auth_user'. Skipping.")
                continue
        elif service.content_type == internal_order_ct:
            # InternalOrder has 'internal_seller' field
            if hasattr(service.order, 'internal_seller') and service.order.internal_seller and hasattr(service.order.internal_seller, 'auth_user'):
                client_username = service.order.internal_seller.auth_user.username
            else:
                logger.warning(f"InternalOrder for CommissionBreakdown ID {service.id} missing 'internal_seller' or 'auth_user'. Skipping.")
                continue
        else:
            logger.warning(f"Skipping CommissionBreakdown ID {service.id}: Unexpected content type '{service.content_type}'.")
            continue

        if client_username:
            client_total_commissions[client_username] += service.amount
            logger.debug(
                f"Commission for {client_username}: {service.amount}, Current total: {client_total_commissions[client_username]}")

    logger.debug(f"client_total_commissions (after summing): {client_total_commissions}")
    logger.debug(f"max_progress_value: {max_progress_value}")

    enriched_clients_provide_service = {
        'mentor': [],
        'recruiter': [],
        'renter_lvl': {}
    }

    # Process Mentors (no progress bar)
    logger.debug(f"Processing Mentors. Raw data: {my_clients_provide_service.get('mentor', [])}")
    for client_name in my_clients_provide_service.get('mentor', []):
        amount = client_total_commissions.get(client_name, Decimal('0.0'))
        enriched_clients_provide_service['mentor'].append({
            'client_name': client_name,
            'total_received_amount': amount,
        })

    # Process Recruiters (with progress bar)
    logger.debug(f"Processing Recruiters. Raw data: {my_clients_provide_service.get('recruiter', [])}")
    for client_name in my_clients_provide_service.get('recruiter', []):
        amount = client_total_commissions.get(client_name, Decimal('0.0'))
        if max_progress_value == Decimal('0'):
            percentage = Decimal('0.0')
            logger.warning(f"max_progress_value is 0. Setting percentage to {percentage} for recruiter {client_name}.")
        else:
            percentage = min((amount / max_progress_value) * 100, Decimal('100.0'))

        logger.debug(f"Recruiter: {client_name}, Amount: {amount}, Calculated Percentage: {percentage}")

        enriched_clients_provide_service['recruiter'].append({
            'client_name': client_name,
            'total_received_amount': amount,
            'total_received_percentage': percentage
        })

    # Process Renters (by seller and then by level - no progress bar)
    logger.debug(f"Processing Renters. Raw data: {my_clients_provide_service.get('renter_lvl', {})}")
    for seller_name, levels in my_clients_provide_service.get('renter_lvl', {}).items():
        enriched_levels = {}


        # Revised processing for Renters:
        lvl1_total_amount = Decimal('0.0')
        lvl2_total_amount = Decimal('0.0')

        # Filter commissions for the current seller_name and service type 'renter_lvl1'/'renter_lvl2'
        for commission in my_service_commission_list:
            commission_username = None
            if commission.content_type == sold_order_ct:
                if hasattr(commission.order, 'seller') and commission.order.seller and hasattr(commission.order.seller,
                                                                                               'auth_user'):
                    commission_username = commission.order.seller.auth_user.username
            elif commission.content_type == internal_order_ct:
                if hasattr(commission.order, 'internal_seller') and commission.order.internal_seller and hasattr(
                        commission.order.internal_seller, 'auth_user'):
                    commission_username = commission.order.internal_seller.auth_user.username

            if commission_username == seller_name:  # Check if this commission belongs to the current seller
                if commission.service_type == 'renter_lvl1':
                    lvl1_total_amount += commission.amount
                elif commission.service_type == 'renter_lvl2':
                    lvl2_total_amount += commission.amount

        if levels.get('renter_lvl1'):
            logger.debug(
                f"Renter Lvl1 ({seller_name}): Clients: {levels['renter_lvl1']}, Calculated Amount: {lvl1_total_amount}")

            enriched_levels['renter_lvl1'] = {
                'client_names': levels['renter_lvl1'],
                'total_received_amount': lvl1_total_amount,
            }

        if levels.get('renter_lvl2'):
            logger.debug(
                f"Renter Lvl2 ({seller_name}): Clients: {levels['renter_lvl2']}, Calculated Amount: {lvl2_total_amount}")

            enriched_levels['renter_lvl2'] = {
                'client_names': levels['renter_lvl2'],
                'total_received_amount': lvl2_total_amount,
            }

        enriched_clients_provide_service['renter_lvl'][seller_name] = enriched_levels

    logger.debug(f"Final enriched_clients_provide_service: {enriched_clients_provide_service}")

    return render(request, 'main/my_services.html', context={
        "my_services": my_service_commission_list,
        'my_clients_provide_service': enriched_clients_provide_service,
        'max_progress_value': max_progress_value
    })

