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

function sourceSpecificFields(source) {
    if (source.type === "rtmp") {
        return `
            <div class="form-field form-field-wide">
                <label>RTMP-Empfangsadresse</label>
                <input
                    class="bos-input"
                    data-role="publish-url"
                    value="rtmp://&lt;StreamPi-IP&gt;:1935/${escapeHTML(source.id)}"
                    readonly>
                <small>Der Empfangspfad entspricht automatisch der ID.</small>
            </div>
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
                <small>Zugangsdaten werden in der Anzeige maskiert.</small>
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
        const card = document.createElement("article");
        card.className = "rtmp-input-config source-config";
        card.dataset.index = String(index);
        card.innerHTML = `
            <div class="rtmp-input-config-header">
                <div>
                    <strong>Quelle ${index + 1}: ${escapeHTML(source.name)}</strong>
                    <small>${escapeHTML(source.type)} · ${escapeHTML(source.profile)}</small>
                </div>
                <div class="source-order-actions">
                    <button class="bos-button bos-button-small"
                        type="button"
                        title="Quelle nach oben verschieben"
                        aria-label="Quelle nach oben verschieben"
                        onclick="moveSource(${index}, -1)"
                        ${index === 0 ? "disabled" : ""}>
                        ↑
                    </button>
                    <button class="bos-button bos-button-small"
                        type="button"
                        title="Quelle nach unten verschieben"
                        aria-label="Quelle nach unten verschieben"
                        onclick="moveSource(${index}, 1)"
                        ${index === sources.length - 1 ? "disabled" : ""}>
                        ↓
                    </button>
                    <button class="bos-button bos-button-small"
                        type="button" onclick="removeSource(${index})">
                        Entfernen
                    </button>
                </div>
            </div>
            <div class="form-grid">
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
                        <option value="copy" ${source.audio_mode !== "none" && source.audio_mode !== "aac" ? "selected" : ""}>Übernehmen</option>
                        <option value="aac" ${source.audio_mode === "aac" ? "selected" : ""}>AAC umkodieren</option>
                        <option value="none" ${source.audio_mode === "none" ? "selected" : ""}>Deaktivieren</option>
                    </select>
                </div>
                <div class="form-field">
                    <label>Encoder bei Transcoding</label>
                    <input class="bos-input" data-field="codec"
                        value="${escapeHTML(source.codec ?? currentConfig.encoder.codec)}"
                        ${source.profile === "transcode" ? "" : "disabled"}>
                </div>
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
            event => {
                saveSources();
                currentConfig.sources[index].type = event.target.value;
                if (event.target.value === "v4l2") {
                    currentConfig.sources[index].profile = "transcode";
                }
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
                const display = card.querySelector('[data-role="publish-url"]');
                if (display) {
                    display.value =
                        `rtmp://<StreamPi-IP>:1935/${event.target.value}`;
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
            audio_mode: value("audio_mode", "copy"),
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
        audio_mode: "copy",
    });
    renderSources();
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
