from . import nodes as N
from . import ast as A


class TranslationError(Exception):
    def __init__(self, location, message):
        self.location = location
        self.message = message

    def __str__(self):
        return "{}: Translation error {}".format(self.location, self.message)


def translate_call(item):
    return A.GenericCall(
        name=item.symbol.name,
        args=[x for x in item.args if not isinstance(x, N.KeywordPair)],
        kwargs={x.keyword.name: y.value for x in item.args
                                        if isinstance(x, N.KeywordPair)})


def _find_placeholders(node):
    # TODO(tailhook)
    return
    yield


def find_placeholders(lst):
    res = []
    for node in lst:
        for val in _find_placeholders(node):
            res.append(val)
    return []


def translate_template(lst):
    functions = []
    for item in lst:
        assert isinstance(item, N.Tuple)
        if item.symbol.name != 'def':
            raise TranslationError(item.symbol.location,
                "Top level items must always be `def`s. Got {!r}. "
                "You're adviced to create function 'main' or just fix your "
                "indentation error")
        body = item.args[:]
        if not body or not isinstance(body[0], N.Dotname):
            raise TranslationError(item.symbol.location,
                "First argument to `def` must be function name (i.e. symbol)")
        nameitem = body.pop(0)
        if nameitem.attrs:
            raise TranslationError(item.symbol.location,
                "Dot is not allowed in function name")
        placeholders = find_placeholders(item.args)
        func = A.Function(nameitem.item.name,
            list(map(translate_call, body)),
            arguments=placeholders)
        functions.append(func)
    return A.File(functions=functions)
