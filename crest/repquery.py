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

import re

import datamodel
from conary import files, trove, versions
from conary.deps import deps
from conary.lib.sha1helper import sha1ToString, md5ToString, sha1FromString
from conary.server import schema

def searchTroves(cu, roleIds, label = None, filterSet = None, mkUrl = None,
                 latest = True, start = 0, limit = None, name = None):
    d = { 'labelCheck' : '', 'nameCheck' : '' }
    args = []
    regex = None
    if label:
        d['labelCheck'] = "label = ? AND"
        args.append(label)

    if name:
        if set('?.*[]\\()+') & set(name):
            # if only .* appears, replace them with '%' and use LIKE. this
            # code currently fails with \.* in the regex, but neither .
            # nor \* are valid trove names anyway
            likeName = name
            while '.*' in likeName:
                likeName = likeName.replace('.*', '%')

            if set('?.*[]\\()+') & set(name):
                regex = re.compile(name)
            else:
                d['nameCheck'] = "WHERE item LIKE ?"
                args.append(likeName)
        else:
            d['nameCheck' ] = "WHERE item = ?"
            args.append(name)

    d['roleIds'] = ",".join( str(x) for x in roleIds)

    if latest:
        cu.execute("""
            SELECT item, version, flavor, ts FROM
                (SELECT DISTINCT Nodes.itemId AS itemId,
                                 Nodes.versionId AS versionId, flavorId,
                                 Nodes.timeStamps AS ts FROM Labels
                    JOIN LabelMap USING (labelId)
                    JOIN LatestCache USING (itemId, branchId)
                    JOIN Nodes USING (itemId, versionId)
                    WHERE %(labelCheck)s
                          LatestCache.latestType = 1 AND
                          LatestCache.userGroupId in (%(roleIds)s))
                AS idTable JOIN
                Items USING (itemId) JOIN
                Versions ON (idTable.versionId = Versions.versionId) JOIN
                Flavors ON (idTable.flavorId = Flavors.flavorId)
                %(nameCheck)s
                ORDER BY item, version, flavor
        """ % d, *args)
    else:
        cu.execute("""
            SELECT item, version, flavor, ts FROM
                (SELECT DISTINCT Instances.itemId AS itemId,
                                 Instances.versionId AS versionId,
                                 Instances.flavorId AS flavorId,
                                 Nodes.timeStamps AS ts
                                 FROM Labels
                    JOIN LabelMap USING (labelId)
                    JOIN Nodes USING (itemId, branchid)
                    JOIN Instances USING (itemid, versionid)
                    JOIN usergroupinstancescache AS ugi USING (instanceid)
                    WHERE %(labelCheck)s
                          ugi.userGroupId in (%(roleIds)s))
                AS idTable JOIN
                Items USING (itemId) JOIN
                Versions ON (idTable.versionId = Versions.versionId) JOIN
                Flavors ON (idTable.flavorId = Flavors.flavorId)
                %(nameCheck)s
                ORDER BY item, version, flavor
        """ % d, *args)

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

    l = list(cu)

    if regex:
        l = [ x for x in l if regex.match(x[0]) ]

    filteredL = []
    for item in l:
        if filters:
            for f in filters:
                if f and f(item[0]): break
            if f is None:
                continue

        filteredL.append(item)

    if limit is None:
        limit = len(filteredL) - start
    troveList = datamodel.TroveIdentList(total = len(filteredL), start = start)

    for (name, version, flavor, ts) in filteredL[start:start + limit]:
        flavor = str(deps.ThawFlavor(flavor))
        frzVer = versions.strToFrozen(version,
                                      [ x for x in ts.split(":") ])
        ver = versions.ThawVersion(frzVer)

        troveList.append(name = name, version = ver, flavor = flavor,
                         mkUrl = mkUrl)

    return troveList

def getRepository(cu, roleIds, mkUrl = None):
    cu.execute("""
        SELECT branch FROM
            (SELECT DISTINCT branchId FROM LatestCache
             WHERE userGroupId IN (%s) AND latestType=1) AS AvailBranches
            JOIN Branches USING(branchId)
    """ % ",".join( str(x) for x in roleIds))

    labels = set( str(versions.VersionFromString(x[0]).label()) for x in cu )

    trovelist = datamodel.TroveIdentList(id = mkUrl('trove'))
    repository = datamodel.Repository(trovelist = trovelist)

    [ repository.appendLabel(x, mkUrl = mkUrl) for x in sorted(labels) ]

    return repository

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

    cu.execute("""
    SELECT infoType, data FROM TroveInfo WHERE instanceId = ? AND
        infoType IN (%s)
    """ % ",".join(str(x) for x in (trove._TROVEINFO_TAG_SOURCENAME,
                                    trove._TROVEINFO_TAG_CLONEDFROM,
                                    trove._TROVEINFO_TAG_CLONEDFROMLIST,
                                    trove._TROVEINFO_TAG_BUILDTIME,
                                    trove._TROVEINFO_TAG_SIZE,
                                   )), instanceId)

    troveInfo = dict(
            (x[0], trove.TroveInfo.streamDict[x[0]][1](x[1])) for x in cu )

    kwargs = { 'name' : name, 'version' : versions.VersionFromString(version),
               'flavor' : flavor }

    if trove._TROVEINFO_TAG_BUILDTIME in troveInfo:
        kwargs['buildtime'] = int(troveInfo[trove._TROVEINFO_TAG_BUILDTIME]())

    if trove._TROVEINFO_TAG_SOURCENAME in troveInfo:
        kwargs['source'] = datamodel.BaseTroveInfo(
            name = troveInfo[trove._TROVEINFO_TAG_SOURCENAME](),
            version = versions.VersionFromString(version).getSourceVersion(),
            flavor = '', mkUrl = mkUrl)

    if trove._TROVEINFO_TAG_SIZE in troveInfo:
        kwargs['size'] = troveInfo[trove._TROVEINFO_TAG_SIZE]()

    t = datamodel.SingleTrove(mkUrl = mkUrl, **kwargs)

    if trove._TROVEINFO_TAG_CLONEDFROMLIST in troveInfo:
        clonedFromList = troveInfo[trove._TROVEINFO_TAG_CLONEDFROMLIST]
    elif (trove._TROVEINFO_TAG_CLONEDFROM in troveInfo):
        clonedFromList = [ troveInfo[trove._TROVEINFO_TAG_CLONEDFROM]() ]
    else:
        clonedFromList = []

    for ver in clonedFromList:
        t.addClonedFrom(name, ver, flavor, mkUrl = mkUrl)

    cu.execute("""
        SELECT dirName, basename, version, pathId, fileId FROM TroveFiles
            JOIN Versions USING (versionId)
            JOIN FileStreams ON (TroveFiles.streamId = FileStreams.streamId)
            JOIN FilePaths ON (TroveFiles.filePathId = FilePaths.filePathId)
            JOIN DirNames ON (FilePaths.dirNameId = DirNames.dirNameId)
            JOIN Basenames ON (FilePaths.baseNameId = Basenames.baseNameId)
            WHERE TroveFiles.instanceId = ? ORDER BY dirName, basename
    """, instanceId)

    for (dirName, baseName, fileVersion, pathId, fileId) in cu:
        fileObj = datamodel.FileReference(
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
            WHERE
                TroveTroves.instanceId = ? AND
                (TroveTroves.flags & %d) = 0
            ORDER BY item, version, flavor
    """ % schema.TROVE_TROVES_WEAKREF, instanceId)

    for (subName, subVersion, subFlavor) in cu:
        subFlavor = str(deps.ThawFlavor(subFlavor))
        t.addReferencedTrove(subName, versions.VersionFromString(subVersion),
                             subFlavor, mkUrl = mkUrl)

    return t

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
        return None

    return cu.frombinary(l[0][0])

def getFileInfo(cu, roleIds, fileId, mkUrl = None):
    stream = _getFileStream(cu, roleIds, fileId)
    if not stream:
        return None

    f = files.ThawFile(stream, None)

    args = { 'owner' : f.inode.owner(), 'group' : f.inode.group(),
             'mtime' : f.inode.mtime(), 'perms' : f.inode.perms(),
             'fileId' : fileId, 'mkUrl' : mkUrl }

    if f.lsTag == '-':
        fx = datamodel.RegularFile(size = int(f.contents.size()),
                                   sha1 = sha1ToString(f.contents.sha1()),
                                   **args)
    elif f.lsTag == 'l':
        fx = datamodel.SymlinkFile(target = f.target(), **args)
    elif f.lsTag == 'd':
        fx = datamodel.Directory(**args)
    elif f.lsTag == 'b':
        fx = datamodel.BlockDeviceFile(major = f.devt.major(),
                                       minor = f.devt.minor(), **args)
    elif f.lsTag == 'c':
        fx = datamodel.CharacterDeviceFile(major = f.devt.major(),
                                           minor = f.devt.minor(), **args)
    elif f.lsTag == 's':
        fx = datamodel.Socket(**args)
    elif f.lsTag == 'p':
        fx = datamodel.NamedPipe(**args)
    else:
        # This really shouldn't happen
        raise NotImplementedError

    return fx

def getFileSha1(cu, roleIds, fileId):
    stream = _getFileStream(cu, roleIds, fileId)
    if not files.frozenFileHasContents(stream):
        return None

    sha1 = files.frozenFileContentInfo(stream).sha1()
    return sha1ToString(sha1)
