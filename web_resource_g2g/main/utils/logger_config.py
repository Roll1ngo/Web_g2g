import logging.handlers
import logging
import os
import sys
import coloredlogs

max_bytes = 1024 * 1024 * 1024  # 1 GB
backup_count = 1

# Create a logger instance
logger = logging.getLogger(__name__)

# Set the logging level to DEBUG to capture all messages
logger.setLevel(logging.INFO)

# Get the path to the executable file
# Отримання шляху до кореня проєкту
root_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Формування шляху до файлу логування
log_file_path = os.path.join(root_path, "front_server.ans")

# Create a file handler using the `logging.handlers` module
file_handler = logging.handlers.RotatingFileHandler(
    log_file_path,
    maxBytes=max_bytes,
    backupCount=backup_count
)

# Formatter for the file
file_formatter = logging.Formatter(
    '\033[1;32m%(asctime)s - %(levelname)s -'
    ' \033[1;33m%(module)s\033[1;32m.\033[1;34m%(funcName)s\033[1;32m:%(lineno)d - %(message)s\033[0m'
)
file_handler.setFormatter(file_formatter)

# Add the file handler to the logger
logger.addHandler(file_handler)

# Console colored output configuration
coloredlogs.install(level='INFO',
                    fmt='\033[1;32m%(asctime)s - %(levelname)s -'
                        ' \033[1;33m%(module)s\033[1;32m.\033[1;34m%(funcName)s\033[1;32m:%(lineno)d - %(message)s\033[0m',
                    datefmt='%H:%M:%S')


# Logging uncaught exceptions
def handle_exception(exc_type, exc_value, exc_traceback):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    # Log all uncaught exceptions as critical errors with full traceback
    logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))


# Override default exception hook
sys.excepthook = handle_exception

