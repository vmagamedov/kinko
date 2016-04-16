from logging import getLogger
from collections import namedtuple

from aiohttp import ClientSession
from aiohttp.web import Application, Response, run_app

from .lookup import Lookup
from .loaders import FileSystemLoader
from .typedef import load_types
from .read.simple import loads


ResolveResult = namedtuple('ResolveResult', 'status endpoint')

log = getLogger(__name__)


def current_url(request):
    return '{}://{}{}'.format(request.scheme, request.host, request.path_qs)


class Backend(object):

    def __init__(self, base_url, *, loop):
        self.base_url = base_url
        self.loop = loop

    def _url(self, path):
        return self.base_url + path

    async def types(self):
        url = self._url('types.kinko')
        with ClientSession(loop=self.loop) as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    return load_types(data.decode('utf-8'))
                else:
                    raise Exception(repr(resp))

    async def resolve(self, url):
        _url = self._url('resolve')
        params = {'url': url}
        with ClientSession(loop=self.loop) as session:
            async with session.get(_url, params=params) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    return ResolveResult(result['status'],
                                         result.get('endpoint'))
                else:
                    raise Exception(repr(resp))

    async def pull(self, query, url):
        _url = self._url('pull')
        data = repr(query)
        params = {'url': url}
        headers = {'Content-Type': 'application/edn'}
        with ClientSession(loop=self.loop) as session:
            async with session.post(_url, data=data, params=params,
                                    headers=headers) as resp:
                if resp.status == 200:
                    resp_data = await resp.read()
                    result = loads(resp_data.decode('utf-8'))
                    return result
                else:
                    raise Exception(repr(resp))


def get_backend(app):
    backend = app.get('_backend', None)
    if backend is None:
        base_url = app['BASE_URL']
        backend = app['_backend'] = Backend(base_url, loop=app.loop)
    return backend


async def get_lookup(app):
    lookup = app.get('_lookup', None)
    if lookup is None:
        backend = get_backend(app)
        types = await backend.types()
        loader = FileSystemLoader(app['UI_PATH'])
        lookup = app['_lookup'] = Lookup(types, loader)
    return lookup


async def request_handler(request):
    url = current_url(request)

    backend = get_backend(request.app)

    status, endpoint = await backend.resolve(url)
    if status != 200:
        return Response(status=status,
                        text='HTTP Error {}'.format(status))

    fn = (await get_lookup(request.app)).get(endpoint)

    log.info('%s %r', endpoint, fn.query())

    result = await backend.pull(fn.query(), url)

    return Response(text=fn.render(result),
                    headers={'Content-Type': 'text/html'})


def main(host, port, base_url, ui_path, static_path):
    app = Application()
    app['BASE_URL'] = base_url
    app['UI_PATH'] = ui_path

    if static_path:
        app.router.add_static('/static', static_path)

    app.router.add_route('GET', '/', request_handler)
    app.router.add_route('GET', '/{path:.+}', request_handler)

    run_app(app, host=host, port=port)
