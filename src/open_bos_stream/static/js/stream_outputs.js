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

	container.innerHTML = outputs.map(output => `

	    <div class="info-row">

	        <div>

	            <strong>${output.name}</strong>

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
				    onclick="${
				        output.running
				            ? `stopStreamOutput('${output.name}')`
				            : `startStreamOutput('${output.name}')`
				    }">

				    ${output.running ? "Stop" : "Start"}

				</button>

	    </div>

	`).join("");

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