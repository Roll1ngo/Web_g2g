from main import models as main_models
from django.db.models import F, Sum, DecimalField, Q
from main.utils.logger_config import logger
from main import crud as main_crud


def get_lots_for_sale(auth_user_id: int):
    seller_id = main_crud.get_seller_id_by_user_id(auth_user_id)

    main_data = (
        main_models.OffersForPlacement.objects
        .select_related('server_urls')
        .annotate(
            game_name=F('server_urls__game_name'),
            region=F('server_urls__region'),
            server_name=F('server_urls__server_name'),
        ).exclude(sellers__auth_user__id=auth_user_id)
        .filter(active_rate=True, order_status=False)
        .order_by('server_name')
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
                new_price, interest_rate = get_float_price(row)
                row['price'] = new_price
                row['interest_rate'] = interest_rate
                row['full_cost'] = round(new_price * stock, 3)

            else:
                row['price'] = None

            main_data_float_price.append(row)
        except (ValueError, TypeError) as e:
            logger.info(f"Error updating {row['server_name']}: {e}")
            continue  # Пропустити помилковий рядок і перейти до наступного

    return main_data_float_price


def get_float_price(row):
    try:
        # Перевірка наявності ключів у `row`
        seller_id = row.get('sellers')
        currently_strategy = row.get('price')
        server_urls_id = row.get('server_urls')
        rang_exchange = float(main_crud.get_global_commissions_rates()['exchange'])
        logger.info(rang_exchange)
        interest_rate = main_crud.get_interest_rate_by_seller_id(seller_id, server_urls_id)
        logger.info(f"interest_rate__{interest_rate}")

        if not currently_strategy or not server_urls_id:
            logger.error("Missing 'price' or 'server_urls' in row.")
            return None, None

        # Отримання `float_price` з `TopPrices`
        float_price = main_models.TopPrices.objects.filter(server_name=server_urls_id).values_list(
            currently_strategy, flat=True
        ).first()
        # Віднімаєм відсоток біржі від повної вартості
        float_price_without_exchange = float_price * (1 - rang_exchange / 100)
        logger.info(f"source_price__{float_price}, final_price_without_exchange__{float_price_without_exchange}")

        logger.warning(f"Відсутні ціни для сервера {server_urls_id}. Потрібен сеанс парсингу")\
            if float_price is None else None

        return round(float_price_without_exchange, 3), interest_rate

    # except Exception as e:
    #     # Логування будь-якої несподіваної помилки
    #     logger.error(f"Unexpected error in get_float_price: {e}", exc_info=True)
    #     return None, None
    finally:
        pass
