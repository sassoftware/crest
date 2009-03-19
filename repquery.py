import datamodel
from conary import files, trove, versions
from conary.deps import deps
from conary.lib.sha1helper import sha1ToString, md5ToString, sha1FromString

def searchTroves(cu, roleIds, label = None, filterSet = None, mkUrl = None,
                 latest = True):
    if latest:
        cu.execute("""
            SELECT item, version, flavor FROM
                (SELECT DISTINCT itemId, versionId, flavorId FROM Labels
                    JOIN LabelMap USING (labelId)
                    JOIN LatestCache USING (itemId, branchId)
                    WHERE label=? AND
                          LatestCache.latestType = 1 AND
                          LatestCache.userGroupId in (%s))
                AS idTable JOIN
                Items USING (itemId) JOIN
                Versions ON (idTable.versionId = Versions.versionId) JOIN
                Flavors ON (idTable.flavorId = Flavors.flavorId)
        """ % ",".join( str(x) for x in roleIds), label)
    else:
        cu.execute("""
            SELECT item, version, flavor FROM
                (SELECT DISTINCT itemId, versionId, flavorId FROM Labels
                    JOIN LabelMap USING (labelId)
                    JOIN Nodes USING (itemid, branchid)
                    JOIN Instances USING (itemid, versionid)
                    JOIN usergroupinstancescache AS ugi USING (instanceid)
                    WHERE label=? AND
                          ugi.userGroupId in (%s)) 
                AS idTable JOIN
                Items USING (itemId) JOIN
                Versions ON (idTable.versionId = Versions.versionId) JOIN
                Flavors ON (idTable.flavorId = Flavors.flavorId)
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

    troveList = datamodel.TroveIdentList()
    for (name, version, flavor) in cu:
        if filters:
            for f in filters:
                if f and f(name): break
            if f is None:
                continue

        flavor = str(deps.ThawFlavor(flavor))

        troveList.trove.append(datamodel.TroveIdent(name = name,
                                                    version = version,
                                                    flavor = flavor,
                                                    mkUrl = mkUrl))

    return troveList

def listLabels(cu, roleIds):
    cu.execute("""
        SELECT branch FROM
            (SELECT DISTINCT branchId FROM LatestCache
             WHERE userGroupId IN (%s) AND latestType=1) AS AvailBranches
            JOIN Branches USING(branchId)
    """ % ",".join( str(x) for x in roleIds))

    labels = set( str(versions.VersionFromString(x[0]).label()) for x in cu )

    l = datamodel.LabelList()
    [ l.append(x) for x in labels ]

    return l

def getTrove(cu, roleIds, name, version, flavor, mkUrl = None,
             thisHost = None):
    cu.execute("""
        SELECT Instances.instanceId FROM Instances
            JOIN Items USING (itemId)
            JOIN Versions ON (Instances.versionId = Versions.versionId)
            JOIN Flavors ON (Instances.flavorId = Flavors.flavorId)
            JOIN UserGroupInstancesCache AS ugi
                ON (instances.instanceId = ugi.instanceId AND
                    ugi.userGroupId in (%s))
        WHERE
            item = ? AND version = ? AND flavor = ?
    """ % ",".join( str(x) for x in roleIds), name, version,
        deps.parseFlavor(flavor).freeze())

    l = [ x[0] for x in cu ]
    if not l:
        return None

    instanceId = l[0]

    t = datamodel.SingleTrove(name = name, version = version, flavor = flavor,
                              mkUrl = mkUrl)

    cu.execute("""
        SELECT dirName, basename, version, pathId, fileId FROM TroveFiles
            JOIN Versions USING (versionId)
            JOIN FileStreams ON (TroveFiles.streamId = FileStreams.streamId)
            JOIN FilePaths ON (TroveFiles.filePathId = FilePaths.filePathId)
            JOIN DirNames ON (FilePaths.dirNameId = DirNames.dirNameId)
            JOIN Basenames ON (FilePaths.baseNameId = Basenames.baseNameId)
            WHERE TroveFiles.instanceId = ?
    """, instanceId)

    for (dirName, baseName, fileVersion, pathId, fileId) in cu:
        fileObj = datamodel.FileInTrove(
                        path = dirName + '/' + baseName,
                        version = fileVersion,
                        pathId = md5ToString(cu.frombinary(pathId)),
                        fileId = sha1ToString(cu.frombinary(fileId)),
                        mkUrl = mkUrl, thisHost = thisHost)
        t.addFile(fileObj)

    cu.execute("""
        SELECT item, version, flavor FROM TroveTroves
            JOIN Instances ON (Instances.instanceId = TroveTroves.includedId)
            JOIN Items USING (itemId)
            JOIN Versions ON (Versions.versionId = Instances.versionId)
            JOIN Flavors ON (Flavors.flavorId = Instances.flavorId)
            WHERE TroveTroves.instanceId = ?
    """, instanceId)

    for (subName, subVersion, subFlavor) in cu:
        t.addReferencedTrove(subName, subVersion, subFlavor, mkUrl = mkUrl)

    return datamodel.TroveList(trove = [ t ])

def _getFileStream(cu, roleIds, fileId):
    cu.execute("""
        SELECT FileStreams.stream
        FROM FileStreams
        JOIN TroveFiles USING (streamId)
        JOIN UserGroupInstancesCache ON
            TroveFiles.instanceId = UserGroupInstancesCache.instanceId
        WHERE FileStreams.stream IS NOT NULL
          AND FileStreams.fileId = ?
          AND UserGroupInstancesCache.userGroupId IN (%(roleids)s)
          LIMIT 1
        """ % { 'roleids' : ", ".join("%d" % x for x in roleIds) },
        cu.binary(sha1FromString(fileId)))

    l = list(cu)
    if not l:
        raise NotImplementedError

    return cu.frombinary(l[0][0])

def getFileInfo(cu, roleIds, fileId, mkUrl = None):
    stream = _getFileStream(cu, roleIds, fileId)
    f = files.ThawFile(stream, None)

    if f.lsTag == '-':
        fx = datamodel.RegularFile(owner = f.inode.owner(),
                                   group = f.inode.group(),
                                   mtime = f.inode.mtime(),
                                   perms = f.inode.perms(),
                                   size = int(f.contents.size()),
                                   sha1 = sha1ToString(f.contents.sha1()),
                                   fileId = fileId,
                                   mkUrl = mkUrl)
    elif f.lsTag == 'l':
        fx = datamodel.SymlinkFile(owner = f.inode.owner(),
                                   group = f.inode.group(),
                                   mtime = f.inode.mtime(),
                                   perms = f.inode.perms(),
                                   target = f.target())
    else:
        assert(0)

    l = datamodel.FileList()
    l.append(fx)

    return l

def getFileSha1(cu, roleIds, fileId):
    stream = _getFileStream(cu, roleIds, fileId)
    if not files.frozenFileHasContents(stream):
        return None

    sha1 = files.frozenFileContentInfo(stream).sha1()
    return sha1ToString(sha1)
