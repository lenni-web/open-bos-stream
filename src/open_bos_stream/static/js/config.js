let currentConfig = null;

let availableEncoders = [];

let configDirty = false;

function setConfigDirty(dirty) {
    configDirty = dirty;

    const indicator =
        document.getElementById(
            "config-dirty-indicator"
        );

    if (!indicator) {
        return;
    }

    indicator.textContent = dirty
        ? "Ungespeicherte Änderungen"
        : "Keine ungespeicherten Änderungen";

    indicator.classList.toggle(
        "is-dirty",
        dirty
    );
}

function setConfigSaveStatus(message, type = "") {
    const status =
        document.getElementById(
            "config-save-status"
        );

    if (!status) {
        return;
    }

    status.textContent = message;
    status.className =
        "save-status" +
        (type ? ` is-${type}` : "");
}

function bindConfigChangeTracking() {
    const settings =
        document.getElementById(
            "settings-content"
        );

    if (!settings || settings.dataset.trackingBound) {
        return;
    }

    settings.dataset.trackingBound = "true";

    settings.addEventListener(
        "input",
        event => {
            if (
                event.target.id?.startsWith(
                    "cfg-display-"
                )
                || event.target.id === "cfg-recording-automatic"
                || event.target.id?.startsWith("cfg-storage-")
            ) {
                return;
            }

            setConfigDirty(true);
            setConfigSaveStatus("");
        }
    );
}

async function loadEncoders(
    forceSelection = false,
) {

    if (!currentConfig) {
        return;
    }

    availableEncoders =
        await api.encoders(
            currentConfig.input,
        );

    selectDefaultEncoder(
        forceSelection,
    );

    updateEncoderSelect();

}

async function refreshConfig() {

    try {

        currentConfig =

            await api.config();

        await loadInputTypes();

        await loadSourceEncoders();

        loadStreamConfig();

        renderStreamOutputs();

        renderSources();

        renderMediaCaptureConfig();

        renderStorageSettings();

        setConfigDirty(false);
        setConfigSaveStatus("");

    }

    catch (err) {

        console.error(
            "Config:",
            err
        );

    }

}

async function saveConfig() {
    const button =
        document.getElementById(
            "config-save-button"
        );

    try {
        if (button) {
            button.disabled = true;
            button.textContent =
                "Wird gespeichert …";
        }

        setConfigSaveStatus(
            "Konfiguration wird geprüft und aktiviert. " +
            "Das kann einige Sekunden dauern …"
        );

        saveStreamConfig();

        saveStreamOutputs();
        saveSources();
        saveMediaCaptureConfig();

        const result = window.currentUser?.role === "superadmin"
            ? await api.saveConfig(currentConfig)
            : await api.saveSources(currentConfig.sources);

        await refreshConfig();

        setConfigDirty(false);
        setConfigSaveStatus(
            result.message,
            "success"
        );

        addEvent(
            "success",
            "⚙️ " + result.message
        );

    }

    catch (err) {

        console.error(
            "Config:",
            err
        );

        setConfigSaveStatus(
            err.message,
            "error"
        );

        addEvent(
            "error",
            "⚙️ " + err.message
        );

    } finally {
        if (button) {
            button.disabled = false;
            button.textContent =
                "Änderungen speichern";
        }
    }

}

function collectConfigForm() {
    saveStreamConfig();
    saveStreamOutputs();
    saveSources();
    saveMediaCaptureConfig();
}

function renderMediaCaptureConfig() {
    const select = document.getElementById("cfg-media-source");
    if (!select || !currentConfig) {
        return;
    }
    const sources = (currentConfig.sources ?? []).filter(
        source => source.enabled
    );
    select.innerHTML = sources.length
        ? sources.map(source => `
            <option value="${escapeHTML(source.id)}">
                ${escapeHTML(source.name)}
            </option>
        `).join("")
        : '<option value="">Keine aktive Quelle</option>';

    const selected = currentConfig.media_capture?.source_id;
    if (selected && sources.some(source => source.id === selected)) {
        select.value = selected;
    } else {
        select.value = sources[0]?.id ?? "";
    }

    const automatic = document.getElementById(
        "cfg-recording-automatic"
    );
    if (automatic) {
        automatic.checked = (
            currentConfig.media_capture?.recording_mode === "automatic"
        );
        if (!automatic.dataset.immediateSaveBound) {
            automatic.dataset.immediateSaveBound = "true";
            automatic.addEventListener(
                "change",
                () => saveRecordingModeImmediately()
            );
        }
    }
}

function renderStorageSettings() {
    const storage = currentConfig?.storage ?? {};
    const warning = document.getElementById("cfg-storage-warning");
    const minimum = document.getElementById("cfg-storage-minimum");
    const cleanup = document.getElementById("cfg-storage-auto-cleanup");
    if (!warning || !minimum || !cleanup) {
        return;
    }
    warning.value = storage.warning_free_percent ?? 15;
    minimum.value = storage.minimum_free_percent ?? 5;
    cleanup.checked = Boolean(storage.auto_cleanup);
}

async function saveStorageSettings() {
    const warning = document.getElementById("cfg-storage-warning");
    const minimum = document.getElementById("cfg-storage-minimum");
    const cleanup = document.getElementById("cfg-storage-auto-cleanup");
    const button = document.getElementById("cfg-storage-save");
    const status = document.getElementById("cfg-storage-status");
    if (!warning || !minimum || !cleanup || !currentConfig) {
        return;
    }

    const payload = {
        warning_free_percent: Number(warning.value),
        minimum_free_percent: Number(minimum.value),
        auto_cleanup: cleanup.checked,
    };
    if (payload.minimum_free_percent >= payload.warning_free_percent) {
        if (status) {
            status.textContent =
                "Die Mindestgrenze muss unter der Warnschwelle liegen.";
        }
        return;
    }

    if (button) button.disabled = true;
    if (status) status.textContent = "Wird gespeichert …";
    try {
        const result = await api.saveStorage(payload);
        currentConfig.storage = result.storage;
        renderStorageSettings();
        if (status) {
            status.textContent = result.storage.auto_cleanup
                ? "Gespeichert. Älteste Medien werden bei Speichermangel gelöscht."
                : "Gespeichert. Bei Speichermangel werden neue Medien gesperrt.";
        }
        addEvent("success", "▤ " + result.message);
    } catch (err) {
        renderStorageSettings();
        if (status) {
            status.textContent = "Speichern fehlgeschlagen: " + err.message;
        }
        addEvent("error", "▤ " + err.message);
    } finally {
        if (button) button.disabled = false;
    }
}

async function saveRecordingModeImmediately() {
    const automatic = document.getElementById(
        "cfg-recording-automatic"
    );
    const source = document.getElementById("cfg-media-source");
    const status = document.getElementById(
        "cfg-recording-mode-status"
    );
    if (!automatic || !source || !currentConfig) {
        return;
    }

    const previous = currentConfig.media_capture?.recording_mode ?? "manual";
    const payload = {
        source_id: source.value || null,
        recording_mode: automatic.checked ? "automatic" : "manual",
    };

    automatic.disabled = true;
    if (status) status.textContent = "Wird gespeichert …";
    try {
        const result = await api.saveMediaCapture(payload);
        currentConfig.media_capture = result.media_capture;
        automatic.checked = (
            result.media_capture.recording_mode === "automatic"
        );
        if (status) {
            status.textContent = automatic.checked
                ? "Automatische Aufnahme ist aktiv."
                : "Manuelle Aufnahme ist aktiv.";
        }
        addEvent("success", "⏺ " + result.message);
    } catch (err) {
        automatic.checked = previous === "automatic";
        if (status) {
            status.textContent = "Speichern fehlgeschlagen: " + err.message;
        }
        addEvent("error", "⏺ " + err.message);
    } finally {
        automatic.disabled = false;
    }
}

function saveMediaCaptureConfig() {
    const select = document.getElementById("cfg-media-source");
    if (!select || !currentConfig) {
        return;
    }
    currentConfig.media_capture = {
        source_id: select.value || null,
        recording_mode: document.getElementById(
            "cfg-recording-automatic"
        )?.checked ? "automatic" : "manual",
    };
}

async function testConfig() {
    const button =
        document.getElementById("config-test-button");

    try {
        if (button) {
            button.disabled = true;
            button.textContent = "Wird geprüft …";
        }
        collectConfigForm();
        const result = await api.testConfig(currentConfig);
        setConfigSaveStatus(
            `${result.message} ${result.checks.join(" · ")}`,
            "success"
        );
    } catch (err) {
        setConfigSaveStatus(err.message, "error");
    } finally {
        if (button) {
            button.disabled = false;
            button.textContent = "Konfiguration testen";
        }
    }
}

async function restoreConfig() {
    const confirmed = window.confirm(
        "Die letzte funktionierende Konfiguration " +
        "wiederherstellen und aktivieren?"
    );
    if (!confirmed) {
        return;
    }

    try {
        setConfigSaveStatus(
            "Wiederherstellung läuft …"
        );
        const result = await api.restoreConfig();
        await refreshConfig();
        setConfigSaveStatus(result.message, "success");
    } catch (err) {
        setConfigSaveStatus(err.message, "error");
    }
}

function updateEncoderSelect() {

    const select =

        document.getElementById(
            "cfg-encoder-codec"
        );

    if (!select) {
        return;
    }

    select.innerHTML = "";

    availableEncoders.forEach(

        encoder => {

            const option =

                document.createElement(
                    "option"
                );

            option.value =
                encoder.codec;

            option.textContent =
                encoder.name;

            option.disabled =
                !encoder.available;

            select.appendChild(
                option
            );

        }

    );

}

function findEncoder(codec) {

    return availableEncoders.find(

        encoder =>

            encoder.codec === codec &&

            encoder.available

    );

}

function preferredEncoders(
    inputType,
) {

    switch (inputType) {

        case "rtmp":
        case "rtsp":
        case "srt":

            return [
                "copy",
                "libx264",
                "h264_v4l2m2m",
                "libx265",
            ];

        default:

            return [
                "h264_v4l2m2m",
                "libx264",
                "libx265",
                "copy",
            ];
    }

}

function selectDefaultEncoder(
    force = false,
) {

    //
    // Benutzerwahl beibehalten,
    // solange der Encoder noch verfügbar ist.
    //
    if (

        !force &&

        currentConfig.encoder.codec &&

        findEncoder(
            currentConfig.encoder.codec
        )

    ) {

        return;

    }

    const preferred =
        preferredEncoders(
            currentConfig.input.type,
        );

    for (const codec of preferred) {

        const encoder =
            findEncoder(codec);

        if (encoder) {

            currentConfig.encoder.codec =
                encoder.codec;

            return;

        }

    }

    if (availableEncoders.length > 0) {

        currentConfig.encoder.codec =
            availableEncoders[0].codec;

    }

}

bindConfigChangeTracking();
