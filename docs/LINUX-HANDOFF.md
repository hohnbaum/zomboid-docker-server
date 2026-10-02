# Moving to a Linux host

The public repository supplies code. A private handoff separately supplies a
verified world archive, its SHA256, deployment `.env` and secret files. Never copy
Docker Desktop internal volume directories, a Windows app installation, the
Windows Workshop cache or a Python virtual environment.

## Prepare the source deployment

Choose the explicit source Compose project in `.env`. Confirm its name with
`docker compose config --services` and `docker compose ps`. Keep clients offline
during transfer. Run `./pz stop`, then `./pz backup`; these enforce known player
state and stopped-copy integrity. Inspect the returned backup name.

Stop the project's control services with
`docker compose stop pz-ops pz-server`. Export:

```sh
./pz export --backup BACKUP_NAME --output exports/private-handoff.tar.gz
```

The result reports archive size and SHA256. Store it and its checksum privately.
`manifest.json` inside the archive contains per-file SHA256 and byte counts;
`_backup.json` is completion metadata. The archive contains credentials and player
data even though it has no Discord/API secret files. Protect it accordingly.

## Prepare the destination

Install Docker Engine, Compose and Python 3.12+ using your host's normal approved
setup. Use an x86-64 Linux host. Clone the public repository, copy `.env.example`
to `.env` and select a **new explicit project name** plus the archived server name.
Choose a heap and verify actual memory/disk headroom. Run `./pz init-secrets` and
`docker compose build pz-server pz-ops`.

To establish Linux version evidence before restoring an imported world, use a
separate disposable empty project to install and start the public package, reach
READY, stop it, then stop its services. An explicitly shared app volume may be
selected with `PZ_APP_VOLUME`; only one project may run or update that app at once.
The agent enforces this with a persistent kernel lock. Prefer separate app volumes
for independently operated deployments.

Copy the private archive using your chosen private transfer method. Verify the
external archive checksum against the source report. With the destination's
control services stopped:

```sh
./pz restore --archive /private/location/private-handoff.tar.gz
docker compose up -d pz-server pz-ops
./pz status
./pz version
./pz start
```

Restore verifies extraction paths, hashes, counts, databases and pending mod
provenance. It starts with `desired=false`. An empty data target is preferred;
replacement requires `--confirm-replace` and a protected pre-restore backup.
The archive's server name must match the configured name.

The initial imported-world gate is exactly 42.21.0. If the public package has
moved, an old startup log cannot satisfy the new build's gate. Keep the pristine
copy and report `BLOCKED_VERSION`; obtain a legitimate compatible package or make
an explicit, separately reviewed migration decision. Do not guess depot IDs.

## Network and bot settings

For deliberate LAN/public operation set `PZ_BIND_ADDRESS=0.0.0.0` in private
`.env`, configure the host firewall/router for the two selected **UDP game**
ports, and set advertised LAN/VPN/public endpoints. RCON and the ops API remain
unpublished. Confirm the intended interface and ports with `docker compose ps`.

Generate a new private API token on the destination. Supply the Discord token
separately only if enabling the `discord` profile; stop the old bot before
starting its replacement. Never run two deployments with the same bot token.

Verify status, players, save/quit, mod state and backup creation. Perform a client
join/rejoin and a representative restored-world check before directing production
players to the new host. Historical reference archives from an original import
remain in the source backup volume and are not recursively included in operational
handoff archives; transfer those separately if you need their private provenance.
