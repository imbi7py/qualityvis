
import time
from datetime import datetime
import re
import itertools
import os
from os.path import join as pjoin
import requests
import json
from sys import maxint
import sys

from collections import namedtuple, deque
from functools import partial

import urllib2
import socket
from StringIO import StringIO
import gzip
import hashlib
import tempfile
import pickle


IS_BOT = False

if IS_BOT:
    PER_CALL_LIMIT = 5000
else:
    PER_CALL_LIMIT = 500

API_URL = "http://en.wikipedia.org/w/api.php"
DEFAULT_CONC     = 50
DEFAULT_PER_CALL = 4
DEFAULT_TIMEOUT  = 15
DEFAULT_HEADERS = { 'User-Agent': 'Loupe/0.0.0 Mahmoud Hashemi makuro@gmail.com' }
DEFAULT_MAX_COUNT = maxint
MAX_ARTICLES_LIST = 50
DEFAULT_CACHE_TIMEOUT = 1209600


###################
_DEFAULT_DIR_PERMS = 0755
socket.setdefaulttimeout(DEFAULT_TIMEOUT)  # TODO: better timeouts for fake requests
CACHE_EXT = '.wapiti_cache'
CACHE_PATH = 'wapiti_cache'


class CachedWapiti(object):
    def __init__(self, cache_path=''):
        self.root_path = cache_path
        self._init_dir(self.root_path)

    def __getattr__(self, name):
        cached = ['get_category',
                  'flatten_category',
                  'get_category_recursive',
                  'get_transcluded',
                  'get_articles_by_title',
                  'get_articles',
                  'get_talk_page',
                  'get_backlinks',
                  'get_langlinks',
                  'get_interwikilinks',
                  'get_protection',
                  'get_feedback_stats',
                  'get_feedbackv5_count',
                  'get_revision_infos'
                  ]
        if name in cached:
            return CachedFunction(name)
        else:
            try:
                return globals()[name]
            except KeyError:
                raise AttributeError('no attribute named %s' % name)

    def _init_dir(self, path):
        path = os.path.normpath(path)
        dirs = ['category', 'template', 'page_info']
        for d in dirs:
            path_to_create = pjoin(path, d)
            try:
                os.makedirs(path_to_create, _DEFAULT_DIR_PERMS)
            except OSError:
                if not os.path.isdir(path_to_create):
                    raise
        return



'''
def get_category(cat_name, count=PER_CALL_LIMIT, to_zero_ns=False, namespaces=None, cont_str=""):
def flatten_category(cat_name, page_limit=DEFAULT_MAX_COUNT, depth_first=True, *a, **kw):
def get_categories(cat_infos, page_limit=DEFAULT_MAX_COUNT, namespaces=None, sortby='pages', *a, **kw):
def get_category_recursive(cat_name, page_limit=DEFAULT_MAX_COUNT):
def get_subcategory_infos(cat_name):
def get_transcluded(page_title=None, page_id=None, namespaces=None, limit=PER_CALL_LIMIT, to_zero_ns=True):
def get_infos_by_title(titles, **kwargs):
def get_articles_by_title(titles, **kwargs):
def get_articles(page_ids=None, titles=None,
def get_talk_page(title):
def get_backlinks(title, count=PER_CALL_LIMIT, limit=DEFAULT_MAX_COUNT, cont_str='', **kwargs):
def get_langlinks(title, limit=DEFAULT_MAX_COUNT, cont_str='', **kwargs):
def get_interwikilinks(title, **kwargs):
def get_protection(title, **kwargs):
def get_feedback_stats(page_id, **kwargs):
def get_feedbackv5_count(page_id, **kwargs):
def get_revision_infos(page_title=None, page_id=None, limit=PER_CALL_LIMIT, cont_str=""):


'''

class CachedFunction(object):
    def __init__(self, name):
        self.name = name

    def __call__(self, *a, **kw):
        c_result = FileCache(self.name, *a, **kw)
        ret = c_result.get()
        if ret is not None:
            return ret
        ret = globals()[self.name](*a, **kw)
        c_result.save(ret)
        return ret

class FileCache(object):
    def __init__(self, function, *args, **kw):
        if not os.path.exists(CACHE_PATH):
            os.makedirs(CACHE_PATH)
        self.filename = os.path.join(CACHE_PATH, self.identifier(function, *args, **kw) + CACHE_EXT)
        self.timeout = DEFAULT_CACHE_TIMEOUT


    def identifier(self, func_name, *a, **args):
        f_a = str(a)
        f_str = str(func_name)
        f_args = str(args)

        return hashlib.sha1(f_str + f_a + f_args).hexdigest()

    def get(self):
        filename = self.filename
        try:
            f = open(filename, 'rb')
            try:
                if pickle.load(f) >= time.time():
                    print 'Loading from cache\n###'
                    return pickle.load(f)
            finally:
                f.close()
        except Exception:
            return None

    def save(self, value):
        filename = self.filename
        try:
            fd, tmp = tempfile.mkstemp()
            f = os.fdopen(fd, 'wb')
            try:
                pickle.dump(int(time.time() + self.timeout), f, 1)
                pickle.dump(value, f, pickle.HIGHEST_PROTOCOL)
            finally:
                f.close()
            os.rename(tmp, filename)
            os.chmod(filename, _DEFAULT_DIR_PERMS)
        except (IOError, OSError):
            pass


class WikiException(Exception):
    pass
PageIdentifier = namedtuple("PageIdentifier", "page_id, ns, title")
CategoryInfo = namedtuple('CategoryInfo', 'title, page_id, ns, size, pages, files, subcats')
Page = namedtuple("Page", "title, req_title, namespace, page_id, rev_id, rev_text, is_parsed, fetch_date, fetch_duration")
RevisionInfo = namedtuple('RevisionInfo', 'page_title, page_id, namespace, rev_id, rev_parent_id, user_text, user_id, length, time, sha1, comment, tags')

# From http://en.wikipedia.org/wiki/Wikipedia:Namespace
NAMESPACES = {
    'Main': 0,
    'Talk': 1,
    'User': 2,
    'User talk': 3,
    'Wikipedia': 4,
    'Wikipedia talk': 5,
    'File': 6,
    'File talk': 7,
    'MediaWiki': 8,
    'MediaWiki talk': 9,
    'Template': 10,
    'Template talk': 11,
    'Help': 12,
    'Help talk': 13,
    'Category': 14,
    'Category talk': 15,
    'Portal': 100,
    'Portal talk': 101,
    'Book': 108,
    'Book talk': 109,
    'Special': -1,
    'Media': -2
    }


NEW = 2
AUTOCONFIRMED = 1
SYSOP = 0
Protection = namedtuple('Protection', 'level, expiry')
PROTECTION_ACTIONS = ['create', 'edit', 'move', 'upload']


class Permissions(object):
    """
    For more info on protection,
    see https://en.wikipedia.org/wiki/Wikipedia:Protection_policy
    """
    levels = {
        'new': NEW,
        'autoconfirmed': AUTOCONFIRMED,
        'sysop': SYSOP,
    }

    def __init__(self, protections=None):
        protections = protections or {}
        self.permissions = {}
        for p in protections:
            if p['expiry'] != 'infinity':
                expiry = parse_timestamp(p['expiry'])
            else:
                expiry = 'infinity'
            level = self.levels[p['level']]
            self.permissions[p['type']] = Protection(level, expiry)

    @property
    def has_protection(self):
        return any([x.level != NEW for x in self.permissions.values()])

    @property
    def has_indef(self):
        return any([x.expiry == 'infinity' for x in self.permissions.values()])

    @property
    def is_full_prot(self):
        try:
            if self.permissions['edit'].level == SYSOP and \
                self.permissions['move'].level == SYSOP:
                return True
            else:
                return False
        except (KeyError, AttributeError):
            return False

    @property
    def is_semi_prot(self):
        try:
            if self.permissions['edit'].level == AUTOCONFIRMED:
                return True
            else:
                return False
        except (KeyError, AttributeError):
            return False


def parse_timestamp(timestamp):
    return datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')


class FakeResponse(object):
    pass


def fake_requests(url, params=None, headers=None, use_gzip=True):
    ret = FakeResponse()
    full_url = url
    try:
        if params:
            url_vals = encode_url_params(params)
            full_url = url + '?' + url_vals
    except:
        pass

    if not headers:
        headers = DEFAULT_HEADERS
    if use_gzip and not headers.get('Accept-encoding'):
        headers['Accept-encoding'] = 'gzip'

    req = requests.Request(url, params=params, headers=headers, method='GET', prefetch=False)
    full_url = req.full_url  # oh lawd, usin requests to create the url for now
    req = urllib2.Request(full_url, headers=headers)
    resp = urllib2.urlopen(req)
    resp_text = resp.read()
    resp.close()
    if resp.info().get('Content-Encoding') == 'gzip':
        comp_resp_text = resp_text
        buf = StringIO(comp_resp_text)
        f = gzip.GzipFile(fileobj=buf)
        resp_text = f.read()

    ret.text = resp_text
    ret.status_code = resp.getcode()
    ret.headers = resp.headers
    return ret


def get_url(url, params=None, raise_exc=True):
    resp = FakeResponse()
    try:
        resp = fake_requests(url, params)
    except Exception as e:
        if raise_exc:
            raise
        else:
            resp.error = e
    return resp


def get_json(*args, **kwargs):
    resp = get_url(*args, **kwargs)
    return json.loads(resp.text)


def api_req(action, params=None, raise_exc=True, **kwargs):
    all_params = {'format': 'json',
                  'servedby': 'true'}
    all_params.update(kwargs)
    all_params.update(params)
    all_params['action'] = action

    headers = {'accept-encoding': 'gzip'}

    resp = FakeResponse()
    resp.results = None
    try:
        if action == 'edit':
            #TODO
            resp = requests.post(API_URL, params=all_params, headers=headers, timeout=DEFAULT_TIMEOUT)
        else:
            resp = fake_requests(API_URL, all_params)

    except Exception as e:
        if raise_exc:
            raise
        else:
            resp.error = e
            resp.results = None
            return resp

    try:
        resp.results = json.loads(resp.text)
        resp.servedby = resp.results.get('servedby')
        # TODO: warnings?
    except Exception as e:
        if raise_exc:
            raise
        else:
            resp.error = e
            resp.results = None
            resp.servedby = None
            return resp

    mw_error = resp.headers.getheader('MediaWiki-API-Error')
    if mw_error:
        error_str = mw_error
        error_obj = resp.results.get('error')
        if error_obj and error_obj.get('info'):
            error_str += ' ' + error_obj.get('info')
        if raise_exc:
            raise WikiException(error_str)
        else:
            resp.error = error_str
            return resp

    return resp


def api_req_old(action, params=None, raise_exc=True, **kwargs):
    all_params = {'format': 'json',
                  'servedby': 'true'}
    all_params.update(kwargs)
    all_params.update(params)
    all_params['action'] = action

    headers = {'accept-encoding': 'gzip'}

    resp = requests.Response()
    resp.results = None
    try:
        if action == 'edit':
            resp = requests.post(API_URL, params=all_params, headers=headers, timeout=DEFAULT_TIMEOUT)
        else:
            resp = requests.get(API_URL, params=all_params, headers=headers, timeout=DEFAULT_TIMEOUT)

    except Exception as e:
        if raise_exc:
            raise
        else:
            resp.error = e
            resp.results = None
            return resp

    try:
        resp.results = json.loads(resp.text)
        resp.servedby = resp.results.get('servedby')
        # TODO: warnings?
    except Exception as e:
        if raise_exc:
            raise
        else:
            resp.error = e
            resp.results = None
            resp.servedby = None
            return resp

    mw_error = resp.headers.get('MediaWiki-API-Error')
    if mw_error:
        error_str = mw_error
        error_obj = resp.results.get('error')
        if error_obj and error_obj.get('info'):
            error_str += ' ' + error_obj.get('info')
        if raise_exc:
            raise WikiException(error_str)
        else:
            resp.error = error_str
            return resp

    return resp


def get_random(limit=10):
    ret = []
    while len(ret) < limit:
        params = {
            'generator': 'random',
            'grnnamespace': 0,
            'grnlimit': 10,
            'prop': 'info',
            'inprop': 'subjectid|protection',
        }
        resp = api_req('query', params)
        for page_id, info in resp.results['query']['pages'].iteritems():
            ret.append(PageIdentifier(title=info['title'],
                                       page_id=info['pageid'],
                                       ns=info['ns']))
    return ret


def get_category(cat_name, page_limit=DEFAULT_MAX_COUNT, to_zero_ns=False, namespaces=None, cont_str=""):
    ret = []
    retries = 0
    if not isinstance(namespaces, list):
        namespaces = [namespaces]
    if not cat_name.startswith('Category:'):
        cat_name = 'Category:' + cat_name
    while len(ret) < page_limit and cont_str is not None:
        cur_count = min(page_limit - len(ret), PER_CALL_LIMIT)
        params = {'generator': 'categorymembers',
                  'gcmtitle':   cat_name,
                  'prop':       'info',
                  'inprop':     'title|pageid|ns|subjectid|protection',
                  'gcmlimit':    cur_count,
                  'gcmcontinue': cont_str}
        try:
            resp = api_req('query', params)
        except Exception as e:
            if retries > 4:
                break
            print e, ', retrying ', (4 - retries), 'more times'
            retries +=1
            continue
        try:
            qres = resp.results['query']
        except:
            break  # hmmm

        for k, cm in qres['pages'].iteritems():
            if not cm.get('pageid'):
                continue
            namespace = cm['ns']
            title = cm['title']
            page_id = cm['pageid']
            if to_zero_ns:  # non-Main/zero namespace
                try:
                    page_id = cm['subjectid']
                except KeyError as e:
                    pass # TODO: log
                else:
                    if namespace == NAMESPACES['Talk']:
                        _, _, title = cm['title'].partition(':')
                    else:
                        title = cm['title'].replace(' talk:', '')
                    namespace = namespace - 1


            if namespaces and namespace not in namespaces:
                continue

            ret.append(PageIdentifier(title=title,
                                      page_id=page_id,
                                      ns=namespace))

        try:
            cont_str = resp.results['query-continue']['categorymembers']['gcmcontinue']
        except:
            cont_str = None
    return ret


def flatten_category(cat_name, page_limit=DEFAULT_MAX_COUNT, depth_first=True, *a, **kw):
    cat_names = deque([cat_name])
    seen_cat_names = set(cat_names)
    cat_infos = set()
    page_count = 0
    while cat_names:
        if page_limit and page_limit < page_count:
            break
        if depth_first:
            cur_cat = cat_names.popleft()
        else:
            cur_cat = cat_names.pop()
        print cur_cat, len(cat_names), page_count
        subcat_infos = get_subcategory_infos(cur_cat)
        for cat_info in subcat_infos:
            if cat_info.title not in seen_cat_names:
                seen_cat_names.add(cat_info.title)
                if cat_info.subcats > 0:
                    cat_names.append(cat_info.title)
                cat_infos.add(cat_info)
                page_count += cat_info.pages
    return cat_infos


def get_categories(cat_infos, page_limit=DEFAULT_MAX_COUNT, namespaces=None, sortby='pages', *a, **kw):
    ret = []
    sorted_cat_infos = list(cat_infos)
    if sortby:
        sorted_cat_infos = sorted(sorted_cat_infos,
            key=lambda x: getattr(x, sortby))
    while len(ret) < page_limit and sorted_cat_infos:
        cur_cat = sorted_cat_infos.pop()
        ret.extend(get_category(cur_cat.title, namespaces=namespaces, page_limit=page_limit))
        print len(ret), '/', page_limit, ', added', cur_cat.title
    return ret[:page_limit]


def get_category_recursive(cat_name, page_limit=DEFAULT_MAX_COUNT):
    categories = flatten_category(cat_name, page_limit)
    return get_categories(categories, page_limit, namespaces=0)


def get_subcategory_infos(cat_name):
    ret = []
    cont_str = ''
    retries = 0
    while cont_str is not None:
        params = {'generator': 'categorymembers',
                  'gcmtitle':   cat_name,
                  'prop':       'categoryinfo',
                  'gcmtype':    'subcat',
                  'gcmlimit':    PER_CALL_LIMIT,
                  'gcmcontinue': cont_str}
        try:
            resp = api_req('query', params)
        except Exception as e:
            if retries > 4:
                break
            print e, ', retrying ', (4 - retries), 'more times'
            retries +=1
            continue
        try:
            qres = resp.results['query']
        except:
            break  # hmmm

        for k, cm in qres['pages'].iteritems():
            if not cm.get('pageid') or k < 0:
                continue
            namespace = cm['ns']
            title = cm['title']
            page_id = cm['pageid']
            ci = cm.get('categoryinfo')
            if ci:
                size = ci['size']
                pages = ci['pages']
                files = ci['files']
                subcats = ci['subcats']
            else:
                size, pages, files, subcats = (0, 0, 0, 0)
            ret.append(CategoryInfo(title=title,
                                      page_id=page_id,
                                      ns=namespace,
                                      size=size,
                                      pages=pages,
                                      files=files,
                                      subcats=subcats))
        try:
            cont_str = resp.results['query-continue']['categorymembers']['gcmcontinue']
        except:
            cont_str = None
    return ret


def join_titles(orig_titles, prefix=None):
    titles = []
    if isinstance(orig_titles, basestring):
        orig_titles = [orig_titles]
    if prefix:
        for title in orig_titles:
            if not title.startswith(prefix):
                title = prefix + title
            titles.append(title)
    else:
        titles = orig_titles
    return "|".join([unicode(t) for t in titles])


def get_category_infos(cat_names, cont_str=""):
    ret = []
    while cont_str is not None:
        params = {'prop': 'categoryinfo',
                  'titles': join_titles(cat_names, 'Category:')}
        resp = api_req('query', params)
        try:
            qres = resp.results['query']
        except:
            break  # hmmm

        for k, cm in qres['pages'].iteritems():
            if not cm.get('pageid'):
                continue
            title = cm['title']
            page_id = k
            namespace = cm['ns']
            size = cm['categoryinfo']['size']
            pages = cm['categoryinfo']['pages']
            files = cm['categoryinfo']['files']
            subcats = cm['categoryinfo']['subcats']

            ret.append(CategoryInfo(title=title,
                                    page_id=page_id,
                                      ns=namespace,
                                      size=size,
                                      pages=pages,
                                      files=files,
                                      subcats=subcats))
        try:
            cont_str = resp.results['query-continue']['categoryinfo']['cicontinue']
        except:
            cont_str = None
    return ret


# TODO: default 'limit' to infinity/all
def get_transcluded(page_title=None, page_id=None, namespaces=None, limit=PER_CALL_LIMIT, to_zero_ns=True):
    ret = []
    cont_str = ""
    params = {'generator':  'embeddedin',
              'prop':       'info',
              'inprop':     'title|pageid|ns|subjectid'}
    if page_title and page_id:
        raise ValueError('Expected one of page_title or page_id, not both.')
    elif page_title:
        params['geititle'] = page_title
    elif page_id:
        params['geipageid'] = str(page_id)
    else:
        raise ValueError('page_title and page_id cannot both be blank.')
    if namespaces is not None:
        try:
            if isinstance(namespaces, basestring):
                namespaces_str = namespaces
            else:
                namespaces_str = '|'.join([str(int(n)) for n in namespaces])
        except TypeError:
            namespaces_str = str(namespaces)
        params['geinamespace'] = namespaces_str
    while len(ret) < limit and cont_str is not None:
        cur_count = min(limit - len(ret), PER_CALL_LIMIT)
        params['geilimit'] = cur_count
        if cont_str:
            params['geicontinue'] = cont_str

        resp = api_req('query', params)
        try:
            qres = resp.results['query']
        except:
            #print resp.error  # log
            raise
        for k, pi in qres['pages'].iteritems():
            if not pi.get('pageid'):
                continue
            ns = pi['ns']
            if ns != 0 and to_zero_ns:  # non-Main/zero namespace
                try:
                    _, _, title = pi['title'].partition(':')
                    page_id = pi['subjectid']
                    ns = 0
                except KeyError as e:
                    continue  # TODO: log
            else:
                title = pi['title']
                page_id = pi['pageid']
            ret.append(PageIdentifier(title=title,
                                      page_id=page_id,
                                      ns=ns))
        try:
            cont_str = resp.results['query-continue']['embeddedin']['geicontinue']
        except:
            cont_str = None
    return ret


def get_infos_by_title(titles, **kwargs):
    ret = []
    params = {}
    if isinstance(titles, basestring):
        return get_infos_by_title([titles])
    if len(titles) > MAX_ARTICLES_LIST:
        for page_chunk in chunked_pimap(get_infos_by_title, titles, chunk_size=MAX_ARTICLES_LIST):
            ret.extend(page_chunk)
    else:
        try:
            titles = "|".join([unicode(t) for t in titles])
        except:
            print "Couldn't join: ", repr(titles)
        params['titles'] = titles
        params['prop'] = 'info'
        pages = api_req('query', params).results['query']['pages']
        for page_id, info in pages.items():
            ret.append(PageIdentifier(title=info['title'],
                                       page_id=info['pageid'],
                                       ns=info['ns']))
    return ret


def get_articles_by_title(titles, **kwargs):
    return get_articles(titles=titles, **kwargs)


def get_articles(page_ids=None, titles=None,
    parsed=True, follow_redirects=False, **kwargs):
    ret = []
    params = {'prop':   'revisions',
              'rvprop': 'content|ids'}

    if page_ids:
        if not isinstance(page_ids, basestring):
            try:
                page_ids = "|".join([str(p) for p in page_ids])
            except:
                pass
        params['pageids'] = str(page_ids)
    elif titles:
        if not isinstance(titles, basestring):
            try:
                titles = "|".join([unicode(t) for t in titles])
            except:
                print "Couldn't join: ", repr(titles)
        params['titles'] = titles
    else:
        raise Exception('You need to pass in a page id or a title.')

    if parsed:
        params['rvparse'] = 'true'
    if follow_redirects:
        params['redirects'] = 'true'

    fetch_start_time = time.time()
    parse_resp = api_req('query', params, **kwargs)
    if parse_resp.results:
        try:
            pages = parse_resp.results['query']['pages'].values()
            redirect_list = parse_resp.results['query'].get('redirects', [])
        except:
            print "Couldn't get_articles() with params: ", params
            print 'URL:', parse_resp.url
            return ret

        redirects = dict([(r['to'], r['from']) for r in redirect_list])
        # this isn't perfect since multiple pages might redirect to the same page
        fetch_end_time = time.time()
        for page in pages:
            if not page.get('pageid') or not page.get('title'):
                continue
            title = page['title']
            pa = Page( title=title,
                       req_title=redirects.get(title, title),
                       namespace=page['ns'],
                       page_id=page['pageid'],
                       rev_id=page['revisions'][0]['revid'],
                       rev_text=page['revisions'][0]['*'],
                       is_parsed=parsed,
                       fetch_date=fetch_start_time,
                       fetch_duration=fetch_end_time - fetch_start_time)
            ret.append(pa)
    return ret


def get_talk_page(title):
    params = {'prop': 'revisions',
              'titles': 'Talk:' + title,
              'rvprop': 'content',
             }
    resp = api_req('query', params).results
    try:
        talk_page = resp['query']['pages'].values()[0]['revisions'][0]['*']
    except KeyError as e:
        talk_page = ''
    return talk_page


def get_backlinks(title, count=PER_CALL_LIMIT, limit=DEFAULT_MAX_COUNT, cont_str='', **kwargs):
    ret = []
    while len(ret) < limit and cont_str is not None:
        params = {'list': 'backlinks',
                  'bltitle': title,
                  'blnamespace': 0,
                  'bllimit': PER_CALL_LIMIT,
                  }
        if cont_str:
            params['blcontinue'] = cont_str
        resp = api_req('query', params)
        for link in resp.results['query']['backlinks']:
            ret.append(resp.results['query']['backlinks'])
        try:
            cont_str = resp.results['query-continue']['backlinks']['blcontinue']
        except:
            cont_str = None
    return ret


def get_langlinks(title, limit=DEFAULT_MAX_COUNT, cont_str='', **kwargs):
    ret = []
    while len(ret) < limit and cont_str is not None:
        params = {'prop': 'langlinks',
                  'titles': title,
                  'lllimit': PER_CALL_LIMIT,  # TODO?
                  }
        if cont_str:
            params['llcontinue'] = cont_str
        resp = api_req('query', params).results
        if resp['query']['pages'].values()[0].get('langlinks') is None:
            return []
        langs = resp['query']['pages'].values()[0].get('langlinks')
        for language in langs:
            ret.append(language['lang'])
        try:
            cont_str = resp.results['query-continue']['langlinks']['llcontinue']
        except:
            cont_str = None
    return ret


def get_interwikilinks(title, **kwargs):
    params = {'prop': 'iwlinks',
              'titles': title,
              'iwlimit': 500,  # TODO?
              }
    try:
        query_results = api_req('query', params).results['query']['pages'].values()[0]['iwlinks']
    except KeyError:
        query_results = []
    return query_results


def get_protection(title, **kwargs):
    params = {'prop': 'info',
              'titles': title,
              'inprop': 'protection',
              }
    try:
        query_results = api_req('query', params).results['query']['pages'].values()[0]['protection']
    except KeyError:
        query_results = []
    return query_results


def get_feedback_stats(page_id, **kwargs):
    params = {'list': 'articlefeedback',
              'afpageid': page_id
              }
    # no ratings entry in the json means there are no ratings. if any of the other keys are missing
    # that's an error.
    return api_req('query', params).results['query']['articlefeedback'][0].get('ratings', [])


def get_feedbackv5_count(page_id, **kwargs):
    params = {'list': 'articlefeedbackv5-view-feedback',
              'afvfpageid': page_id,
              'afvflimit': 1
              }
    return api_req('query', params).results['articlefeedbackv5-view-feedback']['count']


def get_revision_infos(page_title=None, page_id=None, limit=PER_CALL_LIMIT, cont_str=""):
    ret = []
    params = {'prop': 'revisions',
              'rvprop': 'ids|flags|timestamp|user|userid|size|sha1|comment|tags'}
    if page_title and page_id:
        raise ValueError('Expected one of page_title or page_id, not both.')
    elif page_title:
        params['titles'] = page_title
    elif page_id:
        params['pageids'] = str(page_id)
    else:
        raise ValueError('page_title and page_id cannot both be blank.')

    resps = []
    res_count = 0
    while res_count < limit and cont_str is not None:
        cur_limit = min(limit - len(ret), PER_CALL_LIMIT)
        params['rvlimit'] = cur_limit
        if cont_str:
            params['rvcontinue'] = cont_str
        resp = api_req('query', params)
        try:
            qresp = resp.results['query']
            resps.append(qresp)

            plist = qresp['pages'].values()  # TODO: uuuugghhhhh
            if plist and not plist[0].get('missing'):
                res_count += len(plist[0]['revisions'])
        except:
            #print resp.error  # log
            raise
        try:
            cont_str = resp.results['query-continue']['revisions']['rvcontinue']
        except:
            cont_str = None

    for resp in resps:
        plist = resp['pages'].values()
        if not plist or plist[0].get('missing'):
            continue
        else:
            page_dict = plist[0]
        page_title = page_dict['title']
        page_id = page_dict['pageid']
        namespace = page_dict['ns']

        for rev in page_dict.get('revisions', []):
            rev_info = RevisionInfo(page_title=page_title,
                                    page_id=page_id,
                                    namespace=namespace,
                                    rev_id=rev['revid'],
                                    rev_parent_id=rev['parentid'],
                                    user_text=rev.get('user', '!userhidden'),  # user info can be oversighted
                                    user_id=rev.get('userid', -1),
                                    time=parse_timestamp(rev['timestamp']),
                                    length=rev['size'],
                                    sha1=rev['sha1'],
                                    comment=rev.get('comment', ''),  # comments can also be oversighted
                                    tags=rev['tags'])
            ret.append(rev_info)
    return ret


def chunked_pimap(func, iterable, concurrency=DEFAULT_CONC, chunk_size=DEFAULT_PER_CALL, **kwargs):
    from gevent.pool import Pool
    func = partial(func, **kwargs)
    chunked = (iterable[i:i + chunk_size]
               for i in xrange(0, len(iterable), chunk_size))
    pool = Pool(concurrency)
    return pool.imap_unordered(func, chunked)
