"use strict";

// Seite für DJI Pilot 2: anmelden, Lizenz prüfen, MQTT-Modul laden.
// window.djiBridge gibt es nur in der Webansicht von Pilot 2. Antworten sind
// Text mit JSON: {code: 0 = Erfolg, message, data}.

const djiStatus = document.getElementById("dji-status");
const djiForm = document.getElementById("dji-login");
const djiRetry = document.getElementById("dji-retry");

function djiLog(text) {
    const entry = document.createElement("li");
    entry.textContent = `${new Date().toLocaleTimeString("de-DE")} ${text}`;
    document.getElementById("dji-log").appendChild(entry);
}

function djiShow(text, error = false) {
    djiStatus.textContent = text;
    djiStatus.classList.toggle("is-error", error);
    djiLog(text);
}

// Ruft eine Funktion der Bridge auf; Zugangsdaten werden nie protokolliert.
function djiCall(name, ...args) {
    const raw = window.djiBridge[name](...args);
    let result = raw;
    try {
        result = JSON.parse(raw);
    } catch (error) {
        // Manche Funktionen liefern reinen Text.
    }
    if (result && typeof result === "object" && "code" in result && result.code !== 0) {
        throw new Error(`${name}: ${result.message || result.code}`);
    }
    djiLog(`${name}: in Ordnung`);
    return result && typeof result === "object" && "data" in result ? result.data : result;
}

// Wird von Pilot nach dem Verbindungsaufbau aufgerufen.
window.openBosDjiConnect = connected => {
    if (connected === true || connected === "true") {
        djiShow("Verbunden. Die Drohne meldet ihre Daten an den Server.");
    } else {
        djiShow("Verbindung zum Server unterbrochen oder abgelehnt.", true);
    }
};

async function djiConnect() {
    djiRetry.hidden = true;
    const response = await fetch("/api/dji/pilot-config", {cache: "no-store", credentials: "same-origin"});
    if (response.status === 401) {
        djiForm.hidden = false;
        djiShow("Bitte mit dem eigenen Konto anmelden.");
        return;
    }
    const config = await response.json();
    if (!response.ok) {
        throw new Error(config.detail || `Fehler ${response.status}`);
    }
    djiForm.hidden = true;
    if (!window.djiBridge) {
        djiShow("Diese Seite bitte in DJI Pilot 2 unter „Cloud-Dienste“ öffnen.", true);
        return;
    }
    djiCall("platformVerifyLicense", config.app_id, config.app_key, config.license);
    djiCall("platformSetWorkspaceId", config.workspace_id);
    djiCall("platformSetInformation", config.platform_name, config.workspace_name, "Open BOS Drohnen");
    djiShow(`Verbindung zu ${config.mqtt.host} wird aufgebaut …`);
    djiCall("platformLoadComponent", "thing", JSON.stringify({
        host: config.mqtt.host,
        username: config.mqtt.username,
        password: config.mqtt.password,
        connectCallback: "openBosDjiConnect",
    }));
    djiRetry.hidden = false;
}

function djiStart() {
    djiConnect().catch(error => {
        djiShow(error.message, true);
        djiRetry.hidden = false;
    });
}

djiForm.addEventListener("submit", async event => {
    event.preventDefault();
    try {
        const response = await fetch("/auth/login", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                username: document.getElementById("dji-username").value,
                password: document.getElementById("dji-password").value,
            }),
        });
        const payload = await response.json();
        if (!response.ok) {
            throw new Error(typeof payload.detail === "string" ? payload.detail : "Anmeldung fehlgeschlagen.");
        }
        document.getElementById("dji-password").value = "";
        djiStart();
    } catch (error) {
        djiShow(error.message, true);
    }
});

djiRetry.addEventListener("click", () => {
    if (window.djiBridge) {
        try {
            window.djiBridge.platformUnloadComponent("thing");
        } catch (error) {
            djiLog(error.message);
        }
    }
    djiStart();
});

djiStart();
