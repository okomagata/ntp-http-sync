# ntp-http-sync
# ntp-http-sync

A script to correct the Windows system clock using HTTPS only, for environments where NTP (UDP/123) is blocked by a firewall.

This is intended for situations such as a corporate proxy where NTP/SNTP traffic is not allowed, but HTTPS (TCP/443) is available.

## Features

- Uses only the Python standard library (no `pip install` required)
- Communicates over HTTPS (443) only
- Automatically picks up Windows proxy settings (registry / environment variables)
- Can be combined with Windows Task Scheduler to run periodically under the SYSTEM account

## How it works

Instead of NTP, this script uses the `Date` header of an HTTP response as its time source. It sends an HTTPS request to a lightweight connectivity-check endpoint (e.g. Google's or Cloudflare's `generate_204`-style endpoints) and estimates the current time from the `Date` header and the round-trip delay of the request.

NICT (National Institute of Information and Communications Technology, Japan) used to provide a JSON-based time API over HTTP/HTTPS, but it was discontinued on March 31, 2022, and time distribution is now consolidated to NTP only ([reference, in Japanese](https://jjy.nict.go.jp/httphttps-index.html)). The technique used here — treating the HTTP `Date` header as a time source — is the same fallback method NICT itself used to recommend for environments where NTP/SNTP is blocked by a firewall.

## Security notes (please read)

- **This uses an unauthenticated time source.** Unlike NTS (Network Time Security), the HTTP `Date` header has no cryptographic authentication mechanism. TLS verifies that you're talking to the genuine server, but it does not guarantee that the server's own clock is correct. In environments that perform SSL/TLS inspection (e.g. a corporate proxy that installs its own root certificate), there is, in theory, a non-zero risk that the `Date` header value could be tampered with on the wire. If you need cryptographically verified, tamper-resistant time, use authenticated NTP (NTS) instead.
- **This assumes periodic execution with SYSTEM privileges.** In the Task Scheduler example, this `.py` file is executed periodically with SYSTEM / highest privileges. This means that if the file is ever modified (maliciously or otherwise), SYSTEM-level code would keep running periodically without anyone necessarily noticing. **Always review the code before registering it as a scheduled task.** If you clone this repo directly, review any diffs before updating.
- **Never commit proxy credentials.** If you fill in real credentials in `PROXY_URL` / `PROXY_USER` / `PROXY_PASS` in the script, do not commit or push them to Git under any circumstances. Exclude them via `.gitignore`, or load them from environment variables or another external source instead.

## Usage

### Manual run

Run the following from an elevated (Administrator) command prompt or PowerShell:

```
python ntp_http_sync.py
```

Without administrator privileges, the script only reports the clock offset and does not change the system time.

### Scheduled run (Task Scheduler)

The included `run_ntp_http_sync.bat` can be used to register a SYSTEM-level scheduled task as follows.

1. Edit `PYTHON_EXE` in `run_ntp_http_sync.bat` to match the full path to your Python executable (find it with `where python`).
2. Place `ntp_http_sync.py` and `run_ntp_http_sync.bat` in the same folder.
3. From an elevated command prompt, register a task that runs every hour:

   ```
   schtasks /create /tn "HTTPTimeSync" /tr "C:\path\to\run_ntp_http_sync.bat" /sc hourly /mo 1 /ru SYSTEM /rl HIGHEST /f
   ```

4. Verify it works:

   ```
   schtasks /run /tn "HTTPTimeSync"
   ```

Output is appended, as UTF-8 text, to `ntp_sync.log` in the same folder as the batch file.

## Requirements

- Windows 10 / 11
- Python 3.7+ (standard library only, no extra packages needed)

## License

MIT License. See [LICENSE](./LICENSE) for details.

## Disclaimer

This software is provided "as is", without warranty of any kind. The author is not liable for any damages arising from the use of this software. In particular, no guarantee is made regarding the accuracy or reliability of the time correction it provides. Please review the code carefully and use it at your own risk, especially for any critical use case.
