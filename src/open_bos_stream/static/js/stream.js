// ==========================================================
// Stream
// ==========================================================

async function toggleStream() {
	
    const status =
        await api.status();

    if (status.running) {

        await stopStream();

    } else {

        await startStream();

    }

}

// ==========================================================
// Stream starten
// ==========================================================

async function startStream() {
	
    const result =
        await api.start();

    if (!result.success) {
		addEvent(
		    "error",
		    result.error ??
		    "Stream konnte nicht gestartet werden."
		);

        return;

    }

	await refreshDashboard();

	const pid =

	    window.dashboard?.stream?.pid;

	addEvent(

	    "success",

	    pid

	        ? `📡 Stream gestartet (PID ${pid})`

	        : "📡 Stream gestartet"

	);

}

// ==========================================================
// Stream stoppen
// ==========================================================

async function stopStream() {

    const result =
        await api.stop();

    if (!result.success) {

        alert(
            result.error ??
            "Stream konnte nicht gestoppt werden."
        );

        return;

    }

    await refreshDashboard();

    addEvent(
        "warning",
        "🛑 Stream gestoppt"
    );

}

// ==========================================================
// Vollbild
// ==========================================================

async function toggleFullscreen() {

    const container =
        document.getElementById(
            "video-container"
        );

    if (!container) {
        return;
    }

    if (!document.fullscreenElement) {

        await container.requestFullscreen();

    } else {

        await document.exitFullscreen();

    }

}
