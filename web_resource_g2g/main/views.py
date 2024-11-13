import json
import time

from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect
from .crud import get_main_data_from_table, update_data
from .utils.logger_config import logger


def start_page(request):
    if request.method == 'GET':
        all_bets = get_main_data_from_table()
        return render(request, 'main/index.html', context={"bets_list": all_bets})


def update_table_data(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        logger.info(data)
        new_price = update_data(data)
        logger.info(new_price)
        return JsonResponse({'success': True, 'new_price': new_price})
    return HttpResponseNotAllowed(['POST'])
