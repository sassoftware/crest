from restlib.controller import RestController
from restlib.response import Response

class Troves(RestController):

    def index(self, request, cu, *args, **kwargs):
        cu.execute("""
            SELECT item FROM Items ORDER BY item
        """)
        return Response("\n".join(x[0] for x in cu))

class Controller(RestController):

    urls = { 'troves' : Troves }
