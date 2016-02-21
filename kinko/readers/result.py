import weakref


class Ref(object):

    def __init__(self, result, entity, ident):
        self.result = weakref.proxy(result)
        self.entity = entity
        self.ident = ident

    def __getitem__(self, key):
        return self.result[self.entity].get(self.ident)[key]

    def __repr__(self):
        return '<{}:{}>'.format(self.entity, self.ident)

    def __eq__(self, other):
        return self.result[self.entity].get(self.ident) == other


class Result(dict):

    def ref(self, entity, ident):
        return Ref(self, entity, ident)
