
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from django.forms import model_to_dict
from django.utils import timezone

from internal_market.models import InternalOrder
from .models import (OffersForPlacement, ServerUrls, Sellers, TopPrices,
                     SoldOrders, SellerServerInterestRate, ChangeStockHistory, CommissionBreakdown,
                     CommissionRates)
from django.db.models import F, Sum, DecimalField, Q
from .utils.logger_config import logger
from main import crud


def get_my_service_list(user_id):
    my_services = CommissionBreakdown.objects.filter(seller__auth_user_id=user_id)
    return my_services


def get_global_commissions_rates():
    rates = CommissionRates.objects.first()
    commissions = {
        "exchange": rates.exchange,
        "renter_lvl1": rates.renter_lvl1,
        "renter_lvl2": rates.renter_lvl2,
        "mentor": rates.mentor,
        "owner": rates.owner,
        "technical": rates.technical,
        "recruiter": rates.recruiter
    }
    return commissions


def get_interest_rate_by_seller_id(seller_id, server_id):
    # Отримання `interest_rate` з `Sellers`
    try:
        seller_rate = SellerServerInterestRate.objects.filter(seller_id=seller_id, server_id=server_id).first()
        if not seller_rate or seller_rate.interest_rate is None:
            interest_rate = 0
            logger.info(f"Ставка відсутня для seller_id={seller_id} та server_id={server_id}.")
            return interest_rate
    except ObjectDoesNotExist:
        logger.error(f"Запис SellerServerInterestRate не знайдено для seller_id={seller_id} та server_id={server_id}.")
        return None
    return seller_rate.interest_rate


def get_renter_info(seller_id, server_id):
    try:
        renter_info = SellerServerInterestRate.objects.get(seller=seller_id, server=server_id)

        # Перетворюємо об'єкт на словник
        renter_info_dict = model_to_dict(renter_info)

        lvl1 = renter_info_dict.get('renter_lvl1')
        lvl2 = renter_info_dict.get('renter_lvl2')
        if lvl1:
            return {'renter_lvl1': lvl1}
        elif lvl2:
            return {'renter_lvl2': lvl2}
        else:
            return {}
    except SellerServerInterestRate.DoesNotExist:
        logger.error(f"Запис SellerServerInterestRate не знайдено для seller_id={seller_id} та server_id={server_id}.")


def get_seller_services_info(seller_id, server_id):
    renter_info = get_renter_info(seller_id, server_id)

    mentor_recruiter_from_seller = Sellers.objects.get(id=seller_id)
    if mentor_recruiter_from_seller is None:
        logger.warning(f"No seller found with ID: {seller_id}")
        return None  # Or raise an exception if appropriate

    mentor_recruiter_from_seller_info_dict = model_to_dict(mentor_recruiter_from_seller)
    mentor_recruiter_from_seller_info_dict.update(renter_info)

    return mentor_recruiter_from_seller_info_dict


def get_breakdown_commissions(seller_id):
    commission_earned = CommissionBreakdown.objects.filter(
        seller=seller_id,
        charged_to_payment_commission=True,
        paid_in_salary_commission=False
    ).aggregate(total_commission=Sum('amount'))['total_commission'] or 0
    logger.info(f"seller_id__{seller_id}, commission_earned__{commission_earned}")
    return commission_earned


def calculate_owner_technical_commissions(seller_id, server_id, total_amount, exist_exchange_commission=True):
    logger.info(f"seller_id__{seller_id}, server_id__{server_id}, total_amount__{total_amount}")
    global_commissions_rates = get_global_commissions_rates()
    exchange_commission = Decimal(global_commissions_rates['exchange'])
    technical_commission = Decimal(global_commissions_rates['technical'])
    owner_commission = Decimal(global_commissions_rates['owner'])
    seller_interest_rate = get_interest_rate_by_seller_id(seller_id, server_id)

    # Обчислюємо значення за формулами
    if exist_exchange_commission:
        to_be_earned_without_exchange_commission = total_amount * (Decimal(1) - exchange_commission / Decimal(100))
    else:
        to_be_earned_without_exchange_commission = total_amount
    earned_without_service_commission = to_be_earned_without_exchange_commission * (
            seller_interest_rate / Decimal(100))
    technical_commission = to_be_earned_without_exchange_commission * (
            technical_commission / Decimal(100))
    owner_commission = to_be_earned_without_exchange_commission * (
            owner_commission / Decimal(100))

    return (round(to_be_earned_without_exchange_commission, 3), round(earned_without_service_commission,3),
            round(technical_commission, 3), round(owner_commission, 3), seller_interest_rate)


def calculate_and_record_mentor_renter_recruiter_commissions(seller_id, server_id,
                                                             quantity_cost, order_number, internal_order=False):
    # Отримуємо словник з інформацією про послуги якими користується продавець та кто їх надає
    seller_services_info = get_seller_services_info(seller_id, server_id)
    logger.info(f"seller_services_info__{seller_services_info}")

    # Отримуємо словник для продавця з послугами та вартістю кожної для цього замовлення
    commissions_service_providers = calculate_commissions_for_service_providers(seller_services_info,
                                                                                quantity_cost)
    logger.info(f"commissions_values__{commissions_service_providers}")

    # Чистий відсоток продавця після віднімання комісій
    seller_total_rate = calculate_seller_total_rate(seller_id, server_id)
    logger.info(f"seller_total_rate__{seller_total_rate}")

    record_commissions_service_providers(seller_services_info, commissions_service_providers,
                                         order_number, seller_id, internal_order)


def calculate_commissions_for_service_providers(seller_services_info, quantity_cost):
    # Отримуємо словник з комісіями за послуги
    commissions = get_global_commissions_rates()

    # Створюємо словник для збереження комісій
    commissions_service_providers = {}

    # Обчислюємо комісії для кожного сервісного провайдера
    if seller_services_info.get('mentor') is not None:
        mentor_commission = commissions.get('mentor', Decimal('0.0'))
        commissions_service_providers['mentor'] = round(quantity_cost * mentor_commission / Decimal('100.0'), 6)

    if seller_services_info.get('renter_lvl1') is not None:
        renter_lvl1_commission = commissions.get('renter_lvl1', Decimal('0.0'))
        commissions_service_providers['renter_lvl1'] = round(quantity_cost * renter_lvl1_commission / Decimal('100.0'),
                                                             6)

    if seller_services_info.get('renter_lvl2') is not None:
        renter_lvl2_commission = commissions.get('renter_lvl2', Decimal('0.0'))
        commissions_service_providers['renter_lvl2'] = round(quantity_cost * renter_lvl2_commission / Decimal('100.0'),
                                                             6)

    if seller_services_info.get('recruiter') is not None:
        recruiter_commission = commissions.get('recruiter', Decimal('0.0'))
        commissions_service_providers['recruiter'] = round(quantity_cost * recruiter_commission / Decimal('100.0'), 6)

    return commissions_service_providers


def calculate_seller_total_rate(seller_id, server_id):
    seller_services_info = get_seller_services_info(seller_id, server_id)
    commissions = get_global_commissions_rates()

    # Початкова комісія (100%)
    seller_total_rate = Decimal('100.0')

    # Віднімаємо обов'язкові комісії (власник та технічна комісія)
    seller_total_rate -= commissions.get('owner', Decimal('0.0'))
    seller_total_rate -= commissions.get('technical', Decimal('0.0'))

    # Віднімаємо комісії, якщо вони існують
    if seller_services_info.get('mentor') is not None:
        seller_total_rate -= commissions.get('mentor', Decimal('0.0'))

    if seller_services_info.get('renter_lvl1') is not None:
        seller_total_rate -= commissions.get('renter_lvl1', Decimal('0.0'))

    if seller_services_info.get('renter_lvl2') is not None:
        seller_total_rate -= commissions.get('renter_lvl2', Decimal('0.0'))

    if seller_services_info.get('recruiter') is not None:
        seller_total_rate -= commissions.get('recruiter', Decimal('0.0'))

    return seller_total_rate


def update_status_charged_to_payment_commission(order_id):
    CommissionBreakdown.objects.filter(object_id=order_id).update(charged_to_payment_commission=True)
    logger.info("Status paid_in_salary_commission updated successfully.")


def update_status_paid_in_salary_commission(user_id):
    seller_id = Sellers.objects.get(auth_user_id=user_id)
    CommissionBreakdown.objects.filter(seller_id=seller_id).update(paid_in_salary_commission=True)
    logger.info("Status paid_in_salary_commission updated successfully.")


def record_commissions_service_providers(seller_services_info, commissions_service_providers,
                                         order_number, seller_id, internal_order):
    try:
        # Отримуємо об'єкт замовлення
        if internal_order:
            order_id = InternalOrder.objects.get(sold_order_number=order_number, internal_seller=seller_id)
        else:
            order_id = SoldOrders.objects.get(sold_order_number=order_number, seller_id=seller_id)

        logger.info(f"order_id__{order_id}")
        logger.info(f"seller_services_info__{seller_services_info}")
        logger.info(f"commissions_service_providers__{commissions_service_providers}")

        # Створюємо записи для кожного service_provider
        for service_provider, commission in commissions_service_providers.items():
            # Перевіряємо, чи існує service_provider у seller_services_info
            if service_provider not in seller_services_info:
                logger.error(f"Service provider '{service_provider}' not found in seller_services_info.")
                continue

            # Отримуємо продавця
            try:
                seller = Sellers.objects.get(id=seller_services_info[service_provider])
            except Sellers.DoesNotExist:
                logger.error(f"Seller with id {seller_services_info[service_provider]} not found.")
                continue

            # Створюємо запис у CommissionBreakdown
            CommissionBreakdown.objects.create(
                order=order_id,
                seller=seller,
                service_type=service_provider,
                amount=commission,
                charged_to_payment_commission=False,
                paid_in_salary_commission=False,
                created_time=timezone.now()
            )

    except ObjectDoesNotExist as e:
        logger.error(f"Order not found: {e}")
    except Exception as e:
        logger.error(f"An error occurred: {e}")

def remove_commission_record(sold_order_id):
    logger.info(f"sold_order_id: {sold_order_id}")
    content_type = ContentType.objects.get_for_model(SoldOrders)
    CommissionBreakdown.objects.filter(object_id=sold_order_id,
                                       content_type = content_type).delete()