# CREST - Conary REST API -- Archived Repository
**Notice: This repository is part of a Conary/rpath project at SAS that is no longer supported or maintained. Hence, the repository is being archived and will live in a read-only state moving forward. Issues, pull requests, and changes will no longer be accepted.**

Overview
--------

This API appears as /api/ under the conary repository.

### /
Returns a list of all of the labels which contain troves the user
has access to. As well as a <trovelist> with an id for seeing all
of the troves the user may access.

### /trove
Returns name, version, and flavor for all of the troves the user
has access to. Results can be limited by using one or more parameters.
The parameters are logically ANDed together.

    label=<conary label>
    name=<regex>
    latest=<int>
        If latest is 0, all results are returned, otherwise only the
        more recent results for a given label are returned. If this
        parameter is ommitted, only the latest results are returned.
    type=<type>
        Type is one of:
            group
            package
            component
            fileset
            collection
            source
            binarycomponent
    first=<int>
        The first item returned from the matches is number <int> (counting
        from zero). The total number of matches is always available
        via the 'total' attribute of the trovelist element.
    count=<int>
        The maximum number of matches to return.

### /trove/&lt;name&gt;=&lt;version&gt;[&lt;flavor&gt;]
Returns information on the trove specified.

### /file/&lt;fileId&gt;/info
Returns metadata associated with the file specified. The fileId must
be a sha1 string.

### /file/&lt;fileId&gt;/content
Returns the gzipped contents of the file specified.

### /node
Returns nodes, which are name/version pairs. The search can be restricted
using label and type, which are the same as the search parameters for
/trove.

### /troves/&lt;name&gt;=&lt;version&gt;
Returns a list of troves which match the name/version given. Note that
the objects returned are full troves.
