// ==========================================================
// App-Rahmen: Seitenleiste, Kopfzeile, Status und Darstellung
// ==========================================================

const SIDEBAR_STORAGE_KEY = "openBosSidebarCollapsed";

function readStoredFlag(key) {
    try {
        return localStorage.getItem(key) === "true";
    } catch (error) {
        return false;
    }
}

function storeFlag(key, value) {
    try {
        localStorage.setItem(key, String(value));
    } catch (error) {
        // Ohne Speicher gilt die Einstellung nur bis zum Neuladen.
    }
}

// ----------------------------------------------------------
// Seitenleiste
// ----------------------------------------------------------

function setSidebarCollapsed(collapsed) {
    const shell = document.getElementById("app-shell");
    const button = document.getElementById("sidebar-collapse");
    if (!shell) {
        return;
    }
    shell.classList.toggle("is-sidebar-collapsed", collapsed);
    if (button) {
        const label = collapsed
            ? "Seitenleiste ausklappen"
            : "Seitenleiste einklappen";
        button.setAttribute("aria-pressed", String(collapsed));
        button.setAttribute("aria-label", label);
        button.title = label;
        const text = button.querySelector(".nav-label");
        if (text) {
            text.textContent = collapsed ? "Ausklappen" : "Einklappen";
        }
    }
    // Karte und Videos passen sich an die neue Breite an.
    window.dispatchEvent(new Event("resize"));
}

function initSidebar() {
    setSidebarCollapsed(readStoredFlag(SIDEBAR_STORAGE_KEY));
    document
        .getElementById("sidebar-collapse")
        ?.addEventListener("click", () => {
            const collapsed = !document
                .getElementById("app-shell")
                .classList.contains("is-sidebar-collapsed");
            setSidebarCollapsed(collapsed);
            storeFlag(SIDEBAR_STORAGE_KEY, collapsed);
        });
}

// ----------------------------------------------------------
// Seitentitel in der Kopfzeile
// ----------------------------------------------------------

function updateTopbarTitle(page) {
    const header = document.querySelector(`#page-${page} .page-header`);
    const title = header?.querySelector("h1")?.textContent?.trim();
    const eyebrow = header
        ?.querySelector(".page-eyebrow")
        ?.textContent
        ?.trim();
    const titleElement = document.getElementById("topbar-title");
    const eyebrowElement = document.getElementById("topbar-eyebrow");
    if (titleElement && title) {
        titleElement.textContent = title;
        document.title = `${title} · Open BOS Stream`;
    }
    if (eyebrowElement) {
        eyebrowElement.textContent = eyebrow || "";
    }
}

// ----------------------------------------------------------
// Aufklappfenster (Status, Benutzer)
// ----------------------------------------------------------

function closePopovers(except = null) {
    document.querySelectorAll(".app-popover").forEach(panel => {
        if (panel === except) {
            return;
        }
        panel.hidden = true;
        document
            .querySelector(`[aria-controls="${panel.id}"]`)
            ?.setAttribute("aria-expanded", "false");
    });
}

function bindPopover(buttonId, panelId) {
    const button = document.getElementById(buttonId);
    const panel = document.getElementById(panelId);
    if (!button || !panel) {
        return;
    }
    button.addEventListener("click", event => {
        event.stopPropagation();
        const open = panel.hidden;
        closePopovers(panel);
        panel.hidden = !open;
        button.setAttribute("aria-expanded", String(open));
    });
    panel.addEventListener("click", event => {
        if (event.target.closest("[data-close-popover]")) {
            closePopovers();
            return;
        }
        event.stopPropagation();
    });
}

// ----------------------------------------------------------
// Smartphone: „Mehr“-Menü für weitere Bereiche
// ----------------------------------------------------------

function closeMoreSheet() {
    const sheet = document.getElementById("app-more-sheet");
    if (sheet) {
        sheet.hidden = true;
    }
    document.getElementById("nav-more")?.setAttribute("aria-expanded", "false");
}

function initMoreSheet() {
    const button = document.getElementById("nav-more");
    const sheet = document.getElementById("app-more-sheet");
    if (!button || !sheet) {
        return;
    }
    button.addEventListener("click", event => {
        event.stopPropagation();
        const open = sheet.hidden;
        closePopovers();
        sheet.hidden = !open;
        button.setAttribute("aria-expanded", String(open));
    });
    sheet.addEventListener("click", event => event.stopPropagation());
    document.addEventListener("click", closeMoreSheet);
    document.addEventListener("keydown", event => {
        if (event.key === "Escape") {
            closeMoreSheet();
        }
    });
    // Beim Wechsel auf Tablet- oder Desktop-Breite nicht offen stehen lassen.
    window.matchMedia("(min-width: 769px)").addEventListener?.("change", closeMoreSheet);
}

function initPopovers() {
    bindPopover("status-button", "status-panel");
    bindPopover("user-button", "user-panel");
    document.addEventListener("click", () => closePopovers());
    document.addEventListener("keydown", event => {
        if (event.key === "Escape") {
            closePopovers();
        }
    });
}

// ----------------------------------------------------------
// Darstellung (Hell / Dunkel / Automatisch)
// ----------------------------------------------------------

function syncThemeSwitch() {
    const choice = window.OpenBosTheme?.preference() ?? "auto";
    document.querySelectorAll("[data-theme-choice]").forEach(button => {
        button.setAttribute(
            "aria-checked",
            String(button.dataset.themeChoice === choice)
        );
    });
}

function initThemeSwitch() {
    document.querySelectorAll("[data-theme-choice]").forEach(button => {
        button.addEventListener("click", () => {
            window.OpenBosTheme?.set(button.dataset.themeChoice);
        });
    });
    document.addEventListener("open-bos:theme", syncThemeSwitch);
    syncThemeSwitch();
}

// ----------------------------------------------------------
// Statusanzeige
// ----------------------------------------------------------

function formatPercent(value) {
    if (!Number.isFinite(value)) {
        return "—";
    }
    return value > 0
        ? `${value.toFixed(1).replace(".", ",")} %`
        : "< 0,1 %";
}

function updateShellStatus(services, system) {
    if (!services) {
        return;
    }
    const online = Boolean(services.mediamtx?.online);
    const dot = document.getElementById("status-dot");
    const label = document.getElementById("status-label");
    if (dot) {
        dot.classList.toggle("is-ok", online);
        dot.classList.toggle("is-error", !online);
    }
    if (label) {
        label.textContent = online ? "Einsatzbereit" : "Störung";
    }
    document
        .getElementById("status-button")
        ?.classList.toggle("is-error", !online);

    updateValue(
        "status-mediamtx",
        online ? "Erreichbar" : "Nicht erreichbar"
    );
    if (!system) {
        return;
    }
    updateValue("status-cpu", formatPercent(system.cpu));
    updateValue("status-ram", formatPercent(system.ram));

    const hasTemperature = Number.isFinite(system.temperature);
    const temperatureRow = document.getElementById("status-temp-row");
    if (temperatureRow) {
        temperatureRow.hidden = !hasTemperature;
    }
    if (hasTemperature) {
        updateValue(
            "status-temp",
            `${system.temperature.toFixed(1).replace(".", ",")} °C`
        );
    }
}

document.addEventListener("DOMContentLoaded", () => {
    initSidebar();
    initPopovers();
    initMoreSheet();
    initThemeSwitch();
});
