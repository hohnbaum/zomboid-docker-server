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
- Für Live ist ein **6-GiB-Java-Heap** vorgesehen, dazu native JVM-/Mod-Speicher,
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

Die Git-URL durch die tatsächlich bereitgestellte URL ersetzen. Im lokalen
Übergaberepository ist bereits ein GitHub-origin eingerichtet; dessen private
URL wird hier nicht übernommen. Diese Finalisierung führt keinen Push aus.

```bash
PZ_REPOSITORY_URL='https://github.com/DEIN_ACCOUNT/pz-docker-server.git'
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
| .env.live | Importierte Produktionswelt szs | Eigenständig, Projekt pzlive | 6g |

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

## 7. Finale Windows-Welt als privaten File-Drop importieren

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

```bash
# Auf dem Rechner mit dem privaten Archiv; Platzhalter ersetzen.
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
Vor einem späteren Push Tests und `python3 scripts/audit-public-tree.py --history`
ausführen; nur Code veröffentlichen. CI verwendet ausschließlich synthetische Daten.

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
