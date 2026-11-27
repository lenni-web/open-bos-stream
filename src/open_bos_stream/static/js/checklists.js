// ==========================================================
// Checklisten-Modul: Listen, Vorlagen, Dokumente
// ==========================================================

const CHECKLIST_POLL_MS = 5000;

const checklistState = {
    tab: "lists",
    overview: null,
    openId: null,
    detail: null,
    editingTemplate: null,   // {id|null, title, description, items:[...]}
    viewTemplateDetail: null,
    creating: false,
    documents: null,
    message: "",
    error: false,
    timer: null,
    active: false,
};

function setChecklistMessage(message, error = false) {
    checklistState.message = message;
    checklistState.error = error;
}

function checklistMessageHTML() {
    return checklistState.message
        ? `<p class="incident-message ${checklistState.error ? "is-error" : ""}" role="status">${escapeHTML(checklistState.message)}</p>`
        : "";
}

function checklistTime(value) {
    if (!value) {
        return "";
    }
    const date = new Date(value);
    return Number.isNaN(date.getTime())
        ? value
        : date.toLocaleString("de-DE", {dateStyle: "short", timeStyle: "short"});
}

function checklistSize(bytes) {
    if (bytes > 1024 * 1024) {
        return `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} MB`;
    }
    return `${Math.max(1, Math.round(bytes / 1024))} kB`;
}

function checklistProgress(item) {
    const percent = item.total ? Math.round(item.done / item.total * 100) : 0;
    return `
        <span class="checklist-progress" title="${item.done} von ${item.total} erledigt">
            <span style="width:${percent}%"></span>
        </span>
        <small>${item.done}/${item.total}${item.open_required?.length
            ? ` · <span class="incident-warning">${item.open_required.length} Pflicht offen</span>` : ""}</small>`;
}

function checklistBusy() {
    const root = document.getElementById("checklists-root");
    const focused = document.activeElement;
    return Boolean(root && focused && root.contains(focused) &&
        ["INPUT", "TEXTAREA", "SELECT"].includes(focused.tagName)) ||
        Boolean(checklistState.editingTemplate) || checklistState.creating;
}

// ----------------------------------------------------------
// Laden und Seitenwechsel
// ----------------------------------------------------------

async function loadChecklistOverview({quiet = false} = {}) {
    try {
        checklistState.overview = await api.get("/api/checklists");
    } catch (error) {
        if (!quiet) {
            setChecklistMessage(error.message, true);
        }
    }
}

async function loadChecklistDetail(id, {quiet = false} = {}) {
    try {
        const data = await api.get(`/api/checklists/${id}`);
        checklistState.detail = data.checklist;
        checklistState.openId = id;
    } catch (error) {
        if (error.status === 404) {
            checklistState.openId = null;
            checklistState.detail = null;
        }
        if (!quiet) {
            setChecklistMessage(error.message, true);
        }
    }
}

async function loadDocuments({quiet = false} = {}) {
    try {
        checklistState.documents = await api.get("/api/documents");
    } catch (error) {
        if (!quiet) {
            setChecklistMessage(error.message, true);
        }
    }
}

async function refreshChecklists({quiet = false} = {}) {
    if (checklistState.tab === "documents") {
        await loadDocuments({quiet});
    } else if (checklistState.openId) {
        await loadChecklistDetail(checklistState.openId, {quiet});
    } else {
        await loadChecklistOverview({quiet});
    }
    renderChecklists();
}

function scheduleChecklistRefresh() {
    window.clearTimeout(checklistState.timer);
    if (!checklistState.active) {
        return;
    }
    checklistState.timer = window.setTimeout(async () => {
        if (document.visibilityState === "visible" && !checklistBusy() && checklistState.openId) {
            // Häkchen anderer Beteiligter sichtbar machen.
            await refreshChecklists({quiet: true});
        }
        scheduleChecklistRefresh();
    }, CHECKLIST_POLL_MS);
}

function setChecklistsPageActive(active) {
    checklistState.active = active;
    if (active) {
        refreshChecklists();
        scheduleChecklistRefresh();
    } else {
        window.clearTimeout(checklistState.timer);
    }
}

function showChecklistTab(tab) {
    checklistState.tab = tab;
    checklistState.openId = null;
    checklistState.detail = null;
    checklistState.editingTemplate = null;
    checklistState.viewTemplateDetail = null;
    checklistState.creating = false;
    setChecklistMessage("");
    document.querySelectorAll("[data-checklist-tab]").forEach(button => {
        button.setAttribute("aria-selected", String(button.dataset.checklistTab === tab));
    });
    refreshChecklists();
}

// Aus der Einsatzseite: Liste direkt öffnen.
function openChecklist(id) {
    checklistState.tab = "lists";
    document.querySelectorAll("[data-checklist-tab]").forEach(button => {
        button.setAttribute("aria-selected", String(button.dataset.checklistTab === "lists"));
    });
    checklistState.openId = Number(id);
    checklistState.detail = null;
    setChecklistMessage("");
    if (typeof showPage === "function" && !document.getElementById("page-checklists")?.classList.contains("active")) {
        showPage("checklists");
    } else {
        refreshChecklists();
    }
}

function closeChecklist() {
    checklistState.openId = null;
    checklistState.detail = null;
    setChecklistMessage("");
    refreshChecklists();
}

// ----------------------------------------------------------
// Darstellung: Listen
// ----------------------------------------------------------

function checklistCard(item) {
    const incident = item.incident;
    return `
        <li>
            <button class="incident-card checklist-card ${item.status === "completed" ? "is-done" : ""}"
                type="button" onclick="openChecklist(${Number(item.id)})">
                <span class="incident-card-head">
                    <span class="incident-status ${item.status === "completed" ? "is-closed" : ""}">${escapeHTML(item.status_label)}</span>
                    ${incident ? `<span class="incident-code">Einsatz ${escapeHTML(incident.code)}</span>` : ""}
                    ${incident?.exercise ? '<span class="incident-exercise">Übung</span>' : ""}
                </span>
                <strong>${escapeHTML(item.title)}</strong>
                <span class="incident-card-meta">${escapeHTML(item.organization_name)}${incident
                    ? ` · ${escapeHTML(incident.keyword || "Einsatz")}` : ""} · ${escapeHTML(checklistTime(item.created_at))}</span>
                <span class="checklist-card-progress">${checklistProgress(item)}</span>
            </button>
        </li>`;
}

function renderChecklistCreateForm() {
    const overview = checklistState.overview;
    if (!checklistState.creating || !overview) {
        return "";
    }
    const templates = overview.templates.filter(item => !item.archived);
    return `
        <form class="org-form incident-form" onsubmit="createChecklist(event)">
            <h3>Neue Checkliste</h3>
            <div class="form-grid">
                <label class="form-field">
                    <span>Wehr</span>
                    <select class="bos-input" name="organization_id" required>
                        ${overview.organizations.map(org => `<option value="${Number(org.id)}">${escapeHTML(org.name)}</option>`).join("")}
                    </select>
                </label>
                <label class="form-field">
                    <span>Grundlage</span>
                    <select class="bos-input" name="template_id">
                        ${templates.map(item => `<option value="${Number(item.id)}">Vorlage: ${escapeHTML(item.title)}</option>`).join("")}
                        <option value="">Eigene Liste (ohne Vorlage)</option>
                    </select>
                </label>
                <label class="form-field form-field-wide">
                    <span>Titel (leer = Titel der Vorlage)</span>
                    <input class="bos-input" name="title" maxlength="120" placeholder="z. B. Gerätecheck Drohne 1">
                </label>
            </div>
            <p class="incident-hint">Checklisten für einen Einsatz werden direkt auf der Einsatzseite hinzugefügt.</p>
            <div class="org-form-actions">
                <button class="bos-button bos-button-small bos-button-green" type="submit">Anlegen</button>
                <button class="bos-button bos-button-small" type="button" onclick="toggleChecklistCreate(false)">Abbrechen</button>
            </div>
        </form>`;
}

function renderChecklistList() {
    const overview = checklistState.overview;
    if (!overview) {
        return '<p class="service-inline-status">Wird geladen …</p>';
    }
    const open = overview.checklists.filter(item => !(item.status === "completed" || item.incident?.status === "closed"));
    const done = overview.checklists.filter(item => item.status === "completed" || item.incident?.status === "closed");
    return `
        ${checklistMessageHTML()}
        <section class="bos-card incident-section">
            <div class="org-block-header">
                <h2>Offene Checklisten</h2>
                ${overview.organizations.length && !checklistState.creating ? `
                    <button class="bos-button" type="button" onclick="toggleChecklistCreate(true)">＋ Neue Checkliste</button>` : ""}
            </div>
            ${renderChecklistCreateForm()}
            ${open.length ? `<ul class="incident-cards">${open.map(checklistCard).join("")}</ul>`
                : '<p class="incident-empty">Keine offene Checkliste.</p>'}
        </section>
        <section class="bos-card incident-section">
            <h2>Abgeschlossen</h2>
            ${done.length ? `<ul class="incident-cards is-compact">${done.map(checklistCard).join("")}</ul>`
                : '<p class="incident-empty">Noch keine abgeschlossenen Checklisten.</p>'}
        </section>`;
}

function groupChecklistItems(items) {
    const groups = [];
    items.forEach(item => {
        const last = groups[groups.length - 1];
        if (last && last.section === item.section) {
            last.items.push(item);
        } else {
            groups.push({section: item.section, items: [item]});
        }
    });
    return groups;
}

function renderChecklistItem(item, editable) {
    return `
        <li class="checklist-item ${item.checked ? "is-checked" : ""} ${item.required && !item.checked ? "is-required-open" : ""}">
            <label class="checklist-check">
                <input type="checkbox" ${item.checked ? "checked" : ""} ${editable ? "" : "disabled"}
                    onchange="toggleChecklistItem(${Number(item.id)}, this.checked)">
                <span>
                    <strong>${escapeHTML(item.text)}</strong>
                    ${item.required ? '<em class="checklist-required">Pflicht</em>' : ""}
                    ${item.hint ? `<small>${escapeHTML(item.hint)}</small>` : ""}
                    ${item.checked ? `<small class="checklist-meta">✓ ${escapeHTML(item.checked_by || "")} · ${escapeHTML(checklistTime(item.checked_at))}</small>` : ""}
                </span>
            </label>
            <div class="checklist-note">
                ${editable ? `
                    <input class="bos-input" maxlength="1000" placeholder="Anmerkung"
                        value="${escapeHTML(item.note)}" aria-label="Anmerkung zu ${escapeHTML(item.text)}"
                        onchange="saveChecklistNote(${Number(item.id)}, this.value)">`
                    : item.note ? `<p>${escapeHTML(item.note)}</p>` : ""}
                ${item.note && item.note_by ? `<small class="checklist-meta">${escapeHTML(item.note_by)} · ${escapeHTML(checklistTime(item.note_at))}</small>` : ""}
            </div>
            ${editable ? `<button class="checklist-remove" type="button" title="Position entfernen"
                onclick="removeChecklistItem(${Number(item.id)})">✕</button>` : ""}
        </li>`;
}

function renderChecklistDetail() {
    const list = checklistState.detail;
    if (!list) {
        return '<p class="service-inline-status">Wird geladen …</p>';
    }
    const can = list.can || {};
    const editable = Boolean(can.edit);
    const incident = list.incident;
    const locked = !editable && (list.status === "completed" || incident?.status === "closed");
    const actions = [];
    if (!list.incident_id && list.status === "open" && editable) {
        actions.push(`<button class="bos-button bos-button-small bos-button-green" type="button" onclick="setChecklistStatus('completed')">Abschließen</button>`);
    }
    if (!list.incident_id && list.status === "completed" && can.admin) {
        actions.push(`<button class="bos-button bos-button-small" type="button" onclick="setChecklistStatus('open')">Wieder öffnen</button>`);
    }
    if (incident) {
        actions.push(`<button class="bos-button bos-button-small" type="button" onclick="openIncident(${Number(incident.id)})">Zum Einsatz</button>`);
    }
    if (editable) {
        actions.push(`<button class="bos-button bos-button-small app-logout" type="button" onclick="deleteChecklist()">Löschen</button>`);
    }
    return `
        <div class="incident-topline">
            <button class="incident-back" type="button" onclick="closeChecklist()">← Alle Checklisten</button>
        </div>
        ${checklistMessageHTML()}
        <section class="bos-card incident-head">
            <div class="incident-head-main">
                <span class="incident-card-head">
                    <span class="incident-status ${list.status === "completed" ? "is-closed" : ""}">${escapeHTML(list.status_label)}</span>
                    ${incident ? `<span class="incident-code">Einsatz ${escapeHTML(incident.code)}</span>` : ""}
                    ${incident?.exercise ? '<span class="incident-exercise">Übung</span>' : ""}
                </span>
                <h2>${escapeHTML(list.title)}</h2>
                ${list.description ? `<p class="incident-card-meta">${escapeHTML(list.description)}</p>` : ""}
                <p class="incident-card-meta">${escapeHTML(list.organization_name)} · angelegt von ${escapeHTML(list.created_by)}
                    · ${escapeHTML(checklistTime(list.created_at))}${list.completed_at
                        ? ` · abgeschlossen von ${escapeHTML(list.completed_by)} · ${escapeHTML(checklistTime(list.completed_at))}` : ""}</p>
                <span class="checklist-card-progress">${checklistProgress(list)}</span>
            </div>
            <div class="org-row-actions incident-actions">${actions.join("")}</div>
        </section>
        ${locked ? `<p class="incident-hint checklist-locked">🔒 ${incident
            ? "Der Einsatz ist abgeschlossen. Änderungen nur durch Admins der führenden Wehr."
            : "Die Liste ist abgeschlossen. Änderungen nur durch Admins der Wehr."}</p>` : ""}
        <section class="bos-card incident-section">
            ${list.items.length ? groupChecklistItems(list.items).map(group => `
                ${group.section ? `<h3 class="checklist-section">${escapeHTML(group.section)}</h3>` : ""}
                <ul class="checklist-items">${group.items.map(item => renderChecklistItem(item, editable)).join("")}</ul>
            `).join("") : '<p class="incident-empty">Noch keine Positionen.</p>'}
            ${editable ? `
                <form class="org-inline-add checklist-add" onsubmit="addChecklistItem(event)">
                    <input class="bos-input" name="section" maxlength="80" placeholder="Abschnitt (optional)">
                    <input class="bos-input" name="text" maxlength="300" required placeholder="Neue Position">
                    <label class="checklist-required-toggle"><input type="checkbox" name="required"> Pflicht</label>
                    <button class="bos-button bos-button-small" type="submit">Hinzufügen</button>
                </form>` : ""}
        </section>`;
}

// ----------------------------------------------------------
// Darstellung: Vorlagen
// ----------------------------------------------------------

function templateItemRow(item, index) {
    return `
        <li class="template-item" data-index="${index}">
            <input class="bos-input" data-field="section" maxlength="80" placeholder="Abschnitt" value="${escapeHTML(item.section || "")}">
            <input class="bos-input" data-field="text" maxlength="300" placeholder="Position" value="${escapeHTML(item.text || "")}">
            <input class="bos-input" data-field="hint" maxlength="300" placeholder="Hinweis (optional)" value="${escapeHTML(item.hint || "")}">
            <label class="checklist-required-toggle"><input type="checkbox" data-field="required" ${item.required ? "checked" : ""}> Pflicht</label>
            <span class="template-item-actions">
                <button type="button" title="Nach oben" onclick="moveTemplateItem(${index}, -1)">↑</button>
                <button type="button" title="Nach unten" onclick="moveTemplateItem(${index}, 1)">↓</button>
                <button type="button" title="Entfernen" onclick="removeTemplateItem(${index})">✕</button>
            </span>
        </li>`;
}

function renderTemplateEditor() {
    const template = checklistState.editingTemplate;
    return `
        ${checklistMessageHTML()}
        <section class="bos-card incident-section">
            <form class="incident-form" onsubmit="saveTemplate(event)">
                <h2>${template.id ? "Vorlage bearbeiten" : "Neue Vorlage"}</h2>
                <label class="form-field">
                    <span>Titel</span>
                    <input class="bos-input" id="template-title" maxlength="120" required value="${escapeHTML(template.title)}"
                        placeholder="z. B. Vorflugkontrolle Drohne">
                </label>
                <label class="form-field">
                    <span>Beschreibung</span>
                    <textarea class="bos-input" id="template-description" rows="2" maxlength="2000">${escapeHTML(template.description)}</textarea>
                </label>
                <h3>Positionen</h3>
                <ol id="template-items" class="template-items">
                    ${template.items.map(templateItemRow).join("")}
                </ol>
                <div class="org-form-actions">
                    <button class="bos-button bos-button-small" type="button" onclick="addTemplateItem()">＋ Position</button>
                </div>
                <p class="incident-hint">Gleicher Abschnitt hintereinander = eine Gruppe. „Pflicht“-Positionen
                    werden beim Beenden eines Einsatzes angemahnt, wenn sie offen sind. Bereits angelegte
                    Checklisten behalten ihren Stand.</p>
                <div class="org-form-actions">
                    <button class="bos-button bos-button-small bos-button-green" type="submit">Speichern</button>
                    <button class="bos-button bos-button-small" type="button" onclick="cancelTemplateEdit()">Abbrechen</button>
                </div>
            </form>
        </section>`;
}

function renderTemplates() {
    const overview = checklistState.overview;
    if (!overview) {
        return '<p class="service-inline-status">Wird geladen …</p>';
    }
    if (checklistState.editingTemplate) {
        return renderTemplateEditor();
    }
    const manage = overview.can_manage_templates;
    const viewing = checklistState.viewTemplateDetail;
    return `
        ${checklistMessageHTML()}
        <section class="bos-card incident-section">
            <div class="org-block-header">
                <h2>Vorlagen des Landkreises</h2>
                ${manage ? '<button class="bos-button" type="button" onclick="startTemplateEdit(null)">＋ Neue Vorlage</button>' : ""}
            </div>
            <p class="incident-hint">${manage
                ? "Vorlagen stehen allen Wehren zur Verfügung – im Einsatz und für eigene Listen."
                : "Vorlagen pflegt der Landkreis. Eigene Listen legen Sie unter „Checklisten“ an."}</p>
            ${overview.templates.length ? `<ul class="org-memberships template-list">
                ${overview.templates.map(item => `
                    <li class="${item.archived ? "is-muted" : ""}">
                        <span>
                            <strong>${escapeHTML(item.title)}</strong>
                            <small class="is-muted">${item.item_count} Positionen${item.required_count ? `, ${item.required_count} Pflicht` : ""}
                                · Stand ${escapeHTML(checklistTime(item.updated_at))}${item.archived ? " · archiviert" : ""}</small>
                        </span>
                        <span class="org-row-actions">
                            <button class="bos-button bos-button-small" type="button" onclick="viewTemplate(${Number(item.id)})">Ansehen</button>
                            ${manage ? `
                                <button class="bos-button bos-button-small" type="button" onclick="startTemplateEdit(${Number(item.id)})">Bearbeiten</button>
                                <button class="bos-button bos-button-small" type="button" onclick="archiveTemplate(${Number(item.id)}, ${!item.archived})">
                                    ${item.archived ? "Reaktivieren" : "Archivieren"}</button>` : ""}
                        </span>
                    </li>
                    ${viewing && viewing.id === item.id ? `<li class="template-preview">
                        ${viewing.description ? `<p class="incident-hint">${escapeHTML(viewing.description)}</p>` : ""}
                        ${groupChecklistItems(viewing.items).map(group => `
                            ${group.section ? `<h3 class="checklist-section">${escapeHTML(group.section)}</h3>` : ""}
                            <ul class="template-preview-items">${group.items.map(entry => `
                                <li>☐ ${escapeHTML(entry.text)}${entry.required ? ' <em class="checklist-required">Pflicht</em>' : ""}
                                    ${entry.hint ? `<small>${escapeHTML(entry.hint)}</small>` : ""}</li>`).join("")}</ul>
                        `).join("")}
                    </li>` : ""}`).join("")}
            </ul>` : '<p class="incident-empty">Noch keine Vorlagen.</p>'}
        </section>`;
}

// ----------------------------------------------------------
// Darstellung: Dokumente
// ----------------------------------------------------------

function renderDocuments() {
    const data = checklistState.documents;
    if (!data) {
        return '<p class="service-inline-status">Wird geladen …</p>';
    }
    return `
        ${checklistMessageHTML()}
        <section class="bos-card incident-section">
            <h2>Dokumente des Landkreises</h2>
            <p class="incident-hint">Einheitliche Unterlagen für alle Wehren, z. B. Merkblätter, Formulare und Einsatzhilfen.</p>
            ${data.documents.length ? `<ul class="org-memberships document-list">
                ${data.documents.map(item => `
                    <li>
                        <span>
                            <strong>${escapeHTML(item.title)}</strong>
                            <small class="is-muted">${escapeHTML(item.original_name)} · ${escapeHTML(checklistSize(item.size))}
                                · ${escapeHTML(item.uploaded_by)}, ${escapeHTML(checklistTime(item.uploaded_at))}</small>
                            ${item.description ? `<small>${escapeHTML(item.description)}</small>` : ""}
                        </span>
                        <span class="org-row-actions">
                            <a class="bos-button bos-button-small" href="/api/documents/${Number(item.id)}/file" target="_blank" rel="noopener">Öffnen</a>
                            <a class="bos-button bos-button-small" href="/api/documents/${Number(item.id)}/file?download=1">Herunterladen</a>
                            ${data.can_manage ? `<button class="bos-button bos-button-small app-logout" type="button"
                                onclick="deleteDocument(${Number(item.id)})">Löschen</button>` : ""}
                        </span>
                    </li>`).join("")}
            </ul>` : '<p class="incident-empty">Noch keine Dokumente bereitgestellt.</p>'}
            ${data.can_manage ? `
                <form class="org-form incident-form" onsubmit="uploadDocument(event)">
                    <h3>Dokument bereitstellen</h3>
                    <div class="form-grid">
                        <label class="form-field form-field-wide">
                            <span>Datei (PDF, Office, OpenDocument, Text, Bild; max. 25 MB)</span>
                            <input class="bos-input" type="file" name="file" required
                                accept=".pdf,.docx,.xlsx,.pptx,.odt,.ods,.txt,.png,.jpg,.jpeg">
                        </label>
                        <label class="form-field">
                            <span>Titel</span>
                            <input class="bos-input" name="title" maxlength="120" placeholder="leer = Dateiname">
                        </label>
                        <label class="form-field">
                            <span>Beschreibung</span>
                            <input class="bos-input" name="description" maxlength="500">
                        </label>
                    </div>
                    <div class="org-form-actions">
                        <button class="bos-button bos-button-small bos-button-green" type="submit">Hochladen</button>
                    </div>
                </form>` : ""}
        </section>`;
}

function renderChecklists() {
    const root = document.getElementById("checklists-root");
    if (!root) {
        return;
    }
    if (checklistState.tab === "documents") {
        root.innerHTML = renderDocuments();
    } else if (checklistState.tab === "templates") {
        root.innerHTML = renderTemplates();
    } else {
        root.innerHTML = checklistState.openId ? renderChecklistDetail() : renderChecklistList();
    }
}

// ----------------------------------------------------------
// Aktionen: Listen
// ----------------------------------------------------------

function toggleChecklistCreate(open) {
    checklistState.creating = open;
    setChecklistMessage("");
    renderChecklists();
}

async function createChecklist(event) {
    event.preventDefault();
    const data = new FormData(event.target);
    try {
        const result = await api.post("/api/checklists", {
            organization_id: Number(data.get("organization_id")),
            template_id: data.get("template_id") ? Number(data.get("template_id")) : null,
            title: data.get("title"),
        });
        checklistState.creating = false;
        openChecklist(result.checklist.id);
    } catch (error) {
        setChecklistMessage(error.message, true);
        renderChecklists();
    }
}

async function checklistAction(request, message = "") {
    try {
        const result = await request();
        if (result?.checklist) {
            checklistState.detail = result.checklist;
        }
        setChecklistMessage(message);
    } catch (error) {
        setChecklistMessage(error.message, true);
        await loadChecklistDetail(checklistState.openId, {quiet: true});
    }
    renderChecklists();
}

function toggleChecklistItem(itemId, checked) {
    return checklistAction(() => api.put(`/api/checklists/${checklistState.openId}/items/${itemId}`, {checked}));
}

function saveChecklistNote(itemId, note) {
    return checklistAction(() => api.put(`/api/checklists/${checklistState.openId}/items/${itemId}`, {note}));
}

async function addChecklistItem(event) {
    event.preventDefault();
    const data = new FormData(event.target);
    await checklistAction(() => api.post(`/api/checklists/${checklistState.openId}/items`, {
        text: data.get("text"),
        section: data.get("section"),
        required: data.get("required") === "on",
    }));
    document.querySelector('.checklist-add input[name="text"]')?.focus();
}

async function removeChecklistItem(itemId) {
    if (window.confirm("Position aus dieser Liste entfernen?")) {
        await checklistAction(() => api.delete(`/api/checklists/${checklistState.openId}/items/${itemId}`));
    }
}

async function setChecklistStatus(status) {
    const list = checklistState.detail;
    if (status === "completed" && list?.open_required?.length && !window.confirm(
        `Noch offene Pflichtpositionen:\n– ${list.open_required.join("\n– ")}\n\nTrotzdem abschließen?`
    )) {
        return;
    }
    await checklistAction(() => api.post(`/api/checklists/${checklistState.openId}/status`, {status}),
        status === "completed" ? "Checkliste abgeschlossen." : "Checkliste wieder geöffnet.");
}

async function deleteChecklist() {
    const list = checklistState.detail;
    if (!list || !window.confirm(`Checkliste „${list.title}“ löschen?`)) {
        return;
    }
    try {
        await api.delete(`/api/checklists/${list.id}`);
        setChecklistMessage("Checkliste gelöscht.");
        checklistState.openId = null;
        checklistState.detail = null;
        await refreshChecklists();
    } catch (error) {
        setChecklistMessage(error.message, true);
        renderChecklists();
    }
}

// ----------------------------------------------------------
// Aktionen: Vorlagen
// ----------------------------------------------------------

function readTemplateItems() {
    return [...document.querySelectorAll("#template-items .template-item")].map(row => ({
        section: row.querySelector('[data-field="section"]').value,
        text: row.querySelector('[data-field="text"]').value,
        hint: row.querySelector('[data-field="hint"]').value,
        required: row.querySelector('[data-field="required"]').checked,
    }));
}

function syncTemplateEditor() {
    const template = checklistState.editingTemplate;
    if (!template || !document.getElementById("template-title")) {
        return;
    }
    template.title = document.getElementById("template-title").value;
    template.description = document.getElementById("template-description").value;
    template.items = readTemplateItems();
}

async function startTemplateEdit(id) {
    setChecklistMessage("");
    if (id) {
        try {
            const data = await api.get(`/api/checklists/templates/${id}`);
            checklistState.editingTemplate = {
                id,
                title: data.template.title,
                description: data.template.description,
                items: data.template.items,
            };
        } catch (error) {
            setChecklistMessage(error.message, true);
        }
    } else {
        checklistState.editingTemplate = {
            id: null,
            title: "",
            description: "",
            items: [{section: "Vor dem Start", text: "", hint: "", required: false}],
        };
    }
    renderChecklists();
}

function cancelTemplateEdit() {
    checklistState.editingTemplate = null;
    renderChecklists();
}

function addTemplateItem() {
    syncTemplateEditor();
    const items = checklistState.editingTemplate.items;
    items.push({section: items[items.length - 1]?.section || "", text: "", hint: "", required: false});
    renderChecklists();
    const rows = document.querySelectorAll('#template-items [data-field="text"]');
    rows[rows.length - 1]?.focus();
}

function removeTemplateItem(index) {
    syncTemplateEditor();
    checklistState.editingTemplate.items.splice(index, 1);
    renderChecklists();
}

function moveTemplateItem(index, direction) {
    syncTemplateEditor();
    const items = checklistState.editingTemplate.items;
    const target = index + direction;
    if (target < 0 || target >= items.length) {
        return;
    }
    [items[index], items[target]] = [items[target], items[index]];
    renderChecklists();
}

async function saveTemplate(event) {
    event.preventDefault();
    syncTemplateEditor();
    const template = checklistState.editingTemplate;
    const payload = {
        title: template.title,
        description: template.description,
        items: template.items.filter(item => item.text.trim()),
    };
    try {
        if (template.id) {
            await api.put(`/api/checklists/templates/${template.id}`, payload);
        } else {
            await api.post("/api/checklists/templates", payload);
        }
        checklistState.editingTemplate = null;
        setChecklistMessage("Vorlage gespeichert.");
        await loadChecklistOverview();
    } catch (error) {
        setChecklistMessage(error.message, true);
    }
    renderChecklists();
}

async function viewTemplate(id) {
    if (checklistState.viewTemplateDetail?.id === id) {
        checklistState.viewTemplateDetail = null;
        renderChecklists();
        return;
    }
    try {
        const data = await api.get(`/api/checklists/templates/${id}`);
        checklistState.viewTemplateDetail = data.template;
    } catch (error) {
        setChecklistMessage(error.message, true);
    }
    renderChecklists();
}

async function archiveTemplate(id, archived) {
    try {
        await api.put(`/api/checklists/templates/${id}`, {archived});
        setChecklistMessage(archived ? "Vorlage archiviert." : "Vorlage reaktiviert.");
        await loadChecklistOverview();
    } catch (error) {
        setChecklistMessage(error.message, true);
    }
    renderChecklists();
}

// ----------------------------------------------------------
// Aktionen: Dokumente
// ----------------------------------------------------------

async function uploadDocument(event) {
    event.preventDefault();
    const form = event.target;
    const file = form.file.files[0];
    if (!file) {
        return;
    }
    if (file.size > (checklistState.documents?.max_bytes ?? 25 * 1024 * 1024)) {
        setChecklistMessage("Die Datei ist zu groß (höchstens 25 MB).", true);
        renderChecklists();
        return;
    }
    const query = new URLSearchParams({
        filename: file.name,
        title: form.title.value,
        description: form.description.value,
    });
    form.querySelector('button[type="submit"]').disabled = true;
    try {
        const response = await fetch(`/api/documents?${query}`, {
            method: "POST",
            credentials: "same-origin",
            headers: {"Content-Type": "application/octet-stream"},
            body: file,
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            throw new Error(data.detail || `Hochladen fehlgeschlagen (HTTP ${response.status}).`);
        }
        setChecklistMessage(`„${data.document.title}“ bereitgestellt.`);
        await loadDocuments();
    } catch (error) {
        setChecklistMessage(error.message, true);
    }
    renderChecklists();
}

async function deleteDocument(id) {
    const item = checklistState.documents?.documents.find(entry => entry.id === id);
    if (!window.confirm(`Dokument „${item?.title ?? ""}“ löschen? Es steht dann keiner Wehr mehr zur Verfügung.`)) {
        return;
    }
    try {
        await api.delete(`/api/documents/${id}`);
        setChecklistMessage("Dokument gelöscht.");
        await loadDocuments();
    } catch (error) {
        setChecklistMessage(error.message, true);
    }
    renderChecklists();
}
