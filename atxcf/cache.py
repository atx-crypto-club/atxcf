import memcached_client
from settings import get_settings, set_settings, get_settings_option, set_option

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

    def _init_settings_cache(self):
        sett = get_settings()
        modified = False
        if not "cache" in sett:
            sett["cache"] = {}
            modified = True
        if not self._name in sett["cache"]:
            sett["cache"][self._name] = {}
            modified = True
        if modified:
            set_settings(sett)
    
        
    def _get_settings_cache(self):
        self._init_settings_cache()
        return get_settings()["cache"][self._name]


    def _sync_cache(self):
        sett = get_settings()
        sett["cache"][self._name] = self._cache
        set_settings(sett)
        
        
    def get_val(self, key):
        if key in self._cache:
            return self._cache[key]
        return None

    
    def set_val(self, key, value, expire=None):
        self._cache[key] = value
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

