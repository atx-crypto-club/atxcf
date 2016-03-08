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


class SettingsError(RuntimeError):
    pass


_js_settings = {}
_js_settings_lock = threading.RLock()


def _get_settings_filename():
    varname = "ATXCF_SETTINGS"
    if varname in os.environ:
        return os.environ[varname]
    else:
        return "atxcf.json"


def _get_settings_lockfile_name():
    return '.' + _get_settings_filename() + ".lock"

    
_js_filelock = filelock.FileLock(_get_settings_lockfile_name())


def get_default_options():
    """
    Default atxcf bot runtime options.
    """
    return {
        # limit price updates to 60 second intervals
        "price_update_interval": 60,
        # try to keep the settings file synced every 5 minutes
        "settings_update_interval": 60*5
    }


def init_settings():
    """
    Initializes settings dict with default values.
    """
    global _js_settings
    global _js_settings_lock
    with _js_settings_lock:
        _js_settings = {
            "program_url": "https://github.com/transfix/atxcf",
            "version": "0.1",
            "last_updated": 0.0,
            "options": get_default_options(),
            "credentials": {},
            "market_data": {}
        }
        return _js_settings


def _check_options_section(settings):
    """
    Raises an exception if the options section is missing.
    """
    if not "options" in settings:
        raise SettingsError("Missing options section in %s" % _get_settings_filename())


def get_settings():
    """
    Returns the current settings dict. If there isn't one, then 
    it loads it from disk.
    """
    global _js_settings
    global _js_settings_lock
    global _js_filelock
    with _js_settings_lock:
        if not _js_settings:
            fn = _get_settings_filename()
            # if a settings file doesn't exist, just init with defaults
            if not os.path.isfile(fn):
                _js_settings = init_settings()
            else:
                with _js_filelock:
                    try:
                        _js_settings = json.load(open(fn))
                    except IOError as e:
                        raise SettingsError("Error loading %s: %s" % (fn, e.message))
        return _js_settings


def set_settings(new_settings):
    """
    Replaces the settings dict with the input.
    """
    global _js_settings
    global _js_settings_lock
    if not isinstance(new_settings, dict):
        raise SettingsError("invalid settings argument")
    with _js_settings_lock:
        _js_settings.update(new_settings)


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
    settings = get_settings()
    settings["last_updated"] = time.time()
    with _js_filelock:
        fn = _get_settings_filename()
        try:
            with open(fn, 'w') as f:
                json.dump(settings, f)
        except IOError as e:
            raise SettingsError("Error writing %s: %s" % (fn, e.message))


def get_option(option):
    """
    Returns an option from the option settings section.
    """
    settings = get_settings()
    _check_options_section(settings)
    if not option in settings["options"]:
        raise SettingsError("No such option %s in %s" % (option, _get_settings_filename()))
    return settings["options"][option]


def set_option(option, value):
    """
    Sets an option with the specified value in the options section.
    """
    settings = get_settings()
    _check_options_section(settings)
    settings["options"][option] = value
    set_settings(settings)


def get_options():
    """
    Returns the whole options section.
    """
    settings = get_settings()
    _check_options_section(settings)
    return settings["options"]


def remove_option(option):
    """
    Removes an option from the options section.
    """
    settings = get_settings()
    _check_options_section(settings)
    if not option in settings["options"]:
        raise SettingsError("Missing option %s in %s" % (option, _get_settings_filename()))
    del settings["options"][option]
    set_settings(settings)


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
    settings = get_settings()
    _check_credentials_section(settings)
    if not site in settings["credentials"]:
        raise SettingsError("No such site %s in credentials" % site)
    key = settings["credentials"][site]["key"]
    secret = settings["credentials"][site]["secret"]
    return (key, secret)


def set_creds(site, key, secret):
    """
    Sets the API key, secret pair for specified site.
    """
    settings = get_settings()
    _check_credentials_section(settings)
    site_creds = {
        "key": str(key),
        "secret": str(secret)
    }
    settings["credentials"][site] = site_creds
    set_settings(settings)


def remove_creds(site):
    """
    Removes the credentials for the site specified.
    """
    settings = get_settings()
    _check_credentials_section(settings)
    if not site in settings["credentials"]:
        raise SettingsError("No such site %s in credentials" % site)
    del settings["credentials"][site]
    set_settings(settings)


def get_all_creds():
    """
    Returns the whole credentials section.
    """
    settings = get_settings()
    _check_credentials_section(settings)
    return settings["credentials"]


def get_last_updated():
    """
    Returns the value of the last_updated field, which is
    the last time the settings file was written.
    """
    settings = get_settings()
    if not "last_updated" in settings:
        raise SettingsError("Missing last_updated field in %s" % _get_settings_filename())
    return settings["last_updated"]
    

import atexit
atexit.register(write_settings)
