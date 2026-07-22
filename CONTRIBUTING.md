# Contributing to Open BOS Stream

Vielen Dank für dein Interesse an Open BOS Stream!

Dieses Projekt befindet sich derzeit in aktiver Entwicklung. Beiträge,
Fehlerberichte und Verbesserungsvorschläge sind jederzeit willkommen.

---

# Entwicklungsgrundsätze

Open BOS Stream verfolgt folgende Prinzipien:

- Lesbarer Code vor cleverem Code
- Kleine, klar abgegrenzte Komponenten
- Keine unnötigen Abhängigkeiten
- Raspberry Pi als Referenzplattform
- Open Source
- Datenschutzfreundlich
- Klare Projektstruktur

---

# Projektstruktur

```
src/open_bos_stream/

api/            REST-Endpunkte
core/           Gemeinsame Modelle und Infrastruktur
dashboard/      Dashboard-Logik
mediamtx/       MediaMTX-Anbindung
recording/      Aufnahmeverwaltung
snapshot/       Snapshotverwaltung
stream/         Streaming
system/         Systeminformationen

static/
    css/
    js/

templates/
```

---

# Coding Style

## Python

- PEP 8
- Type Hints verwenden
- Kleine Funktionen bevorzugen
- Docstrings für öffentliche Klassen und Funktionen

---

## HTML

- Komponenten statt großer Dateien
- Keine Inline-Styles
- Semantisches HTML

---

## CSS

- Eine Datei pro Bereich

Beispiel:

```
header.css
sidebar.css
video.css
dashboard.css
```

Keine komponentenübergreifenden Styles.

---

## JavaScript

Jede Datei besitzt genau eine Aufgabe.

Beispiele:

```
stream.js
recording.js
health.js
navigation.js
```

Keine globalen Variablen.

API-Aufrufe ausschließlich über

```
api.js
```

---

# Commits

Kurze, aussagekräftige Commit-Nachrichten.

Beispiele:

```
Add snapshot library

Improve video overlay

Fix recording status

Refactor dashboard layout
```

---

# Pull Requests

Ein Pull Request sollte möglichst nur **eine Änderung** enthalten.

Beispiele:

- neues Feature
- Bugfix
- Refactoring
- Dokumentation

---

# Neue Features

Vor größeren Änderungen sollte geprüft werden, ob die Funktion zur
Roadmap passt.

Siehe:

```
ROADMAP.md
```

---

# Lizenz

Mit einem Beitrag erklärst du dich damit einverstanden, dass dein Code
unter der MIT-Lizenz veröffentlicht wird.
