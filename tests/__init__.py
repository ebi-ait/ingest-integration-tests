import logging
import os

logging.basicConfig()
logger = logging.getLogger(__file__)
logger.setLevel(os.environ.get("INTEGRATION_TESTS_LOG_LEVEL", logging.DEBUG))
