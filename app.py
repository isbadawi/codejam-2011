import tornado.ioloop
import tornado.web
from tornado.httpclient import AsyncHTTPClient

from logic import validate_order, unique_id, OrderBook
from render import render_reject_xml, render_accept_xml

class TradeHandler(tornado.web.RequestHandler):
    def initialize(self):
        AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient')
        self.httpclient = AsyncHTTPClient()
        self.order_book = OrderBook()

    def set_default_headers(self):
        self.set_header('Content-Type', 'text/xml; charset=UTF-8')

    def post(self):
        order = validate_order(self)
        if isinstance(order, str):
            self.finish(render_reject_xml(order))
        else:
            refid = unique_id(order)
            order['OrderRefID'] = refid
            self.order_book.add_order_async(order)
            self.finish(render_accept_xml(refid))

class GUIHandler(tornado.web.RequestHandler):
    def get(self):
        pass

    def post(self):
        pass

application = tornado.web.Application([
    (r'/exchange/endpoint', TradeHandler),
    (r'/exchange/home', GUIHandler)
])

if __name__ == '__main__':
    application.listen(3487)
    tornado.ioloop.IOLoop.instance().start()
