from rest_framework.throttling import SimpleRateThrottle


class SearchSuggestionsPerMinuteThrottle(SimpleRateThrottle):
    scope = "search_suggestions_per_minute"
    rate = "50/min"

    def get_cache_key(self, key, *args, **kwargs):
        return f"perMinuteSearchSuggestions{hash(key)}"


class GeocodePerMinuteThrottle(SimpleRateThrottle):
    scope = "geocode_per_minute"
    rate = "5/min"

    def get_cache_key(self, key, *args, **kwargs):
        return f"perMinuteGeocoding{hash(key)}"


class SearchSuggestionsPerDayThrottle(SimpleRateThrottle):
    scope = "search_suggestions_per_day"
    rate = "250/day"

    def get_cache_key(self, key, *args, **kwargs):
        return f"dailySearchSuggestions{hash(key)}"


class GeocodePerDayThrottle(SimpleRateThrottle):
    scope = "geocode_per_day"
    rate = "50/day"

    def get_cache_key(self, key, *args, **kwargs):
        return f"dailyGeocoding{hash(key)}"


class ReverseGeocodePerMinuteThrottle(SimpleRateThrottle):
    scope = "reverse_geocode_per_minute"
    rate = "10/min"

    def get_cache_key(self, key, *args, **kwargs):
        return f"perMinuteReverseGeocoding{hash(key)}"


class ReverseGeocodePerDayThrottle(SimpleRateThrottle):
    scope = "reverse_geocode_per_day"
    rate = "100/day"

    def get_cache_key(self, key, *args, **kwargs):
        return f"dailyReverseGeocoding{hash(key)}"
