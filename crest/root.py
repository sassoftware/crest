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

import os

from restlib import controller
from restlib import response
from xobj import xobj

import repquery

class XMLResponse(response.Response):
    def __init__(self, content, contentType='text/xml; charset=utf-8'):
        response.Response.__init__(self, content, contentType)
        self.headers['cache-control'] = 'private, must-revalidate, max-age=0'

class FileResponse(response.FileResponse):

    def __init__(self, path, remotePath = None, gzipped = False):
        response.FileResponse.__init__(self, path = path)
        self.headers['cache-control'] = 'private, must-revalidate'
        self.headers['Content-Disposition'] = 'attachment'
        if remotePath:
            self.headers['Content-Disposition'] += '; filename=%s' % remotePath
        #if gzipped:
            #self.headers['content-encoding'] = 'gzip'

class RestController(controller.RestController):

    pass

class GetTrove(RestController):

    def index(self, request, cu = None, roleIds = None, *args, **kwargs):
        label = request.GET.get('label', None)
        name = request.GET.get('name', None)
        types = request.GET.get('type', [])
        latest = request.GET.get('latest', 1)
        if type(types) != list:
            types = [ types ]

        latest = (latest != '0')

        types = set(types)

        first = int(request.GET.get('first', 0))
        count = request.GET.get('count', None)
        if count is not None: count = int(count)

        troves = repquery.searchTroves(cu, roleIds, label = label,
                                       filterSet = types, latest = latest,
                                       mkUrl = request.makeUrl,
                                       first = first, count = count,
                                       name = name)

        return XMLResponse(xobj.toxml(troves, None))

    modelName = "troveString"
    modelRegex = '.*\[.*\]'

    def get(self, request, cu = None, roleIds = None, troveString = None,
            repos = None, *args, **kwargs):
        name, rest = troveString.split('=', 2)
        version, flavor = rest.split("[", 2)
        flavor = flavor[:-1]

        x = repquery.getTrove(cu, roleIds, name, version, flavor,
                              mkUrl = request.makeUrl, thisHost = request.host)
        if x is None:
            raise NotImplementedError

        return XMLResponse(xobj.toxml(x, None))

class GetFile(RestController):

    modelName = "fileId"
    urls = { 'info' : { 'GET' : 'info' },
             'content' : { 'GET' : 'content' }}

    def info(self, request, cu, roleIds = None, fileId = None, **kwargs):
        x = repquery.getFileInfo(cu, roleIds, fileId, mkUrl = request.makeUrl)
        if x is None:
            raise NotImplementedError

        return XMLResponse(xobj.toxml(x, None))

    def content(self, request, cu, roleIds = None, fileId = None,
                repos = None, **kwargs):
        sha1 = repquery.getFileSha1(cu, roleIds, fileId)
        if sha1 is None:
            raise NotImplementedError

        path = repos.repos.contentsStore.hashToPath(sha1)
        return FileResponse(path, gzipped = True, remotePath = '%s.gz' % sha1)

class Controller(RestController):

    urls = { 'trove'  : GetTrove,
             'file'   : GetFile }

    def index(self, request, cu = None, roleIds = None, *args, **kwargs):
        l = repquery.getRepository(cu, roleIds, mkUrl = request.makeUrl)
        return XMLResponse(xobj.toxml(l, None))

