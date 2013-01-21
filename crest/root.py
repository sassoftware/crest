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


import gzip, os

from conary.lib import util
from restlib import controller
from restlib import response
from xobj import xobj

import repquery

class XMLResponse(response.Response):
    def __init__(self, content, contentType='text/xml; charset=utf-8'):
        response.Response.__init__(self, content, contentType)
        self.headers['cache-control'] = 'private, must-revalidate, max-age=0'

class FileResponse(response.FileResponse):

    def __init__(self, path, remotePath=None, gzipped=False, download=True):
        response.FileResponse.__init__(self, path=path)
        self.headers['cache-control'] = 'private, max-age=3600'
        if download:
            self.headers['content-type'] = 'application/octet-stream'
            self.headers['content-disposition'] = 'attachment'
            if remotePath:
                self.headers['content-disposition'] += ('; filename=%s'
                        % (remotePath,))
        else:
            # Trick the browser into displaying the file inline
            self.headers['content-type'] = 'text/plain'

        if gzipped:
            self.headers['content-encoding'] = 'gzip'

class CompressFileResponse(response.Response):

    def getLength(self):
        return None

    def get(self):
        class Output:

            def write(self, stream):
                self.s += stream

            def get(self):
                s = self.s
                self.s = ''
                return s

            def __init__(self):
                self.s = ''

        # we read from self.fileObj, we write to the compressor, which sticks
        # the data in the Output object. We read from the Output object and
        # return it from the iterator so it can be sent to the requestor
        output = Output()
        compressor = gzip.GzipFile(None, "w", fileobj = output)

        BUFSZ = 1024 * 32
        s = self.fileObj.read(BUFSZ)
        while s:
            compressor.write(s)
            compressed = output.get()
            if compressed:
                yield compressed
            s = self.fileObj.read(BUFSZ)

        compressor.close()

        yield output.get()

    def __init__(self, fileObj):
        response.Response.__init__(self)

        self.fileObj = fileObj
        # since this is based on a fileId, no reason for it to timeout
        self.headers['cache-control'] = 'private'
        self.headers['content-type'] = 'text/plain'
        self.headers['content-encoding'] = 'gzip'

class RestController(controller.RestController):

    pass

class GetNode(RestController):

    def index(self, request, cu = None, roleIds = None, repos = None, *args,
              **kwargs):
        label = request.GET.get('label', None)
        name = request.GET.get('name', None)

        latest = request.GET.get('latest', 1)
        latest = (latest != '0')

        types = request.GET.get('type', [])
        if type(types) != list:
            types = [ types ]
        types = set(types)

        troves = repquery.searchNodes(cu, roleIds, label = label,
                                      mkUrl = request.makeUrl,
                                      filterSet = types, db = repos.db,
                                      name = name, latest = latest)
        return XMLResponse(xobj.toxml(troves, None))

class GetTrove(RestController):

    modelName = "troveString"
    modelRegex = '.*\[.*\]'

    def index(self, request, cu = None, roleIds = None, *args, **kwargs):
        label = request.GET.get('label', None)
        name = request.GET.get('name', None)

        latest = request.GET.get('latest', 1)
        latest = (latest != '0')

        types = request.GET.get('type', [])
        if type(types) != list:
            types = [ types ]
        types = set(types)

        start = int(request.GET.get('start', 0))
        if 'limit' in request.GET:
            limit = int(request.GET['limit'])
        else:
            limit = None

        troves = repquery.searchTroves(cu, roleIds, label = label,
                                       filterSet = types, latest = latest,
                                       mkUrl = request.makeUrl,
                                       start = start, limit = limit,
                                       name = name)

        return XMLResponse(xobj.toxml(troves, None))

    def get(self, request, cu = None, roleIds = None, troveString = None,
            repos = None, *args, **kwargs):
        name, rest = troveString.split('=', 2)
        version, flavor = rest.split("[", 2)
        flavor = flavor[:-1]

        x = repquery.getTrove(cu, roleIds, name, version, flavor,
                mkUrl=request.makeUrl, thisHost=request.headers['Host'],
                excludeCapsules=kwargs['excludeCapsules'])
        if x is None:
            return response.Response(status=404)

        return XMLResponse(xobj.toxml(x, None))

class GetTroves(RestController):

    modelName = "troveString"
    modelRegex = '.*'

    def get(self, request, cu = None, roleIds = None, troveString = None,
            repos = None, *args, **kwargs):
        name, version = troveString.split('=', 2)

        x = repquery.getTroves(cu, roleIds, name, version,
                mkUrl=request.makeUrl, thisHost=request.headers['Host'])
        if x is None:
            return response.Response(status=404)

        return XMLResponse(xobj.toxml(x, None))

class GetFile(RestController):

    modelName = "fileId"
    urls = { 'info' : { 'GET' : 'info' },
             'content' : { 'GET' : 'content' }}

    def info(self, request, cu, roleIds = None, fileId = None, **kwargs):
        path = request.GET.get('path', None)
        noContent = request.GET.get('nocontent', False)
        x = repquery.getFileInfo(cu, roleIds, fileId, mkUrl = request.makeUrl,
                                 path = path, noContent = noContent)
        if x is None:
            return response.Response(status=404)

        return XMLResponse(xobj.toxml(x, None))

    def content(self, request, cu, roleIds = None, fileId = None,
                repos = None, **kwargs):
        sha1, isConfig = repquery.getFileSha1(cu, roleIds, fileId)
        if sha1 is None:
            return response.Response(status=404)

        localPath = repos.repos.contentsStore.hashToPath(sha1)
        if request.unparsedPath:
            remotePath = os.path.basename(request.unparsedPath)
        else:
            remotePath = sha1
        return FileResponse(localPath, gzipped=True, remotePath=remotePath,
                download=not isConfig)

class GetLogFile(RestController):

    modelName = "fileId"

    def get(self, request, cu, roleIds = None, fileId = None,
            repos = None, **kwargs):
        sha1, isConfig = repquery.getFileSha1(cu, roleIds, fileId)
        if sha1 is None:
            return response.Response(status=404)

        localPath = repos.repos.contentsStore.hashToPath(sha1)
        bzippedFile = gzip.GzipFile(localPath, "r")
        uncompressedFile = util.BZ2File(bzippedFile)

        return CompressFileResponse(uncompressedFile)

class Controller(RestController):

    urls = { 'node'         : GetNode,
             'trove'        : GetTrove,
             'troves'       : GetTroves,
             'file'         : GetFile,
             'logfile'      : GetLogFile }

    def index(self, request, cu = None, roleIds = None, *args, **kwargs):
        l = repquery.getRepository(cu, roleIds, mkUrl = request.makeUrl)
        return XMLResponse(xobj.toxml(l, None))
