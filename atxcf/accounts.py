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

def _append_csv_row(csv_filename, fields):
    """
    Appends row to specified csv file. 'fields' should be
    a list.
    """
    with open(csv_filename, 'ab') as f:
        writer = csv.writer(f)
        writer.writerow(fields)


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


def get_default_user_changelog_filename(name):
    """
    Returns default changelog filename for specfied user.
    """
    return "changes.%s.csv" % name


def add_user(name, email):
    """
    Adds a user to the system.
    """
    global _accounts
    if not has_user(name):
        user = {
            "email": email,
            "metadata": {},
            "balances": {},
            "changelog": get_default_user_changelog_filename(name)
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
    if not "metadata" in _accounts[name]:
        _accounts[name]["metadata"] = {}
    if not "balances" in _accounts[name]:
        _accounts[name]["balances"] = {}
    if not "changelog" in _accounts[name]:
        _accounts[name]["changelog"] = get_default_user_changelog_filename(name)


# serial number for every log entry in the system. Every new log entry
# represents some atomic change to a user account in the system.
_log_id = 0

def _log_change(name, item, cur_time=None):
    """
    Adds a change to the specified user's changelog
    """
    global _log_id
    if not cur_time:
        cur_time = time.time()
    fields = [cur_time, _log_id, name, item]
    log_filename = get_user_changelog(name)
    _append_csv_row(log_filename, fields)
    _log_id += 1
    

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
    _log_change(name, ("email", email))
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

        
def get_assets(name):
    """
    Lists all assets for which the specified user has a
    known balance.
    """
    global _accounts
    _check_user(name)
    return [i for i in _accounts[name]["balances"]]


def get_balance(name, asset):
    """
    Gets the balance for an asset held by the specified user.
    """
    global _accounts
    _check_asset(name, asset)
    return float(_accounts[name]["balances"][asset]["amount"])


def set_balance(name, asset, amount, do_sync=True, cur_time=None):
    """
    Sets the balance for an asset held by the specified user.
    """
    global _accounts
    _check_asset(name, asset)
    _accounts[name]["balances"][asset]["amount"] = float(amount)
    if not cur_time:
        cur_time = time.time()
    _log_change(name, ("balances", asset, amount), cur_time)
    if do_sync:
        sync_account_settings()


def get_metadata(name):
    """
    Returns the metadata field for the specified user.
    """
    global _accounts
    _check_user(name)
    return _accounts[name]["metadata"]


def set_metadata(name, meta):
    """
    Sets the metadata field for the specified user.
    """
    global _accounts
    _check_user(name)
    _accounts[name]["metadata"] = meta
    _log_change(name, ("metadata", meta))
    sync_account_settings()


def get_user_changelog(name):
    """
    Returns the filename used for the spcified user's changelog
    """
    _check_user(name)
    return _accounts[name]["changelog"]


def set_user_changelog(name, changelog):
    """
    Sets the user's changelog filename.
    """
    _check_user(name)
    # log first to record the change in the old changelog
    _log_change(name, ("changelog", changelog))
    _accounts[name]["changelog"] = changelog
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
    new_amount = get_balance(name, asset) + float(amount)
    set_balance(name, asset, new_amount, False, cur_time)

    # append to ledger csv    
    fields=[cur_time, account, 0.0, float(amount), new_amount]
    _append_csv_row(get_user_ledger_name(name, asset), fields)

    if do_sync:
        sync_account_settings()


def _debit(cur_time, name, account, asset, amount, do_sync=False):
    """
    Adds a debit entry in the ledger for the named user
    against another user account for the specified asset
    and amount.
    """
    global _accounts
    new_amount = get_balance(name, asset) - float(amount)
    set_balance(name, asset, new_amount, False, cur_time)    

    # append to ledger csv
    fields=[cur_time, account, float(amount), 0.0, new_amount]
    _append_csv_row(get_user_ledger_name(name, asset), fields)

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
    _append_csv_row(get_transfer_logfile_name(), fields)

    if do_sync:
        sync_account_settings()
    
