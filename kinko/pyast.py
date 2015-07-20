from lib2to3.pygram import python_symbols as syms
from lib2to3.fixer_util import Attr, Call, Name, Number, String, Node
from lib2to3.fixer_util import Comma, Newline


def Suite(lst):
    return Node(syms.file_input, lst)

