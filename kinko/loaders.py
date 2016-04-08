import errno
import codecs
import os.path


class NamespaceNotFound(LookupError):
    pass


class Source(object):

    def __init__(self, name, content, modified_time, file_path):
        self.name = name
        self.content = content
        self.modified_time = modified_time
        self.file_path = file_path


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
        file_path = '<memory:{}.kinko>'.format(name)
        try:
            return Source(name, self._sources[name], None, file_path)
        except KeyError:
            raise NamespaceNotFound(name)


class FileSystemLoader(LoaderBase):
    _encoding = 'utf-8'
    _template = '{}.kinko'

    def __init__(self, path):
        self._path = path

    def is_uptodate(self, ns):
        file_name = os.path.join(self._path, self._template.format(ns.name))
        try:
            return os.path.getmtime(file_name) == ns.modified_time
        except OSError:
            return False

    def load(self, name):
        file_path = os.path.join(self._path, self._template.format(name))
        try:
            with codecs.open(file_path, encoding=self._encoding) as f:
                content = f.read()
        except IOError as e:
            if e.errno not in (errno.ENOENT, errno.EISDIR, errno.EINVAL):
                raise
            raise NamespaceNotFound(name)
        modified_time = os.path.getmtime(file_path)
        return Source(name, content, modified_time, file_path)


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
