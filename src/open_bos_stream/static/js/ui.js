function updateClock() {

    const clock = document.getElementById("clock");

    if (!clock) {
        return;
    }

    clock.textContent = new Date().toLocaleTimeString("de-DE");

}

function toggleSidebar() {

    const sidebar = document.getElementById("sidebar");
    const grid = document.getElementById("dashboard-grid");

    sidebar.classList.toggle("sidebar-hidden");
    grid.classList.toggle("sidebar-collapsed");

    localStorage.setItem(
        "sidebarHidden",
        sidebar.classList.contains("sidebar-hidden")
    );

}

function restoreSidebar() {

    const hidden = localStorage.getItem("sidebarHidden");

    if (hidden === "true") {

        document
            .getElementById("sidebar")
            ?.classList.add("sidebar-hidden");

        document
            .getElementById("dashboard-grid")
            ?.classList.add("sidebar-collapsed");

    }

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
    message
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

    time.textContent =
        new Date().toLocaleTimeString(
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

    log.prepend(
        entry
    );

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
            "Ereignisprotokoll wirklich leeren?"
        )
    ) {
        return;
    }

    log.replaceChildren();

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
