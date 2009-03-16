#!/usr/bin/python

import restlib.auth
from restlib.http import simplehttp
from conary.repository.netrepos import netserver
from conary.server import server
import sys

import root

class Callback:

    def __init__(self, cfgFile):
        cfg = server.ServerConfig()
        cfg.read(cfgFile)
        self.repos = netserver.NetworkRepositoryServer(cfg, 'BASEURL')

    def processMethod(self, request, method, args, kwargs):
        cu = self.repos.db.cursor()
        kwargs['roleIds'] = self.repos.auth.getAuthRoles(
                                    cu, request.auth + (None, None))
        kwargs['cu'] = cu

        if not kwargs['roleIds']:
            return response.Response(status=403)

if __name__ == '__main__':
    print "Running on port 9000"
    simplehttp.serve(9000, root.Controller(None, '/'),
                     callbacks = [ restlib.auth.BasicAuthCallback(),
                                   Callback(sys.argv[1]) ])
