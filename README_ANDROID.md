# Pip-life FX Bot Android APK

This is an Android front-end for the M1 XAUUSD V4 strategy.

Architecture:
- Native Android UI + foreground service.
- Chaquopy embeds Python 3.13.
- The APK downloads the current `m1_v4_runner.py`, `m1_v4_strategy.py`, and `m1_risk_manager.py` from this GitHub repository when started.
- The APK uses MetaApi REST for candles, quotes, account information, positions and trade commands.
- MetaAPI token and account ID are entered on-device and are not stored in GitHub.

Default mode is DRY RUN. Enable LIVE TRADING only when the HFM demo account is intended.

Build:
1. Push this project to GitHub.
2. Open Actions -> Build Pip-life FX Bot APK -> Run workflow.
3. Download the `pip-life-fx-bot-debug` artifact.

The APK is a debug build. Do not treat it as production-safe without testing on the HFM demo account.
