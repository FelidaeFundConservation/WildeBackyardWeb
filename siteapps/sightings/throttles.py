# Licensed under the MIT License.
# See LICENSE file in the project root for full license information.

from rest_framework.throttling import SimpleRateThrottle


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
