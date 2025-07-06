from main.utils.privat_bank import get_current_privatbank_rate
from . crud import get_balance


def user_balance(request):
    if request.user.is_authenticated:
        try:
            balance = get_balance(request.user.id)
        except AttributeError:
            return f"Продавця не додано. Зверніться до адміністратора"
        return {'user_balance': balance}
    return {}

def privat_bank_rate(request):
    if request.user.is_authenticated:
        try:
            curs_usd = get_current_privatbank_rate()
        except AttributeError:
            return f"Продавця не додано. Зверніться до адміністратора"
        return {'privat_bank_rate': curs_usd}
    return {}