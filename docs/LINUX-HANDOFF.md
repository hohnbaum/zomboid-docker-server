# Debian-Handoff und finaler Cutover

Die bestehende private Docker-Testkopie ist erfolgreich mit einem menschlichen
Client abgenommen: Linux 42.21.0 / Build 25485538, READY, 111 Workshop-Items Current,
137 Mods, bestehender Account/lebender Charakter und erwartete interaktive Welt.
Details und Grenzen: [Testbericht](TEST-REPORT.md).

**Diese Kopie und frühere Archive sind nicht die endgültige Produktionsquelle.**
Der alte Windows-Server läuft weiter und hat neueren Spielstand. Git überträgt
ausschließlich Code; die Welt kommt als neuer privater File-Drop.

## 1. Zielhost vor dem letzten Spielabend vorbereiten

Die vollständigen Bash-Befehle stehen im [deutschen README](../README.md):

1. Debian 13 amd64 aktualisieren; Docker Engine/Compose aus dem offiziellen
   Docker-Debian-Repository, Git und Python einrichten.
2. Code klonen, .env.test/.env.live kopieren, getrennte Secrets erzeugen und
   UID/GID 1000-Leserechte sowie Import-/Exportrechte vorbereiten.
3. Host-/Provider-Firewall für UDP 16261/16262 vorbereiten. Docker-DNAT und
   DOCKER-USER berücksichtigen; nur UFW INPUT zu konfigurieren genügt nicht.
4. Leeren pztest installieren, READY/Health/Version prüfen, Client auf UDP 16261
   testen; Serverpasswort ist leer. RCON/Admin/API bleiben private Secrets.
5. Test kontrolliert stoppen **und seine Controlcontainer stoppen**, Volumes behalten.
6. Das unabhängige Live-App-Volume einmal mit der leeren temporären Versionsprüfung
   aus .env.versioncheck.example installieren/starten. Exakt 42.21.0 bestätigen,
   dann Spiel und Controls stoppen. Nur dieser temporäre Prüflauf teilt das
   Live-App-/Workshopvolume; seine leere Datenwelt ist eigenständig.

Live und dauerhafter Test haben getrennte **App-, Workshop-, Daten-, State-,
Control-, Backup- und Logvolumes sowie Secretdateien**. Kein neuer Host benötigt
Docker Desktop, WSL, PowerShell oder private Dateien aus der bisherigen Testphase.

## 2. Aktuellen Windows-Stand kontrolliert einfrieren

Alle Spieler abmelden, alten Server über seine vorhandene Verwaltung speichern
und mit quit vollständig beenden. Vollständigen Prozess-Exit prüfen und dessen
automatischen Wiederstart deaktivieren. Erst danach archivieren; kein Archiv
einer weiterlaufenden Welt als konsistent erklären.

Es gibt **keinen zusätzlichen Windows-Exporthelfer**. Mit dem vorhandenen privaten
Archivwerkzeug ein tar.gz des freigegebenen Persistence-Contracts erzeugen:

| Archivwurzel | Inhalt |
| --- | --- |
| Server/ | Vier aktuelle szs-Konfigurationsdateien; andere Instanzdateien ggf. nur Referenz |
| Saves/ | Vollständige Saves/Multiplayer/szs-Welt einschließlich Player-/Vehicle-DB, Journals und Mod-Persistenz |
| db/ | szs.db und vorhandene zugehörige WAL-/SHM-/Journaldateien |
| Lua/ | Persistente Lua-Moddaten; Diagnose-.log-Dateien ausschließen |
| options.ini | Vorhandene Optionen |

Diese Verzeichnisse liegen direkt an der Archivwurzel, ohne zusätzliches ./
oder umschließendes Instanzverzeichnis. App, Steam, Workshop, Cache, Logs,
historische native Backup-ZIPs und Verwaltungssecrets gehören nicht hinein.
Aktive alte Mod-/Config-Pending-Vorgänge vorher kontrolliert abschließen; alte
Windows-Ops-Records nicht ungeprüft als portable State-Provenienz übernehmen.

Der Linux-Importer erzeugt Inventar, SHA-256-Dateimanifeste, Modreihenfolge und
SQLite-integrity_check auf den extrahierten/kopierten Daten. Ein eingebettetes
Windows-Manifest ist beim rohen Persistence-File-Drop nicht erforderlich.
Das vorhandene portable schema-3-Backupformat und ältere Source-Transferformat
bleiben unterstützt; es entsteht kein zweiter Export-/Restoremechanismus.

Neben szs-final.tar.gz einen privaten szs-final.tar.gz.sha256 erzeugen, entweder
mit dem einzelnen SHA-256-Wert oder der Zeile HASH  szs-final.tar.gz. Das schützt
die Übertragung; Linux prüft zusätzlich enthaltene Dateien und Datenbanken.
Archiv und Sidecar bleiben außerhalb von Git.

**Wird nach dem Export erneut gespielt, ist das Archiv nur noch historisch.
Nach dem letzten Spielbetrieb erneut speichern, vollständig stoppen und frisch
exportieren.**

## 3. Privaten File-Drop übertragen und importieren

Vom Rechner mit den privaten Dateien, Platzhalter ersetzen:

~~~bash
scp szs-final.tar.gz szs-final.tar.gz.sha256 BENUTZER@SERVER:~/pz-docker-server/imports/
~~~

Auf Debian im Codeverzeichnis, mit gestopptem Test-/Versionsprüfprojekt und
**neuem leerem Live-Datenziel**:

~~~bash
chmod 640 imports/szs-final.tar.gz imports/szs-final.tar.gz.sha256
sudo chgrp 1000 imports/szs-final.tar.gz imports/szs-final.tar.gz.sha256
docker compose --env-file .env.live build pz-server pz-ops
./pz --env-file .env.live import --archive imports/szs-final.tar.gz \
  --sha256-file imports/szs-final.tar.gz.sha256
~~~

Der Wrapper bindet nur den privaten Archivordner read-only in netzlose Tools ein.
Der gemeinsame Parser prüft Pfade, Größen, Einträge und Hashes; Import prüft Kopien,
Inventar, INI-Reihenfolge und SQLite. Auch nach einem Volumewechsel veröffentlichte
Dateien werden erneut gehasht. Es entstehen private Referenzprovenienz, geschütztes
pristine Backup und zuletzt die Import-Fertigmarkierung. Der exakte 42.21.0-Gate
bleibt erhalten.

Erfolgreicher Import meldet **desired=false** und startet Java nicht.
Unvollständige/fehlerhafte Ziele offline lassen und ein neues Ziel verwenden;
vorhandene private Daten nicht für einen erneuten Versuch löschen.

## 4. Explizit starten und neuen finalen Stand prüfen

~~~bash
docker compose --env-file .env.live up -d --wait --wait-timeout 120 pz-server pz-ops
./pz --env-file .env.live status
./pz --env-file .env.live version
./pz --env-file .env.live config-state
./pz --env-file .env.live start
./pz --env-file .env.live health
./pz --env-file .env.live workshop-status
~~~

Nur mit bestätigter 42.21.0 und gültigem Pristine-Gate starten. READY verlangt
eigenen Prozess, beide UDP-Sockets und authentifiziertes RCON/lesbare Spielerzahl.
Mit vollständig neu gestartetem Client auf den Debian-Host, Port 16261 verbinden;
Account, lebenden Charakter, erwarteten **letzten** Spielstand und repräsentative
Mods prüfen. Live-Spielerpasswort kommt aus der privaten Windows-Konfiguration.
Anschließend erstes reguläres Backup erstellen und Ergebnisse privat festhalten.
Alten Server gestoppt halten, damit keine zwei auseinanderlaufenden Welten entstehen.

Ein einmaliges Workshop-Downloadproblem ist kein Nachweis einer beschädigten
Welt: Workshop-Status, aktuellen Job und privates Log prüfen, später bewusst
erneut starten. Keine Mods oder Charakterdaten automatisch entfernen.

## 5. Normalbetrieb, Testwechsel und Recovery

Normalerweise läuft nur Live. Für Tests Live Save/Quit und Controlcontainer
stoppen; dann Test auf **16261:16261/udp und 16262:16262/udp** starten. Anschließend
Test ebenso stoppen und Live starten. Gestoppte Datenvolumes bleiben erhalten.
Alternative Hostports sind konfigurierbar, aber nicht abgenommen: der frühere
Versatz 17261/17262 verursachte Connection Failed nach Steam-Handshake. Späterer
Parallelbetrieb braucht eine zweite Host-IP oder ein bewusstes Netzwerkdesign.

Backups, Archivexport, Restore in neue Ziele, Updates, Wartung, dauerhafte Jobs,
Reboot-Intent und optionales Discord stehen im README. Restore startet nicht
automatisch. Eine unterbrochene Publikation bleibt durch ihr Journal gesperrt;
Originalarchiv in ein neues Ziel übernehmen statt Marker zu entfernen.
Code-Rollback ersetzt keine Weltwiederherstellung und bewirkt keinen Steam-Downgrade.

Die bereits geprüfte private Restore-Kopie bekommt bewusst keinen separaten
menschlichen Client-Test mehr; das ist kein Migrationsblocker. Noch ausstehend
sind Einrichtung des tatsächlichen Zielhosts, finaler Cutover und optional echte
Discord-Abnahme. Die Debian-Installation ist inzwischen auf einer isolierten VM
mit neu erzeugten Testdaten geprüft. Diese Prüfung veröffentlicht nichts auf
GitHub und verändert weder Windows-Quellbestand noch frühere private Archive.
