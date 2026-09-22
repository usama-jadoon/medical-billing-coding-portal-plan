import asyncio
import logging
from services.api.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("medical_coding_worker")


def main():
    logger.info("Starting Medical Billing & Coding Portal Worker...")
    logger.info(f"Queue backend: {settings.QUEUE_BACKEND}")
    logger.info(f"Storage provider: {settings.STORAGE_PROVIDER}")
    logger.info(f"LLM provider: {settings.LLM_PROVIDER}")
    logger.info("Worker loop initialized. Ready to process background pipeline tasks.")


if __name__ == "__main__":
    main()
