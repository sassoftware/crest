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
from restlib import response
from restlib.http import simplehttp
from restlib.http import modpython as restmodpython
from conary.web import webauth
import sys

import root

class ReposCallback:

    def __init__(self, repos):
        self.repos = repos

    def processMethod(self, request, method, args, kwargs):
        cu = self.repos.db.cursor()

        entitlementList = webauth.parseEntitlement(
                            request.headers.get('X-Conary-Entitlement', ''))
        if getattr(request, 'auth', None) is None:
            request.auth = ('anonymous', 'anonymous')
        authToken = ( request.auth[0], request.auth[1], entitlementList )

        kwargs['repos'] = self.repos
        kwargs['roleIds'] = self.repos.auth.getAuthRoles(cu, authToken)
        kwargs['cu'] = cu

        if not kwargs['roleIds']:
            return response.Response(status=403)
        request.repos = self.repos
        request.roleIds = kwargs['roleIds']
        # unnatural act
        request.makeUrl = lambda *x, **kw: (self.makeUrl(request, *x, **kw))

    def processResponse(self, request, res):
        if self.repos.db.inTransaction(default=True):
            # Commit if someone left a transaction open (or the
            # DB doesn't have a way to tell)
            self.repos.db.commit()

    def processException(self, request, excClass, exception, tb):
        if self.repos.db.inTransaction(default=True):
            # Commit if someone left a transaction open (or the
            # DB doesn't have a way to tell)
            self.repos.db.rollback()

    def makeUrl(self, request, *args, **kwargs):
        if request.repos is not None and 'host' in kwargs:
            if kwargs['host'] not in request.repos.serverNameList:
                return 'http://%s/%s' % (kwargs['host'], '/'.join(args))
        return request.url(*args)

class AuthCallback(restlib.auth.BasicAuthCallback):

    def getAuth(self, request):
        auth = restlib.auth.BasicAuthCallback.getAuth(self, request)
        if auth is None:
            auth = ('anonymous', 'anonymous')

        return auth

class StandaloneHandler:

    handlerClass = simplehttp.SimpleHttpHandler

    def handle(self, req, path):
        return self.h.handle(req, path[self.prefixLen:])

    def __init__(self, rootUri, repos):
        self.prefix = rootUri
        self.prefixLen = len(self.prefix)
        self.h = self.handlerClass(root.Controller(None, self.prefix))
        self.h.addCallback(AuthCallback())
        self.h.addCallback(ReposCallback(repos))

class ApacheHandler(StandaloneHandler):

    handlerClass = restmodpython.ModPythonHttpHandler
