function normalizeRTMPInputPath(value) {
    return String(value ?? "")
        .trim()
        .replace(/^\/+|\/+$/g, "");
}

function defaultRTMPInput(index) {
    return {
        id: `quelle-${index}`,
        name: `Quelle ${index}`,
        path: `live/quelle-${index}`,
        viewer_path: null,
        enabled: true,
    };
}

function renderRTMPInputs() {
    const container =
        document.getElementById(
            "rtmp-input-settings"
        );
    if (!container || !currentConfig) {
        return;
    }

    const inputs =
        currentConfig.rtmp_inputs ?? [];
    container.innerHTML = "";

    if (inputs.length === 0) {
        container.innerHTML = `
            <p class="empty-state">
                Noch keine RTMP-Eingänge konfiguriert.
            </p>
        `;
    }

    inputs.forEach((input, index) => {
        const card = document.createElement("article");
        card.className = "rtmp-input-config";
        card.dataset.index = String(index);
        card.innerHTML = `
            <div class="rtmp-input-config-header">
                <strong>Eingang ${index + 1}</strong>
                <button
                    class="bos-button bos-button-small"
                    type="button"
                    onclick="removeRTMPInput(${index})">
                    Entfernen
                </button>
            </div>
            <div class="form-grid">
                <div class="form-field">
                    <label>Name</label>
                    <input
                        class="bos-input"
                        data-field="name"
                        value="${escapeHTML(input.name)}">
                </div>
                <div class="form-field">
                    <label>ID</label>
                    <input
                        class="bos-input"
                        data-field="id"
                        value="${escapeHTML(input.id)}">
                </div>
                <div class="form-field form-field-wide">
                    <label>RTMP-Pfad</label>
                    <input
                        class="bos-input"
                        data-field="path"
                        value="${escapeHTML(input.path)}">
                    <small>
                        Empfang: rtmp://&lt;StreamPi-IP&gt;:1935/${escapeHTML(input.path)}
                    </small>
                </div>
                <div class="form-field form-field-wide">
                    <label>Wiedergabepfad (optional)</label>
                    <input
                        class="bos-input"
                        data-field="viewer_path"
                        value="${escapeHTML(input.viewer_path ?? "")}"
                        placeholder="Leer = RTMP-Pfad direkt verwenden">
                    <small>
                        Nur für einen separaten reparierten Ausgabepfad.
                    </small>
                </div>
            </div>
            <label class="switch-row">
                <input
                    type="checkbox"
                    data-field="enabled"
                    ${input.enabled ? "checked" : ""}>
                <span><strong>Eingang aktivieren</strong></span>
            </label>
        `;
        container.appendChild(card);
    });

    const addButton =
        document.getElementById(
            "rtmp-input-add-button"
        );
    if (addButton) {
        addButton.disabled = inputs.length >= 8;
    }
}

function saveRTMPInputs() {
    if (!currentConfig) {
        return;
    }

    const cards = document.querySelectorAll(
        "#rtmp-input-settings .rtmp-input-config"
    );
    currentConfig.rtmp_inputs =
        Array.from(cards).map(card => ({
            id: card.querySelector(
                '[data-field="id"]'
            ).value.trim(),
            name: card.querySelector(
                '[data-field="name"]'
            ).value.trim(),
            path: normalizeRTMPInputPath(
                card.querySelector(
                    '[data-field="path"]'
                ).value
            ),
            viewer_path: normalizeRTMPInputPath(
                card.querySelector(
                    '[data-field="viewer_path"]'
                ).value
            ) || null,
            enabled: card.querySelector(
                '[data-field="enabled"]'
            ).checked,
        }));
}

function addRTMPInput() {
    saveRTMPInputs();
    currentConfig.rtmp_inputs ??= [];
    if (currentConfig.rtmp_inputs.length >= 8) {
        return;
    }

    let index = currentConfig.rtmp_inputs.length + 1;
    const ids = new Set(
        currentConfig.rtmp_inputs.map(item => item.id)
    );
    while (ids.has(`quelle-${index}`)) {
        index += 1;
    }

    currentConfig.rtmp_inputs.push(
        defaultRTMPInput(index)
    );
    renderRTMPInputs();
    setConfigDirty(true);
}

function removeRTMPInput(index) {
    saveRTMPInputs();
    currentConfig.rtmp_inputs.splice(index, 1);
    renderRTMPInputs();
    setConfigDirty(true);
}
