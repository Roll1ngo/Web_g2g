from django.utils.deprecation import MiddlewareMixin
from main.utils.logger_config import logger  # Імпортуйте ваш логер


# your_app/middleware.py
from django.utils.deprecation import MiddlewareMixin
from main.utils.logger_config import logger

class RefMiddleware(MiddlewareMixin):
    def process_request(self, request):
        """Зберігає параметр ref з URL у сесії та request"""
        if 'ref' in request.GET:
            ref = request.GET['ref']
            request.session['ref'] = ref
            request.ref = ref  # Додаємо безпосередньо до об'єкта request
            logger.info(f"Stored ref in session and request: {ref}")
        return None