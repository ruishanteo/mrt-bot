# Credits: https://github.com/cheeaun/railrouter-sg
import json
import logging
import sys
import time
from contextlib import closing

try:
    from typing import Any  # Python 3.5 or later required
except ImportError:
    pass

try:
    import urllib.parse as parse
    import urllib.request as request
except ImportError:
    import urllib as parse
    import urllib2 as request

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

REFERER = "http://journey.smrt.com.sg/journey/station_info/"  


def _is_str_or_unicode(s):  # type: (Any) -> bool
    """Check if `s` is str type in both Python 2 and 3, else if it is
    unicode type in Python 2.

    Args:
        s (Any): Argument to be checked.

    Returns:
        bool: True if `s` is str or unicode type.
    """
    if isinstance(s, str):
        return True
    is_python2 = sys.version_info[0] == 2
    return is_python2 and type(s).__name__ == "unicode"


def _get(url, params=None):  # type: (str, dict[str, str] | None) ->  str
    """Make a GET request to `url` with optional query parameters `params`.

    Return the body as a string if it is a valid JSON string, otherwise {}.

    Args:
        url (str): Target URL.
        params (dict[str, str], optional): Optional query parameters. Defaults to None.

    Returns:
        str: GET request body.
    """
    if params:
        r = request.Request(url + "?" + parse.urlencode(params))
    else:
        r = request.Request(url)
    r.add_header("Referer", REFERER)

    try:
        with closing(request.urlopen(r, timeout=60)) as f:
            status_code = f.status if hasattr(f, "status") else f.getcode()
            if status_code == 200:
                data = f.read().decode("utf-8")
                _ = json.loads(data)  # Validate JSON string.
                return data
            raise Exception(status_code)
    except Exception as e:
        logger.error(e)
        return "{}"


def get_all_station_info():  # type: () -> str
    """Get all train station information from SMRT API.

    Returns:
        str: Train station information as JSON string.
    """
    return _get("https://connect.smrt.wwprojects.com/smrt/api/stations")


def get_all_station_names():  # type: () -> list[str]
    """Get all train station names from SMRT API.

    Returns:
        list[str]: List of train station names in ascending alphabetical order.
    """
    all_stations_info = json.loads(get_all_station_info())  # type: dict
    if not isinstance(all_stations_info, dict):
        all_stations_info = {}

    results = all_stations_info.get("results", [])
    if not isinstance(results, list):
        return []
    station_names = set()

    for station_info in results:
        if isinstance(station_info, dict) and "name" in station_info:
            station_name = station_info[
                "name"
            ]  # Use station name to get its arrival timings
            if _is_str_or_unicode(station_name) and station_name:
                station_names.add(station_name)
    return sorted(station_names)
