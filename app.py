import tornado.ioloop
import tornado.web
from tornado.httpclient import AsyncHTTPClient

from logic import validate_order, unique_id
from render import render_reject_xml, render_accept_xml

class TradeHandler(tornado.web.RequestHandler):
    def initialize(self):
        AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient')
        self.httpclient = AsyncHTTPClient()

    def post(self):
        order = validate_order(self)
        if isinstance(order, str):
            self.finish(render_reject_xml(order))
        else:
            self.finish(render_accept_xml(unique_id(order)))

application = tornado.web.Application([
    (r'/exchange/endpoint', TradeHandler)
])

if __name__ == '__main__':
    application.listen(3487)
    tornado.ioloop.IOLoop.instance().start()
