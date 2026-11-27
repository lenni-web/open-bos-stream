// ==========================================================
// Mein Konto: eigene Angaben, Rollen, Nachweise, Passwort
// ==========================================================

const accountState = {
    user: null,
    message: "",
    error: false,
};

function accountDate(value) {
    if (!value) {
        return "–";
    }
    const date = new Date(value);
    return Number.isNaN(date.getTime())
        ? value
        : date.toLocaleDateString("de-DE", {dateStyle: "medium"});
}

function accountDateTime(value) {
    if (!value) {
        return "–";
    }
    const date = new Date(value);
    return Number.isNaN(date.getTime())
        ? value
        : date.toLocaleString("de-DE", {dateStyle: "short", timeStyle: "short"});
}

function setAccountMessage(message, error = false) {
    accountState.message = message;
    accountState.error = error;
}

function renderAccount() {
    const body = document.getElementById("account-body");
    if (!body) {
        return;
    }
    const user = accountState.user;
    if (!user) {
        body.innerHTML = accountState.message
            ? `<p class="push-message is-error">${escapeHTML(accountState.message)}</p>`
            : '<p class="service-inline-status">Wird geladen …</p>';
        return;
    }
    const roles = user.platform_admin
        ? '<li><strong>Superadmin</strong> <span>Technische Verwaltung des ganzen Servers</span></li>'
        : "";
    const memberships = user.memberships.map(item => `
        <li><strong>${escapeHTML(item.role_label)}</strong>
            <span>${escapeHTML(item.organization_name)}</span></li>`).join("");
    const qualifications = user.qualifications.map(item => `
        <li class="${item.valid ? "" : "is-expired"}">
            <strong>${escapeHTML(item.label)}</strong>
            <span>${item.reference ? `${escapeHTML(item.reference)} · ` : ""}${item.valid_until
                ? `gültig bis ${escapeHTML(accountDate(item.valid_until))}`
                : "ohne Ablaufdatum"}${item.valid ? "" : " – abgelaufen"}</span>
        </li>`).join("");
    body.innerHTML = `
        ${accountState.message ? `<p class="push-message ${accountState.error ? "is-error" : ""}" role="status">
            ${escapeHTML(accountState.message)}</p>` : ""}

        <section class="account-section">
            <h3>Angaben</h3>
            <form class="account-form" onsubmit="saveAccountProfile(event)">
                <label class="form-field">
                    <span>Benutzername</span>
                    <input class="bos-input" value="${escapeHTML(user.username)}" disabled>
                </label>
                <label class="form-field">
                    <span>Vorname</span>
                    <input class="bos-input" name="first_name" maxlength="60" required
                        value="${escapeHTML(user.first_name || "")}" autocomplete="given-name">
                </label>
                <label class="form-field">
                    <span>Nachname</span>
                    <input class="bos-input" name="last_name" maxlength="60" required
                        value="${escapeHTML(user.last_name || "")}" autocomplete="family-name">
                </label>
                <label class="form-field">
                    <span>Spitzname (optional, oben rechts angezeigt)</span>
                    <input class="bos-input" name="nickname" maxlength="40"
                        value="${escapeHTML(user.nickname || "")}" autocomplete="nickname">
                </label>
                <label class="form-field">
                    <span>E-Mail (optional)</span>
                    <input class="bos-input" name="email" type="email" maxlength="254"
                        value="${escapeHTML(user.email)}" autocomplete="email">
                </label>
                <div class="push-actions">
                    <button class="bos-button bos-button-small bos-button-green" type="submit">Speichern</button>
                </div>
            </form>
            <p class="push-hint">Letzte Anmeldung: ${escapeHTML(accountDateTime(user.last_login_at))}</p>
        </section>

        <section class="account-section">
            <h3>Rollen</h3>
            ${roles || memberships
                ? `<ul class="account-list">${roles}${memberships}</ul>`
                : '<p class="push-hint">Noch keiner Organisation zugeordnet.</p>'}
            <p class="push-hint">Rollen vergibt der Admin Ihrer Wehr bzw. des Landkreises.</p>
        </section>

        <section class="account-section">
            <h3>Fernpilotennachweise</h3>
            ${qualifications
                ? `<ul class="account-list">${qualifications}</ul>`
                : '<p class="push-hint">Kein Nachweis hinterlegt.</p>'}
            <p class="push-hint">Nachweise trägt der Admin Ihrer Wehr ein.</p>
        </section>

        <section class="account-section">
            <h3>Passwort ändern</h3>
            <form class="account-form" onsubmit="saveAccountPassword(event)">
                <input type="text" name="username" value="${escapeHTML(user.username)}"
                    autocomplete="username" hidden>
                <label class="form-field">
                    <span>Bisheriges Passwort</span>
                    <input class="bos-input" name="current_password" type="password" required
                        autocomplete="current-password">
                </label>
                <label class="form-field">
                    <span>Neues Passwort (mind. 10 Zeichen)</span>
                    <input class="bos-input" name="new_password" type="password" required minlength="10"
                        autocomplete="new-password">
                </label>
                <label class="form-field">
                    <span>Neues Passwort wiederholen</span>
                    <input class="bos-input" name="repeat_password" type="password" required minlength="10"
                        autocomplete="new-password">
                </label>
                <div class="push-actions">
                    <button class="bos-button bos-button-small" type="submit">Passwort ändern</button>
                </div>
                <p class="push-hint">Danach werden alle anderen Geräte abgemeldet; dieses bleibt angemeldet.</p>
            </form>
        </section>

        <section class="account-section">
            <h3>Benachrichtigungen</h3>
            <p class="push-hint">Push-Benachrichtigungen werden je Gerät eingeschaltet.</p>
            <div class="push-actions">
                <button class="bos-button bos-button-small" type="button" onclick="openPushFromAccount()">
                    Benachrichtigungen verwalten</button>
            </div>
        </section>`;
}

async function loadAccount() {
    try {
        const data = await api.get("/api/org/me");
        accountState.user = data.user;
    } catch (error) {
        accountState.user = null;
        setAccountMessage(error.message, true);
    }
    renderAccount();
}

async function openAccountDialog() {
    const dialog = document.getElementById("account-dialog");
    if (!dialog) {
        return;
    }
    setAccountMessage("");
    renderAccount();
    if (typeof dialog.showModal === "function") {
        dialog.showModal();
    } else {
        dialog.setAttribute("open", "");
    }
    await loadAccount();
}

function openPushFromAccount() {
    document.getElementById("account-dialog")?.close();
    if (typeof openPushDialog === "function") {
        openPushDialog();
    }
}

function updateVisibleUserName(user) {
    const full = user.display_name || user.username;
    document.querySelectorAll(".app-user-info strong").forEach(element => {
        element.textContent = full;
    });
    document.querySelectorAll(".app-user-name").forEach(element => {
        element.textContent = user.nickname || full;
    });
}

async function saveAccountProfile(event) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.target));
    try {
        const result = await api.patch("/api/org/me", {
            first_name: data.first_name,
            last_name: data.last_name,
            nickname: data.nickname,
            email: data.email,
        });
        accountState.user = result.user;
        updateVisibleUserName(result.user);
        setAccountMessage("Angaben gespeichert.");
    } catch (error) {
        setAccountMessage(error.message, true);
    }
    renderAccount();
}

async function saveAccountPassword(event) {
    event.preventDefault();
    const data = Object.fromEntries(new FormData(event.target));
    if (data.new_password !== data.repeat_password) {
        setAccountMessage("Die neuen Passwörter stimmen nicht überein.", true);
        renderAccount();
        return;
    }
    try {
        const result = await api.patch("/api/org/me", {
            current_password: data.current_password,
            new_password: data.new_password,
        });
        accountState.user = result.user;
        setAccountMessage("Passwort geändert. Andere Geräte wurden abgemeldet.");
    } catch (error) {
        setAccountMessage(error.message, true);
    }
    renderAccount();
}
