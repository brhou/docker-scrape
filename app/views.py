from app import app
import json
from flask import request, jsonify

import tasks


class TaskStatus():
    def __init__(self, total, completed):
        self.total = total
        self.completed = completed
        self.waiting = self.total - self.completed

    @property
    def ready(self):
        return self.waiting == 0

def task_status(results):
    if not results:
        return None
    total = len(results)
    completed = 0
    for res in results:
        if res.ready:
            completed += 1
    return TaskStatus(total, completed)

@app.route('/', methods=['POST'])
def start_crawler():
    print request.data
    data = request.get_json(force=True)
    ret_code = 400
    if not data:
        return "Please input proper json", ret_code
    if 'urls' not in data:
        return "Please include 'urls' as json key", ret_code
    if not isinstance(data['urls'], list):
        return "Please include non empty type list for 'url' input", ret_code
    t = tasks.group_wrapper.delay((data['urls']))
    ret_code = 200
    return t.id, ret_code

@app.route('/status/<id>', methods=['GET'])
def check_status(id):
    try:
        results = tasks.ret_results(id)
        status = task_status(results)
    except (tasks.TaskNotStartedException, tasks.TaskNotFoundException) as e:
        return str(e)
    ret = {
        'id': id,
        'completed': status.completed,
        'inprogress': status.waiting
    }
    return jsonify(ret)

@app.route('/result/<id>', methods=['GET'])
def get_result(id):
    try:
        results = tasks.ret_results(id)
        status = task_status(results)
    except (tasks.TaskNotStartedException, tasks.TaskNotFoundException) as e:
        return str(e)
    if not status.ready:
        return "Please check the status, the results aren't ready yet", 503
    res_dict = {}
    for result in results:
        res_dict[result.url] = result.results
    return jsonify(res_dict)
