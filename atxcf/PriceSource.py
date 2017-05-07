"""
PriceSource module for atxcf-bot. To add price sources, simply extend the PriceSource class
and add an instance of it to the _sources dict in AllSources (or use AllSources.init_sources).
- transfix@sublevels.net - 20160117
- 20170328 - transfix - not writing to file anymore when getting prices...
"""

import bitfinex
import poloniex
import bittrex
import settings
from settings import (get_creds, has_creds)
import pricedb
import memcached_client
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
            memcached_key = self._class_name() + ".bfx_symbols"
            if memcached_client.has_key(memcached_key):
                self.bfx_symbols = memcached_client.get(memcached_key)
            else:
                try:
                    self.bfx_symbols = self._bfx_client().symbols()
                    memcached_client.set(memcached_key, self.bfx_symbols)
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


    def get_symbols(self):
        """
        List of tradable symbols at Poloniex
        """
        symbol_set = set()
        key = self._class_name() + ".symbols"
        if memcached_client.has_key(key):
            return memcached_client.get(key)
        with self._lock:
            for cur in self._get_pol_ticker().iterkeys():
                for item in cur.split("_"):
                    symbol_set.add(item)
        symbols = list(symbol_set)
        memcached_client.set(key, symbols)
        return symbols


    def get_base_symbols(self):
        """
        List of base currencies at Poloniex
        """
        symbol_set = set()
        key = self._class_name() + ".base_symbols"
        if memcached_client.has_key(key):
            return memcached_client.get(key)
        with self._lock:
            for cur in self._get_pol_ticker().iterkeys():
                items = cur.split("_")
                symbol_set.add(items[0]) # the first item is the base currency
        symbols = list(symbol_set)
        memcached_client.set(key, symbols)
        return symbols


    def get_markets(self):
        """
        List of all trade pairs
        """
        mkts = []
        key = self._class_name() + ".markets"
        if memcached_client.has_key(key):
            return memcached_client.get(key)    
        with self._lock:
            for cur in self._get_pol_ticker().iterkeys():
                pair = cur.split("_")
                mkts.append(pair[1] + "/" + pair[0])
        memcached_client.set(key, mkts)
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
        if memcached_client.has_key(key):
            symbols = memcached_client.get(key)
        else:
            with self._lock:
                symbols = self._get_symbols()
                memcached_client.set(key, symbols)
        return symbols


    def get_base_symbols(self):
        """
        Returns list of base currency symbols used. For instance, in the
        trade pair XBT/USD, the base symbol is USD.
        """
        base_symbols = None
        key = self._class_name() + ".base_symbols"
        if memcached_client.has_key(key):
            base_symbols = memcached_client.get(key)
        else:
            with self._lock:
                base_symbols = self._get_base_symbols()
                memcached_client.set(key, base_symbols)
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


class AllSources(PriceSource):
    """
    Uses info from all available sources
    """

    def __init__(self):
        super(AllSources, self).__init__()
        self._lock = threading.RLock()
        self._using_pricedb = get_settings_option("using_pricedb", False)

        # handles to price sources
        self._sources = {}


    def init_sources(self, addl_sources=None):
        """
        (Re-)Populates the _sources dict. For now, this needs to be called
        to refresh the view of available symbols to price against.
        """
        with self._lock:
            errors = []
            #src_classes = [Bitfinex, Bittrex, Poloniex, CryptoAssetCharts, Conversions]
            src_classes = [Bitfinex, Poloniex, Conversions]

            # if any additional sources were passed, let's add them to the dict
            if addl_sources:
                for addl_source in addl_sources:
                    src_classes.append(addl_source)

            def add_source(srcclassobj):
                try:
                    class_name = srcclassobj.__name__
                    mkt_pairs_known = []
                    if not srcclassobj.requires_creds() or has_creds(class_name):
                        obj = srcclassobj()
                        self._sources.update({class_name: obj})
                        for mkt_pair in obj.get_markets():
                            self._store_source(class_name, mkt_pair)
                            mkt_pairs_known.append(mkt_pair)
                        print "Known pairs for source " + class_name + ":", mkt_pairs_known
                    else:
                        print "No required credentials for " + class_name + ", skipping..."
                except RuntimeError as e:
                    errors.append(e.message)

            for src_class in src_classes:
                add_source(src_class)

            if len(errors) > 0:
                print "AllSources errors:", errors


    def get_sources(self):
        if not self._sources:
            self.init_sources()
        return self._sources


    @staticmethod
    def get_cached_sources_cache_key(mkt_pair):
        return "atxcf_agent_known_sources_for_" + mkt_pair


    @staticmethod
    def get_cached_prices_cache_key(mkt_pair):
        return "atxcf_agent_prices_for_" + mkt_pair


    @staticmethod
    def get_cached_sources(mkt_pair):
        return memcached_client.get(AllSources.get_cached_sources_cache_key(mkt_pair))


    @staticmethod
    def get_cached_prices(mkt_pair):
        return memcached_client.get(AllSources.get_cached_prices_cache_key(mkt_pair))


    @staticmethod
    def set_cached_sources(mkt_pair, sources):
        memcached_client.set(AllSources.get_cached_sources_cache_key(mkt_pair), sources)


    @staticmethod
    def set_cached_prices(mkt_pair, prices):
        memcached_client.set(AllSources.get_cached_prices_cache_key(mkt_pair), prices)

    
    def _store_source(self, source_name, mkt_pair):
        """
        Associates a source with a market pair in the AllSources cache
        """
        # memcached stuff
        sources = AllSources.get_cached_sources(mkt_pair)
        if not sources:
            sources = {}
        if not mkt_pair in sources:
            sources.update({mkt_pair:[source_name]})
        else:
            source_set = set(sources[mkt_pair])
            source_set.add(source_name)
            sources[mkt_pair] = list(source_set)
        AllSources.set_cached_sources(mkt_pair, sources)

        # store in the database
        if self._using_pricedb:
            def do_db_store():
                pricedb.store_sourceentry(source_name, mkt_pair)
            db_store = threading.Thread(target=do_db_store)
            db_store.start()


    def _store_price(self, source_name, mkt_pair, price):
        """
        Appends a price to the settings AllSources cache for a 
        particular market pair known by a source.
        """
        self._store_source(source_name, mkt_pair)

        # timestamp
        now_t = time.time()
        now_dt = datetime.datetime.fromtimestamp(now_t)

        # force storing floats
        price = float(price)
        print "Storing price for pair", mkt_pair, price

        # memcached stuff
        prices = AllSources.get_cached_prices(mkt_pair)
        if not prices:
            prices = {}
        if not source_name in prices:
            prices.update({source_name:{}})
        if not mkt_pair in prices[source_name]:
            prices[source_name].update({mkt_pair:[]})
        price_list = prices[source_name][mkt_pair]
        # just update the time of last element if price is unch
        if len(price_list) > 0 and price_list[-1][1] == price:
            price_list[-1] = (now_t, price)
        else:
            price_list.append((now_t, price))
        AllSources.set_cached_prices(mkt_pair, prices)

        # store in the database
        if self._using_pricedb:
            def do_db_store():
                pricedb.store_price(source_name, mkt_pair, price, now_dt)
            db_store = threading.Thread(target=do_db_store)
            db_store.start()


    def _has_stored_price(self, mkt_pair):
        """
        Returns whether a price for the specified market pair has been
        recorded either in the cache or in the database.
        """
        sources = AllSources.get_cached_sources(mkt_pair)
        prices = AllSources.get_cached_prices(mkt_pair)
        if not sources:
            sources = {}
        if not prices:
            prices = {}
        if mkt_pair in sources:
            for source in sources[mkt_pair]:
                if not source in prices:
                    continue
                if not mkt_pair in prices[source]:
                    continue
                return True
        if self._using_pricedb:
            return pricedb.has_stored_price(mkt_pair)
        return False


    def _get_stored_last_price_pairs(self, mkt_pair):
        sources = AllSources.get_cached_sources(mkt_pair)
        prices = AllSources.get_cached_prices(mkt_pair)
        
        if not mkt_pair in sources:
            raise PriceSourceError(
                "%s: no stored market %s" % (self._class_name(), mkt_pair)
            )

        price_list = []
        for source in sources[mkt_pair]:
            if not source in prices:
                continue
            if not mkt_pair in prices[source]:
                continue
            price_seq = prices[source][mkt_pair]
            if len(price_seq) == 0:
                raise PriceSourceError(
                    "%s: missing prices for market %s in source %s" % (self._class_name(), mkt_par, source)
                )
            last_price = price_seq[-1]
            price_list.append(last_price)

        # check the database if the cache doesn't have anything
        if len(price_list) == 0 and self._using_pricedb:
            for last_price in pricedb.get_last_price_pairs(mkt_pair):
                last_price_list = list(last_price)
                last_price_list[0] = (last_price[0]-datetime.datetime(1970,1,1)).total_seconds()
                price_list.append(tuple(last_price_list))
        
        return price_list


    def _get_stored_price(self, mkt_pair):
        price_list = self._get_stored_last_price_pairs(mkt_pair)
        if len(price_list) == 0:
            raise PriceSourceError(
                "%s: empty stored price list" % self._class_name()
            )
        price_list = [item[1] for item in price_list]
        return math.fsum(price_list)/float(len(price_list))


    def _get_last_stored_price_time(self, mkt_pair):
        price_list = self._get_stored_last_price_pairs(mkt_pair)
        if len(price_list) == 0:
            raise PriceSourceError(
                "%s: empty stored price list" % self._class_name()
            )
        return max([item[0] for item in price_list])


    def get_symbols(self):
        """
        Returns the set of all known symbols across all price sources.
        """
        symbols = set()
        with self._lock:
            for source_name, source in self.get_sources().iteritems():
                for symbol in source.get_symbols():
                    symbols.add(symbol)
        return list(symbols)


    def get_base_symbols(self):
        """
        Returns the set of all known symbols across all price sources.
        """
        symbols = set()
        with self._lock:
            for source_name, source in self.get_sources().iteritems():
                for symbol in source.get_base_symbols():
                    symbols.add(symbol)
        return list(symbols)


    def get_markets(self):
        """
        Returns all markets known by all of the price sources.
        """
        mkts = set()
        with self._lock:
            for source in self.get_sources().itervalues():
                for mkt in source.get_markets():
                    mkts.add(mkt)
        return list(mkts)


    def get_market_sources(self):
        """
        Returns all market sources with their respective markets
        """
        mkt_srcs = {}
        with self._lock:
            for source in self.get_sources().itervalues():
                mkt_srcs.update({source._class_name(): source.get_markets()})
        return mkt_srcs


    def get_price(self, from_asset, to_asset, amount=1.0, get_last=False, do_store=True):
        """
        Returns price detemrined as an average across all known sources.
        If get_last is True, this will return the last price recorded if one
        exists and won't try to get a fresh price in that case.
        """
        mkt_pair = "{0}/{1}".format(from_asset, to_asset)
        print "getting price for", mkt_pair
        interval = self._update_interval
        stored_price = None
        if self._has_stored_price(mkt_pair):
            print "has stored price for", mkt_pair
            last_price_time = self._get_last_stored_price_time(mkt_pair)
            stored_price = self._get_stored_price(mkt_pair)
            print "last_price_time:", datetime.datetime.fromtimestamp(last_price_time)
            if get_last or time.time() - last_price_time <= interval:
                print "Returning stored price for", mkt_pair, stored_price, amount
                return stored_price * amount

        # If we have already retrieved a price for this pair before, only try to retrieve
        # prices from the same sources as before. Otherwise, just try all sources and record
        # the one that succeeds. TODO: avoid having to try all sources in the first place.
        values = []

        source_names = AllSources.get_cached_sources(mkt_pair)
        if not source_names:
            source_names = {}
            
        with self._lock:
            # Check if this pair is in the sources cache. If so, no need to re-check
            # what sources know about the requested mkt_pair.
            sources = []
            if mkt_pair in source_names:
                for source_name in source_names[mkt_pair]:
                    source = self.get_sources()[source_name]
                    sources.append((source_name, source))
            else:
                for source_name, source in self.get_sources().iteritems():
                    sources.append((source_name, source))
            
            for source_name, source in sources:
                try:
                    value = source.get_price(from_asset, to_asset, amount)
                    values.append(float(value))
                    price = 0.0
                    try:
                        price = value / amount
                    except ZeroDivisionError:
                        pass
                    self._store_price(source_name, mkt_pair, price)
                except PriceSourceError:
                    pass # TODO: might want to log this error

        if len(values) == 0 and stored_price:
            print "Could not retrieve price for %s, using previously stored" % mkt_pair
            values.append(stored_price * amount)
                        
        if len(values) == 0:
            raise PriceSourceError("%s: Couldn't determine price of %s/%s" % (self._class_name(), from_asset, to_asset))
        return math.fsum(values)/float(len(values)) # TODO: work on price list reduction
