import sys
import os

from django.core.wsgi import get_wsgi_application


# Встановлюємо шлях до кореня проєкту
sys.path.insert(0, '/home/h70472c/public_html/Web_g2g/web_resource_g2g')
sys.path.insert(0, '/home/h70472c/public_html/Web_g2g/web_resource_g2g/web_resource_g2g')

# Встановлюємо змінну середовища Django
os.environ['DJANGO_SETTINGS_MODULE'] = 'web_resource_g2g.settings'

# Імпортуємо WSGI-додаток
application = get_wsgi_application()
