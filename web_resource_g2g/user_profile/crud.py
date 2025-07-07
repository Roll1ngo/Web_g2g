from django.contrib.auth import get_user_model

from main.models import Sellers
from main import crud as main_crud
from main.utils.logger_config import logger
from user_profile.models import WithdrawalRequest
User = get_user_model() # Отримуємо поточну модель користувача

def get_withdrawal_user_info(user_id):
    user = User.objects.get(id=user_id)
    withdrawal_info = WithdrawalRequest.objects.filter(user=user).order_by('-created_at').first()
    return withdrawal_info

def record_balance_before_withdrawal(seller_ids:list):

    for seller_id in seller_ids:
        user = Sellers.objects.get(id=seller_id).auth_user
        user_balance = main_crud.get_balance(user.id)
        logger.info(f"Balance for user {user.username} is {user_balance}")
        try:
            user_withdrawal = WithdrawalRequest.objects.get(user=user)
        except WithdrawalRequest.DoesNotExist:
            logger.info(f"No balance record for user {user.username}")
        user_withdrawal.amount = user_balance
        user_withdrawal.save()
        logger.info(f"Balance for user {user.username} record to Withdrawal Table.")


