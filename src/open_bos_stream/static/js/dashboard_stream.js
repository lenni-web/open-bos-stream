// ==========================================================
// Stream
// ==========================================================

function updateDashboardStream(
    stream,
    recording
) {

    if (!stream) {
        return;
    }

    const streamState =

        streamLabel(stream);

updateValue(
    "video-stream-state",
    streamState
);

updateValue(
    "video-viewers",
    "👤 " + stream.viewers
);

const recordingElement =

    document.getElementById(
        "video-recording-time"
    );

if (recordingElement) {

    if (recording?.active) {

        recordingElement.style.display =
            "inline";

        recordingElement.textContent =

            "⏺ REC " +

            formatRecordingDuration(
                recording.duration
            );

    } else {

        recordingElement.style.display =
            "none";

    }

}

    updateValue(
        "status-stream",
        stream.running
            ? "🟢 Aktiv"
            : "⚪ Gestoppt"
    );

    updateStreamButton(
        stream
    );

    updateDashboardStreamCard(
        stream
    );

const video =
    document.getElementById(
        "live-video"
    );

const placeholder =
    document.getElementById(
        "video-placeholder"
    );

const videoContainer =
    document.getElementById(
        "video-container"
    );

if (
    video &&
    placeholder &&
    videoContainer
) {

	if (
	    stream.running &&
	    stream.ready
	) {

	    const viewerProtocol =
	        currentConfig?.stream?.viewer?.protocol ??
	        "hls";

    	window.livePlayer.play(
	        stream.name,
	        viewerProtocol
	    );

	    videoContainer.style.display =
	        "block";

	    placeholder.style.display =
	        "none";

	} else {

	    window.livePlayer.stop();

	    videoContainer.style.display =
	        "none";

	    placeholder.style.display =
	        "flex";
		}
	}
}

function updateStreamButton(
    stream
) {

    const button =
        document.getElementById(
            "stream-toggle"
        );

    if (!button) {
        return;
    }

    button.textContent =
        stream.running
            ? "■ Stream stoppen"
            : "▶ Stream starten";

    button.classList.toggle(
        "bos-button-red",
        stream.running
    );

    button.classList.toggle(
        "bos-button-green",
        !stream.running
    );

}

function updateDashboardStreamCard(
    stream
) {

    if (!stream) {
        return;
    }

    updateValue(
        "stream-status",
        stream.running
            ? "🟢 Aktiv"
            : "⚪ Gestoppt"
    );

    updateValue(
        "stream-protocol",
        stream.protocol.toUpperCase()
    );

    updateValue(
        "stream-source",
        formatStreamSource(
            stream.source
        )
    );

    updateValue(
        "stream-codec",
        stream.codec ?? "—"
    );

    updateValue(
        "stream-resolution",
        stream.width > 0
            ? stream.width +
              " × " +
              stream.height
            : "—"
    );

    updateValue(
        "stream-viewers",
        String(
            stream.viewers
        )
    );

    updateValue(
        "stream-received",
        formatBytes(
            stream.bytes_received
        )
    );

    updateValue(
        "stream-sent",
        formatBytes(
            stream.bytes_sent
        )
    );

    updateValue(
        "stream-uptime",
        formatUptime(
            stream.online_time
        )
    );

const now =
    Date.now();

const elapsedSeconds =
    lastStreamTimestamp == null
        ? 0
        : (
            now -
            lastStreamTimestamp
        ) / 1000;

updateValue(
    "stream-rx-rate",
    formatBitrate(
        stream.bytes_received,
        lastStreamStats?.bytes_received,
        elapsedSeconds
    )
);

updateValue(
    "stream-tx-rate",
    formatBitrate(
        stream.bytes_sent,
        lastStreamStats?.bytes_sent,
        elapsedSeconds
    )
);

lastStreamStats = {

    bytes_received:
        stream.bytes_received,

    bytes_sent:
        stream.bytes_sent,

};

lastStreamTimestamp =
    now;

}

function streamLabel(
    stream
) {

    if (!stream.running) {

        return "🔴 Offline";

    }

    switch (
        stream.protocol
    ) {

        case "rtsp":
            return "🟢 RTSP";

        case "webrtc":
            return "🟣 WebRTC";

        case "hls":
            return "🟠 HLS";

        default:
            return "⚪ Unbekannt";

    }

}

function formatStreamSource(
    source
) {

    switch (source) {

        case "rtspSession":
            return "RTSP Publisher";

        case "webRTCSession":
            return "WebRTC";

        case "hlsMuxer":
            return "HLS";

        case "rtmpConn":
            return "RTMP";

        case null:
        case undefined:
            return "—";

        default:
            return source;

    }

}

function formatBytes(
    bytes
) {

    if (bytes == null) {

        return "—";

    }

    if (bytes < 1024) {

        return bytes + " B";

    }

    if (bytes < 1024 * 1024) {

        return (
            (bytes / 1024).toFixed(1) +
            " kB"
        );

    }

    if (bytes < 1024 * 1024 * 1024) {

        return (
            (
                bytes /
                (1024 * 1024)
            ).toFixed(1) +
            " MB"
        );

    }

    return (

        (
            bytes /
            (1024 * 1024 * 1024)
        ).toFixed(1) +

        " GB"

    );

}

function formatBitrate(
    currentBytes,
    previousBytes,
    elapsedSeconds
) {

    if (
        previousBytes == null ||
        elapsedSeconds <= 0
    ) {
        return "—";
    }

    const deltaBytes =
        Math.max(
            0,
            currentBytes -
            previousBytes
        );

    const bitsPerSecond =
        (deltaBytes * 8) /
        elapsedSeconds;

    if (bitsPerSecond < 1000) {

        return (
            bitsPerSecond.toFixed(0) +
            " bit/s"
        );

    }

    if (bitsPerSecond < 1000000) {

        return (
            (bitsPerSecond / 1000).toFixed(1) +
            " kbit/s"
        );

    }

    return (
        (bitsPerSecond / 1000000).toFixed(2) +
        " Mbit/s"
    );

}

function formatUptime(
    onlineTime
) {

    if (!onlineTime) {

        return "—";

    }

    const started =
        new Date(
            onlineTime
        );

    const seconds =
        Math.max(
            0,
            Math.floor(
                (
                    Date.now() -
                    started.getTime()
                ) / 1000
            )
        );

    const hours =
        Math.floor(
            seconds / 3600
        );

    const minutes =
        Math.floor(
            (seconds % 3600) / 60
        );

    const secs =
        seconds % 60;

    return (

        String(hours)
            .padStart(2, "0") +

        ":" +

        String(minutes)
            .padStart(2, "0") +

        ":" +

        String(secs)
            .padStart(2, "0")

    );

}

function formatRecordingDuration(
    seconds
) {

    seconds =

        Number(seconds ?? 0);

    const hours =

        Math.floor(
            seconds / 3600
        );

    const minutes =

        Math.floor(
            (seconds % 3600) / 60
        );

    const secs =

        seconds % 60;

    return (

        String(hours)
            .padStart(2, "0") +

        ":" +

        String(minutes)
            .padStart(2, "0") +

        ":" +

        String(secs)
            .padStart(2, "0")

    );

}

// ==========================================================
// LivePlayer Status
// ==========================================================

window.livePlayer.onStateChanged((event) => {

    const playerState =
        typeof event === "string"
            ? event
            : event.state;

    const live =
        document.getElementById(
            "video-live"
        );

    const status =
        document.getElementById(
            "video-status"
        );

    if (!live || !status) {
        return;
    }

    switch (playerState) {

        case "connecting":

            status.style.display =
                "inline";

            status.textContent =
                "🔄 Verbinde...";

            live.style.display =
                "none";

            break;

        case "playing":

            status.style.display =
                "none";

            live.style.display =
                "inline";

            break;

        case "error":

            status.style.display =
                "inline";

            status.textContent =
                "⚠ Offline";

            live.style.display =
                "none";

            break;

        case "idle":
        default:

            status.style.display =
                "none";

            live.style.display =
                "none";

    }

});