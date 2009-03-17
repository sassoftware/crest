from restlib.controller import RestController
from restlib.response import Response
from xobj import xobj

import repquery

class SearchTroves(RestController):

    def index(self, request, cu, roleIds, *args, **kwargs):
        label = request.GET.get('label', None)
        types = request.GET.get('type', [])
        if type(types) != list:
            types = [ types ]

        types = set(types)

        troves = repquery.searchTroves(cu, roleIds, label = label,
                                       filterSet = types)

        return Response(xobj.toxml(troves, "Response"))

class ListLabels(RestController):

    def index(self, request, cu, roleIds, *args, **kwargs):
        l = repquery.listLabels(cu, roleIds)
        return Response(xobj.toxml(l, "Response"))

class Controller(RestController):

    urls = { 'search' : SearchTroves,
             'labels' : ListLabels }
