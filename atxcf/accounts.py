# handles double entry accounting for accounts on the system.

import csv
import time

from settings import (
    get_settings_option, get_settings, set_settings, set_option
)

# TODO:
# - csv logging for every mutation and transfer
# - thread safety
# - atomic mutation

_accounts = None
def _init_accounts_dict():
    """
    Initializes the accounts dict from the settings.
    """
    global _accounts
    if not _accounts:
        sett = get_settings()
        if "accounts" in sett:
            _accounts = sett["accounts"]
        else:
            _accounts = {}
    

def sync_account_settings():
    """
    sets the settings section for the account dict.
    """
    sett = get_settings()
    sett["accounts"] = _accounts
    set_settings(sett)

            
def number_of_users():
    """
    Returns the number of users known to the system.
    """
    _init_accounts_dict()
    return len(_accounts)


def get_users():
    """
    Returns the user names of all in the system
    """
    _init_accounts_dict()    
    return [name for name in _accounts]


def has_user(name):
    """
    Returns a boolean whether the user is known to the system.
    """
    _init_accounts_dict()
    return name in _accounts


def add_user(name, email):
    """
    Adds a user to the system.
    """
    global _accounts
    if not has_user(name):
        user = {
            "email": email,
            "balances": {}
        }
        _accounts[name] = user
        sync_account_settings()
    else:
        raise SystemError("User %s already exists" % name)

    
def _check_user(name):
    """
    Raises an exception if a user doesn't exist.
    """
    global _accounts
    if not has_user(name):
        raise SystemError("No such user %s" % name)
    if not "balances" in _accounts[name]:
        _accounts[name]["balances"] = {}
    

def get_user_email(name):
    """
    Returns a user's email
    """
    _check_user(name)
    return _accounts[name]["email"]


def set_user_email(name, email):
    """
    Sets a user's email.
    """
    global _accounts
    _check_user(name)
    _accounts[name]["email"] = email
    sync_account_settings()


def _check_asset(name, asset):
    """
    Adds asset info to user balance if not present.
    """
    global _accounts
    _check_user(name)
    if not asset in _accounts[name]["balances"]:
        _accounts[name]["balances"][asset] = {
            "amount": 0.0,
            "ledger": "ledger.%s.%s.csv" % (asset, name)
        }


def get_balance(name, asset):
    """
    Gets the balance for an asset held by the specified user.
    """
    global _accounts
    _check_asset(name, asset)
    return float(_accounts[name]["balances"][asset]["amount"])


def _set_balance(name, asset, amount, do_sync=True):
    """
    Sets the balance for an asset held by the specified user.
    """
    global _accounts
    _check_asset(name, asset)
    _accounts[name]["balances"][asset]["amount"] = float(amount)
    if do_sync:
        sync_account_settings()


def get_user_ledger_name(name, asset):
    """
    Gets a user's csv ledger file name.
    """
    global _accounts
    _check_asset(name, asset)
    return _accounts[name]["balances"][asset]["ledger"]


def _credit(cur_time, name, account, asset, amount, do_sync=False):
    """
    Adds a credit entry in the ledger for the named user
    against another user account for the specified asset
    and amount.
    """
    global _accounts
    new_amount = get_balance(name, asset) + amount
    _set_balance(name, asset, new_amount, False)

    # append to ledger csv
    fields=[cur_time, account, 0.0, float(amount), new_amount]
    with open(get_user_ledger_name(name, asset), 'ab') as f:
        writer = csv.writer(f)
        writer.writerow(fields)

    if do_sync:
        sync_account_settings()


def _debit(cur_time, name, account, asset, amount, do_sync=False):
    """
    Adds a debit entry in the ledger for the named user
    against another user account for the specified asset
    and amount.
    """
    global _accounts
    new_amount = get_balance(name, asset) - amount
    _set_balance(name, asset, new_amount, False)    

    # append to ledger csv
    fields=[cur_time, account, float(amount), 0.0, new_amount]
    with open(get_user_ledger_name(name, asset), 'ab') as f:
        writer = csv.writer(f)
        writer.writerow(fields)

    if do_sync:
        sync_account_settings()
    

def get_transfer_logfile_name():
    """
    Gets the transfer logfile name.
    """
    return get_settings_option("accounts_transfer_log", "transfers.csv")


def set_transfer_logfile_name(name):
    """
    Sets the transfer logfile name.
    """
    set_option("accounts_transfer_log", name)


def transfer(from_user, to_user, asset, amount, cur_time=None, do_sync=True):
    """
    Subtracts the specified amount from the from_user account's
    balance of the specified asset and adds it to the to_user
    account's balance of that asset.
    """
    if not cur_time:
        cur_time = time.time()
    
    # double accounting
    _credit(cur_time, to_user, from_user, asset, amount)
    _debit(cur_time, from_user, to_user, asset, amount)
    
    # append to transfers log csv
    fields=[cur_time, from_user, to_user, asset, float(amount)]
    with open(get_transfer_logfile_name(), 'ab') as f:
        writer = csv.writer(f)
        writer.writerow(fields)

    if do_sync:
        sync_account_settings()
    
