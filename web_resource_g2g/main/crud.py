from pathlib import Path
import os
from .models import OffersForPlacement, ServerUrls, Sellers, TopPrices
from django.db.models import F
from .utils.logger_config import logger


def get_main_data_from_table():
    main_data = (
        OffersForPlacement.objects
        .select_related('server_urls')
        .annotate(
            game_name=F('server_urls__game_name'),
            region=F('server_urls__region'),
            server_name=F('server_urls__server_name'),
        )
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

        )
    )
    # Оновлюємо ціни та створюємо новий список
    main_data_float_price = []
    for row in main_data:
        try:
            row['strategy_price'] = row['price']
            if row['price']:
                new_price, new_min_stack = get_float_price(row)
                row['price'] = new_price
                row['Min_units_per_order'] = new_min_stack
            else:
                row['price'] = None

            main_data_float_price.append(row)
        except (ValueError, TypeError) as e:
            logger.info(f"Error updating {row.server_name}: {e}")
            continue  # Пропустити помилковий рядок і перейти до наступного

    return main_data_float_price


def get_float_price(row):
    currently_strategy = row['price']
    min_stack = row['min_units_per_order']
    percent_offset = row['percent_offset']
    server_urls_id = row['server_urls']
    stock = row['stock']

    float_price = (TopPrices.objects.filter(server_name=server_urls_id).
                   values_list(currently_strategy, flat=True).first())
    # if float_price:
    #     # Коригуємо відсоток
    #     if percent_offset and percent_offset != 'nan' and float_price and stock:
    #         calculate_float_price = float_price * \
    #                                 (1 + percent_offset / 100) * stock
    #         float_price = round(calculate_float_price, 2)
    return float_price, min_stack


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
                                   reserve_stock=0
                                   )
    new_offer.save()


def delete_server_from_list(offer_id):
    offer = OffersForPlacement.objects.get(id=offer_id)
    offer.delete()
