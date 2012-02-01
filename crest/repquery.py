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

import itertools, os, re

import datamodel
from conary import files, trove, versions
from conary.deps import deps
from conary.lib.sha1helper import sha1ToString, md5ToString, sha1FromString
from conary.server import schema

def typeFilter(l, filterSet):
    if not filterSet:
        return l

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

    filters.append(None)

    filteredL = []
    for item in l:
        if filters:
            for f in filters:
                if f and f(item[0]): break
            if f is None:
                continue

        filteredL.append(item)

    return filteredL

def searchNodes(cu, roleIds, label = None, mkUrl = None, filterSet = None,
                db = None, name = None, latest = 1):
    args = []
    d = { 'labelCheck' : '', 'itemCheck' : '' }
    d['roleIds'] = ",".join( str(x) for x in roleIds)
    d['SOURCENAME'] = trove._TROVEINFO_TAG_SOURCENAME
    d['METADATA'] = trove._TROVEINFO_TAG_METADATA

    if label:
        d['labelCheck'] = "label = ? AND"
        args.append(label)

    if name:
        d['itemCheck'] = "item = ? AND"
        args.append(name)

    if latest:
        cu.execute("""
            SELECT idTable.item, version, ts, finalTs, SourceNameTroveInfo.data,
                   MetadataTroveInfo.data FROM
                (SELECT DISTINCT Items.item AS item,
                                 Nodes.versionId AS versionId,
                                 Nodes.timeStamps AS ts,
                                 Nodes.finalTimeStamp as finalTs,
                                 MIN(Instances.instanceId) AS instanceId
                    FROM Labels
                    JOIN LabelMap USING (labelId)
                    JOIN LatestCache USING (itemId, branchId)
                    JOIN Nodes USING (itemId, versionId)
                    JOIN Instances USING (itemId, versionId)
                    JOIN Items USING (itemId)
                    WHERE %(labelCheck)s
                          %(itemCheck)s
                          LatestCache.latestType = 1 AND
                          LatestCache.userGroupId in (%(roleIds)s)
                    GROUP BY
                          Items.item, Nodes.versionId, Nodes.timeStamps,
                          Nodes.finalTimestamp)
                AS idTable
                JOIN Versions ON (idTable.versionId = Versions.versionId)
                LEFT OUTER JOIN TroveInfo AS SourceNameTroveInfo ON
                    idTable.instanceId = SourceNameTroveInfo.instanceId AND
                    SourceNameTroveInfo.infoType = %(SOURCENAME)d
                LEFT OUTER JOIN TroveInfo AS MetadataTroveInfo ON
                    idTable.instanceId = MetadataTroveInfo.instanceId AND
                    MetadataTroveInfo.infoType = %(METADATA)d
        """ % d, args)
    else:
        cu.execute("""
            SELECT idTable.item, version, ts, finalTs, SourceNameTroveInfo.data,
                   MetadataTroveInfo.data FROM
                (SELECT DISTINCT Items.item AS item,
                                 Nodes.versionId AS versionId,
                                 Nodes.timeStamps AS ts,
                                 Nodes.finalTimeStamp as finalTs,
                                 MIN(Instances.instanceId) AS instanceId
                    FROM Labels
                    JOIN LabelMap USING (labelId)
                    JOIN Nodes USING (itemId, branchId)
                    JOIN Instances USING (itemId, versionId)
                    JOIN Items USING (itemId)
                    JOIN usergroupinstancescache AS ugi ON
                        Instances.instanceId = ugi.instanceId
                    WHERE %(labelCheck)s
                          %(itemCheck)s
                          ugi.userGroupId in (%(roleIds)s)
                    GROUP BY
                          Items.item, Nodes.versionId, Nodes.timeStamps,
                          Nodes.finalTimestamp)
                AS idTable
                JOIN Versions ON (idTable.versionId = Versions.versionId)
                LEFT OUTER JOIN TroveInfo AS SourceNameTroveInfo ON
                    idTable.instanceId = SourceNameTroveInfo.instanceId AND
                    SourceNameTroveInfo.infoType = %(SOURCENAME)d
                LEFT OUTER JOIN TroveInfo AS MetadataTroveInfo ON
                    idTable.instanceId = MetadataTroveInfo.instanceId AND
                    MetadataTroveInfo.infoType = %(METADATA)d
        """ % d, args)

    l = list(cu)
    filteredL = typeFilter(l, filterSet)

    # sort based on (name, version, desc(finalTimestamp))
    def sortorder(x, y):
        c = cmp(x[0], y[0])
        if c:
            return c

        return -(cmp(x[3], y[3]))

    filteredL.sort(sortorder)

    if latest:
        # keep the latest
        newL = []
        last = None
        for item in filteredL:
            if last and last[0] == item[0]:
                continue

            newL.append(item)
            last = item

        filteredL = newL

    nodeList = datamodel.NamedNodeList(total = len(filteredL), start = 0)

    addList = []
    for (name, version, ts, finalTs, sourceName, metadata) in filteredL:
	if sourceName is None and trove.troveIsSourceComponent(name):
            sourceName = name
        addList.append((sourceName,
                str(versions.VersionFromString(version).getSourceVersion())))

    schema.resetTable(cu, 'tmpNVF')

    # This is painful, but it converts the source name from a blob to
    # a string
    db.bulkload("tmpNVF", [ (x[0],) + x[1] for x in enumerate(addList) ],
                ["idx", "name", "version"],
                start_transaction = False)
    cu.execute("""
        SELECT ChangeLogs.name, ChangeLogs.message, tmpNVF.name
            FROM tmpNVF JOIN Items AS SourceItems ON
                tmpNVF.name = SourceItems.item
            LEFT OUTER JOIN Versions AS SourceVersion ON
                tmpNVF.version = SourceVersion.version
            LEFT OUTER JOIN Nodes ON
                SourceItems.itemId = Nodes.itemId AND
                SourceVersion.versionId = Nodes.versionId
            LEFT OUTER JOIN ChangeLogs USING (nodeId)
            ORDER BY tmpNVF.idx
    """)

    for ( (name, version, ts, finalTs, sourceName, metadata),
          (clName, clMessage, troveName) ) in itertools.izip(filteredL, cu):
        frzVer = versions.strToFrozen(version,
                                      [ x for x in ts.split(":") ])
        ver = versions.ThawVersion(frzVer)

        shortdesc = None

        if metadata:
            md = trove.Metadata(metadata)
            shortdesc = md.get()['shortDesc']

        if clName:
            cl = datamodel.ChangeLog(name = clName, message = clMessage)
        else:
            cl = None

        nodeList.append(name = name, version = ver, mkUrl = mkUrl,
                        changeLog = cl, shortdesc = shortdesc)

    return nodeList

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

    l = list(cu)
    filteredL = typeFilter(l, filterSet)

    if regex:
        filteredL = [ x for x in filteredL if regex.match(x[0]) ]

    if limit is None:
        limit = len(filteredL) - start

    troveList = datamodel.NamedTroveIdentList(total = len(filteredL),
                                              start = start)

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
             thisHost = None, displayFlavor = None, excludeCapsules = False):

    def buildTupleList(tuples, name, mkUrl = mkUrl):
        l = getattr(datamodel.SingleTrove, name)()
        for troveInfo in sorted(tuples.iter()):
            l.append(name = troveInfo.name(), version = troveInfo.version(),
                     flavor = troveInfo.flavor(), mkUrl = mkUrl)

        return l

    def fileQuery(gfcu, filesInstanceId, dirName = None):
        # XXX restricing by dirName seems and obvious thing to do here,
        # but it actually slows things down??
        #
        # the distinct here is unfortunate, but conary repositories had
        # a bug for about a year which caused it to store duplicate paths
        # if a path was committed for the first time duplicate times in
        # a single commit job
        gfcu.execute("""
            SELECT DISTINCT dirName, basename, version, pathId, fileId
                FROM TroveFiles
                JOIN Versions USING (versionId)
                JOIN FileStreams ON (TroveFiles.streamId = FileStreams.streamId)
                JOIN FilePaths ON (TroveFiles.filePathId = FilePaths.filePathId)
                JOIN DirNames ON
                    FilePaths.dirNameId = DirNames.dirNameId
                JOIN Basenames ON (FilePaths.baseNameId = Basenames.baseNameId)
                WHERE TroveFiles.instanceId = ? ORDER BY dirName, basename
        """, filesInstanceId)

    cu.execute("""
        SELECT Instances.instanceId, Nodes.timeStamps FROM Instances
            JOIN Nodes USING (itemId, versionId)
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

    l = [ (x[0], x[1]) for x in cu ]
    if not l:
        return None

    instanceId, timeStamps = l[0]
    frzVer = versions.strToFrozen(version, timeStamps.split(":"))
    verobj = versions.ThawVersion(frzVer)

    tupleLists = [ ( trove._TROVEINFO_TAG_BUILDDEPS, 'builddeps' ),
                   ( trove._TROVEINFO_TAG_POLICY_PROV, 'policyprovider' ),
                   ( trove._TROVEINFO_TAG_LOADEDTROVES, 'loadedtroves' ),
                   ( trove._TROVEINFO_TAG_COPIED_FROM, 'copiedfrom' ),
                   ( trove._TROVEINFO_TAG_DERIVEDFROM, 'derivedfrom' ) ]

    cu.execute("""
    SELECT infoType, data FROM TroveInfo WHERE instanceId = ? AND
        infoType IN (%s)
                """ % ",".join(str(x) for x in
                        [ trove._TROVEINFO_TAG_SOURCENAME,
                          trove._TROVEINFO_TAG_CLONEDFROM,
                          trove._TROVEINFO_TAG_CLONEDFROMLIST,
                          trove._TROVEINFO_TAG_BUILDTIME,
                          trove._TROVEINFO_TAG_SIZE,
                          trove._TROVEINFO_TAG_METADATA,
                          trove._TROVEINFO_TAG_CAPSULE,
                        ] + [ x[0] for x in tupleLists ]
                ), instanceId)

    troveInfo = dict(
            (x[0], trove.TroveInfo.streamDict[x[0]][1](x[1])) for x in cu )

    kwargs = { 'name' : name,
               'version' : verobj,
               'flavor' : flavor }

    if displayFlavor is not None:
        kwargs['displayflavor'] = displayFlavor

    if trove._TROVEINFO_TAG_BUILDTIME in troveInfo:
        kwargs['buildtime'] = int(troveInfo[trove._TROVEINFO_TAG_BUILDTIME]())

    if trove._TROVEINFO_TAG_SOURCENAME in troveInfo:
        kwargs['source'] = (troveInfo[trove._TROVEINFO_TAG_SOURCENAME](),
            verobj.getSourceVersion(), '')

    if trove._TROVEINFO_TAG_SIZE in troveInfo:
        kwargs['size'] = troveInfo[trove._TROVEINFO_TAG_SIZE]()

    if trove._TROVEINFO_TAG_METADATA in troveInfo:
        md = troveInfo[trove._TROVEINFO_TAG_METADATA].get()
        kwargs['shortdesc'] = md['shortDesc']
        kwargs['longdesc'] = md['longDesc']

        if md['licenses']:
            kwargs['license'] = [ x for x in md['licenses' ]]
        if md['crypto']:
            kwargs['crypto'] = [ x for x in md['crypto'] ]

    for (tag, tagName) in tupleLists:
        if tag in troveInfo:
            kwargs[tagName] = buildTupleList(troveInfo[tag], tagName,
                                             mkUrl = mkUrl)

    t = datamodel.SingleTrove(mkUrl = mkUrl, thisHost = thisHost, **kwargs)

    if trove._TROVEINFO_TAG_CLONEDFROMLIST in troveInfo:
        clonedFromList = troveInfo[trove._TROVEINFO_TAG_CLONEDFROMLIST]
    elif (trove._TROVEINFO_TAG_CLONEDFROM in troveInfo):
        clonedFromList = [ troveInfo[trove._TROVEINFO_TAG_CLONEDFROM]() ]
    else:
        clonedFromList = []

    for ver in clonedFromList:
        t.addClonedFrom(name, ver, flavor, mkUrl = mkUrl)

    hasCapsule = False
    if trove._TROVEINFO_TAG_CAPSULE in troveInfo:
        if troveInfo[trove._TROVEINFO_TAG_CAPSULE].type():
            hasCapsule = True

    fileQuery(cu, instanceId)

    for (dirName, baseName, fileVersion, pathId, fileId) in cu:
        if pathId == trove.CAPSULE_PATHID:
            isCapsule = 1
            contentAvailable = not excludeCapsules
        else:
            isCapsule = None
            contentAvailable = not hasCapsule

        fileObj = datamodel.FileReference(
                        path = os.path.join(dirName, baseName),
                        version = fileVersion,
                        pathId = md5ToString(cu.frombinary(pathId)),
                        fileId = sha1ToString(cu.frombinary(fileId)),
                        isCapsule = isCapsule,
                        contentAvailable = contentAvailable,
                        mkUrl = mkUrl, thisHost = thisHost)
        t.addFile(fileObj)

    cu.execute("""
        SELECT item, version, flavor, TroveTroves.includedId,
               Nodes.finalTimeStamp
          FROM TroveTroves
            JOIN Instances ON (Instances.instanceId = TroveTroves.includedId)
            JOIN Nodes USING (itemId, versionId)
            JOIN Items USING (itemId)
            JOIN Versions ON (Versions.versionId = Instances.versionId)
            JOIN Flavors ON (Flavors.flavorId = Instances.flavorId)
            WHERE
                TroveTroves.instanceId = ? AND
                (TroveTroves.flags & %d) = 0
            ORDER BY item, version, flavor
    """ % schema.TROVE_TROVES_WEAKREF, instanceId)

    for (subName, subVersion, subFlavor, refInstanceId, subTS) in list(cu):
        subFlavor = str(deps.ThawFlavor(subFlavor))
        subV = versions.VersionFromString(subVersion, timeStamps = [ subTS ])
        t.addReferencedTrove(subName, subV, subFlavor, mkUrl = mkUrl)

        # It would be far better to use file tags to identify these build
        # logs, but it's significantly slower as well because they're in
        # the file objects rather than the trove (and those file objects
        # could be stored on a different repository)
        if not subName.endswith(':debuginfo'):
            continue

        fileQuery(cu, refInstanceId, dirName = '/usr/src/debug/buildlogs')
        logHost = \
            versions.VersionFromString(subVersion).trailingLabel().getHost()
        for (dirName, baseName, fileVersion, pathId, fileId) in cu:
            if (dirName) != '/usr/src/debug/buildlogs':
                continue

            if baseName.endswith('-log.bz2'):
                t.setBuildLog(logHost, sha1ToString(fileId))
            elif baseName.endswith('-xml.bz2'):
                t.setXMLBuildLog(logHost, sha1ToString(fileId))

    return t

def getTroves(cu, roleIds, name, version, mkUrl = None,
              thisHost = None):
    cu.execute("""
        SELECT DISTINCT flavor FROM Instances
            JOIN Items USING (itemId)
            JOIN Versions ON (Instances.versionId = Versions.versionId)
            JOIN Flavors ON (Instances.flavorId = Flavors.flavorId)
            JOIN UserGroupInstancesCache AS ugi
                ON (instances.instanceId = ugi.instanceId AND
                    ugi.userGroupId in (%s))
        WHERE
            item = ? AND version = ?
    """ % ",".join( str(x) for x in roleIds), name, version)

    flavors = [ deps.ThawFlavor(x[0]) for x in cu  ]
    commonFlavor = flavors[0]
    for flavor in flavors[1:]:
        commonFlavor = commonFlavor.intersection(flavor)


    troves = datamodel.TroveList()
    for flavor in flavors:
        troves.append(getTrove(cu, roleIds, name, version, str(flavor),
                               mkUrl = mkUrl, thisHost = thisHost,
                               displayFlavor =
                                    str(flavor.difference(commonFlavor))))

    return troves

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

    bin = cu.frombinary(l[0][0])
    if bin is not None:
        return files.ThawFile(bin, None)
    return None


def getFileInfo(cu, roleIds, fileId, mkUrl = None, path = None,
                noContent = False):
    f = _getFileStream(cu, roleIds, fileId)
    if f is None:
        return None

    args = { 'owner' : f.inode.owner(), 'group' : f.inode.group(),
             'mtime' : f.inode.mtime(), 'perms' : f.inode.perms(),
             'fileId' : fileId, 'mkUrl' : mkUrl }

    if f.lsTag == '-':
        fx = datamodel.RegularFile(size = int(f.contents.size()),
                                   sha1 = sha1ToString(f.contents.sha1()),
                                   path = path, withContentLink = not noContent,
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
    fStream = _getFileStream(cu, roleIds, fileId)
    if not fStream or not hasattr(fStream, 'contents'):
        # Missing or no contents (not a regular file).
        return None, None

    return sha1ToString(fStream.contents.sha1()), fStream.flags.isConfig()
