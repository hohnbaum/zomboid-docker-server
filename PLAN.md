# Stand der Docker-Migration

Stand: 4. Oktober 2026. Discovery, Implementierung und lokale Finalisierung sind
abgeschlossen. Der private Snapshot bleibt unverändert; es wird keine Produktion
kontaktiert und in dieser Finalisierung nichts auf GitHub veröffentlicht.

## Implementierung und Abnahme

| Bereich | Stand |
| --- | --- |
| Repository | Eigenständiges main, nur Code/Dokumentation/synthetische Tests, ignorierte private Ablage, Public-tree-/History-Audit |
| Linux-Spiel | SteamCMD, nativer mitgelieferter JVM-Launcher, UID 1000, exakte 42.21.0-/Build-Evidenz, frischer pztest READY |
| Private importierte Testkopie | Betreiber bestätigt READY, 111 Workshop Current, 137 Mods, vorhandenen Account/lebenden Charakter und interaktive erwartete Welt |
| Persistenz | Vollständige Server/Saves/db/Lua/options-Backups, geschützte Pristine-/Referenzkopien, Retention und geprüfter Runtime-Restore |
| Linux-File-Drop | Vorhandenen begrenzten Extractor/Import/Restore erweitert, externer SHA-Sidecar, Linux-Inventar/integrity_check, neues Ziel und false Intent |
| Ops | Dauerhafte Jobs/Locks/Intent, sichere RCON-Spielerpolitik, Reconciliation, Wartung/Telemetry/Build- und Backupprüfung |
| Mods/Config | Geordnete schema-2-Pläne, Byteerhaltung, vollständige Apply-/Ack-Provenienz und explizite Recovery |
| Logs/Workshop | Modulaufruf statt verschachteltem Quoting; aktueller fester Workshop-Download-Diagnosecode ohne rohe API-Logs |
| Test und Live | Eigenständige permanente Volumes/Secrets, sequentiell auf 1:1-UDP 16261/16262 |
| Discord | Optional, sechs deutsche Commands, private API, synthetisch geprüft; echte Anmeldung optional offen |
| Debian-Handoff | Vollständiges deutsches README und privater Cutoverweg ohne neuen Windows-Exporthelfer |

Die menschliche Abnahme der privaten Importkopie ist abgeschlossen. Die gesonderte
hash-/DB-verifizierte private Restore-Kopie bekommt bewusst keinen weiteren
menschlichen Test; kein Blocker. [TEST-REPORT.md](docs/TEST-REPORT.md) unterscheidet
Betreiberbestätigung, eigene Runtime-/Unit-Prüfungen und offene Zielhostschritte.

## Beibehaltene Betriebsgarantien

- Unbekannte Spieler/RCON verweigern Save/Quit/Mutation; force erlaubt nur bekannte
  Belegung, niemals Kill oder unbekannten Zustand.
- Dauerhafte Kernelguards für Agent, App und Daten; kein Docker-Socket, privilegierter
  Dienst, beliebiger Shell-Endpunkt oder automatisches Steam-Update beim Booten.
- Bestehende degradierte Prozesse werden nicht automatisch beendet/neugestartet.
- Import und Restore starten nicht selbst, erhalten false Intent/Pristine-Evidenz.
  Initiale Migrationsversion bleibt exakt 42.21.0; keine Gate-Abschwächung.
- Backups/Archive prüfen Hashes, Inventar, SQLite und kohärente Pending-Provenienz.
  Auch veröffentlichte Kopien über Volumegrenzen werden erneut geprüft.
- Unterbrochene Jobs brauchen explizite Recovery, keinen blinden Replay.
- Workshop ist dynamisch; ein einzelner Downloadfehler bewirkt weder Modlöschung
  noch Weltänderung und löst keinen automatischen Upstream-Neustart aus.
- Normalerweise nur Live auf nativen Ports; Test/Versionsprüfung vorher und nachher
  sauber stoppen. Andere Hostports sind nicht für den abgenommenen Pfad verifiziert.

Die detaillierte alte Windows-Discovery bleibt als historischer Befund in
[CURRENT-SYSTEM.md](docs/CURRENT-SYSTEM.md). Private Discoverydateien/Identitäten
werden nicht ins öffentliche Repository übernommen.

## Verbleibende Übergabe

1. Debian-13-Zielhost gemäß README installieren; Test und unabhängige Live-App-
   Versionsprüfung ausführen.
2. **Neueste Windows-Produktion** nach letztem Spielbetrieb speichern/vollständig
   stoppen; neuen privaten Persistence-File-Drop und SHA-Sidecar erstellen.
3. Separat von Git übertragen, in neues Live-Ziel importieren, explizit starten
   und letzten Weltstand mit Client prüfen. Alte akzeptierte Docker-Welt ist
   keine finale Produktionsquelle.
4. Optional echte Discord-Credentials/Guild/Rollen testen.
5. Später vorhandenen GitHub-origin/Berechtigungen prüfen und nur nach erneutem
   Audit Code pushen. Remote blieb unverändert; GitHub-CLI oder weitere Hostsoftware
   wurden nicht installiert.

README, LINUX-HANDOFF, DATA-MIGRATION, ARCHITECTURE, MOD-PLAN-LIFECYCLE,
TROUBLESHOOTING und TEST-REPORT dokumentieren Bedienung, Grenzen und Recovery.
