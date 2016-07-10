"""
PriceSource module for atxcf-bot. To add price sources, simply extend the PriceSource class
and add an instance of it to the _sources dict.
- transfix@sublevels.net - 20160117
"""

import bitfinex
import poloniex
import bittrex
# import coinmarketcap
import settings
import pricedb

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


def get_creds(site):
    return settings.get_creds(site)


class PriceSource(object):
    """
    The basic asset price querying interface.
    """

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


    def _class_name(self):
        return self.__class__.__name__


class Bitfinex(PriceSource):
    """
    Bitfinex exchange interface for atxcf-bot
    """

    def __init__(self):
        super(Bitfinex, self).__init__()
        self.bfx = bitfinex.Client()
        try:
            self.bfx_symbols = self.bfx.symbols()
        except:
            raise PriceSourceError("%s: Error getting symbols from bitfinex" % self._class_name())
        self._lock = threading.RLock()
    

    def get_symbols(self):
        """
        List of symbols at Bitfinex
        """
        s = []
        with self._lock:
            s = self.bfx_symbols
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
            return [i.upper()[:3] + '/' + i.upper()[3:] for i in self.bfx_symbols]


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
            if not bfx_symbol in self.bfx_symbols:
                inverse = True
                bfx_symbol = to_asset_lower + from_asset_lower
                if not bfx_symbol in self.bfx_symbols:
                    raise PriceSourceError("%s: Missing market" % self._class_name())

            try:
                price = float(self.bfx.ticker(bfx_symbol)["last_price"])
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

    def __init__(self):
        super(Poloniex, self).__init__()
        api_key, api_secret = get_creds(self._class_name())
        self._pol = poloniex.poloniex(api_key, api_secret)
        try:
            self._pol_ticker = self._pol.returnTicker()
        except:
            raise PriceSourceError("%s: Error getting ticker" % self._class_name())
        self._pol_ticker_ts = time.time()
        self._lock = threading.RLock()


    def _update_ticker(self):
        with self._lock:
            # update ticker if it is older than the specified amount of seconds.
            timeout = settings.get_option("price_update_interval")
            if time.time() - self._pol_ticker_ts > timeout:
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


    def get_markets(self):
        """
        List of all trade pairs
        """
        mkts = []
        with self._lock:
            for cur in self._pol_ticker.iterkeys():
                pair = cur.split("_")
                mkts.append(pair[1] + "/" + pair[0])
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
            if not pol_symbol in self._pol_ticker.iterkeys():
                inverse = True
                pol_symbol = from_asset + "_" + to_asset
                if not pol_symbol in self._pol_ticker.iterkeys():
                    raise PriceSourceError("%s: Missing market" % self._class_name())

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
            timeout = settings.get_option("price_update_interval")
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

    def __init__(self):
        super(Bittrex, self).__init__()
        api_key, api_secret = get_creds(self._class_name())
        self._bittrex = bittrex.Bittrex(api_key, api_secret)
        try:
            currencies = self._bittrex.get_currencies()
        except:
            raise PriceSourceError("%s: Error getting currency list" % self._class_name())
        self._symbols = [item["Currency"] for item in currencies["result"]]
        try:
            self._markets = self._bittrex.get_markets()["result"]
        except:
            raise PriceSourceError("%s: Error getting markets" % self._class_name())
        self._base_symbols = list(set([item["BaseCurrency"] for item in self._markets]))
        self._price_map = {}
        self._ticker_ts = time.time()
        self._lock = threading.RLock()

        self._update_price_map(True)


    def _update_price_map(self, force=False):
        with self._lock:
            # update ticker if it is older than timout seconds.
            timeout = settings.get_option("price_update_interval")
            if force or time.time() - self._ticker_ts > timeout:
                result = self._bittrex.get_market_summaries()["result"]
                prices = [(res["MarketName"], res["Last"]) for res in result]
                for market, price in prices:
                    self._price_map[market] = (price, time.time())


    def _get_price(self, market):
        self._update_price_map()
        with self._lock:
            if not market in self._price_map:
                ticker = self._bittrex.get_ticker(market)["result"]
                if not ticker:
                    raise PriceSourceError("%s: No such market %s" % (self._class_name(), market))
                if ticker["Last"] == None:
                    raise PriceSourceError("%s: Market unavailable" % self._class_name())
                price = float(ticker["Last"])
                self._price_map[market] = (price, time.time())
                return price
            else:
                return self._price_map[market][0]


    def get_symbols(self):
        """
        Returns list of asset/currency symbols tradable at this exchange.
        """
        with self._lock:
            return self._symbols


    def get_base_symbols(self):
        """
        Returns list of base currency symbols used. For instance, in the
        trade pair XBT/USD, the base symbol is USD.
        """
        with self._lock:
            return self._base_symbols


    def get_markets(self):
        """
        Returns all markets at bittrex
        """
        with self._lock:
            return [str(c["MarketCurrency"]+"/"+c["BaseCurrency"]) for c in self._markets]


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
        sett = settings.get_settings()
        if not "Conversions" in sett:
            sett["Conversions"] = self._mapping
        else:
            conv = sett["Conversions"]
            self._mapping.update(conv)
            sett["Conversions"] = self._mapping
        settings.set_settings(sett)

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

        # make sure there is a AllSources section in the settings
        sett = settings.get_settings()
        if not self._class_name() in sett:
            sett.update({self._class_name():{}})

        # make sure there is a "prices" subsection in the AllSources section
        if not "prices" in sett[self._class_name()]:
            sett[self._class_name()].update({"prices": {}})

        # make sure there is a "sources" subsection in the AllSources section
        if not "sources" in sett[self._class_name()]:
            sett[self._class_name()].update({"sources": {}})

        settings.set_settings(sett)

        # handles to price sources
        self._sources = {}
        self.init_sources()


    def init_sources(self, addl_sources=None):
        """
        (Re-)Populates the _sources dict. For now, this needs to be called
        to refresh the view of available symbols to price against.
        """
        with self._lock:
            errors = []
            src_classes = [Bitfinex, Bittrex, Poloniex, CryptoAssetCharts, Conversions]

            # if any additional sources were passed, let's add them to the dict
            if addl_sources:
                for addl_source in addl_sources:
                    src_classes.append(addl_source)

            def add_source(srcclassobj):
                try:
                    obj = srcclassobj()
                    self._sources.update({srcclassobj.__name__: obj})
                    for mkt_pair in obj.get_markets():
                        self._store_source(srcclassobj.__name__, mkt_pair)
                except RuntimeError as e:
                    errors.append(e.message)

            for src_class in src_classes:
                add_source(src_class)

            if len(errors) > 0:
                print "AllSources errors:", errors


    def _store_source(self, source_name, mkt_pair):
        """
        Associates a source with a market pair in the AllSources cache
        """
        sett = settings.get_settings()
        sources = sett[self._class_name()]["sources"]
        if not mkt_pair in sources:
            sources.update({mkt_pair:[source_name]})
        else:
            source_set = set(sources[mkt_pair])
            source_set.add(source_name)
            sources[mkt_pair] = list(source_set)
        settings.set_settings(sett)
        pricedb.store_sourceentry(source_name, mkt_pair)


    def _store_price(self, source_name, mkt_pair, price):
        """
        Appends a price to the settings AllSources cache for a 
        particular market pair known by a source.
        """
        self._store_source(source_name, mkt_pair)
        sett = settings.get_settings()
        prices = sett[self._class_name()]["prices"]
        if not source_name in prices:
            prices.update({source_name:{}})
        if not mkt_pair in prices[source_name]:
            prices[source_name].update({mkt_pair:[]})
        price_list = prices[source_name][mkt_pair]
        # just update the time of last element if price is unch
        now_t = time.time()
        now_dt = datetime.datetime.fromtimestamp(now_t)
        if len(price_list) > 0 and price_list[-1][1] == price:
            price_list[-1] = (now_t, price)
        else:
            price_list.append((now_t, price))
        settings.set_settings(sett)
        # TODO: only need to update time if last price hasn't changed
        pricedb.store_price(source_name, mkt_pair, price, now_dt)


    def _has_stored_price(self, mkt_pair):
        """
        Returns whether a price for the specified market pair has been
        recorded.
        """
        sett = settings.get_settings()
        sources = sett[self._class_name()]["sources"]
        prices = sett[self._class_name()]["prices"]
        if mkt_pair in sources:
            for source in sources[mkt_pair]:
                if not source in prices:
                    continue
                if not mkt_pair in prices[source]:
                    continue
                return True
        return False


    def _get_stored_last_price_pairs(self, mkt_pair):
        sett = settings.get_settings()
        sources = sett[self._class_name()]["sources"]
        prices = sett[self._class_name()]["prices"]
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
            for source_name, source in self._sources.iteritems():
                for symbol in source.get_symbols():
                    symbols.add(symbol)
        return list(symbols)


    def get_base_symbols(self):
        """
        Returns the set of all known symbols across all price sources.
        """
        symbols = set()
        with self._lock:
            for source_name, source in self._sources.iteritems():
                for symbol in source.get_base_symbols():
                    symbols.add(symbol)
        return list(symbols)


    def get_markets(self):
        """
        Returns all markets known by all of the price sources.
        """
        mkts = set()
        with self._lock:
            for source in self._sources.itervalues():
                for mkt in source.get_markets():
                    mkts.add(mkt)
        return list(mkts)


    def get_market_sources(self):
        """
        Returns all market sources with their respective markets
        """
        mkt_srcs = {}
        with self._lock:
            for source in self._sources.itervalues():
                mkt_srcs.update({source._class_name(): source.get_markets()})
        return mkt_srcs


    def get_price(self, from_asset, to_asset, amount = 1.0, get_last=False):
        """
        Returns price detemrined as an average across all known sources.
        If get_last is True, this will return the last price recorded if one
        exists and won't try to get a fresh price in that case.
        """
        mkt_pair = "{0}/{1}".format(from_asset, to_asset)
        print "getting price for", mkt_pair
        interval = settings.get_option("price_update_interval")
        stored_price = None
        if self._has_stored_price(mkt_pair):
            last_price_time = self._get_last_stored_price_time(mkt_pair)
            stored_price = self._get_stored_price(mkt_pair)
            if get_last or time.time() - last_price_time <= interval:
                print "Returning stored price for", mkt_pair
                return stored_price * amount

        # If we have already retrieved a price for this pair before, only try to retrieve
        # prices from the same sources as before. Otherwise, just try all sources and record
        # the one that succeeds. TODO: avoid having to try all sources in the first place.
        prices = []
        sett = settings.get_settings()
        sources = sett[self._class_name()]["sources"]
        prices_d = sett[self._class_name()]["prices"]
        with self._lock:
            if mkt_pair in sources:
                for source_name in sources[mkt_pair]:
                    try:
                        price = self._sources[source_name].get_price(from_asset, to_asset, amount)
                        prices.append(price)
                        self._store_price(source_name, mkt_pair, price / amount)
                    except PriceSourceError:
                        pass # TODO: might want to log this error
            else:
                for source_name, source in self._sources.iteritems():
                    try:
                        price = source.get_price(from_asset, to_asset, amount)
                        prices.append(price)
                        self._store_price(source_name, mkt_pair, price / amount) 
                    except PriceSourceError:
                        pass

        if len(prices) == 0 and stored_price:
            print "Could not retrieve price for %s, using previously stored" % mkt_pair
            prices.append(stored_price)
                        
        if len(prices) == 0:
            raise PriceSourceError("%s: Couldn't determine price of %s/%s" % (self._class_name(), from_asset, to_asset))
        return math.fsum(prices)/float(len(prices)) # TODO: work on price list reduction


    def purge_cache(self, **kwargs):
        """
        Purges cache of prices depending on arguments:
        - olderthan: purges all prices that are older than 'olderthan'
        - mkt_pair: purges prices from the specified market pair
        - source: purges prices from the specified source
        """
        olderthan=time.time()
        if "olderthan" in kwargs:
            olderthan = kwargs["olderthan"]
        mkt_pair = None # if none, purge all market pairs
        if "mkt_pair" in kwargs:
            mkt_pair = kwargs["mkt_pair"]
        source = None # if none, purge from all sources
        if "source" in kwargs:
            source = kwargs["source"]

        # TODO: maybe source and mkt_pair can be regexes?

        # purge all prices for now
        # TODO: finish me!
        sett = settings.get_settings()
        sett[self._class_name()].update({"prices": {}})
        sett[self._class_name()].update({"sources": {}})
        settings.set_settings(sett)


    def get_num_prices(self, **kwargs):
        """
        Returns the number of prices for the specified source and market pair
        """
        # TODO: make mkt_pair and source regexes.
        mkt_pair = None
        if "mkt_pair" in kwargs:
            mkt_pair = kwargs["mkt_pair"]
        source = None
        if "source" in kwargs:
            source = kwargs["source"]

        # TODO: finish me!
        return 0


    def get_cache_time_range(self, **kwargs):
        """
        Returns a tuple of times representing oldest time and newest time (inclusive)
        of prices gathered for specified source and mkt_pair.
        """
        # TODO: make mkt_pair and source regexes.
        mkt_pair = None
        if "mkt_pair" in kwargs:
            mkt_pair = kwargs["mkt_pair"]
        source = None
        if "source" in kwargs:
            source = kwargs["source"]

        # TODO: finish me!
        return (time.time(), time.time())
