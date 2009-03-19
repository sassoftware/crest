from restlib.controller import RestController
from restlib.response import Response
from xobj import xobj

import repquery

class SearchTroves(RestController):

    def index(self, request, cu, roleIds, *args, **kwargs):
        label = request.GET.get('label', None)
        types = request.GET.get('type', [])
        latest = request.GET.get('latest', 1)
        if type(types) != list:
            types = [ types ]

        latest = (latest != '0')

        types = set(types)

        troves = repquery.searchTroves(cu, roleIds, label = label,
                                       filterSet = types, latest = latest,
                                       baseUrl = self.url(request, 'trove'))

        return Response(xobj.toxml(troves, "Response"))

class ListLabels(RestController):

    def index(self, request, cu, roleIds, *args, **kwargs):
        l = repquery.listLabels(cu, roleIds)
        return Response(xobj.toxml(l, "Response"))

class GetTrove(RestController):

    modelName = "troveString"
    modelRegex = '.*\[.*\]'

    def get(self, request, cu, roleIds, troveString, *args, **kwargs):
        name, rest = troveString.split('=', 2)
        version, flavor = rest.split("[", 2)
        flavor = flavor[:-1]

        x = repquery.getTrove(cu, roleIds, name, version, flavor,
                              baseUrl = request.baseUrl,
                              thisHost = request.host)
        if x is None:
            raise NotImplementedError

        return Response(xobj.toxml(x, "Response"))

class GetFile(RestController):

    modelName = "fileId"
    urls = { 'info' : { 'GET' : 'info' },
             'content' : { 'GET' : 'content' }}

    def info(self, request, cu, roleIds = None, fileId = None, **kwargs):
        x = repquery.getFileInfo(cu, roleIds, fileId,
                                 baseUrl = request.baseUrl)
        if x is None:
            raise NotImplementedError

        return Response(xobj.toxml(x, "Response"))

    def content(self, request, cu, roleIds = None, fileId = None,
                repos = None, **kwargs):
        sha1 = repquery.getFileSha1(cu, roleIds, fileId)
        if sha1 is None:
            raise NotImplementedError

        path = repos.repos.contentsStore.hashToPath(sha1)
        return Response(open(path).read())

class Controller(RestController):

    urls = { 'search' : SearchTroves,
             'labels' : ListLabels,
             'trove'  : GetTrove,
             'file'   : GetFile }
