import mock
import json
from collections import namedtuple

from app import views

views.app.config['TESTING'] = True
test_app = views.app.test_client()

Task = namedtuple('Task', 'id')

@mock.patch('app.views.tasks.async_group_wrapper.delay')
def test_start_crawler(wrapper):
    # should return 400 bad request with empty data
    rv = test_app.post('/', data=json.dumps(dict()))
    assert "Please input proper json" in rv.data

    # return 400 when the key is wrong
    rv = test_app.post('/', data=json.dumps(dict(wrongkey="test")))
    assert "Please include 'urls' as json key" in rv.data

    # url not a list
    rv = test_app.post('/', data=json.dumps(dict(urls="test")))
    assert "Please include non empty type list for 'url' input" in rv.data

    # url is valid
    wrapper.return_value = Task(id="12345")
    url_dict = dict(urls=['http://test.com', 'http://google.com'])
    rv = test_app.post('/', data=json.dumps(url_dict))
    assert "12345" in rv.data
    wrapper.assert_called_with(url_dict['urls'])

