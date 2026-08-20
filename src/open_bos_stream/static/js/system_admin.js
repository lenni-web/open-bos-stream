let streamLogRefreshTimer = null;

function setSystemAdminFeedback(message, isError = false) {
    const feedback = document.getElementById("system-admin-feedback");
    if (!feedback) {
        return;
    }
    feedback.textContent = message;
    feedback.classList.toggle("is-error", isError);
}

async function refreshStreamLog() {
    const status = document.getElementById("stream-log-status");
    const content = document.getElementById("stream-log-content");
    const button = document.getElementById("stream-log-refresh");
    if (!status || !content) {
        return;
    }

    status.textContent = "Wird geladen …";
    if (button) {
        button.disabled = true;
    }
    try {
        const result = await api.streamLog();
        content.textContent = result.content || "Keine Meldungen vorhanden.";
        status.textContent =
            `Aktualisiert ${new Date(result.generated_at).toLocaleTimeString("de-DE")}`;
        content.scrollTop = content.scrollHeight;
        setSystemAdminFeedback("");
    } catch (error) {
        status.textContent = "Abruf fehlgeschlagen";
        setSystemAdminFeedback(error.message, true);
    } finally {
        if (button) {
            button.disabled = false;
        }
    }
}

function stopStreamLogRefresh() {
    if (streamLogRefreshTimer !== null) {
        window.clearInterval(streamLogRefreshTimer);
        streamLogRefreshTimer = null;
    }
}

async function toggleStreamLog() {
    const panel = document.getElementById("stream-log-panel");
    const button = document.getElementById("stream-log-toggle");
    if (!panel || !button) {
        return;
    }

    panel.hidden = !panel.hidden;
    button.textContent = panel.hidden
        ? "Stream-Log anzeigen"
        : "Stream-Log schließen";
    stopStreamLogRefresh();
    if (!panel.hidden) {
        await refreshStreamLog();
        streamLogRefreshTimer = window.setInterval(
            refreshStreamLog,
            5000
        );
    }
}

async function requestSystemReboot() {
    if (!window.confirm(
        "Server wirklich neu starten? Alle laufenden Streams werden kurz unterbrochen."
    )) {
        return;
    }
    if (!window.confirm(
        "Neustart endgültig bestätigen. Die Oberfläche ist danach kurz nicht erreichbar."
    )) {
        return;
    }

    const button = document.getElementById("system-reboot");
    if (button) {
        button.disabled = true;
    }
    try {
        const result = await api.rebootSystem();
        setSystemAdminFeedback(result.message);
    } catch (error) {
        setSystemAdminFeedback(error.message, true);
        if (button) {
            button.disabled = false;
        }
    }
}

document.getElementById("stream-log-toggle")?.addEventListener(
    "click",
    toggleStreamLog
);
document.getElementById("stream-log-refresh")?.addEventListener(
    "click",
    refreshStreamLog
);
document.getElementById("system-reboot")?.addEventListener(
    "click",
    requestSystemReboot
);
