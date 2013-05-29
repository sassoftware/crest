#
# Copyright (c) SAS Institute Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


import base64
import lxml
import os
import urllib, urllib2, urlparse

from conary_test.rephelp import RegularFile, Symlink, Directory, BlockDevice
from conary_test.rephelp import CharacterDevice, Socket, NamedPipe
from conary_test.auth_helper import AuthHelper

from conary import trove
from conary.lib import util

from crest import datamodel

from conary import versions

from xobj import xobj

class Server:
    server_name = 'localhost'
    server_port = 80

class RestTest(AuthHelper):

    def makeHandler(self):
        class Handler:
            def c(self, url, raw = False, auth = ('test', 'foo'),
                  entitlements = [], checkHeaders = {}):
                if not url.startswith('http:'):
                    url = 'http://localhost' + url

                    (scheme, netloc, path, query, fragment) = \
                        urlparse.urlsplit(url)

                    mappedLoc = self.map[netloc]

                    finalUrl = "%sapi%s" % (mappedLoc, path)

                    if query:
                        finalUrl += '?' + query
                else:
                    finalUrl = url

                req = urllib2.Request(finalUrl)

                if auth:
                    req.add_header('Authorization',
                            'Basic ' + base64.encodestring('%s:%s' % auth))

                if entitlements:
                    l = [ "* %s" % base64.b64encode(x) for x in entitlements ]
                    req.add_header('X-Conary-Entitlement', " ".join(l))

                f = urllib2.urlopen(req)
                for key, val in checkHeaders.iteritems():
                    assert(f.headers[key] == val)

                s = f.read()
                f.close()

                if raw:
                    return s

                return xobj.parse(s)

            def e(self, *args, **kwargs):
                try:
                    s = self.c(*args, **kwargs)
                except IOError:
                    return
                except lxml.etree.XMLSyntaxError:
                    return

                assert(0)

            def __init__(self, repos):
                self.map = repos.c.map
                self.repos = repos

        repos = self.openRepository(0)
        repos.deleteUserByName(self.cfg.buildLabel, 'anonymous')

        for user in [ ('user1', 'pw1'), ('user2', 'pw2') ]:
            self.addUserAndRole(repos, self.cfg.buildLabel, user[0], user[1])
            l = versions.Label('localhost@ns:%s' % user[0])
            repos.addAcl(l,  user[0], 'ALL', l)

        return Handler(repos)

    def testRepository(self):
        handler = self.makeHandler()
        self.addComponent('foo:runtime')
        self.addComponent('bar:runtime=localhost@ns:label1')
        self.addComponent('foo:runtime=localhost@ns:user1')
        resp = handler.c('/')
        assert([ x.name for x in resp.repository.label ] ==
                    ['localhost@ns:label1', 'localhost@ns:user1',
                      'localhost@rpl:linux'] )

        resp = handler.c('/', auth = ('user1', 'pw1'))
        assert(resp.repository.label.name == 'localhost@ns:user1' )
        assert(urllib.unquote(resp.repository.label.latest.id).endswith(
                                '/trove?label=localhost@ns:user1' ))
        assert(urllib.unquote(resp.repository.label.summary.href).endswith(
                                '/node?label=localhost@ns:user1&type=package'
                                '&type=group&type=fileset' ))
        assert(urllib.unquote(resp.repository.label.groups.href).endswith(
                                '/node?label=localhost@ns:user1&type=group'))
        assert(urllib.unquote(resp.repository.label.sources.href).endswith(
                                '/node?label=localhost@ns:user1&type=source'))
        assert(urllib.unquote(resp.repository.label.packages.href).endswith(
                                '/node?label=localhost@ns:user1&type=package'
                                '&type=fileset' ))

        resp = handler.c('/', auth = ('user2', 'pw2'))
        assert('label' not in resp.repository.__dict__)

    @staticmethod
    def nvf(trv):
        return '%s=%s[%s]' % (trv.getName(), trv.getVersion(),
                              urllib.quote(str(trv.getFlavor())))

    def testGetTrove(self):
        handler = self.makeHandler()
        repos = self.openRepository()
        breq1 = self.addComponent('br1:runtime=localhost@ns:user1/1.0-1-1')
        breq1TrvTup = repos.findTrove(None, breq1.getNameVersionFlavor())[0]

        visibleTrv = self.addComponent(
                        'foo:runtime=localhost@ns:user1/1.0-1-1[is:x86]',
                        fileContents = [
                                ('/etc/path',
                                 RegularFile(contents = 'fileContents',
                                             pathId = '1234') ) ] )
        visibleTrvTup = repos.findTrove(None, visibleTrv.getNameVersionFlavor())[0]
        sourceTrv = self.addComponent('foo:source=localhost@ns:user1/1.0-1')
        packageTrv = self.addCollection(
                    'foo=localhost@ns:user1/1.0-1-1[is:x86]',
                    buildReqs = [ breq1.getNameVersionFlavor() ],
                    strongList = [ ':runtime' ],
                    weakRefList = [ ':debuginfo' ] )
        packageTrvTup = repos.findTrove(None, packageTrv.getNameVersionFlavor())[0]

        componentUri = '/trove/%s' % self.nvf(visibleTrv)
        resp = handler.c(componentUri)
        assert(resp.trove.name == 'foo:runtime')
        assert(resp.trove.version.full == '/localhost@ns:user1/1.0-1-1')
        assert(resp.trove.version.label == 'localhost@ns:user1')
        assert(resp.trove.version.revision == '1.0-1-1')
        self.failUnlessEqual("%.2f" % float(resp.trove.version.ordering),
            "%.2f" % visibleTrvTup[1].trailingRevision().timeStamp)
        assert(resp.trove.flavor == 'is: x86')
        assert('id' in resp.trove._xobj.attributes)
        componentId = resp.trove.id
        assert(urllib.unquote(componentId).endswith(
                                    urllib.unquote(componentUri)))
        # file id's are checkd in testFiles instead of here
        assert(type(resp.trove.fileref) != list)
        assert('id' in resp.trove.fileref.inode._xobj.attributes)
        assert(resp.trove.fileref.path == '/etc/path')
        assert(resp.trove.fileref.pathId == '31323334303030303030303030303030')
        assert(resp.trove.fileref.fileId ==
                        '969841a9d366cf44071a445bf67af4a635ca34c3')
        assert(resp.trove.fileref.version == '/localhost@ns:user1/1.0-1-1')
        assert('troves' not in resp.trove.__dict__)
        assert(int(resp.trove.buildtime) == 1238075164)
        assert(int(resp.trove.size) == 12)
        assert('clonedfrom' not in dir(resp.trove))
        assert('included' not in dir(resp.trove))

        resp = handler.c('/trove/%s' % self.nvf(packageTrv))

        assert(resp.trove.name == 'foo')
        assert(resp.trove.version.full == '/localhost@ns:user1/1.0-1-1')
        self.failUnlessEqual("%.2f" % float(resp.trove.version.ordering),
            "%.2f" % packageTrvTup[1].trailingRevision().timeStamp)
        assert(resp.trove.flavor == 'is: x86')
        assert(type(resp.trove.included.trovelist.trove) != list)
        assert(resp.trove.included.trovelist.trove.id == componentId)
        assert('id' in resp.trove.included.trovelist.trove._xobj.attributes)
        assert(resp.trove.included.trovelist.trove.name == 'foo:runtime')
        assert(resp.trove.included.trovelist.trove.version.full ==
                            '/localhost@ns:user1/1.0-1-1')
        self.failUnlessEqual(
            "%.2f" % float(resp.trove.included.trovelist.trove.version.ordering),
            "%.2f" % visibleTrvTup[1].trailingRevision().timeStamp)
        assert(resp.trove.included.trovelist.trove.flavor == 'is: x86')
        assert(resp.trove.included.displayname == 'Includes')
        assert(urllib.unquote(resp.trove.source.trovelist.trove.id).endswith(
                    '/trove/foo:source=/localhost@ns:user1/1.0-1[]'))
        assert(resp.trove.source.displayname == 'Source')
        assert('id' in resp.trove.source.trovelist.trove._xobj.attributes)
        assert('files' not in resp.trove.__dict__)
        self.failUnlessEqual(
            "%.2f" % float(resp.trove.builddeps.trovelist.trove.version.ordering),
            # XXX Build reqs saved in the trove info do not have the timestamp set
            # "%.2f" % breq1TrvTup[1].trailingRevision().timeStamp)
            "0.00")

        handler.e('/trove/%s' % self.nvf(visibleTrv), auth = ('user2', 'pw2'))

        self.clone('/localhost@ns:clone', 'foo:source=localhost@ns:user1')
        resp = handler.c('/trove/foo:source=/localhost@ns:clone/1.0-1[]')
        assert(resp.trove.clonedfrom.displayname == 'Cloned from')
        assert(urllib.unquote(resp.trove.clonedfrom.trovelist.trove.id).endswith(
                     '/trove/foo:source=/localhost@ns:user1/1.0-1[]'))

    def testGetFile(self):
        handler = self.makeHandler()
        trv = self.addComponent(
                        'foo:runtime=localhost@ns:user1/1.0-1-1[is:x86]',
                        fileContents = [
                                ('/dev/block', BlockDevice(major = 1,
                                                           minor = 2)),
                                ('/dev/char', CharacterDevice(major = 3,
                                                              minor = 4)),
                                ('/etc/directory', Directory(mode = 0123,
                                                             owner = 'john',
                                                             group = 'doe')),
                                ('/etc/link',
                                 Symlink(target = 'symtarget')),
                                ('/etc/namedpipe', NamedPipe()),
                                ('/etc/regular',
                                    RegularFile(contents='fileContents', pathId
                                        = '1234') ),
                                ('/etc/socket', Socket()),
                                ('/usr/bin/regular',
                                    RegularFile(contents='fileContents',
                                        pathId='4567')),
                        ] )

        t = handler.c('/trove/%s' % self.nvf(trv))
        paths = [ x.path for x in t.trove.fileref ]
        assert(paths == sorted(paths))

        fileInfo = [ handler.c(x.inode.id) for x in t.trove.fileref ]
        (block, char, directory, symlink, namedPipe,
                regular, socket, regBin) = fileInfo

        assert(block.blockdevice.major == '1')
        assert(block.blockdevice.minor == '2')
        assert(block.blockdevice.id ==
                    t.trove.fileref[0].inode.id.split('?')[0])
        assert('id' in block.blockdevice._xobj.attributes)
        assert('href' not in dir(block.blockdevice))
        assert(char.chardevice.major == '3')
        assert(char.chardevice.minor == '4')
        assert(int(directory.directory.perms) == 0123)
        assert(directory.directory.owner == 'john')
        assert(directory.directory.group == 'doe')
        assert(symlink.symlink.target == 'symtarget')
        assert('socket' in dir(socket))
        assert('namedpipe' in dir(namedPipe))

        # config file
        assert(regular.file.sha1 == '6446a6956eb3f9780f9c71516a455c14f8237db4')
        assert(regular.file.size == '12')
        assert('content' in regular.file._xobj.elements)
        assert(regular.file.content.href.endswith(
            '/file/%s/content/regular' % t.trove.fileref[5].fileId))
        contents = handler.c(regular.file.content.href, raw=True,
                checkHeaders={'content-type': 'text/plain'})
        assert(util.decompressString(contents) == 'fileContents')

        # text file
        assert(regBin.file.sha1 == '6446a6956eb3f9780f9c71516a455c14f8237db4')
        assert(regBin.file.size == '12')
        assert('content' in regBin.file._xobj.elements)
        assert(regBin.file.content.href.endswith(
            '/file/%s/content/regular' % t.trove.fileref[7].fileId))
        contents = handler.c(regBin.file.content.href, raw=True, checkHeaders={
                    'content-disposition' : 'attachment; filename=regular',
                    'content-type': 'application/octet-stream', })
        assert(util.decompressString(contents) == 'fileContents')

        # This file type doesn't have contents (which is why it doesn't have
        # an href attribute
        handler.e('/file/%s/content' % t.trove.fileref[0].fileId)
        handler.e('/file/0101010101010101010101010101010101010101/info')

    def testBadConstructor(self):
        self.assertRaises(TypeError,
                          datamodel.BlockDeviceFile, target = 'hello')

    def testTrove(self):
        def _names(r):
            if type(resp.trovelist.trove) is list:
                return [ x.name for x in resp.trovelist.trove ]
            return [ resp.trovelist.trove.name ]

        def _versions(r):
            if type(resp.trovelist.trove) is list:
                return [ x.version for x in resp.trovelist.trove ]
            return [ resp.trovelist.trove.version ]

        handler = self.makeHandler()
        self.addComponent('hello:runtime=0.1')
        self.addComponent('hello:runtime')       # version 1.0 by default
        self.addComponent('hello:lib')
        self.addComponent('hello:source')
        self.addComponent('fileset-test=2.0-2-1[is:x86_64]')
        self.addCollection('hello', [ ':runtime', ':lib', ':source' ])
        self.addCollection('group-hello', [ 'hello', 'fileset-test' ])

        basicQ = "/trove?label=%s" % str(self.cfg.buildLabel)
        resp = handler.c(basicQ)
        assert(resp.trovelist.total == '6')
        assert(_names(resp) == [ 'fileset-test', 'group-hello', 'hello',
                                 'hello:lib', 'hello:runtime', 'hello:source' ])
        assert(resp.trovelist.total == '6')
        assert(resp.trovelist.trove[0].version.full ==
                        '/localhost@rpl:linux/2.0-2-1')
        assert(float(resp.trovelist.trove[0].version.ordering) > 0)
        assert(resp.trovelist.trove[0].flavor == 'is: x86_64')

        # test paging
        resp = handler.c(basicQ + '&start=2&limit=3')
        assert(resp.trovelist.total == '6')
        assert('total' in resp.trovelist._xobj.attributes)
        assert(_names(resp) == [ 'hello', 'hello:lib', 'hello:runtime' ])
        resp = handler.c(basicQ + '&start=3')
        assert(resp.trovelist.total == '6')
        assert(_names(resp) == [ 'hello:lib', 'hello:runtime', 'hello:source' ])
        resp = handler.c(basicQ + '&limit=1')
        assert(resp.trovelist.total == '6')
        assert(_names(resp) == [ 'fileset-test' ])

        resp = handler.c(basicQ + '&type=group')
        assert(_names(resp) == [ 'group-hello' ])
        resp = handler.c(basicQ + '&type=group&type=fileset')
        assert(_names(resp) == [ 'fileset-test', 'group-hello' ])
        resp = handler.c(basicQ + '&type=source')
        assert(_names(resp) == [ 'hello:source' ])
        resp = handler.c(basicQ + '&type=component')
        assert(_names(resp) == [ 'hello:lib', 'hello:runtime', 'hello:source' ])
        resp = handler.c(basicQ + '&type=binarycomponent')
        assert(_names(resp) == [ 'hello:lib', 'hello:runtime' ])
        resp = handler.c(basicQ + '&type=package')
        assert(_names(resp) == [ 'hello' ])
        resp = handler.c(basicQ + '&type=collection')
        assert(_names(resp) == [ 'group-hello', 'hello' ])

        resp = handler.c(basicQ + '&type=binarycomponent&latest=0')
        assert(_names(resp) ==
                        [ 'hello:lib', 'hello:runtime', 'hello:runtime' ])
        assert(resp.trovelist.total == '3')
        assert(repr(_versions(resp) ==
                        [ '/localhost@rpl:linux/1.0-1-1',
                          '/localhost@rpl:linux/0.1-1-1',
                          '/localhost@rpl:linux/0.2-1-1' ]))

        resp = handler.c(basicQ + '&name=hello:runtime')
        assert(_names(resp) == [ 'hello:runtime' ])
        resp = handler.c(basicQ + '&name=hello:runtime&latest=0')
        assert(_names(resp) == [ 'hello:runtime', 'hello:runtime' ])
        resp = handler.c(basicQ + '&name=hello.*')
        assert(_names(resp) == [ 'hello', 'hello:lib', 'hello:runtime',
                                 'hello:source'])
        resp = handler.c(basicQ + '&name=h.llo:.*')
        assert(_names(resp) == [ 'hello:lib', 'hello:runtime', 'hello:source'])

        # simple permissions check
        resp = handler.c(basicQ, auth = ('user1', 'pw1'))
        assert('trove' not in dir(resp.trovelist))
        repos = self.openRepository(0)
        repos.addAcl(self.cfg.buildLabel,  'user1', 'ALL', self.cfg.buildLabel)
        resp = handler.c(basicQ, auth = ('user1', 'pw1'))
        assert(len(resp.trovelist.trove) == 6)

        resp = handler.c('/trove')
        assert(_names(resp) ==
                ['fileset-test', 'group-hello', 'hello', 'hello:lib',
                 'hello:runtime', 'hello:source'])

        resp = handler.c('/trove?latest=0')
        assert(_names(resp) ==
                ['fileset-test', 'group-hello', 'hello', 'hello:lib',
                 'hello:runtime', 'hello:runtime', 'hello:source'])

    def testDistributed(self):
        handler = self.makeHandler()

        comp = self.addComponent('foo:runtime', fileContents =
            [ ('/local', RegularFile(version = '1.0')),
              ('/remote', RegularFile(version = 'localhost2@foo:bar'))
            ] )

        resp = handler.c('/trove/%s' % self.nvf(comp))
        assert(resp.trove.fileref[0].path == '/local')
        assert(resp.trove.fileref[0].inode.id.startswith('http://localhost:'))
        assert(resp.trove.fileref[1].path == '/remote')
        assert(resp.trove.fileref[1].inode.id.startswith(
                                'http://localhost2/conary/api/'))

        group = self.addCollection('group-foo',
                                   [ 'foo:runtime',
                                     'other:runtime=localhost3@foo:bar' ])

        resp = handler.c('/trove/%s' % self.nvf(group))
        assert(resp.trove.included.trovelist.trove[0].name == 'foo:runtime')
        assert(resp.trove.included.trovelist.trove[0].id.startswith(
                    'http://localhost:'))
        assert(resp.trove.included.trovelist.trove[1].name == 'other:runtime')
        assert(resp.trove.included.trovelist.trove[1].id.startswith(
                    'http://localhost3/conary/api/'))

    def testEntitlements(self):
        handler = self.makeHandler()
        self.setupEntitlement(handler.repos, "entGroup", "12345",
                              self.cfg.buildLabel, None,
                              self.cfg.buildLabel, withClass = True)

        self.addComponent('foo:runtime')
        self.addComponent('bar:runtime=localhost@ns:hidden')

        resp = handler.c('/', auth = None, entitlements = [ "12345" ])
        assert(resp.repository.label.name == 'localhost@rpl:linux' )

        resp = handler.c('/')
        assert(len(resp.repository.label) == 2)

    def testNodes(self):
        handler = self.makeHandler()
        self.addComponent('foo:runtime=1.0[is:x86]')
        self.addComponent('foo:runtime=1.0[is:x86_64]')
        self.addComponent('foo:runtime=2.0[is:x86]')

        resp = handler.c('/node?label=localhost@rpl:linux')
        assert(resp.nodelist.node.name == 'foo:runtime')
        assert(resp.nodelist.node.version.revision == '2.0-1-1')
        assert(urllib.unquote(resp.nodelist.node.trovelist.id).endswith(
            '/troves/foo:runtime=/localhost@rpl:linux/2.0-1-1'))
        assert(urllib.unquote(resp.nodelist.node.fullnodelist.id).endswith(
            '/node?label=localhost@rpl:linux&name=foo:runtime&latest=0'))

        tresp = handler.c(resp.nodelist.node.trovelist.id)
        assert(type(tresp.trovelist.trove) != list)
        assert(tresp.trovelist.trove.name == 'foo:runtime')
        assert(tresp.trovelist.trove.version.full ==
                        '/localhost@rpl:linux/2.0-1-1')
        assert(tresp.trovelist.trove.flavor == 'is: x86')

        self.addCollection('foo=1.0[is:x86]', [ 'foo:runtime' ])
        resp = handler.c('/node?label=localhost@rpl:linux&type=package')
        assert(type(resp.nodelist.node) != list)

        self.addComponent('foo:lib=1.0[is:x86]')
        self.addComponent('foo:lib=2.0[is:x86]')

        resp = handler.c('/node?label=localhost@rpl:linux&name=foo:lib')
        resp.nodelist.node.name == 'foo:lib'
        resp.nodelist.node.version.revision == '2.0-1-1'
        resp = handler.c(
                    '/node?label=localhost@rpl:linux&name=foo:lib&latest=0')
        assert(len(resp.nodelist.node) == 2)

    def testMetadata(self):
        repos = self.openRepository(0)
        handler = self.makeHandler()

        mi = trove.MetadataItem()
        mi.shortDesc.set('summary')
        mi.longDesc.set('description')

        trv = self.addComponent('foo:runtime', metadata = mi)
        resp = handler.c('/trove/%s' % self.nvf(trv))
        assert(resp.trove.shortdesc == 'summary')
        assert(resp.trove.longdesc == 'description')
        assert('license' not in dir(resp.trove))
        assert('crypto' not in dir(resp.trove))

        mi = trove.MetadataItem()
        mi.licenses.set('GPL')
        mi.licenses.set('BSD')
        mi.crypto.set('blowfish')
        mi.crypto.set('sha1')
        trv = self.addComponent('foo:runtime=2', metadata = mi)
        resp = handler.c('/trove/%s' % self.nvf(trv))
        assert('shortdesc' not in dir(resp.trove))
        assert('longdesc' not in dir(resp.trove))
        assert(resp.trove.license == [ 'BSD', 'GPL' ])
        assert(resp.trove.crypto == [ 'blowfish', 'sha1' ])

    def testTroveListDisplayFlavors(self):
        handler = self.makeHandler()
        for f in [ 'foo,bar,baz is:x86', 'foo,baz is:x86', 'bar,baz is:x86' ]:
            self.addComponent('foo:runtime[%s]' % f)

        resp = handler.c('/node?label=localhost@rpl:linux')
        resp = handler.c(resp.nodelist.node.trovelist.id)
        flavors = dict([ (x.flavor, x.displayflavor) for x in
                        resp.trovelist.trove ])
        assert(flavors == { 'baz,foo is: x86': 'foo',
                            'bar,baz is: x86': 'bar',
                            'bar,baz,foo is: x86': 'bar,foo' })

        self.addComponent('foo:runtime[baz is:x86_64]')
        resp = handler.c('/node?label=localhost@rpl:linux')
        resp = handler.c(resp.nodelist.node.trovelist.id)
        flavors = dict([ (x.flavor, x.displayflavor) for x in
                        resp.trovelist.trove ])

        assert(flavors == { 'baz,foo is: x86': 'foo is: x86',
                            'baz is: x86_64': 'is: x86_64',
                            'bar,baz is: x86': 'bar is: x86',
                            'bar,baz,foo is: x86': 'bar,foo is: x86'} )

    def testBuildLogs(self):
        def _mklog(contents):
            os.chdir(self.workDir)
            f = open("tmplog", "w")
            f.write(contents)
            f.close()
            os.system("bzip2 < tmplog > tmplog.bz2")
            compressedContents = open("tmplog.bz2").read()
            os.unlink("tmplog")
            os.unlink("tmplog.bz2")
            return compressedContents

        handler = self.makeHandler()
        xmlLog = _mklog("xml log")
        textLog = _mklog("text log")

        self.addComponent("foo:debuginfo=1",
                          [ ('/usr/src/debug/buildlogs/foo-log.bz2', textLog),
                            ('/usr/src/debug/buildlogs/foo-xml.bz2', xmlLog) ])
        self.addComponent("foo:runtime=1")
        self.addCollection("foo=1", [ ":debuginfo", ":runtime" ])

        resp = handler.c('/troves/foo%3D/localhost%40rpl%3Alinux/1-1-1')

        gzipped = handler.c(resp.trovelist.trove.buildlog.id, raw = True)
        assert(util.decompressString(gzipped) == "text log")

        gzipped = handler.c(resp.trovelist.trove.xmlbuildlog.id, raw = True)
        assert(util.decompressString(gzipped) == "xml log")

    def testContainer(self):
        cmp = self.addRPMComponent("simple:rpm=1.0", 'simple-1.0-1.i386.rpm')
        handler = self.makeHandler()
        resp = handler.c('/trove/%s' % self.nvf(cmp))
        fileObjs = dict((x.path, x) for x in resp.trove.fileref)
        assert(not hasattr(fileObjs['/config'], 'isCapsule'))
        assert(not hasattr(fileObjs['/normal'], 'isCapsule'))
        assert(fileObjs['simple-1.0-1.i386.rpm'].isCapsule)

        fileRef = handler.c(fileObjs['/normal'].inode.id)
        assert(not hasattr(fileRef.file, 'content'))
        fileRef = handler.c(fileObjs['simple-1.0-1.i386.rpm'].inode.id)
        assert(    hasattr(fileRef.file, 'content'))
