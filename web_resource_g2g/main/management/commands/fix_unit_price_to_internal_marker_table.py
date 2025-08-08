from decimal import Decimal, DivisionByZero
from django.core.management.base import BaseCommand
from internal_market.models import InternalOrder  # заміни your_app на свій додаток


class Command(BaseCommand):
    help = "Оновлює поле price_unit для всіх замовлень"

    def handle(self, *args, **options):
        orders = InternalOrder.objects.all()
        updated_count = 0

        for order in orders:
            if order.total_amount and order.total_amount != 0:
                try:
                    order.price_unit = (
                        Decimal(order.earned_without_admins_commission) /
                        Decimal(order.quantity)
                    )
                    order.save(update_fields=['price_unit'])
                    updated_count += 1
                except DivisionByZero:
                    pass
            else:
                order.price_unit = Decimal(0)
                order.save(update_fields=['price_unit'])

        self.stdout.write(
            self.style.SUCCESS(f"✅ Оновлено {updated_count} записів із {orders.count()}")
        )
