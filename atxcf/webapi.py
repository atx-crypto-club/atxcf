import argparse

from flask import Flask
from flask.ext.cors import CORS
#from flask import jsonify

import PriceNetwork

import coinmarketcap

class ProxySource(PriceNetwork.PriceNetwork):
    """
    Gets price info from a price source web API.
    TODO: finish!
    """
    pass


app = Flask(__name__)
CORS(app)
_source = None


@app.route('/')
def index():
    return '~~ atxcf-bot ~~'


@app.route('/get_symbols')
def get_symbols():
    if _source == None:
        raise PriceNetwork.PriceSource.PriceSourceError("No price source set")
    symbols = _source.get_symbols()
    return " ".join(sorted(symbols))


@app.route('/get_price/<from_asset>/<to_asset>', defaults={'value': 1.0})
@app.route('/get_price/<from_asset>/<to_asset>/<value>')
def get_price(from_asset, to_asset, value):
    if _source == None:
        raise PriceNetwork.PriceSource.PriceSourceError("No price source set")
    price = _source.get_price(from_asset, to_asset, value)
    return str(price)


@app.route('/get_markets')
def get_markets():
    if _source == None:
        raise PriceNetwork.PriceSource.PriceSourceError("No price source set")
    mkts = _source.get_markets()
    return " ".join(sorted(mkts))


@app.route('/get_top_coins', defaults={'top': 10})
@app.route('/get_top_coins/<top>')
def get_top_coins(top):
    top_symbols = [coinmarketcap.short(name.lower()) for name in coinmarketcap.top(int(top))]
    return " ".join(top_symbols)


def main():
    parser = argparse.ArgumentParser(
        description="Launches atxcf price API",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    _source = PriceNetwork.PriceNetwork()
    app.run(host='0.0.0.0', port=1337, threaded=True)


if __name__ == '__main__':
    main()

