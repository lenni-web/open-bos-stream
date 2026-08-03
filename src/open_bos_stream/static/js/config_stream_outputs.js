function renderStreamOutputs() {

    const container = document.getElementById(
        "stream-output-settings"
    );

    if (!container) {
        return;
    }

    container.innerHTML = "";

    currentConfig.stream_outputs.forEach(
        (output, index) => {

            output.audio ??= {
                source: "none",
            };

            output.source_id ??=
                currentConfig.sources?.find(
                    source => source.enabled
                )?.id ?? currentConfig.sources?.[0]?.id ?? null;

            const sourceOptions = (currentConfig.sources ?? [])
                .map(source => `
                    <option
                        value="${escapeHTML(source.id)}"
                        ${output.source_id === source.id ? "selected" : ""}>
                        ${escapeHTML(source.name)}${source.enabled ? "" : " (deaktiviert)"}
                    </option>
                `)
                .join("");

            container.innerHTML += `

                <div class="stream-output-config">

                    <label>Name</label>

                    <input
                        class="bos-input"
                        data-index="${index}"
                        data-field="name"
                        value="${output.name}">

                    <label>Protokoll</label>

                    <select
                        class="bos-input"
                        data-index="${index}"
                        data-field="type">

                        <option
                            value="rtmp"
                            ${output.type === "rtmp" ? "selected" : ""}>
                            RTMP
                        </option>

                        <option
                            value="srt"
                            ${output.type === "srt" ? "selected" : ""}>
                            SRT
                        </option>

                    </select>

                    <label>Weiterzuleitende Quelle</label>

                    <select
                        class="bos-input"
                        data-index="${index}"
                        data-field="source-id"
                        ${sourceOptions ? "" : "disabled"}>

                        ${sourceOptions || `
                            <option value="">
                                Keine Quelle verfügbar
                            </option>
                        `}

                    </select>

                    <label>Zieladresse</label>

                    <input
                        class="bos-input"
                        data-index="${index}"
                        data-field="url"
                        value="${output.url}">

                    <label>Audio</label>

                    <select
                        class="bos-input"
                        data-index="${index}"
                        data-field="audio-source">

                        <option
                            value="none"
                            ${output.audio.source === "none" ? "selected" : ""}>
                            Kein Audio
                        </option>

                        <option
                            value="silence"
                            ${output.audio.source === "silence" ? "selected" : ""}>
                            Stilles Audio
                        </option>

                        <option
                            value="input"
                            ${output.audio.source === "input" ? "selected" : ""}>
                            Eingangston
                        </option>

                    </select>

                    <label>

                        <input
                            type="checkbox"
                            data-index="${index}"
                            data-field="enabled"
                            ${output.enabled ? "checked" : ""}>

                        Aktiviert

                    </label>

                    <button
                        class="bos-button bos-button-red"
                        onclick="removeStreamOutput(${index})">

                        🗑 Entfernen

                    </button>

                    <hr>

                </div>

            `;

        }
    );

}

function addStreamOutput() {

    currentConfig.stream_outputs.push({
        type: "rtmp",
        name: "Neuer Output",
        url: "",
        enabled: true,
        source_id:
            currentConfig.sources?.find(
                source => source.enabled
            )?.id ?? currentConfig.sources?.[0]?.id ?? null,
        audio: {
            source: "none",
        },

    });

    renderStreamOutputs();

}

function removeStreamOutput(index) {

    currentConfig.stream_outputs.splice(
        index,
        1
    );

    renderStreamOutputs();

}

function saveStreamOutputs() {
    const container = document.getElementById(
        "stream-output-settings"
    );
    if (!container) {
        return;
    }

    const outputs = [];

    document
        .querySelectorAll(".stream-output-config")
        .forEach(card => {

            outputs.push({

                type: card.querySelector(
                    '[data-field="type"]'
                ).value,

                name: card.querySelector(
                    '[data-field="name"]'
                ).value,

                url: card.querySelector(
                    '[data-field="url"]'
                ).value,

                enabled: card.querySelector(
                    '[data-field="enabled"]'
                ).checked,

                source_id: card.querySelector(
                    '[data-field="source-id"]'
                ).value || null,

                audio: {

                    source: card.querySelector(
                        '[data-field="audio-source"]'
                    ).value,

                },

            });

        });

    currentConfig.stream_outputs = outputs;

}
