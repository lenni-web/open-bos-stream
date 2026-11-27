function updateStreamOutputs(outputs) {

    const container = document.getElementById(
        "stream-outputs"
    );

    if (!container) {
        return;
    }

    if (!outputs || outputs.length === 0) {

        container.innerHTML = `
            <div class="text-muted">
                Keine Streaming Outputs vorhanden.
            </div>
        `;

        return;
    }

    // Namen nur maskiert einsetzen und nicht in onclick-Code einbauen:
    // ein Name wie  x'); alert(1); ('  würde sonst als Skript ausgeführt.
    container.innerHTML = outputs.map(output => `

        <div class="info-row">

            <div>

                <strong>${escapeHTML(output.name)}</strong>

                <div class="text-muted">
                    Drohne: ${escapeHTML(output.source_name ?? "Nicht gewählt")}
                </div>

                <div class="stream-output-status">

                    <span class="
                        stream-output-indicator
                        ${output.running ? "running" : "stopped"}
                    "></span>

                    ${output.running ? "Läuft" : "Gestoppt"}

                </div>

            </div>

            <button
                class="bos-button ${
                    output.running
                        ? "bos-button-red"
                        : "bos-button-green"
                }"
                type="button"
                data-output-action="${output.running ? "stop" : "start"}"
                data-output-name="${escapeHTML(output.name)}">

                ${output.running ? "Stop" : "Start"}

            </button>

        </div>

    `).join("");

    if (!container.dataset.outputActionsBound) {
        container.dataset.outputActionsBound = "true";
        container.addEventListener("click", event => {
            const button = event.target.closest("[data-output-action]");
            if (!button) {
                return;
            }
            const name = button.dataset.outputName;
            if (button.dataset.outputAction === "stop") {
                stopStreamOutput(name);
            } else {
                startStreamOutput(name);
            }
        });
    }

}

async function startStreamOutput(name) {

    try {

        await apiStartStreamOutput(name);

        await refreshDashboard();

    }

    catch (error) {

        console.error(error);

        alert(error.message);

    }

}

async function stopStreamOutput(name) {

    try {

        await apiStopStreamOutput(name);

        await refreshDashboard();

    }

    catch (error) {

        console.error(error);

        alert(error.message);

    }

}
