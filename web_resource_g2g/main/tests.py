import os

import django

from web_resource_g2g.main.models import SoldOrders
from web_resource_g2g.main.utils.logger_config import logger

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_resource_g2g.settings')
django.setup()


def create_video_filename(request, sold_order_number):
    sold_order = (SoldOrders.objects.get(sold_order_number=sold_order_number)
                  .select_related('server'))
    sent_gold = request.POST.get('sent_gold')
    seller = request.user

    server = sold_order.server_name
    game = sold_order.game_name
    date = sold_order.created_time

    logger.info(f"{seller}_{server}_{game}_{date}_{sent_gold}.mp4")
    filename = f"{seller}_{server}_{game}_{date}_{sent_gold}.mp4"
    return filename


if __name__ == '__main__':
    print(create_video_filename(1, 22149958))
