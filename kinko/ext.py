import importlib


def defn(name, type_):
    def decorator(func):
        func.__defn_name__ = name
        func.__defn_type__ = type_
        return func
    return decorator


def _iter_extensions(modules):
    for module in modules:
        mod = importlib.import_module(module)
        for name, obj in mod.__dict__.items():
            if getattr(obj, '__defn_name__', None) and \
                    getattr(obj, '__defn_type__', None):
                yield obj


def load_extensions(modules):
    return list(_iter_extensions(modules))
