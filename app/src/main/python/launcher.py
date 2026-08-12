import hashlib
import os
import runpy
import sys
import tempfile
import time
import urllib.request

REPO = "kunguglobal-cpu/Pip-life-fx-bot-2"
RAW_BASE = "https://raw.githubusercontent.com/" + REPO + "/main"

HOME = os.environ.get("HOME", ".")
WORK = os.path.join(HOME, "piplife_bot")
os.makedirs(WORK, exist_ok=True)
LOG = os.path.join(WORK, "bot.log")
STAMP = os.path.join(WORK, "runtime_update.stamp")

RUNTIME_FILES = (
    "m1_v4_runner.py",
    "m1_v4_strategy.py",
    "m1_risk_manager.py",
)

# Do NOT use api.github.com here. The old launcher called the GitHub REST
# API on every start and could hit the unauthenticated 60 requests/hour
# limit, causing the 403 shown in the Android app.
UPDATE_INTERVAL = int(os.getenv("M1_UPDATE_INTERVAL", "21600"))  # 6 hours
DOWNLOAD_TIMEOUT = int(os.getenv("M1_DOWNLOAD_TIMEOUT", "20"))
MAX_RETRIES = int(os.getenv("M1_UPDATE_RETRIES", "3"))

_stop = False


def write_log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(
            time.strftime("%Y-%m-%d %H:%M:%S ")
            + str(msg)
            + "\n"
        )


def _runtime_digest():
    h = hashlib.sha256()
    for name in RUNTIME_FILES:
        path = os.path.join(WORK, name)
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as f:
            h.update(f.read())
    return h.hexdigest()[:12]


def _cache_ready():
    return _runtime_digest() is not None


def _cache_fresh():
    if not _cache_ready() or not os.path.isfile(STAMP):
        return False
    try:
        return (time.time() - os.path.getmtime(STAMP)) < UPDATE_INTERVAL
    except OSError:
        return False


def _download_one(name):
    url = RAW_BASE + "/" + name
    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):
        tmp_path = None
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Pip-life-FX-Bot/4",
                    "Accept": "text/plain",
                    "Cache-Control": "no-cache",
                },
            )

            with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as r:
                data = r.read()

            if not data:
                raise RuntimeError("empty download")

            final_path = os.path.join(WORK, name)
            fd, tmp_path = tempfile.mkstemp(
                prefix=name + ".",
                suffix=".tmp",
                dir=WORK,
            )
            with os.fdopen(fd, "wb") as f:
                f.write(data)
                f.flush()
                os.fsync(f.fileno())

            # Atomic replacement: a partial download can never become active.
            os.replace(tmp_path, final_path)
            return True

        except Exception as exc:
            last_error = exc
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            if attempt < MAX_RETRIES:
                time.sleep(min(2 ** (attempt - 1), 8))

    write_log("DOWNLOAD FAILED | " + name + " | " + repr(last_error))
    return False


def _install_runtime_sources():
    # Repeated starts use the local cache. No GitHub request is made unless
    # the cache is older than UPDATE_INTERVAL or missing.
    if _cache_fresh():
        digest = _runtime_digest()
        write_log("GITHUB VERSION | CACHED-MAIN | " + str(digest))
        sys.path.insert(0, WORK)
        return os.path.join(WORK, "m1_v4_runner.py")

    write_log("RUNTIME UPDATE | checking raw GitHub source")

    all_ok = True
    for name in RUNTIME_FILES:
        if not _download_one(name):
            all_ok = False

    digest = _runtime_digest()

    if digest is None:
        raise RuntimeError(
            "No cached runtime and GitHub raw download failed"
        )

    if all_ok:
        try:
            with open(STAMP, "w", encoding="utf-8") as f:
                f.write(str(time.time()))
        except OSError as exc:
            write_log("STAMP WARNING | " + repr(exc))
        write_log("GITHUB VERSION | RAW-MAIN | " + digest)
    else:
        write_log("GITHUB VERSION | CACHED-FALLBACK | " + digest)

    sys.path.insert(0, WORK)
    return os.path.join(WORK, "m1_v4_runner.py")


def run_bot(token, account_id, live):
    global _stop

    _stop = False

    os.environ["METAAPI_TOKEN"] = str(token)
    os.environ["METAAPI_ACCOUNT_ID"] = str(account_id)
    os.environ["M1_DRY_RUN"] = "false" if bool(live) else "true"
    os.environ["M1_POLL"] = "2.0"

    open(LOG, "w").close()

    write_log(
        "PIP-LIFE FX BOT START | live="
        + str(bool(live))
    )

    real_sleep = time.sleep

    try:
        runner = _install_runtime_sources()

        def bot_sleep(seconds):
            if _stop:
                raise KeyboardInterrupt()
            real_sleep(min(float(seconds), 2.0))

        time.sleep = bot_sleep

        runpy.run_path(runner, run_name="__main__")

    except KeyboardInterrupt:
        write_log("BOT STOPPED")

    except Exception as e:
        write_log("BOT ERROR | " + repr(e))

    finally:
        time.sleep = real_sleep


def stop_bot():
    global _stop
    _stop = True
    write_log("STOP REQUESTED")
