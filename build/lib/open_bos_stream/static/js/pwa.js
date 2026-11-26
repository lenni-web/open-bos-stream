// ==========================================================
// Installation als App (PWA): Hinweis und Anleitung
// ==========================================================

const PWA_HINT_NEVER_KEY = "openBosInstallHintNever";
const PWA_HINT_LATER_KEY = "openBosInstallHintLater";
const PWA_HINT_LATER_MS = 7 * 24 * 60 * 60 * 1000;

let deferredInstallPrompt = null;

function pwaStorageGet(key) {
    try {
        return localStorage.getItem(key);
    } catch (error) {
        return null;
    }
}

function pwaStorageSet(key, value) {
    try {
        localStorage.setItem(key, value);
    } catch (error) {
        // Ohne Speicher erscheint der Hinweis beim nächsten Laden erneut.
    }
}

function isInstalledApp() {
    return (
        window.matchMedia?.("(display-mode: standalone)").matches ||
        window.matchMedia?.("(display-mode: fullscreen)").matches ||
        window.navigator.standalone === true
    );
}

function detectPlatform() {
    const agent = navigator.userAgent || "";
    // iPadOS meldet sich als Mac, hat aber einen Touchscreen.
    const iOS = /iPad|iPhone|iPod/.test(agent) ||
        (/Macintosh/.test(agent) && navigator.maxTouchPoints > 1);
    if (iOS) {
        return "ios";
    }
    if (/Android/i.test(agent)) {
        return "android";
    }
    return "desktop";
}

function renderInstallDialog() {
    const dialog = document.getElementById("pwa-install-dialog");
    if (!dialog) {
        return;
    }
    const platform = detectPlatform();
    const installed = isInstalledApp();
    dialog.querySelectorAll(".pwa-install-guide").forEach(section => {
        const own = section.dataset.platform === platform;
        section.classList.toggle("is-current", own);
        // Eigene Anleitung zuerst, die übrigen darunter.
        if (own) {
            section.parentElement.insertBefore(
                section,
                dialog.querySelector(".pwa-install-guide")
            );
        }
    });
    document.getElementById("pwa-installed-note").hidden = !installed;
    document.getElementById("pwa-install-button").hidden =
        installed || !deferredInstallPrompt;
}

function openInstallDialog() {
    const dialog = document.getElementById("pwa-install-dialog");
    if (!dialog) {
        return;
    }
    renderInstallDialog();
    if (typeof dialog.showModal === "function") {
        dialog.showModal();
    } else {
        dialog.setAttribute("open", "");
    }
}

async function promptInstall() {
    if (!deferredInstallPrompt) {
        return;
    }
    const promptEvent = deferredInstallPrompt;
    deferredInstallPrompt = null;
    promptEvent.prompt();
    try {
        await promptEvent.userChoice;
    } finally {
        renderInstallDialog();
    }
}

function dismissInstallHint(forever) {
    pwaStorageSet(
        forever ? PWA_HINT_NEVER_KEY : PWA_HINT_LATER_KEY,
        forever ? "true" : String(Date.now())
    );
    const hint = document.getElementById("pwa-install-hint");
    if (hint) {
        hint.hidden = true;
    }
}

function shouldShowInstallHint() {
    if (isInstalledApp() || detectPlatform() === "desktop") {
        return false;
    }
    if (pwaStorageGet(PWA_HINT_NEVER_KEY) === "true") {
        return false;
    }
    const later = Number(pwaStorageGet(PWA_HINT_LATER_KEY));
    return !later || Date.now() - later > PWA_HINT_LATER_MS;
}

function initInstallHint() {
    const menuEntry = document.getElementById("pwa-menu-entry");
    if (menuEntry && isInstalledApp()) {
        // In der installierten App ist der Menüeintrag überflüssig.
        menuEntry.hidden = true;
    }
    const hint = document.getElementById("pwa-install-hint");
    if (hint) {
        hint.hidden = !shouldShowInstallHint();
    }
}

// Chrome, Edge und Samsung Internet bieten einen eigenen Installationsdialog.
window.addEventListener("beforeinstallprompt", event => {
    event.preventDefault();
    deferredInstallPrompt = event;
    renderInstallDialog();
});

window.addEventListener("appinstalled", () => {
    deferredInstallPrompt = null;
    pwaStorageSet(PWA_HINT_NEVER_KEY, "true");
    const hint = document.getElementById("pwa-install-hint");
    if (hint) {
        hint.hidden = true;
    }
    renderInstallDialog();
});

document.addEventListener("DOMContentLoaded", initInstallHint);
