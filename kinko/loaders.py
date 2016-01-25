class NamespaceNotFound(LookupError):
    pass


class DictLoader(object):

    def __init__(self, mapping):
        self.mapping = mapping

    def load(self, name):
        try:
            return self.mapping[name]
        except KeyError:
            raise NamespaceNotFound(name)
