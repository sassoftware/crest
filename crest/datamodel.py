#
# Copyright (c) 2009 rPath, Inc.
#
# This program is distributed under the terms of the Common Public License,
# version 1.0. A copy of this license should have been distributed with this
# source file in a file called LICENSE. If it is not present, the license
# is always available at http://www.rpath.com/permanent/licenses/CPL-1.0.
#
# This program is distributed in the hope that it will be useful, but
# without any warranty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the Common Public License for
# full details.
#

import urllib

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

class Version(BaseObject):

    full = str
    label = str
    revision = str
    ordering = float

    def __init__(self, v):
        self.full = str(v)
        self.label = str(v.trailingLabel())
        self.revision = str(v.trailingRevision())
        # we don't use getTimestamp here because 0 is okay...
        ts = v.trailingRevision().timeStamp
        self.ordering = ts

class BaseTroveInfo(BaseObject):

    _xobj = xobj.XObjMetadata(attributes = { 'id' : str })
    name = str
    version = Version
    flavor = str

    def __init__(self, version = None, mkUrl = None, **kwargs):
        BaseObject.__init__(self, **kwargs)
        self.version = Version(version)
        if mkUrl:
            host = version.trailingLabel().getHost()
            self.id = mkUrl('trove', "%s=%s[%s]" % (self.name, version,
                                                    self.flavor),
                            host = host)

class TroveIdent(BaseTroveInfo):

    _xobj = xobj.XObjMetadata(attributes = { 'id' : str }, tag = 'trove')

class TroveIdentList(BaseObject):

    _xobj = xobj.XObjMetadata(tag = 'trovelist',
                              attributes = { 'total' : int, 'start' : int,
                                             'id' : str, 'href' : str } )
    troveList = [ TroveIdent ]

    def append(self, name = None, version = None, flavor = None, mkUrl = None):
        self.troveList.append(TroveIdent(name = name, version = version,
                                         flavor = flavor, mkUrl = mkUrl))

class Label(BaseObject):

    name = str
    latest = TroveIdentList

class FileId(xobj.XObj):

    _xobj = xobj.XObjMetadata(attributes = { 'href' : str })

class FileReference(BaseObject):

    _xobj = xobj.XObjMetadata(attributes = { 'id' : str })

    path = str
    version = str
    fileId = str
    pathId = str

    def __init__(self, mkUrl = None, fileId = None, version = None,
                 thisHost = None, **kwargs):
        BaseObject.__init__(self, fileId = fileId, version = version, **kwargs)
        if mkUrl:
            host = versions.VersionFromString(version).trailingLabel().getHost()
            self.id = mkUrl('file', self.fileId, 'info', host = host)

class ReferencedTrove(BaseTroveInfo):

    pass

class SingleTrove(TroveIdent):

    _xobj = xobj.XObjMetadata(attributes = { 'id' : str }, tag = 'trove')
    fileref = [ FileReference ]
    trove = [ ReferencedTrove ]
    source = BaseTroveInfo
    buildtime = long
    clonedfrom = [ BaseTroveInfo ]
    size = long

    def addFile(self, f):
        self.fileref.append(f)

    def addReferencedTrove(self, name, version, flavor, mkUrl = None):
        self.trove.append(ReferencedTrove(name = name, version = version,
                                           flavor = flavor, mkUrl = mkUrl))

    def addClonedFrom(self, name, version, flavor, mkUrl = None):
        self.clonedfrom.append(BaseTroveInfo(name = name,version = version,
                                             flavor = flavor, mkUrl = mkUrl))

class FileObj(BaseObject):

    _xobj = xobj.XObjMetadata(attributes = { 'id' : str })

    owner = str
    group = str
    mtime = long
    perms = int

    def __init__(self, mkUrl = None, fileId = None, **kwargs):
        BaseObject.__init__(self, **kwargs)
        if mkUrl:
            self.id = mkUrl('file', fileId, 'info')

class XObjLong(long):

    pass

class RegularFile(FileObj):

    _xobj = xobj.XObjMetadata(attributes = { 'href' : str,
                                             'id' : str },
                              tag = 'file')
    size = XObjLong
    sha1 = str

    def __init__(self, mkUrl = None, fileId = None, **kwargs):
        FileObj.__init__(self, mkUrl = mkUrl, fileId = fileId, **kwargs)
        if mkUrl:
            self.href = mkUrl('file', fileId, 'content')

class Directory(FileObj):

    _xobj = xobj.XObjMetadata(attributes = { 'id' : str }, tag = 'directory')

class Socket(FileObj):

    _xobj = xobj.XObjMetadata(attributes = { 'id' : str }, tag = 'socket')

class NamedPipe(FileObj):

    _xobj = xobj.XObjMetadata(attributes = { 'id' : str }, tag = 'namedpipe')

class SymlinkFile(FileObj):

    _xobj = xobj.XObjMetadata(attributes = { 'id' : str }, tag = 'symlink')
    target = str

class _DeviceFile(FileObj):

    major = int
    minor = int

class BlockDeviceFile(_DeviceFile):
    _xobj = xobj.XObjMetadata(attributes = { 'id' : str }, tag = 'blockdevice')

class CharacterDeviceFile(_DeviceFile):
    _xobj = xobj.XObjMetadata(attributes = { 'id' : str }, tag = 'chardevice')

class Repository(BaseObject):

    _xobj = xobj.XObjMetadata(attributes = { 'id' : str }, tag = 'repository')
    label = [ str ]
    trovelist = TroveIdentList

    def appendLabel(self, labelStr, mkUrl = None):
        l = Label(name = labelStr)
        if mkUrl:
            l.latest = TroveIdentList(href =
                            mkUrl('trove',  [ ('label', labelStr) ]))
        self.label.append(l)

