"use strict";

// DJI-Geräte auf der Seite Drohnen: benennen, Wehr zuordnen, sperren.

const djiDevices = {data: null, timer: null, message: ""};

// Einsätze je Drohne (Quellen und DJI-Drohnen) mit beteiligten Personen.
const droneHistory = {data: null, open: new Set()};

function droneHistoryCount(count) {
    return count === 1 ? "1 Einsatz" : `${count} Einsätze`;
}

function droneHistoryEntry(entry) {
    const date = new Date(entry.alarm_at).toLocaleDateString("de-DE",
        {day: "2-digit", month: "2-digit", year: "numeric"});
    return `
        <li class="drone-history-entry">
            <div class="dji-device-head">
                <strong>${escapeHTML(date)} · ${escapeHTML(entry.title)}</strong>
                ${entry.exercise ? '<span class="org-chip">Übung</span>' : ""}
                ${entry.running ? '<span class="org-chip is-valid">läuft</span>' : ""}
            </div>
            ${entry.persons.length ? `<ul class="drone-history-persons">${entry.persons.map(person => `
                <li>${escapeHTML(person.name)}
                    <small class="is-muted">${escapeHTML(
                        [person.roles.join(", "), person.organization_name].filter(Boolean).join(" · "))}</small>
                </li>`).join("")}</ul>`
                : '<small class="is-muted">Keine Personen eingetragen.</small>'}
        </li>`;
}

function droneHistoryHTML(kind, key) {
    if (!droneHistory.data) {
        return "";
    }
    const item = droneHistory.data[kind]?.[key] || {count: 0, hidden: 0, incidents: []};
    if (!item.count) {
        return '<p class="drone-history is-muted">Noch in keinem Einsatz.</p>';
    }
    const id = `${kind}:${key}`;
    return `
        <details class="drone-history" data-history-id="${escapeHTML(id)}"
            ${droneHistory.open.has(id) ? "open" : ""} ontoggle="rememberDroneHistory(this)">
            <summary>${droneHistoryCount(item.count)}</summary>
            ${item.incidents.length
                ? `<ul class="drone-history-list">${item.incidents.map(droneHistoryEntry).join("")}</ul>` : ""}
            ${item.hidden ? `<p class="is-muted">${item.incidents.length ? "Weitere " : ""}${droneHistoryCount(item.hidden)}
                ohne Einsichtsrecht.</p>` : ""}
        </details>`;
}

function rememberDroneHistory(element) {
    droneHistory.open[element.open ? "add" : "delete"](element.dataset.historyId);
}

// Platzhalter in den Quellenlisten füllen (auch nach deren Neuaufbau).
function fillDroneHistory() {
    document.querySelectorAll("[data-source-history]").forEach(element => {
        element.innerHTML = droneHistoryHTML("sources", element.dataset.sourceHistory);
    });
}

async function loadDroneHistory() {
    try {
        droneHistory.data = await api.get("/api/drones/history");
    } catch (error) {
        console.debug("Einsätze der Drohnen:", error);
        return;
    }
    fillDroneHistory();
    renderDjiDevices();
}

function renderDjiDevices() {
    const root = document.getElementById("dji-devices");
    const data = djiDevices.data;
    if (!root || !data) {
        return;
    }
    // Laufende Eingaben nicht durch das Nachladen überschreiben.
    if (root.contains(document.activeElement) && ["INPUT", "SELECT"].includes(document.activeElement.tagName)) {
        return;
    }
    const hint = !data.configured
        ? "Die DJI-Anbindung ist auf dem Server noch nicht eingerichtet."
        : (data.broker_connected ? "Der Nachrichtendienst läuft." : "Der Nachrichtendienst ist nicht erreichbar.");
    const organizations = item => [
        `<option value="">– keine Wehr –</option>`,
        ...data.organizations.map(org => `<option value="${Number(org.id)}"
            ${org.id === item.organization_id ? "selected" : ""}>${escapeHTML(org.name)}</option>`),
        item.organization_id && !data.organizations.some(org => org.id === item.organization_id)
            ? `<option value="${Number(item.organization_id)}" selected>
                ${escapeHTML(data.organization_names[item.organization_id] ?? "?")}</option>` : "",
    ].join("");
    root.innerHTML = `
        <p class="incident-hint">${escapeHTML(hint)}</p>
        ${djiDevices.message ? `<p class="service-inline-status">${escapeHTML(djiDevices.message)}</p>` : ""}
        ${data.devices.length ? `<ul class="dji-device-list">${data.devices.map(item => `
            <li data-serial="${escapeHTML(item.serial)}">
                <div class="dji-device-head">
                    <strong>${escapeHTML(item.name || item.model)}</strong>
                    <span class="org-chip ${item.state.online ? "is-valid" : "is-muted"}">
                        ${item.state.online ? "sendet" : "offline"}</span>
                </div>
                <small class="is-muted">${item.kind === "aircraft" ? "Drohne" : "Fernsteuerung"} ·
                    ${escapeHTML(item.model)} · ${escapeHTML(item.serial)}
                    ${item.blocked ? " · gesperrt" : ""}</small>
                ${item.kind === "aircraft" ? droneHistoryHTML("devices", item.serial) : ""}
                ${item.can_manage ? `<form class="dji-device-form" onsubmit="saveDjiDevice(event)">
                    <input class="bos-input" name="name" maxlength="80" value="${escapeHTML(item.name)}"
                        placeholder="Rufname" aria-label="Rufname">
                    <select class="bos-input" name="organization_id" aria-label="Wehr">${organizations(item)}</select>
                    <button class="bos-button bos-button-small bos-button-green" type="submit">Speichern</button>
                    <button class="bos-button bos-button-small" type="button"
                        onclick="blockDjiDevice(this, ${item.blocked ? "false" : "true"})">
                        ${item.blocked ? "Entsperren" : "Sperren"}</button>
                    <button class="bos-button bos-button-small app-logout" type="button"
                        onclick="deleteDjiDevice(this)">Entfernen</button>
                </form>` : ""}
            </li>`).join("")}</ul>`
            : '<p class="incident-empty">Noch kein Gerät. Neue Geräte erscheinen nach dem ersten Verbinden.</p>'}`;
}

async function djiDeviceRequest(request, message = "") {
    try {
        djiDevices.data = await request();
        djiDevices.message = message;
    } catch (error) {
        djiDevices.message = error.message;
    }
    document.activeElement?.blur();
    renderDjiDevices();
}

function djiDeviceUrl(element) {
    return `/api/dji/devices/${encodeURIComponent(element.closest("li").dataset.serial)}`;
}

function djiPatch(url, body) {
    return api.request(url, {
        method: "PATCH",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body),
    });
}

function saveDjiDevice(event) {
    event.preventDefault();
    const form = event.target;
    const body = {name: form.elements.name.value};
    const device = djiDevices.data.devices.find(item => item.serial === form.closest("li").dataset.serial);
    const organization = Number(form.elements.organization_id.value) || null;
    if (organization !== device.organization_id) {
        body.organization_id = organization;
    }
    djiDeviceRequest(() => djiPatch(djiDeviceUrl(form), body), "Gespeichert.");
}

function blockDjiDevice(button, blocked) {
    djiDeviceRequest(() => djiPatch(djiDeviceUrl(button), {blocked}), blocked ? "Gerät gesperrt." : "Gerät entsperrt.");
}

function deleteDjiDevice(button) {
    if (!window.confirm("Gerät entfernen? Aufzeichnungen in Einsätzen bleiben erhalten.")) {
        return;
    }
    const url = djiDeviceUrl(button);
    djiDeviceRequest(() => api.request(url, {method: "DELETE"}), "Gerät entfernt.");
}

// Ohne Verwaltungsrechte: Quellen der eigenen Wehr als Liste.
function renderDroneSourceList(sources) {
    const root = document.getElementById("drone-source-list");
    if (!root) {
        return;
    }
    root.innerHTML = sources.length
        ? `<ul class="dji-device-list">${sources.map(item => `
            <li>
                <div class="dji-device-head">
                    <strong>${escapeHTML(item.name)}</strong>
                    ${item.enabled ? "" : '<span class="org-chip is-muted">deaktiviert</span>'}
                </div>
                <small class="is-muted">${escapeHTML(
                    [item.drone_type, item.organization_name].filter(Boolean).join(" · ") || "–")}</small>
                <div data-source-history="${escapeHTML(item.id)}"></div>
            </li>`).join("")}</ul>`
        : '<p class="incident-empty">Für die eigene Wehr ist noch keine Drohne eingetragen.</p>';
    fillDroneHistory();
}

function setDjiDevicesActive(active) {
    window.clearInterval(djiDevices.timer);
    // Adresse dieses Servers in die Kurzanleitung eintragen.
    document.querySelectorAll("[data-dji-url]").forEach(element => {
        element.textContent = `${window.location.origin}/dji`;
    });
    if (!active || !document.getElementById("dji-devices")) {
        return;
    }
    if (document.getElementById("drone-source-list")) {
        api.get("/api/drones/sources")
            .then(data => renderDroneSourceList(data.sources))
            .catch(error => console.debug("Drohnen:", error));
    }
    const load = () => {
        if (document.visibilityState === "visible") {
            api.get("/api/dji/devices").then(data => {
                djiDevices.data = data;
                renderDjiDevices();
            }).catch(error => console.debug("DJI-Geräte:", error));
        }
    };
    load();
    loadDroneHistory();
    djiDevices.timer = window.setInterval(load, 5000);
}
