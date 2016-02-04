from itertools import chain
from collections import namedtuple
try:
    from html.parser import HTMLParser
except ImportError:
    from HTMLParser import HTMLParser

from .nodes import Tuple, Symbol, Keyword, String, List
from .printer import Printer


Tag = namedtuple('Tag', 'name attrs body')


class HTMLConverter(HTMLParser):

    def __init__(self):
        super(HTMLConverter, self).__init__()
        self._stack = [Tag(None, None, [])]

    @classmethod
    def convert(cls, source):
        converter = cls()
        converter.feed(source)
        return Printer.dumps(List(converter._stack[0].body))

    def handle_starttag(self, tag_name, attrs):
        self._stack.append(Tag(tag_name, attrs, []))

    def handle_endtag(self, tag_name):
        tag = self._stack.pop()

        t_args = [Symbol(tag.name)]
        t_args.extend(chain.from_iterable((Keyword(name), String(value))
                                          for name, value in tag.attrs))
        if len(tag.body) == 1:
            t_args.append(tag.body[0])
        elif len(tag.body) > 1:
            t_args.append(Tuple([Symbol('join'), List(tag.body)]))

        self._stack[-1].body.append(Tuple(t_args))
