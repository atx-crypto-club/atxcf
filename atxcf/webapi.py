import argparse

from flask import Flask
from flask.ext.cors import CORS
from flask import jsonify

import PriceNetwork
from settings import get_settings_option, has_option, get_option
import cmd
import sys
import logging

import coinmarketcap

class ProxySource(PriceNetwork.PriceNetwork):
    """
    Gets price info from a price source web API.
    TODO: finish!
    """
    pass


app = Flask(__name__)
CORS(app)


@app.route('/')
def index():
    idx = """
<pre>
  ~~ atxcf-bot ~~
  commands: %s
</pre>
    """ % cmd.get_commands()
    return idx


@app.route('/get_symbols')
def get_symbols():
    symbols = cmd.get_symbols()
    return " ".join(sorted(symbols))


@app.route('/get_price/<from_asset>/<to_asset>', defaults={'value': 1.0})
@app.route('/get_price/<from_asset>/<to_asset>/<value>')
def get_price(from_asset, to_asset, value):
    price = cmd.get_price(value, from_asset, to_asset) # this inverted API sucks...
    return str(price)


@app.route('/get_markets')
def get_markets():
    mkts = cmd.get_markets()
    return " ".join(sorted(mkts))


@app.route('/get_top_coins', defaults={'top': 10})
@app.route('/get_top_coins/<top>')
def get_top_coins(top):
    top_symbols = cmd.get_top_coins(top)
    return " ".join(top_symbols)


@app.route('/get_commands')
def get_commands():
    return " ".join(sorted(cmd.get_commands()))


@app.route('/get_help', defaults={'cmd_help': 'get_help'})
@app.route('/get_help/<cmd_help>')
def get_help(cmd_help):
    return "<pre>%s</pre>" % cmd.get_help(cmd_help)


@app.route('/coinbase_webhook', methods=["POST"])
def coinbase_webhook():
    if request.method == "POST":
        json_dict = request.get_json()
	# TODO: do stuff with incoming data for the fund
	logging.info(jsonify(json_dict))
        return jsonify(json_dict)
    else:
        return """<html><body>
        <p>bollocks</p>
        </body></html>"""


def _get_port():
    """
    Returns the port from the settings, and sets a reasonable default if
    it isn't there.
    """
    return get_settings_option("port", default=1337)


def _get_host():
    """
    Returns the host from the settings, and sets a reasonable default if
    it isn't there.
    """
    return get_settings_option("host", default="0.0.0.0")


def _get_logfile():
    """
    Returns the logfile from the setting. If unset, returns None.
    """
    if has_option("logfile"):
	return get_option("logfile")
    return None


def main(argv=[]):
    # get resonable defaults
    host = _get_host()
    port = _get_port()
    logfile = _get_logfile()

    # override with command line args
    argc = len(argv)
    if argc > 0:
        host = argv[0]
    if argc > 1:
        port = argv[1]
    if argc > 2:
        logfile = argv[2]

    if logfile:
	logging.basicConfig(filename=logfile, level=logging.DEBUG)
    app.run(host=host, port=port, threaded=True)


if __name__ == '__main__':
    main(sys.argv[1:])
