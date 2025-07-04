from django.contrib.auth import get_user_model
from archive_payments.models import WithdrawalArchive, ReservedFunds
from django.utils import timezone
from django.db import models

from main.models import Sellers
from main import crud as main_crud
from main.utils.logger_config import logger
from user_profile.models import WithdrawalRequest

User = get_user_model() # Отримуємо поточну модель користувача

def create_withdrawal_archive_record(paid_orders_data):
    """
    Створює записи в WithdrawalArchive на основі даних про оплачені замовлення
    та інформації з WithdrawalRequest.

    Args:
        paid_orders_data (list): Дані з функції mark_orders_and_commissions_as_paid у форматі:
            [{"seller_id": {"SoldOrders": [], "InternalOrder": [], "CommissionBreakdown": []}}]

    Returns:
        list: Список створених об'єктів WithdrawalArchive
    """
    created_archives = []

    for seller_data in paid_orders_data:
        for seller_id_str, orders_ids in seller_data.items():
            user_id = Sellers.objects.get(id=seller_id_str).auth_user_id
            balance = main_crud.get_balance(user_id)

            try:
                # Отримуємо останній активний запит на виведення для користувача
                withdrawal_request = WithdrawalRequest.objects.filter(
                    user_id=user_id,
                    status__in=['approved', 'pending']
                ).latest('created_at')

                # Створюємо архівний запис
                archive = WithdrawalArchive(
                    user_id=user_id,
                    amount=withdrawal_request.amount,
                    withdraw_type=withdrawal_request.withdraw_type,
                    payment_method=withdrawal_request.payment_method,
                    commission_rate=withdrawal_request.commission_rate,
                    withdrawal_date=timezone.now().date(),
                    payment_details=withdrawal_request.payment_details,
                    archived_sold_order_ids=orders_ids.get('SoldOrders', []),
                    archived_internal_order_ids=orders_ids.get('InternalOrder', []),
                    archived_commission_breakdown_ids=orders_ids.get('CommissionBreakdown', [])
                )

                archive.save()
                created_archives.append(archive)

                # Оновлюємо статус запиту на виведення на "completed"
                if withdrawal_request.status != 'completed':
                    withdrawal_request.status = 'completed'
                    withdrawal_request.save()

            except WithdrawalRequest.DoesNotExist:
                # Якщо немає активного запиту, створюємо архів з мінімальною інформацією
                archive = WithdrawalArchive(
                    user_id=user_id,
                    withdrawal_date=timezone.now().date(),
                    archived_sold_order_ids=orders_ids.get('SoldOrders', []),
                    archived_internal_order_ids=orders_ids.get('InternalOrder', []),
                    archived_commission_breakdown_ids=orders_ids.get('CommissionBreakdown', [])
                )
                archive.save()
                created_archives.append(archive)

    return created_archives


def create_withdrawal_reserver_record(user, withdrawal_request):
    ReservedFunds.objects.create(
        reserve_type='withdrawal',
        status='pending',
        user=user,
        amount=withdrawal_request.amount,  # Сума, яку потрібно зарезервувати

    )
    logger.info(
        f"Створено запис ReservedFunds для користувача {user.username} на суму {withdrawal_request.amount}")

def get_reserved_funds_amount(user_id):

    reserved_funds = ReservedFunds.objects.filter(user=User.objects.get(id=user_id),
                                                  reserve_type='withdrawal',
                                                  status__in=['pending', 'paid'])
    logger.info(f"reserved_funds__{reserved_funds} for user_id__{user_id}")
    if reserved_funds:
        amount = reserved_funds.aggregate(total_amount=models.Sum('amount'))['total_amount']
        logger.info(f"reserved_funds__{amount} for user_id__{user_id}")

        return amount
    else:
        logger.info(f"No reserved funds found for user_id__{user_id}")
        return 0