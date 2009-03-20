#!/usr/bin/python
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

import restlib.auth
from restlib.http import simplehttp
from conary.repository.netrepos import netserver
from conary.server import server
import sys

import root

class ReposCallback:

    def __init__(self, cfgFile):
        cfg = server.ServerConfig()
        cfg.read(cfgFile)
        self.repos = netserver.NetworkRepositoryServer(cfg, 'BASEURL')

    def processMethod(self, request, method, args, kwargs):
        cu = self.repos.db.cursor()
        kwargs['repos'] = self.repos
        kwargs['roleIds'] = self.repos.auth.getAuthRoles(
                                    cu, request.auth + (None, None))
        kwargs['cu'] = cu

        if not kwargs['roleIds']:
            return response.Response(status=403)

class AuthCallback(restlib.auth.BasicAuthCallback):

    def getAuth(self, request):
        auth = restlib.auth.BasicAuthCallback.getAuth(self, request)
        if auth is None:
            auth = ('anonymous', 'anonymous')

        return auth

if __name__ == '__main__':
    print "Running on port 9000"
    simplehttp.serve(9000, root.Controller(None, '/'),
                     callbacks = [ AuthCallback(),
                                   ReposCallback(sys.argv[1]) ])
