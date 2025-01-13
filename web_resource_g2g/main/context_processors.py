from . crud import get_balance


def user_balance(request):
    if request.user.is_authenticated:
        balance = get_balance(request.user.id)
        return {'user_balance': balance}
    return {}
