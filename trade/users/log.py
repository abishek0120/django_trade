import logging
import os
from django.conf import settings

LOG_FILE = os.path.join(settings.BASE_DIR, "trading_bot.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger("trading_bot")
