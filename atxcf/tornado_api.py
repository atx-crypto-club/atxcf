from tornado import websocket, web, ioloop
import json

import cmd
from settings import get_settings_option

cl = []

class IndexHandler(web.RequestHandler):
    def get(self):
	idx = """
<pre>
  ~~ atxcf-bot ~~
  commands: %s
</pre>
        """ % cmd.get_commands()
        self.write(idx)

class SocketHandler(websocket.WebSocketHandler):
    def check_origin(self, origin):
        return True # accept from anywhere for now

    def open(self):
        if self not in cl:
            cl.append(self)

    def on_message(self, message):
	data = json.loads(message)
	cmd_str = None
	if "cmd" in data:
	    cmd_str = data["cmd"]
	    
	if cmd_str == "get_price":
	    from_asset = data["from_asset"]
	    to_asset = data["to_asset"]
	    value = data["value"]
	    price = cmd.get_price(value, from_asset, to_asset)
	    data["price"] = price
	    self.write_message(json.dumps(data))

	elif cmd_str == "get_markets":
	    mkts = cmd.get_markets()
	    self.write_message(json.dumps(mkts))

	elif cmd_str == "get_top_coins":
	    top_symbols = cmd.get_top_coins(top)
	    self.write_message(json.dumps(top_symbols)) 

	elif cmd_str == "get_commands":
	    self.write_message(json.dumps(cmd.get_commands()))

	elif cmd_str == "get_help":
	    self.write_message(json.dumps(cmd.get_help(cmd_help)))

    def on_close(self):
        if self in cl:
            cl.remove(self)

class ApiHandler(web.RequestHandler):

    @web.asynchronous
    def get(self, *args):
	cmd_str = self.get_argument("cmd")
	
	if cmd_str == "get_price":
	    from_asset = self.get_argument("from_asset")
	    to_asset = self.get_argument("to_asset")
	    value = self.get_argument("value", default=1.0)
	    price = cmd.get_price(value, from_asset, to_asset)
	    self.write(str(price))
	    
	elif cmd_str == "get_symbols":
	    symbols = cmd.get_symbols()
	    self.write(" ".join(sorted(symbols)))

	elif cmd_str == "get_markets":
	    mkts = cmd.get_markets()
	    self.write(" ".join(sorted(mkts)))

	elif cmd_str == "get_top_coins":
	    top = self.get_argument("top", default=10)
	    top_symbols = cmd.get_top_coins(top)
	    self.write(" ".join(top_symbols))

	elif cmd_str == "get_commands":
	    self.write(" ".join(sorted(cmd.get_commands())))

	elif cmd_str == "get_help":
	    cmd_help = self.get_argument("cmd_help", default="get_help")
	    self.write("<pre>%s</pre>" % cmd.get_help(cmd_help))
	
	self.finish()


    @web.asynchronous
    def post(self):
        pass


def _get_port():
    """
    Returns the port from the settings, and sets a reasonable default if
    it isn't there.
    """
    return get_settings_option("tornado_port", default=8888)


def _get_host():
    """
    Returns the host from the settings, and sets a reasonable default if
    it isn't there.
    """
    return get_settings_option("tornado_host", default='') # default, bind to all interfaces


app = web.Application([
    (r'/', IndexHandler),
    (r'/ws', SocketHandler),
    (r'/api', ApiHandler),
])


def main():
    app.listen(_get_port(), address=_get_host())
    ioloop.IOLoop.instance().start()


if __name__ == '__main__':
    main()
