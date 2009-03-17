import datamodel
from conary import trove
from conary.deps import deps

def searchTroves(cu, roleIds, label = None, filterSet = None):
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

    filters = []
    if 'group' in filterSet:
        filters.append(trove.troveIsGroup)
    if 'package' in filterSet:
        filters.append(trove.troveIsPackage)
    if 'component' in filterSet:
        filters.append(trove.troveIsComponent)
    if 'fileset' in filterSet:
        filters.append(trove.troveIsFileSet)
    if 'collection' in filterSet:
        filters.append(trove.troveIsCollection)
    if 'source' in filterSet:
        filters.append(trove.troveIsSourceComponent)
    if 'binarycomponent' in filterSet:
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

        flavor = str(deps.ThawFlavor(flavor))

        troveList.trove.append(datamodel.TroveIdent(name = name,
                                                    version = version,
                                                    flavor = flavor))

    return troveList

def listLabels(cu, roleIds):
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

    return l
