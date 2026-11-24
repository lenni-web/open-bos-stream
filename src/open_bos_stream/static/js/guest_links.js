// ==========================================================
// Gastlinks erstellen und verwalten (Admins und Superadmins)
// ==========================================================

let createdGuestLinkUrl = "";

function guestLinkDialog() {
    return document.getElementById("guest-link-dialog");
}

function formatGuestLinkTime(seconds) {
    if (!seconds) {
        return "—";
    }
    return new Date(seconds * 1000).toLocaleString("de-DE", {
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
    });
}

function renderGuestLinkSources() {
    const fieldset = document.getElementById("guest-link-sources");
    if (!fieldset) {
        return;
    }
    const sources = window.dashboard?.sources ?? [];
    const legend = '<legend>Freigegebene Quellen</legend>';
    if (sources.length === 0) {
        fieldset.innerHTML = legend +
            "<p>Es sind keine aktiven Quellen eingerichtet.</p>";
        return;
    }
    const anyOnline = sources.some(source => source.ready);
    fieldset.innerHTML = legend + sources.map(source => `
        <label>
            <input type="checkbox" value="${escapeHTML(source.id)}"
                ${(!anyOnline || source.ready) ? "checked" : ""}>
            <span>${escapeHTML(source.name)}</span>
            ${source.ready ? "<small>live</small>" : ""}
        </label>
    `).join("");
}

function openGuestLinkDialog() {
    const dialog = guestLinkDialog();
    if (!dialog) {
        return;
    }
    document.getElementById("guest-link-form").hidden = false;
    document.getElementById("guest-link-result").hidden = true;
    document.getElementById("guest-link-status").textContent = "";
    document.getElementById("guest-link-label").value = "";
    renderGuestLinkSources();
    dialog.showModal();
    document.getElementById("guest-link-label").focus();
}

function closeGuestLinkDialog() {
    createdGuestLinkUrl = "";
    document.getElementById("guest-link-url").value = "";
    document.getElementById("guest-link-qr").innerHTML = "";
    guestLinkDialog()?.close();
}

function renderGuestLinkQr(url) {
    const target = document.getElementById("guest-link-qr");
    if (!target || typeof qrcode !== "function") {
        return;
    }
    const code = qrcode(0, "M");
    code.addData(url);
    code.make();
    target.innerHTML = code.createSvgTag({
        cellSize: 4,
        margin: 2,
        scalable: true,
    });
}

async function submitGuestLink(event) {
    event.preventDefault();
    const status = document.getElementById("guest-link-status");
    const label = document.getElementById("guest-link-label").value.trim();
    const sourceIds = Array.from(
        document.querySelectorAll("#guest-link-sources input:checked")
    ).map(input => input.value);
    const hours = Number(document.getElementById("guest-link-hours").value);

    if (!label) {
        status.textContent = "Bitte eine Bezeichnung angeben.";
        return;
    }
    if (sourceIds.length === 0) {
        status.textContent = "Bitte mindestens eine Quelle auswählen.";
        return;
    }

    status.textContent = "Wird erstellt …";
    try {
        const result = await api.post("/guest-links", {
            label,
            source_ids: sourceIds,
            hours,
        });
        createdGuestLinkUrl = result.url;
        document.getElementById("guest-link-form").hidden = true;
        document.getElementById("guest-link-result").hidden = false;
        document.getElementById("guest-link-url").value = result.url;
        document.getElementById("guest-link-summary").textContent =
            `„${result.link.label}“ · ` +
            result.link.sources.map(source => source.name).join(", ") +
            ` · gültig bis ${formatGuestLinkTime(result.link.expires_at)} Uhr`;
        document.getElementById("guest-link-share").hidden =
            typeof navigator.share !== "function";
        renderGuestLinkQr(result.url);
        addEvent("success", `Gastlink „${result.link.label}“ erstellt`);
        loadGuestLinks();
    } catch (error) {
        status.textContent = "Erstellen fehlgeschlagen: " + error.message;
    }
}

async function copyGuestLink() {
    const input = document.getElementById("guest-link-url");
    try {
        await navigator.clipboard.writeText(createdGuestLinkUrl);
        addEvent("info", "Gastlink kopiert");
    } catch (error) {
        input.select();
        document.execCommand?.("copy");
    }
}

async function shareGuestLink() {
    try {
        await navigator.share({
            title: "Open BOS Stream – Livebilder",
            text: "Gastzugang zu den Livebildern",
            url: createdGuestLinkUrl,
        });
    } catch (error) {
        // Teilen abgebrochen: nichts zu tun.
    }
}

async function loadGuestLinks() {
    const list = document.getElementById("guest-link-list");
    if (!list) {
        return;
    }
    try {
        const result = await api.get("/guest-links");
        const links = result.links ?? [];
        if (links.length === 0) {
            list.innerHTML =
                '<p class="service-inline-status">Noch keine Gastlinks.</p>';
            return;
        }
        list.innerHTML = links.map(link => {
            const state = link.revoked_at
                ? `gesperrt ${formatGuestLinkTime(link.revoked_at)}` +
                    (link.revoked_by ? ` von ${escapeHTML(link.revoked_by)}` : "")
                : link.active
                    ? `gültig bis ${formatGuestLinkTime(link.expires_at)}`
                    : `abgelaufen ${formatGuestLinkTime(link.expires_at)}`;
            return `
                <div class="guest-link-row ${link.active ? "" : "is-inactive"}">
                    <div>
                        <strong>${escapeHTML(link.label)}</strong>
                        <small>${escapeHTML(
                            link.sources.map(source => source.name).join(", ")
                        )}</small>
                        <small>
                            ${state} · erstellt von ${escapeHTML(link.created_by)}
                            · zuletzt genutzt ${formatGuestLinkTime(link.last_used_at)}
                        </small>
                    </div>
                    ${link.active ? `
                        <button class="bos-button bos-button-small bos-button-red"
                            type="button" data-revoke-guest-link="${escapeHTML(link.id)}">
                            Sperren
                        </button>
                    ` : ""}
                </div>
            `;
        }).join("");
    } catch (error) {
        list.innerHTML = `<p class="service-inline-status">${
            escapeHTML("Gastlinks konnten nicht geladen werden: " + error.message)
        }</p>`;
    }
}

async function revokeGuestLink(linkId) {
    if (!window.confirm(
        "Gastlink sperren? Laufende Gastansichten werden beendet."
    )) {
        return;
    }
    try {
        await api.request(`/guest-links/${encodeURIComponent(linkId)}`, {
            method: "DELETE",
        });
        addEvent("success", "Gastlink gesperrt");
    } catch (error) {
        addEvent("error", "Gastlink konnte nicht gesperrt werden: " + error.message);
    }
    loadGuestLinks();
}

document.addEventListener("DOMContentLoaded", () => {
    document
        .getElementById("guest-link-form")
        ?.addEventListener("submit", submitGuestLink);
    document
        .getElementById("guest-link-list")
        ?.addEventListener("click", event => {
            const button = event.target.closest("[data-revoke-guest-link]");
            if (button) {
                revokeGuestLink(button.dataset.revokeGuestLink);
            }
        });
    loadGuestLinks();
});
