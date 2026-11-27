// ==========================================================
// Push-Benachrichtigungen auf diesem Gerät
// ==========================================================

const pushState = {
    overview: null,
    registration: null,
    subscription: null,
    busy: false,
    message: "",
    error: false,
};

function pushPlatform() {
    return typeof detectPlatform === "function" ? detectPlatform() : "desktop";
}

function pushInstalled() {
    return typeof isInstalledApp === "function" && isInstalledApp();
}

function pushSupport() {
    if (!window.isSecureContext) {
        return "insecure";
    }
    const available = "serviceWorker" in navigator &&
        "PushManager" in window &&
        "Notification" in window;
    if (!available) {
        // iOS bietet Web Push nur in der installierten App (ab 16.4).
        return pushPlatform() === "ios" && !pushInstalled()
            ? "ios-install"
            : "unsupported";
    }
    return "ok";
}

function pushKeyBytes(base64url) {
    const padded = (base64url + "=".repeat((4 - base64url.length % 4) % 4))
        .replace(/-/g, "+")
        .replace(/_/g, "/");
    const raw = atob(padded);
    return Uint8Array.from(raw, character => character.charCodeAt(0));
}

function pushDeviceLabel() {
    const agent = navigator.userAgent || "";
    const platform = pushPlatform();
    let device = "Computer";
    if (platform === "ios") {
        device = /iPad/.test(agent) || navigator.maxTouchPoints > 1 && /Macintosh/.test(agent)
            ? "iPad"
            : "iPhone";
    } else if (platform === "android") {
        device = "Android";
    } else if (/Windows/.test(agent)) {
        device = "Windows";
    } else if (/Macintosh/.test(agent)) {
        device = "Mac";
    } else if (/Linux/.test(agent)) {
        device = "Linux";
    }
    let browser = "Browser";
    if (/Edg\//.test(agent)) {
        browser = "Edge";
    } else if (/SamsungBrowser/.test(agent)) {
        browser = "Samsung Internet";
    } else if (/Firefox\//.test(agent)) {
        browser = "Firefox";
    } else if (/Chrome\//.test(agent) || /CriOS/.test(agent)) {
        browser = "Chrome";
    } else if (/Safari\//.test(agent)) {
        browser = "Safari";
    }
    return `${device} · ${pushInstalled() ? "App" : browser}`;
}

async function registerServiceWorker() {
    if (!("serviceWorker" in navigator) || !window.isSecureContext) {
        return null;
    }
    try {
        pushState.registration = await navigator.serviceWorker.register(
            "/sw.js",
            {scope: "/"}
        );
    } catch (error) {
        console.warn("Service Worker nicht registriert:", error);
        pushState.registration = null;
    }
    return pushState.registration;
}

async function pushRegistration() {
    if (!pushState.registration) {
        await registerServiceWorker();
    }
    if (!pushState.registration) {
        throw new Error("Der Service Worker konnte nicht gestartet werden.");
    }
    return navigator.serviceWorker.ready;
}

function currentPushDevice() {
    const endpoint = pushState.subscription?.endpoint;
    return (pushState.overview?.subscriptions || [])
        .find(item => item.endpoint === endpoint) || null;
}

function pushTime(value) {
    if (!value) {
        return "noch nie";
    }
    const date = new Date(value);
    return Number.isNaN(date.getTime())
        ? value
        : date.toLocaleString("de-DE", {dateStyle: "short", timeStyle: "short"});
}

function renderPushStatus() {
    const status = document.getElementById("push-status");
    if (!status) {
        return;
    }
    const support = pushSupport();
    const device = currentPushDevice();
    const permission = "Notification" in window ? Notification.permission : "default";
    let html = "";

    if (support === "insecure") {
        html = `<p class="push-note is-warning">Push-Benachrichtigungen funktionieren nur über
            eine sichere Verbindung (HTTPS). Bitte die Adresse mit https:// aufrufen.</p>`;
    } else if (support === "ios-install") {
        html = `<p class="push-note">Auf iPhone und iPad gibt es Benachrichtigungen nur in der
            installierten App (ab iOS 16.4). Erst als App installieren, dann die App
            öffnen und hier aktivieren.</p>
            <button class="bos-button bos-button-small" type="button"
                onclick="document.getElementById('push-dialog').close(); openInstallDialog()">
                Anleitung zur Installation</button>`;
    } else if (support === "unsupported") {
        html = `<p class="push-note is-warning">Dieser Browser unterstützt keine
            Push-Benachrichtigungen.</p>`;
    } else if (permission === "denied") {
        html = `<p class="push-note is-warning">Benachrichtigungen sind für diese Seite
            blockiert. Bitte in den Browser- bzw. Systemeinstellungen für
            Open BOS Drohnen erlauben und den Dialog neu öffnen.</p>`;
    } else if (device) {
        html = `<p class="push-note is-active">Auf diesem Gerät aktiv
            (${escapeHTML(device.label || pushDeviceLabel())}).
            Zuletzt zugestellt: ${escapeHTML(pushTime(device.last_success_at))}.</p>
            ${device.last_error ? `<p class="push-note is-warning">Letzter Fehler:
                ${escapeHTML(device.last_error)}</p>` : ""}
            <div class="push-actions">
                <button class="bos-button bos-button-small" type="button"
                    onclick="sendTestPush()" ${pushState.busy ? "disabled" : ""}>Test senden</button>
                <button class="bos-button bos-button-small" type="button"
                    onclick="disablePush()" ${pushState.busy ? "disabled" : ""}>Auf diesem Gerät ausschalten</button>
            </div>`;
    } else {
        html = `<p class="push-note">Auf diesem Gerät sind Benachrichtigungen aus.</p>
            <div class="push-actions">
                <button class="bos-button" type="button" onclick="enablePush()"
                    ${pushState.busy || !pushState.overview ? "disabled" : ""}>
                    Auf diesem Gerät aktivieren</button>
            </div>`;
    }
    if (pushState.message) {
        html += `<p class="push-message ${pushState.error ? "is-error" : ""}" role="status">
            ${escapeHTML(pushState.message)}</p>`;
    }
    status.innerHTML = html;
}

function renderPushEvents() {
    const container = document.getElementById("push-events");
    if (!container) {
        return;
    }
    const device = currentPushDevice();
    const events = pushState.overview?.events || [];
    container.hidden = !device || !events.length;
    if (container.hidden) {
        container.innerHTML = "";
        return;
    }
    const chosen = new Set(device.events);
    container.innerHTML = `
        <h3>Benachrichtigen bei</h3>
        ${events.map(event => `
            <label class="push-event">
                <input type="checkbox" value="${escapeHTML(event.key)}"
                    ${chosen.has(event.key) ? "checked" : ""}
                    onchange="savePushEvents()">
                <span>${escapeHTML(event.label)}</span>
            </label>`).join("")}
        <p class="push-hint">Meldungen zu Drohnen kommen nur für Drohnen der eigenen
            Wehr(en). Entwarnungen ersetzen die Störungsmeldung.</p>`;
}

function renderPushDevices() {
    const container = document.getElementById("push-devices");
    if (!container) {
        return;
    }
    const endpoint = pushState.subscription?.endpoint;
    const others = (pushState.overview?.subscriptions || [])
        .filter(item => item.endpoint !== endpoint);
    container.hidden = !others.length;
    container.innerHTML = others.length ? `
        <h3>Weitere Geräte dieses Kontos</h3>
        <ul>
            ${others.map(item => `
                <li>
                    <span>
                        <strong>${escapeHTML(item.label || item.service)}</strong>
                        <small>Zuletzt zugestellt: ${escapeHTML(pushTime(item.last_success_at))}
                        ${item.last_error ? ` · ${escapeHTML(item.last_error)}` : ""}</small>
                    </span>
                    <button class="bos-button bos-button-small" type="button"
                        onclick="removePushDevice(${Number(item.id)})">Entfernen</button>
                </li>`).join("")}
        </ul>` : "";
}

function renderPushDialog() {
    renderPushStatus();
    renderPushEvents();
    renderPushDevices();
}

function setPushMessage(message, error = false) {
    pushState.message = message;
    pushState.error = error;
}

async function refreshPush() {
    try {
        pushState.overview = await api.get("/api/push");
    } catch (error) {
        pushState.overview = null;
        setPushMessage(error.message, true);
    }
    pushState.subscription = null;
    if (pushSupport() === "ok" && pushState.registration) {
        try {
            const registration = await navigator.serviceWorker.ready;
            pushState.subscription = await registration.pushManager.getSubscription();
        } catch (error) {
            pushState.subscription = null;
        }
    }
    // Abo im Browser vorhanden, aber auf dem Server unbekannt (z. B. nach
    // Kontowechsel): erneut melden, damit es wieder Nachrichten erhält.
    if (pushState.subscription && pushState.overview && !currentPushDevice()) {
        await savePushSubscription(pushState.subscription);
    }
    renderPushDialog();
}

async function savePushSubscription(subscription, events = null) {
    const result = await api.post("/api/push/subscriptions", {
        ...subscription.toJSON(),
        label: pushDeviceLabel(),
        events,
    });
    const list = pushState.overview.subscriptions
        .filter(item => item.id !== result.subscription.id);
    pushState.overview.subscriptions = [...list, result.subscription];
}

async function enablePush() {
    if (pushState.busy || !pushState.overview) {
        return;
    }
    pushState.busy = true;
    setPushMessage("");
    renderPushStatus();
    try {
        // Muss direkt aus dem Tippen heraus kommen (Safari).
        const permission = await Notification.requestPermission();
        if (permission !== "granted") {
            throw new Error("Benachrichtigungen wurden nicht erlaubt.");
        }
        const registration = await pushRegistration();
        const key = pushKeyBytes(pushState.overview.public_key);
        let subscription = await registration.pushManager.getSubscription();
        if (subscription) {
            const current = subscription.options?.applicationServerKey;
            const same = current &&
                new Uint8Array(current).every((byte, index) => byte === key[index]);
            if (!same) {
                // Abo eines anderen Serverschlüssels ersetzen.
                await subscription.unsubscribe();
                subscription = null;
            }
        }
        subscription = subscription || await registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: key,
        });
        pushState.subscription = subscription;
        await savePushSubscription(subscription);
        setPushMessage("Benachrichtigungen sind auf diesem Gerät aktiv. Zum Prüfen „Test senden“ wählen.");
    } catch (error) {
        setPushMessage(error.message || "Aktivieren fehlgeschlagen.", true);
    } finally {
        pushState.busy = false;
        renderPushDialog();
    }
}

async function disablePush() {
    const device = currentPushDevice();
    pushState.busy = true;
    setPushMessage("");
    renderPushStatus();
    try {
        if (device) {
            await api.delete(`/api/push/subscriptions/${device.id}`);
            pushState.overview.subscriptions = pushState.overview.subscriptions
                .filter(item => item.id !== device.id);
        }
        await pushState.subscription?.unsubscribe();
        pushState.subscription = null;
        setPushMessage("Benachrichtigungen auf diesem Gerät ausgeschaltet.");
    } catch (error) {
        setPushMessage(error.message, true);
    } finally {
        pushState.busy = false;
        renderPushDialog();
    }
}

async function savePushEvents() {
    const device = currentPushDevice();
    const container = document.getElementById("push-events");
    if (!device || !container) {
        return;
    }
    const events = [...container.querySelectorAll("input[type=checkbox]:checked")]
        .map(input => input.value);
    try {
        const result = await api.put(`/api/push/subscriptions/${device.id}`, {events});
        Object.assign(device, result.subscription);
        setPushMessage(events.length
            ? "Auswahl gespeichert."
            : "Auswahl gespeichert. Ohne Häkchen kommen keine Meldungen.");
    } catch (error) {
        setPushMessage(error.message, true);
    }
    renderPushStatus();
}

async function sendTestPush() {
    pushState.busy = true;
    setPushMessage("");
    renderPushStatus();
    try {
        const result = await api.post("/api/push/test");
        setPushMessage(result.message);
        pushState.overview = await api.get("/api/push");
    } catch (error) {
        setPushMessage(error.message, true);
    } finally {
        pushState.busy = false;
        renderPushDialog();
    }
}

async function removePushDevice(id) {
    try {
        await api.delete(`/api/push/subscriptions/${id}`);
        pushState.overview.subscriptions = pushState.overview.subscriptions
            .filter(item => item.id !== id);
        setPushMessage("Gerät entfernt.");
    } catch (error) {
        setPushMessage(error.message, true);
    }
    renderPushDialog();
}

async function openPushDialog() {
    const dialog = document.getElementById("push-dialog");
    if (!dialog) {
        return;
    }
    setPushMessage("");
    renderPushDialog();
    if (typeof dialog.showModal === "function") {
        dialog.showModal();
    } else {
        dialog.setAttribute("open", "");
    }
    await refreshPush();
}

document.addEventListener("DOMContentLoaded", () => {
    if (document.getElementById("push-dialog")) {
        registerServiceWorker();
    }
});
