import os
import sys
from django.core.wsgi import get_wsgi_application
from whitenoise import WhiteNoise

# Додаємо шлях до проекту
sys.path.insert(0, '/home/h70472c/public_html/Web_g2g/web_resource_g2g')

# Встановлюємо змінну середовища Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'web_resource_g2g.settings')

# Отримуємо WSGI-додаток
django_application = get_wsgi_application()

# Налаштовуємо WhiteNoise для обробки статики
application = WhiteNoise(
    django_application,
    root='/home/h70472c/public_html/Web_g2g/web_resource_g2g/staticfiles',
    prefix='/static/',
    max_age=31536000  # Кешування на 1 рік
)

# Додаткові шляхи до статики (якщо потрібно)
application.add_files('/home/h70472c/public_html/Web_g2g/web_resource_g2g/static', prefix='/static/')