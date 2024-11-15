import json
import time

from django.http import JsonResponse, HttpResponseNotAllowed, HttpResponse
from django.shortcuts import render, redirect
from . import crud
from .utils.logger_config import logger


def start_page(request):
    if request.method == 'GET':
        all_bets = crud.get_main_data_from_table()

        servers = crud.query_servers()
        games = set(server.game_name for server in servers)
        regions = set(server.region for server in servers)
        server_data = []
        for server in servers:
            server_data.append({
                'game_name': server.game_name,
                'region': server.region,
                'server_name': server.server_name
            })

        # Групуємо дані за грою та регіоном
        grouped_data = {}
        for data in server_data:
            game = data['game_name']
            region = data['region']
            if game not in grouped_data:
                grouped_data[game] = {}
            if region not in grouped_data[game]:
                grouped_data[game][region] = []
            grouped_data[game][region].append(data['server_name'])

        return render(request, 'main/index.html', context={"bets_list": all_bets,
                                                           'games': games,
                                                           'regions': regions,
                                                           'servers_json': json.dumps(grouped_data)})


def update_table_data(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        logger.info(data)
        new_price = crud.update_data(data)
        logger.info(new_price)
        return JsonResponse({'success': True, 'new_price': new_price})
    return HttpResponseNotAllowed(['POST'])


def add_server(request):
    if request.method == 'POST':
        add_server_info = json.loads(request.body)
        logger.info(f"add_server_info__{add_server_info}")
        return JsonResponse({'success': True})


def about(request):
    return render(request, "main/about.html")
