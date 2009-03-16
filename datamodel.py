from xobj import xobj

class BaseObject(object):

    def __init__(self, **kwargs):
        for key, val in self.__class__.__dict__.iteritems():
            if type(val) == list:
                setattr(self, key, [])

        for key, val in kwargs.iteritems():
            if (hasattr(self.__class__, key) or
                (hasattr(self, '_xobj') and key in (self._xobj.attributes))):
                setattr(self, key, val)
            else:
                raise TypeError, 'unknown constructor parameter %s' % key

class TroveIdent(BaseObject):

    name = str
    version = str
    flavor = str

class TroveList(BaseObject):

    trove = [ TroveIdent ]

class LabelList(BaseObject):

    label = [ str ]

    def append(self, labelStr):
        self.label.append(labelStr)
