// ==========================================================
// Einsätze: Übersicht, Anlegen, Einsatzführung
// ==========================================================

const INCIDENT_LIST_POLL_MS = 20000;
const INCIDENT_DETAIL_POLL_MS = 8000;

const incidentState = {
    meta: null,
    list: [],
    detail: null,
    openId: null,
    creating: false,
    editingAlarm: false,
    message: "",
    error: false,
    lastLink: null,
    timer: null,
    active: false,
};

// ----------------------------------------------------------
// Hilfsfunktionen
// ----------------------------------------------------------

function incidentTime(value, withDate = true) {
    if (!value) {
        return "–";
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return value;
    }
    return withDate
        ? date.toLocaleString("de-DE", {dateStyle: "short", timeStyle: "short"})
        : date.toLocaleTimeString("de-DE", {hour: "2-digit", minute: "2-digit"});
}

function incidentInputTime(value) {
    // ISO mit Zeitzone → Wert für <input type="datetime-local"> (Ortszeit).
    const date = value ? new Date(value) : new Date();
    if (Number.isNaN(date.getTime())) {
        return "";
    }
    const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
    return local.toISOString().slice(0, 16);
}

function incidentDuration(start, end) {
    const from = new Date(start);
    const to = end ? new Date(end) : new Date();
    const minutes = Math.max(0, Math.round((to - from) / 60000));
    if (Number.isNaN(minutes)) {
        return "";
    }
    const hours = Math.floor(minutes / 60);
    return hours ? `${hours} h ${minutes % 60} min` : `${minutes} min`;
}

function incidentStatusChip(status, label, exercise = false) {
    return `<span class="incident-status is-${escapeHTML(status)}">${escapeHTML(label || status)}</span>${exercise
        ? '<span class="incident-exercise" title="Übung, kein Realeinsatz">Übung</span>' : ""}`;
}

function incidentOptions(items, selected, valueKey = "id", labelFn = item => item.name) {
    return items.map(item => `
        <option value="${escapeHTML(String(item[valueKey]))}" ${String(item[valueKey]) === String(selected) ? "selected" : ""}>
            ${escapeHTML(labelFn(item))}</option>`).join("");
}

function incidentOrgLabel(org) {
    return org.short_name ? `${org.name} (${org.short_name})` : org.name;
}

function setIncidentMessage(message, error = false) {
    incidentState.message = message;
    incidentState.error = error;
}

function incidentMessageHTML() {
    if (!incidentState.message) {
        return "";
    }
    return `<p class="incident-message ${incidentState.error ? "is-error" : ""}" role="status">
        ${escapeHTML(incidentState.message)}</p>`;
}

function incidentFormBusy() {
    const root = document.getElementById("incidents-root");
    const focused = document.activeElement;
    return Boolean(
        root && focused && root.contains(focused) &&
        ["INPUT", "TEXTAREA", "SELECT"].includes(focused.tagName)
    ) || incidentState.creating || incidentState.editingAlarm;
}

// ----------------------------------------------------------
// Laden
// ----------------------------------------------------------

async function loadIncidents({quiet = false} = {}) {
    try {
        const data = await api.get("/api/incidents");
        incidentState.meta = data;
        incidentState.list = data.incidents;
    } catch (error) {
        if (!quiet) {
            setIncidentMessage(error.message, true);
        }
    }
    if (!incidentState.openId) {
        renderIncidents();
    }
}

async function loadIncidentDetail(id, {quiet = false} = {}) {
    try {
        incidentState.detail = await api.get(`/api/incidents/${id}`);
        incidentState.openId = id;
    } catch (error) {
        if (error.status === 404) {
            incidentState.openId = null;
            incidentState.detail = null;
            setIncidentMessage("Der Einsatz ist nicht mehr verfügbar.", true);
            await loadIncidents();
            return;
        }
        if (!quiet) {
            setIncidentMessage(error.message, true);
        }
    }
    renderIncidents();
}

function scheduleIncidentRefresh() {
    window.clearTimeout(incidentState.timer);
    if (!incidentState.active) {
        return;
    }
    const delay = incidentState.openId ? INCIDENT_DETAIL_POLL_MS : INCIDENT_LIST_POLL_MS;
    incidentState.timer = window.setTimeout(async () => {
        if (document.visibilityState === "visible" && !incidentFormBusy()) {
            if (incidentState.openId) {
                await loadIncidentDetail(incidentState.openId, {quiet: true});
            } else {
                await loadIncidents({quiet: true});
            }
        }
        scheduleIncidentRefresh();
    }, delay);
}

function setIncidentsPageActive(active) {
    incidentState.active = active;
    if (active) {
        if (incidentState.openId) {
            loadIncidentDetail(incidentState.openId);
        } else {
            loadIncidents();
        }
        scheduleIncidentRefresh();
    } else {
        window.clearTimeout(incidentState.timer);
    }
}

function openIncident(id) {
    incidentState.openId = Number(id);
    incidentState.editingAlarm = false;
    incidentState.lastLink = null;
    setIncidentMessage("");
    if (window.location.hash !== `#incidents/${id}`) {
        history.replaceState(null, "", `#incidents/${id}`);
    }
    if (typeof showPage === "function" && !document.getElementById("page-incidents")?.classList.contains("active")) {
        showPage("incidents");
    } else {
        loadIncidentDetail(incidentState.openId);
    }
    scheduleIncidentRefresh();
}

function closeIncident() {
    incidentState.openId = null;
    incidentState.detail = null;
    incidentState.lastLink = null;
    setIncidentMessage("");
    if (window.location.hash.startsWith("#incidents")) {
        history.replaceState(null, "", window.location.pathname);
    }
    loadIncidents();
    scheduleIncidentRefresh();
}

// ----------------------------------------------------------
// Übersicht
// ----------------------------------------------------------

function incidentCard(item) {
    const title = item.keyword || item.title || "Einsatz";
    return `
        <li>
            <button class="incident-card is-${escapeHTML(item.status)}${item.exercise ? " is-exercise" : ""}" type="button" onclick="openIncident(${Number(item.id)})">
                <span class="incident-card-head">
                    ${incidentStatusChip(item.status, item.status_label, item.exercise)}
                    <span class="incident-code">${escapeHTML(item.code)}</span>
                </span>
                <strong>${escapeHTML(title)}</strong>
                <span class="incident-card-meta">
                    ${item.address ? `${escapeHTML(item.address)} · ` : ""}${escapeHTML(item.lead_name)}
                    ${item.organization_ids.length > 1 ? ` + ${item.organization_ids.length - 1} Wehr(en)` : ""}
                </span>
                <span class="incident-card-meta">
                    Alarm ${escapeHTML(incidentTime(item.alarm_at))}
                    · ${escapeHTML(incidentDuration(item.alarm_at, item.ended_at))}
                    ${item.status === "running" ? ` · ${item.source_count} Drohne(n)` : ""}
                </span>
            </button>
        </li>`;
}

function renderIncidentCreateForm() {
    const meta = incidentState.meta;
    if (!incidentState.creating || !meta) {
        return "";
    }
    const sources = meta.sources || [];
    return `
        <form class="org-form incident-form" onsubmit="createIncident(event)">
            <h3>Neuer Einsatz</h3>
            <div class="form-grid">
                <label class="form-field">
                    <span>Führende Wehr</span>
                    <select class="bos-input" name="lead_organization_id" required>
                        ${incidentOptions(meta.lead_options, meta.lead_options[0]?.id, "id", incidentOrgLabel)}
                    </select>
                </label>
                <label class="form-field">
                    <span>Alarmzeit</span>
                    <input class="bos-input" type="datetime-local" name="alarm_at" required
                        value="${incidentInputTime(null)}">
                </label>
                <label class="form-field form-field-wide">
                    <span>Alarmstichwort</span>
                    <input class="bos-input" name="keyword" maxlength="80" required
                        placeholder="z. B. TH Person vermisst">
                </label>
                <label class="form-field form-field-wide">
                    <span>Einsatzadresse</span>
                    <input class="bos-input" name="address" maxlength="200"
                        placeholder="Straße, Ort oder Beschreibung">
                </label>
                <label class="form-field form-field-wide">
                    <span>Alarmierungstext / Meldebild</span>
                    <textarea class="bos-input" name="alarm_text" rows="3" maxlength="4000"
                        placeholder="Text der Alarmierung, z. B. aus GroupAlarm"></textarea>
                </label>
                <label class="form-field">
                    <span>Alarmierte Einheiten</span>
                    <input class="bos-input" name="alerted_units" maxlength="300">
                </label>
                <label class="form-field">
                    <span>Einsatznummer Leitstelle</span>
                    <input class="bos-input" name="dispatch_number" maxlength="40">
                </label>
            </div>
            <label class="incident-exercise-toggle">
                <input type="checkbox" name="exercise">
                <span><strong>Übung</strong> – kein Realeinsatz; wird überall deutlich als Übung gekennzeichnet.</span>
            </label>
            ${sources.length ? `
                <fieldset class="incident-sources-pick">
                    <legend>Drohnen im Einsatz</legend>
                    ${sources.map(source => `
                        <label><input type="checkbox" name="source_ids" value="${escapeHTML(source.id)}">
                            ${escapeHTML(source.name)}</label>`).join("")}
                </fieldset>` : ""}
            <p class="incident-hint">Das Wetter am Einsatzort wird beim Anlegen automatisch
                festgehalten. Beteiligte Wehren und Personen lassen sich danach ergänzen.</p>
            <div class="org-form-actions">
                <button class="bos-button bos-button-small bos-button-red" type="submit">Einsatz anlegen</button>
                <button class="bos-button bos-button-small" type="button" onclick="toggleIncidentCreate(false)">Abbrechen</button>
            </div>
        </form>`;
}

function renderIncidentList() {
    const meta = incidentState.meta;
    const running = incidentState.list.filter(item => item.status === "running");
    const done = incidentState.list.filter(item => item.status !== "running");
    const canCreate = Boolean(meta?.lead_options?.length);
    return `
        ${incidentMessageHTML()}
        <section class="bos-card incident-section">
            <div class="org-block-header">
                <h2>Laufende Einsätze</h2>
                ${canCreate && !incidentState.creating ? `
                    <button class="bos-button bos-button-red" type="button" onclick="toggleIncidentCreate(true)">
                        ＋ Neuer Einsatz</button>` : ""}
            </div>
            ${renderIncidentCreateForm()}
            ${running.length
                ? `<ul class="incident-cards">${running.map(incidentCard).join("")}</ul>`
                : '<p class="incident-empty">Kein laufender Einsatz.</p>'}
        </section>
        <section class="bos-card incident-section">
            <h2>Beendete Einsätze</h2>
            ${done.length
                ? `<ul class="incident-cards is-compact">${done.map(incidentCard).join("")}</ul>`
                : '<p class="incident-empty">Noch keine beendeten Einsätze.</p>'}
        </section>`;
}

function toggleIncidentCreate(open) {
    incidentState.creating = open;
    setIncidentMessage("");
    renderIncidents();
    if (open) {
        document.querySelector('.incident-form input[name="keyword"]')?.focus();
    }
}

async function createIncident(event) {
    event.preventDefault();
    const form = event.target;
    const data = new FormData(form);
    const payload = {
        lead_organization_id: Number(data.get("lead_organization_id")),
        alarm_at: data.get("alarm_at"),
        keyword: data.get("keyword"),
        address: data.get("address"),
        alarm_text: data.get("alarm_text"),
        alerted_units: data.get("alerted_units"),
        dispatch_number: data.get("dispatch_number"),
        exercise: data.get("exercise") === "on",
        source_ids: data.getAll("source_ids"),
    };
    form.querySelector('button[type="submit"]').disabled = true;
    try {
        const result = await api.post("/api/incidents", payload);
        incidentState.creating = false;
        setIncidentMessage(`Einsatz ${result.incident.code} angelegt.`);
        openIncident(result.incident.id);
    } catch (error) {
        setIncidentMessage(error.message, true);
        form.querySelector('button[type="submit"]').disabled = false;
        renderIncidents();
    }
}

// ----------------------------------------------------------
// Einsatz im Detail
// ----------------------------------------------------------

function renderIncidentHeader(detail) {
    const incident = detail.incident;
    const can = detail.can;
    const title = incident.keyword || incident.title || "Einsatz";
    const actions = [];
    if (can.edit && incident.status === "running") {
        actions.push(`<button class="bos-button bos-button-small bos-button-red" type="button"
            onclick="setIncidentStatus('ended')">Einsatz beenden</button>`);
    }
    if (can.edit && incident.status === "ended") {
        actions.push(`<button class="bos-button bos-button-small" type="button"
            onclick="setIncidentStatus('running')">Wieder aufnehmen</button>`);
    }
    if (can.administer && incident.status === "ended") {
        actions.push(`<button class="bos-button bos-button-small bos-button-green" type="button"
            onclick="setIncidentStatus('closed')">Abschließen</button>`);
    }
    if (can.administer && incident.status === "closed") {
        actions.push(`<button class="bos-button bos-button-small" type="button"
            onclick="setIncidentStatus('ended')">Zur Nachbearbeitung öffnen</button>`);
    }
    actions.push(`<a class="bos-button bos-button-small" href="/api/incidents/${incident.id}/report"
        target="_blank" rel="noopener">Bericht / PDF</a>`);
    if (can.administer) {
        actions.push(`<button class="bos-button bos-button-small app-logout" type="button"
            onclick="deleteIncident()">Löschen</button>`);
    }
    return `
        <div class="incident-topline">
            <button class="incident-back" type="button" onclick="closeIncident()">← Alle Einsätze</button>
        </div>
        ${incidentMessageHTML()}
        <section class="bos-card incident-head is-${escapeHTML(incident.status)}${incident.exercise ? " is-exercise" : ""}">
            <div class="incident-head-main">
                <span class="incident-card-head">
                    ${incidentStatusChip(incident.status, incident.status_label, incident.exercise)}
                    <span class="incident-code">${escapeHTML(incident.code)}</span>
                </span>
                <h2>${escapeHTML(title)}</h2>
                ${incident.title && incident.keyword ? `<p>${escapeHTML(incident.title)}</p>` : ""}
                <p class="incident-card-meta">
                    ${incident.address ? `${escapeHTML(incident.address)} · ` : ""}
                    Alarm ${escapeHTML(incidentTime(incident.alarm_at))}
                    ${incident.ended_at ? ` · Ende ${escapeHTML(incidentTime(incident.ended_at))}` : ""}
                    · Dauer ${escapeHTML(incidentDuration(incident.alarm_at, incident.ended_at))}
                </p>
                <p class="incident-card-meta">Führende Wehr: <strong>${escapeHTML(incident.lead_name)}</strong></p>
            </div>
            <div class="org-row-actions incident-actions">${actions.join("")}</div>
        </section>`;
}

function renderIncidentAlarm(detail) {
    const incident = detail.incident;
    const can = detail.can;
    if (incidentState.editingAlarm && can.edit) {
        return `
            <section class="bos-card incident-section">
                <form class="incident-form" onsubmit="saveIncidentAlarm(event)">
                    <h3>Alarmierung bearbeiten</h3>
                    <div class="form-grid">
                        <label class="form-field">
                            <span>Alarmzeit</span>
                            <input class="bos-input" type="datetime-local" name="alarm_at"
                                value="${incidentInputTime(incident.alarm_at)}" required>
                        </label>
                        <label class="form-field">
                            <span>Führende Wehr</span>
                            <select class="bos-input" name="lead_organization_id"
                                ${can.administer ? "" : 'disabled title="Die Führung übergeben nur Admins der führenden Wehr."'}>
                                ${incidentOptions(detail.organizations || [], incident.lead_organization_id, "id", incidentOrgLabel)}
                            </select>
                        </label>
                        <label class="form-field form-field-wide">
                            <span>Alarmstichwort</span>
                            <input class="bos-input" name="keyword" maxlength="80" value="${escapeHTML(incident.keyword)}">
                        </label>
                        <label class="form-field form-field-wide">
                            <span>Titel (optional)</span>
                            <input class="bos-input" name="title" maxlength="120" value="${escapeHTML(incident.title)}">
                        </label>
                        <label class="form-field form-field-wide">
                            <span>Einsatzadresse</span>
                            <input class="bos-input" name="address" maxlength="200" value="${escapeHTML(incident.address)}">
                        </label>
                        <label class="form-field form-field-wide">
                            <span>Alarmierungstext / Meldebild</span>
                            <textarea class="bos-input" name="alarm_text" rows="4" maxlength="4000">${escapeHTML(incident.alarm_text)}</textarea>
                        </label>
                        <label class="form-field">
                            <span>Alarmierte Einheiten</span>
                            <input class="bos-input" name="alerted_units" maxlength="300" value="${escapeHTML(incident.alerted_units)}">
                        </label>
                        <label class="form-field">
                            <span>Einsatznummer Leitstelle</span>
                            <input class="bos-input" name="dispatch_number" maxlength="40" value="${escapeHTML(incident.dispatch_number)}">
                        </label>
                    </div>
                    <label class="incident-exercise-toggle">
                        <input type="checkbox" name="exercise" ${incident.exercise ? "checked" : ""}>
                        <span><strong>Übung</strong> – kein Realeinsatz</span>
                    </label>
                    <p class="incident-hint">Eine geänderte Alarmzeit ändert auch die Einsatzkennung.</p>
                    <div class="org-form-actions">
                        <button class="bos-button bos-button-small bos-button-green" type="submit">Speichern</button>
                        <button class="bos-button bos-button-small" type="button" onclick="editIncidentAlarm(false)">Abbrechen</button>
                    </div>
                </form>
            </section>`;
    }
    const rows = [
        ["Art", incident.exercise ? "Übung (kein Realeinsatz)" : "Realeinsatz"],
        ["Alarmstichwort", incident.keyword],
        ["Alarmzeit", incidentTime(incident.alarm_at)],
        ["Einsatzadresse", incident.address],
        ["Alarmierte Einheiten", incident.alerted_units],
        ["Einsatznummer Leitstelle", incident.dispatch_number],
        ["Einsatzort", incident.latitude !== null && incident.latitude !== undefined
            ? `${Number(incident.latitude).toFixed(5)}, ${Number(incident.longitude).toFixed(5)}`
            : ""],
    ].filter(([, value]) => value);
    return `
        <section class="bos-card incident-section">
            <div class="org-block-header">
                <h3>Alarmierung</h3>
                ${can.edit ? `<button class="bos-button bos-button-small" type="button" onclick="editIncidentAlarm(true)">Bearbeiten</button>` : ""}
            </div>
            <dl class="incident-facts">
                ${rows.map(([label, value]) => `<dt>${escapeHTML(label)}</dt><dd>${escapeHTML(value)}</dd>`).join("")}
            </dl>
            ${incident.alarm_text ? `<p class="incident-alarm-text">${escapeHTML(incident.alarm_text)}</p>` : ""}
        </section>`;
}

function renderIncidentSources(detail) {
    const can = detail.can;
    const active = detail.sources.filter(item => item.active);
    const earlier = detail.sources.filter(item => !item.active);
    const available = detail.available_sources || [];
    return `
        <section class="bos-card incident-section">
            <div class="org-block-header">
                <h3>Drohnen im Einsatz</h3>
                ${active.length ? `<button class="bos-button bos-button-small" type="button" onclick="showPage('streams')">Livebilder</button>` : ""}
            </div>
            ${active.length ? `<ul class="org-memberships">
                ${active.map(item => `
                    <li>
                        <span><strong>${escapeHTML(item.name)}</strong>
                            <small class="is-muted">seit ${escapeHTML(incidentTime(item.added_at, false))} Uhr</small></span>
                        ${can.edit ? `<button class="bos-button bos-button-small" type="button"
                            onclick="removeIncidentSource('${escapeHTML(item.source_id)}')">Aus Einsatz nehmen</button>` : ""}
                    </li>`).join("")}
            </ul>` : '<p class="incident-empty">Keine Drohne zugeordnet.</p>'}
            ${earlier.length ? `<p class="incident-hint">Vorher im Einsatz: ${earlier.map(item =>
                `${escapeHTML(item.name)} (${escapeHTML(incidentTime(item.added_at, false))}–${escapeHTML(incidentTime(item.removed_at, false))})`).join(", ")}</p>` : ""}
            ${can.edit && detail.incident.status === "running" && available.length ? `
                <div class="org-inline-add">
                    <select id="incident-add-source" class="bos-input">
                        ${incidentOptions(available, null)}
                    </select>
                    <button class="bos-button bos-button-small" type="button" onclick="addIncidentSource()">Zuordnen</button>
                </div>` : ""}
            ${active.length ? `<p class="incident-hint">Alle beteiligten Wehren sehen die Livebilder dieser
                Drohnen, solange der Einsatz läuft.</p>` : ""}
        </section>`;
}

function renderIncidentMapSection(detail) {
    const items = detail.map_items || [];
    const statusCounts = {};
    items.forEach(item => {
        statusCounts[item.status_label] = (statusCounts[item.status_label] || 0) + 1;
    });
    return `
        <section class="bos-card incident-section">
            <div class="org-block-header">
                <h3>Einsatzkarte</h3>
                <button class="bos-button bos-button-small" type="button"
                    onclick="openIncidentMap(${Number(detail.incident.id)})">Karte öffnen</button>
            </div>
            ${items.length ? `
                <p class="incident-hint">${Object.entries(statusCounts)
                    .map(([label, count]) => `${count} ${escapeHTML(label)}`).join(" · ")}</p>
                <ul class="incident-quadrants">
                    ${items.map(item => `
                        <li class="is-${escapeHTML(item.status)}">
                            <strong>${escapeHTML(item.name)}</strong>
                            <span>${escapeHTML(item.status_label)}${item.assignee ? ` · ${escapeHTML(item.assignee)}` : ""}</span>
                        </li>`).join("")}
                </ul>` : `<p class="incident-empty">Noch keine Quadranten. ${detail.can.edit
                    ? "Auf der Karte lassen sich Raster und Suchflächen zeichnen und der Einsatzort setzen."
                    : ""}</p>`}
            <p class="incident-hint">Alle Beteiligten sehen Änderungen auf der Karte sofort.</p>
        </section>`;
}

function renderIncidentChecklists(detail) {
    const lists = detail.checklists || [];
    const templates = detail.checklist_templates || [];
    const canAdd = detail.can.edit;
    return `
        <section class="bos-card incident-section">
            <h3>Checklisten</h3>
            ${lists.length ? `<ul class="org-memberships">
                ${lists.map(list => `
                    <li>
                        <span>
                            <strong>${escapeHTML(list.title)}</strong>
                            <small class="is-muted">${list.done}/${list.total} erledigt${list.open_required.length
                                ? ` · <span class="incident-warning">${list.open_required.length} Pflicht offen</span>` : ""}</small>
                        </span>
                        <button class="bos-button bos-button-small" type="button"
                            onclick="openChecklist(${Number(list.id)})">${canAdd ? "Abhaken" : "Ansehen"}</button>
                    </li>`).join("")}
            </ul>` : '<p class="incident-empty">Noch keine Checkliste in diesem Einsatz.</p>'}
            ${canAdd ? `
                <div class="org-inline-add">
                    <select id="incident-add-checklist" class="bos-input" aria-label="Vorlage">
                        ${templates.map(item => `<option value="${Number(item.id)}">${escapeHTML(item.title)} (${item.item_count})</option>`).join("")}
                        <option value="">Leere Liste</option>
                    </select>
                    <button class="bos-button bos-button-small" type="button" onclick="addIncidentChecklist()">Checkliste hinzufügen</button>
                </div>` : ""}
        </section>`;
}

async function addIncidentChecklist() {
    const value = document.getElementById("incident-add-checklist")?.value;
    try {
        const result = await api.post("/api/checklists", {
            incident_id: incidentState.openId,
            template_id: value ? Number(value) : null,
            title: value ? "" : "Checkliste",
        });
        openChecklist(result.checklist.id);
    } catch (error) {
        setIncidentMessage(error.message, true);
        renderIncidents();
    }
}

function incidentOpenRequired() {
    return (incidentState.detail?.checklists || [])
        .filter(list => list.open_required.length)
        .map(list => `„${list.title}“: ${list.open_required.join(", ")}`);
}

function renderIncidentOrganizations(detail) {
    const incident = detail.incident;
    const can = detail.can;
    const used = new Set(incident.organization_ids);
    const options = (detail.organizations || []).filter(org => !used.has(org.id));
    return `
        <section class="bos-card incident-section">
            <h3>Beteiligte Wehren</h3>
            <ul class="org-memberships">
                <li><span><strong>${escapeHTML(incident.lead_name)}</strong></span>
                    <span class="org-chip">führend</span></li>
                ${incident.involved.map(entry => `
                    <li>
                        <span>${escapeHTML(entry.name)}
                            <small class="is-muted">seit ${escapeHTML(incidentTime(entry.added_at, false))} Uhr</small></span>
                        ${can.edit ? `<button class="bos-button bos-button-small" type="button"
                            onclick="removeIncidentOrganization(${Number(entry.organization_id)})">Entfernen</button>` : ""}
                    </li>`).join("")}
            </ul>
            ${can.edit && options.length ? `
                <div class="org-inline-add">
                    <select id="incident-add-org" class="bos-input">
                        ${incidentOptions(options, null, "id", incidentOrgLabel)}
                    </select>
                    <button class="bos-button bos-button-small" type="button" onclick="addIncidentOrganization()">Beteiligen</button>
                </div>
                <p class="incident-hint">Beteiligte Wehren sehen den Einsatz und die Livebilder seiner Drohnen.</p>` : ""}
        </section>`;
}

function renderIncidentPeople(detail) {
    const can = detail.can;
    const roles = incidentState.meta?.roles || {};
    const people = detail.participants;
    const candidates = detail.candidates || [];
    return `
        <section class="bos-card incident-section incident-section-wide">
            <h3>Personen im Einsatz</h3>
            ${people.length ? `<div class="incident-table-wrap"><table class="incident-table">
                <thead><tr><th>Name</th><th>Funktion</th><th>Wehr</th><th>Zeitraum</th><th></th></tr></thead>
                <tbody>
                ${people.map(person => `
                    <tr class="${person.until_at ? "is-ended" : ""}">
                        <td>${escapeHTML(person.name)}${person.user_id ? "" : ' <small class="is-muted">(ohne Konto)</small>'}
                            ${person.warning ? `<br><small class="incident-warning">⚠ ${escapeHTML(person.warning)}</small>` : ""}</td>
                        <td>${escapeHTML(person.role_label)}</td>
                        <td>${escapeHTML(person.organization_name || "–")}</td>
                        <td>${escapeHTML(incidentTime(person.from_at, false))}–${person.until_at ? escapeHTML(incidentTime(person.until_at, false)) : ""}</td>
                        <td class="incident-table-actions">
                            ${can.edit && !person.until_at ? `<button class="bos-button bos-button-small" type="button"
                                onclick="endIncidentParticipant(${Number(person.id)})">Austragen</button>` : ""}
                            ${can.edit ? `<button class="bos-button bos-button-small" type="button"
                                onclick="removeIncidentParticipant(${Number(person.id)})" title="Eintrag löschen">✕</button>` : ""}
                        </td>
                    </tr>`).join("")}
                </tbody></table></div>` : '<p class="incident-empty">Noch niemand eingetragen.</p>'}
            ${can.edit ? `
                <form class="org-inline-add incident-person-form" onsubmit="addIncidentParticipant(event)">
                    <select class="bos-input" name="user_id" aria-label="Konto">
                        <option value="">Person ohne Konto …</option>
                        ${candidates.map(item => `<option value="${Number(item.user_id)}">
                            ${escapeHTML(item.name)} · ${escapeHTML(item.organization_name)}${item.pilot ? " · Fernpilot" : ""}</option>`).join("")}
                    </select>
                    <input class="bos-input" name="name" maxlength="80" placeholder="Name (ohne Konto)" aria-label="Name ohne Konto">
                    <select class="bos-input" name="role" aria-label="Funktion">
                        ${Object.entries(roles).map(([key, label]) => `<option value="${escapeHTML(key)}">${escapeHTML(label)}</option>`).join("")}
                    </select>
                    <button class="bos-button bos-button-small" type="submit">Eintragen</button>
                </form>` : ""}
        </section>`;
}

function renderIncidentWeather(detail) {
    const weather = detail.incident.weather;
    const can = detail.can;
    let body = '<p class="incident-empty">Noch kein Wetter erfasst.</p>';
    if (weather) {
        const current = weather.current || {};
        const values = [
            ["Wind", current.wind_speed_ms != null ? `${current.wind_speed_ms} m/s` : null],
            ["Böen", current.wind_gust_ms != null ? `${current.wind_gust_ms} m/s` : null],
            ["Temperatur", current.temperature_c != null ? `${current.temperature_c} °C` : null],
            ["Niederschlag", current.precipitation_mm_h != null ? `${current.precipitation_mm_h} mm/h` : null],
            ["Sicht", current.visibility_m != null ? `${(current.visibility_m / 1000).toFixed(1)} km` : null],
            ["Kp-Index", weather.kp?.kp != null ? String(weather.kp.kp) : null],
        ].filter(([, value]) => value);
        body = `
            <p class="incident-weather-level is-${escapeHTML(weather.assessment?.level || "unknown")}">
                ${escapeHTML(weather.assessment?.summary || "Keine Bewertung")}</p>
            <dl class="incident-facts is-compact">
                ${values.map(([label, value]) => `<dt>${escapeHTML(label)}</dt><dd>${escapeHTML(value)}</dd>`).join("")}
            </dl>
            ${(weather.alerts || []).length ? `<p class="incident-warning">⚠ ${weather.alerts.map(item => escapeHTML(item.headline || item.event)).join(" · ")}</p>` : ""}
            <p class="incident-hint">Erfasst ${escapeHTML(incidentTime(weather.captured_at))} · ${escapeHTML(weather.location?.name || "")}</p>`;
    }
    return `
        <section class="bos-card incident-section">
            <div class="org-block-header">
                <h3>Wetter</h3>
                ${can.edit ? `<button class="bos-button bos-button-small" type="button" onclick="refreshIncidentWeather()">Neu erfassen</button>` : ""}
            </div>
            ${body}
        </section>`;
}

function renderIncidentMedia(detail) {
    const media = detail.media;
    const id = detail.incident.id;
    return `
        <section class="bos-card incident-section">
            <h3>Aufnahmen</h3>
            ${media.length ? `<ul class="incident-media">
                ${media.map(item => {
                    const url = `/api/incidents/${id}/media/${encodeURIComponent(item.name)}`;
                    return item.type === "snapshot"
                        ? `<li><a href="${url}" target="_blank" rel="noopener">
                            <img src="${url}" alt="Snapshot ${escapeHTML(incidentTime(item.taken_at, false))}" loading="lazy">
                            <span>${escapeHTML(incidentTime(item.taken_at, false))}</span></a></li>`
                        : `<li class="is-video"><a href="${url}?download=1">
                            <span class="incident-media-icon">▶</span>
                            <span>Video ${escapeHTML(incidentTime(item.taken_at, false))}</span></a></li>`;
                }).join("")}
            </ul>` : '<p class="incident-empty">Keine Aufnahmen der Einsatzdrohnen im Einsatzzeitraum.</p>'}
        </section>`;
}

function renderIncidentGuestLinks(detail) {
    if (!detail.can.edit) {
        return "";
    }
    const links = detail.guest_links || [];
    const running = detail.incident.status === "running";
    const last = incidentState.lastLink;
    return `
        <section class="bos-card incident-section">
            <h3>Einsatz-Gastlinks</h3>
            <p class="incident-hint">Für externe Stellen (z. B. Leitstelle, Polizei): zeigt alle Drohnen des
                Einsatzes live und endet spätestens mit dem Einsatz.</p>
            ${last ? `<div class="incident-link-result">
                <input class="bos-input" readonly value="${escapeHTML(last)}" onclick="this.select()">
                <button class="bos-button bos-button-small" type="button" onclick="copyIncidentLink()">Kopieren</button>
            </div>` : ""}
            ${links.length ? `<ul class="org-memberships">
                ${links.map(link => `
                    <li class="${link.active ? "" : "is-muted"}">
                        <span>${escapeHTML(link.label)}
                            <small class="is-muted">${link.active
                                ? `bis ${escapeHTML(incidentTime(new Date(link.expires_at * 1000).toISOString()))}`
                                : "gesperrt/abgelaufen"}</small></span>
                        ${link.active ? `<button class="bos-button bos-button-small" type="button"
                            onclick="revokeIncidentLink('${escapeHTML(link.id)}')">Sperren</button>` : ""}
                    </li>`).join("")}
            </ul>` : ""}
            ${running ? `
                <form class="org-inline-add" onsubmit="createIncidentLink(event)">
                    <input class="bos-input" name="label" maxlength="80" required placeholder="Für wen? z. B. Leitstelle">
                    <select class="bos-input" name="hours" aria-label="Gültigkeit">
                        <option value="4">4 Stunden</option>
                        <option value="12" selected>12 Stunden</option>
                        <option value="24">24 Stunden</option>
                        <option value="48">48 Stunden</option>
                    </select>
                    <button class="bos-button bos-button-small" type="submit">Link erstellen</button>
                </form>` : ""}
        </section>`;
}

function renderIncidentSummary(detail) {
    const incident = detail.incident;
    if (!detail.can.edit && !incident.summary) {
        return "";
    }
    return `
        <section class="bos-card incident-section incident-section-wide">
            <h3>Lage- und Abschlussbericht</h3>
            ${detail.can.edit ? `
                <form onsubmit="saveIncidentSummary(event)" class="incident-summary-form">
                    <textarea class="bos-input" name="summary" rows="4" maxlength="8000"
                        placeholder="Verlauf, Ergebnis, Besonderheiten – erscheint im Bericht">${escapeHTML(incident.summary)}</textarea>
                    <div class="org-form-actions">
                        <button class="bos-button bos-button-small" type="submit">Bericht speichern</button>
                    </div>
                </form>` : `<p class="incident-alarm-text">${escapeHTML(incident.summary)}</p>`}
        </section>`;
}

function renderIncidentLog(detail) {
    const entries = [...detail.log].reverse();
    return `
        <section class="bos-card incident-section incident-section-wide">
            <h3>Verlauf</h3>
            ${detail.can.edit ? `
                <form class="org-inline-add" onsubmit="addIncidentNote(event)">
                    <input class="bos-input" name="text" maxlength="2000" required placeholder="Notiz, Lagemeldung, Funkspruch …">
                    <button class="bos-button bos-button-small" type="submit">Eintragen</button>
                </form>` : ""}
            <ol class="incident-log">
                ${entries.map(entry => `
                    <li class="is-${escapeHTML(entry.kind)}">
                        <time datetime="${escapeHTML(entry.at)}">${escapeHTML(incidentTime(entry.at, false))}</time>
                        <span>${escapeHTML(entry.text)}</span>
                        <small>${escapeHTML(entry.actor)}</small>
                    </li>`).join("")}
            </ol>
        </section>`;
}

function renderIncidentDetail() {
    const detail = incidentState.detail;
    if (!detail) {
        return '<p class="service-inline-status">Wird geladen …</p>';
    }
    return `
        ${renderIncidentHeader(detail)}
        <div class="incident-grid">
            ${renderIncidentAlarm(detail)}
            ${renderIncidentMapSection(detail)}
            ${renderIncidentChecklists(detail)}
            ${renderIncidentSources(detail)}
            ${renderIncidentOrganizations(detail)}
            ${renderIncidentWeather(detail)}
            ${renderIncidentPeople(detail)}
            ${renderIncidentMedia(detail)}
            ${renderIncidentGuestLinks(detail)}
            ${renderIncidentSummary(detail)}
            ${renderIncidentLog(detail)}
        </div>`;
}

function renderIncidents() {
    const root = document.getElementById("incidents-root");
    if (!root) {
        return;
    }
    root.innerHTML = incidentState.openId ? renderIncidentDetail() : renderIncidentList();
    updateIncidentBadge();
}

function updateIncidentBadge() {
    const running = incidentState.list.filter(item => item.status === "running").length;
    document.querySelectorAll("[data-incident-badge]").forEach(badge => {
        badge.textContent = running ? String(running) : "";
        badge.hidden = !running;
    });
}

// ----------------------------------------------------------
// Aktionen
// ----------------------------------------------------------

async function incidentAction(request, successMessage = "") {
    try {
        const detail = await request();
        if (detail?.incident) {
            incidentState.detail = detail;
        }
        setIncidentMessage(successMessage);
    } catch (error) {
        setIncidentMessage(error.message, true);
    }
    renderIncidents();
}

function incidentUrl(path = "") {
    return `/api/incidents/${incidentState.openId}${path}`;
}

function editIncidentAlarm(open) {
    incidentState.editingAlarm = open;
    setIncidentMessage("");
    renderIncidents();
}

async function saveIncidentAlarm(event) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.target));
    if (data.lead_organization_id) {
        data.lead_organization_id = Number(data.lead_organization_id);
    } else {
        // Gesperrtes Feld (keine Admin-Rechte): Führung unverändert lassen.
        delete data.lead_organization_id;
    }
    data.exercise = data.exercise === "on";
    incidentState.editingAlarm = false;
    await incidentAction(() => api.patch(incidentUrl(), data), "Alarmierung gespeichert.");
}

async function saveIncidentSummary(event) {
    event.preventDefault();
    const summary = new FormData(event.target).get("summary");
    await incidentAction(() => api.patch(incidentUrl(), {summary}), "Bericht gespeichert.");
}

async function setIncidentStatus(status) {
    const texts = {
        ended: "Einsatz beenden? Drohnen werden aus dem Einsatz genommen und Einsatz-Gastlinks gesperrt.",
        closed: "Einsatz abschließen? Danach können nur noch Admins der führenden Wehr Änderungen vornehmen.",
    };
    const openRequired = status === "ended" || status === "closed" ? incidentOpenRequired() : [];
    if (openRequired.length && !window.confirm(
        "Offene Pflichtpositionen in Checklisten:\n– " + openRequired.join("\n– ") +
        "\n\nTrotzdem fortfahren?"
    )) {
        return;
    }
    if (texts[status] && !window.confirm(texts[status])) {
        return;
    }
    await incidentAction(() => api.post(incidentUrl("/status"), {status}));
    loadIncidents({quiet: true});
}

async function deleteIncident() {
    const incident = incidentState.detail?.incident;
    if (!incident || !window.confirm(
        `Einsatz ${incident.code} endgültig löschen? Personen, Verlauf und Zuordnungen gehen verloren. ` +
        "Aufnahmen bleiben erhalten."
    )) {
        return;
    }
    try {
        await api.delete(incidentUrl());
        setIncidentMessage(`Einsatz ${incident.code} gelöscht.`);
        incidentState.openId = null;
        incidentState.detail = null;
        history.replaceState(null, "", window.location.pathname);
        await loadIncidents();
    } catch (error) {
        setIncidentMessage(error.message, true);
        renderIncidents();
    }
}

async function addIncidentSource() {
    const sourceId = document.getElementById("incident-add-source")?.value;
    if (sourceId) {
        await incidentAction(() => api.post(incidentUrl("/sources"), {source_id: sourceId}));
    }
}

async function removeIncidentSource(sourceId) {
    await incidentAction(() => api.delete(incidentUrl(`/sources/${encodeURIComponent(sourceId)}`)));
}

async function addIncidentOrganization() {
    const organizationId = Number(document.getElementById("incident-add-org")?.value);
    if (organizationId) {
        await incidentAction(() => api.post(incidentUrl("/organizations"), {organization_id: organizationId}));
    }
}

async function removeIncidentOrganization(organizationId) {
    await incidentAction(() => api.delete(incidentUrl(`/organizations/${organizationId}`)));
}

async function addIncidentParticipant(event) {
    event.preventDefault();
    const data = new FormData(event.target);
    const userId = data.get("user_id");
    const payload = {
        role: data.get("role"),
        user_id: userId ? Number(userId) : null,
        name: userId ? "" : data.get("name"),
    };
    await incidentAction(() => api.post(incidentUrl("/participants"), payload));
}

async function endIncidentParticipant(participantId) {
    await incidentAction(() => api.patch(
        incidentUrl(`/participants/${participantId}`),
        {until_at: incidentInputTime(null)}
    ));
}

async function removeIncidentParticipant(participantId) {
    if (window.confirm("Eintrag löschen? Zum Dokumentieren des Endes besser „Austragen“ verwenden.")) {
        await incidentAction(() => api.delete(incidentUrl(`/participants/${participantId}`)));
    }
}

async function addIncidentNote(event) {
    event.preventDefault();
    const text = new FormData(event.target).get("text");
    await incidentAction(() => api.post(incidentUrl("/notes"), {text}));
}

async function refreshIncidentWeather() {
    await incidentAction(() => api.post(incidentUrl("/weather")), "Wetter erfasst.");
}

async function createIncidentLink(event) {
    event.preventDefault();
    const data = new FormData(event.target);
    try {
        const result = await api.post(incidentUrl("/guest-links"), {
            label: data.get("label"),
            hours: Number(data.get("hours")),
        });
        incidentState.lastLink = result.url;
        setIncidentMessage("Gastlink erstellt. Er wird nur jetzt angezeigt – bitte kopieren und weitergeben.");
        incidentState.detail = await api.get(incidentUrl());
    } catch (error) {
        setIncidentMessage(error.message, true);
    }
    renderIncidents();
}

async function copyIncidentLink() {
    try {
        await navigator.clipboard.writeText(incidentState.lastLink);
        setIncidentMessage("Link kopiert.");
    } catch (error) {
        setIncidentMessage("Kopieren nicht möglich – bitte den Link markieren und kopieren.", true);
    }
    renderIncidents();
}

async function revokeIncidentLink(linkId) {
    if (!window.confirm("Gastlink sperren? Wer ihn geöffnet hat, sieht sofort keine Livebilder mehr.")) {
        return;
    }
    try {
        await api.delete(incidentUrl(`/guest-links/${encodeURIComponent(linkId)}`));
        incidentState.detail = await api.get(incidentUrl());
        setIncidentMessage("Gastlink gesperrt.");
    } catch (error) {
        setIncidentMessage(error.message, true);
    }
    renderIncidents();
}

// Direkter Aufruf über #incidents/<id> (z. B. aus einer Push-Nachricht).
function incidentFromHash() {
    const match = window.location.hash.match(/^#incidents(?:\/(\d+))?$/);
    if (!match) {
        return false;
    }
    if (match[1]) {
        incidentState.openId = Number(match[1]);
    }
    if (typeof showPage === "function") {
        showPage("incidents");
    }
    return true;
}

window.addEventListener("hashchange", incidentFromHash);

document.addEventListener("DOMContentLoaded", () => {
    // Laufende Einsätze für die Markierung im Menü, auch auf anderen Seiten.
    if (document.getElementById("page-incidents")) {
        loadIncidents({quiet: true});
    }
});
