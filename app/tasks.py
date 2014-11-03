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
    p = urlparse(url)
    try:
        conn = httplib.HTTPConnection(p.netloc)
        conn.request('HEAD', p.path)
        resp = conn.getresponse()
    except Exception:
        return False
    return resp.status < 400

@app_celery.task()
def get_urls_group(urls, recurse=False):
    return group(scrape_url.subtask(args=(url, recurse)) for url in urls)

@app_celery.task(max_retries=2, soft_time_limit=30, default_retry_delay=5)
def scrape_url(result, recurse=False):
    try:
        page = requests.get(result.url, timeout=5)
    except Exception as e:
        raise scrape_url.retry(exc=e)
    soup = BeautifulSoup(page.text)
    # get all img tags first
    for img in soup.find_all('img'):
        src = img.get('src')
        if src and src[-3:] in ['gif', 'png', 'jpg']:
            result.results.append(src)
    new_url_list = []
    # get all links
    if recurse:
        for link in soup.find_all('a'):
            url = link.get('href')
            if url and check_url(url):
                new_url_list.append(Result(url))
    new_url_list = set(new_url_list)
    if recurse:
        result.next_results = url_list_wrapper.delay(new_url_list)
    return result

@app_celery.task()
def url_list_wrapper(urls):
    """
    Have to wrap group but with url lists combined already
    """
    return get_urls_group(urls).delay()


@app_celery.task()
def group_wrapper(urls):
    """
    Have to wrap groups because there is no way to retrieve group id
    """
    url_dicts = []
    for url in urls:
        url_dicts.append(Result(url))
    return get_urls_group(url_dicts, recurse=True).delay()

def ret_results(task_id):
    """
    Format: Async.groupresults[].Async.result.nextresult.groupresults[].Async.result
    """
    # initiate the results dictionary
    res_list = []
    group_list = []
    res = AsyncResult(task_id, app=app_celery)
    if not res:
        raise TaskNotFoundException("Task id %s not found or has expired." % task_id)
    # remove the async wrapper
    if res.ready():
        res = res.get()
    else:
        raise TaskNotStartedException("Task id %s has not started. Please try again later." % task_id)
    # res is a groupresult
    for group in res:
        group = AsyncResult(group.id, app=app_celery)
        if not group.ready():
            res_list.append(Result("", [], ready=False))
            continue
        # fail gracefully by skipping errored
        if group.failed():
            continue
        result = group.get()
        comb_res = Result(result.url, result.results)
        res_list.append(comb_res)
        next_results = result.next_results
        if next_results:
            group_list.append((comb_res, next_results))
    res_tup = None
    if group_list:
        res_tup = group_list.pop()
    # res_tup is a (string key, asyncresult)
    while res_tup:
        comb_res = res_tup[0]
        # res is asyncresult
        res = res_tup[1]
        res = AsyncResult(res.id, app=app_celery)
        # remove async wrapper
        if res.ready():
            res = res.get()
        else:
            comb_res.ready = False
        # if there is one group that is not ready, set the result to not ready
        #if not res.ready():
        #    comb_res.ready = False
        if comb_res.ready:
            # group is an asyncresult
            for group in res:
                group = AsyncResult(group.id, app=app_celery)
                # added as a hack since the data can't be checked as a group Result
                if not group.ready():
                    comb_res.ready = False
                    continue
                # skip over errored results, ignore them for now
                if group.failed():
                    continue
                result = group.get()
                comb_res.results.extend(result.results)
                r = result.next_results
                if r:
                     group_list.append((comb_res, r))
        res_tup = None
        if group_list:
            res_tup = group_list.pop()
    for comb_res in res_list:
        comb_res.results = list(set(comb_res.results))
    return res_list

