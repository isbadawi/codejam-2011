import tornado.ioloop
import tornado.web
from tornado.httpclient import AsyncHTTPClient

from logic import validate_order, unique_id, OrderBook
from render import render_reject_xml, render_accept_xml

AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient')
order_book = OrderBook(AsyncHTTPClient())
class TradeHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header('Content-Type', 'text/xml; charset=UTF-8')

    def post(self):
        order = validate_order(self)
        if isinstance(order, str):
            self.finish(render_reject_xml(order))
        else:
            refid = unique_id(order['BS'])
            order['OrderRefID'] = refid
            order_book.add_order_async(order)
            self.finish(render_accept_xml(refid))

class GUIHandler(tornado.web.RequestHandler):
    def get(self):
        # display gui
        pass

class SnapshotHandler(tornado.web.RequestHandler):
    def get(self):
        self.finish(render_snapshot_html)

    def post(self):
        # post snapshot to silanis
        pass

application = tornado.web.Application([
    (r'/exchange/endpoint', TradeHandler),
    (r'/exchange/home', GUIHandler),
    (r'/exchange/snapshot', SnapshotHandler)
])

if __name__ == '__main__':
    application.listen(3487)
    tornado.ioloop.IOLoop.instance().start()
