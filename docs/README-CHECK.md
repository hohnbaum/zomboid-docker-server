# Prüfung der README-Befehle

Stand: **5. Oktober 2026**. Die Debian-Installation und die PZ-Betriebsabläufe aus
dem README wurden mit neu erzeugten Testdaten tatsächlich ausgeführt. Externe
Zugangsdaten und Veröffentlichungen wurden durch die unten genannten Prüfungen
ersetzt. Die vorhandene private Welt wurde nicht erneut gestartet.

## Umgebung und Methode

Die Installation lief über echtes SSH auf einer frischen Debian-13-amd64-VM mit
eigenem Kernel, systemd und Docker-Daemon. Geprüfte Versionen: Host-Python 3.13.5,
Docker Engine 29.8.2 und Compose v5.6.0. APT-Rückfragen wurden im unbeaufsichtigten
Test mit -y bestätigt. Der SSH-Benutzer hatte UID 1001, die PZ-Dienste UID/GID 1000.
Git clone verwendete ein Bundle des öffentlichen lokalen Codebestands; anschließend
wurden die geänderten Compose-/Testdateien übernommen. Private GitHub-Anmeldung
und Remote-URL sind damit nicht geprüft.

Die CPU-emulierte VM erreichte mit leeren 2-GiB-Instanzen READY. Dort traten jedoch
auch JVM-Segfaults auf, einschließlich beim 6-GiB-Start einer importierten Testwelt.
Deshalb wurden die vollständigen Spielabläufe zusätzlich auf nativer CPU in einem
separaten Debian-13-systemd-Testcontainer mit **eigenem Docker-Daemon** ausgeführt.
Dieser nutzte den Linux-Kernel von Docker Desktop, eigene PID-/Netzwerk-/Cgroup-
Namespaces und neue Datenvolumes. Kein Host-Docker-Socket, Hostnetzwerk, Host-PID-
Namespace oder Hostport wurde verwendet. Der verschachtelte Prüfharness benötigte
SYS_ADMIN/NET_ADMIN/SYS_PTRACE; die Produktdienste blieben unverändert ohne
Capabilities und privilegierten Modus. Der separate Daemon verwendete vfs/cgroupfs.

Spielversion, gelieferte JVM und GC-/JIT-Flags wurden nicht verändert. Test und
Versionsprüfprofile liefen mit 2g, Live/Restore mit den damals dokumentierten **6g**.
Test- und Live-App wurden vollständig neu mit SteamCMD heruntergeladen. Für das
dritte, unabhängige Restore-App-Volume wurden ausschließlich Vendor-Dateien der
neuen Testinstallation als Downloadcache kopiert: keine Welt, Logs oder Linux-
Versionsevidenz. Install und der eigene leere Linux-Start im Restoreprüfprofil
mussten trotzdem erfolgreich sein, bevor die importierte Restorewelt startete.

Die abhängigen Befehlsblöcke liefen mit Bash-Fehlerabbruch. Platzhalter wurden
durch tatsächlich erzeugte Archiv-/Backup-/Jobwerte ersetzt. Die Managementliste
wurde als einzelne Bedienbeispiele ausgeführt: backup/update bei gestopptem Spiel,
restart als expliziter Start und workshop-update bei laufendem Spiel. Der Mod-Plan
war ein gültiger synthetischer Plan ohne Änderungen oder externe Workshop-Items.

## Ergebnisse

| README-Abschnitt | Ausgeführte Prüfung | Ergebnis |
| --- | --- | --- |
| 1 | Architektur, Speicherplatz und RAM-Abfrage | PASS |
| 2 | APT, offizielles Docker-Repository/GPG, Pakete, systemd, hello-world, root/sudo, docker-Gruppe und neue SSH-Sitzung | PASS in der VM |
| 3 | Frischer Clone, ausführbarer Wrapper, getrennte Secrets, UID-1001-/GID-1000-Import-/Exportrechte | PASS |
| 4 | Build, init-empty, gesunde Controls, install/start, status/health/version/workshop-status und Compose-Status | PASS; READY, 42.21.0 / 25485538 |
| 4 | Password leer, RCON/Admin/API zufällig und privat; beide UDP-Sockets und authentifiziertes Nullspieler-RCON | PASS |
| 5 | DOCKER-USER-Regel und systemd-Unit; Boot-/Docker-Neustart-Persistenz | PASS |
| 6 | Save/Quit und Controlstop; unabhängige leere Versionsprüfung auf Live-App | PASS |
| 7 | Tatsächliches SCP, SHA-Sidecar/Rechte, roher Persistence-Import, Pristine und expliziter 6g-Live-Start | PASS; READY |
| 8 | Live → Test → Live auf 16261/16262; jeweils vorige Controls gestoppt | PASS |
| 9 | Native Logs, Spieler-/Konfigurationsabfragen, Save/Stop/Restart, Backup/Update/Workshop-Update, Plan-Preview/Apply, Wartung, Jobs und echte Job-ID | PASS |
| 9 | config-commit, recover und save --detach | PASS |
| 10 | Export mit lesbarem Archiv/Sidecar für UID 1001 | PASS |
| 10 | Archivrestore in neues Projekt, false Intent, eigene App-Versionsprüfung, expliziter 6g-Start | PASS; READY |
| 10 | Online-Restore des erzeugten lokalen Backups mit --confirm-replace und false Intent | PASS |
| 11 | Nano verfügbar, Token-Dateirechte, Discord-Imagebuild und Compose-Aktivierung als Dry-Run | PASS; keine echte Anmeldung |
| 12 / Git | Syntax aller 21 Bash-Blöcke, Compilation, Compose-Prüfung, Public-tree/History-Audit und lokaler Push-Dry-Run | PASS; kein GitHub-Push |

Nach einem echten **VM-Kernel-Reboot bei gestopptem Spiel** waren SSH, Docker und
die Firewallunit wieder aktiv. Der native systemd-Prüfcontainer wurde anschließend
mit laufender Restorewelt kontrolliert über systemctl reboot neu gestartet:
true Intent führte durch Reconciliation zu **READY mit neuer Spielgeneration und
bekannten 0 Spielern**. Der manuell gestoppte Test blieb offline. Danach blieb
false Intent nach systemctl restart docker.service offline; die Firewallunit wurde
erneut ausgeführt, und die UDP-Regel war vorhanden. Das ist ein Namespace-/Daemon-
Neustart auf nativer CPU, kein Kernel-Reboot mit laufendem Spiel oder Stromausfall.

Runtime-Prüfung der Produktdienste: UID/GID 1000, privileged=false, cap_drop ALL,
CapEff=0, NoNewPrivs=1 und aktiver Seccomp-Filter. Linux-Unit-Suite nach der
Healthcheck-Änderung: **115 Tests, PASS, 1 Skip**; Windows: **115 Tests, PASS,
6 Skips**. Die API-Regression prüft den authentifizierten Ping und die Ablehnung
eines falschen Tokens. Private Quellenprüfung: **44 erfasste Dateien, 0 geändert**.

## Korrigierte Anweisungen und Grenzen

Das README wartet nun auf gesunde Controls, setzt Fehlerabbruch voraus und hält
Initialisierung/Import von Wiederholungsversuchen getrennt. Ergänzt wurden fehlende
Pakete, private Env-Dateirechte, persistente UDP-Regeln, lesbare Exportdateien für
andere Host-UIDs und der vollständige Versionsprüfablauf vor einem Restore-Start.
Restore verwendet den tatsächlich zuvor erzeugten Exportpfad. Die Ops-Healthcheck-
Abfrage importiert nur den authentifizierten API-Client; beide Control-Checks haben
10 Sekunden Timeout. Wartungs-, Backup- und Boot-Aussagen entsprechen dem Code.

SteamCMD meldete beim ersten Installationsversuch einzelner neuer Profile
**Missing configuration / STEAM_INSTALL_FAILED**. Die Befehlsfolge wurde angehalten;
derselbe install-Befehl wurde ohne erneutes init-empty wiederholt und erfolgreich
abgeschlossen. Das README dokumentiert diese beobachtete Wiederholung ausdrücklich.

Provider-Firewall/NAT, GitHub-Berechtigungen, echte Discord-Anmeldung/Rollen sowie
der finale Windows-Cutover und dessen menschlicher Client-Check bleiben vom
tatsächlichen Zielbetrieb abhängig. Interaktive Token-Eingabe wurde nicht durch
Fake-Credentials ersetzt. Die unabhängigen Spielstarts hier benutzen synthetische
Welten ohne private Mods; die frühere menschliche Abnahme der privaten Modwelt bleibt
im [Testbericht](TEST-REPORT.md) dokumentiert. Ein weiterer menschlicher Test ihrer
bereits verifizierten Restorekopie wird weiterhin bewusst nicht durchgeführt.

## Ergänzung: Betreiberfragen und neue Bedienbeispiele

Das README verwendet nun den tatsächlichen öffentlichen origin statt einer
Platzhalter-URL und erklärt den bestehenden CI-Workflow. Der Workflow selbst
bleibt unverändert: synthetische Tests, Compilation, Public-tree/history-Audit
und Compose-Grenzprüfung; kein Image-Build, Spielstart oder Deployment.

Die neue .env.live.example verwendet **8g**, leere Test-/Versionsprüfprofile
weiterhin 2g. Bestehende private Env-Dateien wurden nicht geändert. Die obigen
realen Live-/Restore-Starts belegen weiterhin 6g; ein neuer Spielstart mit 8g
wurde für diese Dokumentationsergänzung nicht ausgeführt.

Zu diesem Zwischenstand war der fest codierte, dauerhafte 42.21.0-Gate noch
vorhanden und wurde erklärt. **Die nachfolgende Korrektur entfernt diese Sperre.**
Die SteamCMD-Installationspolitik bleibt erhalten. Der genaue
Dateiweg vom Windows-Persistence-Archiv über imports/ ins Linux-Datenvolume sowie
der spätere Linux-Backup-Export stehen getrennt im README und Handoff.

Zusätzlich geprüfte Bedienbeispiele:

- **INI/Lua:** tatsächlich mit Compose aus einem eigenen synthetischen Datenvolume
  kopiert, privat bearbeitet und mit der wörtlichen Python-Transportzeile aus dem
  README atomar zurückgeschrieben. Bytegleichheit einschließlich CRLF, Dienst-UID
  1000 und Dateimodus 0600 bestätigt. Der kurzlebige Prüfdienst hatte kein Netzwerk,
  keinen Host-Socket und keine privaten Datenmounts. Kein echter Spielstart für
  diesen reinen Transportcheck.
- **Windows-SHA/SCP:** PowerShell-Block geparst, Get-FileHash und ASCII-Sidecar mit
  synthetischem Eingang praktisch ausgeführt; Produkt-Checksum-Prüfer akzeptiert
  den Sidecar. SCP-Argumente mit lokalem Ersatz geprüft; kein weiterer SSH-Transfer.
- **Mod-Pläne:** Add-/Remove-/Reihenfolge-/Pending-Ablauf anhand des vorhandenen
  Lifecycle-Codes dokumentiert; synthetischer JSON-Plan durch Produktparser und
  Vorschau geprüft. Die bestehenden Apply-/Ack-Regressionen wurden erneut ausgeführt.
- **Statische Prüfung:** 24 Bash-Blöcke mit echtem Bash -n, 17 lokale Markdown-
  Links und alle vier öffentlichen Env-/Compose-Beispiele geprüft. Live löst
  für Server/Ops auf 8g auf, Test/Versionsprüfung auf 2g.
- **Regression:** Windows **115 Tests PASS, 6 Skips**; Linux/Python 3.12 mit den
  festgelegten Discord-Abhängigkeiten **115 Tests PASS, 1 Skip**. Compilation und
  Public-tree/history-Audit erneut bestanden.

Die Linux-Regression lief ohne Netzwerk mit einer Kopie ausschließlich öffentlicher
Code-/Testdateien im Container. Der eigene Container für den Konfigurationstransport
ist entfernt; dessen synthetisches Testvolume bleibt erhalten. Frühere private
Quelldaten, Testwelten und Archive wurden für diese Ergänzung nicht verwendet.

## Korrektur: Reguläre PZ-Updates für importierte Welten

Die dauerhafte 42.21.0-Sperre war mit dem normalen Betrieb unvereinbar und wurde
aus Start und Backupimport entfernt. Alte required_version-Marker werden weiter
gelesen, dienen aber nur als Provenienz. Neue Imports verwenden version_policy=
steam-public; portable Backups behalten ihre deklarierte Quellversion, rohe
Persistence-Archive bleiben hinsichtlich der Quellversion unbekannt.

Ein vollständig installierter Build darf vor seinem ersten Versionsnachweis
starten; der Nachweis entsteht aus diesem Linux-Start und muss zur installierten
Steam-Build-ID gehören. READY verlangt ihn jetzt zusätzlich zu eigenem Prozess,
UDP und authentifiziertem RCON. APP_INSTALL_INCOMPLETE, fehlende Build-ID,
Pristine-/Hash-/SQLite-/Pending-Prüfungen und die sichere Spielerpolitik bleiben
aktiv. Eine optionale leere Probe ist nicht bei jedem Update erforderlich.

Neue Regressionen prüfen den synthetischen Wechsel 42.21.0 → 42.22.0 mit altem
Importmarker: Safety-Backup der alten Version vor SteamCMD, ungültig gewordene
alte Evidenz, Start mit zunächst unbekannter neuer Version, neuer Nachweis und
READY sowie unveränderte Altmarker. Weiter geprüft sind Restore/Import neuerer
Backups, unbekannte Version bei laufendem Prozess, neuere Hauptversion im
Readiness-Test, fehlgeschlagene Installation und Backup-/false-Intent-Erhaltung.

Ergebnis: **122 Tests PASS**, Linux/Python 3.12 mit 1 Skip, Windows mit 6 Skips.
Compilation, 25 Bash-Blöcke und 18 lokale Markdown-Links sind geprüft. Neue
Server-/Ops-Images unter eigenem Prüfprojektnamen gebaut und ihre Codeimports
ohne Netzwerk/Datenmounts geprüft; alle vier öffentlichen Compose-Beispiele
bestehen die Grenzprüfung. Public-tree/history-Audit erneut bestanden. Die Tests
verwenden Fake-SteamCMD/Launcher/RCON und synthetische Welten; ein noch zukünftiger
echter 42.22-Release samt privater Modwelt ist damit nicht abgenommen. Die private
Welt und bestehende Runtime-Volumes wurden für diese Codeänderung nicht gestartet
oder verändert. Frühere reale 42.21.0-/6g-Prüfungen bleiben historische Evidenz.
