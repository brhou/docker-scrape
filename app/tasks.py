from app import app_celery
from celery import group, subtask
from celery.result import AsyncResult
from bs4 import BeautifulSoup

import requests

import httplib
from urlparse import urlparse

class TaskNotFoundException(BaseException):
    pass

class TaskNotStartedException(BaseException):
    pass

class Result():
    def __init__(self, url, results=[], ready=True):
        self.url = url
        self.results = results
        self.next_results = None
        self.ready = ready

def check_url(url):
    """
    Helper function to check whether the url is reachable
    Args:
        url
    Return:
        whether the url head can be reached
    """
    p = urlparse(url)
    try:
        conn = httplib.HTTPConnection(p.netloc)
        conn.request('HEAD', p.path)
        resp = conn.getresponse()
    except Exception:
        return False
    return resp.status < 400

def get_urls(soup):
    """
    Looks through html to grab all the links, returns unique set of links
    Args:
        soup: BeautifulSoup instance
    Returns:
        List of urls found in html
    """
    new_url_list = []
    for link in soup.find_all('a'):
        url = link.get('href')
        # append the schema to the links, incase they aren't there
        if url and not url.startswith('http://'):
            url = "http://%s" % url
        if url and check_url(url):
            new_url_list.append(url)
    return list(set(new_url_list))

@app_celery.task(max_retries=2, soft_time_limit=30, default_retry_delay=5)
def scrape_url(result, recurse=False):
    """
    This is the url scraper. It grabs all img tags to check for valid images
    Args:
        result: Type result that contains the url. Results are stored back in the same class
        resurse: Specify whether recursion should occur.
    Returns:
        result, of class Result
    """
    try:
        if not result.url.startswith("http://"):
            result.url = "http://%s" % result.url
        page = requests.get(result.url, timeout=5)
    except Exception as e:
        raise scrape_url.retry(exc=e)
    soup = BeautifulSoup(page.text)
    # get all img tags first
    for img in soup.find_all('img'):
        src = img.get('src')
        if src and src[-3:] in ['gif', 'png', 'jpg']:
            result.results.append(src)
    # get all links
    if recurse:
        url_list = get_urls(soup)
        result.next_results = async_group_wrapper.delay(url_list, False)
    return result

@app_celery.task()
def get_urls_group(urls, recurse=False):
    """
    Return a GroupResult of AsyncResult tasks of scrape_url
    Args:
        urls: list of class Results
        recurse: recursively look through urls
    """
    return group(scrape_url.subtask(args=(url, recurse)) for url in urls)

@app_celery.task()
def async_group_wrapper(urls, recurse=True):
    """
    Return an AsyncResult that contains group results
    This is a workaround since the docker vm has trouble getting to RabbitMQ
    AsyncResult is retrieved each time in ret_results for each tasks
    Also helps to return only one TaskId back to the user to be able to track
    Args:
        urls: List of string urls
        recurse: look through urls recursively
    Returns:
        an Async task
    """
    results = [Result(url) for url in urls]
    return get_urls_group(results, recurse=recurse).delay()


def process_top_urls(async_res):
    """
    Process top layer urls
    Args:
        async_res: AsyncResult to be processed
    Returns:
        Result object
    """
    async_res = AsyncResult(async_res.id, app=app_celery)
    # there's no way to get the url
    if not async_res.ready():
        return Result("", [], ready=False)
    # fail gracefully by skipping errored
    if async_res.failed():
        return Result("", ["error"], ready=True)
    return async_res.get()

def process_inner_urls(comb_res, async_res):
    """
    Process second layer urls and append to the combined results object
    Args:
        comb_res: combined result object for parent url
        async_res: an AsyncResult
    Returns:
        next result task on current Result object
    """
    async_res = AsyncResult(async_res.id, app=app_celery)
    # added as a hack since the data can't be checked as a group Result
    if not async_res.ready():
        comb_res.ready = False
        return None
        # skip over errored results, ignore them for now
    if async_res.failed():
        return None
    result = async_res.get()
    comb_res.results.extend(result.results)
    return result.next_results

def ret_results(task_id):
    """
    Given a task id, return the dictionary result of all urls one level down
    The AsyncResult object returned looks like the following:
        Format: Async.groupresults[].Async.result.nextresult.groupresults[].Async.result
    Args:
        task_id: task_id of rabbitmq task
    Returns:
        List of Result objects of top level urls and all sub urls combined
    """
    # initiate the results dictionary
    ret_list = []
    # list of result tuples to be processed
    group_list = []
    res = AsyncResult(task_id, app=app_celery)
    if not res:
        raise TaskNotFoundException("Task id %s not found or has expired." % task_id)
    # remove the async wrapper
    if res.ready():
        group_res = res.get()
    else:
        raise TaskNotStartedException("Task id %s has not started. Please try again later." % task_id)
    # process top urls and place them in results list
    for group in group_res:
        comb_res = process_top_urls(group)
        ret_list.append(comb_res)
        if comb_res.next_results:
            group_list.append((comb_res, comb_res.next_results))
    # if there are results to process
    while group_list:
        # res_tup is a (Result, AsyncResult)
        res_tup = group_list.pop()
        # comb_res represents the top level url result to be returned
        comb_res = res_tup[0]
        # res is AsyncResult
        res = res_tup[1]
        res = AsyncResult(res.id, app=app_celery)
        # remove async wrapper
        if res.ready():
            res = res.get()
        else:
            comb_res.ready = False
        # if there is one group that is not ready, set the result to not ready
        # disabled for now since you can't check on the group in the docker vm
        #if not res.ready():
        #    comb_res.ready = False
        # if the top level url is ready to be processed
        if comb_res.ready:
            # group_list is an GroupResult
            for group in res:
                next_results = process_inner_urls(comb_res, group)
                if next_results:
                    group_list.append((comb_res, next_results))
    # make sure all urls collected in each group is unique
    for comb_res in ret_list:
        comb_res.results = list(set(comb_res.results))
    return ret_list

