// ==========================================================
// E-Mail-Benachrichtigungen (nur Superadmin)
// ==========================================================

let notificationSettings = null;

function notificationElement(id) {
    return document.getElementById(`cfg-notify-${id}`);
}

function setNotificationStatus(text) {
    const status = notificationElement("status");
    if (status) {
        status.textContent = text;
    }
}

function cleanValidationMessage(message) {
    return String(message || "").replace(/^Value error,\s*/i, "");
}

function describeLastNotification(result) {
    if (!result) {
        return "Wird separat und ohne Neustart gespeichert.";
    }
    const time = new Date(result.at * 1000).toLocaleString("de-DE");
    return result.success
        ? `Zuletzt versendet am ${time}.`
        : `Letzter Versand am ${time} fehlgeschlagen: ${result.error}`;
}

function renderNotificationSettings() {
    const settings = notificationSettings;
    if (!settings || !notificationElement("enabled")) {
        return;
    }
    notificationElement("enabled").checked = Boolean(settings.enabled);
    notificationElement("host").value = settings.smtp_host ?? "";
    notificationElement("port").value = settings.smtp_port ?? 587;
    notificationElement("security").value = settings.security ?? "starttls";
    notificationElement("username").value = settings.username ?? "";
    notificationElement("password").value = "";
    notificationElement("sender").value = settings.sender ?? "";
    notificationElement("recipients").value =
        (settings.recipients ?? []).join(", ");
    notificationElement("password-hint").textContent = settings.password_set
        ? "Ein Passwort ist gespeichert. Leer lassen, um es zu behalten."
        : "Noch kein Passwort gespeichert.";
    document.querySelectorAll("[data-notify-event]").forEach(input => {
        input.checked = Boolean(
            settings.events?.[input.dataset.notifyEvent]
        );
    });
    setNotificationStatus(describeLastNotification(settings.last_result));
}

async function loadNotificationSettings() {
    if (!notificationElement("enabled")) {
        return;
    }
    try {
        notificationSettings = await api.notificationSettings();
        renderNotificationSettings();
    } catch (error) {
        setNotificationStatus(
            "Benachrichtigungen konnten nicht geladen werden: " +
            error.message
        );
    }
}

function collectNotificationSettings() {
    const events = {};
    document.querySelectorAll("[data-notify-event]").forEach(input => {
        events[input.dataset.notifyEvent] = input.checked;
    });
    return {
        enabled: notificationElement("enabled").checked,
        smtp_host: notificationElement("host").value.trim(),
        smtp_port: Number(notificationElement("port").value) || 587,
        security: notificationElement("security").value,
        username: notificationElement("username").value.trim(),
        password: notificationElement("password").value || null,
        sender: notificationElement("sender").value.trim(),
        recipients: notificationElement("recipients").value,
        events,
    };
}

function setNotificationButtonsDisabled(disabled) {
    ["save", "test"].forEach(id => {
        const button = notificationElement(id);
        if (button) {
            button.disabled = disabled;
        }
    });
}

async function persistNotificationSettings() {
    const result = await api.saveNotificationSettings(
        collectNotificationSettings()
    );
    notificationSettings = result.notifications;
    renderNotificationSettings();
    return result;
}

async function saveNotificationSettings() {
    setNotificationButtonsDisabled(true);
    setNotificationStatus("Wird gespeichert …");
    try {
        const result = await persistNotificationSettings();
        setNotificationStatus(
            notificationSettings.enabled
                ? "Gespeichert. Störungen werden per E-Mail gemeldet."
                : "Gespeichert. Benachrichtigungen sind ausgeschaltet."
        );
        addEvent("success", result.message);
    } catch (error) {
        const message = cleanValidationMessage(error.message);
        setNotificationStatus("Speichern fehlgeschlagen: " + message);
        addEvent("error", message);
    } finally {
        setNotificationButtonsDisabled(false);
    }
}

async function sendTestNotification() {
    setNotificationButtonsDisabled(true);
    setNotificationStatus("Wird gespeichert und gesendet …");
    try {
        await persistNotificationSettings();
        const result = await api.sendTestNotification();
        setNotificationStatus(result.message);
        addEvent("success", result.message);
    } catch (error) {
        const message = cleanValidationMessage(error.message);
        setNotificationStatus("Test fehlgeschlagen: " + message);
        addEvent("error", "Testnachricht: " + message);
    } finally {
        setNotificationButtonsDisabled(false);
    }
}
