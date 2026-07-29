let displayConfig = null;

function applyDisplayCursorMode() {
    const params =
        new URLSearchParams(
            window.location.search
        );

    if (params.get("display") === "1") {
        document.documentElement.classList.add(
            "display-mode"
        );
    }
}

async function loadDisplayConfig() {
    try {
        displayConfig =
            await api.displayConfig();

        document.getElementById(
            "cfg-display-mode"
        ).value = displayConfig.mode;

        document.getElementById(
            "cfg-display-dashboard-url"
        ).value = displayConfig.dashboard_url;

        document.getElementById(
            "cfg-display-stream-url"
        ).value = displayConfig.stream_url;

        document.getElementById(
            "cfg-display-hide-cursor"
        ).checked = displayConfig.hide_cursor;

        document.getElementById(
            "cfg-display-power"
        ).checked =
            displayConfig.disable_power_saving;

        document.getElementById(
            "cfg-display-enabled"
        ).checked = displayConfig.enabled;

        await refreshDisplayStatus();

    } catch (error) {
        console.error("Display:", error);
    }
}

async function refreshDisplayStatus() {
    const element =
        document.getElementById(
            "display-service-status"
        );

    if (!element) {
        return;
    }

    try {
        const status =
            await api.displayStatus();

        if (status.running) {
            element.textContent =
                `🟢 Display läuft (${status.mode})`;
        } else if (status.error) {
            element.textContent =
                `🔴 ${status.error}`;
        } else {
            element.textContent =
                "⚪ Display ist ausgeschaltet";
        }
    } catch (error) {
        element.textContent =
            "🔴 Display-Status nicht verfügbar";
    }
}

async function saveDisplayConfig() {
    const button =
        document.getElementById(
            "display-save-button"
        );

    const candidate = {
        ...displayConfig,
        enabled: document.getElementById(
            "cfg-display-enabled"
        ).checked,
        mode: document.getElementById(
            "cfg-display-mode"
        ).value,
        browser: "chromium",
        dashboard_url: document.getElementById(
            "cfg-display-dashboard-url"
        ).value,
        stream_url: document.getElementById(
            "cfg-display-stream-url"
        ).value,
        hide_cursor: document.getElementById(
            "cfg-display-hide-cursor"
        ).checked,
        disable_power_saving:
            document.getElementById(
                "cfg-display-power"
            ).checked,
    };

    try {
        if (button) {
            button.disabled = true;
            button.textContent =
                "Wird übernommen …";
        }

        const result =
            await api.saveDisplayConfig(
                candidate
            );
        displayConfig = candidate;

        if (currentConfig) {
            currentConfig.display = candidate;
        }

        addEvent("success", "🖥 " + result.message);
    } catch (error) {
        addEvent("error", "🖥 " + error.message);
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent =
                "Display übernehmen";
        }
    }

    await refreshDisplayStatus();
}

applyDisplayCursorMode();
