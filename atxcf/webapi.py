import argparse

from flask import Flask
from flask.ext.cors import CORS
#from flask import jsonify

import PriceNetwork
import settings
import cmd

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


def _get_port():
    """
    Returns the port from the settings, and sets a reasonable default if
    it isn't there.
    """
    port = 1337
    try:
        port = settings.get_option("port")
    except settings.SettingsError:
        settings.set_option("port", port)
    return port


def _get_host():
    """
    Returns the host from the settings, and sets a reasonable default if
    it isn't there.
    """
    host = "0.0.0.0" # bind to all interfaces
    try:
        host = settings.get_option("host")
    except settings.SettingsError:
        settings.set_option("host", host)
    return host


def main():
    # TODO: finish arg parsing...
    parser = argparse.ArgumentParser(
        description="Launches atxcf price API",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    PriceNetwork.init() # avoid annoying lazy init
    app.run(host=_get_host(), port=_get_port(), threaded=True)


if __name__ == '__main__':
    main()
