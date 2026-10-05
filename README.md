# pz-docker-server: Project Zomboid auf Debian 13

Dieses Repository betreibt einen Linux-Dedicated-Server mit Docker Compose,
Python-Verwaltung, sicheren Save/Stop-Abläufen, Backups, Mod-Plänen und optionalem
Discord-Bot. Es enthält ausschließlich Code, Dokumentation und synthetische Tests.
Spiel, Workshop-Inhalte, Welten und Secrets liegen in privaten Docker-Volumes bzw.
ignorierten Verzeichnissen. Keine Zugehörigkeit zu The Indie Stone.

**Abnahme:** Die importierte private Testkopie wurde mit PZ **42.21.0 / Steam Build
25485538** erfolgreich gestartet und mit einem echten Client geprüft. Account,
lebender Charakter, Welt und repräsentative Mods funktionierten; danach waren
111 Workshop-Items Current und alle 137 konfigurierten Mods vorhanden. Das ist
ein Migrationsnachweis, **nicht der finale Produktionsspielstand**. Dieser kommt
nach dem letzten Spielbetrieb frisch vom kontrolliert gestoppten Windows-Server.

Die Debian-Befehle sind für **Bash**. In jeder neuen SSH-/sudo-Shell zuerst
ausführen, damit abhängige Schritte nach einem Fehler stehen bleiben:

```bash
set -e
```

Bei einem Fehler endet die Bash-Sitzung; gegebenenfalls neu per SSH anmelden.
Nach der Fehlerklärung ab dem fehlgeschlagenen Befehl fortsetzen. Bereits erledigte
Initialisierung und Import dabei nicht wiederholen. Abschnitt 9 enthält einzelne
Bedienbeispiele, die jeweils bewusst ausgewählt werden.

## 1. Voraussetzungen

- Debian 13 (Trixie), **amd64/x86-64**, SSH-Zugang und sudo bzw. root.
- Docker Engine mit Compose-Plugin, Git und Python 3.12 oder neuer auf dem Host.
- Internet für SteamCMD/Workshop und genügend freien SSD-Speicher. Plane Platz
  für zwei Spielinstallationen, Workshop, Welt, Importstaging und mehrere Backups;
  mindestens das Mehrfache der entpackten Welt zusätzlich zur Installation.
- Für Live ist standardmäßig ein **8-GiB-Java-Heap** vorgesehen, dazu native JVM-/Mod-Speicher,
  Betriebssystem und Container. 16 GiB Host-RAM sind ein sinnvoller Ausgangspunkt,
  keine Garantie für beliebige Mods. Messe freie Ressourcen vor dem Start.
- Der leere Testserver verwendet 2 GiB Heap und eigene persistente Volumes.

```bash
uname -m
df -h
```

Der Servercontainer verwendet das von PZ gelieferte Java. Kein Host-Java, Docker
Desktop, WSL oder PowerShell ist für diesen Debian-Quickstart erforderlich.

## 2. Debian und Docker installieren

Auf einem frischen Debian-Server:

Die Befehle verwenden sudo. Bei direkter Root-Anmeldung und fehlendem sudo zuerst
als root einmal ausführen:

```bash
apt-get update
apt-get install sudo
```

```bash
sudo apt-get update
sudo apt-get upgrade
sudo apt-get install ca-certificates curl git python3 iptables procps iproute2 nano
sudo install --directory --mode=0755 /etc/apt/keyrings
sudo curl --fail --silent --show-error --location \
  https://download.docker.com/linux/debian/gpg \
  --output /etc/apt/keyrings/docker.asc
sudo chmod 0644 /etc/apt/keyrings/docker.asc
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/debian
Suites: trixie
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt-get update
sudo apt-get install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker.service containerd.service
sudo docker run --rm hello-world
free -h
```

Bei einem bereits eingerichteten Host zuerst die bestehenden Pakete und Dienste
prüfen. Konfliktpakete wie docker.io, docker-compose, podman-docker oder separat
installiertes containerd/runc nach der [offiziellen Debian-Anleitung von Docker](https://docs.docker.com/engine/install/debian/)
behandeln; diese Anleitung setzt einen frischen Zielserver voraus.

Für einen normalen SSH-Benutzer:

```bash
sudo usermod --append --groups docker "$USER"
```

Danach vollständig abmelden und per SSH neu anmelden, dann `docker info` und
`docker compose version` prüfen. Die docker-Gruppe gewährt faktisch Root-Rechte;
nur vertrauenswürdige Administratoren aufnehmen. Alternativ in einer administrativen
Shell (`sudo -i`) arbeiten und dort alle folgenden Befehle ausführen. Die
[Docker-Nachinstallation](https://docs.docker.com/engine/install/linux-postinstall/)
erläutert Gruppenrechte und Start beim Booten.

## 3. Repository und zwei Instanzen vorbereiten

Die folgende URL ist der origin dieses öffentlichen Repositorys. Klonen über HTTPS
benötigt für das Lesen keine GitHub-Tokens. Private Welten und Secrets kommen
separat; sie sind auch nach dem Klonen nicht vorhanden.

```bash
PZ_REPOSITORY_URL='https://github.com/hohnbaum/zomboid-docker-server.git'
git clone "$PZ_REPOSITORY_URL" pz-docker-server
cd pz-docker-server
cp .env.test.example .env.test
cp .env.live.example .env.live
chmod 600 .env.test .env.live
./pz --env-file .env.test init-secrets
./pz --env-file .env.live init-secrets
sudo chown 1000:1000 secrets/test/api.token secrets/test/discord.token \
  secrets/live/api.token secrets/live/discord.token
sudo install -d -o "$(id -u)" -g 1000 -m 2750 imports
sudo install -d -o "$(id -u)" -g 1000 -m 2770 exports
```

Die Dienste laufen als UID/GID 1000. Token-Dateien bleiben 0600 in privaten
Verzeichnissen; der gezielte chown stellt auch bei root oder einer anderen
Host-UID ihre Lesbarkeit im Container sicher. Imports benötigen Leserechte,
Exports Schreibrechte für GID 1000. Keine Secrets werden im Terminal ausgegeben.
`.env.test`, `.env.live`, `secrets/`, `imports/` und `exports/` sind gitignoriert.

| Profil | Zweck | Spiel/Workshop/Daten/State/Backups | Heap |
| --- | --- | --- | --- |
| .env.test | Dauerhafter, bei Bedarf genutzter leerer pztest | Eigenständig, Projekt pztest | 2g |
| .env.live | Importierte Produktionswelt szs | Eigenständig, Projekt pzlive | 8g |

`PZ_HEAP=8g` in .env.live setzt beim nächsten Spielstart sowohl Java -Xms als auch
-Xmx auf 8 GiB. Bereits angelegte .env.live-Dateien werden durch ein Git-Update
nicht geändert: dort den Wert bei Bedarf selbst anpassen. Der leere Test und die
temporäre Versionsprüfung bleiben bei 2g. Die bisherige Live-/Restore-Abnahme lief
mit 6g; 8g ist die neue Vorgabe, kein zusätzlich abgenommener Spielstart.

Beide Beispiele verwenden **16261:16261/udp und 16262:16262/udp**, gebunden an
0.0.0.0 für einen externen Client. Prüfe und passe die private Konfiguration an.
Für rein lokale Tests kann PZ_BIND_ADDRESS auf 127.0.0.1 gesetzt werden.
PZ_APP_VOLUME/PZ_WORKSHOP_VOLUME nicht aus der alten Windows-Testkonfiguration
übernehmen: die normalen Projekte erhalten getrennte App-/Workshop-Volumes.

## 4. Testserver frisch installieren und starten

Prüfe zunächst, dass die UDP-Ports frei sind und kein Live-Projekt läuft:

```bash
sudo ss -lunp | grep -E ':(16261|16262)\b' || true
docker ps --format 'table {{.Names}}\t{{.Ports}}'
docker compose --env-file .env.test build pz-server pz-ops
./pz --env-file .env.test init-empty
docker compose --env-file .env.test up -d --wait --wait-timeout 120 pz-server pz-ops
./pz --env-file .env.test install
./pz --env-file .env.test start
./pz --env-file .env.test status
./pz --env-file .env.test health
./pz --env-file .env.test version
./pz --env-file .env.test workshop-status
docker compose --env-file .env.test ps
```

`init-empty` erzeugt einen neuen leeren pztest mit **Password=**, also ohne
Spieler-Serverpasswort. RCON- und Bootstrap-Admin-Passwort werden sicher zufällig
erzeugt und bleiben privat; der interne API-Token ebenfalls. `init-empty` ersetzt
keine bestehende Welt. `start` wartet auf READY: eigener Spielprozess, beide
UDP-Listener und authentifiziertes RCON mit lesbarer Spielerzahl.

`up --wait` wartet auf die gesunden Control-Dienste, bevor `install` bzw. `start`
deren API verwenden. Bei einem Fehler **nicht die nächsten Zeilen weiter ausführen**:
zuerst Ursache und Compose-Status prüfen. `init-empty` und der spätere Live-Import
sind einmalige Initialisierungen; für vorhandene Instanzen nur up/start verwenden.

Vor dem externen Client-Test Firewall/NAT gemäß Abschnitt 5 einrichten.
Im PZ-Client den Debian-Host und Port **16261** verwenden, das Serverpasswortfeld
leer lassen und einen normalen Spieleraccount benutzen. Der Bootstrap-Admin ist
kein allgemeines Spielerpasswort. Server und Client müssen kompatible PZ-Versionen
haben. Für die abgenommene Migration ist dies exakt 42.21.0.

## 5. Firewall und Internetzugang

Nur **UDP 16261 und 16262** für die vorgesehenen Clients öffnen; zusätzlich den
bestehenden SSH-Zugang beibehalten. TCP 27015/RCON, Ops-API 8080 und den Unix-Socket
nicht öffentlich freigeben. Bei einem Cloud-Anbieter dieselben UDP-Ports in dessen
Netzwerkfirewall erlauben. Router-Portweiterleitung/NAT ist nur nötig, wenn Clients
über das Internet auf einen Host hinter einem Router zugreifen.

Docker verwaltet für veröffentlichte Ports DNAT/Forwarding. Ein gewöhnliches
`ufw allow` bzw. eine INPUT-Regel allein schützt/freigibt Docker-Ports nicht
zuverlässig. Beim standardmäßigen iptables-Backend eigene Regeln in DOCKER-USER
einordnen, beispielsweise vor einer vorhandenen Drop-Regel:

```bash
sudo iptables -S DOCKER-USER
sudo iptables -C DOCKER-USER -p udp -m multiport --dports 16261,16262 -j ACCEPT 2>/dev/null || \
  sudo iptables -I DOCKER-USER 1 -p udp -m multiport --dports 16261,16262 -j ACCEPT
```

Diese zusätzliche Regel ist zunächst temporär; in der bestehenden Firewallverwaltung
dauerhaft hinterlegen und nach einem Reboot prüfen. Vorhandene Regeln nicht pauschal
löschen. Andere Firewall-Backends erfordern deren passende Forwarding-Regeln.
Siehe [Docker mit iptables](https://docs.docker.com/engine/network/firewall-iptables/)
und [Docker/Host-Firewalls](https://docs.docker.com/engine/network/packet-filtering-firewalls/).

Auf einem frischen Zielhost ohne eigene Firewallverwaltung kann diese systemd-Unit
die Regel bei Docker-Start/-Neustart erneut setzen. Sie setzt das standardmäßige
iptables-Backend voraus; bei vorhandener Firewallverwaltung die Regel stattdessen
dort pflegen:

```bash
sudo tee /etc/systemd/system/pz-docker-udp.service >/dev/null <<'EOF'
[Unit]
Description=Project Zomboid UDP in Docker forwarding
After=docker.service
Requires=docker.service
PartOf=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/sh -c '/usr/sbin/iptables -C DOCKER-USER -p udp -m multiport --dports 16261,16262 -j ACCEPT || /usr/sbin/iptables -I DOCKER-USER 1 -p udp -m multiport --dports 16261,16262 -j ACCEPT'

[Install]
WantedBy=docker.service
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now pz-docker-udp.service
sudo systemctl status pz-docker-udp.service --no-pager
```

Nach einem Host-Reboot `sudo iptables -S DOCKER-USER` sowie Docker-/PZ-Status erneut
prüfen. Die Unit öffnet keine zusätzlichen Ports.

## 6. Test sauber stoppen und Live-Version vorbereiten

Nach dem Client-Test alle Spieler abmelden:

```bash
./pz --env-file .env.test save
./pz --env-file .env.test stop
docker compose --env-file .env.test stop pz-ops pz-server
```

Die Container müssen gestoppt sein, damit die Host-Ports frei werden; ein gestoppter
Spielprozess allein reicht nicht. Testvolumes bleiben für spätere Tests erhalten.

Der Import besitzt weiterhin einen strikten 42.21.0-Gate. Ein unabhängig installiertes
Live-App-Volume benötigt dafür **eigene Linux-Start-Evidenz**. Diese wird einmal mit
einer temporären leeren Instanz auf genau dem Live-App-Volume erzeugt:

```bash
cp .env.versioncheck.example .env.versioncheck
chmod 600 .env.versioncheck
./pz --env-file .env.versioncheck init-secrets
sudo chown 1000:1000 secrets/versioncheck/api.token secrets/versioncheck/discord.token
docker compose --env-file .env.versioncheck build pz-server pz-ops
./pz --env-file .env.versioncheck init-empty
docker compose --env-file .env.versioncheck up -d --wait --wait-timeout 120 pz-server pz-ops
./pz --env-file .env.versioncheck install
./pz --env-file .env.versioncheck start
./pz --env-file .env.versioncheck version
./pz --env-file .env.versioncheck stop
docker compose --env-file .env.versioncheck stop pz-ops pz-server
```

Dabei müssen Test und Live gestoppt sein. Nur dieser temporäre Prüflauf nutzt
pzlive_app/pzlive_workshop; sein leerer Datenbestand ist getrennt. Der dauerhafte
pztest teilt keine Volumes mit Live. Wenn COMPOSE_PROJECT_NAME geändert wird,
die zwei Volumennamen im Versionsprüfprofil entsprechend anpassen.
Nur bei bestätigter **42.21.0** fortfahren. Ein späterer anderer Steam-Build braucht
neue passende Evidenz; alte Logs oder geänderte Hashes ersetzen diese nicht.

### Was der Versions-Gate tatsächlich prüft

Für importierte Welten ist **42.21.0 fest im Code vorgegeben**, nicht als
änderbare VERSION-Umgebungsvariable. Der Import schreibt required_version=42.21.0
in private Migrationsmarker. Vor einem neuen Spielstart prüft
[server/agent.py](server/agent.py), dass sowohl dieser Marker als auch die
nachgewiesene installierte Spielversion exakt 42.21.0 sind; sonst BLOCKED_VERSION.
Auch ein veränderter Marker auf eine andere Version wird verweigert.

Die tatsächlich installierte Version stammt aus der ersten version=-Meldung
eines vom Linux-Agent gestarteten Spielprozesses. Die Evidenz wird auf dem
App-Volume gespeichert und an die Steam-Build-ID aus appmanifest_380870.acf
gebunden. Ändert sich die Build-ID, zählt die alte Evidenz nicht mehr. Deshalb
startet die leere Versionsprüfung zuerst genau diese App-Installation, bevor sie
die importierte Welt laden darf. Kopierte Windows-Logs zählen nicht.

Das ist **kein Vergleich mit der Client-Version oder der neuesten Steam-Version**.
SteamCMD installiert den verfügbaren Build; der Gate pinnt und lädt keinen alten
Build herunter. Die Steam-Updateprüfung im Betrieb ist davon unabhängig.
Ein anderer Build mit nachgewiesener Version 42.21.0 kann passieren; eine neue
Spielversion wie 42.22.0 bleibt für importierte Welten gesperrt. Der Gate gilt auch
nach dem Erststart und für wiederhergestellte Importwelten. Für ein späteres
Versionsupgrade muss diese Code-Vorgabe bewusst weiterentwickelt und die Migration
getestet werden; eine Änderung in .env.live genügt nicht. Frische leere Testwelten
ohne Migrationsmarker unterliegen diesem Gate nicht.

## 7. Finale Windows-Welt als privaten File-Drop importieren

Der Weg der privaten Dateien ist:

| Schritt | Rechner und Pfad | Ergebnis |
| --- | --- | --- |
| Export der gestoppten Quelle | Windows: `C:\PZ\instances\szs` → privater Transferordner | szs-final.tar.gz und szs-final.tar.gz.sha256 |
| Übertragung mit SCP/SFTP | Windows-Transferordner → Debian: ~/pz-docker-server/imports/ | Beide Dateien liegen auf dem Linux-Host, außerhalb von Git |
| Import | Debian: ./pz --env-file .env.live import | Validierte Welt im Docker-Volume pzlive_data; noch gestoppt |
| Späterer Linux-Export | Debian: Backup → exports/private-handoff.tar.gz | Portables Backup mit Manifest und SHA-Sidecar, siehe Abschnitt 10 |

Windows-Export ist das Archivieren der bisherigen Instanz. Linux-Import liest
dieses Archiv und richtet die neue Live-Welt ein. Der spätere Linux-Export wird
aus einem Linux-Betriebsbackup erzeugt und enthält zusätzlich portable
Verwaltungsprovenienz. Keines dieser Archive gehört in Git.

**Die schon abgenommene Docker-Testkopie und alte Testarchive sind nicht die finale
Quelle.** Vor dem endgültigen Umzug am alten Windows-Server alle Spieler abmelden,
kontrolliert `save` und `quit` ausführen und den vollständigen Prozess-Exit prüfen.
Den automatischen Wiederstart dort deaktivieren. Erst den danach konsistenten
aktuellen szs-Bestand archivieren. Wird danach wieder gespielt, ist dieses Archiv
nur historisch: nach dem letzten Spielbetrieb nochmals frisch exportieren.

Es wird kein zusätzlicher Windows-Exporthelfer benötigt. Ein privates tar.gz kann
mit dem vorhandenen Archivwerkzeug erstellt werden. Der Linux-Eingang akzeptiert:

- Ein Persistence-Archiv mit **Server/, Saves/, db/, Lua/, options.ini** direkt
  an der Archivwurzel, ohne App, Workshop, Cache, Logs oder native Alt-Backup-ZIPs.
- Das vorhandene portable Backupformat mit data/, optional state/, manifest.json
  und _backup.json. Hier werden Manifest und vollständige Pending-Provenienz geprüft.
- Das ältere Source-Transferformat instance/ plus source-manifest.json bleibt
  kompatibel, ist aber nicht für den neuen File-Drop erforderlich.

Die aktive Welt umfasst die vier szs-Konfigurationsdateien, komplette Multiplayer-
Welt einschließlich Player-/Vehicle-DB und Journals, Account-DB inklusive vorhandener
Journal/WAL-Dateien, persistente Lua-Moddaten und options.ini. Andere Instanzdateien
werden privat als Referenz gehalten. Beim rohen Persistence-Archiv erzeugt Linux
das Inventar und die SHA-256-Manifeste selbst; ein eingebettetes Windows-Manifest
ist hierfür nicht erforderlich. Kopien und SQLite integrity_check werden vor der
fertigen Importmarkierung geprüft. Ungültige oder unvollständige Daten verweigern
den Import. Aktives altes Windows-Pending vor dem Export kontrolliert abschließen;
nicht blind einen v1-Ops-Record in portable State-Dateien kopieren.

Ein SHA-256-Sidecar `szs-final.tar.gz.sha256` enthält als einzelne ASCII-/UTF-8-
Textzeile entweder den Hash allein oder `HASH  szs-final.tar.gz` (kein UTF-16).
Archiv und Sidecar separat von Git übertragen, z.B.:

**Auf Windows:** Im vorhandenen Archivwerkzeug als Quelle den gestoppten Ordner
`C:\PZ\instances\szs` öffnen und ausschließlich Server/, Saves/, db/, Lua/
und options.ini auswählen. Lua-Diagnose-.log-Dateien weglassen. Als tar.gz im
privaten Transferordner speichern, beispielsweise `C:\PZ-Transfer\szs-final.tar.gz`.
Die fünf Einträge müssen direkt an der Archivwurzel stehen, nicht unter szs/.
Den SHA-256-Wert mit Get-FileHash ermitteln und einen ASCII-Sidecar erstellen:

```powershell
$ErrorActionPreference = 'Stop'
$PzArchive = 'C:\PZ-Transfer\szs-final.tar.gz'
$PzHash = (Get-FileHash -LiteralPath $PzArchive -Algorithm SHA256).Hash
[System.IO.File]::WriteAllText($PzArchive + '.sha256', $PzHash + "`n", [System.Text.Encoding]::ASCII)
scp $PzArchive ($PzArchive + '.sha256') BENUTZER@SERVER:~/pz-docker-server/imports/
if ($LASTEXITCODE -ne 0) { throw 'SCP-Übertragung fehlgeschlagen' }
```

BENUTZER@SERVER vorher ersetzen. Das sind manuelle Transferbefehle, kein neuer
Windows-Exporthelfer. Bei SFTP dieselben beiden Dateien in imports/ hochladen.
Wenn das Archiv auf einem anderen Rechner liegt, dort stattdessen:

```bash
# Auf dem Rechner mit dem privaten Archiv, aus dessen Transferordner.
scp szs-final.tar.gz szs-final.tar.gz.sha256 BENUTZER@SERVER:~/pz-docker-server/imports/
```

Auf Debian, aus dem Repositoryverzeichnis:

```bash
chmod 640 imports/szs-final.tar.gz imports/szs-final.tar.gz.sha256
sudo chgrp 1000 imports/szs-final.tar.gz imports/szs-final.tar.gz.sha256
docker compose --env-file .env.live build pz-server pz-ops
./pz --env-file .env.live import --archive imports/szs-final.tar.gz \
  --sha256-file imports/szs-final.tar.gz.sha256
docker compose --env-file .env.live up -d --wait --wait-timeout 120 pz-server pz-ops
./pz --env-file .env.live status
./pz --env-file .env.live version
./pz --env-file .env.live config-state
./pz --env-file .env.live start
./pz --env-file .env.live health
./pz --env-file .env.live workshop-status
```

Das Live-Datenvolume muss **neu und leer** sein. Beide Live-Control-Dienste müssen
beim Import gestoppt sein. Der Import prüft Archiv-SHA, Pfade, Inventar, Kopien,
SQLite und Konfigurationsreihenfolge, erzeugt ein geschütztes pristine Backup und
setzt **desired=false**. Java startet erst mit dem separaten `start`-Befehl.
Ein Nicht-42.21.0-Build führt zu BLOCKED_VERSION; den Gate nicht abschwächen.

Nach READY mit dem realen Client verbinden und Account, lebenden Charakter,
erwartete Welt und repräsentative Mods prüfen. Bei Wechsel von pztest zu Live den
PZ-Client vorher vollständig beenden und neu starten. Das Spielerpasswort für Live
kommt aus der privaten bisherigen Serverkonfiguration, nicht aus Git.

## 8. Betrieb: Live und Test wechseln

Normal läuft nur Live. Für einen Test nach Abmeldung aller Spieler:

```bash
./pz --env-file .env.live save
./pz --env-file .env.live stop
docker compose --env-file .env.live stop pz-ops pz-server
docker compose --env-file .env.test up -d --wait --wait-timeout 120 pz-server pz-ops
./pz --env-file .env.test start
# Test durchführen, dann alle Testspieler abmelden.
./pz --env-file .env.test stop
docker compose --env-file .env.test stop pz-ops pz-server
docker compose --env-file .env.live up -d --wait --wait-timeout 120 pz-server pz-ops
./pz --env-file .env.live start
```

Bei aktivem Discord den Live-Bot vor dem Wechsel ebenfalls mit dem discord-Profil
stoppen und anschließend wieder starten. Nie beide Projekte auf derselben Host-IP
mit denselben Ports betreiben. Für späteren Parallelbetrieb ist eine zweite Host-IP
oder ein bewusst geplantes Netzwerkdesign nötig. Alternative externe Ports bleiben
technisch einstellbar, sind **nicht für den abgenommenen Live-Pfad verifiziert**.
Der frühere Versatz 17261/17262 auf interne 16261/16262 führte beobachtet zu
Connection Failed nach beginnendem Steam-Handshake. 1:1 ist der unterstützte Pfad.

## 9. Verwaltung und Wiederanlauf

Die folgenden Befehle sind **einzelne Bedienbeispiele**, kein gemeinsam auszuführendes
Script. JOB_ID und imports/private-plan.json durch tatsächlich vorhandene Werte ersetzen.
Mod-Pläne vorher nach dem [Planformat](docs/MOD-PLAN-LIFECYCLE.md) erstellen und
prüfen; --apply nur für den bewusst freigegebenen Plan verwenden.

```bash
./pz --env-file .env.live status
./pz --env-file .env.live health
./pz --env-file .env.live players
./pz --env-file .env.live logs
./pz --env-file .env.live save
./pz --env-file .env.live stop
./pz --env-file .env.live restart
./pz --env-file .env.live backup
./pz --env-file .env.live update
./pz --env-file .env.live workshop-status
./pz --env-file .env.live workshop-update
./pz --env-file .env.live config-state
./pz --env-file .env.live apply-mod-plan imports/private-plan.json
./pz --env-file .env.live apply-mod-plan imports/private-plan.json --apply
./pz --env-file .env.live maintenance on --reason 'Geplante Arbeit'
./pz --env-file .env.live maintenance off
./pz --env-file .env.live jobs
./pz --env-file .env.live job JOB_ID
```

`stop` speichert und beendet kontrolliert; unbekannte Spieler/RCON verweigern den
Eingriff. `--force` erlaubt nur einen bewussten Save/Quit bei bekannter Belegung,
keinen Kill und keinen unbekannten Zustand. Logs nur privat prüfen: sie können
Spieler-/Chatdaten enthalten, auch wenn bekannte Zugangsdaten gefiltert werden.

`maintenance on` unterdrückt automatische Aufgaben; ein laufender Spielprozess
wird dadurch nicht gestoppt. Für Arbeiten an einer ruhenden Welt zusätzlich stop
ausführen. Lesen, save/stop, Planarbeit, config-commit, export und recover bleiben
verfügbar. Vor start/restart/install/update/backup/workshop-update/Online-Restore
zuerst `maintenance off` ausführen; diese Jobs melden sonst OPERATOR_MAINTENANCE.

Ein Backup umfasst Server/Saves/db/Lua/options und kohärente Mod-/Config-Provenienz.
Ein Backup bei laufendem Spiel speichert, stoppt und startet anschließend frisch;
ein absichtlich gestoppter Server bleibt gestoppt. Vier neueste plus bis zu vier
ältere Wochenanker werden behalten;
geschützte pristine-/Referenz-Backups werden nicht rotiert. Alle Backup-Alterswerte
verwenden denselben abgeschlossenen Katalog.

`update` erzeugt zuerst ein Safety-Backup und installiert explizit mit SteamCMD.
`workshop-update` benötigt einen laufenden Server und sichere Spielerlage, erstellt
ein Backup und führt einen frischen Start mit Workshop-Prüfung aus. Ein Upstream-
Workshop-Update allein erzwingt keinen automatischen Neustart. Jobs laufen unabhängig
von SSH-/CLI-/Discord-Verbindungen weiter; `--detach` gibt nur die Job-ID zurück.

**Intent:** `start` setzt desired=true; `stop` setzt dauerhaft desired=false.
Containerstarts starten die Verwaltungsdienste. Steam-Installationen laufen über
install/update oder einen fälligen Wartungsjob, nicht direkt aus dem Container-Entrypoint.
Nach einem Reboot laufen Reconciliation und fällige Wartung wieder an.
Wenn Docker und beide Control-Dienste wieder laufen, startet die Reconciliation
einen fehlenden gewünschten Spielprozess bei freier Wartung/Recovery erneut.
Sie prüft beim Booten und ungefähr alle fünf Minuten; Startreihenfolge kann den
ersten Versuch verzögern. Ein vorhandener degradierter Prozess wird nicht getötet.
Manuell gestoppte Testcontainer bleiben mit unless-stopped gestoppt. Deshalb
vor Reboot/Wechsel alle unbenutzten Projekte sauber stoppen und Ports freihalten.
Unterbrochene Jobs setzen false Intent/Recovery und werden nicht blind wiederholt.

Zusätzlich prüft die stündliche Wartung ungefähr alle sechs Stunden den Steam-Build
und nach 24 Stunden ohne reguläres Backup dessen Fälligkeit. Bei true Intent und
ohne Wartung/Recovery kann sie ein Update bzw. Backup einreihen; Änderungen erfordern
bekannte null Spieler. Bei Importdaten bleibt auch nach einem Update der 42.21.0-
Gate bestehen. Ein anderer installierter Build kann daher den Wiederstart blockieren;
vor einem geplanten Versionswechsel Kompatibilität und Wiederherstellung vorbereiten.

### INI und Lua bearbeiten

Die aktiven Dateien liegen im Docker-Datenvolume, im Container unter
/pz/data/Server/: szs.ini, szs_SandboxVars.lua, szs_spawnpoints.lua und
szs_spawnregions.lua. .env.live enthält Deploymentwerte wie Heap und Ports;
Sandbox-/Servereinstellungen stehen in diesen INI-/Lua-Dateien. Lua/ ist dagegen
Mod-Persistenz und kein Ersatz für Server/szs_SandboxVars.lua.

Vorher alle Spieler abmelden. Die Controls bleiben für diese Arbeit gestartet;
nur der Spielprozess wird gestoppt. Das Beispiel bearbeitet SandboxVars:
Es setzt voraus, dass config-state keinen offenen Mod-Plan (pending=false) meldet;
einen vorhandenen Plan zuerst über dessen frischen Start/Recovery abschließen.

```bash
./pz --env-file .env.live stop
./pz --env-file .env.live backup
./pz --env-file .env.live maintenance on --reason 'INI/Lua bearbeiten'
./pz --env-file .env.live config-state

umask 077
mkdir -p runtime/live-config
PZ_CONFIG_FILE=szs_SandboxVars.lua
docker compose --env-file .env.live cp "pz-ops:/pz/data/Server/$PZ_CONFIG_FILE" "runtime/live-config/$PZ_CONFIG_FILE"
nano "runtime/live-config/$PZ_CONFIG_FILE"
docker compose --env-file .env.live exec -T pz-ops python -c 'import sys; from pathlib import Path; from pzops.util import atomic_bytes; atomic_bytes(Path("/pz/data/Server") / sys.argv[1], sys.stdin.buffer.read())' "$PZ_CONFIG_FILE" < "runtime/live-config/$PZ_CONFIG_FILE"

./pz --env-file .env.live config-state
./pz --env-file .env.live maintenance off
./pz --env-file .env.live start
./pz --env-file .env.live health
./pz --env-file .env.live config-state
```

Für allgemeine INI-Einstellungen PZ_CONFIG_FILE=szs.ini setzen; für Spawn-Lua
entsprechend einen der beiden anderen genannten Dateinamen. Nur existierende
Dateien der aktiven Instanz bearbeiten. runtime/ ist gitignoriert und bleibt
privat: insbesondere die INI kann Passwörter enthalten. Der Rücktransfer schreibt
atomar als Dienst-UID 1000; keine Volume-Mounts auf dem Host direkt bearbeiten.
Der Start übernimmt die neue Konfiguration und bestätigt die Baseline erst nach
frischem READY. config-state sollte dann none und pending=false melden.
Es gibt keine vorgezogene vollständige Prüfung der Lua-Syntax oder Mod-Kompatibilität;
bei Startfehlern Job und private Logs prüfen und das zuvor erzeugte Backup bewahren.

WorkshopItems, Mods und Map in der INI über den folgenden Mod-Plan ändern.
config-commit speichert nur den aktuellen Konfigurationsstand als Baseline;
es lädt keine Einstellungen ins Spiel und kann keinen offenen Mod-Plan bestätigen.
Beim obigen Ablauf ist es nicht nötig, weil der erfolgreiche frische Start
die Baseline bereits bestätigt.

### Mods hinzufügen oder entfernen

Ein Workshop-Item hat eine numerische Workshop-ID; ein enthaltenes Mod hat eine
eigene Mod-ID. Ein Item kann mehrere Mods/Varianten enthalten. Die gewünschten
IDs und Abhängigkeiten vorab bestimmen; es wird keine Variante automatisch gewählt.
Planschlüssel Add/RemoveWorkshopItems betreffen Downloads, Add/RemoveMods die
aktivierten Mods, Add/RemoveMaps die Kartenreihenfolge (INI-Schlüssel Map).

Eine private JSON-Datei unter imports/private-plan.json anlegen. Dieses Beispiel
ist synthetisch: **alle IDs vor Apply durch die tatsächlich gewünschten ersetzen**.
Nicht benötigte Add-/Remove-Zeilen weglassen; zum reinen Entfernen nur Remove-Zeilen
verwenden, zum reinen Hinzufügen nur Add-Zeilen:

```json
{
  "Description": "Modwechsel nach Betreiberprüfung",
  "RemoveWorkshopItems": ["100"],
  "RemoveMods": ["OldExampleMod"],
  "AddWorkshopItems": ["300"],
  "AddMods": ["NewExampleMod"]
}
```

Ein Workshop-Item erst entfernen, wenn daraus kein aktivierter Mod mehr benötigt
wird. Before/After können die Ladereihenfolge von Mods/Karten gezielt festlegen,
z.B. {"Id": "NewExampleMod", "Before": "ExistingExampleMod"}; der Anker muss
vorhanden sein. Kartenänderungen und das Entfernen weltrelevanter Mods benötigen
eine passende Kompatibilitätsprüfung; das Planformat kann deren Spielwirkung nicht
automatisch beweisen. Details: [Mod-Planformat](docs/MOD-PLAN-LIFECYCLE.md).

Vorher alle Spieler abmelden. Für den vorbereiteten und geprüften Plan:

```bash
./pz --env-file .env.live stop
./pz --env-file .env.live backup
./pz --env-file .env.live maintenance on --reason 'Mods ändern'
nano imports/private-plan.json
./pz --env-file .env.live apply-mod-plan imports/private-plan.json
```

Die Vorschau zeigt Before und Expected einschließlich Reihenfolge. Nur wenn diese
genau der gewünschten Änderung entsprechen, die nächsten Befehle ausführen:

```bash
./pz --env-file .env.live apply-mod-plan imports/private-plan.json --apply
./pz --env-file .env.live config-state
./pz --env-file .env.live maintenance off
./pz --env-file .env.live start
./pz --env-file .env.live health
./pz --env-file .env.live workshop-status
./pz --env-file .env.live config-state
```

Apply schreibt die INI samt unveränderlicher Plan-/Vorher-Provenienz und setzt
pending; es startet und lädt noch nichts herunter. Der frische Start prüft die
exakten erwarteten Mod-/Workshop-/Kartenlisten, erstellt bei Pending ein zusätzliches
Safety-Backup und lässt PZ die benötigten Workshop-Inhalte laden. Erst nach READY
wird pending bestätigt und entfernt. Bei Fehlschlag bleibt es bestehen; nicht
durch config-commit oder Löschen von Markern umgehen. Danach die Änderung mit dem
Client prüfen. Bereits heruntergeladene, entfernte Items können im Cache bleiben;
das Entfernen im Plan ist keine Cache-Bereinigung.

## 10. Export, Restore und Rollback

Diese Abläufe bei einem geplanten Handoff oder einer Wiederherstellung ausführen.
Vor dem normalen Weiterbetrieb alle hierfür verwendeten temporären Projekte
kontrolliert stoppen und die gewünschte Instanz bewusst wieder aktivieren.

Ein aktuelles privates Linux-Backup kann mit den vorhandenen Tools exportiert werden:

```bash
./pz --env-file .env.live stop
./pz --env-file .env.live backup
# Zurückgegebenen Backupnamen einsetzen.
docker compose --env-file .env.live stop pz-ops pz-server
./pz --env-file .env.live export --backup BACKUP_NAME --output exports/private-handoff.tar.gz
sudo chown "$(id -u):1000" exports/private-handoff.tar.gz exports/private-handoff.tar.gz.sha256
sudo chmod 640 exports/private-handoff.tar.gz exports/private-handoff.tar.gz.sha256
```

Das ist der **spätere Export vom Linux-Server**, unabhängig vom Windows-Export
in Abschnitt 7. Quelle ist BACKUP_NAME im privaten Backupvolume; Ziel sind
~/pz-docker-server/exports/private-handoff.tar.gz und dessen .sha256-Datei auf
dem Linux-Host. Beide Dateien für die Übergabe vom Linux-Host herunterladen
(z.B. per SFTP), auf dem nächsten Host unter imports/ hochladen und dort mit
restore --archive wiederherstellen. Lokaler Restore kann direkt exports/ lesen,
wie im folgenden Beispiel.

Der Export liefert tar.gz und externen .sha256-Sidecar; interne Manifest-/Metadata-
Dateien bleiben im Archiv. Git allein kann eine private Welt nicht wiederherstellen.
Tools schreiben den Export zunächst privat als UID 1000; chown/chmod machen ihn
für den SSH-Betreiber lesbar und erhalten die Import-Leserechte für GID 1000.

Restore bevorzugt ein **neues** Projekt mit passenden Servernamen, eigener
Konfiguration und Secrets. Für das gerade auf diesem Host exportierte Archiv:

```bash
cp .env.live .env.restore
chmod 600 .env.restore
sed -i 's/^COMPOSE_PROJECT_NAME=.*/COMPOSE_PROJECT_NAME=pzrestore/' .env.restore
sed -i 's|^PZ_SECRETS_DIR=.*|PZ_SECRETS_DIR=./secrets/restore|' .env.restore
./pz --env-file .env.restore init-secrets
sudo chown 1000:1000 secrets/restore/api.token secrets/restore/discord.token
docker compose --env-file .env.restore build pz-server pz-ops
./pz --env-file .env.restore restore --archive exports/private-handoff.tar.gz \
  --sha256-file exports/private-handoff.tar.gz.sha256
```

Restore validiert Archive und kopiertes Staging, startet nie selbst und setzt
desired=false. Das Restoreprojekt darf nicht parallel zu Live/Test auf denselben
Ports laufen. Bei ausdrücklich gesetzten App-/Workshop-Overrides in .env.live
diese nicht ungeprüft in das Restoreprofil übernehmen; das folgende Beispiel setzt
die normalen getrennten Projektvolumes voraus.
Ein von einem anderen Host hochgeladenes Archiv stattdessen unter imports/ verwenden
und wie in Abschnitt 7 lesbar vorbereiten. Zielprojekt/-Secretpfad müssen neu sein.

Vor dem ersten Restore-Start müssen Live und Test samt Controls gestoppt sein.
Für ein importiertes Backup die eigene leere Versionsprüfung auf dem neuen
pzrestore_app/pzrestore_workshop ausführen:

```bash
cp .env.versioncheck.example .env.restorecheck
sed -i 's/^COMPOSE_PROJECT_NAME=.*/COMPOSE_PROJECT_NAME=pzrestore-versioncheck/;s|^PZ_SECRETS_DIR=.*|PZ_SECRETS_DIR=./secrets/restorecheck|;s/pzlive_app/pzrestore_app/;s/pzlive_workshop/pzrestore_workshop/' .env.restorecheck
chmod 600 .env.restorecheck
./pz --env-file .env.restorecheck init-secrets
sudo chown 1000:1000 secrets/restorecheck/api.token secrets/restorecheck/discord.token
docker compose --env-file .env.restorecheck build pz-server pz-ops
./pz --env-file .env.restorecheck init-empty
docker compose --env-file .env.restorecheck up -d --wait --wait-timeout 120 pz-server pz-ops
./pz --env-file .env.restorecheck install
./pz --env-file .env.restorecheck start
./pz --env-file .env.restorecheck version
./pz --env-file .env.restorecheck stop
docker compose --env-file .env.restorecheck stop pz-ops pz-server
```

Nur bei bestätigter **42.21.0** anschließend die wiederhergestellte Welt starten:

```bash
docker compose --env-file .env.restore up -d --wait --wait-timeout 120 pz-server pz-ops
./pz --env-file .env.restore start
./pz --env-file .env.restore health
```

Online-Restore eines lokalen Backups: `restore --backup BACKUP_NAME`,
ebenfalls bei gestopptem Spiel/false Intent. Vorhandene Daten ersetzen erfordert
ausdrücklich `--confirm-replace` und erzeugt ein geschütztes Pre-Restore-Backup.

Vor Code-/Image-Upgrade aktuellen Backupnamen und Git-Commit notieren. Nach Save/Stop
Controls stoppen, Git aktualisieren, Images bauen und Controls wieder starten;
Version, Jobs und Health prüfen, dann bewusst starten. Code-Rollback über einen
bekannten Git-Commit ersetzt keine bereits geänderten Weltdaten. Bei Weltproblemen
ein geprüftes Backup in ein neues Projekt mit kompatibler PZ-/Mod-Version restoren.
SteamCMD bietet hier keinen automatischen Binär-Downgrade; keine Depot-IDs raten.
Persistente Volumes nicht als normalen Wartungsschritt löschen.

## 11. Optional Discord

Voraussetzung: Live ist wie in Abschnitt 7 aktiviert, seine Control-Dienste sind
gesund und Test-/Versionsprüf-/Restoreprojekte sind gestoppt. Den Bot immer mit
dem Profil der tatsächlich betriebenen Instanz verwenden.

PZ_DISCORD_GUILD_ID und PZ_DISCORD_RESTART_ROLE nur in der privaten .env.live setzen.
Den Bot-Token in secrets/live/discord.token schreiben und 0600/UID 1000 sicherstellen:

```bash
sudo nano secrets/live/discord.token
sudo chown 1000:1000 secrets/live/discord.token
sudo chmod 0600 secrets/live/discord.token
docker compose --env-file .env.live --profile discord build pz-discord
docker compose --env-file .env.live --profile discord up -d pz-discord
```

Kommandos: /pzstatus, /pzinfo, /pzmods, /pzip, /pzhealth, /pzrestart. Für /pzip
gewollte PZ_ADVERTISE_LAN/VPN/PUBLIC-Werte privat konfigurieren. Restart benötigt
die konfigurierte Rolle und bekannte null Spieler. Der Bot hat keine Weltmounts,
keinen RCON-Schlüssel und keinen Docker-Socket. Den alten Bot vor einem Tokenwechsel
stoppen. Live-Discord wurde ohne bereitgestellte Credentials nicht abgenommen.

## 12. Troubleshooting und Grenzen

- **Connection Failed nach Steam-Handshake:** zuerst native 1:1-UDP-Ports,
  Host-/Provider-Firewall und genau eine aktive Instanz prüfen.
- **Character Creation beim Wechsel von Test zu Live:** in der Abnahme einmal
  beobachtet; vollständiger Client-Neustart lud danach den bestehenden Charakter.
  Dies ist eine Beobachtung, keine bewiesene Erklärung des internen Clientzustands.
  Keine Charakterdaten deswegen löschen oder zurücksetzen.
- **START_PROCESS_EXITED / START_WORKSHOP_DOWNLOAD_FAILED:** `workshop-status`,
  aktuelles `logs` und Job prüfen. Current/Update/Missing/Unknown ändern sich
  upstream. Ein einmaliger Downloadfehler beweist keine Weltkorruption. Im
  beobachteten Fall war das Item später Current und der Start funktionierte.
  Keine Mods automatisch löschen oder die Welt wegen eines Fehlversuchs ändern.
- **STARTING_OR_DEGRADED:** fehlende UDP-/RCON-Evidenz; vorhandenen Prozess privat
  diagnostizieren. READINESS_TIMEOUT beendet ihn nicht automatisch.
- **BLOCKED_VERSION / APP_INSTALL_INCOMPLETE:** kompatiblen Build bzw. erfolgreiche
  explizite Installation herstellen; Gates nicht durch Markeränderungen umgehen.
- **STEAM_INSTALL_FAILED:** den Job und dessen privates Steam-Installationslog
  prüfen. Im Debian-Prüflauf scheiterte der erste Download mit SteamCMD
  „Missing configuration“; der erneute `install`-Aufruf installierte erfolgreich.
  Den fehlgeschlagenen Installationsbefehl mit demselben --env-file wiederholen.
  Dabei weder `init-empty` wiederholen noch Volumes löschen.
- **TARGET_NOT_EMPTY:** frisches Projekt wählen, keine privaten Daten entfernen.
- **Recovery:** `jobs`, Jobphase und private Journale prüfen. `recover` ist explizit;
  bei ambiger Apply-/Ack-Provenienz oder unterbrochener Restore-Publikation das
  Originalbackup in ein neues Projekt übernehmen und das alte Ziel offline lassen.
- **Berechtigungen:** Dienst-UID/GID 1000, private Secrets und Import-/Exportrechte
  prüfen; Dienste nicht als privileged starten.

Der separate menschliche Client-Test der hash-/DB-seitig verifizierten Restore-
Kopie wird bewusst nicht wiederholt. Diese Restgrenze ist **kein Migrationsblocker**.
Die Debian-13-Installation und die README-Befehle wurden mit neu erzeugten Testdaten
in isolierten Debian-Prüfumgebungen ausgeführt. Einrichtung des tatsächlichen Zielhosts
und finaler aktueller Windows-Cutover bleiben erforderlich; hier wird keine private
Welt erneut gestartet oder produktiv exportiert.

Details: [README-Befehlsprüfung](docs/README-CHECK.md), [Abnahme und Tests](docs/TEST-REPORT.md), [Linux/Cutover-Handoff](docs/LINUX-HANDOFF.md),
[Datenvertrag](docs/DATA-MIGRATION.md), [Architektur](docs/ARCHITECTURE.md),
[Mod-Lifecycle](docs/MOD-PLAN-LIFECYCLE.md), [Recovery](docs/TROUBLESHOOTING.md).

### Was GitHub CI prüft

Der Workflow [Synthetic validation](.github/workflows/ci.yml) läuft bei jedem Push
und Pull Request auf einem GitHub-Ubuntu-Runner mit Python 3.12. Er:

- checkt die vollständige Git-Historie aus und installiert die festgelegten
  Discord-Abhängigkeiten aus discord/requirements.lock;
- führt python -m unittest discover -s tests -v mit synthetischen Daten aus;
- kompiliert ops, server, discord, scripts und tests mit compileall;
- prüft die getrackten Dateien und die gesamte Historie mit audit-public-tree.py
  auf verbotene Runtime-/Weltdateien und erkannte Secret-/Privatwertmuster;
- löst Compose mit den Profilen discord und tools auf und prüft mit check-compose.py
  unter anderem UDP-Portgrenzen, Netztrennung, Capability-Drops und fehlende
  privilegierte Dienste bzw. Docker-Socket-Mounts.

Die CI baut/publiziert keine Docker-Images, installiert kein PZ, startet keinen
Spielserver und macht kein Deployment. Ein grüner Lauf belegt die Code-/Strukturtests,
keinen aktuellen Steam-/Workshop-Download oder menschlichen Client-Test. Der
Muster-Audit ist keine Garantie, beliebige neue Secrets automatisch zu erkennen.

Vor einem späteren Push Tests und `python3 scripts/audit-public-tree.py --history`
auch lokal ausführen; nur Code veröffentlichen.

Für einen späteren Push vorhandenen origin und Repository-Berechtigungen privat
prüfen und Git-Zugriff per SSH oder bestehender Git-Anmeldung sicherstellen:

```bash
git push --set-upstream origin main
```

Dieser Push ist hier nicht ausgeführt. Nur falls ein anderes lokales Repository
noch keinen origin besitzt, diesen zuerst mit der tatsächlich berechtigten URL
einrichten. Tokens gehören nicht in Remote-URLs oder Git-Dateien.

### Windows-Bedienung separat

Bestehende lokale Tests können weiter `./pz` durch `.\pz.ps1` ersetzen, z.B.
`.\pz.ps1 --env-file .env.test logs`. Der Logs-Aufruf verwendet ein Python-Modul
und keine verschachtelten Newline-/python--c-Escapes. Ein spezieller Windows-
Exporthelfer wird nicht eingeführt; Archivformat und Cutover-Voraussetzungen sind
im [Handoff](docs/LINUX-HANDOFF.md) beschrieben.
