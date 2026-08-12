import os, sys, time, threading, runpy, json, urllib.request

REPO = "kunguglobal-cpu/Pip-life-fx-bot-2"
RAW_BASE = "https://raw.githubusercontent.com/" + REPO
API_BASE = "https://api.github.com/repos/" + REPO

HOME = os.environ.get("HOME", ".")
WORK = os.path.join(HOME, "piplife_bot")
os.makedirs(WORK, exist_ok=True)
LOG = os.path.join(WORK, "bot.log")

_stop = False
_thread = None


def write_log(msg):
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(
            time.strftime("%Y-%m-%d %H:%M:%S ")
            + str(msg)
            + "\n"
        )


def _latest_github_version():
    req = urllib.request.Request(
        API_BASE + "/commits/main",
        headers={
            "User-Agent": "Pip-life-FX-Bot",
            "Accept": "application/vnd.github+json",
        },
    )

    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())

    sha = str(data["sha"])
    message = str(
        data.get("commit", {})
        .get("message", "")
    ).splitlines()[0]

    if not sha:
        raise RuntimeError("GitHub returned no commit SHA")

    return sha, message


def _download(name, sha):
    path = os.path.join(WORK, name)

    url = (
        RAW_BASE
        + "/"
        + sha
        + "/"
        + name
    )

    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Pip-life-FX-Bot"},
    )

    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()

    with open(path, "wb") as f:
        f.write(data)

    return path


def _install_runtime_sources():
    # Resolve main to one exact commit.
    sha, message = _latest_github_version()

    short = sha[:12]

    write_log(
        "GITHUB VERSION | "
        + short
        + " | "
        + message
    )

    write_log(
        "GITHUB COMMIT | "
        + sha
    )

    # Download every runtime file from the SAME commit.
    for name in (
        "m1_v4_runner.py",
        "m1_v4_strategy.py",
        "m1_risk_manager.py",
    ):
        _download(name, sha)

        write_log(
            "UPDATED | "
            + name
            + " | "
            + short
        )

    sys.path.insert(0, WORK)

    return os.path.join(
        WORK,
        "m1_v4_runner.py"
    )


def run_bot(token, account_id, live):
    global _stop

    _stop = False

    os.environ["METAAPI_TOKEN"] = str(token)
    os.environ["METAAPI_ACCOUNT_ID"] = str(account_id)

    os.environ["M1_DRY_RUN"] = (
        "false" if bool(live) else "true"
    )

    os.environ["M1_POLL"] = "2.0"

    open(LOG, "w").close()

    write_log(
        "PIP-LIFE FX BOT START | live="
        + str(bool(live))
    )

    try:
        runner = _install_runtime_sources()

        real_sleep = time.sleep

        def bot_sleep(seconds):
            if _stop:
                raise KeyboardInterrupt()

            real_sleep(
                min(float(seconds), 2.0)
            )

        time.sleep = bot_sleep

        runpy.run_path(
            runner,
            run_name="__main__"
        )

    except KeyboardInterrupt:
        write_log("BOT STOPPED")

    except Exception as e:
        write_log(
            "BOT ERROR | "
            + repr(e)
        )

    finally:
        time.sleep = (
            real_sleep
            if "real_sleep" in locals()
            else time.sleep
        )


def stop_bot():
    global _stop

    _stop = True

    write_log(
        "STOP REQUESTED"
    )
