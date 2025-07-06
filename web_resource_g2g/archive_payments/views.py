from django.shortcuts import render

# Create your views here.
def archive_payments_page(request):
    return render(request, 'archive_payments/archive_payments.html')