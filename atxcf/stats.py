"""
stats module for the atxcf bot. Here we compute various metrics on historical data.
- transfix@sublevels.net - 20180102
"""
from settings import get_setting, set_setting, has_setting
from PriceNetwork import get_all_prices
import cache

import time
import os
import uuid
import json
import glob
import hashlib
from collections import defaultdict
from collections import namedtuple


def log_prices(mkts=None):
    """
    Logs market prices at a rate specified in the settings. If mkts is None,
    logs prices of all known markets.
    """
    last_prices = {}
    cur_prices = {}
    price_history = []
    while True:
        # TODO: break this thread from outside
        
        pre_t = time.time()
        cur_prices = get_all_prices(mkts)
        post_t = time.time()

        # only record changes from the last record
        recorded_prices = {}
        for mkt, price in cur_prices.iteritems():
            changed = False
            if not mkt in last_prices:
                changed = True
            else:
                if last_prices[mkt] != price:
                    changed = True
            if changed:
                recorded_prices[mkt] = price

        print "changed mkts: ", post_t, [mkt for mkt in recorded_prices]

        if recorded_prices:
            price_history.append((pre_t, post_t, recorded_prices))
        last_prices = cur_prices

        # default 60 second delay minimum between samples
        while True:
            delay = get_setting("price_history", "delay", default=60)
            cur_time = time.time()
            if cur_time - pre_t > delay:
                break
            time.sleep(1)

        # if we have enough samples saved, let's dump them to a file.
        num_samples = get_setting("price_history", "samples_per_file", default=5)
        print "len(price_history)", len(price_history)
        if len(price_history) >= num_samples:
            ph_prefix = get_setting("price_history", "file_prefix", default="price_history")
            unique = str(uuid.uuid1())
            ph_fn = ph_prefix + "." + unique + ".json"
            try:
                print "log_prices: Writing ", ph_fn
                with open(ph_fn, 'w') as f:
                    price_history_d = {
                        unique: price_history
                    }
                    json.dump(price_history_d, f, sort_keys=True,
                              indent=4, separators=(',', ': '))
            except IOError as e:
                _log_error(['log_prices', '', str(e)])

            price_history = []


def _md5(s):
    """
    Returns the md5 hash string of s.
    """
    return hashlib.md5(s).hexdigest()


def _fhash(fn):
    """
    Returns the md5 hash of the filename.
    Hashes the absolute filename.
    """
    return _md5(os.path.abspath(fn))


Candle = namedtuple('Candle', ['begin', 'end', 'low', 'high',
                               'first_time', 'last_time', 'num_samples'])
def make_Candle(begin=0.0, end=0.0, low=0.0, high=0.0,
               first_time=0.0, last_time=0.0, num_samples=0.0):
    return Candle(begin, end, low, high,
                  first_time, last_time, num_samples)


def _visited_cache_key(ph_fn, market, interval=60*60):
    """
    Cache key for visited files.
    """
    mkt_str = "%s%s" % tuple(market.split("/"))
    return _fhash(ph_fn) + "_" + mkt_str + "_" + str(float(interval))


def _is_visited(ph_fn, market, interval=60*60):
    """
    Check the cache if we have visited this price history file already.
    """
    return cache.has_key(_visited_cache_key(ph_fn, market, interval))


def _set_visited(ph_fn, market, interval=60*60):
    """
    Check the cache if we have visited this price history file for the
    interval already.
    """
    return cache.set_val(_visited_cache_key(ph_fn, market, interval), 1)


def get_price_history_files(file_prefix=None):
    """
    Returns a list of price history files according to the
    file_prefix setting.
    """
    if not file_prefix:
        file_prefix = get_setting("price_history", "file_prefix", default="price_history")
    return glob.glob(file_prefix+"*.json")


def get_new_price_history_files(market, interval=60*60, file_prefix=None):
    """
    Returns a list of unvisited price history files.
    """
    file_names = []
    for fn in get_price_history_files(file_prefix):
        if not _is_visited(fn, market, interval):
            file_names.append(fn)
    return file_names


def compute_candles(market, interval=60*60, file_prefix=None):
    """
    Computes candle tuples (enter, max, min, exit) for the market
    using the specified interval. Searches for market history using the
    file_prefix pointing to a collection of raw json file history dumps.
    """
    file_names = get_new_price_history_files(market, interval, file_prefix)

    candles = defaultdict(lambda: make_Candle())
    
    for fn in file_names:
        if not os.path.isfile(fn):
            continue

        try:
            with open(fn, 'r') as f:
                raw_prices = json.load(f)
                for unique, price_history in raw_prices.iteritems():
                    for item in price_history:
                        pre_t = item[0]
                        post_t = item[1]
                        recorded_prices = item[2]
                        if market in recorded_prices:

                            idx, rem = divmod(post_t, interval)
                            bin = idx * float(interval)
                            rec_price = recorded_prices[market]
                            candle = candles[bin]

                            # initialize the candle if no samples
                            # have been provided for it
                            if candle.num_samples == 0:
                                candles[bin] = Candle(rec_price, rec_price,
                                                      rec_price, rec_price,
                                                      post_t, post_t, 1)
                            else:
                                begin = candle.begin
                                end = candle.end
                                low = candle.low
                                high = candle.high
                                first_time = candle.first_time
                                last_time = candle.last_time
                                num_samples = candle.num_samples

                                # handle enter / exit of the candle
                                if post_t < first_time:
                                    first_time = post_t
                                    begin = rec_price
                                elif post_t > last_time:
                                    last_time = post_t
                                    end = rec_price

                                # handle low/high
                                if rec_price < low:
                                    low = rec_price
                                elif rec_price > high:
                                    high = rec_price

                                candles[bin] = Candle(begin, end, low, high,
                                                      first_time, last_time,
                                                      num_samples + 1)
        finally:
            _set_visited(fn, market, interval)
    return candles


def merge_candles(candle_a, candle_b):
    """
    Returns a candle encompassing both input candles.
    """
    # Don't try to merge candles with NaNs.
    for elem in candle_a:
        if elem == float('NaN'):
            candle_a.num_samples = 0
    for elem in candle_b:
        if elem == float('NaN'):
            candle_b.num_samples = 0

    if not candle_a or candle_a.num_samples == 0:
        return candle_b
    if not candle_b or candle_b.num_samples == 0:
        return candle_a
    
    return make_Candle(candle_a.begin if candle_a.first_time < candle_b.first_time else candle_b.begin,
                       candle_a.end if candle_a.last_time > candle_b.last_time else candle_b.end,
                       candle_a.low if candle_a.low < candle_b.low else candle_b.low,
                       candle_a.high if candle_a.high > candle_b.high else candle_b.high,
                       candle_a.first_time if candle_a.first_time < candle_b.first_time else candle_b.first_time,
                       candle_a.last_time if candle_a.last_time > candle_b.last_time else candle_b.last_time,
                       candle_a.num_samples + candle_b.num_samples)


def _candle_cache_key(market, interval, candle_bin):
    """
    Returns a string suitable for referring to the candle in the cache.
    """
    mkt_str = "%s%s" % tuple(market.split("/"))
    return "candle_" + mkt_str + "_" + str(float(interval)) + "_" + str(candle_bin)


def update_candles(market, interval=60*60, file_prefix=None):
    """
    Computes candles from the latest data and merges it with
    existing candles.
    """
    candles = compute_candles(market, interval, file_prefix)
    for candle_bin, new_candle in candles.iteritems():
        cur_candle_key = _candle_cache_key(market, interval, candle_bin)
        cur_candle = cache.get_val(cur_candle_key)
        if not cur_candle:
            cur_candle = make_Candle()
        cache.set_val(cur_candle_key,
                      merge_candles(make_Candle(*cur_candle),
                                    new_candle))


def get_candle(market, candle_bin, interval=60*60, file_prefix=None):
    """
    Returns candles of the specified interval of the market.
    """
    update_candles(market, interval, file_prefix)
    candle = cache.get_val(_candle_cache_key(market,
                                             interval,
                                             candle_bin))
    if not candle:
        candle = make_Candle()
    return make_Candle(*candle)


def get_candle_bin(moment, interval=60*60):
    """
    Returns the candle for the moment timestamp.
    """
    idx, rem = divmod(float(moment), interval)
    return idx * float(interval)


def get_candle_attr(attr, market, moment, interval=60*60):
    """
    Returns the attribute for the latest candle for the market and interval.
    """
    candle_bin = get_candle_bin(moment, interval)
    candle = get_candle(market, candle_bin, interval)
    if not candle or candle.num_samples <= 0:
        return float('NaN')
    return getattr(candle, attr)


def get_candle_begin(*args):
    return get_candle_attr("begin", *args)

def get_candle_end(*args):
    return get_candle_attr("end", *args)

def get_candle_low(*args):
    return get_candle_attr("low", *args)

def get_candle_high(*args):
    return get_candle_attr("high", *args)


def get_current_candle_bin(interval=60*60):
    """
    Returns the current candle bin for the specified interval.
    """
    return get_candle_bin(time.time(), interval)


def get_current_candle_attr(attr, market, interval=60*60):
    """
    Returns the attribute for the latest candle for the market and interval.
    """
    return get_candle_attr(attr, market, time.time(), interval)


def get_current_begin(*args):
    return get_current_candle_attr("begin", *args)

def get_current_end(*args):
    return get_current_candle_attr("end", *args)

def get_current_low(*args):
    return get_current_candle_attr("low", *args)

def get_current_high(*args):
    return get_current_candle_attr("high", *args)


def get_current_percent_change(market, interval=60*60):
    """
    Returns the current percentage change over the interval.
    """
    now = time.time()
    prev_moment = now - float(interval)
    prev_begin = get_candle_begin(market, prev_moment, interval)
    prev_end = get_candle_end(market, prev_moment, interval)    
    prev = (prev_begin + prev_end) / 2.0
    begin = get_current_begin(market, interval)
    end = get_current_end(market, interval)
    cur = (begin + end) / 2.0
    diff = cur - prev
    return 100.0 * (diff / prev)
