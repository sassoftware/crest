from xobj import xobj
from conary import versions

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

    _xobj = xobj.XObjMetadata(attributes = { 'id' : str })

    name = str
    version = str
    flavor = str

    def __init__(self, baseUrl = None, **kwargs):
        BaseObject.__init__(self, **kwargs)
        if baseUrl:
            self.id = baseUrl + "%s=%s[%s]" % (self.name, self.version,
                                               self.flavor)

class TroveIdentList(BaseObject):

    trove = [ TroveIdent ]

class LabelList(BaseObject):

    label = [ str ]

    def append(self, labelStr):
        self.label.append(labelStr)

class FileId(xobj.XObjStr):

    _xobj = xobj.XObjMetadata(attributes = { 'href' : str })

class FileInTrove(BaseObject):

    _xobj = xobj.XObjMetadata(attributes = { 'id' : str })

    path = str
    version = str
    fileId = str
    pathId = str

    def __init__(self, baseUrl = None, fileId = None, version = None,
                 thisHost = None, **kwargs):
        BaseObject.__init__(self, fileId = fileId, version = version, **kwargs)
        if baseUrl:
            host = versions.VersionFromString(version).trailingLabel().getHost()
            if host == thisHost:
                prefix = baseUrl
            else:
                prefix = "http://%s/" % host

            self.id = ("%sfile/%s/info" % (prefix, self.fileId))

class SingleTrove(TroveIdent):

    file = [ FileInTrove ]

    def addFile(self, f):
        self.file.append(f)

class TroveList(BaseObject):

    trove = [ SingleTrove ]

class FileObj(BaseObject):

    owner = str
    group = str
    mtime = int
    perms = int

class XObjLong(long):

    pass

class RegularFile(FileObj):

    _xobj = xobj.XObjMetadata(attributes = { 'href' : str,
                                             'id' : str })
    _xobj.tag = 'File'

    size = XObjLong
    sha1 = str

    def __init__(self, baseUrl = None, fileId = None, sha1 = None, **kwargs):
        FileObj.__init__(self, **kwargs)
        if baseUrl:
            self.href = "%s/file/%s/content" % (baseUrl, fileId)
            self.id = "%s/file/%s/info" % (baseUrl, fileId)

class SymlinkFile(FileObj):

    _xobj = xobj.XObjMetadata()
    _xobj.tag = 'Symlink'
    target = str

class FileList(BaseObject):

    all = [ object ]

    def append(self, o):
        self.all.append(o)
