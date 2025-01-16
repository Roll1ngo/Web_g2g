from . crud import get_balance


def user_balance(request):
    if request.user.is_authenticated:
        try:
            balance = get_balance(request.user.id)
        except AttributeError:
            return f"Продавця не додано. Зверніться до адміністратора"
        return {'user_balance': balance}
    return {}
