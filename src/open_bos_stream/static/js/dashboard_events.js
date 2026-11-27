// ==========================================================
// Stream Events
// ==========================================================

window.addEventListener(
    "open-bos:player-reconnect",
    event => {
        const detail = event.detail ?? {};
        addEvent(
            "warning",
            `🔄 ${detail.sourceName || detail.sourceId}: ` +
            `Player neu verbunden · ${detail.reason || "unbekannt"}`
        );
    }
);

function checkSourceEvents(sources = []) {
    const currentIds = new Set();

    for (const source of sources) {
        currentIds.add(source.id);
        const previous =
            lastDashboardState.sources[source.id];

        if (previous) {
            if (source.viewers > previous.viewers) {
                addEvent(
                    "info",
                    `👤 ${source.name}: Viewer verbunden ` +
                    `(${source.viewers})`
                );
            }
            if (source.viewers < previous.viewers) {
                addEvent(
                    "info",
                    `👤 ${source.name}: Viewer getrennt ` +
                    `(${source.viewers})`
                );
            }
        }

        lastDashboardState.sources[source.id] = {
            name: source.name,
            ready: Boolean(source.ready),
            viewers: Number(source.viewers ?? 0),
        };
    }

    for (
        const [sourceId, previous]
        of Object.entries(lastDashboardState.sources)
    ) {
        if (currentIds.has(sourceId)) {
            continue;
        }
        addEvent(
            "info",
            `⚪ ${previous.name}: Drohne deaktiviert oder entfernt`
        );
        delete lastDashboardState.sources[sourceId];
    }
}

function checkStreamEvents(
    stream
) {

    if (!stream) {
        return;
    }

    if (
        lastDashboardState.viewers !== null
    ) {

        if (
            stream.viewers >
            lastDashboardState.viewers
        ) {

            addEvent(
                "info",
                "👤 Viewer verbunden (" +
                stream.viewers +
                ")"
            );

        }

        if (
            stream.viewers <
            lastDashboardState.viewers
        ) {

            addEvent(
                "info",
                "👤 Viewer getrennt (" +
                stream.viewers +
                ")"
            );

        }

    }

    lastDashboardState.streamRunning =
        stream.running;

    lastDashboardState.viewers =
        stream.viewers;

}

// ==========================================================
// Service Events
// ==========================================================

function checkServiceEvents(
    services
) {

    if (!services) {
        return;
    }

    // ---------------------------------------------------------
    // MediaMTX
    // ---------------------------------------------------------

    lastDashboardState.mediamtx =
        services.mediamtx.online;

        // ---------------------------------------------------------
        // Capture Card
        // ---------------------------------------------------------

        if (
            lastDashboardState.capture !== null
        ) {

            if (
                !lastDashboardState.capture &&
                services.capture.online
            ) {

                addEvent(
                    "success",
                    "🎥 Capture Card verbunden"
                );

            }

            if (
                lastDashboardState.capture &&
                !services.capture.online
            ) {

                addEvent(
                    "warning",
                    "🎥 Capture Card getrennt"
                );

            }

        }

        lastDashboardState.capture =
            services.capture.online;

        // ---------------------------------------------------------
        // FFmpeg
        // ---------------------------------------------------------

        if (
            lastDashboardState.ffmpeg !== null
        ) {

            if (
                !lastDashboardState.ffmpeg &&
                services.ffmpeg.online
            ) {

                addEvent(
                    "success",
                    "🎬 FFmpeg gestartet"
                );

            }

            if (
                lastDashboardState.ffmpeg &&
                !services.ffmpeg.online
            ) {

                addEvent(
                    "warning",
                    "🎬 FFmpeg beendet"
                );

            }

        }

        lastDashboardState.ffmpeg =
            services.ffmpeg.online;

    }

    // ==========================================================
    // Streaming Output Events
    // ==========================================================

    function checkStreamOutputEvents(
        outputs
    ) {

        if (!outputs) {
            return;
        }

        for (const output of outputs) {

            const previous =
                lastDashboardState.streamOutputs[
                    output.name
                ];

            lastDashboardState.streamOutputs[
                output.name
            ] = output.running;

        }

    }
