from enum import Enum
from string import ascii_letters, digits, whitespace
from collections import namedtuple

MATCHING_BRACKET = {
    '{': '}',
    '(': ')',
    '[': ']',
}
KEYWORD_CHARS = ascii_letters + digits
PLACEHOLDER_CHARS = ascii_letters + digits
IDENT_CHARS = ascii_letters + digits
NUMBER_CHARS = ascii_letters + digits + '.'


class Token(Enum):
    KEYWORD = 'keyword'
    PLACEHOLDER = 'placeholder'
    NEWLINE = 'newline'
    DOT = 'dot'
    STRING = 'string'
    IDENT = 'ident'
    NUMBER = 'number'
    OPEN_BRACE = 'open_brace'
    OPEN_PAREN = 'open_paren'
    OPEN_BRACKET = 'open_bracket'
    CLOSE_BRACE = 'close_brace'
    CLOSE_PAREN = 'close_paren'
    CLOSE_BRACKET = 'close_bracket'
    INDENT = 'indent'
    DEDENT = 'dedent'


BRACKET_NAMES = {
    '{': Token.OPEN_BRACE,
    '(': Token.OPEN_PAREN,
    '[': Token.OPEN_BRACKET,
    '}': Token.CLOSE_BRACE,
    ')': Token.CLOSE_PAREN,
    ']': Token.CLOSE_BRACKET,
}


class TokenizerError(Exception):
    def __init__(self, location, message):
        self.location = location
        self.message = message

    def __str__(self):
        return "{}: Tokenizer error {}".format(self.location, self.message)


class _Interrupt(Exception):
    pass


class Position(object):
    __slots__ = ('offset', 'line', 'column')

    def __init__(self, offset, line, column):
        self.offset = offset
        self.line = line
        self.column = column

    def __index__(self):
        return self.offset

    def __repr__(self):
        return '<Pos {}:{}[{}]>'.format(self.line, self.column, self.offset)


class Location(object):
    __slots__ = ('filename', 'start', 'end')

    def __init__(self, filename, start, end):
        self.filename = filename
        assert isinstance(start, Position), start
        assert isinstance(end, Position), start
        self.start = start
        self.end = end

    def __str__(self):
        if self.start.filename == self.end.filename:
            if self.start.offset == self.end.offset-1:
                return "{0.filename}:{0.start.line}:{0.start.column}"\
                    .format(self)
            else:
                return "{0.filename}:{0.start.line}:{0.start.column}\
                    -{0.end.line}:{0.end.column}".format(self)
        else:
            return "{0.filename}:{0.start.line}:{0.start.column}-\n"\
                "  {0.end.filename}:{0.end.line}:{0.end.column}"\
                .format(self)


class Chars(object):
    def __init__(self, string, filename):
        self.string = string
        self.filename = filename
        self.index = 0
        self.line = 1
        self.pos = 1

    def __iter__(self):
        return self


    def __next__(self):
        rpos = self.next_position
        if self.index >= len(self.string):
            raise StopIteration()
        char = self.string[self.index]
        self.index += 1
        self.pos += 1
        if char == '\n':
            self.line += 1
            self.pos = 1
        return rpos, char
    next = __next__  # crappy py2

    def peek(self):
        try:
            return self.string[self.index+1]
        except IndexError:
            return None

    @property
    def next_position(self):
        return Position(self.index, self.line, self.pos)

    def location_from(self, pos):
        return Location(self.filename, pos, self.next_position)


def read_slice(char_iter, valid_chars, name, start=None):
    start = start or char_iter.next_position
    while char_iter.peek() in valid_chars:
        next(char_iter)
    next(char_iter)
    end = char_iter.next_position
    return (name, char_iter.string[start:end],
        Location(char_iter.filename, start, end))


def read_string(char_iter, start, quote):
    start = start or char_iter.next_position
    for pos, ch in char_iter:
        if ch == '\'':
            try:
                next(char_iter)  # skip next character regardless of value
            except StopIteration:
                break
        elif ch == quote:
            return (Token.STRING,
                char_iter.string[start:char_iter.next_position],
                char_iter.location_from(start))
        elif ch == '\n':
            raise TokenizerError(char_iter.location_from(start),
                "Newlines are not allowed in strings")

    raise TokenizerError(char_iter.location_from(start),
        "String does not and at EOF")


def tokenize(string, filename='<string>'):
    """Tokenizes a text

    :param filename: a filename used for Location's

    Yields three-tuples: (token_type, literal_value, location)
    """
    char_iter = Chars(string, filename)
    brackets = []
    indents = [1]
    for pos, ch in char_iter:
        try:
            while pos.column == 1 and not brackets:
                start = end = pos
                while ch in whitespace:
                    if ch != ' ':
                        if ch == '\n':
                            break
                        raise TokenizerError(char_iter.location_from(start),
                            "Please indent by spaces. "
                            "Forget about that crappy {!r} characters"
                            .format(ch))
                    end = pos
                    try:
                        pos, ch = next(char_iter)
                    except StopIteration:
                        raise _Interrupt()
                if ch == ';':
                    # ignore comments
                    for _, ch in char_iter:
                        if ch == '\n':
                            break
                    try:
                        pos, ch = next(char_iter)
                    except StopIteration:
                        raise _Interrupt()
                    continue
                elif ch == '\n':
                    # ignore empty lines
                    try:
                        pos, ch = next(char_iter)
                    except StopIteration:
                        raise _Interrupt()
                    continue
                cur_indent = indents[-1]
                new_indent = pos.column
                loc = Location(filename, start, end)
                if new_indent < cur_indent:
                    try:
                        ident_pos = indents.index(new_indent)
                    except IndexError:
                        raise TokenizerError(loc,
                            "Unindent doesn't match any previous level "
                            "of indentation")
                    else:
                        for _i in range(ident_pos+1, len(indents)):
                            yield (Token.DEDENT, '', loc)
                        del indents[ident_pos+1:]
                elif new_indent > cur_indent:
                    indents.append(new_indent)
                    yield (Token.INDENT, '', loc)
                break
        except _Interrupt:
            break
        if ch == ':':
            yield read_slice(char_iter, KEYWORD_CHARS, Token.KEYWORD)
        elif ch == ';':
            for pos, ch in char_iter:
                if ch == '\n':
                    break
            yield (Token.NEWLINE, '\n', char_iter.location_from(pos))
        elif ch == '#':
            yield read_slice(char_iter, PLACEHOLDER_CHARS, Token.PLACEHOLDER)
        elif ch == '\n' and not brackets:
            yield (Token.NEWLINE, '\n', char_iter.location_from(pos))
        elif ch in whitespace:
            continue
        elif ch == '.':
            yield (Token.DOT, '.', char_iter.location_from(pos))
        elif ch == '"':
            yield read_string(char_iter, pos, '"')
        elif ch in ascii_letters:
            yield read_slice(char_iter, IDENT_CHARS, Token.IDENT, pos)
        elif ch in digits:
            yield read_slice(char_iter, NUMBER_CHARS, Token.NUMBER, pos)
        elif ch in '([{':
            brackets.append((ch, pos))
            yield (BRACKET_NAMES[ch], ch, char_iter.location_from(pos))
        elif ch in '}])':
            if brackets:
                bch, bpos = brackets.pop()
                if MATCHING_BRACKET[bch] != ch:
                    raise TokenizerError(char_iter.location_from(bpos),
                        "Unmatching parenthesis, expected {!r} got {!r}"
                        .format(MATCHING_BRACKET[bch], ch))
            else:
                raise TokenizerError(char_iter.location_from(pos),
                    "No parenthesis matching {!r}".format(ch))
            yield (BRACKET_NAMES[ch], ch, char_iter.location_from(pos))
        else:
            raise TokenizerError(char_iter.location_from(pos),
                "Wrong character {!r}".format(ch))
    else:
        eof_pos = char_iter.location_from(char_iter.next_position)
        if char_iter.next_position.column != 1:
            yield (Token.NEWLINE, '\n', eof_pos)
    eof_pos = char_iter.location_from(char_iter.next_position)
    for i in range(1, len(indents)):
        yield (Token.DEDENT, '', eof_pos)


