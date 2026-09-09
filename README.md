# SpyPoint Photo Kiosk for Home Assistant

Download photos from a SpyPoint cellular trail camera and show them as a
kiosk dashboard in Home Assistant — with a push notification whenever a
new photo arrives.

## Why this exists

The official [SpyPoint HACS integration](https://github.com/happydev-ca/spypoint-home-assistant)
only exposes **sensors** (battery, signal strength, status, etc.) for your
camera. It does **not** pull down the actual photos, even though they're
visible in the SpyPoint app. This project fills that gap with:

- a small Python script that logs into SpyPoint and downloads new photos
- a Home Assistant setup that turns those photos into camera entities
- a dashboard view showing the latest photos
- a push notification (with image preview) whenever a new photo lands

## Architecture

```
SpyPoint cloud
      │  (pyspypoint library)
      ▼
spypoint_download.py  (runs via cron on the machine hosting HA)
      │  writes .jpg files to a folder, keeps a "latest" subfolder
      │  with fixed filenames (latest_1.jpg … latest_N.jpg)
      ▼
Docker volume mount  →  /media/spypoint  inside the HA container
      │
      ├─ local_file integration  →  camera.spypoint_foto_1 … _N
      ├─ folder_watcher integration  →  fires on new downloads
      └─ automation  →  push notification with photo attached
```

## Prerequisites

- Home Assistant running (this was built against a Docker install, but
  the HA-side steps work the same for any install as long as you can
  mount/reach the photo folder from the HA container or host)
- A machine that can run Python and cron independently of HA (e.g. the
  same host if HA runs in Docker there, or any other always-on machine
  with access to the same filesystem/volume)
- A SpyPoint account with at least one camera

## 1. Install the downloader script

```bash
python3 -m venv ~/spypoint-env
source ~/spypoint-env/bin/activate
pip install pyspypoint requests
```

Copy [`spypoint_download.py`](spypoint_download.py) to your machine, e.g.
`~/spypoint_download.py`.

Store your SpyPoint credentials as environment variables rather than in
the script itself. One simple way: a file only you can read, sourced
before running the script.

```bash
cat > ~/.spypoint_credentials << 'EOF'
export SPYPOINT_USERNAME="you@example.com"
export SPYPOINT_PASSWORD="your-password"
EOF
chmod 600 ~/.spypoint_credentials
```

Test it once:

```bash
source ~/.spypoint_credentials
~/spypoint-env/bin/python3 ~/spypoint_download.py
ls -la ~/spypoint-photos/latest/
```

You should see `latest_1.jpg` (newest) through `latest_7.jpg`
(default: 7 — see `LATEST_COUNT` in the script).

Then add a cron job to run it periodically, e.g. every 30 minutes:

```bash
crontab -e
# add:
*/30 * * * * source /home/YOUR_USER/.spypoint_credentials && /home/YOUR_USER/spypoint-env/bin/python3 /home/YOUR_USER/spypoint_download.py
```

## 2. Mount the photo folder into Home Assistant

If HA runs in Docker, add a volume to your compose file / `docker run`:

```yaml
volumes:
  - /home/YOUR_USER/spypoint-photos:/media/spypoint
```

Restart the container, then confirm HA can see the files:

```bash
docker exec homeassistant ls -lah /media/spypoint
```

## 3. Set up the Home Assistant integrations

**Important:** on current Home Assistant versions, both `local_file`
(camera) and `folder_watcher` are **UI-only integrations** — they no
longer accept `platform: local_file` / `folder_watcher:` blocks in
`configuration.yaml`. If you add them as YAML, HA will show a repair
error telling you to remove them and set them up via the UI instead.

Go to **Settings → Devices & Services → Add Integration**:

- Add **Local File** once per photo slot, pointing at
  `/media/spypoint/latest/latest_1.jpg`, `latest_2.jpg`, … Name them
  something like `SpyPoint Foto 1`, `SpyPoint Foto 2`, etc. This gives
  you entities `camera.spypoint_foto_1` … `_N`.
- Add **Folder Watcher** once, folder `/media/spypoint`, pattern
  `*.jpg`. Point it at the **top-level** folder only (not the `latest`
  subfolder) — otherwise the script's own housekeeping copies into
  `latest/` will trigger false "new photo" events.

You'll also want `allowlist_external_dirs` set in `configuration.yaml`
(this key itself is still plain YAML, unlike the two integrations above):

```yaml
homeassistant:
  allowlist_external_dirs:
    - /media/spypoint
```

## 4. Notification automation

See [`examples/automation.yaml`](examples/automation.yaml). Adjust the
`notify.mobile_app_YOUR_DEVICE` action to your own device's notify
service — find it under **Developer Tools → Actions**, search
`mobile_app`.

**Note on `notify.send_message`:** newer Home Assistant versions
introduced a unified `notify.send_message` action targeting notify
*entities*. It's the modern, recommended way to send notifications, but
as of this writing it only accepts `message` and `title` — no `data`
block, so **no image attachments**. For a photo preview in the push
notification you need the classic per-device action
(`notify.mobile_app_<device>`), which still works even on setups that
have otherwise migrated to notify entities.

The image path uses Home Assistant's `/media/local/...` convention: a
file at `/media/spypoint/foo.jpg` on disk is referenced as
`/media/local/spypoint/foo.jpg` in a notification — this gets
authenticated automatically by the companion app, no public URL needed.

## 5. Dashboard

See [`examples/dashboard-view.yaml`](examples/dashboard-view.yaml) for a
`sections`-type view: one large "latest photo" card, smaller cards for
the rest, and a status panel with gauges for battery/signal/SD card
usage plus a history graph.

If your dashboard is in **storage mode** (the default — no `lovelace:`
key in `configuration.yaml`), you can't just drop in a YAML file.
Create a new view in the UI, then use its three-dot menu →
**"Edit in YAML"** and paste the section content in.

## Known pitfalls (things that bit us building this)

- **SpyPoint photo URLs are signed and expire.** They include a
  time-limited signature token that changes on every API call, even for
  the *same* photo. Don't deduplicate downloads by hashing the full URL
  — hash/compare the **filename** instead (or just check whether the
  file already exists on disk). Otherwise every cron run will
  "helpfully" re-download everything.
- **The API returns newest-first, but don't re-sort by download/file
  mtime.** Downloads happen sequentially, so the *last* file written in
  a batch gets the newest mtime on disk — even though it's actually the
  *oldest* photo in that batch. Sort the "latest N" selection by the
  capture timestamp encoded in the filename instead, never by
  filesystem mtime.
- **`local_file` and `folder_watcher` are config-entry-only now.** YAML
  platform config for these silently doesn't apply on current HA
  versions (with a repair-issue warning) — use Settings → Devices &
  Services.
- **`notify.send_message` can't send images (yet).** Use the legacy
  per-device `notify.mobile_app_<device>` action if you need an image
  attachment in the push notification.

## Credits

Built using [`pyspypoint`](https://github.com/hstern/pyspypoint), an
unofficial Python client for the SpyPoint cloud API.

## License

MIT — see [LICENSE](LICENSE).
