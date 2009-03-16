from restlib.controller import RestController
from restlib.response import Response
from xobj import xobj

import datamodel

from conary import trove

class SearchTroves(RestController):

    def index(self, request, cu, roleIds, *args, **kwargs):
        label = request.GET.get('label', None)
        cu.execute("""
            SELECT DISTINCT item, version, flavor
            FROM UserGroupInstancesCache AS ugi
                join Instances using (instanceId)
                join Nodes using (itemId, versionId)
                join LabelMap using (branchId)
                join Labels using (labelId)
                join Items on (instances.itemId = Items.itemId)
                join Versions on (instances.versionId = Versions.versionId)
                join Flavors on (instances.flavorId = Flavors.flavorId)
                where ugi.userGroupId in (%s) and
                    Labels.label = ?
        """ % ",".join( str(x) for x in roleIds), label)

        types = request.GET.get('type', [])
        if type(types) != list:
            types = [ types ]

        filters = []
        if 'group' in types:
            filters.append(trove.troveIsGroup)
        if 'package' in types:
            filters.append(trove.troveIsPackage)
        if 'component' in types:
            filters.append(trove.troveIsComponent)
        if 'fileset' in types:
            filters.append(trove.troveIsFileSet)
        if 'collection' in types:
            filters.append(trove.troveIsCollection)
        if 'source' in types:
            filters.append(trove.troveIsSourceComponent)
        if 'binarycomponent' in types:
            filters.append(lambda x: trove.troveIsComponent(x) and
                                     not trove.troveIsSourceComponent(x))

        if filters:
            filters.append(None)

        troveList = datamodel.TroveList()
        for (name, version, flavor) in cu:
            if filters:
                for f in filters:
                    if f and f(name): break
                if f is None:
                    continue

            troveList.trove.append(datamodel.TroveIdent(name = name,
                                                        version = version,
                                                        flavor = flavor))

        s = xobj.toxml(troveList, "Result")

        return Response(s)

class ListLabels(RestController):

    def index(self, request, cu, roleIds, *args, **kwargs):
        cu.execute("""
            SELECT distinct(label) FROM UserGroupInstancesCache AS ugi
                join Instances using (instanceId)
                join Nodes using (itemId, versionId)
                join LabelMap using (branchId)
                join Labels using (labelId)
                where ugi.userGroupId in (%s)
        """ % ",".join( str(x) for x in roleIds))

        l = datamodel.LabelList()
        [ l.append(x[0]) for x in cu ]

        return Response(xobj.toxml(l, "Response"))

class Controller(RestController):

    urls = { 'search' : SearchTroves,
             'labels' : ListLabels }
