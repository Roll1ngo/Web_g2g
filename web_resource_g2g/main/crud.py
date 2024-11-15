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
            logger.info(row['strategy_price'])
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

    offer = OffersForPlacement.objects.get(id=data['row_id'])
    setattr(offer, data['field_name'], data['new_value'])
    offer.save()

    new_strategy = offer.price
    top_prices_row = TopPrices.objects.get(server_name=offer.server_urls_id)
    new_price = getattr(top_prices_row, new_strategy)

    return new_price


def get_servers_for_add():
    servers = ServerUrls.objects.values('game_name', 'region', 'fraction')
    return servers


def query_servers():
    servers = ServerUrls.objects.all()
    return servers

