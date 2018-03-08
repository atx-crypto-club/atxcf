# -*- coding: utf-8 -*-
"""
Core module for the atxcf agent bot.
"""

import os
import os.path
import json
from json import dumps
import filelock
import time
import threading
import copy
import csv
from collections import defaultdict


def append_record(csv_filename, fields):
    """
    Appends record to specified csv file. 'fields' should be
    a list.
    """
    with open(csv_filename, 'ab') as f:
        writer = csv.writer(f)
        writer.writerow(fields)


def _log_setting(fields):
    """
    Writes a record denoted by 'fields' to the settings log.
    Used to log settings changes.
    """
    append_record(get_settingslog_filename(), fields)


def _log_error(fields):
    """
    Writes a record denoted by 'fields' to the error log.
    Used to log various errors.
    """
    append_record(get_errorlog_filename(), fields)


class SettingsError(RuntimeError):
    pass


_js_settings_filename = None
_js_settings = {}
_js_settings_ts = 0
_js_settings_lock = threading.RLock()
_prevent_write = False

# This dictionary stores the callables that are
# invoked when a setting is changed.
_settings_change_callbacks = defaultdict(lambda: defaultdict(list))


def _args_list_key(args):
    """
    Produces a key for a specifed settings path args
    """
    return "|".join([str(arg) for arg in args])


def add_settings_change_callback(*args, **kwargs):
    """
    Use this to set a change callback.
    TODO: write more about this
    """
    global _settings_change_callbacks
    global _js_settings_lock

    if len(args) < 1:
        raise SettingsError("Invalid number of arguments to add_settings_change_callback")

    name = "default"
    if "name" in kwargs:
        name = kwargs["name"]

    args_key = _args_list_key(args[:-1])
    args_cb = args[-1]
    if not callable(args_cb):
        raise SettingError("Missing callable argument to add_settings_change_callback")
    
    with _js_settings_lock:
        _settings_change_callbacks[args_key][name].append(args_cb)
    return args_key # might be useful to return this
        

def remove_settings_change_callback(*args, **kwargs):
    """
    Use this to remove a change callback.
    TODO: write more...
    """
    global _settings_change_callbacks
    global _js_settings_lock

    name = "default"
    if "name" in kwargs:
        name = kwargs["name"]

    args_key = ""
    if len(args) > 0:
        args_key = _args_list_key(args)
    with _js_settings_lock:
        del _settings_change_callbacks[args_key][name]
    return args_key


def get_settings_change_callbacks(*args, **kwargs):
    """
    Returns the list of callbacks for the specified setting
    arguments.
    """
    global _settings_change_callbacks
    global _js_settings_lock

    prefix = "default"
    if "prefix" in kwargs:
        prefix = kwargs["prefix"]

    args_key = ""
    if len(args) > 0:
        args_key = _args_list_key(args)
    cbs = []
    with _js_settings_lock:
        for name, callbacks in _settings_change_callbacks[args_key]:
            if name.startswith(prefix):
                for cb in callbacks:
                    cbs.append(cb) # TODO: clean this up
    return cbs


def _invoke_callbacks(*args, **kwargs):
    global _settings_change_callbacks
    global _js_settings_lock

    prefix = "default"
    if "prefix" in kwargs:
        prefix = kwargs["prefix"]

    args_key = ""
    if len(args) > 0:
        args_key = _args_list_key(args)

    cbs = []
    with _js_settings_lock:
        for name, callbacks in _settings_change_callbacks[args_key]:
            if name.startswith(prefix):
                for cb in callbacks:
                    cbs.append(cb) # TODO: clean this up
    for cb in cbs:
        cb()


def _invoke_pre_change_callbacks(*args):
    _invoke_callbacks(*args, prefix="__pre__")

    
def _invoke_post_change_callbacks(*args):
    _invoke_callbacks(*args, prefix="__post__")


def add_settings_pre_change_callback(*args, **kwargs):
    """
    Use this to add a pre change callback. Adds a '__pre__' prefix
    to the name keyword argument.
    """
    name = "default"
    if "name" in kwargs:
        name = kwargs["name"]
    new_name = "__pre__"+name
    return add_settings_change_callback(*args, name=new_name)


def add_settings_post_change_callback(*args, **kwargs):
    """
    Use this to add a post change callback. Adds a '__post__' prefix
    to the name keyword argument.
    """
    name = "default"
    if "name" in kwargs:
        name = kwargs["name"]
    new_name = "__post__"+name
    return add_settings_change_callback(*args, name=new_name)


def remove_settings_pre_change_callback(*args, **kwargs):
    """
    Use this to remove a pre change callback list. Adds a '__pre__' prefix
    to the name keyword argument.
    """
    name = "default"
    if "name" in kwargs:
        name = kwargs["name"]
    new_name = "__pre__"+name
    return remove_settings_change_callback(*args, name=new_name)


def remove_settings_post_change_callback(*args, **kwargs):
    """
    Use this to remove a post change callback list. Adds a '__post__' prefix
    to the name keyword argument.
    """
    name = "default"
    if "name" in kwargs:
        name = kwargs["name"]
    new_name = "__post__"+name
    return remove_settings_change_callback(*args, name=new_name)


def get_settings_filename():
    global _js_settings_lock
    global _js_settings_filename

    if not _js_settings_filename:
        with _js_settings_lock:
            varname = "ATXCF_SETTINGS"
            if varname in os.environ:
                set_settings_filename(os.environ[varname])
            else:
                set_settings_filename("atxcf.json")
    return _js_settings_filename


def set_settings_filename(filename):
    global _js_settings_filename
    if not os.path.isabs(filename):
        filename = os.path.join(os.getcwd(), filename)
    _js_settings_filename = filename


def _get_settings_lockfile_name():
    return get_settings_filename() + ".lock"

    
_js_filelock = filelock.FileLock(_get_settings_lockfile_name())


_settings_log = None
def init_settings():
    """
    Initializes settings dict with default values.
    """
    global _js_settings
    global _js_settings_ts
    global _js_settings_lock
    with _js_settings_lock:
        cur_time = time.time()
        _js_settings = {
            "program_url": "https://gitlab.catx.io/catx/atxcf",
            "version": "0.1",
            "last_modified": cur_time,
            "options": {},
            "credentials": {}
        }
        _js_settings_ts = cur_time


def _get_settings():
    """
    Returns the current settings dict. If there isn't one, then 
    it loads it from disk.
    """
    global _js_settings
    global _js_settings_lock
    global _js_filelock
    doInit = False
    fn = get_settings_filename()
    with _js_settings_lock:
        if not _js_settings:
            # if a settings file doesn't exist, just init with defaults
            if not os.path.isfile(fn):
                doInit = True
            else:
                with _js_filelock:
                    try:
                        _js_settings = json.load(open(fn))
                        _js_settings_ts = get_last_modified(fn)
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
    global _js_settings_ts
    global _js_settings_lock
    if len(args) < 1:
        raise SettingsError("Invalid number of arguments to get_setting")
    default = None
    if "default" in kwargs:
        default = kwargs["default"]
    meta = None
    if "meta" in kwargs:
        meta = kwargs["meta"]
    do_set = False
    with _js_settings_lock:
        sett = _get_settings()
        for arg in args[:-1]:
            if not arg in sett:
                sett[arg] = {}
            next_sett = sett[arg]
            sett = next_sett
        if not args[-1] in sett:
            if default == None:
                return None
            do_set = True
        if not do_set:
            return copy.deepcopy(sett[args[-1]])

    local_args = list(args)
    local_args.append(default)
    set_setting(*local_args, **kwargs)
    # try it again, should succeed this time.
    return get_setting(*args, **kwargs)

    
def has_setting(*args, **kwargs):
    """
    Returns whether there exists a setting with the specified path.
    """
    if not "default" in kwargs:
        kwargs["default"] = None
    return not get_setting(*args, **kwargs) is None

    
def get_settingslog_filename():
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
    global _js_settings_ts
    global _js_settings_lock
    with _js_settings_lock:
        _js_settings.update(new_settings)
        _js_settings_ts = time.time()


def set_settings(new_settings):
    """
    Deprecated.
    """
    _set_settings(new_settings)
    

def set_setting(*args, **kwargs):
    """
    Use this to set a program setting in a thread safe way.
    """
    global _js_settings_ts
    global _js_settings_lock
    if len(args) < 2:
        raise SettingsError("Invalid number of arguments to set_setting")
    _invoke_pre_change_callbacks(*args)
    with _js_settings_lock:
        sett = _get_settings()
        for arg in args[:-2]:
            if not arg in sett:
                sett[arg] = {}
            next_sett = sett[arg]
            sett = next_sett
        sett[args[-2]] = args[-1]
        _js_settings_ts = time.time()
    _invoke_post_change_callbacks(*args)
    meta = None
    if "meta" in kwargs:
        meta = kwargs["meta"]
    _log_setting([_js_settings_ts] + list(args) + [dumps(meta)])
            

def remove_setting(*args, **kwargs):
    """
    Removes a setting entry in the settings dict.
    """
    global _js_settings_ts
    global _js_settings_lock
    if len(args) < 1:
        raise SettingsError("Invalid number of arguments to remove_setting")
    meta = None
    if "meta" in kwargs:
        meta = kwargs["meta"]
    with _js_settings_lock:
        sett = _get_settings()
        for arg in args[:-1]:
            if not arg in sett:
                sett[arg] = {}
            next_sett = sett[arg]
            sett = next_sett
        del sett[args[-1]]
        _js_settings_ts = time.time()
        _log_setting([_js_settings_ts] + list(args) + [dumps(meta)])

    
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
    """
    Writes the settings dict to disk.
    """
    global _js_filelock
    global _js_settings_ts
    global _js_settings_lock
    global _prevent_write
    if _prevent_write:
        return

    fn = get_settings_filename()
    if _js_settings_ts <= get_last_modified(fn):
        return
    
    set_setting("last_modified", _js_settings_ts)
    with _js_settings_lock:
        with _js_filelock:
            try:
                with open(fn, 'w') as f:
                    json.dump(_get_settings(), f, sort_keys=True,
                              indent=4, separators=(',', ': '))
            except IOError as e:
                raise SettingsError("Error writing %s: %s" % (fn, e.message))
    _js_settings_ts = get_last_modified(fn)


def get_option(option, default=None):
    """
    Returns an option from the option settings section.
    """
    return get_setting("options", option, default=default)


def has_option(option):
    """
    Returns whether an option exists
    """
    return has_setting("options", option)


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
    remove_setting("options", option)


def get_settings_option(option_name, default=None):
    """
    Convenience function to get an option and set a
    default if it doesn't exist.
    """
    return get_setting("options", option_name, default=default)


def get_errorlog_filename():
    """
    Returns the errorlog filename.
    """
    return get_option("errorlog", default="errorlog.csv")


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
    remove_setting("credentials", site)


def has_creds(site):
    """
    Returns whether a site has credentials in the settings file
    """
    return has_setting("credentials", site)


def get_all_creds():
    """
    Returns the whole credentials section.
    """
    return get_setting("credentials")


def get_last_modified(filename=get_settings_filename()):
    """
    Returns the time the settings file was last updated.
    """
    if not os.path.isfile(filename):
        return 0
    statbuf = os.stat(filename)
    return statbuf.st_mtime


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
    global _js_settings
    global _js_settings_ts
    global _js_settings_lock
    
    while True:
        interval = get_option("settings_update_interval", default=60)
        time.sleep(float(interval))

        if not _js_settings:
            init_settings()

        settings_filename = get_settings_filename()
        file_js_settings_ts = get_last_modified(settings_filename)

        # If the update time is the same, do nothing
        if file_js_settings_ts == _js_settings_ts:
            continue

        # If it is newer, lets use those settings for this
        # process. If not, lets overwrite the file with
        # our settings.
        try:
            if file_js_settings_ts > _js_settings_ts:
                print file_js_settings_ts, _js_settings_ts
                print "_sync_settings: using newer settings from file", settings_filename
                with open(settings_filename, 'r') as f:
                    with _js_settings_lock:
                        _js_settings = json.load(f)
                        _js_settings_ts = file_js_settings_ts
        finally:
            write_settings()

get_settings()
_js_sync_thread = threading.Thread(target=_sync_settings)
_js_sync_thread.daemon = True
_js_sync_thread.start()
