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

from mod_python import apache

from restlib.http import modpython as restmodpython
import root, server

handlers = {}

class SingleHandler:

    def handle(self, req):
        return self.h.handle(req, req.unparsed_uri[self.prefixLen:])

    def __init__(self, cfg, prefix):
        self.prefixLen = len(prefix)
        self.prefix = prefix
        self.h = restmodpython.ModPythonHttpHandler(
                                root.Controller(None, self.prefix))
        self.h.addCallback(server.AuthCallback())
        self.h.addCallback(server.ReposCallback(cfg))

def handler(req):
    path = req.filename[:-5]
    handler = handlers.get(path, None)
    if not handler:
        handler = SingleHandler(path, req.get_options()[path])
        handlers[path] = handler

    return handler.handle(req)
