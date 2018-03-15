# -*- coding: utf-8 -*-
"""
handles double entry accounting for the system.
"""

import csv
import time
import threading
from copy import deepcopy
from collections import defaultdict
from json import dumps

from settings import (
    get_settings_option, get_settings, set_settings, set_option,
    get_option, get_setting, set_setting, get_settings_filename
)

from utils import (
    append_record
)

from PriceNetwork import get_price

class InsufficientBalance(RuntimeError):
   def __init__(self, from_user, to_user, asset, amount, meta):
      self.from_user = from_user
      self.to_user = to_user
      self.asset = asset
      self.amount = amount
      self.meta = meta

_lock = threading.RLock()

# serial number for every log entry in the system. Every new log entry
# represents some atomic change to a user account in the system.
_log_id = 0
def _log_change(name, item, cur_time=None, meta={}):
    """
    Adds a change to the specified user's changelog
    """
    global _log_id
    if not cur_time:
        cur_time = time.time()
    fields = [cur_time, _log_id, name, item, dumps(meta)]
    log_filename = get_user_changelog(name)
    append_record(log_filename, fields)
    _log_id += 1


def get_domain():
    """
    Returns the DNS domain to use.
    """
    return get_setting("accounts", "domain", default="localhost")


def set_domain(domain, meta=None):
    """
    Sets the DNS domain namespace to use for this agent instance.
    """
    global _lock
    with _lock:
        set_setting("accounts", "domain", domain, meta=meta)
    

def _get_accounts():
    """
    Returns accounts dict from settings.
    """
    return get_setting("accounts", default={})


def _get_users():
    """
    Returns the user dict from settings.
    """
    return get_setting("accounts", "users", default={})


def _get_balances(user):
    """
    Returns the balances dict from settings.
    """
    return get_setting("accounts", "users", user, "balances", default={})


def number_of_users():
    """
    Returns the number of users known to the system.
    """
    return len(_get_users())


def get_users():
    """
    Returns the user names of all in the system
    """
    return [name for name in _get_users()]


def has_user(name):
    """
    Returns a boolean whether the user is known to the system.
    """
    return name in _get_users()


def get_default_user_changelog_filename(name):
    """
    Returns default changelog filename for specfied user.
    """
    return "%s.changes.%s.csv" % (get_settings_filename(), name)


def add_user(name, email=None, meta=None):
    """
    Adds a user to the system.
    """
    global _lock
    if has_user(name):
        raise SystemError("User %s already exists" % name)
    with _lock:
        if not email:
            email = "%s@%s" % (name, get_domain())
        user = {
            "email": email,
            "changelog": get_default_user_changelog_filename(name)
        }
        set_setting("accounts", "users", name, user, meta=meta)
    

def get_user_email(name):
    """
    Returns a user's email
    """
    return get_setting("accounts", "users", name, "email")


def set_user_email(name, email, meta={}):
    """
    Sets a user's email.
    """
    global _lock
    with _lock:
        set_setting("accounts", "users", name, "email", email, meta=meta)
    _log_change(name, ("email", email), meta=meta)


def get_user_min_value(name):
    """
    Returns the minimum account value before transfer starts throwing
    InsufficientBalance exceptions.
    """
    return get_setting("accounts", "users", name, "min_value", default=-0.001)


def set_user_min_value(name, value, meta={}):
    """
    Sets the minimum account value.
    """
    global _lock
    with _lock:
        set_setting("accounts", "users", name, "min_value", value, meta=meta)


def get_user_min_value_asset(name):
    """
    Returns the asset in which the minimum balance requirement is calculated
    against.
    """
    return get_setting("accounts", "users", name, "min_value_asset", default="BTC")


def set_user_min_value_asset(name, asset, meta={}):
    """
    Sets the minimum value asset.
    """
    global _lock
    with _lock:
        set_setting("accounts", "users", name, "min_value_asset", asset, meta=meta)

        
def get_assets(name):
    """
    Lists all assets for which the specified user has a
    known balance.
    """
    return [i for i in _get_balances(name)]


def get_balance(name, asset):
    """
    Gets the balance for an asset held by the specified user.
    """
    return get_setting("accounts", "users", name, "balances", asset, "amount", default=0.0)


_set_balance_callbacks_lock = threading.RLock()
_pre_set_balance_callbacks = {}
_post_set_balance_callbacks = {}

def has_pre_set_balance_callback(name):
    with _set_balance_callbacks_lock:
        return name in _pre_set_balance_callbacks

def has_post_set_balance_callback(name):
    with _set_balance_callbacks_lock:
        return name in _post_set_balance_callbacks

def add_pre_set_balance_callback(name, call):
    global _set_balance_callbacks_lock
    global _pre_set_balance_callbacks
    with _set_balance_callbacks_lock:
        _pre_set_balance_callbacks[name] = call

def del_pre_set_balance_callback(name):
    global _set_balance_callbacks_lock
    global _pre_set_balance_callbacks
    with _set_balance_callbacks_lock:
        del _pre_set_balance_callbacks[name]


def add_post_set_balance_callback(name, call):
    global _set_balance_callbacks_lock
    global _post_set_balance_callbacks
    with _set_balance_callbacks_lock:
        _post_set_balance_callbacks[name] = call


def del_post_set_balance_callback(name):
    global _set_balance_callbacks_lock
    global _post_set_balance_callbacks
    with _set_balance_callbacks_lock:
        del _post_set_balance_callbacks[name]

        
def set_balance(name, asset, amount, cur_time=None, meta={}):
    """
    Sets the balance for an asset held by the specified user.
    """
    global _lock
    with _set_balance_callbacks_lock:
        for key, call in _pre_set_balance_callbacks.iteritems():
            call(name, asset, amount, cur_time, meta)
    with _lock:
        set_setting("accounts", "users", name, "balances", asset, "amount", float(amount))
    if not cur_time:
        cur_time = time.time()
    _log_change(name, ("set_balance", asset, amount), cur_time, meta)
    with _set_balance_callbacks_lock:
        for key, call in _post_set_balance_callbacks.iteritems():
            call(name, asset, amount, cur_time, meta)


def inc_balance(name, asset, amount, cur_time=None, meta={}):
    """
    Incrememnt balance of asset held by the named user by the spcified amount.
    """
    bal = 0.0
    meta.update({"type": "inc_balance"})
    with _lock:
        bal = get_balance(name, asset)
        bal += amount
        set_balance(name, asset, bal, cur_time, meta)
    return bal


def dec_balance(name, asset, amount, cur_time=None, meta={}):
    """
    Decrement balance of asset held by the named user by the spcified amount.
    """
    bal = 0.0
    meta.update({"type": "dec_balance"})
    with _lock:
        bal = get_balance(name, asset)
        bal -= amount
        set_balance(name, asset, bal, cur_time, meta)
    return bal


def get_metadata(name):
    """
    Returns the user metadata.
    """
    return get_setting("accounts", "users", name, "meta", default={})
    

def get_metadata_value(name, key):
    """
    Returns the user metadata value for the specified key.
    """
    return get_setting("accounts", "users", name, "meta", key)


def set_metadata_value(name, key, value, meta=None):
    """
    Returns the user metadata value for the specified key.
    """
    global _lock
    with _lock:
        set_setting("accounts", "users", name, "meta", key, value, meta=meta)
        _log_change(name, ("metadata", key, value), meta)
    

def get_user_changelog(name):
    """
    Returns the filename used for the spcified user's changelog
    """
    default = get_default_user_changelog_filename(name)
    return get_setting("accounts", "users", name, "changelog", default=default)


def set_user_changelog(name, changelog, meta=None):
    """
    Sets the user's changelog filename.
    """
    global _lock
    with _lock:
        # log first to record the change in the old changelog
        _log_change(name, ("changelog", changelog), meta)
        set_setting("accounts", "users", name, "changelog", changelog, meta=meta)
    

def get_user_ledger_name(name, asset):
    """
    Gets a user's csv ledger file name.
    """
    default = "%s.ledger.%s.%s.csv" % (get_settings_filename(), asset, name)
    return get_setting("accounts", "users", name, "balances", asset, "ledger", default=default)


def _credit(cur_time, name, account, asset, amount, meta={}):
    """
    Adds a credit entry in the ledger for the named user
    against another user account for the specified asset
    and amount.
    """
    new_amount = inc_balance(name, asset, float(amount), cur_time, meta)
    # append to ledger csv    
    fields=[cur_time, account, 0.0, float(amount), new_amount, meta]
    append_record(get_user_ledger_name(name, asset), fields)


def _debit(cur_time, name, account, asset, amount, meta={}):
    """
    Adds a debit entry in the ledger for the named user
    against another user account for the specified asset
    and amount.
    """
    new_amount = dec_balance(name, asset, float(amount), cur_time, meta)    
    # append to ledger csv
    fields=[cur_time, account, float(amount), 0.0, new_amount, meta]
    append_record(get_user_ledger_name(name, asset), fields)
    

def get_transfer_logfile_name():
    """
    Gets the transfer logfile name.
    """
    return get_settings_option("accounts_transfer_log", "%s.transfers.csv" % get_settings_filename())


def set_transfer_logfile_name(name):
    """
    Sets the transfer logfile name.
    """
    set_option("accounts_transfer_log", name)

    
# Only one thread can do a transaction at any given time.
def transfer(from_user, to_user, asset, amount,
             cur_time=None, meta={}):
    """
    Subtracts the specified amount from the from_user account's
    balance of the specified asset and adds it to the to_user
    account's balance of that asset.
    """
    global _lock
    
    if not cur_time:
        cur_time = time.time()

    with _lock:
        from_balance = get_balance(from_user, asset)
        #from_user_min_value = get_user_min_value(from_user)
        #from_user_min_value_asset = get_user_min_value_asset(from_user)
        #from_balance_in_min_val_asset = get_price(amount, asset, from_user_min_value_asset)

        if from_balance - amount < 0.0:
            raise InsufficientBalance(from_user, to_user, asset, amount, meta)
        
        # double accounting
        _credit(cur_time, to_user, from_user, asset, amount, meta)
        _debit(cur_time, from_user, to_user, asset, amount, meta)

        # append to transfers log csv
        fields=[cur_time, from_user, to_user, asset, float(amount), meta]
        append_record(get_transfer_logfile_name(), fields)    
