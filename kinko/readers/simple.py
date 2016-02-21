from hiku.edn import loads as _loads

from .result import Result


def _ref_handler(result):
    def handler(value):
        entity, ident = value
        return result.ref(entity, ident)
    return handler


def loads(data):
    result = Result()
    result.update(_loads(data, {'graph/ref': _ref_handler(result)}))
    return result
