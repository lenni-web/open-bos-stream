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

        const result = await api.saveConfig(
            currentConfig
        );

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
