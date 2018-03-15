"""
Basic demo of how to use this module.
"""
import atxcf
import json
import unittest
import tempfile
import os

from functools import wraps
from random import sample, triangular

import cProfile
import pstats

from itertools import izip, tee


def pairwise(iterable):
    "s -> (s0,s1), (s1,s2), (s2, s3), ..."
    a, b = tee(iterable)
    next(b, None)
    return izip(a, b)


def get_temp_filename(prefix="atxcf_"):
    #tf_name = None
    #with tempfile.NamedTemporaryFile(delete=False) as tf:
    #    tf_name = tf.name
    fd, tf_name = tempfile.mkstemp(prefix=prefix, suffix=".json")
    os.close(fd)
    return tf_name


def set_temp_settings_filename(prefix="atxcf_"):
    atxcf.set_settings_filename(get_temp_filename(prefix))


def do_profile(cb):
    pr = cProfile.Profile()
    pr.enable()
    cb()
    pr.disable()
    return pr


def profile_stats(cb, sortby='cumulative', num_stats=100):
    prof = pstats.Stats(do_profile(cb))
    return prof.sort_stats(sortby)


def print_profile_stats(cb, sortby='cumulative', num_stats=100):
    ps = profile_stats(cb, sortby, num_stats)
    ps.print_stats(num_stats)
    
    
def print_portfolio_info(portfolio, base_asset="USD"):
    info = {
        "name": portfolio,
        "email": atxcf.get_user_email(portfolio),
        "base_asset": base_asset,
        "values": atxcf.get_portfolio_values(portfolio,
                                             base_asset),
        "NAV": atxcf.get_portfolio_nav(portfolio,
                                       base_asset),
        "has_shares": atxcf.has_shares(portfolio),
        "meta": atxcf.get_metadata(portfolio)
    }

    if atxcf.has_shares(portfolio):
        info.update({
            "num_shares": atxcf.get_num_shares_outstanding(portfolio),
            "num_shareholders": atxcf.get_num_shareholders(portfolio),
            "shareholders": atxcf.get_shareholders(portfolio),
            "nav_share_ratio": atxcf.get_portfolio_nav_share_ratio(portfolio,
                                                                   base_asset)
        })

    print json.dumps(info, sort_keys=True, indent=4,
                     separators=(',', ': '))


def print_portfolios():
    for portfolio in atxcf.get_users():
        print_portfolio_info(portfolio)


def print_banner(title):
    print "-"*80
    print title
    print "-"*80


def add_user(username, balances={}, metadata={}):
    if not atxcf.has_user(username):
        print "Adding user", username
        atxcf.add_user(username)
    else:
        print "Already added user", username
    for asset, balance in balances.iteritems():
        atxcf.set_balance(username, asset, float(balance))
    for key, value in metadata.iteritems():
        atxcf.set_metadata_value(username, key, value)


def init_users():
    """
    Initialize the test users.
    """
    # default domain for user email addresses
    atxcf.set_domain("catx.io")

    # using create_shares
    add_user("catx_00")

    # using grant_shares
    add_user("catx_01",
             {
                 "BTC": 12,
                 "LTC": 82,
                 "ETH": 132
             })

    # transfer test accounts
    add_user("transfix",
             {
                 "BTC": 1.0,
                 "LTC": 4.20,
             },
             {
                 "data": "blaaah",
                 "store_stuff": "here",
                 "like": "passwords",
                 "and_other": "identity data to associate to users"
             })
    add_user("sheldon",
             {
                 "BTC": 0.5,
                 "ETH": 14
             })


#print_banner("START")
#print_portfolios()


def init_shared_users():
    init_users()
    if atxcf.get_balance("transfix", "catx_00") <= 0.0:
        print_banner("create_shares catx_00 transfix")
        atxcf.create_shares("catx_00", "transfix", {"BTC": 0.432, "LTC": 4})
        print_portfolios()

    if atxcf.get_balance("sheldon", "catx_00") <= 0.0:
        print_banner("create_shares catx_00 sheldon")
        atxcf.create_shares("catx_00", "sheldon", {"BTC": 0.322, "ETH": 4.22})
        print_portfolios()

    if atxcf.get_balance("transfix", "catx_01") <= 0.0:
        print_banner("grant_shares catx_01 transfix")
        atxcf.grant_shares("catx_01", "transfix", 200)
        print_portfolios()

    if atxcf.get_balance("sheldon", "catx_01") <= 0.0:
        print_banner("grant_shares catx_01 sheldon")
        atxcf.grant_shares("catx_01", "sheldon", 100)
        print_portfolios()


class SettingsContext():
    def __init__(self, prefix):
        self._prefix = prefix
        self.error_epsilon = 0.0000001 # for price arithmetic float error testing

    def __enter__(self):
        set_temp_settings_filename(self._prefix)
        atxcf.clear_settings()

        # only use the simple linear price conversion source for tests
        atxcf.set_option("price_sources", ["Conversions"])

        # add some fake assets priced against USD
        atxcf.set_conversion("FOO_A/USD", 0.1)
        atxcf.set_conversion("FOO_B/USD", 0.01)
        atxcf.set_conversion("FOO_C/USD", 0.001)
        atxcf.set_conversion("FOO_D/USD", 0.0001)

        # re-init the price network so the above conversions are available
        # TODO: shouldn't have to re-init... when a source changes, any new
        # nodes and edges should be added and nodes with no info available
        # anymore should be dropped.
        atxcf.init_price_network()
        
        return self
    
    def __exit__(self, type, value, traceback):
        atxcf.write_settings()


def settings_context(test_func):
    """
    Handy decorator for setting up a settings file context for
    each test run.
    """
    @wraps(test_func)
    def _wrap(*args, **kwargs):
        with SettingsContext("atxcf_" + test_func.__name__ + "_") as sc:
            kwargs["SettingsContext"] = sc
            return test_func(*args, **kwargs)
    return _wrap


class TestAtxcf(unittest.TestCase):

    def test_settings_filename(self):
        """
        Checking that the settings filename is absolute
        """
        fn = atxcf.get_settings_filename()
        self.assertTrue(os.path.isabs(fn))


    @settings_context
    def test_init_settings(self, **kwargs):
        """
        Looking for default settings when initializing from
        nothing.
        """
        # check by default url setting
        self.assertEqual(atxcf.get_setting("program_url"),
                         atxcf.get_default_program_url())
        os.remove(atxcf.get_settings_filename())


    @settings_context
    def test_set_setting(self, **kwargs):
        """
        Making sure we can set settings.
        """
        atxcf.set_setting("test", 4.20)
        self.assertEqual(atxcf.get_setting("test"), 4.20)


    @settings_context
    def test_settings_pre_change_callback(self, **kwargs):
        """
        Testing settings pre-change callbacks.
        """
        closure2 = {}
        def change_cb():
            closure2["key"] = True
            # since this is a pre-change callback,
            # we should not have a "test" setting
            self.assertFalse(atxcf.has_setting("test"))

        atxcf.add_settings_pre_change_callback("test", change_cb)
        self.assertEqual(len(atxcf.get_settings_change_callbacks("test", prefix="__pre__")), 1)

        atxcf.set_setting("test", "value")
        self.assertEqual(atxcf.get_setting("test"), "value")
        self.assertTrue("key" in closure2)


    @settings_context
    def test_settings_post_change_callback(self, **kwargs):
        """
        Testing settings post-change callbacks.
        """
        closure2 = {}
        def change_cb():
            closure2["key"] = True
            # since this is a post-change callback,
            # we should now have a "test" setting
            self.assertTrue(atxcf.has_setting("test"))

        atxcf.add_settings_post_change_callback("test", change_cb)
        self.assertEqual(len(atxcf.get_settings_change_callbacks("test", prefix="__post__")), 1)

        atxcf.set_setting("test", "value")
        self.assertEqual(atxcf.get_setting("test"), "value")
        self.assertTrue("key" in closure2)


    @settings_context
    def test_domain(self, **kwargs):
        """
        Checking for the default domain setting and whether we
        can change it and read it back.
        """
        self.assertEqual(atxcf.get_domain(), "localhost")
        domain = "catx.io"
        atxcf.set_domain(domain)
        self.assertEqual(atxcf.get_domain(), domain)


    @settings_context
    def test_add_user(self, **kwargs):
        """
        Testing add user functionality.
        """
        username = "transfix"
        self.assertFalse(atxcf.has_user(username))
        atxcf.add_user(username)
        self.assertTrue(atxcf.has_user(username))
        print atxcf.get_users()
        self.assertEqual(atxcf.number_of_users(), 1)


    @settings_context
    def test_set_user_email(self, **kwargs):
        """
        Checking for default email setting when adding a user.
        Then checking if we can change it.
        """
        username = "transfix"
        self.assertFalse(atxcf.has_user(username))

        # first check for the default email if none set when user is created.
        atxcf.add_user(username)
        domain = atxcf.get_domain()
        self.assertEqual(atxcf.get_user_email(username), "%s@%s" % (username, domain))

        atxcf.set_user_email(username, "user@example.com")
        self.assertEqual(atxcf.get_user_email(username), "user@example.com")


    @settings_context
    def test_set_user_metadata(self, **kwargs):
        """
        Testing get/set of user metadata.
        """
        username = "transfix"
        metakey = "test"
        metadata = "hello"
        self.assertFalse(atxcf.has_user(username))
        atxcf.add_user(username)
        self.assertTrue(atxcf.has_user(username))
        atxcf.set_metadata_value(username, metakey, metadata)
        self.assertEqual(atxcf.get_metadata_value(username, metakey), metadata)


    @settings_context
    def test_conversion(self, **kwargs):
        """
        Testing basic linear symbol conversion.
        """
        atxcf.set_conversion("TEST_ASSET/USD", 1337.0)
        price = atxcf.get_price(1337.0, "TEST_ASSET/USD")
        self.assertTrue(abs(price - 1.0) <= 0.001)    


    @settings_context
    def test_get_nav(self, **kwargs):
        """
        Testing getting net asset value with fake assets.
        """
        balances = {
            "FOO_A": 10.0,
            "FOO_B": 100.0,
            "FOO_C": 1000.0
        }
        nav = atxcf.get_nav(balances, "USD")
        self.assertTrue(abs(nav - 1010100.0) <= 0.001)


    @settings_context
    def test_set_balance(self, **kwargs):
        """
        Testing simple set_balance call.
        """
        
        username = "transfix"
        user_asset = "FOO_A"
        user_asset_amount = 5.0
        epsilon = kwargs["SettingsContext"].error_epsilon

        atxcf.add_user(username)
        self.assertTrue(atxcf.has_user(username))
        atxcf.set_balance(username, user_asset, user_asset_amount)
        self.assertTrue(abs(atxcf.get_balance(username, user_asset) - user_asset_amount) <= epsilon)

        
    @settings_context
    def test_set_balance_callbacks(self, **kwargs):
        """
        Making sure pre set balance callbacks work.
        """
        pre_closure = {}
        post_closure = {}
        def _cb(closure, name, asset, amount, cur_time, meta):
            closure.update({
                "name": name,
                "asset": asset,
                "amount": amount,
                "cur_time": cur_time,
                "meta": meta
            })

        username = "transfix"
        user_asset = "FOO_A"
        user_asset_amount = 5.0
        epsilon = kwargs["SettingsContext"].error_epsilon

        atxcf.add_user(username)
        self.assertTrue(atxcf.has_user(username))

        def _pre_cb(name, asset, amount, cur_time, meta):
            _cb(pre_closure, name, asset, amount, cur_time, meta)
        atxcf.add_pre_set_balance_callback("test", _pre_cb)
        self.assertTrue(atxcf.has_pre_set_balance_callback("test"))

        def _post_cb(name, asset, amount, cur_time, meta):
            _cb(post_closure, name, asset, amount, cur_time, meta)            
        atxcf.add_post_set_balance_callback("test", _post_cb)
        self.assertTrue(atxcf.has_post_set_balance_callback("test"))

        atxcf.set_balance(username, user_asset, user_asset_amount)
        self.assertTrue(abs(atxcf.get_balance(username, user_asset) - user_asset_amount) <= epsilon)

        # test if the closures were modified by callback calls
        self.assertTrue(abs(pre_closure["amount"] - user_asset_amount) <= epsilon)
        self.assertTrue(abs(post_closure["amount"] - user_asset_amount) <= epsilon)

        # time of the pre callback should be before the post 
        self.assertTrue(pre_closure["cur_time"] < post_closure["cur_time"])

    @settings_context
    def test_inc_balance(self, **kwargs):
        """
        Testing inc_balance call.
        """
        username = "transfix"
        user_asset = "FOO_A"
        user_asset_amount = 5.0
        epsilon = kwargs["SettingsContext"].error_epsilon

        atxcf.add_user(username)
        self.assertTrue(atxcf.has_user(username))
        atxcf.set_balance(username, user_asset, user_asset_amount)
        self.assertTrue(abs(atxcf.get_balance(username, user_asset) - user_asset_amount) <= epsilon)

        atxcf.inc_balance(username, user_asset, user_asset_amount)
        self.assertTrue(abs(atxcf.get_balance(username, user_asset) - user_asset_amount*2) <= epsilon)

        
    @settings_context
    def test_dec_balance(self, **kwargs):
        """
        Testing inc_balance call.
        """
        username = "transfix"
        user_asset = "FOO_A"
        user_asset_amount = 5.0
        epsilon = kwargs["SettingsContext"].error_epsilon

        atxcf.add_user(username)
        self.assertTrue(atxcf.has_user(username))
        atxcf.set_balance(username, user_asset, user_asset_amount)
        self.assertTrue(abs(atxcf.get_balance(username, user_asset) - user_asset_amount) <= epsilon)

        atxcf.dec_balance(username, user_asset, user_asset_amount)
        self.assertTrue(atxcf.get_balance(username, user_asset) <= epsilon)


    @settings_context
    def test_get_assets(self, **kwargs):
        """
        Test getting user assets
        """
        users = ["transfix", "sheldon", "icky", "scott"]
        b_l = [1.0, 10.0, 100.0, 1000.0]
        asset_balances = {
            "FOO_A": sample(b_l, len(b_l)),
            "FOO_B": sample(b_l, len(b_l)),
            "FOO_C": sample(b_l, len(b_l)),
            "FOO_D": sample(b_l, len(b_l)),
        }

        # add some balances
        for i, user in enumerate(users):
            atxcf.add_user(user)
            self.assertTrue(atxcf.has_user(user))
            for asset, balances in asset_balances.iteritems():
                atxcf.set_balance(user, asset, balances[i])

        assets = []
        for asset in asset_balances:
            assets.append(asset)

        for user in users:
            self.assertEqual(atxcf.get_assets(user), assets)


    @settings_context
    def test_transfer(self, **kwargs):
        """
        Test moving assets from one account to another.
        """
        users = ["transfix", "sheldon", "icky", "scott"]
        b_l = [1.0, 10.0, 100.0, 1000.0]
        asset_balances = {
            "FOO_A": sample(b_l, len(b_l)),
            "FOO_B": sample(b_l, len(b_l)),
            "FOO_C": sample(b_l, len(b_l)),
            "FOO_D": sample(b_l, len(b_l)),
        }
        assets = [asset for asset in asset_balances]

        epsilon = kwargs["SettingsContext"].error_epsilon
        
        # set some balances
        for i, user in enumerate(users):
            atxcf.add_user(user)
            self.assertTrue(atxcf.has_user(user))
            for asset, balances in asset_balances.iteritems():
                atxcf.set_balance(user, asset, balances[i])

        total_nav_foo_d = 0.0
        for user in users:
            total_nav_foo_d += atxcf.get_portfolio_nav(user, "FOO_D")
        print total_nav_foo_d

        # do a bunch of random transfers and make sure
        # the sum of all the user navs equal what we started
        # with.
        for i in xrange(100):
            for asset in sample(assets, len(assets)):
                for t_users in pairwise(sample(users, len(users))):
                    max_value = atxcf.get_balance(t_users[0], asset)
                    amount = triangular(0.001, 1.0, 0.3) * max_value
                    print i, t_users, asset, max_value, amount
                    try:
                        atxcf.transfer(t_users[0], t_users[1], asset, amount)
                    except atxcf.InsufficientBalance as ib:
                        print ib.from_user, ib.to_user, ib.asset, ib.amount

        new_total_nav_foo_d = 0.0
        for user in users:
            print user, atxcf.get_portfolio(user)
            new_total_nav_foo_d += atxcf.get_portfolio_nav(user, "FOO_D")

        print new_total_nav_foo_d

        self.assertTrue(abs(total_nav_foo_d - new_total_nav_foo_d) <= epsilon)

        # TODO: reconcile all the transfers that happened with the transfer
        # log and ledgers to make sure everything lines up
        
        

if __name__ == "__main__":
    unittest.main()


# limit orders for the book
#atxcf.limit_buy("transfix", "CATX/BTC", 221, 0.0007)
#atxcf.limit_buy("transfix", "CATX/BTC", 445, 0.0008)
#atxcf.limit_buy("sheldon", "CATX/BTC", 335, 0.0007)
#atxcf.limit_buy("sheldon", "CATX/BTC", 124, 0.00065)
#atxcf.limit_sell("transfix", "CATX/BTC", 221, 0.0015)
#atxcf.limit_sell("transfix", "CATX/BTC", 445, 0.0017)
#atxcf.limit_sell("sheldon", "CATX/BTC", 335, 0.002)
#atxcf.limit_sell("sheldon", "CATX/BTC", 124, 0.0019)

#print atxcf.orderbook("CATX/BTC")

# print atxcf.spread("CATX/BTC")

#print atxcf.get_orders("transfix", "CATX/BTC")
#print atxcf.get_orders("sheldon", "CATX/BTC")

# limit orders that resolve
# atxcf.limit_buy("transfix", "CATX/BTC", 20, 0.00195)
# atxcf.limit_sell("sheldon", "CATX/BTC", 4, 0.0007)

# print atxcf.orderbook("CATX/BTC")

# Print how much CATX can be had for 0.3 BTC according
# to the order book.
# print atxcf.ask_depth("CATX/BTC", 0.3)

# Print the total ask depth
# print atxcf.ask_depth("CATX/BTC")

# Print how much BTC can be had for 10 CATX according
# to the order book.
# print atxcf.bid_depth("CATX/BTC", 10)

# Print the total bid depth.
# print atxcf.bid_depth("CATX/BTC")

# market orders
# atxcf.market_buy("transfix", "CATX/BTC", 24)
# atxcf.market_sell("sheldon", "CATX/BTC", 15)


