"""
PriceSource module for atxcf-bot. To add price sources, simply extend the PriceSource class
and add an instance of it to the _sources dict.
- transfix@sublevels.net - 20160117
"""

import bitfinex
import poloniex
import bittrex

import requests
import re
from pyquery import PyQuery as pq
import unicodedata
import json

import math
import time
import threading

import locale
locale.setlocale(locale.LC_ALL, '')


class PriceSourceError(RuntimeError):
    pass


class PriceSource(object):
    """
    The basic asset price querying interface.
    """

    def get_symbols(self):
        """
        Returns list of asset/currency symbols tradable at this exchange.
        """
        raise NotImplementedError("get_symbols not implemented!")

    def get_base_symbols(self):
        """
        Returns list of base currency symbols used. For instance, in the
        trade pair XBT/USD, the base symbol is USD.
        """
        raise NotImplementedError("get_base_symbols not implemented!")

    def get_price(self, from_asset, to_asset, amount=1.0):
        """
        Returns how much of to_asset you would have after exchanging it
        for amount of from_asset based on the last price traded here.
        """
        raise NotImplementedError("get_price not implemented!")


class Bitfinex(PriceSource):
    """
    Bitfinex exchange interface for atxcf-bot
    """

    def __init__(self):
        super(Bitfinex, self).__init__()
        self.bfx = bitfinex.Client()
        self.bfx_symbols = self.bfx.symbols()
    

    def get_symbols(self):
        """
        List of symbols at Bitfinex
        """
        s = self.bfx_symbols
        ss = list(set([i[:3] for i in s] + [i[3:] for i in s]))
        return [i.upper() for i in ss]


    def get_base_symbols(self):
        """
        List of base currencies
        """
        return ["USD", "BTC"]


    def get_price(self, from_asset, to_asset, amount=1.0):
        """
        Returns how much of to_asset you would have after exchanging it
        for amount of from_asset based on the last price traded here.        
        """
        symbols = self.get_symbols()
        from_asset = from_asset.upper()
        to_asset = to_asset.upper()
        if not from_asset in symbols:
            raise PriceSourceError("No such symbol %s" % from_asset)
        if not to_asset in symbols:
            raise PriceSourceError("No such symbol %s" % to_asset)

        if from_asset == to_asset:
            return amount

        inverse = False
        from_asset_lower = from_asset.lower()
        to_asset_lower = to_asset.lower()

        bfx_symbol = from_asset_lower + to_asset_lower
        if not bfx_symbol in self.bfx_symbols:
            inverse = True
            bfx_symbol = to_asset_lower + from_asset_lower
            if not bfx_symbol in self.bfx_symbols:
                raise PriceSourceError("Missing market")

        price = float(self.bfx.ticker(bfx_symbol)["last_price"])
        if inverse:
            try:
                price = 1.0/price
            except ZeroDivisionError:
                pass
        return price * amount


class Poloniex(PriceSource):
    """
    Poloniex exchange interface for atxcf-bot
    """

    def __init__(self, creds = "poloniex_cred.json"):
        super(Poloniex, self).__init__()
        self._pol = poloniex.poloniex(creds)
        self._pol_ticker = self._pol.returnTicker()
        self._pol_ticker_ts = time.time()
        self._lock = threading.RLock()


    def _update_ticker(self):
        # update ticker if it is older than 60 seconds.
        if time.time() - self._pol_ticker_ts > 60:
            self._pol_ticker = self._pol.returnTicker()
            self._pol_ticker_ts = time.time()


    def get_symbols(self):
        """
        List of tradable symbols at Poloniex
        """
        symbol_set = set()
        with self._lock:
            for cur in self._pol_ticker.iterkeys():
                for item in cur.split("_"):
                    symbol_set.add(item)
        return list(symbol_set)


    def get_base_symbols(self):
        """
        List of base currencies at Poloniex
        """
        symbol_set = set()
        with self._lock:
            for cur in self._pol_ticker.iterkeys():
                items = cur.split("_")
                symbol_set.add(items[0]) # the first item is the base currency
        return list(symbol_set)


    def get_price(self, from_asset, to_asset, amount = 1.0):
        """
        Returns how much of from_asset you would have after exchanging it
        for the amount of from_asset based on the last price traded here.
        """
        symbols = self.get_symbols()
        from_asset = from_asset.upper()
        to_asset = to_asset.upper()
        if not from_asset in symbols:
            raise PriceSourceError("No such symbol %s" % from_asset)
        if not to_asset in symbols:
            raise PriceSourceError("No such symbol %s" % to_asset)
        
        if from_asset == to_asset:
            return amount

        inverse = False
        pol_symbol = to_asset + "_" + from_asset
        with self._lock:
            if not pol_symbol in self._pol_ticker.iterkeys():
                inverse = True
                pol_symbol = from_asset + "_" + to_asset
                if not pol_symbol in self._pol_ticker.iterkeys():
                    raise PriceSourceError("Missing market")

            self._update_ticker()
            price = float(self._pol_ticker[pol_symbol]["last"])
            if inverse:
                try:
                    price = 1.0/price
                except ZeroDivisionError:
                    pass
            return price * amount


class CryptoAssetCharts(PriceSource):
    """
    Scrapes from cryptoassetcharts.info to get crypto asset price info.
    """

    def __init__(self):
        super(CryptoAssetCharts, self).__init__()
        self._req_url = "http://cryptoassetcharts.info/assets/info"
        self._asset_symbols = set()
        self._base_symbols = set()
        self._price_map = {}
        self._response = requests.get(self._req_url)
        self._response_ts = time.time()
        
        self._update_info()


    def _update_info(self):
        # if it is older than 60 seconds, do another request.
        if time.time() - self._response_ts > 60:
            self._response = requests.get(self._req_url)
            self._response_ts = time.time()
        doc = pq(self._response.content)
        tbl = doc("#tableAssets")
        self._price_map = {}
        for row in tbl('tr'):
            col = []
            for c in row.findall('td'):
                c_text = c.text
                if isinstance(c_text, unicode):
                    c_text = unicodedata.normalize('NFKD', c_text).encode('ascii','ignore')
                col.append(c_text)
            if len(col) < 7:
                continue
            asset_symbol = col[1]
            self._asset_symbols.add(asset_symbol)

            # extract last price from row
            price_str = col[4]
            price_str_comp = price_str.split(" ")
            base_symbol = price_str_comp[1]
            self._base_symbols.add(base_symbol)
            
            price_val = locale.atof(price_str_comp[0])
            self._price_map["_"+asset_symbol+"/"+base_symbol] = price_val
        

    def get_symbols(self):
        """
        List all asset symbols at the site.
        """

        # Prefix asset symbols with _ so they don't collide with other real symbol names.
        return ['_'+s for s in self._asset_symbols] + self.get_base_symbols()


    def get_base_symbols(self):
        """
        List base currencies that market prices are listed in.
        """
        return list(self._base_symbols)


    def get_price(self, from_asset, to_asset, amount = 1.0):
        """
        Returns the price as reflected in the price map
        """
        symbols = self.get_symbols()
        if not from_asset in symbols:
            raise PriceSourceError("No such symbol %s" % from_asset)
        if not to_asset in symbols:
            raise PriceSourceError("No such symbol %s" % to_asset)

        # nothing to do here
        if from_asset == to_asset:
            return amount

        inverse = False
        trade_pair_str = to_asset + '/' + from_asset
        if not trade_pair_str in self._price_map.iterkeys():
            inverse = True
            trade_pair_str = from_asset + '/' + to_asset
            if not trade_pair_str in self._price_map.iterkeys():
                raise PriceSourceError("Missing market")

        self._update_info()
        price = self._price_map[trade_pair_str]
        if inverse:
            try:
                price = 1.0/price
            except ZeroDivisionError:
                pass
        return price * amount


class Bittrex(PriceSource):
    """
    Using bittrex as an asset price source.
    """

    def __init__(self, creds = "bittrex_cred.json"):
        super(Bittrex, self).__init__()
        js_cred = json.load(open(creds))
        api_key = str(js_cred["key"])
        api_secret = str(js_cred["secret"])
        self._bittrex = bittrex.Bittrex(api_key, api_secret)

        currencies = self._bittrex.get_currencies()
        self._symbols = [item["Currency"] for item in currencies["result"]]

        mkts = self._bittrex.get_markets()["result"]
        self._base_symbols = list(set([item["BaseCurrency"] for item in mkts]))

        self._price_map = {}


    def _get_price(self, market):
        if not market in self._price_map or time.time() - self._price_map[market][1] > 60:
            ticker = self._bittrex.get_ticker(market)["result"]
            if not ticker:
                raise PriceSourceError("No such market %s" % market)
            price = float(ticker["Last"])
            self._price_map[market] = (price, time.time())
            return price
        else:
            return self._price_map[market][0]
 

    def get_symbols(self):
        """
        Returns list of asset/currency symbols tradable at this exchange.
        """
        return self._symbols


    def get_base_symbols(self):
        """
        Returns list of base currency symbols used. For instance, in the
        trade pair XBT/USD, the base symbol is USD.
        """
        return self._base_symbols


    def get_price(self, from_asset, to_asset, amount=1.0):
        """
        Returns how much of to_asset you would have after exchanging it
        for amount of from_asset based on the last price traded here.
        """
        symbols = self.get_symbols()
        from_asset = from_asset.upper()
        to_asset = to_asset.upper()
        if not from_asset in symbols:
            raise PriceSourceError("No such symbol %s" % from_asset)
        if not to_asset in symbols:
            raise PriceSourceError("No such symbol %s" % to_asset)
        
        if from_asset == to_asset:
            return amount

        inverse = False
        mkt = to_asset + "-" + from_asset
        try:
            price = self._get_price(mkt)
        except PriceSourceError:
            inverse = True
            mkt = from_asset + "-" + to_asset
            price = self._get_price(mkt)

        if inverse:
            try:
                price = 1.0/price
            except ZeroDivisionError:
                pass
        return price * amount


class Conversions(PriceSource):
    """
    Contains mappings and conversions between symbols such as
    mNXT <-> NXT, XBT <-> BTC, etc.
    """

    def __init__(self):
        super(Conversions, self).__init__()
        self._mapping = {
            "XBT/BTC": 1.0,
            "mNHZ/NHZ": 1000.0,
            "mNXT/NXT": 1000.0,
            "sat/BTC": 100000000,
            "_Coinomat1/Coinomat1": 1.0,
            "_MMNXT/MMNXT": 1.0
        }


    def get_symbols(self):
        symbols = set()
        for key in self._mapping.iterkeys():
            symbol = key.split("/")
            symbols.add(symbol[0])
            symbols.add(symbol[1])
        return list(symbols)


    def get_base_symbols(self):
        symbols = set()
        for key in self._mapping.iterkeys():
            symbol = key.split("/")
            symbols.add(symbol[1])
        return list(symbols)


    def get_price(self, from_asset, to_asset, amount = 1.0):
        """
        Uses the mapping to convert from_asset to to_asset.
        """
        symbols = self.get_symbols()
        if not from_asset in symbols:
            raise PriceSourceError("No such symbol %s" % from_asset)
        if not to_asset in symbols:
            raise PriceSourceError("No such symbol %s" % to_asset)

        # nothing to do here
        if from_asset == to_asset:
            return amount

        inverse = False
        trade_pair_str = to_asset + '/' + from_asset
        if not trade_pair_str in self._mapping.iterkeys():
            inverse = True
            trade_pair_str = from_asset + '/' + to_asset
            if not trade_pair_str in self._mapping.iterkeys():
                raise PriceSourceError("Missing market")

        price = self._mapping[trade_pair_str]
        if inverse:
            try:
                price = 1.0/price
            except ZeroDivisionError:
                pass
        return price * amount


class AllSources(PriceSource):
    """
    Uses info from all available sources
    """

    def __init__(self):
        super(AllSources, self).__init__()

        # handles to price sources
        self._sources = {
            "bitfinex.com": Bitfinex(),
            "bittrex.com": Bittrex(),
            "poloniex.com": Poloniex(),
            "cryptoassetcharts.info": CryptoAssetCharts(),
            "conversions": Conversions(),
        }


    def get_symbols(self):
        """
        Returns the set of all known symbols across all price sources.
        """
        symbols = set()
        for source_name, source in self._sources.iteritems():
            for symbol in source.get_symbols():
                symbols.add(symbol)
        return list(symbols)


    def get_base_symbols(self):
        """
        Returns the set of all known symbols across all price sources.
        """
        symbols = set()
        for source_name, source in self._sources.iteritems():
            for symbol in source.get_base_symbols():
                symbols.add(symbol)
        return list(symbols)


    def get_price(self, from_asset, to_asset, amount = 1.0):
        """
        Returns price detemrined as an average across all known sources.
        """
        prices = []
        for source_name, source in self._sources.iteritems():
            try:
                price = source.get_price(from_asset, to_asset, amount)
                prices.append(price)
            except PriceSourceError:
                pass
        if len(prices) == 0:
            raise PriceSourceError("Couldn't determine price")
        return math.fsum(prices)/float(len(prices))
