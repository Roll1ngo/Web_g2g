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
from .utils.logger_config import logger
from main import calculate_commissions_crud as commissions_crud

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
    other_orders_exist = SoldOrders.objects.filter(server_id=server_id,
                                                   seller_id=seller_id,
                                                   download_video_status=False
                                                   ).exclude(
                                                   sold_order_number=sold_order_number
                                                   ).exists()

    return other_orders_exist


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
            # #Шукаємо стратегію на активному лоті такого ж сервера
            current_strategy = OffersForPlacement.objects.filter(
                server_urls=row['server_urls'],
                active_rate=True
            ).exclude(sellers=row['sellers']).values_list('price', flat=True).first()

            if current_strategy:
                ballance_strategy_for_all = 'mean10_lot'
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
            update_stock_table(row_id, 'change stock')

        offer_dict = model_to_dict(offer)
        logger.info(f"offer_dict__{offer_dict}")

        try:
            # Retrieve the TopPrices object
            show_price, interest_rate = get_float_price(offer_dict, user_id)
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
    update_stock_table(offer_id, 'Change status')


def get_order_info(user_id):
    seller_id = Sellers.objects.get(auth_user_id=user_id)
    order_info = (SoldOrders.objects.filter(seller_id=seller_id,
                                            download_video_status=False,
                                            status='DELIVERING').
                  select_related('server').first())

    logger.info(f"server_id__{order_info.server_id}, seller_id_{seller_id}") if order_info else None

    return order_info


def update_sold_order_when_video_download(user_id, order_number, path_to_video, sent_gold):
    logger.info(f"sold_order_number__{order_number}, path_to_video__{path_to_video}, sent_gold__{sent_gold}")
    seller_id = Sellers.objects.get(auth_user_id=user_id)
    try:
        with transaction.atomic():  # Забезпечує цілісність транзакції
            # Оновлюємо статуси у SoldOrders
            sold_order = SoldOrders.objects.get(sold_order_number=order_number, seller_id=seller_id.id)
            sold_order.path_to_video = path_to_video
            sold_order.sent_gold = sent_gold
            sold_order.download_video_status = True
            sold_order.charged_to_payment = True
            sold_order.save()
            logger.info('посилання на відео додано до бази даних')

            # Зараховуємо комісії до оплати
            commissions_crud.update_status_charged_to_payment_commission(sold_order.id)

            # Оновлюємо баланс продавця
            update_seller_balance(user_id)
            update_owner_balance()
            update_technical_balance()

            # Перевірка на наявність інших замовлень перед зміною статусу
            exists_order = check_exists_another_order_before_change_order_status(seller_id,
                                                                                 sold_order.server,
                                                                                 order_number)
            if not exists_order:
                # Знаходимо запис у OffersForPlacement, пов'язаний із SoldOrders
                offer = OffersForPlacement.objects.filter(sellers=sold_order.seller,
                                                          server_urls=sold_order.server,
                                                          order_status=True
                                                          ).first()

                if offer:
                    offer.order_status = False
                offer.save()

                return f'статус активного замовлення на сервері змінено на False.'
            else:
                return (f'статус активного замовлення залишається True.'
                        f' Продавець має ще активні замовлення на цьому сервері')

    except SoldOrders.DoesNotExist:
        return f"Замовлення не знайдено"
    except Exception as e:
        return f"Помилка: {e}"


def get_orders_history(user_id):
    try:
        seller_id = Sellers.objects.get(auth_user_id=user_id)
        orders_history = SoldOrders.objects.filter(seller_id=seller_id, ).select_related('server')
    except Sellers.DoesNotExist:
        logger.error(f"Seller with auth_user_id {user_id} does not exist.")
    return orders_history


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
    logger.info('inside')
    sold_order = SoldOrders.objects.filter(sold_order_number=sold_order_number, ).select_related('server').first()
    sent_gold = request.POST.get('sent_gold')
    seller = request.user

    server = sold_order.server.server_name
    game = sold_order.server.game_name
    current_time = datetime.now().strftime("%Y-%m-%d___%H-%M")

    filename = f"{seller}__{sent_gold}__{server}__{game}__{sold_order_number}__{current_time}.mp4"
    logger.info(filename)
    return filename


def get_balance(user_id):
    logger.info("inside get_balance")
    if user_id == owner_user_and_seller_id:
        return update_owner_balance()
    if user_id == technical_user_and_seller_id:
        return update_technical_balance()
    try:
        seller_id = get_seller_id_by_user_id(user_id)
        logger.info(f"user_id__{user_id}, seller_id__{seller_id}")
    except Sellers.DoesNotExist:
        logger.error(f"Seller with auth_user_id {user_id} does not exist.")
        return 0

    total_earned = SoldOrders.objects.filter(
        seller_id=seller_id,
        charged_to_payment=True,
        paid_in_salary=False,
    ).aggregate(total_earned=Sum('earned_without_admins_commission'))['total_earned']

    if total_earned is None:
        total_earned = 0
    elif not isinstance(total_earned, (int, float)):
        try:
            total_earned = float(total_earned)
        except (ValueError, TypeError):
            total_earned = 0

    # 2. Баланс із CommissionBreakdown (тільки для Delivered лотів)
    commission_earned = commissions_crud.get_breakdown_commissions(seller_id)
    total_balance = float(total_earned) + float(commission_earned)

    # If no records are found, total_earned will be None. Set it to 0 in that case.
    if total_balance is None:
        total_balance = 0

    Sellers.objects.filter(id=seller_id).update(balance=total_balance)

    logger.info(f"seller_total_balance_{total_balance}")
    return round(total_balance, 2)


def get_seller_id_by_user_id(user_id):
    seller = Sellers.objects.get(auth_user_id=user_id)
    return seller.id


def update_seller_balance(user_id):
    get_balance(user_id)

    return 'Seller balance updated successfully.'


def update_owner_balance():
    target_field = 'owner_commission'
    # Step 1: Calculate the total earned_without_admins_commission for the specific seller
    total_earned = SoldOrders.objects.filter(
        charged_to_payment=True,
        paid_to_owner=False
    ).aggregate(total_earned=Sum(target_field, output_field=DecimalField()))['total_earned']

    # If no records are found, total_earned will be None. Set it to 0 in that case.
    total_earned = 0 if total_earned is None else total_earned
    logger.info(f"technical_sum_total_earned__{total_earned}")

    # 2. Баланс із CommissionBreakdown
    commission_earned = commissions_crud.get_breakdown_commissions(owner_user_and_seller_id)
    total_balance = float(total_earned) + float(commission_earned)

    Sellers.objects.filter(id=owner_user_and_seller_id).update(balance=total_balance)

    logger.info('Balance updated successfully.')
    return round(total_balance, 2)


def update_technical_balance():
    target_field = 'technical_commission'

    # Step 1: Calculate the total earned_without_admins_commission for the specific seller
    total_earned = SoldOrders.objects.filter(
        charged_to_payment=True,
        paid_to_technical=False
    ).aggregate(total_earned=Sum(target_field, output_field=DecimalField()))['total_earned']

    # If no records are found, total_earned will be None. Set it to 0 in that case.
    total_earned = 0 if total_earned is None else total_earned

    # 2. Баланс із CommissionBreakdown (тільки для Delivered лотів)
    commission_earned = commissions_crud.get_breakdown_commissions(technical_user_and_seller_id)
    total_balance = float(total_earned) + float(commission_earned)

    Sellers.objects.filter(id=technical_user_and_seller_id).update(balance=total_balance)

    return round(total_balance, 2)


def update_stock_table(row_id, description):
    offer = OffersForPlacement.objects.get(id=row_id)
    stock_row = ChangeStockHistory.objects.create(
        seller_id=offer.sellers.id,
        server_id=offer.server_urls.id,
        stock=offer.stock,
        active_rate_record=offer.active_rate,
        description=description,
        created_time=timezone.now()
    )
    stock_row.save()
    logger.info("New record to stock table created.")






