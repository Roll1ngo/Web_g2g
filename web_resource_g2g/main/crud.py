from datetime import datetime
from pathlib import Path
import os

from django.db import transaction
from django.shortcuts import get_object_or_404

from .models import OffersForPlacement, ServerUrls, Sellers, TopPrices, SoldOrders, Commission
from django.db.models import F
from .utils.logger_config import logger


def get_main_data_from_table(auth_user_id: int):
    main_data = (
        OffersForPlacement.objects
        .select_related('server_urls')
        .annotate(
            game_name=F('server_urls__game_name'),
            region=F('server_urls__region'),
            server_name=F('server_urls__server_name'),
        ).filter(sellers__auth_user__id=auth_user_id)
        .values(
            'id',
            'sellers',
            'server_urls',
            'currency',
            'description',
            'price',
            'stock',
            'min_units_per_order',
            'active_rate',
            'percent_offset',
            'duration',
            'face_to_face_trade',
            'mail_delivery',
            'auction_house',
            'delivery_online_hrs',
            'delivery_offline_hrs',
            'is_created_lot',
            'reserve_stock',
            'game_name',
            'region',
            'server_name',
            'order_status',
        )
    )
    # Оновлюємо ціни та створюємо новий список
    main_data_float_price = []
    for row in main_data:
        try:
            row['strategy_price'] = row['price']
            stock = row['stock']
            if row['price']:
                new_price = get_float_price(row, auth_user_id)
                row['price'] = new_price
                row['full_cost'] = round(new_price * stock, 3)

            else:
                row['price'] = None

            main_data_float_price.append(row)
        except (ValueError, TypeError) as e:
            logger.info(f"Error updating {row.server_name}: {e}")
            continue  # Пропустити помилковий рядок і перейти до наступного

    return main_data_float_price


import logging
from django.core.exceptions import ObjectDoesNotExist

logger = logging.getLogger(__name__)

def get_float_price(row, auth_user_id):
    try:
        # Перевірка наявності ключів у `row`
        currently_strategy = row.get('price')
        server_urls_id = row.get('server_urls')

        if not currently_strategy or not server_urls_id:
            logger.error("Missing 'price' or 'server_urls' in row.")
            return None

        # Отримання останнього запису з `Commission`
        try:
            rang_exchange = Commission.objects.latest('created_time').commission
        except ObjectDoesNotExist:
            logger.error("No Commission records found.")
            return None

        # Отримання `interest_rate` з `Sellers`
        try:
            interest_rate = Sellers.objects.get(auth_user_id=auth_user_id).interest_rate
        except Sellers.DoesNotExist:
            logger.error(f"No Sellers record found for auth_user_id={auth_user_id}.")
            return None

        # Отримання `float_price` з `TopPrices`
        float_price = TopPrices.objects.filter(server_name=server_urls_id).values_list(
            currently_strategy, flat=True
        ).first()

        total_percent = interest_rate - rang_exchange
        float_price_without_exchange = float_price * (total_percent / 100)

        if float_price is None:
            logger.error(f"No TopPrices record found for server_name={server_urls_id}.")
            return None

        # Логування результатів
        logger.info(f"float_price__{float_price}")
        logger.info(f"rang_exchange__{rang_exchange}, interest_rate__{interest_rate}")
        logger.info(f"float_price_without_exchange__{float_price_without_exchange}, total_percent__{total_percent}")

        return round(float_price_without_exchange, 3)

    except Exception as e:
        # Логування будь-якої несподіваної помилки
        logger.error(f"Unexpected error in get_float_price: {e}", exc_info=True)
        return None


def update_data(data):
    try:
        # Retrieve the OffersForPlacement object
        offer = OffersForPlacement.objects.get(id=data['row_id'])

        # Update the specified field with the new value
        setattr(offer, data['field_name'], data['new_value'])
        offer.save()

        # Get the new strategy (price)
        new_strategy = offer.price

        try:
            # Retrieve the TopPrices object
            top_prices_row = TopPrices.objects.get(server_name=offer.server_urls_id)
            new_price = getattr(top_prices_row, new_strategy)
        except TopPrices.DoesNotExist:
            # Handle the case where the TopPrices object does not exist
            new_price = 0

    except OffersForPlacement.DoesNotExist:
        # Handle the case where the OffersForPlacement object does not exist
        raise ValueError(f"OffersForPlacement with id {data['row_id']} does not exist.")

    return new_price


def get_servers_for_add():
    servers = ServerUrls.objects.values('game_name', 'region', 'fraction')
    return servers


def query_servers():
    servers = ServerUrls.objects.all()
    return servers


def get_grouped_data(servers):
    server_data = []
    for server in servers:
        server_data.append({
            'game_name': server.game_name,
            'region': server.region,
            'server_name': server.server_name
        })
    # Групуємо дані за грою та регіоном і сортуємо сервери
    grouped_data = {}
    for data in server_data:
        game = data['game_name']
        region = data['region']
        if game not in grouped_data:
            grouped_data[game] = {}
        if region not in grouped_data[game]:
            grouped_data[game][region] = []
        grouped_data[game][region].append(data['server_name'])
        # Сортуємо список серверів за алфавітом
        grouped_data[game][region].sort()
    return grouped_data


def add_server_to_db(data):
    auth_user_id = data['auth_user_id']
    server_name = data['server']
    game_name = data['game']

    seller_id = Sellers.objects.get(auth_user_id=auth_user_id)
    server_id = ServerUrls.objects.get(server_name=server_name,
                                       game_name=game_name)

    logger.info(f'seller_id__{seller_id.id}, server_id__{server_id.id}')
    new_offer = OffersForPlacement(sellers=seller_id,
                                   server_urls=server_id,
                                   currency='USD',
                                   description='gold',
                                   price='mean20_lot',
                                   stock=0,
                                   min_units_per_order=0,
                                   active_rate=False,
                                   percent_offset=0,
                                   duration=3,
                                   face_to_face_trade=True,
                                   mail_delivery=True,
                                   auction_house=True,
                                   delivery_online_hrs=1,
                                   delivery_offline_hrs=6,
                                   is_created_lot=True,
                                   reserve_stock=0,
                                   order_status=False,
                                   )
    new_offer.save()


def delete_server_from_list(offer_id):
    offer = OffersForPlacement.objects.get(id=offer_id)
    offer.delete()


def pause_offer(offer_id, action):
    offer = OffersForPlacement.objects.get(id=offer_id)

    if action == 'pause':
        setattr(offer, 'active_rate', 0)
    elif action == 'resume':
        setattr(offer, 'active_rate', 1)

    offer.save()


def get_order_info(server_id, user_id):

    order_info = (SoldOrders.objects.filter(server_id=server_id, seller_id=user_id, download_video_status=False).
                  select_related('server').first())

    return order_info


def update_sold_order_when_video_download(order_number, path_to_video, sent_gold):
    logger.info(f"sold_order_number__{order_number}, path_to_video__{path_to_video}, sent_gold__{sent_gold}")
    try:
        with transaction.atomic():  # Забезпечує цілісність транзакції
            # Оновлюємо запис у SoldOrders
            sold_order = SoldOrders.objects.get(sold_order_number=order_number)
            seller_id = sold_order.seller_id
            pay_to_completed_order = sold_order.to_be_earned
            sold_order.path_to_video = path_to_video
            sold_order.sent_gold = sent_gold
            sold_order.download_video_status = True
            sold_order.charged_to_payment = True
            sold_order.save()

            seller_info = Sellers.objects.get(auth_user_id=seller_id)
            seller_info.balance += pay_to_completed_order
            seller_info.save()
            # Знаходимо запис у OffersForPlacement, пов'язаний із SoldOrders
            offer = OffersForPlacement.objects.filter(
                sellers=sold_order.seller,
                server_urls=sold_order.server,
                order_status=True
            ).first()

            if offer:
                offer.order_status = False
                offer.save()
        logger.info('посилання на відео додано до бази даних та статус змінено')
        return "Статус оновлено успішно."
    except SoldOrders.DoesNotExist:
        return f"Замовлення не знайдено"
    except Exception as e:
        return f"Помилка: {e}"


def get_orders_history(user_id):
    orders_history = SoldOrders.objects.filter(seller_id=user_id,).select_related('server')
    return orders_history


def get_server_id(user_id):
    try:
        order_info = SoldOrders.objects.get(seller_id=user_id, download_video_status=False)
        server_id = order_info.server_id
    except SoldOrders.DoesNotExist:
        return f"Замовлення не знайдено"
    except Exception as e:
        return f"Помилка: {e}"
    return server_id


def create_video_filename(request, sold_order_number):
    logger.info('inside')
    sold_order = SoldOrders.objects.filter(sold_order_number=sold_order_number,).select_related('server').first()
    sent_gold = request.POST.get('sent_gold')
    seller = request.user

    server = sold_order.server.server_name
    game = sold_order.server.game_name
    current_time = datetime.now().strftime("%Y-%m-%d___%H-%M")

    filename = f"{seller}__{sent_gold}__{server}__{game}__{sold_order_number}__{current_time}.mp4"
    logger.info(filename)
    return filename


def get_balance(user_id):
    seller = Sellers.objects.filter(auth_user_id=user_id).first()
    return seller.balance

