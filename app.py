import tornado.ioloop
import tornado.web
from tornado.httpclient import AsyncHTTPClient

from logic import validate_order, unique_id, OrderBook
from render import render_reject_xml, render_accept_xml, render_snapshot_html, render_home_page


SILANIS_URL = 'http://ec2-184-73-166-185.compute-1.amazonaws.com/aws/rest/services/codejam/processes'
AsyncHTTPClient.configure('tornado.curl_httpclient.CurlAsyncHTTPClient')
httpclient = AsyncHTTPClient()
order_book = OrderBook(httpclient)
class TradeHandler(tornado.web.RequestHandler):
    def set_default_headers(self):
        self.set_header('Content-Type', 'text/xml; charset=UTF-8')

    def post(self):
        order = validate_order(self)
        if isinstance(order, str):
            self.finish(render_reject_xml(order))
        else:
            refid = unique_id(order['action'])
            order['orderRef'] = refid
            order_book.add_order_async(order)
            self.finish(render_accept_xml(refid))

class GUIHandler(tornado.web.RequestHandler):
    def get(self):
        self.finish(render_home_page())

class SnapshotHandler(tornado.web.RequestHandler):
    snapshot = ''
    num = 0
    def get(self):
        SnapshotHandler.snapshot = order_book.orders[:]
        self.finish(render_snapshot_html(SnapshotHandler.snapshot))

    def post(self):
        message = {
            'name': 'ESE Snapshot Upload',
            'description': 'Trading snapshot %d' % SnapshotHandler.num,
            'owner': {
                'name': 'Pinky and the Brain',
                'email': 'isbadawi@gmail.com',
            },
            'signer': {
                'name': 'Ismail Badawi',
                'email': 'ismail.badawi@mail.mcgill.ca',
            },
            'transactions': SnapshotHandler.snapshot
        }
        SnapshotHandler.num += 1

application = tornado.web.Application([
    (r'/exchange/endpoint', TradeHandler),
    (r'/exchange/home', GUIHandler),
    (r'/exchange/snapshot', SnapshotHandler),
    (r'/exchange/static/(.*)', tornado.web.StaticFileHandler, {'path': 'static'})
])

if __name__ == '__main__':
    application.listen(3487)
    tornado.ioloop.IOLoop.instance().start()
