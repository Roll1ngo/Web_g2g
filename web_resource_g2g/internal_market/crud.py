import decimal
import json

from internal_market.models import InternalOrder
from main import models as main_models
from django.db.models import F, Sum, DecimalField, Q

from main.models import Sellers, ServerUrls, OffersForPlacement
from main.utils.logger_config import logger
from main import crud as main_crud
from main import calculate_commissions_crud as commissions_crud
from main.tg_bot_run import send_messages_sync


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
        rang_exchange = float(commissions_crud.get_global_commissions_rates()['exchange'])
        logger.info(rang_exchange)
        interest_rate = commissions_crud.get_interest_rate_by_seller_id(seller_id, server_urls_id)
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

        logger.warning(f"Відсутні ціни для сервера {server_urls_id}. Потрібен сеанс парсингу") \
            if float_price is None else None

        return round(float_price_without_exchange, 3), interest_rate

    # except Exception as e:
    #     # Логування будь-якої несподіваної помилки
    #     logger.error(f"Unexpected error in get_float_price: {e}", exc_info=True)
    #     return None, None
    finally:
        pass


def create_order(user_id, internal_order_data):
    internal_buyer_id = Sellers.objects.get(auth_user_id=user_id)
    internal_order_data['buyer_id'] = internal_buyer_id.id
    logger.info(f"internal_order_data{internal_order_data}")
    internal_seller_id = Sellers.objects.get(id=internal_order_data['seller_id'])
    server_id = ServerUrls.objects.get(id=internal_order_data['server_id'])
    total_amount = decimal.Decimal(internal_order_data['total_amount'])

    (to_be_earned_without_exchange_commission, earned_without_service_commission, technical_commission,
     owner_commission, seller_rate) = commissions_crud.calculate_owner_technical_commissions(internal_seller_id,
                                                                                             server_id.id,
                                                                                             total_amount,
                                                                                             exist_exchange_commission=
                                                                                             False)
    logger.info(f"to_be_earned_without_exchange_commission__{to_be_earned_without_exchange_commission},"
                f"earned_without_service_commission__{earned_without_service_commission},"
                f"technical_commission__{technical_commission}, owner_commission_{owner_commission},"
                f"seller_rate__{seller_rate}")

    new_internal_order = InternalOrder.objects.create(server=server_id,
                                                      internal_seller=internal_seller_id,
                                                      internal_buyer=internal_buyer_id,
                                                      trade_mode=internal_order_data['delivery_method'],
                                                      character_name=internal_order_data['character_name'],
                                                      quantity=internal_order_data['order_quantity'],
                                                      price_unit=internal_order_data['unit_price'],
                                                      total_amount=internal_order_data['total_amount'],
                                                      earned_without_admins_commission=
                                                      earned_without_service_commission,
                                                      owner_commission=owner_commission,
                                                      technical_commission=technical_commission,
                                                      )
    new_internal_order.save()

    commissions_crud.calculate_and_record_mentor_renter_recruiter_commissions(internal_seller_id.id, server_id.id,
                                                                              to_be_earned_without_exchange_commission,
                                                                              new_internal_order.sold_order_number,
                                                                              internal_order=True)

    OffersForPlacement.objects.filter(sellers=internal_seller_id.id,
                                      server_urls=new_internal_order.server.id).update(order_status=True)
    message = create_order_message(new_internal_order, order_source='internal_market')

    send_messages_sync(internal_seller_id.id, internal_seller_id.auth_user.username, message)
    new_internal_order.send_message = True
    new_internal_order.save()


def create_order_message(order, order_source='exchange'):

    seller = order.seller if order_source == 'exchange' else order.internal_seller
    if seller.id_telegram:  # Перевіряємо, чи є у продавця Telegram ID
        message = str(f"Вітаю, {seller.auth_user.first_name} для вас замовлення від {order.created_time.strftime('%Y-%m-%d %H:%M:%S')} \n"
                      f"Сервер___________{order.server.server_name}\n"
                      f"Гра___________{order.server.game_name}\n"
                      f"Кількість___________{order.quantity}\n"
                      f"Ім'я персонажа___________{order.character_name}\n"
                      f"Спосіб доставки___________{order.trade_mode}\n"
                      f"Сума замовлення: {order.earned_without_admins_commission}\n"
                      )
        logger.info(message)

    else:
        logger.warning(f"Продавець {seller.auth_user.username} не має Telegram ID")

    return message
