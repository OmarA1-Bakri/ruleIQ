import configparser
from sqlalchemy import create_engine, text
import logging

logger = logging.getLogger(__name__)
config = configparser.ConfigParser()
config.read("alembic.ini")
db_url = config.get("alembic", "sqlalchemy.url")
logger.info("Connecting to database: %s" % db_url)
try:
    engine = create_engine(db_url)
    with engine.connect() as connection:
        logger.info("Connection successful. Dropping table...")
        connection.execute(text("DROP TABLE IF EXISTS alembic_version;"))
        connection.commit()
        logger.info("Table 'alembic_version' dropped successfully.")
except Exception as e:
    logger.info("An error occurred: %s" % e)
