import decimal
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from django.forms import model_to_dict
from django.utils import timezone

from .models import (OffersForPlacement, ServerUrls, Sellers, TopPrices,
                     SoldOrders, SellerServerInterestRate, ChangeStockHistory, CommissionBreakdown,
                     CommissionRates)
from django.db.models import F, Sum, DecimalField, Q

from main.tg_bot_run import send_messages_sync
from main.tg_bot_run import send_messages_sync

from main.utils.logger_config import logger
from main import calculate_commissions_crud as commissions_crud
from internal_market.models import InternalOrder
from main import calculate_commissions_crud as commissions_crud
from internal_market.models import InternalOrder

owner_user_and_seller_id = 1
technical_user_and_seller_id = 2


def check_exists_another_order_before_change_order_status(seller_id,
                                                          server_id,
                                                          sold_order_number):
    """
    Перевіряє, чи існують інші замовлення (крім замовлення з sold_order_number)
    для вказаного сервера та продавця, у яких download_video_status = False.

    :param server_id: ID сервера
    :param seller_id: ID продавця
    :param sold_order_number: Номер замовлення, яке не враховується
    :return: True, якщо такі замовлення існують, інакше False
    """
    # Виконуємо запит до моделі SoldOrders
    other_exchange_orders_exist = SoldOrders.objects.filter(server_id=server_id,
                                                            seller_id=seller_id,
                                                            download_video_status=False,
                                                            status='DELIVERING'
                                                            ).exclude(
        sold_order_number=sold_order_number
    ).exists()
    logger.info(f"other_exchange_orders_exist__{other_exchange_orders_exist}")
    other_internal_market_orders_exist = InternalOrder.objects.filter(server_id=server_id,
                                                                      internal_seller=seller_id,
                                                                      download_video_status=False,
                                                                      status='DELIVERING'
                                                                      ).exclude(
        sold_order_number=sold_order_number
    ).exists()
    logger.info(f"other_internal_market_orders_exist__{other_internal_market_orders_exist}")
    return False if not other_exchange_orders_exist and not other_internal_market_orders_exist else True


def get_main_data_from_table(auth_user_id: int):
    seller_id = get_seller_id_by_user_id(auth_user_id)

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
            'double_minimal_mode_status',
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
            # #Шукаємо стратегію на активному лоті такого ж сервера
            current_strategy = OffersForPlacement.objects.filter(
                server_urls=row['server_urls'],
                active_rate=True
            ).exclude(sellers=row['sellers']).values_list('price', flat=True).first()

            if current_strategy:
                ballance_strategy_for_all = 'minimal'
                change_all_strategy = OffersForPlacement.objects.filter(server_urls_id=row['server_urls'])
                change_all_strategy.update(price=ballance_strategy_for_all, face_to_face_trade=True)

                row['strategy_price'] = ballance_strategy_for_all
                row['price'] = ballance_strategy_for_all
                row['exists_strategy'] = True
                row['face_to_face_trade'] = False
            else:
                row['strategy_price'] = row['price']
                row['exists_strategy'] = False

            stock = row['stock']
            if row['price']:
                new_price, interest_rate = get_float_price(row, seller_id)
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


def get_float_price(row, seller_id):
    try:
        # Перевірка наявності ключів у `row`
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
        float_price = TopPrices.objects.filter(server_name=server_urls_id).values_list(
            currently_strategy, flat=True
        ).first()

        if float_price is None:
            logger.warning(f"Відсутні ціни для сервера {server_urls_id}. Потрібен сеанс парсингу")
            float_price_without_exchange = 0
            return round(float_price_without_exchange, 3), interest_rate

        total_percent = interest_rate - rang_exchange
        float_price_without_exchange = float_price * (total_percent / 100)

        logger.info(f"float_price__{float_price}, rang_exchange__{rang_exchange},"
                    f" interest_rate__{interest_rate} float_price_without_exchange__{float_price_without_exchange},"
                    f" total_percent__{total_percent}")

        return round(float_price_without_exchange, 3), interest_rate

    # except Exception as e:
    #     # Логування будь-якої несподіваної помилки
    #     logger.error(f"Unexpected error in get_float_price: {e}", exc_info=True)
    #     return None, None
    finally:
        pass


def get_clients_provide_service(user_id):
    seller = Sellers.objects.get(auth_user_id=user_id)
    seller_id = seller.id
    seller_relations = {}

    # Знаходимо продавця
    try:
        seller = Sellers.objects.get(id=seller_id)
    except Sellers.DoesNotExist:
        return seller_relations  # Якщо продавця немає, повертаємо порожній словник

    # Отримуємо продавців, яких seller менторить
    mentees = [mentee.auth_user.username for mentee in seller.mentees.all()]
    if mentees:
        seller_relations["mentor"] = mentees

    # Отримуємо продавців, яких seller рекрутував
    recruits = [recruit.auth_user.username for recruit in seller.recruits.all()]
    if recruits:
        seller_relations["recruiter"] = recruits

    # Отримуємо дані про оренду
    renter_relations = SellerServerInterestRate.objects.filter(
        Q(renter_lvl1=seller) | Q(renter_lvl2=seller)
    ).select_related("seller", "server")

    renter_lvl = defaultdict(lambda: {"renter_lvl1": [], "renter_lvl2": []})

    for relation in renter_relations:
        seller_name = relation.seller.auth_user.username
        server_name = relation.server.server_name
        server_game = relation.server.game_name

        if relation.renter_lvl1 == seller:
            renter_lvl[seller_name]["renter_lvl1"].append(server_name + " - " + server_game)

        if relation.renter_lvl2 == seller:
            renter_lvl[seller_name]["renter_lvl2"].append(server_name + " - " + server_game)

    if renter_lvl:
        seller_relations["renter_lvl"] = dict(renter_lvl)  # Перетворюємо defaultdict у звичайний dict

    return seller_relations


def update_price_delivery(data, user_id):
    field = data['field_name']
    value = data['new_value']
    row_id = data['row_id']
    if field == 'stock' and value == '':
        value = 0

    try:
        # Retrieve the  OffersForPlacement object
        offer = OffersForPlacement.objects.get(id=row_id)

        if field == 'price' or field == 'stock':
            # Update the specified field with the new value
            setattr(offer, field, value)
        elif field == 'face_to_face_trade':
            setattr(offer, field, True if value == 'face_to_face_trade' else False)

        offer.save()
        if field == 'stock':
            create_record_to_stock_history_table(row_id, 'start page change stock')

        offer_dict = model_to_dict(offer)
        logger.info(f"offer_dict__{offer_dict}")

        try:
            seller_id = get_seller_id_by_user_id(user_id)
            # Retrieve the TopPrices object
            show_price, interest_rate = get_float_price(offer_dict, seller_id)
        except TopPrices.DoesNotExist:
            # Handle the case where the TopPrices object does not exist
            new_price = 0

    except OffersForPlacement.DoesNotExist:
        # Handle the case where the OffersForPlacement object does not exist
        raise ValueError(f"OffersForPlacement with id {data['row_id']} does not exist.")

    return show_price


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
                                   double_minimal_mode_status=False,
                                   reserve_stock=0,
                                   order_status=False,
                                   )
    new_offer.save()


def delete_server_from_list(offer_id):
    offer = OffersForPlacement.objects.get(id=offer_id)
    create_record_to_stock_history_table(offer_id, ' delete function change status', active_rate=False)
    offer.delete()


def pause_offer(offer_id, action):
    offer = OffersForPlacement.objects.get(id=offer_id)
    server_id = offer.server_urls_id
    logger.info(f'server_id__{server_id}')

    if action == 'pause':
        setattr(offer, 'active_rate', 0)
        offer.save()
    elif action == 'resume':
        setattr(offer, 'active_rate', 1)
        offer.save()
        OffersForPlacement.objects.filter(server_urls_id=server_id).update(double_minimal_mode_status=False)

    create_record_to_stock_history_table(offer_id, 'start page change status')


def get_order_info(user_id):
    seller_id = Sellers.objects.get(auth_user_id=user_id)
    order_info = (SoldOrders.objects.filter(seller_id=seller_id,
                                            download_video_status=False,
                                            status='DELIVERING').
                  select_related('server').first())
    logger.info(f"order_info__{order_info}")
    if order_info is None:
        order_info = (InternalOrder.objects.filter(internal_seller=seller_id,
                                                   download_video_status=False,
                                                   status='DELIVERING').
                      select_related('server').first())
    logger.info(f"server_id__{order_info.server_id}, seller_id_{seller_id}") if order_info else None

    return order_info


def update_sold_order_when_video_download(user_id, sold_order, path_to_video, sent_gold):
    logger.info(f"sold_order_number__{sold_order}, path_to_video__{path_to_video}, sent_gold__{sent_gold}")
    seller_id = get_seller_id_by_user_id(user_id)
    delivery_method = sold_order.trade_mode
    logger.info(f"seller_id__{seller_id}")
    class_name = sold_order.__class__.__name__

    try:
        sold_order.path_to_video = path_to_video
        sold_order.sent_gold = sent_gold
        sold_order.download_video_status = True
        sold_order.charged_to_payment = True
        if class_name == 'InternalOrder':
            sold_order.status = 'DELIVERED'
        sold_order.save()
        logger.info('посилання на відео додано до бази даних')

        # Зараховуємо комісії до оплати
        commissions_crud.update_status_charged_to_payment_commission(sold_order.id)

        # Оновлюємо баланс продавця
        get_balance(user_id)
        update_owner_balance()
        update_technical_balance()

        # Перевірка на наявність інших замовлень перед зміною статусу
        exists_order = check_exists_another_order_before_change_order_status(sold_order.seller,
                                                                             sold_order.server,
                                                                             sold_order.sold_order_number)
        logger.info(f"exists_order__{exists_order}")
        if not exists_order:
            # Знаходимо запис у OffersForPlacement, пов'язаний із SoldOrders
            offer = OffersForPlacement.objects.filter(sellers=seller_id,
                                                      server_urls=sold_order.server,
                                                      order_status=True
                                                      ).first()

            if offer:
                offer.order_status = False
            offer.save()

            if delivery_method == 'Mail' and class_name == 'InternalOrder':
                message = (f'Замовлення  {sold_order.quantity} золота на сервері {sold_order.server.server_name}'
                           f' - {sold_order.server.game_name} відправлено по ігровій пошті, та надійде протягом години')
                buyer_tg = sold_order.internal_buyer.id_telegram
                buyer_name = sold_order.internal_buyer.auth_user.username
                logger.info(f"buyer_name__{buyer_name}")
                logger.info(f"buyer_tg__{buyer_tg}, delivery_method__{delivery_method}")
                send_messages_sync(buyer_tg, buyer_name, message)

            return f'статус активного замовлення на сервері змінено на False.'
        else:
            return (f'статус активного замовлення залишається True.'
                    f' Продавець має ще активні замовлення на цьому сервері')

    except SoldOrders.DoesNotExist:
        return f"Замовлення не знайдено"
    except Exception as e:
        return f"Помилка: {e}"


def get_sold_orders_for_history(user_id):
    try:
        seller_id = Sellers.objects.get(auth_user_id=user_id)
        sold_orders_history = SoldOrders.objects.filter(seller_id=seller_id, ).select_related('server')
    except Sellers.DoesNotExist:
        logger.error(f"Seller with auth_user_id {user_id} does not exist.")
    return sold_orders_history


def get_internal_orders_for_history(user_id):
    try:
        internal_orders = InternalOrder.objects.filter(
            Q(internal_seller__auth_user_id=user_id) | Q(internal_buyer__auth_user_id=user_id)
        ).select_related('server')
    except InternalOrder.DoesNotExist:
        logger.error(f"Seller with auth_user_id {user_id} does not exist.")

    return internal_orders


def get_orders_with_balance(user_id, sold_orders, internal_orders):
    # Об'єднуємо записи в один список
    all_orders = list(sold_orders) + list(internal_orders)

    # Сортуємо всі записи за часом створення
    all_orders.sort(key=lambda x: x.created_time)

    total_earned = 0  # Ініціалізуємо загальну суму
    orders_with_balance = []

    # Проходимо по відсортованих записах і оновлюємо баланс
    for order in all_orders:
        if isinstance(order, SoldOrders):
            # Обробка записів з SoldOrders
            if order.status == "CANCEL_REQUESTED":
                # Якщо статус "CANCEL_REQUESTED", пропускаємо зміну балансу
                orders_with_balance.append({
                    'order': order,
                    'current_balance': total_earned,  # Записуємо попередній баланс
                    'type': 'sold_order',  # Додаємо тип для розрізнення записів
                    'status': 'CANCEL_REQUESTED'  # Додаємо статус для інформації
                })
            else:
                if not order.paid_in_salary:
                    total_earned += decimal.Decimal(order.earned_without_admins_commission)
                orders_with_balance.append({
                    'order': order,
                    'current_balance': total_earned,
                    'type': 'sold_order'  # Додаємо тип для розрізнення записів
                })
        elif isinstance(order, InternalOrder):
            # Обробка записів з InternalOrder
            if order.status == "CANCEL_REQUESTED":
                # Якщо статус "CANCEL_REQUESTED", пропускаємо зміну балансу
                orders_with_balance.append({
                    'order': order,
                    'current_balance': total_earned,  # Записуємо попередній баланс
                    'type': 'internal_order',  # Додаємо тип для розрізнення записів
                    'status': 'CANCEL_REQUESTED'  # Додаємо статус для інформації
                })
            else:
                if order.internal_seller.auth_user_id == user_id:
                    # Якщо користувач є продавцем, додаємо earned_without_admins_commission
                    total_earned += decimal.Decimal(order.earned_without_admins_commission)
                    orders_with_balance.append({
                        'order': order,
                        'current_balance': total_earned,
                        'type': 'internal_order'  # Додаємо тип для розрізнення записів
                    })
                elif order.internal_buyer and order.internal_buyer.auth_user_id == user_id:
                    # Якщо користувач є покупцем, змінюємо total_amount на від'ємне
                    order.total_amount = decimal.Decimal(-order.total_amount)  # Змінюємо значення на від'ємне
                    order.earned_without_admins_commission = float(order.total_amount)
                    total_earned += decimal.Decimal(order.total_amount)  # Додаємо від'ємне значення до балансу
                    orders_with_balance.append({
                        'order': order,
                        'current_balance': total_earned,
                        'type': 'internal_order'  # Додаємо тип для розрізнення записів
                    })
    return orders_with_balance


def get_server_id(user_id):
    seller_id = Sellers.objects.get(auth_user_id=user_id)
    try:
        order_info = SoldOrders.objects.get(seller_id=seller_id, download_video_status=False)
        server_id = order_info.server_id
    except SoldOrders.DoesNotExist:
        return f"Замовлення не знайдено"
    except Exception as e:
        return f"Помилка: {e}"
    return server_id


def create_video_filename(request, sold_order_number):
    seller_id = get_seller_id_by_user_id(request.user.id)
    sold_order = (SoldOrders.objects.filter(sold_order_number=sold_order_number,
                                            seller_id=seller_id)
                  .select_related('server').first())
    logger.info(f"sold_order__{sold_order}")

    if sold_order is None:
        sold_order = (InternalOrder.objects.filter(sold_order_number=sold_order_number,
                                                   internal_seller=seller_id)
                      .select_related('server').first())
        logger.info(f"sold_order__{sold_order}")

    sent_gold = request.POST.get('sent_gold')
    seller = request.user

    server = sold_order.server.server_name
    game = sold_order.server.game_name
    current_time = datetime.now().strftime("%Y-%m-%d___%H-%M")

    filename = f"{seller}__{sent_gold}__{server}__{game}__{sold_order_number}__{current_time}.mp4"
    logger.info(filename)
    return filename, sold_order


def get_seller_id_by_user_id(user_id):
    try:
        seller = Sellers.objects.get(auth_user_id=user_id)
    except Sellers.DoesNotExist:
        logger.error(f"Seller with auth_user_id {user_id} does not exist.")
    return seller.id


def get_balance(user_id):
    if user_id == owner_user_and_seller_id:
        return update_owner_balance()
    if user_id == technical_user_and_seller_id:
        return update_technical_balance()
    try:
        seller = get_seller_id_by_user_id(user_id)
        logger.info(f"user_id__{user_id}, seller_id__{seller}")
    except Sellers.DoesNotExist:
        logger.error(f"Seller with auth_user_id {user_id} does not exist.")
        return 0

    total_received_from_orders = calculate_seller_owner_technical_earning_from_orders(seller)
    spend_internal_market = get_sum_spend_internal_market(seller)

    # 2. Баланс із CommissionBreakdown (тільки для Delivered лотів)
    commission_earned = commissions_crud.get_breakdown_commissions(seller)
    total_balance = decimal.Decimal(total_received_from_orders) + decimal.Decimal(commission_earned) - decimal.Decimal(
        spend_internal_market)

    # If no records are found, total_earned will be None. Set it to 0 in that case.
    if total_balance is None:
        total_balance = 0

    Sellers.objects.filter(id=seller).update(balance=total_balance)

    logger.info(f"seller_total_balance_{total_balance}")
    return round(total_balance, 2)


def update_owner_balance():
    # Step 1: Calculate the total earned_without_admins_commission for the specific seller
    total_received_from_orders = calculate_seller_owner_technical_earning_from_orders(owner_user_and_seller_id)

    # If no records are found, total_earned will be None. Set it to 0 in that case.
    total_received_from_orders = 0 if total_received_from_orders is None else total_received_from_orders
    logger.info(f"total_received_from_orders{total_received_from_orders}")

    # 2. Баланс із CommissionBreakdown
    commission_earned = commissions_crud.get_breakdown_commissions(owner_user_and_seller_id)
    total_balance = decimal.Decimal(total_received_from_orders) + decimal.Decimal(commission_earned)

    Sellers.objects.filter(id=owner_user_and_seller_id).update(balance=total_balance)

    logger.info('Balance updated successfully.')
    return round(total_balance, 2)


def update_technical_balance():
    # Step 1: Calculate the total earned_without_admins_commission for the specific seller
    total_received_from_orders = calculate_seller_owner_technical_earning_from_orders(technical_user_and_seller_id)

    # If no records are found, total_earned will be None. Set it to 0 in that case.
    total_received_from_orders = 0 if total_received_from_orders is None else total_received_from_orders

    # 2. Баланс із CommissionBreakdown (тільки для Delivered лотів)
    commission_earned = commissions_crud.get_breakdown_commissions(technical_user_and_seller_id)
    total_balance = decimal.Decimal(total_received_from_orders) + decimal.Decimal(commission_earned)

    Sellers.objects.filter(id=technical_user_and_seller_id).update(balance=total_balance)

    return round(total_balance, 2)


def change_offer_stock_when_create_order(server_id, seller_id, order_quantity):
    offer = OffersForPlacement.objects.get(server_urls_id=server_id, sellers_id=seller_id)
    offer.stock -= order_quantity
    offer.save()
    logger.info("Stock updated successfully.")
    create_record_to_stock_history_table(offer.id, 'change stock from order')


def create_record_to_stock_history_table(row_id, description, active_rate=None):
    offer = OffersForPlacement.objects.get(id=row_id)
    stock_row = ChangeStockHistory.objects.create(
        seller_id=offer.sellers.id,
        server_id=offer.server_urls.id,
        stock=offer.stock,
        active_rate_record=offer.active_rate if active_rate is None else active_rate,
        description=description,
        created_time=timezone.now()
    )
    stock_row.save()
    logger.info("New record to stock table created.")


def calculate_seller_owner_technical_earning_from_orders(seller_id):
    if seller_id == owner_user_and_seller_id or seller_id == technical_user_and_seller_id:
        query_filter_sold_orders = (Q(charged_to_payment=True) & Q(paid_to_technical=False)
                                    & (Q(status='DELIVERED') | Q(status='COMPLETED')))

        query_filter_internal_orders = (Q(charged_to_payment=True) & Q(paid_to_technical=False)
                                        & (Q(status='DELIVERED') | Q(status='COMPLETED')))

        if seller_id == owner_user_and_seller_id:
            target_field = 'owner_commission'
        elif seller_id == technical_user_and_seller_id:
            target_field = 'technical_commission'
    else:
        query_filter_sold_orders = (Q(charged_to_payment=True)
                                    & Q(paid_in_salary=False)
                                    & Q(seller_id=seller_id)
                                    & (Q(status='DELIVERED') | Q(status='COMPLETED') | Q(status='DELIVERING')))
        query_filter_internal_orders = (Q(charged_to_payment=True)
                                        & Q(paid_in_salary=False)
                                        & Q(internal_seller=seller_id)
                                        & (Q(status='DELIVERED') | Q(status='COMPLETED') | Q(status='DELIVERING')))
        target_field = 'earned_without_admins_commission'

    sold_orders_earned = SoldOrders.objects.filter(query_filter_sold_orders).aggregate(
        total_earned=Sum(target_field))['total_earned']
    if sold_orders_earned is None:
        sold_orders_earned = 0

    logger.info(f"sold_orders_earned__{sold_orders_earned}")

    internal_market_earned = InternalOrder.objects.filter(query_filter_internal_orders).aggregate(
        total_earned=Sum(target_field))['total_earned']
    if internal_market_earned is None:
        internal_market_earned = 0

    logger.info(f"internal_market_earned__{internal_market_earned}")

    total_balance = decimal.Decimal(sold_orders_earned) + decimal.Decimal(internal_market_earned)
    return total_balance


def get_sum_spend_internal_market(seller_id):
    result = InternalOrder.objects.filter(internal_buyer=seller_id).aggregate(
        total_spend=Sum('total_amount'))
    internal_market_spend = result.get('total_spend', 0)

    if internal_market_spend is None:
        internal_market_spend = 0
    logger.info(f"internal_market_spend__{internal_market_spend}")
    return internal_market_spend
