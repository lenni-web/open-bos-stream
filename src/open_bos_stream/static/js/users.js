// ==========================================================
// Seite „Benutzer“: Liste mit Suche, Filtern und Sortierung,
// darunter je Konto der Editor. Daten und Aktionen liegen in
// organizations.js (orgState, orgAction, saveUser …).
// ==========================================================

const USER_SOON_DAYS = 90;
const USER_SORT_KEY = "openBosUserSort";
const USER_ROLE_RANK = {ortsbrandmeister: 4, admin: 3, operator: 2, viewer: 1};
const USER_SORTS = {
    name: "Name",
    role: "Rolle",
    organization: "Organisation",
    qualification: "Nachweise",
    login: "Letzte Anmeldung",
};

const userList = {
    search: "",
    organization: "",
    role: "",
    status: "",
    sort: "name",
    direction: 1,
    open: null,
    adding: false,
};

try {
    const stored = JSON.parse(localStorage.getItem(USER_SORT_KEY));
    if (stored && USER_SORTS[stored.sort]) {
        userList.sort = stored.sort;
        userList.direction = stored.direction === -1 ? -1 : 1;
    }
} catch (error) {
    // Ohne Speicher wird nach Name sortiert.
}

// ----------------------------------------------------------
// Auswertung
// ----------------------------------------------------------

function userSortName(user) {
    return user.last_name
        ? `${user.last_name}, ${user.first_name}`
        : user.display_name || user.username;
}

function qualificationState(item) {
    if (!item.valid) {
        return "expired";
    }
    if (!item.valid_until) {
        return "ok";
    }
    const days = (new Date(`${item.valid_until}T23:59:59`) - Date.now()) / 86400000;
    return days <= USER_SOON_DAYS ? "soon" : "ok";
}

// Je Art zählt der am längsten gültige Nachweis: Ein abgelaufener, der
// schon erneuert wurde, ist kein Handlungsbedarf.
function currentQualifications(user) {
    const best = new Map();
    for (const item of user.qualifications) {
        const key = item.kind === "other" ? `other-${item.id}` : item.kind;
        const known = best.get(key);
        if (!known || (known.valid_until && (!item.valid_until || item.valid_until > known.valid_until))) {
            best.set(key, item);
        }
    }
    return [...best.values()];
}

function userQualificationState(user) {
    const states = currentQualifications(user).map(qualificationState);
    return ["expired", "soon", "ok"].find(state => states.includes(state)) ?? "none";
}

const USER_STATUS = {
    expired: {label: "Nachweis abgelaufen", test: user => userQualificationState(user) === "expired"},
    soon: {label: `Läuft in ${USER_SOON_DAYS} Tagen ab`, test: user => userQualificationState(user) === "soon"},
    none: {label: "Ohne Nachweis", test: user => userQualificationState(user) === "none"},
    never: {label: "Nie angemeldet", test: user => !user.last_login_at},
    inactive: {label: "Gesperrt", test: user => !user.active},
};

function highestRole(user) {
    if (user.platform_admin) {
        return 5;
    }
    return Math.max(0, ...user.memberships.map(item => USER_ROLE_RANK[item.role] ?? 0));
}

// Je Organisation die Rollen (Reihenfolge wie vom Server: höchste zuerst).
function groupedMemberships(user) {
    const groups = new Map();
    for (const item of user.memberships) {
        const group = groups.get(item.organization_id)
            ?? {id: item.organization_id, editable: item.editable, roles: []};
        group.roles.push(item.role);
        groups.set(item.organization_id, group);
    }
    return [...groups.values()];
}

function userOrganizationNames(user) {
    return groupedMemberships(user).map(group => orgName(group.id))
        .sort((a, b) => a.localeCompare(b, "de"));
}

// Die gewählte Organisation samt Untereinheiten.
function organizationWithChildren(id) {
    const result = new Set([id]);
    for (const {org} of orgTree()) {
        if (result.has(org.parent_id)) {
            result.add(org.id);
        }
    }
    return result;
}

// Gefiltert nach Suche, Organisation und Rolle (ohne Status).
function usersInSelection() {
    const words = userList.search.toLocaleLowerCase("de").split(/\s+/).filter(Boolean);
    const organizations = userList.organization
        ? organizationWithChildren(Number(userList.organization))
        : null;
    return orgState.users.filter(user => {
        const text = [
            user.username, user.display_name, user.first_name, user.last_name,
            user.nickname, user.email, ...userOrganizationNames(user),
        ].join(" ").toLocaleLowerCase("de");
        if (!words.every(word => text.includes(word))) {
            return false;
        }
        // Rolle und Organisation müssen in derselben Zuordnung zutreffen.
        if (userList.role === "superadmin") {
            if (!user.platform_admin) {
                return false;
            }
        } else if (userList.role) {
            return user.memberships.some(item => item.role === userList.role
                && (!organizations || organizations.has(item.organization_id)));
        }
        return !organizations
            || user.memberships.some(item => organizations.has(item.organization_id));
    });
}

function sortUsers(users) {
    const text = (a, b) => a.localeCompare(b, "de", {sensitivity: "base"});
    const urgency = {expired: 0, soon: 1, none: 2, ok: 3};
    const compare = {
        name: (a, b) => text(userSortName(a), userSortName(b)),
        role: (a, b) => highestRole(b) - highestRole(a),
        organization: (a, b) => text(userOrganizationNames(a)[0] ?? "￿", userOrganizationNames(b)[0] ?? "￿"),
        qualification: (a, b) => urgency[userQualificationState(a)] - urgency[userQualificationState(b)],
        // Zuletzt angemeldete zuerst.
        login: (a, b) => text(b.last_login_at ?? "", a.last_login_at ?? ""),
    }[userList.sort];
    return [...users].sort((a, b) =>
        compare(a, b) * userList.direction || text(userSortName(a), userSortName(b)));
}

// ----------------------------------------------------------
// Darstellung
// ----------------------------------------------------------

function roleBadge(role) {
    const label = role === "superadmin" ? "Superadmin" : orgState.meta?.roles?.[role] ?? role;
    return `<span class="role-badge" data-role="${escapeHTML(role)}">${escapeHTML(label)}</span>`;
}

function qualificationShort(item) {
    return {a1a3: "A1/A3", a2: "A2", sts: "STS", other: "Sonstiger"}[item.kind] ?? item.kind;
}

function qualificationValidity(item) {
    if (!item.valid_until) {
        return "unbefristet";
    }
    return item.valid
        ? `gültig bis ${formatDate(item.valid_until)}`
        : `abgelaufen am ${formatDate(item.valid_until)}`;
}

function qualificationChip(item, text) {
    const style = {expired: "is-expired", soon: "is-soon", ok: "is-valid"}[qualificationState(item)];
    return `<span class="org-chip ${style}">${escapeHTML(text)}</span>`;
}

function userLogin(value) {
    return value ? accountDateTime(value) : "nie";
}

function renderUserRow(user) {
    const open = userList.open === user.id;
    const memberships = [
        user.platform_admin ? `<span class="users-membership">${roleBadge("superadmin")}</span>` : "",
        ...groupedMemberships(user).map(group => `
            <span class="users-membership"><span class="users-organization">${escapeHTML(orgName(group.id))}</span>
                ${group.roles.map(roleBadge).join("")}</span>`),
    ].join("");
    const notes = [
        user.username,
        user.nickname ? `„${user.nickname}“` : "",
        user.active ? "" : "gesperrt",
        user.first_name ? "" : "Name fehlt",
    ].filter(Boolean).join(" · ");
    return `
        <li class="users-item${open ? " is-open" : ""}${user.active ? "" : " is-inactive"}">
            <button class="users-row" type="button" aria-expanded="${open}" data-user-row="${user.id}"
                onclick="toggleUser(${user.id})">
                <span><strong>${escapeHTML(userSortName(user))}</strong><small>${escapeHTML(notes)}</small></span>
                <span>${memberships || "<small>ohne Organisation</small>"}</span>
                <span>${currentQualifications(user).map(item => qualificationChip(
                    item, `${qualificationShort(item)} · ${qualificationValidity(item)}`)).join("")
                    || "<small>kein Nachweis</small>"}</span>
                <span><small>Angemeldet: ${escapeHTML(userLogin(user.last_login_at))}</small></span>
                <span class="users-chevron" aria-hidden="true">
                    <svg class="ui-icon" width="16" height="16" viewBox="0 0 24 24" fill="none"
                        stroke="currentColor" stroke-width="2"><path d="m6 9 6 6 6-6"/></svg>
                </span>
            </button>
            ${open ? renderUserEditor(user) : ""}
        </li>`;
}

function usernameField(user) {
    return `
        <label class="form-field">
            <span>Benutzername (Anmeldung)</span>
            <input class="bos-input" value="${escapeHTML(user.username)}" readonly>
        </label>`;
}

function renderUserAccountCard(user) {
    if (!user.manageable) {
        return `
            <section class="users-card">
                <h4>Konto</h4>
                ${usernameField(user)}
                <p class="users-hint">Dieses Konto gehört auch zu Organisationen außerhalb
                    Ihres Bereichs. Kontodaten ändert die zuständige Ebene; Rollen in Ihrem
                    Bereich können Sie hier vergeben.</p>
            </section>`;
    }
    const platform = Boolean(window.currentPermissions?.superadmin);
    const ownId = window.currentUser?.user_id;
    return `
        <section class="users-card">
            <h4>Konto</h4>
            <div class="form-grid">
                ${usernameField(user)}
                ${userNameFields(user)}
                <label class="form-field">
                    <span>E-Mail (optional, auch zur Anmeldung)</span>
                    <input class="bos-input" data-field="email" type="email" maxlength="254"
                        value="${escapeHTML(user.email)}">
                </label>
                <label class="form-field">
                    <span>Neues Passwort</span>
                    <input class="bos-input" data-field="password" type="password"
                        minlength="10" autocomplete="new-password" placeholder="leer = unverändert">
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
            </div>
        </section>`;
}

// Ankreuzfelder; „Ortsbrandmeister“ gibt es nur in Ortsfeuerwehren.
function roleChoices(organizationId, selected, legend, attributes = "") {
    const kind = orgState.organizations.find(item => item.id === organizationId)?.kind;
    return `
        <fieldset class="users-roles">
            <legend>${escapeHTML(legend)}</legend>
            ${Object.entries(orgState.meta?.roles ?? {})
                .filter(([value]) => value !== "ortsbrandmeister" || kind === "ortsfeuerwehr"
                    || selected.includes(value))
                .map(([value, label]) => `
                    <label><input type="checkbox" value="${value}" ${attributes}
                        ${selected.includes(value) ? "checked" : ""}>${escapeHTML(label)}</label>`)
                .join("")}
        </fieldset>`;
}

function checkedRoles(element) {
    return [...element.querySelectorAll(".users-roles input:checked")].map(input => input.value);
}

function renderUserRoleCard(user) {
    // Nur Organisationen ohne Rolle anbieten; vorhandene ändert die Liste darüber.
    const admins = adminOrganizations()
        .filter(({org}) => !user.memberships.some(item => item.organization_id === org.id));
    return `
        <section class="users-card">
            <h4>Rollen</h4>
            <p class="users-hint">In einer Organisation sind mehrere Rollen möglich, zum Beispiel
                Ortsbrandmeister und Drohnenteam. Es gelten die Rechte der höchsten Rolle.</p>
            <ul class="users-entries">
                ${groupedMemberships(user).map(group => group.editable ? `
                    <li class="users-membership-edit">
                        <strong>${escapeHTML(orgName(group.id))}</strong>
                        <button class="bos-button bos-button-small" type="button"
                            onclick="removeMembership(${user.id}, ${group.id})">Entfernen</button>
                        ${roleChoices(group.id, group.roles, `Rollen in ${orgName(group.id)}`,
                            `onchange="changeRoles(${user.id}, ${group.id}, this)"`)}
                    </li>` : `
                    <li>
                        <div><strong>${escapeHTML(orgName(group.id))}</strong>
                            <span class="users-membership">${group.roles.map(roleBadge).join("")}</span></div>
                    </li>`).join("") || '<li class="is-muted">Keiner Organisation zugeordnet.</li>'}
            </ul>
            ${admins.length ? `
            <div class="users-add">
                <h5>Rollen in weiterer Organisation vergeben</h5>
                <label class="form-field">
                    <span>Organisation</span>
                    <select class="bos-input" data-role="new-membership-org"
                        onchange="updateNewRoleChoices(this)">${orgOptions(admins)}</select>
                </label>
                <div data-new-roles>${roleChoices(admins[0].org.id, ["viewer"], "Rollen")}</div>
                <button class="bos-button bos-button-small" type="button"
                    onclick="addMembership(${user.id}, this.closest('.users-add'))">Hinzufügen</button>
            </div>` : ""}
        </section>`;
}

function renderUserQualificationCard(user) {
    const kinds = Object.entries(orgState.meta?.qualification_kinds ?? {}).map(([value, label]) => `
        <option value="${value}">${escapeHTML(label)}</option>`).join("");
    return `
        <section class="users-card">
            <h4>Fernpilotennachweise</h4>
            <ul class="users-entries">
                ${user.qualifications.map(item => `
                    <li>
                        <div>
                            <strong>${escapeHTML(item.label)}</strong>
                            ${item.reference ? `<small>Nr. ${escapeHTML(item.reference)}</small>` : ""}
                            ${qualificationChip(item, qualificationValidity(item))}
                        </div>
                        <button class="bos-button bos-button-small" type="button"
                            onclick="deleteQualification(${item.id})">Entfernen</button>
                    </li>`).join("") || '<li class="is-muted">Noch kein Nachweis erfasst.</li>'}
            </ul>
            <div class="users-add">
                <h5>Nachweis hinzufügen</h5>
                <label class="form-field">
                    <span>Art</span>
                    <select class="bos-input" data-role="new-qualification-kind">${kinds}</select>
                </label>
                <label class="form-field">
                    <span>Nummer (optional)</span>
                    <input class="bos-input" data-role="new-qualification-reference" maxlength="80">
                </label>
                <label class="form-field">
                    <span>Gültig bis (Ablaufdatum)</span>
                    <input class="bos-input" data-role="new-qualification-until" type="date">
                </label>
                <button class="bos-button bos-button-small" type="button"
                    onclick="addQualification(${user.id}, this.closest('.users-add'))">Hinzufügen</button>
            </div>
            <p class="users-hint">Einzutragen ist, bis wann der Nachweis gilt, nicht das
                Ausstellungsdatum (A1/A3 und A2: in der Regel fünf Jahre). Ohne Datum gilt
                er als unbefristet.</p>
        </section>`;
}

function renderUserEditor(user) {
    return `
        <div class="users-editor org-user-editor" data-user-id="${user.id}">
            ${renderUserAccountCard(user)}
            ${renderUserRoleCard(user)}
            ${renderUserQualificationCard(user)}
        </div>`;
}

// Nur Kennzahlen und Liste neu zeichnen, damit das Suchfeld den Fokus behält.
function renderUserResults() {
    const results = document.getElementById("users-results");
    if (!results) {
        return;
    }
    const selection = usersInSelection();
    const users = sortUsers(userList.status
        ? selection.filter(USER_STATUS[userList.status].test)
        : selection);
    const stat = (key, label, count, warning = false) => `
        <button type="button" aria-pressed="${userList.status === key}"
            class="${warning && count ? "is-warning" : ""}" onclick="setUserStatus('${key}')">
            <strong>${count}</strong>${escapeHTML(label)}</button>`;
    const sortButton = key => `
        <button type="button" aria-pressed="${userList.sort === key}" onclick="setUserSort('${key}')">
            ${USER_SORTS[key]}${userList.sort === key ? (userList.direction === 1 ? " ▲" : " ▼") : ""}</button>`;
    results.innerHTML = `
        <div class="users-stats" role="group" aria-label="Nach Status filtern">
            ${stat("", "Konten", selection.length)}
            ${Object.entries(USER_STATUS).map(([key, status]) => stat(
                key, status.label, selection.filter(status.test).length,
                key === "expired" || key === "soon")).join("")}
        </div>
        <p class="users-count" role="status">${users.length} von ${orgState.users.length} Konten</p>
        <ul class="users-table">
            <li class="users-head">
                ${sortButton("name")}
                <div>${sortButton("organization")}${sortButton("role")}</div>
                ${sortButton("qualification")}
                ${sortButton("login")}
                <span></span>
            </li>
            ${users.map(renderUserRow).join("")
                || '<li class="users-empty">Kein Konto passt zu Suche und Filtern.</li>'}
        </ul>`;
}

function renderNewUserForm() {
    const admins = adminOrganizations();
    if (!admins.length || !userList.adding) {
        return "";
    }
    return `
        <form class="org-block org-form" onsubmit="createOrgUser(event)">
            <h3>Neues Konto</h3>
            <div class="form-grid">
                <label class="form-field">
                    <span>Benutzername (Buchstaben, Zahlen, - oder _)</span>
                    <input class="bos-input" name="username" required minlength="3" maxlength="32"
                        autocomplete="off" placeholder="z. B. m-mustermann">
                </label>
                ${userNameFields()}
                <label class="form-field">
                    <span>E-Mail (optional, auch zur Anmeldung)</span>
                    <input class="bos-input" name="email" type="email" maxlength="254">
                </label>
                <label class="form-field">
                    <span>Startpasswort (mind. 10 Zeichen)</span>
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
                <button class="bos-button bos-button-small bos-button-green" type="submit">Konto anlegen</button>
                <button class="bos-button bos-button-small" type="button" onclick="toggleNewUser()">Abbrechen</button>
            </div>
            <p class="users-hint">
                Zuschauer sehen Livebilder, Karte und Wetter ihrer Organisation. Drohnenteams
                erstellen zusätzlich Gastlinks. Wehr-Admins verwalten Quellen und Konten.
                Der Ortsbrandmeister (nur in Ortsfeuerwehren) hat dieselben Rechte.
                Rollen gelten auch für alle Untereinheiten.
            </p>
        </form>`;
}

function renderUserManagement() {
    const element = userElement();
    if (!element) {
        return;
    }
    const option = (value, label, selected) => `
        <option value="${value}" ${value === selected ? "selected" : ""}>${escapeHTML(label)}</option>`;
    const organizations = orgTree().filter(({org}) => org.can_admin);
    const roles = {...orgState.meta?.roles};
    if (window.currentPermissions?.superadmin) {
        roles.superadmin = "Superadmin";
    }
    element.innerHTML = `
        <p class="service-inline-status users-status" role="status" data-org-status></p>
        <div class="users-toolbar">
            <label class="users-search">
                <span>Suche</span>
                <input class="bos-input" type="search" value="${escapeHTML(userList.search)}"
                    placeholder="Name, Benutzername, E-Mail, Wehr"
                    oninput="setUserFilter('search', this.value)">
            </label>
            <label>
                <span>Organisation (mit Untereinheiten)</span>
                <select class="bos-input" onchange="setUserFilter('organization', this.value)">
                    <option value="">Alle in meinem Bereich</option>
                    ${orgOptions(organizations, Number(userList.organization))}
                </select>
            </label>
            <label>
                <span>Rolle</span>
                <select class="bos-input" onchange="setUserFilter('role', this.value)">
                    <option value="">Alle Rollen</option>
                    ${Object.entries(roles).map(([value, label]) => option(value, label, userList.role)).join("")}
                </select>
            </label>
            <label class="users-sort-select">
                <span>Sortieren nach</span>
                <select class="bos-input" onchange="setUserSort(this.value, 1)">
                    ${Object.entries(USER_SORTS).map(([value, label]) => option(value, label, userList.sort)).join("")}
                </select>
            </label>
            ${adminOrganizations().length ? `
            <button class="bos-button bos-button-green" type="button" aria-expanded="${userList.adding}"
                onclick="toggleNewUser()">＋ Neues Konto</button>` : ""}
        </div>
        ${renderNewUserForm()}
        <div id="users-results" class="org-management"></div>`;
    renderUserResults();
}

// ----------------------------------------------------------
// Bedienung
// ----------------------------------------------------------

function setUserFilter(key, value) {
    userList[key] = value;
    renderUserResults();
}

function setUserStatus(status) {
    setUserFilter("status", userList.status === status ? "" : status);
}

function setUserSort(sort, direction = null) {
    userList.direction = direction ?? (userList.sort === sort ? -userList.direction : 1);
    userList.sort = sort;
    try {
        localStorage.setItem(USER_SORT_KEY, JSON.stringify({sort, direction: userList.direction}));
    } catch (error) {
        // Die Sortierung gilt dann nur bis zum Neuladen.
    }
    renderUserResults();
}

function toggleUser(id) {
    userList.open = userList.open === id ? null : id;
    renderUserResults();
    document.querySelector(`[data-user-row="${id}"]`)?.focus();
}

function toggleNewUser() {
    userList.adding = !userList.adding;
    renderUserManagement();
    userElement()?.querySelector('input[name="username"]')?.focus();
}

function changeRoles(userId, organizationId, input) {
    const roles = checkedRoles(input.closest("li"));
    if (!roles.length) {
        input.checked = true;
        orgStatus("Mindestens eine Rolle muss bleiben. Zum Entziehen aller Rollen „Entfernen“ wählen.", "error");
        return;
    }
    setRoles(userId, organizationId, roles);
}

function updateNewRoleChoices(select) {
    const box = select.closest(".users-add").querySelector("[data-new-roles]");
    box.innerHTML = roleChoices(Number(select.value), checkedRoles(box), "Rollen");
}

// Das neue Konto aufgeklappt zeigen, auch wenn Filter es verbergen würden.
function showCreatedUser(id) {
    Object.assign(userList, {search: "", organization: "", role: "", status: "", open: id, adding: false});
}
