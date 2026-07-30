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

function sourceProfileOptions(selected) {
    const profiles = [
        ["direct", "Direkt / Stream Copy"],
        ["copy_repair", "Copy mit Zeitstempel-Korrektur"],
        ["transcode", "Transcodieren"],
    ];
    return profiles.map(([value, label]) => `
        <option
            value="${value}"
            ${value === selected ? "selected" : ""}>
            ${label}
        </option>
    `).join("");
}

function generatePublisherToken() {
    const bytes = new Uint8Array(32);
    window.crypto.getRandomValues(bytes);
    return Array.from(
        bytes,
        value => value.toString(16).padStart(2, "0")
    ).join("");
}

function sourcePublishUrl(source) {
    const host = window.location.hostname || "<Server-IP>";
    const base = `rtmp://${host}:1935/${source.id}`;
    if (
        window.installationProfile === "server"
        && source.publish_token
    ) {
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
    if (source.profile !== "transcode") {
        return "";
    }
    const encoder = currentConfig.encoder;
    const codec = source.codec ?? encoder.codec;
    return `
        <fieldset class="source-transcoding form-field-wide">
            <legend>Transcoding dieser Quelle</legend>
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

function sourceSpecificFields(source) {
    if (source.type === "rtmp") {
        const protectedInput = window.installationProfile === "server";
        const publishUrl = sourcePublishUrl(source);
        return `
            <div class="form-field form-field-wide">
                <label>RTMP-Empfangsadresse</label>
                <input
                    class="bos-input"
                    data-role="publish-url"
                    type="${protectedInput ? "password" : "text"}"
                    value="${escapeHTML(publishUrl)}"
                    readonly>
                ${protectedInput ? `
                <button
                    class="bos-button bos-button-small"
                    type="button"
                    data-role="toggle-publish-url"
                    aria-pressed="false">
                    Adresse anzeigen
                </button>
                ` : ""}
                <small>
                    Der Empfangspfad entspricht automatisch der ID.
                    ${protectedInput
                        ? "Der Token schützt diesen Pfad vor fremden Publishern. RTMP selbst bleibt unverschlüsselt."
                        : "Im lokalen Profil ist RTMP nicht authentifiziert oder verschlüsselt."}
                </small>
            </div>
            ${protectedInput ? `
            <div class="form-field form-field-wide">
                <label>Publisher-Token</label>
                <input
                    class="bos-input"
                    data-field="publish_token"
                    type="password"
                    autocomplete="new-password"
                    minlength="24"
                    maxlength="128"
                    value="${escapeHTML(source.publish_token ?? "")}">
                <button
                    class="bos-button bos-button-small"
                    type="button"
                    data-role="toggle-publish-token"
                    aria-pressed="false">
                    Token anzeigen
                </button>
                <small>Nur an vertrauenswürdige Publisher weitergeben.</small>
            </div>
            ` : ""}
        `;
    }

    if (source.type === "rtsp") {
        return `
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
            <div class="form-field">
                <label>Transport</label>
                <select class="bos-input" data-field="transport">
                    <option value="tcp" ${source.transport !== "udp" ? "selected" : ""}>TCP</option>
                    <option value="udp" ${source.transport === "udp" ? "selected" : ""}>UDP</option>
                </select>
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
                <label>${escapeHTML(urlField?.label ?? "Quell-URL")}</label>
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
        : `<p class="empty-state">Noch keine Quelle konfiguriert.</p>`;

    sources.forEach((source, index) => {
        const card = document.createElement("details");
        card.className = "rtmp-input-config source-config";
        card.dataset.index = String(index);
        card.innerHTML = `
            <summary class="rtmp-input-config-header">
                <div>
                    <strong>Quelle ${index + 1}: ${escapeHTML(source.name)}</strong>
                    <small>${escapeHTML(source.type)} · ${escapeHTML(source.profile)}</small>
                </div>
                <div class="source-order-actions">
                    <button class="bos-button bos-button-small"
                        type="button"
                        title="Quelle nach oben verschieben"
                        aria-label="Quelle nach oben verschieben"
                        onclick="event.preventDefault(); event.stopPropagation(); moveSource(${index}, -1)"
                        ${index === 0 ? "disabled" : ""}>
                        ↑
                    </button>
                    <button class="bos-button bos-button-small"
                        type="button"
                        title="Quelle nach unten verschieben"
                        aria-label="Quelle nach unten verschieben"
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
                <div class="form-field">
                    <label>ID</label>
                    <input class="bos-input" data-field="id"
                        pattern="[a-z0-9][a-z0-9_-]{0,31}"
                        value="${escapeHTML(source.id)}">
                    <small>Nur Kleinbuchstaben, Zahlen, „-“ und „_“.</small>
                </div>
                <div class="form-field">
                    <label>Quellentyp</label>
                    <select class="bos-input" data-field="type">
                        ${sourceTypeOptions(source.type)}
                    </select>
                </div>
                <div class="form-field">
                    <label>Profil</label>
                    <select class="bos-input" data-field="profile">
                        ${sourceProfileOptions(source.profile)}
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
                ${sourceTranscodingFields(source)}
                <div class="source-specific-fields form-grid form-field-wide">
                    ${sourceSpecificFields(source)}
                </div>
            </div>
            <label class="switch-row">
                <input type="checkbox" data-field="enabled"
                    ${source.enabled ? "checked" : ""}>
                <span><strong>Quelle aktivieren</strong></span>
            </label>
        `;
        container.appendChild(card);

        card.querySelector('[data-field="type"]')?.addEventListener(
            "change",
            async event => {
                saveSources();
                currentConfig.sources[index].type = event.target.value;
                if (event.target.value === "v4l2") {
                    currentConfig.sources[index].profile = "transcode";
                }
                await loadSourceEncoders();
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
    });

    const addButton = document.getElementById("source-add-button");
    if (addButton) {
        addButton.disabled = sources.length >= 8;
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
            type: value("type", "rtmp"),
            profile: value("profile", "direct"),
            enabled: card.querySelector('[data-field="enabled"]').checked,
            url: value("url"),
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
            publish_token: value("publish_token"),
        };
    });
}

function addSource() {
    saveSources();
    currentConfig.sources ??= [];
    if (currentConfig.sources.length >= 8) {
        return;
    }

    let number = currentConfig.sources.length + 1;
    const ids = new Set(currentConfig.sources.map(source => source.id));
    while (ids.has(`quelle-${number}`)) {
        number += 1;
    }
    currentConfig.sources.push({
        id: `quelle-${number}`,
        name: `Quelle ${number}`,
        type: "rtmp",
        profile: "direct",
        enabled: true,
        url: null,
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
        publish_token: generatePublisherToken(),
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
