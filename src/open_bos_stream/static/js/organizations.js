// ==========================================================
// Organisation und Konten (Wehr-Admins, Kreis-Admins, Superadmins)
// ==========================================================

const orgState = {
    meta: null,
    organizations: [],
    users: [],
    editingOrg: null,
    openUser: null,
    // Aufgeklappte Mitgliederlisten und Suche bleiben beim Neuzeichnen erhalten.
    openMembers: new Set(),
    search: "",
};

function orgElement() {
    return document.getElementById("org-management");
}

// Benutzerkonten haben seit 0.25.4 eine eigene Seite („Benutzer“).
function userElement() {
    return document.getElementById("user-management");
}

let orgStatusTimer = null;

function orgStatus(text, kind = "") {
    document.querySelectorAll("[data-org-status]").forEach(status => {
        status.textContent = text;
        status.dataset.kind = kind;
    });
    // Erfolgsmeldungen verschwinden wieder, Fehler bleiben stehen.
    clearTimeout(orgStatusTimer);
    if (kind === "success") {
        orgStatusTimer = setTimeout(() => orgStatus(""), 5000);
    }
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

const ORG_KIND_ICONS = {
    landkreis: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2-6-2Zm0 0v14m6-12v14"/>',
    gemeinde: '<path d="M12 3 3 8l9 5 9-5-9-5ZM3 13l9 5 9-5"/>',
    default: '<path d="M3 21h18M5 21V9l7-5 7 5v12M9 21v-6h6v6"/>',
};

// Stadt-, Gemeinde- und Samtgemeindefeuerwehr teilen sich eine Ebene.
function orgKindGroup(kind) {
    return kind.endsWith("gemeindefeuerwehr") || kind === "stadtfeuerwehr" ? "gemeinde" : kind;
}

function orgIcon(paths, size = 18) {
    return `<svg class="ui-icon" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none"
        stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
        aria-hidden="true">${paths}</svg>`;
}

// Konten mit einer Rolle direkt in dieser Organisation, höchste Rolle zuerst.
function organizationMembers(id) {
    return orgState.users
        .map(user => ({
            user,
            roles: user.memberships.filter(item => item.organization_id === id).map(item => item.role),
        }))
        .filter(member => member.roles.length)
        .sort((a, b) => memberRank(b) - memberRank(a)
            || userSortName(a.user).localeCompare(userSortName(b.user), "de"));
}

function memberRank(member) {
    return Math.max(0, ...member.roles.map(role => USER_ROLE_RANK[role] ?? 0));
}

function userInitials(user) {
    const letters = user.first_name && user.last_name
        ? user.first_name[0] + user.last_name[0]
        : (user.display_name || user.username).slice(0, 2);
    return letters.toLocaleUpperCase("de");
}

function userAvatar(member) {
    return `<span class="org-avatar" data-rank="${memberRank(member)}"
        aria-hidden="true">${escapeHTML(userInitials(member.user))}</span>`;
}

function renderMember(member) {
    const {user, roles} = member;
    const state = userQualificationState(user);
    const notes = [user.nickname ? `„${user.nickname}“` : "", user.username].filter(Boolean).join(" · ");
    return `
        <li>
            <button class="org-member${user.active ? "" : " is-inactive"}" type="button"
                data-search="${escapeHTML(memberSearchText(user))}"
                title="Konto unter „Benutzer“ öffnen" onclick="openMemberAccount(${user.id})">
                ${userAvatar(member)}
                <span class="org-member-text">
                    <strong>${escapeHTML(user.display_name || user.username)}</strong>
                    <small>${escapeHTML(notes)}</small>
                    <span class="org-member-badges">
                        ${roles.map(roleBadge).join("")}
                        ${user.active ? "" : '<span class="org-chip is-muted">gesperrt</span>'}
                        ${state === "expired" ? '<span class="org-chip is-expired">Nachweis abgelaufen</span>' : ""}
                        ${state === "soon" ? '<span class="org-chip is-soon">Nachweis läuft ab</span>' : ""}
                    </span>
                </span>
            </button>
        </li>`;
}

function memberSearchText(user) {
    return [user.display_name, user.first_name, user.last_name, user.nickname, user.username]
        .join(" ").toLocaleLowerCase("de");
}

// Mitglieder sehen nur die Admins der Organisation vollständig; sonst
// bleibt es bei der Anzahl.
function renderMemberToggle(org, members) {
    if (!org.can_admin || !members.length) {
        return `<span class="org-members-count">${plural(org.member_count, "Mitglied", "Mitglieder")}</span>`;
    }
    const open = orgState.openMembers.has(org.id);
    const rest = members.length - 5;
    return `
        <button class="org-members-toggle" type="button" aria-expanded="${open}"
            aria-controls="org-members-${org.id}" onclick="toggleMembers(${org.id})">
            <span class="org-avatars">${members.slice(0, 5).map(userAvatar).join("")}
                ${rest > 0 ? `<span class="org-avatar is-more">+${rest}</span>` : ""}</span>
            <span>${plural(members.length, "Mitglied", "Mitglieder")}</span>
            <span class="org-chevron">${orgIcon('<path d="m6 9 6 6 6-6"/>', 16)}</span>
        </button>`;
}

function plural(count, one, many) {
    return `${count} ${count === 1 ? one : many}`;
}

function renderDrone(drone) {
    return `
        <li class="org-drone${drone.enabled ? "" : " is-inactive"}">
            <strong>${escapeHTML(drone.name)}</strong>
            <small>${escapeHTML(drone.drone_type || "Typ nicht angegeben")}${
                drone.enabled ? "" : " · deaktiviert"}</small>
        </li>`;
}

function renderOrganizationRow(org) {
    const parent = orgState.organizations.find(item => item.id === org.parent_id);
    // Ältere Einordnungen, die nicht zur Art passen, sichtbar machen.
    const misplaced = parent && !fitsUnder(org.kind, parent);
    const members = org.can_admin ? organizationMembers(org.id) : [];
    return `
        <div class="org-card${org.archived ? " is-archived" : ""}" data-level="${escapeHTML(orgKindGroup(org.kind))}"
            data-search="${escapeHTML(`${org.name} ${org.short_name ?? ""}`.toLocaleLowerCase("de"))}">
            <div class="org-card-head">
                <span class="org-card-icon">${orgIcon(ORG_KIND_ICONS[orgKindGroup(org.kind)] ?? ORG_KIND_ICONS.default, 20)}</span>
                <div class="org-card-title">
                    <strong>${escapeHTML(org.name)}</strong>
                    <small>${escapeHTML(org.kind_label)}${org.short_name ? ` · ${escapeHTML(org.short_name)}` : ""}</small>
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
            <div class="org-card-foot">
                ${renderMemberToggle(org, members)}
                ${org.source_count ? `<span class="org-chip">${plural(org.source_count, "Drohne", "Drohnen")}</span>` : ""}
                ${org.drones.length ? `
                    <ul class="org-drones" aria-label="Drohnen von ${escapeHTML(org.name)}">
                        ${org.drones.map(renderDrone).join("")}
                    </ul>` : ""}
                ${org.archived ? '<span class="org-chip is-muted">archiviert</span>' : ""}
                ${misplaced ? '<span class="org-chip is-soon">Einordnung prüfen</span>' : ""}
            </div>
            ${members.length ? `
                <ul class="org-members" id="org-members-${org.id}" data-org-members="${org.id}"
                    ${orgState.openMembers.has(org.id) ? "" : "hidden"}>
                    ${members.map(renderMember).join("")}
                </ul>` : ""}
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
    const active = orgState.organizations.filter(org => !org.archived).length;
    const drones = orgState.organizations.reduce((sum, org) => sum + org.source_count, 0);
    const accounts = orgState.users.filter(user => user.memberships.length).length;
    const stat = (count, label) => `<div><strong>${count}</strong><span>${label}</span></div>`;
    return `
        <div class="org-stats">
            ${stat(active, "Organisationen")}
            ${stat(accounts, "Mitglieder")}
            ${stat(drones, "Drohnen")}
        </div>
        <div class="org-toolbar">
            <input class="bos-input" type="search" value="${escapeHTML(orgState.search)}"
                placeholder="Organisation oder Person suchen" aria-label="Organisation oder Person suchen"
                oninput="searchOrganizations(this.value)">
            <button class="bos-button bos-button-small" type="button" data-members-all
                onclick="toggleAllMembers()">Alle aufklappen</button>
        </div>
        <p class="service-inline-status" data-org-empty hidden>Nichts gefunden.</p>
        <ul class="org-tree">${renderOrganizationBranch(null)}</ul>
    `;
}

// ----------------------------------------------------------
// Mitglieder aufklappen und suchen
// Nur Sichtbarkeit ändern: ein offenes Formular bleibt erhalten.
// ----------------------------------------------------------

function applyMemberVisibility() {
    const root = orgElement();
    if (!root) {
        return;
    }
    const query = orgState.search.trim().toLocaleLowerCase("de");
    const matches = element => element.dataset.search.includes(query);
    const visit = (item, parentMatches) => {
        const card = item.querySelector(":scope > .org-card");
        const list = card.querySelector(".org-members");
        const ownMatch = Boolean(query) && matches(card);
        let hits = 0;
        for (const member of list?.querySelectorAll(".org-member") ?? []) {
            const hit = !query || ownMatch || matches(member);
            member.parentElement.hidden = !hit;
            hits += query && !ownMatch && hit ? 1 : 0;
        }
        const showAll = parentMatches || ownMatch;
        let childVisible = false;
        for (const child of item.querySelectorAll(":scope > .org-tree > li")) {
            childVisible = visit(child, showAll) || childVisible;
        }
        const visible = !query || showAll || hits > 0 || childVisible;
        item.hidden = !visible;
        if (list) {
            const id = Number(list.dataset.orgMembers);
            const open = orgState.openMembers.has(id) || hits > 0;
            list.hidden = !open;
            card.querySelector(".org-members-toggle").setAttribute("aria-expanded", String(open));
        }
        return visible;
    };
    let any = false;
    for (const item of root.querySelectorAll(":scope > .org-tree > li")) {
        any = visit(item, false) || any;
    }
    const empty = root.querySelector("[data-org-empty]");
    if (empty) {
        empty.hidden = any;
    }
    const all = root.querySelector("[data-members-all]");
    if (all) {
        const ids = [...root.querySelectorAll("[data-org-members]")].map(list => Number(list.dataset.orgMembers));
        all.hidden = !ids.length;
        all.textContent = ids.every(id => orgState.openMembers.has(id)) ? "Alle zuklappen" : "Alle aufklappen";
    }
}

function toggleMembers(id) {
    if (!orgState.openMembers.delete(id)) {
        orgState.openMembers.add(id);
    }
    applyMemberVisibility();
}

function toggleAllMembers() {
    const ids = [...orgElement().querySelectorAll("[data-org-members]")]
        .map(list => Number(list.dataset.orgMembers));
    const open = !ids.every(id => orgState.openMembers.has(id));
    orgState.openMembers = new Set(open ? ids : []);
    applyMemberVisibility();
}

function searchOrganizations(value) {
    orgState.search = value;
    applyMemberVisibility();
}

// Konto auf der Seite „Benutzer“ geöffnet zeigen.
function openMemberAccount(id) {
    showCreatedUser(id);
    renderUserManagement();
    showPage("users");
    document.querySelector(`[data-user-row="${id}"]`)?.scrollIntoView({block: "center"});
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
    destroyLocationPicker();
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
                <div class="form-field form-field-wide">
                    <button class="bos-button bos-button-small org-location-toggle" type="button"
                        aria-expanded="false" onclick="toggleLocationPicker(this)">Auf Karte wählen</button>
                    <div class="org-location" hidden>
                        <div class="org-location-bar">
                            <small data-location-hint role="status"></small>
                            <select class="bos-input" data-location-base aria-label="Grundkarte" hidden></select>
                            <button class="bos-button bos-button-small" type="button"
                                onclick="clearLocation(this.form)">Standort entfernen</button>
                        </div>
                        <div class="org-location-map"></div>
                    </div>
                </div>
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
    const form = slot.querySelector("form");
    for (const name of ["latitude", "longitude"]) {
        form.elements[name].addEventListener("input", () => showLocationPin(form, true));
    }
}

// ----------------------------------------------------------
// Standort der Wache auf der Karte wählen
// ----------------------------------------------------------

const locationPicker = {map: null, marker: null};

function destroyLocationPicker() {
    locationPicker.map?.remove();
    locationPicker.map = null;
    locationPicker.marker = null;
}

function formLocation(form) {
    const latitude = numberOrNull(form.elements.latitude.value);
    const longitude = numberOrNull(form.elements.longitude.value);
    const valid = latitude !== null && longitude !== null
        && Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180;
    return valid ? [longitude, latitude] : null;
}

// Ohne eigenen Standort: der nächste hinterlegte Standort darüber.
function inheritedLocation() {
    const editing = orgState.editingOrg;
    const find = id => orgState.organizations.find(item => item.id === id);
    let org = find(editing?.id ?? editing?.parentId);
    while (org) {
        if (org.latitude !== null && org.longitude !== null) {
            return [org.longitude, org.latitude];
        }
        org = find(org.parent_id);
    }
    return null;
}

function setLocation(form, lngLat) {
    form.elements.latitude.value = lngLat.lat.toFixed(6);
    form.elements.longitude.value = lngLat.lng.toFixed(6);
    showLocationPin(form);
}

function clearLocation(form) {
    form.elements.latitude.value = "";
    form.elements.longitude.value = "";
    showLocationPin(form);
}

function showLocationPin(form, center = false) {
    const map = locationPicker.map;
    if (!map) {
        return;
    }
    const position = formLocation(form);
    if (!position) {
        locationPicker.marker?.remove();
        locationPicker.marker = null;
        return;
    }
    if (!locationPicker.marker) {
        locationPicker.marker = new maplibregl.Marker({color: "#c92835", draggable: true})
            .setLngLat(position)
            .addTo(map);
        locationPicker.marker.on("dragend", () => setLocation(form, locationPicker.marker.getLngLat()));
    } else {
        locationPicker.marker.setLngLat(position);
    }
    if (center) {
        map.jumpTo({center: position});
    }
}

async function toggleLocationPicker(button) {
    const form = button.form;
    const box = form.querySelector(".org-location");
    const open = box.hidden;
    box.hidden = !open;
    button.setAttribute("aria-expanded", String(open));
    button.textContent = open ? "Karte schließen" : "Auf Karte wählen";
    destroyLocationPicker();
    if (!open) {
        return;
    }
    const hint = box.querySelector("[data-location-hint]");
    const stale = () => !box.isConnected || box.hidden || locationPicker.map;
    hint.textContent = "Karte wird geladen …";
    try {
        await maplibreReady();
        const info = await loadBaseMaps();
        if (!info.options.length) {
            hint.textContent = "Keine Karte verfügbar. Bitte Koordinaten eintippen.";
            return;
        }
        const base = await loadBaseStyle(preferredBaseMap(info));
        if (stale()) {
            return;
        }
        const own = formLocation(form);
        const near = own ?? inheritedLocation();
        const map = new maplibregl.Map({
            container: box.querySelector(".org-location-map"),
            style: base.style,
            center: near ?? info.center.slice(0, 2),
            zoom: own ? 16 : near ? 12 : info.center[2] ?? 10,
            maxZoom: 19,
            attributionControl: false,
        });
        locationPicker.map = map;
        applyBaseZoomRange(map, info, base.id);
        map.addControl(new maplibregl.NavigationControl({showCompass: false}), "top-right");
        map.addControl(new maplibregl.AttributionControl({compact: true}));
        map.once("load", () => collapseMapAttribution(map));
        map.on("click", event => setLocation(form, event.lngLat.wrap()));
        showLocationPin(form);
        bindLocationBaseSelect(box.querySelector("[data-location-base]"), info, base);
        hint.textContent = "Auf die Karte tippen oder den Pin ziehen, dann speichern.";
    } catch (error) {
        console.error("Standortkarte:", error);
        hint.textContent = "Karte konnte nicht geladen werden. Bitte Koordinaten eintippen.";
    }
}

// Karte oder Luftbild; die Wahl gilt nur für dieses Formular.
function bindLocationBaseSelect(select, info, base) {
    let ids = baseStyleIds(base.style);
    select.innerHTML = info.options.map(option => `
        <option value="${option.id}" ${option.id === base.id ? "selected" : ""}>${escapeHTML(option.label)}</option>
    `).join("");
    select.hidden = info.options.length < 2;
    select.onchange = async () => {
        const next = await loadBaseStyle(select.value);
        const map = locationPicker.map;
        if (!map || !select.isConnected) {
            return;
        }
        ids = applyBaseStyle(map, next, ids);
        applyBaseZoomRange(map, info, next.id);
        select.value = next.id;
    };
}

function renderOrganizationManagement() {
    destroyLocationPicker();
    const organizations = orgElement();
    if (organizations) {
        organizations.innerHTML = `
            <p class="service-inline-status" role="status" data-org-status></p>
            ${renderOrganizations()}
        `;
        applyMemberVisibility();
        renderOrganizationForm();
    }
    renderUserManagement();
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
            orgStatus(typeof successText === "function" ? successText() : successText, "success");
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
    let created = "";
    orgAction(async () => {
        const result = await api.post("/api/org/users", {
            ...data,
            organization_id: Number(data.organization_id),
        });
        showCreatedUser(result.user.id);
        created = result.user.username;
    }, () => `Konto angelegt. Anmeldung mit dem Benutzernamen „${created}“.`);
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

async function setRoles(userId, organizationId, roles) {
    await orgAction(
        () => api.put(`/api/org/users/${userId}/memberships/${organizationId}`, {roles}),
        "Rollen gespeichert. Das Konto muss sich ggf. neu anmelden."
    );
    // Auch nach einem Fehler den gespeicherten Stand zeigen.
    renderUserResults();
}

function removeMembership(userId, organizationId) {
    orgAction(
        () => api.delete(`/api/org/users/${userId}/memberships/${organizationId}`),
        "Rolle entfernt."
    );
}

function addMembership(userId, box) {
    const organizationId = box.querySelector('[data-role="new-membership-org"]').value;
    const roles = checkedRoles(box);
    if (!roles.length) {
        orgStatus("Bitte mindestens eine Rolle ankreuzen.", "error");
        return;
    }
    setRoles(userId, Number(organizationId), roles);
}

function addQualification(userId, box) {
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
