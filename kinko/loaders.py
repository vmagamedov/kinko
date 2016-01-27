class NamespaceNotFound(LookupError):
    pass


class Source(object):

    def __init__(self, name, content, modified_time):
        self.name = name
        self.content = content
        self.modified_time = modified_time


class LoaderBase(object):

    def is_uptodate(self, ns):
        raise NotImplementedError

    def load(self, name):
        raise NotImplementedError


class CacheBase(object):

    def get(self, name):
        raise NotImplementedError

    def set(self, name, code):
        raise NotImplementedError


class DictLoader(LoaderBase):

    def __init__(self, mapping):
        self._sources = mapping

    def is_uptodate(self, ns):
        return True

    def load(self, name):
        try:
            return Source(name, self._sources[name], None)
        except KeyError:
            raise NamespaceNotFound(name)


class DictCache(CacheBase):

    def __init__(self):
        self._cache = {}

    def get(self, name):
        try:
            return self._cache[name]
        except KeyError:
            raise NamespaceNotFound(name)

    def set(self, name, code):
        self._cache[name] = code
