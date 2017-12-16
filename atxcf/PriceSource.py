"""
PriceSource module for atxcf-bot.
- transfix@sublevels.net - 20160117
- 20170328 - transfix - not writing to file anymore when getting prices...
- 20171214 - transfix - add sources to the PriceNetwork
"""

import bitfinex
import poloniex
import bittrex
import settings
from settings import (get_creds, has_creds)
import cache
from settings import get_settings_option, get_settings, set_settings

import requests
import re
from pyquery import PyQuery as pq
import unicodedata
import json

import math
import time
import datetime
import threading
import os

import locale
locale.setlocale(locale.LC_ALL, '')


class PriceSourceError(RuntimeError):
    pass


class PriceSource(object):
    """
    The basic asset price querying interface.
    """
    def __init__(self):
        # limit price updates to 60 second intervals
        self._update_interval = get_settings_option("price_update_interval", 60)

    def get_symbols(self):
        """
        Returns list of asset/currency symbols tradable at this exchange.
        """
        raise NotImplementedError("%s: get_symbols not implemented!" % self._class_name())

    def get_base_symbols(self):
        """
        Returns list of base currency symbols used. For instance, in the
        trade pair XBT/USD, the base symbol is USD.
        """
        raise NotImplementedError("%s: get_base_symbols not implemented!" % self._class_name())

    def get_markets(self):
        """
        Returns a list of market pairs seen by this source.
        """
        raise NotImplementedError("%s: get_markets not implemented!" % self._class_name())

    def get_price(self, from_asset, to_asset, amount=1.0):
        """
        Returns how much of to_asset you would have after exchanging it
        for amount of from_asset based on the last price traded here.
        """
        raise NotImplementedError("%s: get_price not implemented!" % self._class_name())


    def check_symbol(self, asset_symbol, uppercase=True):
        """
        Check if this price source knows something about the specified symbol.
        Throws an error if not.
        """
        symbols = self.get_symbols()
        if uppercase:
            asset_symbol = asset_symbol.upper()
        if not asset_symbol in symbols:
            raise PriceSourceError("%s: No such symbol %s" % (self._class_name(), asset_symbol))


    def check_symbols(self, asset_symbols, uppercase=True):
        """
        Checks if we handle all the symbols in the collection.
        """
        for asset_symbol in asset_symbols:
            self.check_symbol(asset_symbol, uppercase)


    @classmethod
    def requires_creds(cls):
        """
        If your source requires credentials to work, override _get_requires_creds to return True.
        """
        return cls._get_requires_creds()


    @staticmethod
    def _get_requires_creds():
        return False


    def _class_name(self):
        return self.__class__.__name__


class Bitfinex(PriceSource):
    """
    Bitfinex exchange interface for atxcf-bot
    """

    def __init__(self):
        super(Bitfinex, self).__init__()
        self.bfx = None
        self.bfx_symbols = None
        self._lock = threading.RLock()


    def _bfx_client(self):
        if not self.bfx:
            self.bfx = bitfinex.Client()
        return self.bfx

    def _bfx_symbols(self):
        if not self.bfx_symbols:
            cache_key = self._class_name() + ".bfx_symbols"
            if cache.has_key(cache_key):
                self.bfx_symbols = cache.get_val(cache_key)
            else:
                try:
                    self.bfx_symbols = self._bfx_client().symbols()
                    cache.set_val(cache_key, self.bfx_symbols)
                except:
                    raise PriceSourceError("%s: Error getting symbols from bitfinex" % self._class_name())
        return self.bfx_symbols


    def get_symbols(self):
        """
        List of symbols at Bitfinex
        """
        s = []
        with self._lock:
            s = self._bfx_symbols()
        ss = list(set([i[:3] for i in s] + [i[3:] for i in s]))
        return [i.upper() for i in ss]


    def get_base_symbols(self):
        """
        List of base currencies
        """
        return ["USD", "BTC"]


    def get_markets(self):
        """
        List of market pairs at Bifinex.
        """
        with self._lock:
            return [i.upper()[:3] + '/' + i.upper()[3:] for i in self._bfx_symbols()]


    def get_price(self, from_asset, to_asset, amount=1.0):
        """
        Returns how much of to_asset you would have after exchanging it
        for amount of from_asset based on the last price traded here.        
        """
        self.check_symbols((from_asset, to_asset))

        if from_asset == to_asset:
            return amount

        inverse = False
        from_asset_lower = from_asset.lower()
        to_asset_lower = to_asset.lower()

        bfx_symbol = from_asset_lower + to_asset_lower
        with self._lock:
            if not bfx_symbol in self._bfx_symbols():
                inverse = True
                bfx_symbol = to_asset_lower + from_asset_lower
                if not bfx_symbol in self._bfx_symbols():
                    raise PriceSourceError("%s: Missing market" % self._class_name())

            try:
                price = float(self._bfx_client().ticker(bfx_symbol)["last_price"])
            except requests.exceptions.ReadTimeout:
                raise PriceSourceError("%s: Error getting last_price: requests.exceptions.ReadTimeout" % self._class_name())
            except ValueError:
                raise PriceSourceError("%s: throttled" % self._class_name())

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


    @staticmethod
    def _get_requires_creds():
        return True


    def __init__(self):
        super(Poloniex, self).__init__()
        self._pol = None
        self._pol_ticker = None
        self._pol_ticker_ts = time.time()
        self._symbols = None
        self._lock = threading.RLock()

    def _get_pol(self):
        if not self._pol:
            api_key, api_secret = get_creds(self._class_name())
            self._pol = poloniex.poloniex(api_key, api_secret)
        return self._pol

    def _get_pol_ticker(self):
        if not self._pol_ticker:
            try:
                self._pol_ticker = self._get_pol().returnTicker()
                self._pol_ticker_ts = time.time()
            except:
                raise PriceSourceError("%s: Error getting ticker" % self._class_name())
        return self._pol_ticker


    def _update_ticker(self):
        with self._lock:
            # update ticker if it is older than the specified amount of seconds.
            timeout = self._update_interval
            if time.time() - self._pol_ticker_ts > timeout:
                self._pol_ticker = None
                self._symbols = None


    def get_symbols(self):
        """
        List of tradable symbols at Poloniex
        """
        if self._symbols != None:
            return self._symbols
        key = self._class_name() + ".symbols"
        if cache.has_key(key):
            self._symbols = cache.get_val(key)
            return self._symbols
        symbol_set = set()
        with self._lock:
            for cur in self._get_pol_ticker().iterkeys():
                for item in cur.split("_"):
                    symbol_set.add(item)
        symbols = list(symbol_set)
        cache.set_val(key, symbols)
        self._symbols = symbols
        return symbols


    def get_base_symbols(self):
        """
        List of base currencies at Poloniex
        """
        symbol_set = set()
        key = self._class_name() + ".base_symbols"
        if cache.has_key(key):
            return cache.get_val(key)
        with self._lock:
            for cur in self._get_pol_ticker().iterkeys():
                items = cur.split("_")
                symbol_set.add(items[0]) # the first item is the base currency
        symbols = list(symbol_set)
        cache.set_val(key, symbols)
        return symbols


    def get_markets(self):
        """
        List of all trade pairs
        """
        mkts = []
        key = self._class_name() + ".markets"
        if cache.has_key(key):
            return cache.get_val(key)    
        with self._lock:
            for cur in self._get_pol_ticker().iterkeys():
                pair = cur.split("_")
                mkts.append(pair[1] + "/" + pair[0])
        cache.set_val(key, mkts)
        return mkts


    def get_price(self, from_asset, to_asset, amount = 1.0):
        """
        Returns how much of from_asset you would have after exchanging it
        for the amount of from_asset based on the last price traded here.
        """
        self.check_symbols((from_asset, to_asset))
        
        if from_asset == to_asset:
            return amount

        inverse = False
        from_asset = from_asset.upper()
        to_asset = to_asset.upper()
        pol_symbol = to_asset + "_" + from_asset
        with self._lock:
            self._update_ticker()
            ticker = self._get_pol_ticker()
            if not pol_symbol in ticker.iterkeys():
                inverse = True
                pol_symbol = from_asset + "_" + to_asset
                if not pol_symbol in ticker.iterkeys():
                    raise PriceSourceError("%s: Missing market" % self._class_name())
            price = float(ticker[pol_symbol]["last"])

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
        try:
            self._response = requests.get(self._req_url)
        except:
            raise PriceSourceError("%s: Error getting cryptoassetcharts.info" % self._class_name())
        self._response_ts = time.time()
        self._lock = threading.RLock()

        self._update_info()

    def _update_info(self):
        with self._lock:
            # if it is older than timeout seconds, do another request.
            timeout = self._update_interval
            if time.time() - self._response_ts > timeout:
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
            
                price_val = locale.atof(price_str_comp[0].replace(',', ''))
                self._price_map["_"+asset_symbol+"/"+base_symbol] = price_val
        

    def get_symbols(self):
        """
        List all asset symbols at the site.
        """
        # Prefix asset symbols with _ so they don't collide with other real symbol names.
        with self._lock:
            return ['_'+s for s in self._asset_symbols] + self.get_base_symbols()


    def get_base_symbols(self):
        """
        List base currencies that market prices are listed in.
        """
        with self._lock:
            return list(self._base_symbols)


    def get_markets(self):
        """
        List all markets known by CryptoAssetCharts
        """
        with self._lock:
            return list(self._price_map.iterkeys())
 

    def get_price(self, from_asset, to_asset, amount = 1.0):
        """
        Returns the price as reflected in the price map
        """
        self.check_symbols((from_asset, to_asset), False)

        # nothing to do here
        if from_asset == to_asset:
            return amount

        inverse = False
        trade_pair_str = to_asset + '/' + from_asset

        with self._lock:
            if not trade_pair_str in self._price_map.iterkeys():
                inverse = True
                trade_pair_str = from_asset + '/' + to_asset
                if not trade_pair_str in self._price_map.iterkeys():
                    raise PriceSourceError("%s: Missing market" % self._class_name())

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


    @staticmethod
    def _get_requires_creds():
        return True


    def __init__(self):
        super(Bittrex, self).__init__()

        self._bittrex = None
        self._symbols = None
        self._markets = None
        self._base_symbols = None
        self._price_map = {}
        self._ticker_ts = time.time()
        self._lock = threading.RLock()

        self._update_price_map(True)


    def _client(self):
        if not self._bittrex:
            api_key, api_secret = get_creds(self._class_name())
            self._bittrex = bittrex.Bittrex(api_key, api_secret)
        return self._bittrex


    def _get_symbols(self):
        if not self._symbols:
            try:
                currencies = self._client().get_currencies()
            except Exception as e:
                raise PriceSourceError("%s: Error getting currency list :: %s" % (self._class_name(), e.message))
            self._symbols = [item["Currency"] for item in currencies["result"]]
        return self._symbols


    def _get_markets(self):
        if not self._markets:
            try:
                self._markets = self._client().get_markets()["result"]
            except:
                raise PriceSourceError("%s: Error getting markets" % self._class_name())
        return self._markets


    def _get_base_symbols(self):
        if not self._base_symbols:
            self._base_symbols = list(set([item["BaseCurrency"] for item in self._get_markets()]))
        return self._base_symbols


    def _get_price_map(self):
        if not self._price_map:
            result = self._client().get_market_summaries()["result"]
            prices = [(res["MarketName"], res["Last"]) for res in result]
            for market, price in prices:
                self._price_map[market] = (price, time.time())
            self._ticker_ts = time.time()
        return self._price_map
        

    def _update_price_map(self, force=False):
        with self._lock:
            # update ticker if it is older than timout seconds.
            timeout = self._update_interval
            if force or time.time() - self._ticker_ts > timeout:
                self._price_map = {}
                

    def _get_price(self, market):
        self._update_price_map()
        with self._lock:
            if not market in self._get_price_map():
                ticker = self._client().get_ticker(market)["result"]
                if not ticker:
                    raise PriceSourceError("%s: No such market %s" % (self._class_name(), market))
                if ticker["Last"] == None:
                    raise PriceSourceError("%s: Market unavailable" % self._class_name())
                price = float(ticker["Last"])
                self._price_map[market] = (price, time.time())
                return price
            else:
                return float(self._get_price_map()[market][0])


    def get_symbols(self):
        """
        Returns list of asset/currency symbols tradable at this exchange.
        """
        symbols = None
        key = self._class_name() + ".symbols"
        if cache.has_key(key):
            symbols = cache.get_val(key)
        else:
            with self._lock:
                symbols = self._get_symbols()
                cache.set_val(key, symbols)
        return symbols


    def get_base_symbols(self):
        """
        Returns list of base currency symbols used. For instance, in the
        trade pair XBT/USD, the base symbol is USD.
        """
        base_symbols = None
        key = self._class_name() + ".base_symbols"
        if cache.has_key(key):
            base_symbols = cache.get_val(key)
        else:
            with self._lock:
                base_symbols = self._get_base_symbols()
                cache.set_val(key, base_symbols)
        return base_symbols


    def get_markets(self):
        """
        Returns all markets at bittrex
        """
        with self._lock:
            return [str(c["MarketCurrency"]+"/"+c["BaseCurrency"]) for c in self._get_markets()]


    def get_price(self, from_asset, to_asset, amount=1.0):
        """
        Returns how much of to_asset you would have after exchanging it
        for amount of from_asset based on the last price traded here.
        """
        self.check_symbols((from_asset, to_asset))
        
        if from_asset == to_asset:
            return amount

        inverse = False
        from_asset = from_asset.upper()
        to_asset = to_asset.upper()
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

        #def test0xbt_func():
        #    return 0.31337

        #def test1test0_func():
        #    return 1337

        # default conversions
        # TODO: support arbitrary conversion functions other than linear f(x) -> x*C
        self._mapping = {
            "XBT/BTC": 1.0,
            "mNHZ/NHZ": 1000.0,
            "mNXT/NXT": 1000.0,
            "sat/BTC": 100000000,
            "_Coinomat1/Coinomat1": 1.0,
            "_MMNXT/MMNXT": 1.0,
            "_CoinoUSD/CoinoUSD": 1.0,
            "XDG/DOGE": 1.0,
            #"TEST0/XBT": test0xbt_func,
            #"TEST1/TEST0": test1test0_func
        }

        # read conversions from settings file
        sett = get_settings()
        if not "Conversions" in sett:
            sett["Conversions"] = self._mapping
            set_settings(sett)
        else:
            conv = sett["Conversions"]
            self._mapping.update(conv)

        self._lock = threading.RLock()


    def get_symbols(self):
        symbols = set()
        with self._lock:
            for key in self._mapping.iterkeys():
                symbol = key.split("/")
                symbols.add(symbol[0])
                symbols.add(symbol[1])
        return list(symbols)


    def get_base_symbols(self):
        symbols = set()
        with self._lock:
            for key in self._mapping.iterkeys():
                symbol = key.split("/")
                symbols.add(symbol[1])
        return list(symbols)


    def get_markets(self):
        """
        Returns list of conversions supported as if they were markets themselves.
        """
        with self._lock:
            return list(self._mapping.iterkeys())


    def get_price(self, from_asset, to_asset, amount = 1.0):
        """
        Uses the mapping to convert from_asset to to_asset.
        """
        self.check_symbols((from_asset, to_asset), False)

        # nothing to do here
        if from_asset == to_asset:
            return amount

        inverse = False
        trade_pair_str = to_asset + '/' + from_asset
        if not trade_pair_str in self._mapping.iterkeys():
            inverse = True
            trade_pair_str = from_asset + '/' + to_asset
            if not trade_pair_str in self._mapping.iterkeys():
                raise PriceSourceError("%s: Missing market" % self._class_name())

        price = 0.0
        with self._lock:
            price = self._mapping[trade_pair_str]
        if hasattr(price, '__call__'):
            price = price()
        price = float(price)
        if inverse:
            try:
                price = 1.0/price
            except ZeroDivisionError:
                pass
        return price * amount
