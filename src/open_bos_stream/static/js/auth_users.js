async function logoutUser() {
    await fetch("/auth/logout", {method: "POST"});
    window.location.href = "/login";
}

async function loadUsers() {
    const container = document.getElementById("user-list");
    if (!container || window.currentUser?.role !== "superadmin") {
        return;
    }
    try {
        const users = await api.get("/auth/users");
        container.innerHTML = users.map(user => `
            <div class="user-row">
                <span>
                    <strong>${escapeHTML(user.username)}</strong>
                    <small>${escapeHTML(user.role)}</small>
                </span>
                ${user.username === window.currentUser.username ? "" : `
                    <button class="bos-button bos-button-small" type="button"
                        onclick="deleteUser('${escapeHTML(user.username)}')">
                        Entfernen
                    </button>
                `}
            </div>
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
