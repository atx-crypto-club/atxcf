# -*- coding: utf-8 -*-
"""
Settings module for atxcf bot to keep state and cache market data.
"""

import os
import os.path
import json
import filelock
import time
import threading
import copy

from utils import (
    append_csv_row
)

class SettingsError(RuntimeError):
    pass


_js_settings = {}
_js_settings_ts = time.time()
_js_settings_lock = threading.RLock()
_prevent_write = False

def _get_settings_filename():
    varname = "ATXCF_SETTINGS"
    if varname in os.environ:
        return os.environ[varname]
    else:
        return "atxcf.json"


def _get_settings_lockfile_name():
    return _get_settings_filename() + ".lock"

    
_js_filelock = filelock.FileLock(_get_settings_lockfile_name())


def get_default_options():
    """
    Default atxcf bot runtime options.
    """
    return {
        # try to keep the settings file synced every 5 minutes
        "settings_update_interval": 60*5
    }


_settings_log = None
def init_settings():
    """
    Initializes settings dict with default values.
    """
    global _js_settings
    global _js_settings_ts
    global _js_settings_lock
    with _js_settings_lock:
        _js_settings = {
            "program_url": "https://github.com/transfix/atxcf",
            "version": "0.1",
            "last_updated": time.time(),
            "options": get_default_options(),
            "credentials": {}
        }
        _js_settings_ts = time.time()


def _check_options_section(settings):
    """
    Raises an exception if the options section is missing.
    """
    if not "options" in settings:
        raise SettingsError("Missing options section in %s" % _get_settings_filename())
    

def _get_settings():
    """
    Returns the current settings dict. If there isn't one, then 
    it loads it from disk.
    """
    global _js_settings
    global _js_settings_lock
    global _js_filelock
    ret_settings = None
    doInit = False
    with _js_settings_lock:
        if not _js_settings:
            fn = _get_settings_filename()
            # if a settings file doesn't exist, just init with defaults
            if not os.path.isfile(fn):
                doInit = True
            else:
                with _js_filelock:
                    try:
                        _js_settings = json.load(open(fn))
                    except IOError as e:
                        raise SettingsError("Error loading %s: %s" % (fn, e.message))
    if doInit:
        init_settings()
    return _js_settings


def get_settings():
    """
    Deprecated
    """
    return _get_settings()


def get_setting(*args, **kwargs):
    """
    Use this to get settings in a thread safe way.
    Use the keyword argument "default" to assign a default value
    if a setting with the specified name isn't present.
    """
    global _js_settings_lock
    default = None
    if "default" in kwargs:
        default = kwargs["default"]
    with _js_settings_lock:
        sett = _get_settings()
        for arg in args[:-1]:
            if not arg in sett:
                sett[arg] = {}
            next_sett = sett[arg]
            sett = next_sett
        if not args[-1] in sett:
            if default == None:
                raise SettingsError("Missing setting value and no default specified")
            sett[args[-1]] = default
            _js_settings_ts = time.time()
            append_csv_row(get_settings_log(), [_js_settings_ts] + list(args) + [default])
        return copy.deepcopy(sett[args[-1]])
    

def get_settings_log():
    """
    Returns the settings log field.
    """
    global _settings_log
    if not _settings_log:
        _settings_log = get_setting("settings_log", default="settings_log.csv")
    return _settings_log

    
def _set_settings(new_settings):
    """
    Replaces the settings dict with the input.
    """
    global _js_settings
    global _js_settings_lock
    if not isinstance(new_settings, dict):
        raise SettingsError("invalid settings argument")
    with _js_settings_lock:
        _js_settings.update(new_settings)
        _js_settings_ts = time.time()


def set_settings(new_settings):
    """
    Deprecated.
    """
    _set_settings(new_settings)
    

def set_setting(*args):
    """
    Use this to set a program setting in a thread safe way.
    """
    global _js_settings_lock
    if len(args) < 2:
        raise SettingsError("Invalid number of arguments to set_setting")
    with _js_settings_lock:
        sett = _get_settings()
        for arg in args[:-2]:
            if not arg in sett:
                sett[arg] = {}
            next_sett = sett[arg]
            sett = next_sett
        sett[args[-2]] = args[-1]
        _js_settings_ts = time.time()
    append_csv_row(get_settings_log(), [_js_settings_ts] + list(args))
            
        
def reload_settings():
    """
    Forces a reload of the settings dict from disk.
    """
    global _js_settings
    global _js_settings_lock
    with _js_settings_lock:
        _js_settings = {}
    return get_settings()


def write_settings():
    global _js_filelock
    global _js_settings_ts
    global _js_settings_lock
    global _prevent_write
    if _prevent_write:
        return
    settings = _get_settings()
    with _js_settings_lock:
        settings["last_updated"] = _js_settings_ts
    with _js_filelock:
        fn = _get_settings_filename()
        try:
            with open(fn, 'w') as f:
                json.dump(settings, f, sort_keys=True,
                          indent=4, separators=(',', ': '))
        except IOError as e:
            raise SettingsError("Error writing %s: %s" % (fn, e.message))


def get_option(option):
    """
    Returns an option from the option settings section.
    """
    return get_setting("options", option)


def has_option(option):
    """
    Returns whether an option exists
    """
    return option in get_setting("options")


def set_option(option, value):
    """
    Sets an option with the specified value in the options section.
    """
    set_setting("options", option, value)


def get_options():
    """
    Returns the whole options section.
    """
    return get_setting("options")


def remove_option(option):
    """
    Removes an option from the options section.
    """
    global _js_settings_lock
    with _js_settings_lock:
      settings = _get_settings()
      _check_options_section(settings)
      if not option in settings["options"]:
          raise SettingsError("Missing option %s in %s" % (option, _get_settings_filename()))
      del settings["options"][option]
      _set_settings(settings)


def get_settings_option(option_name, default=None):
    """
    Convenience function to get an option and set a
    default if it doesn't exist.
    """
    value = default
    try:
        value = get_option(option_name)
    except SettingsError:
        set_option(option_name, value)
    return value


def _check_credentials_section(settings):
    """
    Raises an exception if the credentials section is missing.
    """
    if not "credentials" in settings:
        raise SettingsError("Missing credentials section in %s" % _get_settings_filename())


def get_creds(site):
    """
    Returns API key, secret pair for specified site.
    """
    creds = get_setting("credentials", site)
    return (creds["key"], creds["secret"])


def set_creds(site, key, secret):
    """
    Sets the API key, secret pair for specified site.
    """
    site_creds = {
        "key": str(key),
        "secret": str(secret)
    }
    set_setting("credentials", site, site_creds)


def remove_creds(site):
    """
    Removes the credentials for the site specified.
    """
    global _js_settings_lock
    with _js_settings_lock:
      settings = _get_settings()
      _check_credentials_section(settings)
      if not site in settings["credentials"]:
          raise SettingsError("No such site %s in credentials" % site)
      del settings["credentials"][site]
      _set_settings(settings)


def has_creds(site):
    """
    Returns whether a site has credentials in the settings file
    """
    global _js_settings_lock
    with _js_settings_lock:
      settings = _get_settings()
      _check_credentials_section(settings)
      if not site in settings["credentials"]:
          return False
      return True


def get_all_creds():
    """
    Returns the whole credentials section.
    """
    return get_setting("credentials")


def get_last_updated():
    """
    Returns the value of the last_updated field, which is
    the last time the settings file was written.
    TODO: return the file modification time from file metadata
    """
    return get_setting("last_updated")


class BlockWrite(object):
    """
    Use this with a 'with' clause to block writing the settings file in case
    you want to make several changes and not have the settings file saved
    in between those changes.
    """
    def __enter__(self):
        global _prevent_write
        _prevent_write = True

    def __exit__(self, type, value, traceback):
        global _prevent_write
        _prevent_write = False
    

import atexit
atexit.register(write_settings)


def _sync_settings():
    while True:
        interval = get_option("settings_update_interval")
        time.sleep(float(interval))

        #print "_sync_settings: writing..."
        write_settings()


get_settings()
_js_sync_thread = threading.Thread(target=_sync_settings)
_js_sync_thread.daemon = True
_js_sync_thread.start()
