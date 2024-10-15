from . models import OffersForPlacement, ServerUrls, Sellers, TopPrices


def get_offers_list():
    data = OffersForPlacement.objects.all()
