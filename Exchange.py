"""
Exchange module for atxcf-bot
"""

import bitfinex
import poloniex


class ExchangeError(RuntimeError):
    pass


class Exchange(object):
    """
    The basic exchange querying interface
    """

    def get_symbols():
        """
        Returns list of asset/currency symbols tradable at this exchange.
        """
        raise NotImplementedError("get_symbols not implemented!")

    def get_price(from_asset, to_asset, amount=1.0):
        """
        Returns how much of to_asset you would have after exchanging it
        for amount of from_asset based on the last price traded here.
        """
        raise NotImplementedError("get_price not implemented!")


class Bitfinex(Exchange):
    """
    Bitfinex exchange interface for atxcf-bot
    """

    def __init__(self):
        self.bfx = bitfinex.Client()
        self.bfx_symbols = self.bfx.symbols()
    

    def get_symbols(self):
        """
        List of symbols at Bitfinex
        """
        s = self.bfx_symbols
        ss = list(set([i[:3] for i in s] + [i[3:] for i in s]))
        return [i.upper() for i in ss]


    def get_price(self, from_asset, to_asset, amount=1.0):
        """
        Returns how much of to_asset you would have after exchanging it
        for amount of from_asset based on the last price traded here.        
        """
        symbols = self.get_symbols()
        from_asset = from_asset.upper()
        to_asset = to_asset.upper()
        if not from_asset in symbols:
            raise ExchangeError("No such symbol %s" % from_asset)
        if not to_asset in symbols:
            raise ExchangeError("No such symbol %s" % to_asset)

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
                raise ExchangeError("Missing market")

        price = float(self.bfx.ticker(bfx_symbol)["last_price"])
        if inverse:
            price = 1.0/price
        return price * amount


class Poloniex(Exchange):
    """
    Poloniex exchange interface for atxcf-bot
    """

    def __init__(self, creds = "poloniex_cred.json"):
        self.pol = poloniex.poloniex(creds)
        self.pol_ticker = self.pol.returnTicker()


    def get_symbols(self):
        """
        List of tradable symbols at Poloniex
        """
        symbol_set = set()
        for cur in self.pol_ticker.iterkeys():
            items = cur.split("_")
            for item in items:
                symbol_set.add(item)
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
            raise ExchangeError("No such symbol %s" % from_asset)
        if not to_asset in symbols:
            raise ExchangeError("No such symbol %s" % to_asset)
        
        if from_asset == to_asset:
            return amount

        inverse = False
        pol_symbol = to_asset + "_" + from_asset
        if not pol_symbol in self.pol_ticker.iterkeys():
            inverse = True
            pol_symbol = from_asset + "_" + to_asset
            if not pol_symbol in self.pol_ticker.iterkeys():
                raise ExchangeError("Missing market")

        self.pol_ticker = self.pol.returnTicker() #update it now
        price = float(self.pol_ticker[pol_symbol]["last"])
        if inverse:
            price = 1.0/price
        return price * amount

