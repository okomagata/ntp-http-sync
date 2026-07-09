# -*- coding: utf-8 -*-
"""
A script that retrieves server time over HTTP(S) only and corrects the
Windows system clock accordingly.

- Intended for environments where NTP (UDP/123) is blocked by a firewall.
- All communication happens over HTTPS (TCP/443) only.
- Uses only the Python standard library (no pip install required).
- Changing the system time requires administrator privileges
  (the SeSystemtimePrivilege).

About this approach:
    NICT (National Institute of Information and Communications Technology,
    Japan) used to provide a JSON-based time distribution API over
    HTTP/HTTPS, but it was discontinued on March 31, 2022, and time
    distribution is now consolidated to NTP only
    (https://jjy.nict.go.jp/httphttps-index.html).
    Because of that, this script instead uses the "Date:" header returned
    in the HTTP response of any web server as its time source. This is a
    more general-purpose approach; NICT itself used to recommend this same
    technique as a fallback for environments where NTP/SNTP is blocked, so
    it is not affected by the retirement of any single service.
    Note that the Date header only has one-second resolution, so it is
    less precise than NTP.

Usage:
    Open a Command Prompt or PowerShell "as Administrator" and run:
        python ntp_http_sync.py
    Without administrator privileges, the script only reports the clock
    offset and does not actually change the system time.

Corporate proxies:
    urllib automatically picks up Windows proxy settings (Internet
    Options / registry, or the HTTP_PROXY / HTTPS_PROXY environment
    variables). If your proxy requires authentication (username/password),
    you can fill in PROXY_URL / PROXY_USER / PROXY_PASS below directly
    (normally these can be left blank).
"""

import ctypes
import sys
import time
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

# --- Configuration ------------------------------------------------------
# HTTPS sites used as time sources. All are lightweight endpoints; they
# are tried in order, and the script stops at the first successful one.
TIME_SOURCE_URLS = [
    "https://www.google.com/generate_204",   # Google connectivity check (very lightweight response)
    "https://www.gstatic.com/generate_204",  # Same as above, different domain
    "https://cloudflare.com/cdn-cgi/trace",  # Cloudflare connectivity check
    "https://www.microsoft.com/",            # Fallback (heavier response)
]

TIMEOUT_SEC = 5

# Only fill these in if your proxy requires authentication
# (leave blank to use auto-detected settings)
PROXY_URL = ""    # e.g. "http://proxy.example.com:8080"
PROXY_USER = ""   # e.g. "myuser"
PROXY_PASS = ""   # e.g. "mypassword"
# -------------------------------------------------------------------------


def build_opener():
    if PROXY_URL:
        proxy_handler = urllib.request.ProxyHandler(
            {"http": PROXY_URL, "https": PROXY_URL}
        )
        opener = urllib.request.build_opener(proxy_handler)
        if PROXY_USER:
            password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
            password_mgr.add_password(None, PROXY_URL, PROXY_USER, PROXY_PASS)
            opener.add_handler(urllib.request.ProxyBasicAuthHandler(password_mgr))
        return opener
    # If not specified, automatically use Windows system settings/env vars
    return urllib.request.build_opener()


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def fetch_http_date(opener, url: str):
    """Return the current time (UTC), estimated from the HTTP response's
    Date header plus an estimate of the round-trip network delay."""
    t0 = time.time()
    req = urllib.request.Request(
        url, method="HEAD", headers={"User-Agent": "http-time-sync/1.0"}
    )
    with opener.open(req, timeout=TIMEOUT_SEC) as resp:
        date_header = resp.headers.get("Date")
    t1 = time.time()

    if not date_header:
        raise ValueError("The response did not include a Date header")

    server_dt = parsedate_to_datetime(date_header)  # RFC 1123 format, UTC (GMT)
    if server_dt.tzinfo is None:
        server_dt = server_dt.replace(tzinfo=timezone.utc)

    round_trip = t1 - t0
    # The Date header is truncated to whole seconds, so in addition to half
    # the round-trip delay, add an average rounding correction of 0.5s
    # (a simple approximation)
    corrected = server_dt.timestamp() + (round_trip / 2) + 0.5
    return datetime.fromtimestamp(corrected, tz=timezone.utc), round_trip


class SYSTEMTIME(ctypes.Structure):
    _fields_ = [
        ("wYear", ctypes.c_uint16),
        ("wMonth", ctypes.c_uint16),
        ("wDayOfWeek", ctypes.c_uint16),
        ("wDay", ctypes.c_uint16),
        ("wHour", ctypes.c_uint16),
        ("wMinute", ctypes.c_uint16),
        ("wSecond", ctypes.c_uint16),
        ("wMilliseconds", ctypes.c_uint16),
    ]


def set_system_time_utc(dt_utc: datetime) -> None:
    """Set the Windows system clock to the given UTC datetime.
    Requires administrator privileges."""
    st = SYSTEMTIME()
    st.wYear = dt_utc.year
    st.wMonth = dt_utc.month
    st.wDayOfWeek = dt_utc.isoweekday() % 7  # 0=Sunday, 1=Monday, ...
    st.wDay = dt_utc.day
    st.wHour = dt_utc.hour
    st.wMinute = dt_utc.minute
    st.wSecond = dt_utc.second
    st.wMilliseconds = dt_utc.microsecond // 1000

    result = ctypes.windll.kernel32.SetSystemTime(ctypes.byref(st))
    if result == 0:
        err = ctypes.get_last_error()
        raise OSError(
            f"SetSystemTime failed (error code: {err}). "
            "Make sure you are running as Administrator."
        )


def main():
    opener = build_opener()

    print("Fetching server time over HTTPS...")
    corrected_utc = None
    last_error = None

    for url in TIME_SOURCE_URLS:
        try:
            corrected_utc, rtt = fetch_http_date(opener, url)
            print(f"Success: {url}")
            print(f"  Round-trip delay      : {rtt * 1000:.1f} ms")
            print(f"  Corrected time (UTC)   : {corrected_utc.isoformat()}")
            local_now = datetime.now().astimezone()
            print(f"  Current local time     : {local_now.isoformat()}")
            diff = corrected_utc.timestamp() - datetime.now(timezone.utc).timestamp()
            print(f"  Offset from local clock: {diff:+.3f} sec")
            break
        except Exception as e:
            last_error = e
            print(f"  Failed ({url}): {e}")
            continue

    if corrected_utc is None:
        print("\nFailed to connect to any time source server.")
        if last_error:
            print(f"Last error: {last_error}")
        print("Check your proxy settings (PROXY_URL, etc.) and whether")
        print("outbound HTTPS (443) is allowed by your firewall.")
        sys.exit(1)

    if not is_admin():
        print()
        print("Note: Not running with administrator privileges, so the")
        print("system time was NOT changed. To actually correct the time,")
        print("open Command Prompt/PowerShell 'as Administrator' and")
        print("run this script again.")
        sys.exit(0)

    try:
        set_system_time_utc(corrected_utc)
        print()
        print("System time has been corrected.")
    except OSError as e:
        print()
        print(f"Failed to set the system time: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
