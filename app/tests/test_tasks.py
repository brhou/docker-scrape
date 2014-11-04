from app import tasks
from collections import namedtuple

import mock
import pytest

MockRes = namedtuple('MockRes', 'text')

sample_html = """
<html>
  <head>
    <title>Sample "Hello, World" Application</title>
  </head>
  <body bgcolor=white>

  <img src="images/springsource.png">
  <img src="images/springsource1.jpg">
  <img src="images/springsource3.gif">
  <img src="images/springsource4.notavalidimage">

    <ul>
      <li>To a <a href="hello.jsp">JSP page</a>
      <li>To a <a href="hello">servlet</a>
      <li>To a <a href="hello">servlet</a>
    </ul>

  </body>
</html>
"""

@mock.patch('app.tasks.check_url')
@mock.patch('app.tasks.requests')
@mock.patch('app.tasks.scrape_url.retry')
@mock.patch('app.tasks.async_group_wrapper.delay')
def test_scrape_url(url_wrapper, scraper, request, get_urls):
    # return nothing, just get the url
    request.get.return_value = MockRes(text="")
    result = tasks.Result("test.com")
    result = tasks.scrape_url(result)
    assert "http://test.com" == result.url
    assert not result.results
    # since it wasn't recursive, nothing was called yet
    assert url_wrapper.call_count == 0
    assert scraper.call_count == 0

    # plug in sample html
    request.get.return_value = MockRes(text=sample_html)
    result = tasks.scrape_url(result)
    assert result.results == ['images/springsource.png',
                              'images/springsource1.jpg',
                              'images/springsource3.gif']
    # since it wasn't recursive, nothing was called yet
    assert url_wrapper.call_count == 0
    assert scraper.call_count == 0

    result.results = []
    # use sample html but this time set recursive flag
    result = tasks.scrape_url(result, recurse=True)
    get_urls.return_value = True
    assert result.results == ['images/springsource.png',
                              'images/springsource1.jpg',
                              'images/springsource3.gif']
    # recursed, so called once
    assert url_wrapper.call_count == 1
    url_wrapper.assert_called_with(['http://hello', 'http://hello.jsp'], False)
    assert scraper.call_count == 0

    # check for exceptions
    request.get.side_effect = Exception("An exception occurred running requests")
    with pytest.raises(Exception):
        tasks.scrape_url(result)
    assert url_wrapper.call_count == 1
    assert scraper.call_count == 1