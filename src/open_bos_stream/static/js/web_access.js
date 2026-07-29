let webAccessConfig = null;

function webAccessUrl(port) {
    const host = window.location.hostname;
    return `http://${host}${port === 80 ? "" : `:${port}`}`;
}

async function loadWebAccessConfig() {
    try {
        webAccessConfig = await api.webAccessConfig();
        const toggle = document.getElementById("cfg-web-access-enabled");
        if (toggle) {
            toggle.checked = webAccessConfig.enabled;
        }
        await refreshWebAccessStatus();
    } catch (error) {
        console.error("Webzugriff:", error);
    }
}

async function refreshWebAccessStatus() {
    const inline = document.getElementById("web-access-status");
    const systemText = document.getElementById("system-web-access");
    const systemCard = document.getElementById("service-card-web-access");

    try {
        const status = await api.webAccessStatus();
        let text;
        let state;

        if (status.running) {
            text = `🟢 Aktiv: ${webAccessUrl(status.standard_port)}`;
            state = "is-online";
        } else if (status.error) {
            text = `🔴 ${status.error}`;
            state = "is-offline";
        } else {
            text = `⚪ Aus – erreichbar über ${webAccessUrl(status.fallback_port)}`;
            state = "";
        }

        if (inline) inline.textContent = text;
        if (systemText) systemText.textContent = text.replace(/^[🟢🔴⚪]\s*/, "");
        if (systemCard) {
            systemCard.classList.remove("is-online", "is-offline");
            if (state) systemCard.classList.add(state);
        }
    } catch (error) {
        if (inline) inline.textContent = "🔴 Webzugriff-Status nicht verfügbar";
        if (systemText) systemText.textContent = "Status nicht verfügbar";
        if (systemCard) systemCard.classList.add("is-offline");
    }
}

async function saveWebAccessConfig() {
    const button = document.getElementById("web-access-save-button");
    const candidate = {
        enabled: document.getElementById("cfg-web-access-enabled").checked,
    };

    try {
        if (button) {
            button.disabled = true;
            button.textContent = "Wird übernommen …";
        }
        const result = await api.saveWebAccessConfig(candidate);
        webAccessConfig = candidate;
        if (currentConfig) currentConfig.web_access = candidate;
        addEvent("success", "🌐 " + result.message);
    } catch (error) {
        addEvent("error", "🌐 " + error.message);
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = "Webzugriff übernehmen";
        }
        await loadWebAccessConfig();
    }
}
