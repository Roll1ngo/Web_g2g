import json
from django.shortcuts import render
from main.utils.logger_config import logger
from internal_market import crud as internal_market_crud
from django.http import JsonResponse, HttpResponseNotAllowed, HttpResponse


def main_page(request):
    lots_for_sale = internal_market_crud.get_lots_for_sale(request.user.id)
    logger.info(f"lots_for_sale__{lots_for_sale}")
    return render(request, 'internal_market/internal_market_main.html',
                  context={"lots_for_sale": lots_for_sale})


def create_order_from_form(request):
    logger.info("inside create_order_from_form")
    data = json.loads(request.body)
    logger.info(f"order_details__{data}")
    return JsonResponse({'success': True})
