async function logoutUser() {
    await fetch("/auth/logout", {method: "POST"});
    window.location.href = "/login";
}

async function loadUsers() {
    const container = document.getElementById("user-list");
    if (!container || window.currentUser?.role === "viewer") {
        return;
    }
    try {
        const users = await api.get("/auth/users");
        container.innerHTML = users.map(user => `
            <details class="user-row">
                <summary>
                    <span>
                        <strong>${escapeHTML(user.username)}</strong>
                        <small>${escapeHTML(user.role)}</small>
                    </span>
                    <span class="user-edit-label">Bearbeiten</span>
                </summary>
                <div class="user-edit-fields">
                    <label class="form-field">
                        <span>Rolle</span>
                        <select id="user-role-${escapeHTML(user.username)}"
                            class="bos-input">
                            <option value="viewer"
                                ${user.role === "viewer" ? "selected" : ""}>
                                Viewer
                            </option>
                            <option value="admin"
                                ${user.role === "admin" ? "selected" : ""}>
                                Admin
                            </option>
                            ${window.currentUser?.role === "superadmin" ? `
                                <option value="superadmin"
                                    ${user.role === "superadmin" ? "selected" : ""}>
                                    Superadmin
                                </option>
                            ` : ""}
                        </select>
                    </label>
                    <label class="form-field">
                        <span>Neues Passwort (optional)</span>
                        <input id="user-password-${escapeHTML(user.username)}"
                            class="bos-input" type="password" minlength="10"
                            autocomplete="new-password">
                    </label>
                    <div class="user-edit-actions">
                        <button class="bos-button bos-button-small"
                            type="button"
                            onclick="saveUser('${escapeHTML(user.username)}')">
                            Änderungen speichern
                        </button>
                        ${user.username === window.currentUser.username ? "" : `
                    <button class="bos-button bos-button-small" type="button"
                        onclick="deleteUser('${escapeHTML(user.username)}')">
                        Entfernen
                    </button>
                        `}
                    </div>
                </div>
            </details>
        `).join("");
    } catch (error) {
        container.textContent = error.message;
    }
}

async function createUser() {
    const username = document.getElementById("new-user-name").value;
    const password = document.getElementById("new-user-password").value;
    const role = document.getElementById("new-user-role").value;
    const status = document.getElementById("user-management-status");
    try {
        await api.post("/auth/users", {username, password, role});
        status.textContent = "Benutzer wurde angelegt.";
        document.getElementById("new-user-password").value = "";
        await loadUsers();
    } catch (error) {
        status.textContent = error.message;
    }
}

async function saveUser(username) {
    const role = document.getElementById(
        `user-role-${username}`
    ).value;
    const password = document.getElementById(
        `user-password-${username}`
    ).value;
    const status = document.getElementById("user-management-status");
    try {
        await api.patch(
            `/auth/users/${encodeURIComponent(username)}`,
            {
                role,
                password: password || null,
            }
        );
        if (username === window.currentUser.username) {
            await logoutUser();
            return;
        }
        status.textContent = "Benutzer wurde aktualisiert.";
        await loadUsers();
    } catch (error) {
        status.textContent = error.message;
    }
}

async function deleteUser(username) {
    if (!window.confirm(`Benutzer „${username}“ entfernen?`)) {
        return;
    }
    try {
        await api.delete(`/auth/users/${encodeURIComponent(username)}`);
        await loadUsers();
    } catch (error) {
        document.getElementById("user-management-status").textContent =
            error.message;
    }
}
