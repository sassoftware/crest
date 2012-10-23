#
# Copyright (c) rPath, Inc.
#
# This program is distributed under the terms of the MIT License as found 
# in a file called LICENSE. If it is not present, the license
# is always available at http://www.opensource.org/licenses/mit-license.php.
#
# This program is distributed in the hope that it will be useful, but
# without any waranty; without even the implied warranty of merchantability
# or fitness for a particular purpose. See the MIT License for full details.
#

import restlib.auth
from restlib import response
from restlib.http import simplehttp
from conary.web import webauth

from crest import root


class ReposCallback:

    def __init__(self, repos):
        self.repos = repos

    def processMethod(self, request, method, args, kwargs):
        cu = self.repos.db.cursor()

        authToken = getattr(request, 'authToken', None)
        if not authToken:
            entitlementList = webauth.parseEntitlement(
                                request.headers.get('X-Conary-Entitlement', ''))
            if getattr(request, 'auth', None) is None:
                request.auth = ('anonymous', 'anonymous')
            authToken = ( request.auth[0], request.auth[1], entitlementList )

        kwargs['repos'] = self.repos
        kwargs['roleIds'] = self.repos.auth.getAuthRoles(cu, authToken)
        kwargs['cu'] = cu
        kwargs['excludeCapsules'] = self.repos.excludeCapsuleContents

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
        baseUrl = None
        if request.repos is not None and 'host' in kwargs:
            if kwargs['host'] not in request.repos.serverNameList:
                baseUrl = 'http://%s/conary/api' % kwargs['host']
        return request.url(baseUrl=baseUrl, *args)

class AuthCallback(restlib.auth.BasicAuthCallback):

    def getAuth(self, request):
        auth = restlib.auth.BasicAuthCallback.getAuth(self, request)
        if auth is None:
            auth = ('anonymous', 'anonymous')

        return auth

class StandaloneHandler:

    handlerClass = simplehttp.SimpleHttpHandler

    def handle(self, req, path):
        return self.h.handle(req, pathPrefix=self.prefix)

    def __init__(self, rootUri, repos):
        self.prefix = rootUri
        self.h = self.handlerClass(root.Controller(None, self.prefix))
        self.h.addCallback(AuthCallback())
        self.h.addCallback(ReposCallback(repos))

try:
    from restlib.http import modpython as restmodpython
    class ApacheHandler(StandaloneHandler):
        handlerClass = restmodpython.ModPythonHttpHandler
except ImportError:
    pass


try:
    from restlib.http import wsgi as rl_wsgi
    class WSGIHandler(StandaloneHandler):
        handlerClass = rl_wsgi.WSGIHandler
except ImportError:
    pass
