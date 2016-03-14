import sys


PY3 = sys.version_info[0] == 3


def with_metaclass(meta, *bases):
    """Create a base class with a metaclass."""
    # This requires a bit of explanation: the basic idea is to make a dummy
    # metaclass for one level of class instantiation that replaces itself with
    # the actual metaclass.
    class metaclass(meta):

        def __new__(cls, name, this_bases, d):
            return meta(name, bases, d)
    return type.__new__(metaclass, 'temporary_class', (), {})


if PY3:
    import builtins

    def _exec_in(source, globals_dict):
        getattr(builtins, 'exec')(source, globals_dict)

    text_type = str
    text_type_name = 'str'

else:
    def _exec_in(source, globals_dict):
        exec('exec source in globals_dict')

    text_type = unicode  # noqa
    text_type_name = 'unicode'
