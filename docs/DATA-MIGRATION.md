# Persistenz, privater File-Drop und Restore

Die abgenommene private Docker-Kopie ist ein erfolgreicher Migrationsnachweis,
kein finaler Produktionsstand. Für den Cutover kommt ein **neues Archiv nach
dem letzten Spielbetrieb** vom kontrolliert gespeicherten/gestoppten Windows-Server.
[Handoff](LINUX-HANDOFF.md) und [README](../README.md) enthalten die Bedienbefehle.

## Persistence-Contract und Quellen

Aktiv übernommen werden die vier Serverkonfigurationsdateien der gewählten Instanz,
die vollständige Saves/Multiplayer/SERVERNAME-Welt einschließlich Player-/Vehicle-
DB und Journals, db/SERVERNAME.db einschließlich vorhandener WAL-/SHM-/Journaldateien,
alle persistenten Lua-Dateien außer Diagnose-.log-Dateien und options.ini.
Unbekannte Persistenz innerhalb der aktiven Welt/Lua wird nicht auf zwei bekannte
Mods beschränkt. Andere Instanz-/Referenzdateien werden geschützt privat gehalten.

App, Windows-Binaries/Java/venv, Steam-/Workshop-Cache, Runtime-Logs, Steuerdateien,
Secrets und historische native Backup-ZIPs sind keine aktive Welt. Ein roher
File-Drop enthält nur Server/, Saves/, db/, Lua/ und options.ini an der Archivwurzel.
Kein zusätzlicher Windows-Exporthelfer wird eingeführt.

Vor Archivierung Spieler abmelden, save/quit und vollständigen Prozess-Exit prüfen;
automatischen Wiederstart deaktivieren. Aktive alte Mod-/Config-Pending-Vorgänge
vorher kontrolliert abschließen. Wiederaufgenommener Spielbetrieb macht das Archiv
historisch; für den Cutover nochmals frisch gestoppt exportieren.

## Ein gemeinsamer Archiveingang

Der vorhandene begrenzte Extractor unterstützt:

| Format | Struktur | Validierung |
| --- | --- | --- |
| Roher Persistence-File-Drop | Server/, Saves/, db/, Lua/, options.ini | Linux erzeugt Inventar/Dateimanifest und prüft die kopierten Daten |
| Vorhandenes portables Backup | data/, optional state/, manifest.json, _backup.json | Schema-3-Abschlussmetadaten, vollständiges Manifest und Pending-Provenienz |
| Bestehender nativer Source-Transfer | instance/ plus source-manifest.json | Extraktionsinventar muss vollständig zum Quellmanifest passen |

Es gibt keine parallele neue Backup-/Restoreimplementierung. Absolute Pfade,
Traversal, Links, Spezialdateien, Duplikate und Case-Collisions werden verweigert;
Eintragszahl und entpackte Größe sind begrenzt. Archivinhalte können nicht außerhalb
des privaten Stagingpfads geschrieben werden.

Ein optionaler externer SHA-256-Sidecar wird vor Verarbeitung geprüft. Für den
finalen Cutover **immer mit übertragen und explizit angeben**. Akzeptiert werden
ein einzelner Hash oder HASH  ARCHIVBASENAME (auch üblicher *-Dateimarker).
Ein falscher Hash, mehrzeiliger/ungültiger Sidecar oder anderer Dateiname scheitert.
Ohne explizite Option verwendet der Wrapper den angrenzenden ARCHIVNAME.sha256,
falls vorhanden; Sidecar und Archiv müssen im selben Ordner liegen.

~~~bash
./pz --env-file .env.live import --archive imports/szs-final.tar.gz \
  --sha256-file imports/szs-final.tar.gz.sha256
~~~

Beide Controldienste müssen vorher gestoppt sein; das Datenziel muss neu/leer sein.
Der Wrapper bindet nur den Archivordner read-only ein. Tools sind netzlos und laufen
nach Volumeinitialisierung als UID/GID 1000, mit Lifecycle- und Game-Kernelguards.

Import verifiziert Original-/Kopierhashes, Inventar, genaue WorkshopItems/Mods/Map-
Reihenfolge und SQLite **PRAGMA integrity_check** auf den Kopien. Nach einem
Volumewechsel wird die tatsächlich veröffentlichte Welt erneut gehasht; Dateien
und Linux-Verzeichnisse werden synchronisiert. Erst danach werden Gate, geprüftes
geschütztes pristine Backup und **zuletzt** die Fertigmarkierung veröffentlicht.
Intent bleibt desired=false. Der Import startet Java nicht.

Backupimport benutzt denselben Restoreweg und erstellt seine neue Importprovenienz/
Pristine-Evidenz. Ein deklarierter anderer PZ-Gate/Versionsstand wird vor Publikation
verweigert. Der Erstimport bleibt exakt auf 42.21.0 begrenzt; aktuelle Linux-
Start-Evidenz muss zum installierten Build gehören. Alte Windows-Logs zählen nicht.

Der ältere import --source VERZEICHNIS bleibt kompatibel: Der bereits vorhandene
Hosttransfer liest die gestoppte Quelle nativ, archiviert mit SHA-Inventar unter
ignoriertem tmp/, prüft die Quelle vorher/nachher und übergibt eine read-only-Datei.
Der neue File-Drop benötigt diesen Hostproducer nicht.

## Vollständige Betriebsbackups

Backups entstehen nach kontrolliertem Spielende oder aus schon gestoppten Daten.
Ein dauerhafter Game-Kernellock verhindert unabhängig von Prozesslisten Live-Kopien.
Sie umfassen Server/Saves/db/Lua/options, erlaubte Migrationsmarker und kohärente
Pending-/Config-Provenienz. App/Workshop, Logs, Tokens, Socket-/Job-/Lockzustand
und alte native ZIP-Sammlungen sind ausgeschlossen.

Erzeugung verwendet .inprogress-Staging auf dem Backupvolume, Original-/Kopier-/
erneute Quellhashes und Inventare, kopierte SQLite-Prüfungen, manifest.json und
zuletzt schema-3-_backup.json. Verifikation geht der atomaren Verzeichnisumbenennung
voraus. Geschützte pristine-/Referenzbackups gehören nicht zur rotierenden Löschung.

Der Katalog prüft Name/Schema/Status/Server, Manifestchecksumme, Dateien/Bytes,
UTC-Abschluss und Struktur. Health hasht nicht bei jedem Read die ganze Welt;
vollständige Prüfung erfolgt bei Erzeugung, Export und Restore. Alle Backup-
Alterswerte nutzen denselben abgeschlossenen Katalog. Retention behält vier neueste
Backups plus bis zu vier ältere UTC-ISO-Wochenanker.

Ein Backupjob eines laufenden Servers stoppt und startet frisch. Ein absichtlich
gestoppter Server bleibt gestoppt. Pending wird nur nach einem frischen READY-
Barrier intern bestätigt. Update-/Workshop-/Config-Jobs verwenden Safety-Backups.

## Export und Restore

Mit gestoppten Controldiensten:

~~~bash
./pz --env-file .env.live export --backup BACKUP_NAME \
  --output exports/private-handoff.tar.gz
~~~

Export prüft den Snapshot und erzeugt tar.gz plus angrenzenden SHA-256-Sidecar.
Bestehende Archiv-/Sidecardateien werden nicht überschrieben. Das Archiv enthält
private Spielerdaten/Zugangsdaten; Git allein kann die Welt nicht wiederherstellen.

Ein neues explizites Projekt mit passenden Servernamen und eigenen Secrets wählen:

~~~bash
./pz --env-file .env.restore restore --archive imports/private-handoff.tar.gz \
  --sha256-file imports/private-handoff.tar.gz.sha256
~~~

Restore prüft Manifestchecksumme, sämtliche Datei-Hashes/Größen, tatsächliches Inventar,
Persistenzbereich, Servername, SQLite und kompletten Pending-/History-Replay.
Kein PID, Socket, Job oder stale Lock wird wiederhergestellt. Permanente Guard-
Inodes bleiben erhalten. Bei Migrationsdaten wird Pristine-Evidenz erneut erzeugt.

Staging wird vor Publikation erneut gehasht und synchronisiert. RESTORE_COPY_MISMATCH
verweigert den Eingriff vor Veröffentlichung. Auch die tatsächlichen Daten **nach**
Veröffentlichung über Volumegrenzen werden geprüft; RESTORE_PUBLICATION_MISMATCH
behält das sperrende Journal. Multi-Verzeichnis-Publikation ist kein atomarer
Volumeswitch. Unterbrechung/Fehler lassen false Intent und Recovery-Sperre zurück.

Vorhandene Daten ersetzen erfordert --confirm-replace, false Intent, gestopptes
Spiel, Locks und ein geschütztes Pre-Restore-Backup. Ein unterbrochenes Ziel offline
lassen; Originalarchiv in ein **neues** Projekt restoren statt Journal/Guard zu löschen.
Archive/Quellen bleiben erhalten. Restore startet nie selbst.

## Abnahme

Disposable Runtime-Restore erreichte bereits READY nach vollständigem Backup-/
Marker-/Restore-Smoke. Die private importierte Welt wurde inzwischen auch menschlich
mit vorhandenem Account/lebendem Charakter und repräsentativen Mods abgenommen.
Zusätzlicher menschlicher Test der hash-/DB-verifizierten privaten Restore-Kopie
wird bewusst ausgelassen und ist kein Blocker. Für den finalen neuen Produktionsstand
bleibt ein kurzer Client-Check nach Cutover nötig. [Testbericht](TEST-REPORT.md).
