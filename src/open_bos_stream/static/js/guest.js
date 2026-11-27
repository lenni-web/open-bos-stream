// ==========================================================
// Gastansicht: freigegebene Livebilder und Karte
// ==========================================================

const GUEST_POLL_MS = 2000;
let guestPollTimer = null;
let guestEnded = false;

function showGuestPage(page) {
    document.querySelectorAll(".page").forEach(element => {
        element.classList.toggle("active", element.id === `page-${page}`);
    });
    document.querySelectorAll("[data-guest-page]").forEach(button => {
        const active = button.dataset.guestPage === page;
        button.classList.toggle("is-active", active);
        button.setAttribute("aria-pressed", String(active));
    });
    if (page === "map" && typeof initMapPage === "function") {
        initMapPage();
    }
}

function endGuestView(title, text) {
    if (guestEnded) {
        return;
    }
    guestEnded = true;
    window.clearTimeout(guestPollTimer);
    document.querySelectorAll("video").forEach(video => {
        video.pause();
        video.removeAttribute("src");
    });
    document.body.innerHTML = `
        <main class="guest-ended">
            <img src="/static/icons/open-bos-stream.svg" alt="" width="54" height="54">
            <h1>${escapeHTML(title)}</h1>
            <p>${escapeHTML(text)}</p>
        </main>
    `;
}

function formatGuestExpiry(expiresAt) {
    const end = new Date(expiresAt * 1000);
    const now = new Date();
    const time = end.toLocaleTimeString("de-DE", {
        hour: "2-digit",
        minute: "2-digit",
    });
    const sameDay = end.toDateString() === now.toDateString();
    const compact = window.matchMedia("(max-width: 768px)").matches;
    const date = end.toLocaleDateString("de-DE", {
        day: "2-digit",
        month: "2-digit",
    });
    if (compact) {
        return sameDay ? `bis ${time}` : `bis ${date} ${time}`;
    }
    return sameDay
        ? `gültig bis ${time} Uhr`
        : `gültig bis ${date}, ${time} Uhr`;
}

function updateGuestExpiry() {
    const element = document.getElementById("guest-expiry");
    if (!element) {
        return;
    }
    const expiresAt = Number(element.dataset.expiresAt);
    const remaining = expiresAt * 1000 - Date.now();
    if (remaining <= 0) {
        endGuestView(
            "Gastzugang abgelaufen",
            "Die Gültigkeit dieses Gastlinks ist abgelaufen."
        );
        return;
    }
    element.textContent = formatGuestExpiry(expiresAt);
    element.classList.toggle("is-ending", remaining < 15 * 60 * 1000);
}

function renderGuestIncident(incident) {
    const box = document.getElementById("guest-incident");
    if (!box) {
        return;
    }
    box.hidden = !incident;
    if (!incident) {
        return;
    }
    const alarm = new Date(incident.alarm_at);
    const time = Number.isNaN(alarm.getTime())
        ? ""
        : alarm.toLocaleString("de-DE", {dateStyle: "short", timeStyle: "short"});
    box.innerHTML = `
        <strong>${escapeHTML(incident.keyword || "Einsatz")}</strong>
        <span>${incident.address ? `${escapeHTML(incident.address)} · ` : ""}Alarm ${escapeHTML(time)}
            · ${escapeHTML(incident.code)}</span>`;
}

async function pollGuestStatus() {
    if (guestEnded) {
        return;
    }
    try {
        const response = await fetch("/guest/status", {
            cache: "no-store",
            credentials: "same-origin",
        });
        if (response.status === 401 || response.status === 403) {
            endGuestView(
                "Gastzugang beendet",
                "Dieser Gastlink ist abgelaufen oder wurde gesperrt."
            );
            return;
        }
        if (response.ok) {
            const data = await response.json();
            const sources = data.sources ?? [];
            updateMultiSources(sources);
            renderGuestIncident(data.incident);
            const empty = document.getElementById("guest-empty");
            if (empty) {
                empty.hidden = sources.length > 0;
            }
        }
    } catch (error) {
        console.debug("Gaststatus nicht erreichbar:", error);
    }
    guestPollTimer = window.setTimeout(pollGuestStatus, GUEST_POLL_MS);
}

async function logoutGuest() {
    try {
        await fetch("/auth/logout", {
            method: "POST",
            credentials: "same-origin",
        });
    } finally {
        endGuestView(
            "Gastzugang beendet",
            "Sie haben den Gastzugang verlassen. Zum erneuten Ansehen den " +
            "Gastlink noch einmal öffnen."
        );
    }
}

function syncGuestThemeButton() {
    const button = document.getElementById("guest-theme");
    if (!button) {
        return;
    }
    const dark = document.documentElement.dataset.colorScheme === "dark";
    button.title = dark ? "Helle Darstellung" : "Dunkle Darstellung";
    button.setAttribute("aria-label", button.title);
}

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-guest-page]").forEach(button => {
        button.addEventListener("click", () => {
            showGuestPage(button.dataset.guestPage);
        });
    });
    document.getElementById("guest-theme")?.addEventListener("click", () => {
        const dark = document.documentElement.dataset.colorScheme === "dark";
        window.OpenBosTheme?.set(dark ? "light" : "dark");
        syncGuestThemeButton();
    });
    syncGuestThemeButton();
    updateGuestExpiry();
    window.setInterval(updateGuestExpiry, 30 * 1000);
    pollGuestStatus();
});
