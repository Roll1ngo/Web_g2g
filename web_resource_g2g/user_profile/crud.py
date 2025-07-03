from django.contrib.auth import get_user_model
from user_profile.models import WithdrawalRequest
User = get_user_model() # Отримуємо поточну модель користувача

def get_withdrawal_user_info(user_id):
    user = User.objects.get(id=user_id)
    withdrawal_info = WithdrawalRequest.objects.filter(user=user).order_by('-created_at').first()
    return withdrawal_info