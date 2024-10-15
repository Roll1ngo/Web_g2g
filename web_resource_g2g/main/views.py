from django.shortcuts import render
from . models import OffersForPlacement
from . crud import get_offers_list


def start_page(request):
    all_bets = get_offers_list()
    print("Number of offers:", all_bets.count())
    return render(request, 'main/index.html', context={"bets_list": all_bets})
