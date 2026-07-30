// ==========================================================
// Stream Events
// ==========================================================

function checkSourceEvents(sources = []) {
    const currentIds = new Set();

    for (const source of sources) {
        currentIds.add(source.id);
        const previous =
            lastDashboardState.sources[source.id];

        if (previous) {
            if (!previous.ready && source.ready) {
                addEvent(
                    "success",
                    `🟢 ${source.name}: Signal verfügbar`
                );
            }
            if (previous.ready && !source.ready) {
                addEvent(
                    "warning",
                    `🔴 ${source.name}: Signal verloren`
                );
            }
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
            `⚪ ${previous.name}: Quelle deaktiviert oder entfernt`
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

    if (lastDashboardState.streamRunning !== null) {

        if (
            !lastDashboardState.streamRunning &&
            stream.running
        ) {

            addEvent(
                "success",
                "🟢 Stream gestartet"
            );

        }

        if (
            lastDashboardState.streamRunning &&
            !stream.running
        ) {

            addEvent(
                "warning",
                "🔴 Stream gestoppt"
            );

        }

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

    if (
        lastDashboardState.mediamtx !== null
    ) {

        if (
            !lastDashboardState.mediamtx &&
            services.mediamtx.online
        ) {

            addEvent(
                "success",
                "📡 MediaMTX verbunden"
            );

        }

        if (
            lastDashboardState.mediamtx &&
            !services.mediamtx.online
        ) {

            addEvent(
                "warning",
                "📡 MediaMTX getrennt"
            );

        }

    }

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

	        if (previous !== undefined) {

	            if (
	                !previous &&
	                output.running
	            ) {

	                addEvent(
	                    "success",
	                    "📺 " +
	                    output.name +
	                    " gestartet"
	                );

	            }

	            if (
	                previous &&
	                !output.running
	            ) {

	                addEvent(
	                    "warning",
	                    "📺 " +
	                    output.name +
	                    " gestoppt"
	                );

	            }

	        }

	        lastDashboardState.streamOutputs[
	            output.name
	        ] = output.running;

	    }

	}
