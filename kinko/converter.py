from itertools import chain

from lxml import etree
from lxml.html import fromstring, fragment_fromstring, HtmlElement

from .nodes import Tuple, Symbol, Keyword, String, List
from .compat import text_type
from .printer import Printer


def _filter(nodes):
    for node in nodes:
        if isinstance(node, HtmlElement):
            yield node
        elif isinstance(node, text_type):
            value = node.strip()
            if value:
                yield value


def _convert(el):
    if isinstance(el, text_type):
        content = el.strip()
        if content:
            return String(el)

    t_args = [Symbol(el.tag)]
    t_args.extend(chain.from_iterable((Keyword(name), String(value))
                                      for name, value in el.attrib.items()))

    children = list(_filter(el.xpath("child::node()")))

    if len(children) == 1:
        t_args.append(_convert(children[0]))
    elif len(children) > 1:
        t_args.append(Tuple([Symbol('join'),
                             List([_convert(i) for i in children])]))
    return Tuple(t_args)


def convert(source):
    try:
        tree = fragment_fromstring(source)
    except etree.ParserError:
        tree = fromstring(source)
    node = _convert(tree)
    return Printer.dumps(node)
