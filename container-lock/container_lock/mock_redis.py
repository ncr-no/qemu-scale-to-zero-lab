class MockRedis:
    def __init__(self, *args, **kwargs):
        self._data = {}
        self._sets = {}

    def get(self, key):
        v = self._data.get(key)
        return v.encode() if isinstance(v, str) else v

    def setex(self, key, ttl, value):
        self._data[key] = value
        return True

    def delete(self, key):
        if key in self._data:
            del self._data[key]
            return True
        return False

    def sadd(self, key, member):
        if key not in self._sets:
            self._sets[key] = set()
        self._sets[key].add(member)
        return True

    def srem(self, key, member):
        if key in self._sets and member in self._sets[key]:
            self._sets[key].remove(member)
            return True
        return False

    def smembers(self, key):
        return {m.encode() if isinstance(m, str) else m for m in self._sets.get(key, set())}

    def scan_iter(self, pattern):
        import re
        # Convert redis pattern to regex
        regex = re.compile('^' + pattern.replace('*', '.*') + '$')
        for key in list(self._data.keys()):
            if regex.match(key):
                yield key.encode() if isinstance(key, str) else key
