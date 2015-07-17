from kinko.checker import check, global_scope
from kinko.nodes import Tuple, Symbol


src = Tuple(Symbol('div'),
            # Keyword('class'), "b-panel",
            # Keyword('data-status'), "enabled",
            Tuple(Symbol('div'),
                  # Keyword('class'), "b-panel__content",
                  """
                  Some content
                  """,
                  Symbol('setting')))


print check(src, global_scope)
