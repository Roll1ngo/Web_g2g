import decimal
import json
from django.utils import timezone
from internal_market.models import InternalOrder
from main import models as main_models
from django.db.models import F, Sum, DecimalField, Q

from main.models import Sellers, ServerUrls, OffersForPlacement
from main.utils.logger_config import logger
from main import crud as main_crud
from main import calculate_commissions_crud as commissions_crud
from main.tg_bot_run import send_messages_sync


class InternalOrderProcessor:
    def __init__(self, create_order_message):
        self.main_crud = main_crud
        self.commissions_crud = commissions_crud
        self.send_messages_sync = send_messages_sync
        self.create_order_message = create_order_message
        self.logger = logger

    def get_lots_for_sale(self, auth_user_id: int):
        seller_id = self.main_crud.get_seller_id_by_user_id(auth_user_id)

        main_data = (
            main_models.OffersForPlacement.objects
            .select_related('server_urls')
            .annotate(
                game_name=F('server_urls__game_name'),
                region=F('server_urls__region'),
                server_name=F('server_urls__server_name'),
            ).exclude(sellers__auth_user__id=auth_user_id)
            .filter(active_rate=True, order_status=False)
            .order_by('server_name')
            .values(
                'id',
                'sellers',
                'server_urls',
                'currency',
                'description',
                'price',
                'stock',
                'min_units_per_order',
                'active_rate',
                'percent_offset',
                'duration',
                'face_to_face_trade',
                'mail_delivery',
                'auction_house',
                'delivery_online_hrs',
                'delivery_offline_hrs',
                'double_minimal_mode_status',
                'reserve_stock',
                'game_name',
                'region',
                'server_name',
                'order_status',
            )
        )
        main_data_float_price = []
        for row in main_data:
            try:
                row['strategy_price'] = row['price']
                stock = row['stock']
                if row['price']:
                    new_price, interest_rate = self.get_float_price(row)
                    row['price'] = new_price
                    row['interest_rate'] = interest_rate
                    row['full_cost'] = round(new_price * stock, 3)

                else:
                    row['price'] = None

                main_data_float_price.append(row)
            except (ValueError, TypeError) as e:
                self.logger.info(f"Error updating {row['server_name']}: {e}")
                continue
        return main_data_float_price

    def get_float_price(self, row):
        try:
            seller_id = row.get('sellers')
            currently_strategy = row.get('price')
            server_urls_id = row.get('server_urls')
            rang_exchange = float(self.commissions_crud.get_global_commissions_rates()['exchange'])
            interest_rate = self.commissions_crud.get_interest_rate_by_seller_id(seller_id, server_urls_id)

            if not currently_strategy or not server_urls_id:
                self.logger.error("Missing 'price' or 'server_urls' in row.")
                return None, None

            float_price = main_models.TopPrices.objects.filter(server_name=server_urls_id).values_list(
                currently_strategy, flat=True
            ).first()
            float_price_without_exchange = float_price * (1 - rang_exchange / 100)

            self.logger.warning(f"Відсутні ціни для сервера {server_urls_id}. Потрібен сеанс парсингу") \
                if float_price is None else None

            return round(float_price_without_exchange, 3), interest_rate

        finally:
            pass