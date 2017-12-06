# TODO: docstrings plz
import time
import threading
import memcached_client
from settings import (
    get_settings, set_settings, get_settings_option, set_option,
    get_setting, set_setting
)

class Cache(object):

    def get_val(self, key):
        return None

    def has_key(self, key):
        return self.get_val(key) != None

    def set_val(self, key, value, expire=None):
        pass


class MemcachedCache(Cache):

    def get_val(self, key):
        return memcached_client.get(key)

    def set_val(self, key, value, expire=None):
        memcached_client.set(key, value, expire)


class SettingsCache(Cache):

    def __init__(self, name="default"):
        self._name = name
        self._cache = self._get_settings_cache()
        self._lock = threading.RLock()

    
    def _get_settings_cache(self):
        return get_setting("cache", self._name, default={})


    def _sync_cache(self):
        with self._lock:
            for key, value in self._cache.iteritems():
                cur_val = get_setting("cache", self._name, key, default=value)
                # update the cache on disk if in memory value is newer
                if cur_val[0] < value[0]:
                    set_setting("cache", self._name, key, value)
                    

    def clear_cache(self):
        set_setting("cache", self._name, {})

        
    def get_val(self, key):
        with self._lock:
          if key in self._cache:
              timeout = time.time() - self._cache[key][0]
              expire = self._cache[key][1]
              if expire > 0 and timeout > expire:
                  return None
              return self._cache[key][2]
          return None

    
    def set_val(self, key, value, expire=None):
        if expire == None:
            expire = 0
        self._cache[key] = (time.time(), expire, value)
        self._sync_cache()


_caches = []
if memcached_client.enabled():
    _caches.append(MemcachedCache())
if get_settings_option("using_settings_cache", True):
    _caches.append(SettingsCache())


def get_val(key):
    global _caches
    for cache in _caches:
        try:
            return cache.get_val(key)
        except:
            pass
    return None


def has_key(key):
    return get_val(key) != None


def set_val(key, value, expire=None):
    global _caches
    for cache in _caches:
        try:
            cache.set_val(key, value, expire)
        except:
            pass

