docker run --name scraper_rmq -p 15672:15672 -p 5672:5672 -t -d scraper rabbitmq-server

docker run --name scraper_server -p 80:80 -t -i --link scraper_rmq:scraper_rmq scraper python server.py

docker run --name scraper_worker1 -t -i --link scraper_rmq:scraper_rmq scraper celery -A app.app_celery worker -l info