from django.shortcuts import render
from . crud import get_main_data_from_table
from . utils.logger_config import logger


def start_page(request):
    all_bets = get_main_data_from_table()
    logger.info("Hello")
    return render(request, 'main/index.html', context={"bets_list": all_bets})
