HTML_ELEMENTS = frozenset((
    # root
    'html',

    # metadata
    'head', 'title', 'base', 'link', 'meta', 'style',

    # sections
    'body', 'article', 'section', 'nav', 'aside', 'h1', 'h2', 'h3', 'h4', 'h5',
    'h6', 'hgroup', 'headers', 'footer', 'address',

    # grouping content
    'p', 'hr', 'pre', 'blockquote', 'ol', 'ul', 'li', 'dl', 'dt', 'dd',
    'figure', 'figcaption', 'main', 'div',

    # text-level semantics
    'a', 'em', 'strong', 'small', 's', 'cite', 'q', 'dfn', 'abbr', 'ruby', 'rt',
    'rp', 'data', 'time', 'code', 'var', 'samp', 'kbd', 'sub', 'sup', 'i', 'b',
    'u', 'mark', 'bdi', 'bdo', 'span', 'br', 'wbr',

    # links
    'a', 'area',

    # edits
    'ins', 'del',

    # embedded content
    'picture', 'source', 'img', 'iframe', 'embed', 'object', 'param', 'video',
    'audio', 'track', 'map',

    # tabular data
    'table', 'caption', 'colgroup', 'col', 'tbody', 'thead', 'tfoot', 'tr',
    'td', 'th',

    # forms
    'form', 'label', 'input', 'button', 'select', 'datalist', 'optgroup',
    'option', 'textarea', 'keygen', 'output', 'progress', 'meter', 'fieldset',
    'legend',

    # interactive elements
    'details', 'summary', 'menu', 'menuitem', 'dialog',

    # scripting
    'script', 'noscript', 'template', 'canvas',
))

SELF_CLOSING_ELEMENTS = frozenset((
    'base',
    'link',
    'meta',
    'hr',
    'wbr',
    'img',
    'embed',
    'param',
    'source',
    'track',
    'area',
    'col',
    'input',
    'keygen',
    'menuitem',
))
