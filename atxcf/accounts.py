from settings import get_settings_option, get_settings, set_settings


# TODO:
# - csv logging for every mutation and transfer
# - csv ledger for every user for double accounting across the system.
# - thread safety

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
    

def _sync_account_settings():
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
            "email": email
        }
        _accounts[name] = user
        _sync_account_settings()
    else:
        raise SystemError("User %s already exists" % name)


def get_user_email(name):
    """
    Returns a user's email
    """
    if not has_user(name):
        return None
    return _accounts[name]["email"]


def set_user_email(name, email):
    """
    Sets a user's email.
    """
    global _accounts
    if not has_user(name):
        raise SystemError("No such user %s" % name)
    _accounts[name]["email"] = email
    _sync_account_settings()


def _init_user_balances(name):
    global _accounts
    if not has_user(name):
        raise SystemError("User % doesn't exist")
    if not "balances" in _accounts[name]:
        _accounts[name]["balances"] = {}


def get_balance(name, asset):
    """
    Gets the balance for an asset held by the specified user.
    """
    global _accounts
    _init_user_balances(name)
    if not asset in _accounts[name]["balances"]:
        _accounts[name]["balances"][asset] = 0.0
    return float(_accounts[name]["balances"][asset])


def _set_balance(name, asset, amount, do_sync=True):
    """
    Sets the balance for an asset held by the specified user.
    """
    global _accounts
    _init_user_balances(name)
    _accounts[name]["balances"][asset] = float(amount)
    if do_sync:
        _sync_account_settings()


def transfer(from_user, to_user, asset, amount):
    """
    Subtracts the specified amount from the from_user account's
    balance of the specified asset and adds it to the to_user
    account's balance of that asset.
    """
    from_user_amount = get_balance(from_user, asset) - amount
    _set_balance(from_user, asset, from_user_amount, False)
    to_user_amount = get_balance(to_user, asset) + amount
    _set_balance(to_user, asset, to_user_amount, False)
    _sync_account_settings()
