# CREMA operations

This runbook covers readiness, metrics, structured logs, passive monitoring, backups, and recovery. Commands that inspect monitoring data do not control the kiosk, scanner, sensor, or systemd services.

## Readiness and authentication

`GET /health` is public. It reports database connectivity and, when hardware is expected, kiosk-loop, scanner, and sensor readiness. Hardware degradation returns HTTP 503, so a successful process start alone is not proof that the kiosk is ready.

```bash
curl --fail http://127.0.0.1:8000/health
```

`GET /api/metrics` requires the same authentication as data and control REST endpoints. In token mode, provide the configured bearer token. In session mode, either use that token or an authenticated session cookie.

```bash
curl --fail \
  -H "Authorization: Bearer $CREMA_API_TOKEN" \
  http://127.0.0.1:8000/api/metrics
```

Do not put tokens in URLs, shell history, Prometheus label values, or shared JSONL files. Use an environment variable or a protected credentials file. Keep `/api/metrics` on the same trusted network boundary as the other authenticated API routes.

## Prometheus metrics

The endpoint returns Prometheus text format `0.0.4`. It includes process uptime, HTTP totals, kiosk events and transitions, brew/noise results, database totals, WebSocket activity, and current hardware state. Process counters start at zero after a restart; persisted record counts come from SQLite.

HTTP labels use method, response status, and the registered FastAPI route template. Unmatched requests use `route="unmatched"`. IDs, usernames, email tokens, credentials, raw request paths, query strings, and exception text are never metric labels. Kiosk labels use finite event, state, brew-kind, and disconnect-reason sets. Do not add unbounded values to these labels.

A minimal scrape job is:

```yaml
scrape_configs:
  - job_name: crema
    scrape_interval: 30s
    metrics_path: /api/metrics
    static_configs:
      - targets: ["crema.local:8000"]
    authorization:
      credentials_file: /etc/prometheus/crema-token
```

Use `scheme: https` when the API is served through an HTTPS reverse proxy. Protect the credentials file with operating-system permissions and keep the target address stable to avoid unnecessary target churn.

Useful starting checks include:

- `crema_up` and `crema_kiosk_running` for process and loop availability.
- `crema_kiosk_scanner_connected`, `crema_kiosk_sensor_connected`, and `crema_kiosk_sensor_stale_seconds` for hardware readiness.
- The rate of `crema_http_requests_total` with `status="500"` for server failures.
- Growth in `crema_kiosk_snapshot_drops_total` and `crema_kiosk_websocket_drops_total` for delivery pressure or disconnects.
- `crema_database_open_sessions` after an unclean stop or repeated restart.

## Runtime logs

The service writes text logs to standard output by default. systemd captures them in the journal. Configure runtime logging before startup:

| Variable | Default | Behavior |
|---|---|---|
| `CREMA_LOG_LEVEL` | `INFO` | Standard Python logging level |
| `CREMA_LOG_FORMAT` | `text` | `text` or `jsonl` |
| `CREMA_LOG_FILE` | unset | Also append logs to this file |

JSONL writes one JSON object per line with an ISO 8601 UTC timestamp, level, logger, event, message, and event-specific fields. Kiosk transitions include bounded `from_state` and `to_state` fields. Brew results include duration and kind without a user identity. Exceptions include a formatted traceback field. The supported `main.py`, `crema serve`, and simulator entry points route Uvicorn process and access records through the same handlers and formatter. A plain third-party `uvicorn api.main:app` invocation uses Uvicorn's own logging configuration instead.

```bash
CREMA_LOG_FORMAT=jsonl \
CREMA_LOG_FILE=/var/log/crema/crema.jsonl \
python main.py
```

The service does not rotate `CREMA_LOG_FILE`. Create the directory with appropriate permissions and configure journald, logrotate, or the platform log collector to bound disk use. Avoid logging `Authorization` headers, session cookies, passwords, user tokens, or raw URLs in new events.

## Passive JSONL recorder

`crema-monitor` reads selected Prometheus gauges and, by default, systemd state through read-only D-Bus properties. It does not call service start, stop, restart, kiosk controls, or hardware interfaces. Each sample is appended immediately as one JSONL record.

```bash
export CREMA_API_TOKEN
crema-monitor \
  --url http://127.0.0.1:8000/api/metrics \
  --service crema-kiosk.service \
  --interval 60 \
  --output /var/log/crema/monitoring.jsonl
```

Use `--once` for a single sample and `--no-service` on development machines without the system D-Bus or systemd unit. Omit `--output` to write JSONL to standard output. The interval must be a finite positive number of seconds.

A record has `status="ok"` when metrics and requested D-Bus probes succeed, `status="degraded"` when metrics are available but another probe fails, and `status="error"` when the API metric is unavailable. Probe failures are recorded in `errors` with the exception type and message. Monitoring failures do not terminate the service or attempt recovery automatically.

For a simulator-only soak, explicitly point the recorder at the simulator endpoint and disable the service probe:

```bash
crema-monitor --once --no-service \
  --url http://127.0.0.1:8010/api/metrics
```

Do not use the real kiosk service or its database for development soak tests.

## Verified backups

Use SQLite's backup API through the CLI, including while the database is live. Never copy a live WAL database and its sidecar files with a plain file copy.

```bash
crema db backup
crema db check
```

An automatic destination is `CREMA_BACKUP_DIR/espresso-YYYYMMDD-HHMMSS-ffffff.db`. Backup creation writes a temporary file in the destination directory, completes the SQLite backup, runs an integrity check, and atomically replaces the destination only after verification. A failed backup leaves an existing destination unchanged and cleans up temporary files. The live database itself is rejected as a destination.

An explicit output path creates a verified backup but does not trigger automatic retention:

```bash
crema db backup /secure-backups/espresso-manual.db
```

The update script creates a timestamped backup before pulling changes when the live database exists. Export the same `CREMA_DB_PATH` and `CREMA_BACKUP_DIR` values used by the service when running maintenance commands.

## Retention

Automatic backup and explicit cleanup operate only on regular files whose entire names match the timestamped CREMA backup pattern. Manual backups, unrelated database names, notes, directories, and symbolic links are not pruned.

| Variable | Default | Behavior |
|---|---|---|
| `CREMA_BACKUP_RETENTION_COUNT` | `14` | Keep at most this many newest timestamped backups; minimum 1 |
| `CREMA_BACKUP_RETENTION_DAYS` | `0` | Remove timestamped backups older than this many days; 0 disables age pruning |

Age uses file modification time. When age pruning is enabled, expired files are removed even if they are among the newest retained count. Count and age pruning therefore both apply.

```bash
crema db backup --keep 14
crema db cleanup --keep 14 --max-age-days 30
crema db cleanup /secure-backups --keep 7 --max-age-days 14
```

Review the matching directory and retention settings before the first production cleanup. Keep at least one verified copy outside the Pi, and periodically check free disk space.

## Restore and incident checks

Stop the hardware/API service before restoring or reclassifying the live database. The maintenance lock prevents replacement while the exclusive owner is running. Restore validates the candidate schema and, when possible, creates a safety backup of the current database first.

```bash
sudo systemctl stop crema-kiosk
crema db check /secure-backups/espresso-manual.db
crema db restore /secure-backups/espresso-manual.db
sudo systemctl start crema-kiosk
curl --fail http://127.0.0.1:8000/health
```

After an unclean stop, do not manually close open sessions in a separate API-only process. Only the exclusive hardware owner performs startup session recovery. Confirm `crema_sessions_recovered_total`, logs, and `crema_database_open_sessions` after restart. Restore service control remains a deliberate operator action, not part of the passive recorder.
