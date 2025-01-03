import json
import os
import time

from django.conf import settings
from django.contrib import messages
from django.http import JsonResponse, HttpResponseNotAllowed, HttpResponse
from django.shortcuts import render, redirect
from . import crud
from .utils.logger_config import logger


def start_page(request):
    if request.method == 'GET':
        user_id = request.user.id
        all_bets = crud.get_main_data_from_table(user_id)

        servers = crud.query_servers()
        games = set(server.game_name for server in servers)
        regions = set(server.region for server in servers)

        grouped_data_db = crud.get_grouped_data(servers)
        grouped_data = json.dumps(grouped_data_db)

        double_add = json.dumps([{'server_name': server['server_name'],
                                  'game_name': server['game_name']} for server in all_bets])

        return render(request, 'main/index.html', context={"bets_list": all_bets,
                                                           'games': games,
                                                           'regions': regions,
                                                           'servers_json': grouped_data,
                                                           'double_add': double_add
                                                           })


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

        add_server_info['auth_user_id'] = request.user.id
        logger.info(f"add_server_info__{add_server_info}")
        crud.add_server_to_db(add_server_info)

    return JsonResponse({'success': True})


def handle_option_change(request):
    logger.info("inside handle_option_change")
    payload = json.loads(request.body)
    offer_id = payload["row_id"]
    action = payload["action"]
    logger.info(f'Change option__{action} for__{offer_id},')
    if action == 'delete':
        crud.delete_server_from_list(offer_id)
    else:
        crud.pause_offer(offer_id, action)
    return JsonResponse({'success': True})


def show_order_info(request, server_id):
    order_info = crud.get_order_info(server_id)
    return render(request, 'main/show_order_info.html', context={"order_info": order_info,
                                                                 "server_id": server_id})


def upload_video(request, server_id):
    logger.info(f"server_id__{server_id}")
    if request.method == 'POST':
        if 'video' in request.FILES:
            video_file = request.FILES['video']
            try:
                # Збереження файлу
                filename = video_file.name
                filepath = os.path.join(settings.MEDIA_ROOT, 'videos', filename)  # Шлях до папки videos
                with open(filepath, 'wb+') as destination:
                    for chunk in video_file.chunks():
                        destination.write(chunk)
                logger.info(f"filepath__{filepath}")
                crud.update_sold_order_when_video_download(server_id, filepath)

                # # Створення запису в базі даних
                # video = Video(title=filename, video_file=os.path.join('videos', filename))
                # video.save()

                # messages.success(request, 'Відео успішно завантажено!')
                logger.info('before redirect')
                return redirect('main:start_page')
            except Exception as e:
                messages.success(request, 'Error saving video')
        else:
            messages.error(request, 'Будь ласка, виберіть файл.')
