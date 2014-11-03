from flask import Flask

app = Flask(__name__)

app.config.update(
    CELERY_BROKER_URL='amqp://guest@scraper_rmq//',
    CELERY_RESULT_BACKEND='amqp',
    CELERY_IGNORE_RESULT=False,
)

import start_celery
app_celery = start_celery.make_celery(app)

from app import views
from app import tasks