from celery import Celery

def make_celery(app):
    app_celery = Celery(app.import_name, broker=app.config['CELERY_BROKER_URL'])
    app_celery.conf.update(app.config)
    TaskBase = app_celery.Task
    class ContextTask(TaskBase):
        abstract = True
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)
    app_celery.Task = ContextTask
    return app_celery