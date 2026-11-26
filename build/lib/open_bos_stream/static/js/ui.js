function escapeHTML(value) {
    return String(value ?? "").replace(
        /[&<>"']/g,
        character => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;",
        })[character]
    );
}

function updateClock() {

    const clock = document.getElementById("clock");

    if (!clock) {
        return;
    }

    clock.textContent = new Date().toLocaleTimeString("de-DE");

}

function toggleCard(id) {

    const content = document.getElementById(id + "-content");
    const arrow = document.getElementById(id + "-arrow");

    if (!content || !arrow) {
        return;
    }

    const hidden = content.classList.toggle("hidden");

    arrow.textContent = hidden ? "▶" : "▼";

    localStorage.setItem(
        "card-" + id,
        hidden
    );

}

function restoreCards() {

    document.querySelectorAll(".card-content").forEach(content => {

        const id = content.id.replace("-content", "");

        const hidden =
            localStorage.getItem("card-" + id) === "true";

        if (hidden) {

            content.classList.add("hidden");

            const arrow =
                document.getElementById(id + "-arrow");

            if (arrow) {
                arrow.textContent = "▶";
            }

        }

    });

}

// ==========================================================
// Event Log
// ==========================================================

function addEvent(
    type,
    message,
    timestamp = null
) {

    const log =
        document.getElementById(
            "event-log"
        );

    if (!log) {
        return;
    }

    const entry =
        document.createElement(
            "div"
        );

    entry.className =
        "event-entry event-" +
        type;

    const time =
        document.createElement(
            "div"
        );

    time.className =
        "event-time";

    // Serverereignisse bringen ihren eigenen Zeitpunkt mit (Sekunden).
    const at = timestamp ? timestamp * 1000 : Date.now();
    entry.dataset.at = String(at);

    time.textContent =
        new Date(at).toLocaleTimeString(
            "de-DE"
        );

    const text =
        document.createElement(
            "div"
        );

    text.className =
        "event-text";

    text.textContent =
        message;

    entry.appendChild(
        time
    );

    entry.appendChild(
        text
    );

    // Neueste oben; ältere Serverereignisse an der richtigen Stelle.
    const newer = Array.from(log.children).find(
        item => Number(item.dataset.at || 0) <= at
    );
    log.insertBefore(entry, newer ?? null);

    updateEventCount();

}

function updateEventCount() {

    const counter =
        document.getElementById(
            "event-count"
        );

    const log =
        document.getElementById(
            "event-log"
        );

    if (
        !counter ||
        !log
    ) {

        return;

    }

    const count =
        log.children.length;

    counter.textContent =
        count +
        (count === 1
            ? " Eintrag"
            : " Einträge");

}

function clearEvents() {

    const log =
        document.getElementById(
            "event-log"
        );

    if (!log) {
        return;
    }

    if (
        !confirm(
            "Ereignisprotokoll in diesem Browser leeren?\n" +
            "Für andere Admins bleiben die Einträge erhalten."
        )
    ) {
        return;
    }

    log.replaceChildren();

    if (typeof rememberClearedEvents === "function") {
        rememberClearedEvents();
    }

    updateEventCount();

}

function openSettings() {

    alert("Einstellungen folgen im nächsten Schritt.");

}

// ==========================================================
// DOM Helper
// ==========================================================

function updateValue(
    id,
    value
) {

    const element =
        document.getElementById(
            id
        );

    if (!element) {

        return;

    }

    element.textContent =
        value;

}

function updateClass(
    id,
    className
) {

    const element =
        document.getElementById(
            id
        );

    if (!element) {

        return;

    }

    element.className =
        className;

}

function updateVisible(
    id,
    visible
) {

    const element =
        document.getElementById(
            id
        );

    if (!element) {

        return;

    }

    element.style.display =
        visible
            ? ""
            : "none";

}
