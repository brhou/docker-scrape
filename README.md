Design

I used flask and celery in order to achieve scaling via docker.

The crawler was implemented as a celery task and scales by adding
more workers to process the task queue.

The api endpoints were written in flask.

I have one docker container image that was build from the Dockerfile.
It installs the requirements to run python, then pulls the repo and installs
pip requirements.

I took advantage of the --link option in order to connect these vms.

I've written some unit tests in the code and they can be run with py.test just to give an idea
of how I would go about testing the code. I used the pymock library to help me test.


How to run

Download the code. Build the docker image with the command:
docker build -t scraper .

The docker container is designed to become three types of different servers depending
on what command you instantiate them with.

This command will start a rabbitmq-server. There should only be one instances of these.
docker run --name scraper_rmq -p 15672:15672 -p 5672:5672 -t -d scraper rabbitmq-server

This command will start the web server instance. There is also only one of these instances.
docker run --name scraper_server -p 80:80 -t -d --link scraper_rmq:scraper_rmq scraper python server.py

This command will start a worker. There can be multiple instances of these.
docker run --name scraper_worker1 -t -d --link scraper_rmq:scraper_rmq scraper celery -A app.app_celery worker -l info

Scaling works by adding more worker containers. Just change the name to scraper_worker{new number}


API

POST /
        Accepts Json input of url list.
        ex {'urls': ['http://docker.com', 'http://google.com']}
        Returns: Task-id
GET  /status/<Task-id>
        Get the status given a task id
        Returns: Amount of urls crawled and to be crawled
        ex
        {
            "completed": 1,
            "id": "667ecb18-368b-412a-9bc2-383a5dc7f10f",
            "inprogress": 0
        }
GET /result/<Task-id>
        Get the results from a url if ready
        ex
        {
            "http://docker.com": [
                "hello.png",
                "hello2.png"
            ],
            "http://google.com": [
                "hello.png",
                "hello2.png"
            ],
        }


Areas for improvement

I felt that the point of this task was to show how docker containers can be used to scale.
I accomplished that by being able to run one command to spin up more workers. However,
there is a single point of failure on the RMQ server as well as the web server. To solve these
problems, adding clustering via zookeeper or adding a load balancing server in front of the rmq and
server instances would help to solve these problems.

Right now, the rabbit_mq server must be named scraper_rmq because the config for the workers
is pre-baked into the container. Adding a config file to change the behavior of the containers
would be a nice feature.