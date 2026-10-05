# Abnahme und Testbericht

Stand: **5. Oktober 2026**. Dieser Bericht trennt selbst ausgeführte synthetische/
Runtime-Prüfungen von der inzwischen vom Betreiber bestätigten menschlichen
Abnahme. Private Identitäten, Charakter-Hashes, Koordinaten, Zugangsdaten und
Deploymentadressen bleiben außerhalb des öffentlichen Repositorys.

## Ergebnis der privaten Abnahme

Die importierte private **szs-Testkopie ist erfolgreich abgenommen**. Die frühere
Ressourcengrenze vom 2. Oktober und die damals ausstehende Client-Abnahme sind
kein aktueller Migrationsblocker mehr. Der Betreiber bestätigt:

| Prüfung | Ergebnis |
| --- | --- |
| Linux-Spielversion | Exakt 42.21.0 / Steam Build 25485538 |
| Importierter Server | READY |
| Workshop | Alle 111 konfigurierten Items anschließend Current |
| Mods | Alle 137 konfigurierten Mods vorhanden; repräsentative Mods im Spiel funktional |
| Menschlicher Client | Verbindung, bestehender Account und lebender Charakter erfolgreich |
| Welt | Interaktiv und im erwarteten bisherigen Zustand |
| Charakterpersistenz | Vorheriger Datensatz zwischen geschütztem known-good Backup, erstem Daily-Backup und Live-Daten bytegenau unverändert |
| SQLite | Alle beteiligten Datenbanken: integrity_check=ok |

Beim direkten Instanzwechsel im laufenden Client erschien einmal der Character-
Creation-Screen. Nach vollständigem Beenden und Neustarten des PZ-Clients wurde
der bestehende Charakter korrekt geladen. Das ist eine beobachtete Abhilfe,
**keine bewiesene interne Ursache** und kein Anlass, Charakterdaten zu verändern.

Die separate importierte Restore-Kopie wurde bereits automatisch mit Hashes,
Inventar und Datenbankprüfungen verifiziert. Ein zusätzlicher menschlicher Client-
Test dieser Kopie wird bewusst nicht durchgeführt. Diese Restgrenze ist
**kein Blocker für die Migration**.

**Die Docker-Testkopie ist nicht die finale Produktionsquelle.** Auf dem weiterhin
laufenden Windows-Server entsteht neuerer Spielstand. Der finale File-Drop muss
nach dem letzten Spielbetrieb aus dessen kontrolliert gestopptem aktuellen Bestand
erstellt werden. Wird nach einem Export erneut gespielt, ist dieser nur historisch.

## Aktuelle automatisierte Prüfungen

Nach der Korrektur der dauerhaften Migrationsversionssperre am 5. Oktober:
**122 Tests PASS**, Linux mit 1 Skip, Windows mit 6 Skips. Neue Regressionen
prüfen ein normales 42.21.0 → 42.22.0-Update einer importierten Welt mit altem
Marker, Safety-Backup vor SteamCMD, neuen Linux-Versionsnachweis, READY und
Backup-/false-Intent-Erhaltung bei Fehler. Import/Restore neuerer Backups werden
ebenfalls geprüft. 42.21.0 ist historische Abnahme, keine aktive Versionsvorgabe.
Die neuen Versionswechseltests sind synthetisch und nehmen keinen zukünftigen
echten PZ-Release oder private Mod-Kompatibilität vorweg. Details: [README-Prüfung](README-CHECK.md).

Am 5. Oktober wurden die README-Befehle zusätzlich über echtes Debian-SSH und
einen eigenen Docker-Daemon mit neuen synthetischen Welten ausgeführt, einschließlich
6g-Live-/Restore-Starts, Instanzwechsel, Management, Export/Restore und Wiederanlauf.
Umgebung, Befehlsmatrix und Grenzen: [README-Prüfung](README-CHECK.md).
Nach der leichteren authentifizierten Control-Healthcheck-Abfrage bestand die Suite
erneut: Linux 115 Tests mit 1 Skip, Windows 115 Tests mit 6 Skips. Der API-Test prüft
jetzt auch den Healthcheck-Client mit gültigem und falschem Token.

Am 4. Oktober auf dem finalisierten Code ausgeführt:

| Prüfung | Ergebnis |
| --- | --- |
| Linux, Python 3.12 mit gepinnten Discord-Testabhängigkeiten | 115 Tests, PASS, 1 Skip |
| Windows, vorhandenes Host-Python | 115 Tests, PASS, 6 Skips |
| Python-Compilation | Ops, Agent, Discord, Hostskripte und Tests: PASS |
| Aufgelöstes Compose | Default sowie Test-/Live-/Versionsprüfprofil einschließlich tools/discord: PASS |
| Isolation | Test und Live: getrennte sieben benannte Volumes und Secretpfade; native 1:1-UDP-Ports |
| Public-tree/Git-History-Audit | PASS; private Runtime-Dateien, Archive und Secrets bleiben untracked/ignoriert |

Linux überspringt nur den nativen PowerShell-Test. Windows überspringt drei Tests
mit dort nicht installierten optionalen Discord-Abhängigkeiten, den Linux-
Case-Collision-Test, den Symlink-Test ohne Hostprivileg sowie den nativen POSIX-
Wrapper-Test. Die nativen Wrapper-Argumenttests laufen jeweils auf ihrem
Zielbetriebssystem, einschließlich Pfaden mit Leerzeichen.

Die Suite umfasst byteerhaltende INI-/Mod-Reihenfolge, schema-2-Pending-Provenienz,
Apply-/Ack-Recovery, Backups/Retention, SQLite, Restore und dauerhafte Kernelguards,
READY, unbekannte/belegte Spieler, Intent, unterbrochene Jobs, API-Authentifizierung,
Discord-Rollen, Redaction und Public-tree-Prüfungen. Neue Regressionen prüfen:

- leeres Test-Spielerpasswort und weiterhin zufällige private Admin-/RCON-Secrets;
- rohen Persistence-File-Drop, vorhandenes Backupformat und externe SHA-Sidecars;
- volle Lua-Persistenz und Account-DB-Journals, Quellen unverändert;
- Traversal/Links/falsche Hashes/unerlaubte Archivteile und belegte Importziele;
- im damaligen Stand den 42.21.0-Gate bei Backupimport (inzwischen durch die oben
  beschriebenen Update-/Restore-Regressionen ohne feste Versionssperre ersetzt);
- Hashprüfung **nach** Veröffentlichung über Volumegrenzen; fehlgeschlagene
  Imports erhalten keine Fertigmarkierung, Restorefehler behalten ihr Journal;
- begrenzten Logtail, aktuelle Workshop-Fehlerdiagnose und native Windows-/POSIX-
  Argumentübergabe ohne verschachteltes Python--c-Quoting.

## Frischer synthetischer Runtime-Test am 4. Oktober

Es wurde ausschließlich eine **neue leere pztest-Instanz** mit eigenem App-,
Workshop-, Daten-, State-, Control-, Backup- und Logvolume verwendet. Sie teilte
keine privaten Live-Volumes. Die vorhandene private Welt wurde nicht erneut gestartet.

| Prüfung | Ergebnis |
| --- | --- |
| Neue Linux-SteamCMD-Installation | 42.21.0 / Build 25485538 |
| Start mit 2g Heap | READY, eigener Spielprozess, beide UDP-Sockets, authentifiziertes RCON, bekannte 0 Spieler |
| Effektive Spielkonfiguration | Password vollständig leer; RCON/Admin/API zufällig und privat |
| Docker-Portveröffentlichung | 127.0.0.1:16261 → 16261/udp; 127.0.0.1:16262 → 16262/udp |
| Windows .\pz.ps1 logs über reales Compose | PASS, synthetische Logmarker, kein SyntaxError |
| Linux-Logmodul im echten Ops-Container | PASS, dieselben Marker, kein SyntaxError |
| Kontrollierter Stop | Save/Quit abgeschlossen, desired=false |
| Vollbackup und Offlineexport | 41 persistente Dateien; tar.gz und externer SHA-256-Sidecar |
| Wrapper-Archivimport in neues Ziel | Hash-/SQLite-/Pristine-Prüfung erfolgreich, desired=false, kein Spielstart |
| Wrapper-Archivrestore in weiteres neues Ziel | Manifest-/Hash-/SQLite-Prüfung erfolgreich, desired=false, kein Spielstart |
| Roher Persistence-File-Drop in neues Ziel | Linux-Inventar und geschütztes pristine Backup erfolgreich |

Am 4. Oktober wurde der Linux-POSIX-Wrapper nativ mit einem kontrollierten
Transportstub geprüft, das echte Logmodul zusätzlich im Linux-Ops-Container.
Der Windows-Aufruf verwendete die reale Docker-CLI und das reale Ops-Logmodul.
Am 5. Oktober wurde diese Transportgrenze geschlossen: ./pz logs lief über echtes
SSH auf einer getrennten Debian-13-VM mit deren eigener Docker-CLI und eigenem
Docker-Daemon erfolgreich. Die VM benutzt keine privaten bisherigen Weltdaten.

## Weiterhin gültige Runtime-Evidenz vom 2. Oktober

Leere Linux-Welt und disposable Restore-Welt bestanden bereits den vollständigen
READY-Test. Die Restore-Smoke-Sequenz umfasste READY → Save/Quit → Vollbackup →
harmlosen späteren Marker → Restore in ein neues Ziel → unveränderte Manifestdateien/
fehlenden Marker → expliziten Start → READY. Beide UDP-Sockets und authentifiziertes
Nullspieler-RCON wurden geprüft.

Ebenfalls geprüft: false Intent bleibt bei Control-Neustart offline; true Intent
führt durch Reconciliation zu einem frischen READY-Prozess; absichtlich
verschlechtertes RCON ergibt STARTING_OR_DEGRADED ohne Kill/Neustart; explizites
Update erzeugt ein Safety-Backup und hält false Intent. Die Reconciliation war
wegen anfänglicher Startreihenfolge verzögert, keine Sofortstartgarantie.

Der damalige vollständige private Quellvergleich nach Import und zusätzliche
kritische Fingerprints waren unverändert. Aktive Welt und Konfiguration wurden
importiert, historische Dateien als geschützte Referenz gehalten. Pristine-Backup
und unabhängiger Restore wurden hash-/inventar-/DB-seitig verifiziert. Diese
historischen Prüfungen ersetzen nicht den späteren frischen Produktionsexport.

## Netzwerk- und Workshop-Erkenntnisse

Der Betreiber beobachtete bei 17261 → 16261 und 17262 → 16262 einen beginnenden
Steam-Handshake mit anschließendem Connection Failed. Test und private importierte
Welt funktionierten mit **nativen 1:1-Ports 16261/16262**. Das ist der unterstützte
Debian-Pfad. Andere externe Ports bleiben konfigurierbar, aber nicht abgenommen.
Auf derselben Host-IP laufen Test und Live nacheinander; auch Controlcontainer
müssen zum Freigeben der Hostports gestoppt werden.

Workshop-Zustände sind zeitabhängig. Während der Abnahme wurde ein zuvor Current
Item upstream aktualisiert; PZ beendete einen Startversuch im Download. Später
war das Item vollständig Current und der Start erfolgreich. Ein Einzelfehler
beweist keine Weltkorruption. Der Agent erkennt klare Downloadfehler nur im Log
der aktuellen Startgeneration und meldet einen festen Diagnosecode; unklare Fälle
bleiben START_PROCESS_EXITED. Rohlogs/IDs werden dadurch nicht in die API übernommen.
Es gibt keine automatische Modlöschung oder Weltänderung.

## Sicherheit, Lieferung und Restgrenzen

Runtime-Dienste laufen mit UID/GID 1000, cap_drop ALL und no-new-privileges.
Initializer und Tools sind netzlos; Tools geben Root vor Datenoperationen ab.
Kein Dienst erhält Docker-Socket oder privilegierten Modus. Nur Spiel-UDP wird
veröffentlicht; RCON/API/Unix-Socket bleiben privat. Discord bekommt keine Welt-
oder Controlmounts und keine RCON-Zugangsdaten. Buildkontexte enthalten nur Code.

Die Ausgangsquelle und bereits vorhandenen privaten Archive/Deployment-/Secret-
Dateien wurden vor und nach der Finalisierung per privatem Fingerprintvergleich
geprüft: 44 erfasste Dateien unverändert. Fingerprints bleiben außerhalb von Git.
Die neuen Testziele bleiben gestoppt; ihre Daten werden nicht veröffentlicht.

Offen bleiben Einrichtung des tatsächlichen Zielhosts, frischer Windows-Cutover mit
Client-Check des **neuen finalen Spielstands**, optional echte Discord-Anmeldung/
Rollen-/Nullspieler-Restart und späterer GitHub-Push. Physischer Stromausfall und
echter Betrieb mit belegten Spielern wurden nicht erzwungen; dafür existieren
kontrollierte Fehler-/Sicherheitsprüfungen. Das ausgelassene zusätzliche menschliche
Restore-Testing ist bewusst kein Blocker.

Die Lieferung ist lokal auf main. Ein GitHub-origin ist bereits eingerichtet;
seine private URL bleibt außerhalb der Dokumentation. Während dieser Finalisierung
wurde kein Remote verändert und nichts gepusht. Für den späteren Push vorhandenen
origin/Berechtigungen prüfen, Audit erneut ausführen und ausschließlich Code pushen.
Commit und sauberer Git-Status stehen im abschließenden Übergabebericht.
