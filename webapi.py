from flask import Flask
from flask.ext.cors import CORS
#from flask import jsonify

import prices
import PriceNetwork

app = Flask(__name__)
CORS(app)
_pn = PriceNetwork.PriceNetwork()


@app.route('/')
def index():
    return '~~ atxcf-bot ~~'

@app.route('/prices')
@app.route('/get_fund_asset_prices')
def get_fund_asset_prices():
    price_d = prices.get_fund_asset_prices()
    output = "<p>"
    for key, val in price_d.iteritems():
        if isinstance(val, str):
            output += "{0}: {1}<br />".format(key, val)
        else:
            output += "{0}: {1:.8f}<br />".format(key, val)
    output += "</p>"
    return output


@app.route('/get_symbols')
def get_symbols():
    symbols = _pn.get_symbols()
    return " ".join(sorted(symbols))


@app.route('/get_price/<from_asset>/<to_asset>', defaults={'value': 1.0})
@app.route('/get_price/<from_asset>/<to_asset>/<value>')
def get_price(from_asset, to_asset, value):
    price = _pn.get_price(from_asset, to_asset, value)
    return str(price)


@app.route('/get_markets')
def get_markets():
    mkts = _pn.get_markets()
    return " ".join(sorted(mkts))


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=1337, threaded=True)
