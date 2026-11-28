function sourceTypeMetadata(type) {
    return inputTypes.find(item => item.type === type) ?? null;
}

function sourceTypeOptions(selected) {
    return inputTypes.map(item => `
        <option
            value="${escapeHTML(item.type)}"
            ${item.type === selected ? "selected" : ""}>
            ${escapeHTML(item.name)}
        </option>
    `).join("");
}

// Profile mit Kurzerklärung; die Vorschau-Profile gibt es nur beim Empfang.
const SOURCE_PROFILES = [
    ["direct", "Direkt / Stream Copy",
        "Das Bild wird unverändert übernommen. Geringste Serverlast, " +
        "Standard für ein stabiles Signal."],
    ["copy_repair", "Copy mit Zeitstempel-Korrektur",
        "Ohne Neukodieren, repariert aber fehlerhafte Zeitstempel. " +
        "Bei Rucklern oder Aussetzern."],
    ["copy_repair_low_latency", "Copy-Reparatur · geringe Latenz",
        "Wie die Korrektur, mit kleinerem Puffer und weniger Verzögerung. " +
        "Für weitgehend stabile Signale."],
    ["preview_transcode", "Übersichts-Vorschau · ausgewogen (max. 480p)",
        "Übersicht mit 854×480, 12 fps und etwa 1,1 Mbit/s ohne Ton; " +
        "Vollbild zeigt den Originalstream. Für bis zu vier Drohnen."],
    ["preview_transcode_economy", "Übersichts-Vorschau · sparsam (max. 360p)",
        "Übersicht mit 640×360, 12 fps und etwa 800 kbit/s ohne Ton; " +
        "Vollbild zeigt den Originalstream. Für viele Drohnen oder " +
        "knappe Serverleistung."],
    ["transcode", "Transcodieren",
        "Der Server kodiert das Bild neu, mit eigenen Encoder-Werten. " +
        "Hohe Serverlast."],
    ["transcode_low_latency", "Transcodieren · geringe Latenz (Mobilfunk)",
        "Neukodieren mit einem Schlüsselbild pro Sekunde: schnell wieder " +
        "ein Bild nach Paketverlust. Hohe Serverlast."],
];

// Versteckte Empfangsprofile gelten nur für den RTMP-/SRT-Empfang.
function isHiddenProfile(value, sourceType) {
    return sourceType === "rtmp" &&
        (currentConfig?.hidden_source_profiles ?? []).includes(value);
}

// Kreis-Admins und Superadmins sehen auch versteckte Profile (markiert),
// alle anderen nur freigegebene und das bereits gewählte.
function sourceProfiles(sourceType, selected) {
    const all = Boolean(window.currentPermissions?.server_admin);
    return SOURCE_PROFILES.filter(([value]) => (
        (!value.startsWith("preview_") || sourceType === "rtmp") &&
        (all || value === selected || !isHiddenProfile(value, sourceType))
    )).map(([value, label, text]) => [
        value,
        isHiddenProfile(value, sourceType) ? `${label} (versteckt)` : label,
        text,
    ]);
}

// Vorbelegung für neue Drohnen: das erste freigegebene Profil.
function defaultSourceProfile(sourceType) {
    const released = SOURCE_PROFILES.find(
        ([value]) => !isHiddenProfile(value, sourceType)
    );
    return released?.[0] ?? "direct";
}

function sourceProfileOptions(selected, sourceType) {
    return sourceProfiles(sourceType, selected).map(([value, label]) => `
        <option
            value="${value}"
            ${value === selected ? "selected" : ""}>
            ${label}
        </option>
    `).join("");
}

function sourceProfileHelp(selected, sourceType) {
    return `
        <dl class="source-profile-help">
            ${sourceProfiles(sourceType, selected).map(([value, label, text]) => `
                <div class="${value === selected ? "is-selected" : ""}">
                    <dt>${label}</dt>
                    <dd>${text}</dd>
                </div>
            `).join("")}
        </dl>
    `;
}

// Einstellungen → „Empfangsprofile“: Haken = freigegeben.
function renderSourceProfileRelease() {
    const list = document.getElementById("source-profile-release");
    if (!list || !currentConfig) {
        return;
    }
    const hidden = currentConfig.hidden_source_profiles ?? [];
    list.innerHTML = SOURCE_PROFILES.map(([value, label, text]) => `
        <label class="switch-row">
            <input type="checkbox" value="${value}"
                ${hidden.includes(value) ? "" : "checked"}>
            <span>
                <strong>${label}</strong>
                <small>${text}</small>
            </span>
        </label>
    `).join("");
}

async function saveSourceProfileRelease() {
    const button = document.getElementById("source-profile-release-save");
    const status = document.getElementById("source-profile-release-status");
    const hidden = Array.from(document.querySelectorAll(
        "#source-profile-release input:not(:checked)"
    )).map(input => input.value);
    if (hidden.length === SOURCE_PROFILES.length) {
        status.textContent = "Mindestens ein Profil muss freigegeben bleiben.";
        return;
    }
    button.disabled = true;
    status.textContent = "Wird gespeichert …";
    try {
        const result = await api.put("/config/source-profiles", {hidden});
        // Ungespeicherte Eingaben auf der Drohnenseite behalten.
        saveSources();
        currentConfig.hidden_source_profiles = result.hidden;
        renderSources();
        renderSourceProfileRelease();
        status.textContent = "Gespeichert.";
    } catch (error) {
        status.textContent = "Speichern fehlgeschlagen: " + error.message;
    } finally {
        button.disabled = false;
    }
}

function generatePublisherToken() {
    const alphabet =
        "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
    const limit = Math.floor(256 / alphabet.length) * alphabet.length;
    let token = "";
    while (token.length < 12) {
        const bytes = new Uint8Array(16);
        window.crypto.getRandomValues(bytes);
        bytes.forEach(value => {
            if (value < limit && token.length < 12) {
                token += alphabet[value % alphabet.length];
            }
        });
    }
    return token;
}

function sourcePublishUrl(source) {
    const host = window.location.hostname || "<Server-IP>";
    if (source.ingest_protocol === "srt") {
        // MediaMTX: streamid=publish:<pfad>:<query>; der Token steht in der
        // Query. latency in Mikrosekunden (FFmpeg/libsrt), hier 400 ms.
        const token = source.publish_token
            ? `:token=${encodeURIComponent(source.publish_token)}`
            : "";
        return `srt://${host}:8890?streamid=publish:${source.id}${token}` +
            "&latency=400000&pkt_size=1316";
    }
    const base = `rtmp://${host}:1935/${source.id}`;
    if (source.publish_token) {
        return `${base}?token=${encodeURIComponent(source.publish_token)}`;
    }
    return base;
}

function sourceEncoderOptions(source, selected) {
    const encoders = (
        sourceEncodersByType.get(source.type) ?? availableEncoders
    ).filter(
        encoder => encoder.available && encoder.codec !== "copy"
    );
    return encoders.map(encoder => `
        <option value="${escapeHTML(encoder.codec)}"
            ${encoder.codec === selected ? "selected" : ""}>
            ${escapeHTML(encoder.name)}
        </option>
    `).join("");
}

function sourceTranscodingFields(source) {
    if (
        !["transcode", "transcode_low_latency"].includes(source.profile)
    ) {
        return "";
    }
    const encoder = currentConfig.encoder;
    const codec = source.codec ?? encoder.codec;
    return `
        <fieldset class="source-transcoding form-field-wide">
            <legend>Transcoding dieser Drohne</legend>
            <div class="form-grid">
                <div class="form-field">
                    <label>Encoder</label>
                    <select class="bos-input" data-field="codec">
                        ${sourceEncoderOptions(source, codec)}
                    </select>
                </div>
                <div class="form-field">
                    <label>Bitrate</label>
                    <input class="bos-input" data-field="bitrate"
                        value="${escapeHTML(source.bitrate ?? encoder.bitrate)}">
                </div>
                <div class="form-field">
                    <label>Pixelformat</label>
                    <input class="bos-input" data-field="pixel_format"
                        value="${escapeHTML(source.pixel_format ?? encoder.pixel_format)}">
                </div>
                <div class="form-field">
                    <label>GOP</label>
                    <input class="bos-input" data-field="gop" type="number"
                        min="1" value="${Number(source.gop ?? encoder.gop)}">
                </div>
                <div class="form-field">
                    <label>Preset</label>
                    <input class="bos-input" data-field="preset"
                        value="${escapeHTML(source.preset ?? encoder.preset)}">
                </div>
                <div class="form-field">
                    <label>Tune</label>
                    <input class="bos-input" data-field="tune"
                        value="${escapeHTML(source.tune ?? encoder.tune)}">
                </div>
            </div>
        </fieldset>
    `;
}

// Vorlagen für Drohnen-Controller, die selbst einen RTSP-Stream
// bereitstellen (Abholen statt Senden). Adressen ohne feste IP werden nur
// als Platzhalter vorgegeben; die genaue Adresse zeigt die Controller-App.
const RTSP_CONTROLLER_PRESETS = [
    {
        id: "dji-pilot2",
        label: "DJI Pilot 2 (RTSP)",
        placeholder:
            "rtsp://benutzer:passwort@<IP der Fernsteuerung>:8554/streaming/live/1",
        transport: "tcp",
        hint:
            "In DJI Pilot 2 unter Live-Stream „RTSP“ wählen, Benutzer und " +
            "Passwort festlegen (Port 8554). Die IP der Fernsteuerung steht " +
            "in den WLAN- bzw. Netzwerkeinstellungen. Senden per RTMP an den " +
            "Server ist bei DJI meist einfacher.",
    },
    {
        id: "parrot",
        label: "Parrot SkyController (Anafi USA/UKR)",
        url: "rtsp://192.168.53.1/live",
        transport: "udp",
        hint:
            "Netzwerkkabel von der LAN-Buchse des Pi zu einem USB-C-Ethernet-" +
            "Adapter am SkyController; " +
            "der Controller vergibt die Adresse selbst (Netzwerk-Skript: " +
            "Modus dhcp). Parrot erlaubt nur eine RTSP-Verbindung – Open BOS " +
            "Stream hält sie und verteilt das Bild weiter.",
    },
    {
        id: "skydio",
        label: "Skydio Enterprise Controller (X10)",
        placeholder: "rtsp://<IP des Controllers>:<Port>/<Streamname>",
        transport: "tcp",
        hint:
            "In der Skydio-App RTSP-Streaming aktivieren; die App zeigt die " +
            "Adresse an. Der Controller braucht eine Adresse aus dem Netzwerk " +
            "(Netzwerk-Skript: Modus share).",
    },
    {
        id: "autel",
        label: "Autel Smart Controller (EVO Max)",
        placeholder: "rtsp://<IP des Controllers>/<Pfad aus der App>",
        transport: "tcp",
        hint:
            "Die RTSP-Adresse zeigt die Autel-App unter Live-Stream. Autel " +
            "kann alternativ wie DJI direkt per RTMP an den Server senden.",
    },
];

function rtspPresetOptions() {
    return [
        `<option value="">Eigene Adresse</option>`,
        ...RTSP_CONTROLLER_PRESETS.map(preset => `
            <option value="${escapeHTML(preset.id)}">
                ${escapeHTML(preset.label)}
            </option>
        `),
    ].join("");
}

function applyRtspPreset(card, presetId) {
    const preset = RTSP_CONTROLLER_PRESETS.find(item => item.id === presetId);
    const hint = card.querySelector('[data-role="rtsp-preset-hint"]');
    if (!preset) {
        if (hint) {
            hint.textContent = RTSP_PRESET_DEFAULT_HINT;
        }
        return;
    }
    // Werte einer zuvor gewählten Vorlage ersetzen, eigene Eingaben behalten.
    const presetUrls = RTSP_CONTROLLER_PRESETS.map(item => item.url).filter(Boolean);
    const presetLabels = RTSP_CONTROLLER_PRESETS.map(item => item.label);
    const url = card.querySelector('[data-field="url"]');
    if (url) {
        url.type = "text";
        url.placeholder = preset.placeholder ?? preset.url ?? "";
        if (preset.url) {
            url.value = preset.url;
        } else if (presetUrls.includes(url.value.trim())) {
            url.value = "";
        }
        url.focus();
    }
    const transport = card.querySelector('[data-field="transport"]');
    if (transport) {
        transport.value = preset.transport;
    }
    // Weiterleiten ohne Neukodieren und mit minimalem Puffer.
    const profile = card.querySelector('[data-field="profile"]');
    if (profile) {
        profile.value = "copy_repair_low_latency";
    }
    const droneType = card.querySelector('[data-field="drone_type"]');
    if (
        droneType &&
        (!droneType.value.trim() || presetLabels.includes(droneType.value.trim()))
    ) {
        droneType.value = preset.label;
    }
    if (hint) {
        hint.textContent = preset.hint;
    }
    setConfigDirty(true);
}

const RTSP_PRESET_DEFAULT_HINT =
    "Für Controller, die selbst einen RTSP-Stream bereitstellen. Auf einem " +
    "Raspberry Pi vor Ort lässt sich das Bild so per SRT an den Server " +
    "weiterleiten.";

// Organisation (Wehr), der eine Quelle gehört. Wehr-Admins wählen eine
// ihrer Organisationen; Kreis-Admins dürfen auch ohne Zuordnung speichern
// (dann für alle Konten sichtbar).
function sourceOrganizationOptions() {
    if (typeof orgTree !== "function" || typeof orgState === "undefined" || !orgState.organizations.length) {
        return [];
    }
    return orgTree().filter(({org}) => org.can_admin && !org.archived);
}

function sourceOrganizationField(source) {
    const options = sourceOrganizationOptions();
    const serverAdmin = Boolean(window.currentPermissions?.server_admin);
    const names = window.organizationNames ?? {};
    const current = source.organization_id ?? null;
    const editable = serverAdmin || options.some(({org}) => org.id === current) ||
        current === null && !source.id;
    if (!options.length && !serverAdmin) {
        return "";
    }
    if (!editable && current !== null) {
        return `
            <div class="form-field">
                <label>Organisation</label>
                <input class="bos-input" value="${escapeHTML(names[current] ?? "?")}" disabled>
                <input type="hidden" data-field="organization_id" value="${current}">
                <small>Gehört zu einer anderen Organisation und wird dort verwaltet.</small>
            </div>
        `;
    }
    return `
        <div class="form-field">
            <label>Organisation</label>
            <select class="bos-input" data-field="organization_id">
                ${serverAdmin ? `<option value="" ${current === null ? "selected" : ""}>
                    Ohne Zuordnung (für alle sichtbar)</option>` : ""}
                ${options.map(({org, depth}) => `
                    <option value="${org.id}" ${org.id === current ? "selected" : ""}>
                        ${"  ".repeat(depth)}${escapeHTML(org.name)}
                    </option>
                `).join("")}
            </select>
            <small>Mitglieder dieser Organisation sehen die Drohne.</small>
        </div>
    `;
}

function sourceSpecificFields(source) {
    if (source.type === "rtmp") {
        const publishUrl = sourcePublishUrl(source);
        const srt = source.ingest_protocol === "srt";
        return `
            <div class="form-field form-field-wide">
                <label>Empfangsprotokoll</label>
                <select class="bos-input" data-field="ingest_protocol">
                    <option value="rtmp" ${srt ? "" : "selected"}>
                        RTMP – Drohnen-Apps (TCP 1935)
                    </option>
                    <option value="srt" ${srt ? "selected" : ""}>
                        SRT – geringe Latenz über Mobilfunk, z. B. Raspberry Pi (UDP 8890)
                    </option>
                </select>
                <small>
                    ${srt
                        ? "SRT gleicht Paketverluste aus und hält die Verzögerung " +
                          "klein (typisch 0,5–1 s). Der Sender wählt die Latenz; " +
                          "300–500 ms sind für Mobilfunk ein guter Wert."
                        : "RTMP wird von den meisten Drohnen-Apps unterstützt."}
                </small>
            </div>
            <div class="form-field form-field-wide">
                <label>${srt ? "SRT" : "RTMP"}-Empfangsadresse</label>
                <input
                    class="bos-input"
                    data-role="publish-url"
                    type="password"
                    value="${escapeHTML(publishUrl)}"
                    readonly>
                <button
                    class="bos-button bos-button-small"
                    type="button"
                    data-role="toggle-publish-url"
                    aria-pressed="false">
                    Adresse anzeigen
                </button>
                <small>
                    Der Empfangspfad entspricht automatisch der ID.
                    Der Token schützt diesen Pfad vor fremden Sendern.
                    ${srt
                        ? "Apps mit eigenem Feld für die Stream-ID erhalten " +
                          `<code>publish:${escapeHTML(source.id)}:token=…</code>. `
                        : ""}
                    Die Übertragung selbst ist unverschlüsselt.
                </small>
            </div>
            <div class="form-field form-field-wide">
                <label>Publisher-Token</label>
                <input
                    class="bos-input"
                    data-field="publish_token"
                    type="password"
                    autocomplete="new-password"
                    minlength="12"
                    maxlength="12"
                    pattern="[A-Za-z0-9_-]{12}"
                    value="${escapeHTML(source.publish_token ?? "")}">
                <button
                    class="bos-button bos-button-small"
                    type="button"
                    data-role="toggle-publish-token"
                    aria-pressed="false">
                    Token anzeigen
                </button>
                <small>
                    Genau 12 Zeichen. Das Feld ist bearbeitbar; nach einer
                    Änderung bitte speichern und die neue URL verwenden.
                </small>
            </div>
        `;
    }

    if (source.type === "rtsp") {
        return `
            <div class="form-field form-field-wide">
                <label>Controller-Vorlage</label>
                <select class="bos-input" data-role="rtsp-preset">
                    ${rtspPresetOptions()}
                </select>
                <small data-role="rtsp-preset-hint">${escapeHTML(RTSP_PRESET_DEFAULT_HINT)}</small>
            </div>
            <div class="form-field form-field-wide">
                <label>RTSP-URL</label>
                <input
                    class="bos-input"
                    data-field="url"
                    type="password"
                    autocomplete="off"
                    value="${escapeHTML(source.url ?? "")}"
                    placeholder="rtsp://benutzer:passwort@kamera/stream">
                <button
                    class="bos-button bos-button-small source-url-toggle"
                    type="button"
                    data-role="toggle-source-url"
                    aria-pressed="false">
                    URL anzeigen und bearbeiten
                </button>
                <small>Die Adresse bleibt bis zum bewussten Einblenden maskiert.</small>
            </div>
            <div class="form-field form-field-wide">
                <label>Vorschau-URL (optional)</label>
                <input
                    class="bos-input"
                    data-field="preview_url"
                    type="password"
                    autocomplete="off"
                    value="${escapeHTML(source.preview_url ?? "")}"
                    placeholder="rtsp://benutzer:passwort@kamera/substream">
                <button
                    class="bos-button bos-button-small source-url-toggle"
                    type="button"
                    data-role="toggle-preview-url"
                    aria-pressed="false">
                    URL anzeigen und bearbeiten
                </button>
                <small>
                    Wird für Livebild und Browserwiedergabe bevorzugt. Leer
                    bedeutet: Hauptstream verwenden. Ein H.264-Substream mit
                    720p oder 1080p entlastet Netzwerk und Browser deutlich.
                </small>
            </div>
            <div class="form-field">
                <label>Transport</label>
                <select class="bos-input" data-field="transport">
                    <option value="tcp" ${source.transport !== "udp" ? "selected" : ""}>TCP</option>
                    <option value="udp" ${source.transport === "udp" ? "selected" : ""}>UDP</option>
                </select>
                <small>
                    TCP ist in normalen Netzwerken robuster. Bei kurzen
                    Aussetzern kann zusätzlich das Profil „Copy mit
                    Zeitstempel-Korrektur“ einen moderaten Eingangspuffer
                    verwenden; die Latenz steigt dabei geringfügig.
                </small>
            </div>
        `;
    }

    if (source.type !== "v4l2") {
        const metadata = sourceTypeMetadata(source.type);
        const urlField = metadata?.fields?.find(
            field => field.name === "url"
        );
        return `
            <div class="form-field form-field-wide">
                <label>${escapeHTML(urlField?.label ?? "Stream-URL")}</label>
                <input
                    class="bos-input"
                    data-field="url"
                    type="password"
                    autocomplete="off"
                    value="${escapeHTML(source.url ?? "")}">
                <small>Zugangsdaten und URL-Parameter werden maskiert.</small>
            </div>
        `;
    }

    const metadata = sourceTypeMetadata("v4l2");
    const deviceField = metadata?.fields?.find(
        field => field.name === "device"
    );
    const devices = deviceField?.options ?? [];
    const deviceControl = devices.length
        ? `<select class="bos-input" data-field="device">
            ${devices.map(device => `
                <option value="${escapeHTML(device.value)}"
                    ${device.value === source.device ? "selected" : ""}>
                    ${escapeHTML(device.label)}
                </option>
            `).join("")}
           </select>`
        : `<input class="bos-input" data-field="device"
              value="${escapeHTML(source.device ?? "/dev/video0")}">`;

    return `
        <div class="form-field form-field-wide">
            <label>Videogerät</label>
            ${deviceControl}
        </div>
        <div class="form-field">
            <label>Breite</label>
            <input class="bos-input" data-field="width" type="number"
                min="1" value="${Number(source.width ?? 1280)}">
        </div>
        <div class="form-field">
            <label>Höhe</label>
            <input class="bos-input" data-field="height" type="number"
                min="1" value="${Number(source.height ?? 720)}">
        </div>
        <div class="form-field">
            <label>Bildrate</label>
            <input class="bos-input" data-field="fps" type="number"
                min="1" value="${Number(source.fps ?? 30)}">
        </div>
        <div class="form-field">
            <label>Format</label>
            <input class="bos-input" data-field="format"
                value="${escapeHTML(source.format ?? "mjpeg")}">
        </div>
    `;
}

function renderSources() {
    const container = document.getElementById("source-settings");
    if (!container || !currentConfig) {
        return;
    }

    const sources = currentConfig.sources ?? [];
    container.innerHTML = sources.length
        ? ""
        : `<p class="empty-state">Noch keine Drohne konfiguriert.</p>`;

    sources.forEach((source, index) => {
        const card = document.createElement("details");
        card.className = "rtmp-input-config source-config";
        card.dataset.index = String(index);
        card.innerHTML = `
            <summary class="rtmp-input-config-header">
                <div>
                    <strong>${escapeHTML(source.name || `Drohne ${index + 1}`)}</strong>
                    <small>${escapeHTML(
                        source.type === "rtmp" && source.ingest_protocol === "srt"
                            ? "srt-empfang"
                            : source.type
                    )} · ${escapeHTML(source.profile)}</small>
                </div>
                <div class="source-order-actions">
                    <button class="bos-button bos-button-small"
                        type="button"
                        title="Drohne nach oben verschieben"
                        aria-label="Drohne nach oben verschieben"
                        onclick="event.preventDefault(); event.stopPropagation(); moveSource(${index}, -1)"
                        ${index === 0 ? "disabled" : ""}>
                        ↑
                    </button>
                    <button class="bos-button bos-button-small"
                        type="button"
                        title="Drohne nach unten verschieben"
                        aria-label="Drohne nach unten verschieben"
                        onclick="event.preventDefault(); event.stopPropagation(); moveSource(${index}, 1)"
                        ${index === sources.length - 1 ? "disabled" : ""}>
                        ↓
                    </button>
                    <button class="bos-button bos-button-small"
                        type="button"
                        onclick="event.preventDefault(); event.stopPropagation(); removeSource(${index})">
                        Entfernen
                    </button>
                </div>
            </summary>
            <div class="source-config-body form-grid">
                <div class="form-field">
                    <label>Name</label>
                    <input class="bos-input" data-field="name"
                        value="${escapeHTML(source.name)}">
                </div>
                ${sourceOrganizationField(source)}
                <div class="form-field">
                    <label>Drohnen-Typ</label>
                    <input class="bos-input" data-field="drone_type"
                        maxlength="100"
                        value="${escapeHTML(source.drone_type ?? "")}"
                        placeholder="z. B. DJI Matrice 350 RTK">
                </div>
                <div class="form-field">
                    <label>ID</label>
                    <input class="bos-input" data-field="id"
                        pattern="[a-z0-9][a-z0-9_-]{0,31}"
                        value="${escapeHTML(source.id)}">
                    <small>Nur Kleinbuchstaben, Zahlen, „-“ und „_“.</small>
                </div>
                <div class="form-field">
                    <label>Anschlussart</label>
                    <select class="bos-input" data-field="type">
                        ${sourceTypeOptions(source.type)}
                    </select>
                </div>
                <div class="form-field">
                    <label>Audio</label>
                    <select class="bos-input" data-field="audio_mode">
                        <option value="none" ${source.audio_mode === "none" || !source.audio_mode ? "selected" : ""}>Deaktiviert</option>
                        <option value="copy" ${source.audio_mode === "copy" ? "selected" : ""}>Übernehmen</option>
                        <option value="aac" ${source.audio_mode === "aac" ? "selected" : ""}>AAC umkodieren</option>
                    </select>
                </div>
                <div class="form-field form-field-wide">
                    <label>Profil</label>
                    <select class="bos-input" data-field="profile">
                        ${sourceProfileOptions(source.profile, source.type)}
                    </select>
                    ${sourceProfileHelp(source.profile, source.type)}
                </div>
                ${sourceTranscodingFields(source)}
                <div class="source-specific-fields form-grid form-field-wide">
                    ${sourceSpecificFields(source)}
                </div>
            </div>
            <label class="switch-row">
                <input type="checkbox" data-field="enabled"
                    ${source.enabled ? "checked" : ""}>
                <span><strong>Drohne aktivieren</strong></span>
            </label>
            <div data-source-history="${escapeHTML(source.id)}"></div>
        `;
        container.appendChild(card);

        card.querySelector('[data-field="type"]')?.addEventListener(
            "change",
            async event => {
                saveSources();
                currentConfig.sources[index].type = event.target.value;
                if (event.target.value === "v4l2") {
                    currentConfig.sources[index].profile = "transcode";
                } else if (
                    [
                        "preview_transcode",
                        "preview_transcode_economy",
                    ].includes(currentConfig.sources[index].profile) &&
                    event.target.value !== "rtmp"
                ) {
                    currentConfig.sources[index].profile = "direct";
                }
                // Beim Wechsel zum Empfang kein verstecktes Profil mitnehmen.
                if (
                    !window.currentPermissions?.server_admin &&
                    isHiddenProfile(
                        currentConfig.sources[index].profile,
                        event.target.value
                    )
                ) {
                    currentConfig.sources[index].profile =
                        defaultSourceProfile(event.target.value);
                }
                await loadSourceEncoders();
                renderSources();
                setConfigDirty(true);
            }
        );
        card.querySelector('[data-field="ingest_protocol"]')?.addEventListener(
            "change",
            () => {
                saveSources();
                renderSources();
                setConfigDirty(true);
            }
        );
        card.querySelector('[data-field="profile"]')?.addEventListener(
            "change",
            () => {
                saveSources();
                renderSources();
                setConfigDirty(true);
            }
        );
        card.querySelector('[data-role="rtsp-preset"]')?.addEventListener(
            "change",
            event => applyRtspPreset(card, event.target.value)
        );
        card.querySelector('[data-field="id"]')?.addEventListener(
            "input",
            event => {
                currentConfig.sources[index].id = event.target.value;
                const publishUrl = card.querySelector(
                    '[data-role="publish-url"]'
                );
                if (publishUrl) {
                    publishUrl.value = sourcePublishUrl({
                        ...currentConfig.sources[index],
                        ingest_protocol: card.querySelector(
                            '[data-field="ingest_protocol"]'
                        )?.value,
                        publish_token: card.querySelector(
                            '[data-field="publish_token"]'
                        )?.value,
                    });
                }
            }
        );
        card.querySelector('[data-field="publish_token"]')?.addEventListener(
            "input",
            event => {
                currentConfig.sources[index].publish_token =
                    event.target.value;
                card.querySelector('[data-role="publish-url"]').value =
                    sourcePublishUrl(currentConfig.sources[index]);
            }
        );
        card.querySelector('[data-role="toggle-publish-url"]')?.addEventListener(
            "click",
            event => {
                const input = card.querySelector('[data-role="publish-url"]');
                const visible = input.type === "text";
                input.type = visible ? "password" : "text";
                event.currentTarget.textContent = visible
                    ? "Adresse anzeigen"
                    : "Adresse ausblenden";
                event.currentTarget.setAttribute(
                    "aria-pressed",
                    String(!visible)
                );
            }
        );
        card.querySelector('[data-role="toggle-publish-token"]')?.addEventListener(
            "click",
            event => {
                const input = card.querySelector('[data-field="publish_token"]');
                const visible = input.type === "text";
                input.type = visible ? "password" : "text";
                event.currentTarget.textContent = visible
                    ? "Token anzeigen"
                    : "Token ausblenden";
                event.currentTarget.setAttribute(
                    "aria-pressed",
                    String(!visible)
                );
            }
        );
        card.querySelector('[data-role="toggle-source-url"]')?.addEventListener(
            "click",
            event => {
                const input = card.querySelector('[data-field="url"]');
                const visible = input.type === "text";
                input.type = visible ? "password" : "text";
                event.currentTarget.textContent = visible
                    ? "URL anzeigen und bearbeiten"
                    : "URL wieder ausblenden";
                event.currentTarget.setAttribute(
                    "aria-pressed",
                    String(!visible)
                );
                if (!visible) {
                    input.focus();
                }
            }
        );
        card.querySelector('[data-role="toggle-preview-url"]')?.addEventListener(
            "click",
            event => {
                const input = card.querySelector('[data-field="preview_url"]');
                const visible = input.type === "text";
                input.type = visible ? "password" : "text";
                event.currentTarget.textContent = visible
                    ? "URL anzeigen und bearbeiten"
                    : "URL wieder ausblenden";
                event.currentTarget.setAttribute(
                    "aria-pressed",
                    String(!visible)
                );
                if (!visible) {
                    input.focus();
                }
            }
        );
    });

    updateSourceCountHint(sources.length);
    if (typeof fillDroneHistory === "function") {
        fillDroneHistory();
    }
    if (typeof renderMediaCaptureConfig === "function") {
        renderMediaCaptureConfig();
    }
}

function saveSources() {
    if (!currentConfig) {
        return;
    }

    currentConfig.sources = Array.from(
        document.querySelectorAll("#source-settings .source-config")
    ).map(card => {
        const value = (field, fallback = null) =>
            card.querySelector(`[data-field="${field}"]`)?.value ?? fallback;
        return {
            id: value("id", "").trim().toLowerCase(),
            name: value("name", "").trim(),
            drone_type: value("drone_type", "").trim(),
            type: value("type", "rtmp"),
            profile: value("profile", "direct"),
            enabled: card.querySelector('[data-field="enabled"]').checked,
            url: value("url"),
            preview_url: value("preview_url"),
            device: value("device"),
            width: Number(value("width", 1280)),
            height: Number(value("height", 720)),
            fps: Number(value("fps", 30)),
            format: value("format", "mjpeg"),
            transport: value("transport", "tcp"),
            codec: value("codec"),
            bitrate: value("bitrate"),
            pixel_format: value("pixel_format"),
            gop: value("gop") === null
                ? null
                : Number(value("gop")),
            preset: value("preset"),
            tune: value("tune"),
            audio_mode: value("audio_mode", "none"),
            ingest_protocol: value("ingest_protocol", "rtmp"),
            publish_token: value("publish_token"),
            organization_id: card.querySelector('[data-field="organization_id"]')
                ? (Number(value("organization_id")) || null)
                : (currentConfig.sources?.[Number(card.dataset.index)]?.organization_id ?? null),
        };
    });
}

function addSource() {
    saveSources();
    currentConfig.sources ??= [];

    let number = currentConfig.sources.length + 1;
    const ids = new Set(currentConfig.sources.map(source => source.id));
    while (ids.has(`drohne-${number}`)) {
        number += 1;
    }
    // Wehr-Admins sehen nicht alle Quellen des Servers; eine zufällige
    // Kennung vermeidet Überschneidungen mit Quellen anderer Wehren.
    const restricted = !window.currentPermissions?.server_admin;
    const newId = restricted
        ? `drohne-${Math.random().toString(36).slice(2, 7)}`
        : `drohne-${number}`;
    currentConfig.sources.push({
        id: newId,
        name: `Drohne ${number}`,
        drone_type: "",
        type: "rtmp",
        profile: defaultSourceProfile("rtmp"),
        enabled: true,
        url: null,
        preview_url: null,
        device: "/dev/video0",
        width: 1280,
        height: 720,
        fps: 30,
        format: "mjpeg",
        transport: "tcp",
        codec: null,
        bitrate: null,
        pixel_format: null,
        gop: null,
        preset: null,
        tune: null,
        audio_mode: "none",
        ingest_protocol: "rtmp",
        publish_token: generatePublisherToken(),
        // Neue Quellen gehören zunächst der ersten eigenen Organisation.
        organization_id: sourceOrganizationOptions()[0]?.org.id ?? null,
    });
    renderSources();
    const cards = document.querySelectorAll(
        "#source-settings .source-config"
    );
    if (cards.length) {
        cards[cards.length - 1].open = true;
    }
    setConfigDirty(true);
}

function removeSource(index) {
    saveSources();
    currentConfig.sources.splice(index, 1);
    renderSources();
    setConfigDirty(true);
}

function moveSource(index, direction) {
    saveSources();
    const target = index + direction;
    if (
        target < 0 ||
        target >= currentConfig.sources.length
    ) {
        return;
    }

    const [source] = currentConfig.sources.splice(index, 1);
    currentConfig.sources.splice(target, 0, source);
    renderSources();
    setConfigDirty(true);
    setConfigSaveStatus(
        "Reihenfolge geändert – bitte speichern."
    );
}
const sourceEncodersByType = new Map();

async function loadSourceEncoders() {
    const representatives = new Map();
    for (const source of currentConfig.sources ?? []) {
        if (!representatives.has(source.type)) {
            representatives.set(source.type, source);
        }
    }
    await Promise.all(
        Array.from(representatives.entries()).map(
            async ([type, source]) => {
                try {
                    sourceEncodersByType.set(
                        type,
                        await api.encoders(source)
                    );
                } catch (error) {
                    console.error(
                        `Encoder für ${type} konnten nicht geladen werden:`,
                        error
                    );
                    sourceEncodersByType.set(type, []);
                }
            }
        )
    );
}


// Keine feste Obergrenze mehr: ab neun Quellen auf die Serverlast hinweisen.
const SOURCE_LOAD_HINT_FROM = 9;

function updateSourceCountHint(count) {
    const hint = document.getElementById("source-count-hint");
    if (!hint) {
        return;
    }
    hint.hidden = count < SOURCE_LOAD_HINT_FROM;
    hint.textContent = count >= SOURCE_LOAD_HINT_FROM
        ? `${count} Drohnen eingerichtet. Jede aktive Drohne belegt Rechenleistung ` +
          "auf dem Server. Die Auslastung wird überwacht; bei hoher Last erscheint " +
          "ein Hinweis. Für viele Drohnen das sparsame Vorschauprofil wählen."
        : "";
}
