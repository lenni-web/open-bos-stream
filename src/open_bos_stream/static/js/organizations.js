// ==========================================================
// Organisation und Konten (Wehr-Admins, Kreis-Admins, Superadmins)
// ==========================================================

const orgState = {
    meta: null,
    organizations: [],
    users: [],
    filter: "",
    editingOrg: null,
    openUser: null,
};

function orgElement() {
    return document.getElementById("org-management");
}

// Benutzerkonten haben seit 0.25.4 eine eigene Seite („Benutzer“).
function userElement() {
    return document.getElementById("user-management");
}

function orgStatus(text, kind = "") {
    document.querySelectorAll("[data-org-status]").forEach(status => {
        status.textContent = text;
        status.dataset.kind = kind;
    });
}

function userNameFields(user = {}) {
    return `
        <label class="form-field">
            <span>Vorname</span>
            <input class="bos-input" data-field="first_name" name="first_name" maxlength="60"
                value="${escapeHTML(user.first_name || "")}" autocomplete="off" required>
        </label>
        <label class="form-field">
            <span>Nachname</span>
            <input class="bos-input" data-field="last_name" name="last_name" maxlength="60"
                value="${escapeHTML(user.last_name || "")}" autocomplete="off" required>
        </label>
        <label class="form-field">
            <span>Spitzname (optional)</span>
            <input class="bos-input" data-field="nickname" name="nickname" maxlength="40"
                value="${escapeHTML(user.nickname || "")}" autocomplete="off">
        </label>`;
}

function orgName(id) {
    const org = orgState.organizations.find(item => item.id === id);
    return org ? (org.short_name || org.name) : "?";
}

function compareOrganizations(a, b) {
    // Erst nach Art (Reihenfolge wie in den Stammdaten), dann nach Name.
    const kinds = Object.keys(orgState.meta?.organization_kinds ?? {});
    return kinds.indexOf(a.kind) - kinds.indexOf(b.kind) || a.name.localeCompare(b.name, "de");
}

function fitsUnder(kind, parent) {
    return (orgState.meta?.parent_kinds?.[kind] ?? []).includes(parent?.kind);
}

// Arten, die unter dieser Organisation angelegt werden können.
function childKinds(parent) {
    return Object.keys(orgState.meta?.organization_kinds ?? {}).filter(kind => fitsUnder(kind, parent));
}

function orgTree() {
    // Baum in Anzeigereihenfolge mit Tiefe.
    const children = new Map();
    for (const org of orgState.organizations) {
        const key = org.parent_id ?? 0;
        if (!children.has(key)) {
            children.set(key, []);
        }
        children.get(key).push(org);
    }
    const result = [];
    const walk = (parent, depth) => {
        for (const org of (children.get(parent) ?? []).sort(compareOrganizations)) {
            result.push({org, depth});
            walk(org.id, depth + 1);
        }
    };
    walk(0, 0);
    return result;
}

function adminOrganizations() {
    return orgTree().filter(({org}) => org.can_admin && !org.archived);
}

function orgOptions(items, selected = null) {
    return items.map(({org, depth}) => `
        <option value="${org.id}" ${org.id === selected ? "selected" : ""}>
            ${"  ".repeat(depth)}${escapeHTML(org.name)}
        </option>
    `).join("");
}

function roleOptions(selected = "viewer") {
    return Object.entries(orgState.meta?.roles ?? {}).map(([value, label]) => `
        <option value="${value}" ${value === selected ? "selected" : ""}>${escapeHTML(label)}</option>
    `).join("");
}

function kindOptions(selected = "ortsfeuerwehr", allowed = null) {
    return Object.entries(orgState.meta?.organization_kinds ?? {})
        .filter(([value]) => !allowed || allowed.includes(value))
        .map(([value, label]) => `
        <option value="${value}" ${value === selected ? "selected" : ""}>${escapeHTML(label)}</option>
    `).join("");
}

function qualificationOptions() {
    return Object.entries(orgState.meta?.qualification_kinds ?? {}).map(([value, label]) => `
        <option value="${value}">${escapeHTML(label)}</option>
    `).join("");
}

function formatDate(value) {
    if (!value) {
        return "unbefristet";
    }
    const [year, month, day] = value.split("-");
    return `${day}.${month}.${year}`;
}

// ----------------------------------------------------------
// Darstellung
// ----------------------------------------------------------

function renderOrganizationRow(org) {
    const parent = orgState.organizations.find(item => item.id === org.parent_id);
    // Ältere Einordnungen, die nicht zur Art passen, sichtbar machen.
    const misplaced = parent && !fitsUnder(org.kind, parent);
    return `
        <div class="org-row${org.archived ? " is-archived" : ""}">
            <div class="org-row-main">
                <strong>${escapeHTML(org.name)}</strong>
                <small>${escapeHTML(org.kind_label)}${org.short_name ? ` · ${escapeHTML(org.short_name)}` : ""}
                    · ${org.member_count} Konten · ${org.source_count} Quellen
                    ${org.archived ? " · archiviert" : ""}
                    ${misplaced ? " · Einordnung prüfen" : ""}</small>
            </div>
            <div class="org-row-actions">
                ${org.can_manage_children && !org.archived && childKinds(org).length ? `
                    <button class="bos-button bos-button-small" type="button"
                        onclick="startOrganizationForm(null, ${org.id})">＋ Untereinheit</button>` : ""}
                ${org.can_admin || org.can_edit ? `
                    <button class="bos-button bos-button-small" type="button"
                        onclick="startOrganizationForm(${org.id})">Bearbeiten</button>` : ""}
            </div>
        </div>
        <div data-org-slot="${org.id}"></div>
    `;
}

function renderOrganizationBranch(parentId) {
    return orgState.organizations
        .filter(org => (org.parent_id ?? null) === parentId)
        .sort(compareOrganizations)
        .map(org => {
            const children = renderOrganizationBranch(org.id);
            return `<li>${renderOrganizationRow(org)}${
                children ? `<ul class="org-tree">${children}</ul>` : ""}</li>`;
        })
        .join("");
}

function renderOrganizations() {
    return `
        <div class="org-block">
            <h3>Organisationen</h3>
            <ul class="org-tree">${renderOrganizationBranch(null)}</ul>
        </div>
    `;
}

// Mögliche übergeordnete Organisationen für die gewählte Art.
function parentCandidates(org, kind) {
    const own = new Set([org.id]);
    for (const {org: item} of orgTree()) {
        if (own.has(item.parent_id)) {
            own.add(item.id);
        }
    }
    return orgTree().filter(({org: item}) => !own.has(item.id) && (
        item.id === org.parent_id
        || (item.can_admin && !item.archived && fitsUnder(kind, item))
    ));
}

function updateParentOptions(select) {
    const form = select.form;
    const org = orgState.organizations.find(item => item.id === orgState.editingOrg?.id);
    if (!org || !form.elements.parent_id) {
        return;
    }
    const selected = Number(form.elements.parent_id.value);
    form.elements.parent_id.innerHTML = orgOptions(parentCandidates(org, select.value), selected);
}

function renderOrganizationForm() {
    // Das Formular steht direkt unter der betroffenen Zeile.
    document.querySelectorAll("[data-org-slot]").forEach(item => {
        item.innerHTML = "";
    });
    const editing = orgState.editingOrg;
    if (!editing) {
        return;
    }
    const slot = document.querySelector(`[data-org-slot="${editing.id ?? editing.parentId}"]`);
    if (!slot) {
        return;
    }
    const org = editing.id
        ? orgState.organizations.find(item => item.id === editing.id)
        : null;
    const parentId = org ? org.parent_id : editing.parentId;
    const structural = org ? org.can_edit : true;
    const parent = orgState.organizations.find(item => item.id === parentId);
    const movable = Boolean(org && org.can_edit && org.parent_id !== null);
    // Neue Untereinheiten und verschiebbare Einheiten bekommen nur passende Arten.
    let kinds = null;
    if (!org) {
        kinds = childKinds(parent);
    } else if (org.parent_id !== null) {
        kinds = Object.keys(orgState.meta?.parent_kinds ?? {})
            .filter(kind => kind === org.kind || orgState.meta.parent_kinds[kind].length);
    }
    const kind = org?.kind
        ?? (kinds.includes("ortsfeuerwehr") ? "ortsfeuerwehr" : kinds[0]);
    slot.innerHTML = `
        <form class="org-form" onsubmit="saveOrganization(event)">
            <h4>${org ? `„${escapeHTML(org.name)}“ bearbeiten` : `Neue Untereinheit von ${escapeHTML(orgName(parentId))}`}</h4>
            <div class="form-grid">
                <label class="form-field form-field-wide">
                    <span>Name</span>
                    <input class="bos-input" name="name" required minlength="2" maxlength="120"
                        value="${escapeHTML(org?.name ?? "")}" placeholder="z. B. Ortsfeuerwehr Hagen">
                </label>
                <label class="form-field">
                    <span>Kurzname</span>
                    <input class="bos-input" name="short_name" maxlength="40"
                        value="${escapeHTML(org?.short_name ?? "")}" placeholder="z. B. OF Hagen">
                </label>
                <label class="form-field">
                    <span>Art</span>
                    <select class="bos-input" name="kind" ${structural ? "" : "disabled"}
                        onchange="updateParentOptions(this)">
                        ${kindOptions(kind, kinds)}
                    </select>
                </label>
                ${movable ? `
                <label class="form-field form-field-wide">
                    <span>Übergeordnete Organisation</span>
                    <select class="bos-input" name="parent_id">
                        ${orgOptions(parentCandidates(org, kind), org.parent_id)}
                    </select>
                    <small>Verschiebt auch alle Untereinheiten. Rollen der übergeordneten
                        Ebene gelten für alles darunter.</small>
                </label>` : ""}
                <label class="form-field">
                    <span>Breite (Wache)</span>
                    <input class="bos-input" name="latitude" inputmode="decimal"
                        value="${org?.latitude ?? ""}" placeholder="53.56">
                </label>
                <label class="form-field">
                    <span>Länge (Wache)</span>
                    <input class="bos-input" name="longitude" inputmode="decimal"
                        value="${org?.longitude ?? ""}" placeholder="9.53">
                </label>
            </div>
            <div class="org-form-actions">
                <button class="bos-button bos-button-small bos-button-green" type="submit">Speichern</button>
                <button class="bos-button bos-button-small" type="button" onclick="cancelOrganizationForm()">Abbrechen</button>
                ${org && org.can_edit && org.parent_id !== null ? `
                    <button class="bos-button bos-button-small" type="button"
                        onclick="toggleOrganizationArchive(${org.id}, ${!org.archived})">
                        ${org.archived ? "Wieder aktivieren" : "Archivieren"}</button>
                    ${org.member_count === 0 && org.source_count === 0 ? `
                        <button class="bos-button bos-button-small app-logout" type="button"
                            onclick="deleteOrganization(${org.id})">Löschen</button>` : ""}` : ""}
            </div>
        </form>
    `;
    slot.querySelector('input[name="name"]').focus();
}

function membershipChips(user) {
    return user.memberships.map(item => `
        <span class="org-chip">${escapeHTML(orgState.meta?.roles?.[item.role] ?? item.role)}
            · ${escapeHTML(orgName(item.organization_id))}</span>
    `).join("") || '<span class="org-chip is-muted">ohne Organisation</span>';
}

function qualificationChips(user) {
    return user.qualifications.map(item => `
        <span class="org-chip ${item.valid ? "is-valid" : "is-expired"}"
            title="${escapeHTML(item.label)}${item.reference ? ` · ${escapeHTML(item.reference)}` : ""}">
            ${escapeHTML(item.kind.toUpperCase().replace("A1A3", "A1/A3"))}
            ${item.valid_until ? `bis ${formatDate(item.valid_until)}` : ""}
            ${item.valid ? "" : "(abgelaufen)"}
        </span>
    `).join("");
}

function renderUserEditor(user) {
    const platform = Boolean(window.currentPermissions?.superadmin);
    const ownId = window.currentUser?.user_id;
    const admins = adminOrganizations();
    return `
        <div class="org-user-editor" data-user-id="${user.id}">
            ${user.manageable ? `
            <div class="form-grid">
                ${userNameFields(user)}
                <label class="form-field">
                    <span>E-Mail (optional)</span>
                    <input class="bos-input" data-field="email" type="email" maxlength="254"
                        value="${escapeHTML(user.email)}">
                </label>
                <label class="form-field">
                    <span>Neues Passwort</span>
                    <input class="bos-input" data-field="password" type="password"
                        minlength="10" autocomplete="new-password" placeholder="leer lassen = unverändert">
                </label>
                <label class="switch-row">
                    <input type="checkbox" data-field="active" ${user.active ? "checked" : ""}
                        ${user.id === ownId ? "disabled" : ""}>
                    <span><strong>Konto aktiv</strong><small>Gesperrte Konten können sich nicht anmelden.</small></span>
                </label>
                ${platform ? `
                <label class="switch-row">
                    <input type="checkbox" data-field="platform_admin" ${user.platform_admin ? "checked" : ""}>
                    <span><strong>Superadmin</strong><small>Technische Verwaltung des ganzen Servers.</small></span>
                </label>` : ""}
            </div>
            <div class="org-form-actions">
                <button class="bos-button bos-button-small bos-button-green" type="button"
                    onclick="saveUser(${user.id})">Konto speichern</button>
                ${user.id === ownId ? "" : `
                <button class="bos-button bos-button-small app-logout" type="button"
                    onclick="deleteUser(${user.id}, '${escapeHTML(user.username)}')">Konto löschen</button>`}
            </div>` : `
            <p class="service-inline-status">Dieses Konto gehört auch zu Organisationen außerhalb
                Ihres Bereichs. Kontodaten ändert die zuständige Ebene; Rollen in Ihrem Bereich
                können Sie hier vergeben.</p>`}

            <h4>Rollen</h4>
            <ul class="org-memberships">
                ${user.memberships.map(item => `
                    <li>
                        <span>${escapeHTML(orgName(item.organization_id))}</span>
                        ${item.editable ? `
                            <select class="bos-input" onchange="setMembership(${user.id}, ${item.organization_id}, this.value)">
                                ${roleOptions(item.role)}
                            </select>
                            <button class="bos-button bos-button-small" type="button"
                                onclick="removeMembership(${user.id}, ${item.organization_id})">Entfernen</button>
                        ` : `<span>${escapeHTML(orgState.meta?.roles?.[item.role] ?? item.role)}</span>`}
                    </li>
                `).join("")}
            </ul>
            ${admins.length ? `
            <div class="org-inline-add">
                <select class="bos-input" data-role="new-membership-org">${orgOptions(admins)}</select>
                <select class="bos-input" data-role="new-membership-role">${roleOptions("viewer")}</select>
                <button class="bos-button bos-button-small" type="button"
                    onclick="addMembership(${user.id}, this)">Rolle hinzufügen</button>
            </div>` : ""}

            <h4>Fernpilotennachweise</h4>
            <ul class="org-memberships">
                ${user.qualifications.map(item => `
                    <li>
                        <span>${escapeHTML(item.label)}${item.reference ? ` · ${escapeHTML(item.reference)}` : ""}</span>
                        <span class="org-chip ${item.valid ? "is-valid" : "is-expired"}">
                            ${item.valid_until ? `gültig bis ${formatDate(item.valid_until)}` : "unbefristet"}
                            ${item.valid ? "" : "· abgelaufen"}</span>
                        <button class="bos-button bos-button-small" type="button"
                            onclick="deleteQualification(${item.id})">Entfernen</button>
                    </li>
                `).join("") || '<li class="is-muted">Noch kein Nachweis erfasst.</li>'}
            </ul>
            <div class="org-inline-add">
                <select class="bos-input" data-role="new-qualification-kind">${qualificationOptions()}</select>
                <input class="bos-input" data-role="new-qualification-reference" maxlength="80" placeholder="Nummer (optional)">
                <input class="bos-input" data-role="new-qualification-until" type="date" title="Gültig bis">
                <button class="bos-button bos-button-small" type="button"
                    onclick="addQualification(${user.id}, this)">Nachweis hinzufügen</button>
            </div>
        </div>
    `;
}

function renderUsers() {
    const filter = Number(orgState.filter) || null;
    const inFilter = user => !filter || user.memberships.some(item => item.organization_id === filter);
    const users = orgState.users.filter(inFilter);
    const filterOptions = orgTree().filter(({org}) => org.can_admin);
    return `
        <div class="org-block">
            <div class="org-block-header">
                <h3>Konten</h3>
                <label class="org-filter">
                    <span>Organisation</span>
                    <select class="bos-input" onchange="orgState.filter = this.value; renderOrganizationManagement()">
                        <option value="">Alle in meinem Bereich</option>
                        ${orgOptions(filterOptions, filter)}
                    </select>
                </label>
            </div>
            <ul class="org-users">
                ${users.map(user => `
                    <li class="org-user${user.active ? "" : " is-inactive"}">
                        <details ${orgState.openUser === user.id ? "open" : ""}
                            ontoggle="if (this.open) orgState.openUser = ${user.id}">
                            <summary>
                                <span class="org-user-name">
                                    <strong>${escapeHTML(user.display_name || user.username)}${user.nickname
                                        ? ` <span class="is-muted">„${escapeHTML(user.nickname)}“</span>` : ""}</strong>
                                    <small>${escapeHTML(user.username)}${user.platform_admin ? " · Superadmin" : ""}${user.active ? "" : " · gesperrt"}${user.first_name ? "" : " · Name fehlt"}</small>
                                </span>
                                <span class="org-user-chips">${membershipChips(user)}${qualificationChips(user)}</span>
                            </summary>
                            ${renderUserEditor(user)}
                        </details>
                    </li>
                `).join("") || '<li class="is-muted">Keine Konten in diesem Bereich.</li>'}
            </ul>
        </div>
    `;
}

function renderNewUserForm() {
    const admins = adminOrganizations();
    if (!admins.length) {
        return "";
    }
    return `
        <form class="org-block org-form" onsubmit="createOrgUser(event)">
            <h3>Neues Konto</h3>
            <div class="form-grid">
                <label class="form-field">
                    <span>Benutzername</span>
                    <input class="bos-input" name="username" required minlength="3" maxlength="32"
                        autocomplete="off" placeholder="z. B. m-mustermann">
                </label>
                ${userNameFields()}
                <label class="form-field">
                    <span>E-Mail (optional)</span>
                    <input class="bos-input" name="email" type="email" maxlength="254">
                </label>
                <label class="form-field">
                    <span>Startpasswort</span>
                    <input class="bos-input" name="password" type="password" required minlength="10"
                        autocomplete="new-password">
                </label>
                <label class="form-field">
                    <span>Organisation</span>
                    <select class="bos-input" name="organization_id">${orgOptions(admins)}</select>
                </label>
                <label class="form-field">
                    <span>Rolle</span>
                    <select class="bos-input" name="role">${roleOptions("viewer")}</select>
                </label>
            </div>
            <div class="org-form-actions">
                <button class="bos-button bos-button-green" type="submit">Konto anlegen</button>
            </div>
            <p class="service-inline-status">
                Zuschauer sehen Livebilder, Karte und Wetter ihrer Organisation. Drohnenteams
                erstellen zusätzlich Gastlinks. Wehr-Admins verwalten Quellen und Konten.
                Der Ortsbrandmeister (nur in Ortsfeuerwehren) hat dieselben Rechte.
                Rollen gelten auch für alle Untereinheiten.
            </p>
        </form>
    `;
}

function renderOrganizationManagement() {
    const organizations = orgElement();
    if (organizations) {
        organizations.innerHTML = `
            <p class="service-inline-status" role="status" data-org-status></p>
            ${renderOrganizations()}
        `;
        renderOrganizationForm();
    }
    const users = userElement();
    if (users) {
        users.innerHTML = `
            <p class="service-inline-status" role="status" data-org-status></p>
            ${renderUsers()}
            ${renderNewUserForm()}
        `;
    }
}

// ----------------------------------------------------------
// Laden und Aktionen
// ----------------------------------------------------------

async function loadOrganizationManagement() {
    if (!orgElement() && !userElement()) {
        return;
    }
    try {
        const [meta, organizations, users] = await Promise.all([
            orgState.meta ? Promise.resolve(orgState.meta) : api.get("/api/org/meta"),
            api.get("/api/org/organizations"),
            api.get("/api/org/users"),
        ]);
        orgState.meta = meta;
        orgState.organizations = organizations.organizations;
        orgState.users = users.users;
        window.organizationNames = Object.fromEntries(
            orgState.organizations.map(item => [item.id, item.short_name || item.name])
        );
        renderOrganizationManagement();
        if (typeof renderSources === "function") {
            renderSources();
        }
    } catch (error) {
        for (const element of [orgElement(), userElement()]) {
            if (element) {
                element.innerHTML =
                    `<p class="service-inline-status">Organisation konnte nicht geladen werden: ${escapeHTML(error.message)}</p>`;
            }
        }
    }
}

async function orgAction(action, successText) {
    try {
        await action();
        await loadOrganizationManagement();
        if (successText) {
            orgStatus(successText, "success");
        }
    } catch (error) {
        orgStatus(String(error.message || error).replace(/^Value error,\s*/i, ""), "error");
    }
}

function numberOrNull(value) {
    const text = String(value ?? "").trim().replace(",", ".");
    return text === "" ? null : Number(text);
}

function startOrganizationForm(id = null, parentId = null) {
    orgState.editingOrg = {id, parentId};
    renderOrganizationForm();
}

function cancelOrganizationForm() {
    orgState.editingOrg = null;
    renderOrganizationForm();
}

function saveOrganization(event) {
    event.preventDefault();
    const form = event.target;
    const editing = orgState.editingOrg;
    const data = Object.fromEntries(new FormData(form).entries());
    const payload = {
        name: data.name,
        short_name: data.short_name ?? "",
        latitude: numberOrNull(data.latitude),
        longitude: numberOrNull(data.longitude),
    };
    const org = editing?.id
        ? orgState.organizations.find(item => item.id === editing.id)
        : null;
    if (!org || org.can_edit) {
        payload.kind = form.elements.kind.value;
    }
    const parentId = Number(form.elements.parent_id?.value) || null;
    const moved = Boolean(org && parentId && parentId !== org.parent_id);
    if (moved) {
        const question = `„${org.name}“ unter „${orgName(parentId)}“ verschieben? `
            + "Damit ändert sich, wer Zugriff hat.";
        if (!window.confirm(question)) {
            return;
        }
        payload.parent_id = parentId;
    }
    orgAction(async () => {
        if (org) {
            await api.patch(`/api/org/organizations/${org.id}`, payload);
        } else {
            await api.post("/api/org/organizations", {...payload, parent_id: editing.parentId});
        }
        orgState.editingOrg = null;
    }, moved ? "Organisation verschoben." : org ? "Organisation gespeichert." : "Organisation angelegt.");
}

function toggleOrganizationArchive(id, archived) {
    orgAction(async () => {
        await api.patch(`/api/org/organizations/${id}`, {archived});
        orgState.editingOrg = null;
    }, archived ? "Organisation archiviert." : "Organisation wieder aktiv.");
}

function deleteOrganization(id) {
    if (!window.confirm(`„${orgName(id)}“ wirklich löschen?`)) {
        return;
    }
    orgAction(async () => {
        await api.delete(`/api/org/organizations/${id}`);
        orgState.editingOrg = null;
    }, "Organisation gelöscht.");
}

function createOrgUser(event) {
    event.preventDefault();
    const form = event.target;
    const data = Object.fromEntries(new FormData(form).entries());
    orgAction(async () => {
        const result = await api.post("/api/org/users", {
            ...data,
            organization_id: Number(data.organization_id),
        });
        orgState.openUser = result.user.id;
        form.reset();
    }, "Konto angelegt.");
}

function saveUser(id) {
    const editor = document.querySelector(`.org-user-editor[data-user-id="${id}"]`);
    const value = field => editor?.querySelector(`[data-field="${field}"]`);
    const payload = {
        email: value("email")?.value ?? "",
        nickname: value("nickname")?.value ?? "",
    };
    // Vor- und Nachname nur senden, wenn ausgefüllt (ältere Konten haben
    // noch keinen getrennten Namen).
    for (const key of ["first_name", "last_name"]) {
        const text = value(key)?.value.trim();
        if (text) {
            payload[key] = text;
        }
    }
    if (value("active") && !value("active").disabled) {
        payload.active = value("active").checked;
    }
    if (value("platform_admin")) {
        payload.platform_admin = value("platform_admin").checked;
    }
    if (value("password")?.value) {
        payload.password = value("password").value;
    }
    orgAction(() => api.patch(`/api/org/users/${id}`, payload), "Konto gespeichert.");
}

function deleteUser(id, username) {
    if (!window.confirm(`Konto „${username}“ endgültig löschen?`)) {
        return;
    }
    orgAction(() => api.delete(`/api/org/users/${id}`), "Konto gelöscht.");
}

function setMembership(userId, organizationId, role) {
    orgAction(
        () => api.put(`/api/org/users/${userId}/memberships/${organizationId}`, {role}),
        "Rolle gespeichert. Das Konto muss sich ggf. neu anmelden."
    );
}

function removeMembership(userId, organizationId) {
    orgAction(
        () => api.delete(`/api/org/users/${userId}/memberships/${organizationId}`),
        "Rolle entfernt."
    );
}

function addMembership(userId, button) {
    const box = button.closest(".org-inline-add");
    const organizationId = box.querySelector('[data-role="new-membership-org"]').value;
    const role = box.querySelector('[data-role="new-membership-role"]').value;
    setMembership(userId, Number(organizationId), role);
}

function addQualification(userId, button) {
    const box = button.closest(".org-inline-add");
    const payload = {
        kind: box.querySelector('[data-role="new-qualification-kind"]').value,
        reference: box.querySelector('[data-role="new-qualification-reference"]').value,
        valid_until: box.querySelector('[data-role="new-qualification-until"]').value || null,
    };
    orgAction(
        () => api.post(`/api/org/users/${userId}/qualifications`, payload),
        "Nachweis erfasst."
    );
}

function deleteQualification(id) {
    orgAction(() => api.delete(`/api/org/qualifications/${id}`), "Nachweis entfernt.");
}
