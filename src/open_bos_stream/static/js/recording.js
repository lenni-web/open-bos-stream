// ==========================================================
// Recording Helper
// ==========================================================
let lastRecordingState = null;
let recordingTimerState = {
    active: false,
    baseSeconds: 0,
    synchronizedAt: performance.now(),
};

function formatDuration(seconds) {

    const h =
        Math.floor(seconds / 3600);

    const m =
        Math.floor(
            (seconds % 3600) / 60
        );

    const s =
        seconds % 60;

    return (

        String(h).padStart(2, "0") +

        ":" +

        String(m).padStart(2, "0") +

        ":" +

        String(s).padStart(2, "0")

    );

}

function synchronizeRecordingTimer(recording) {
    recordingTimerState = {
        active: Boolean(recording?.active),
        baseSeconds: Math.max(
            0,
            Number(recording?.duration ?? 0)
        ),
        synchronizedAt: performance.now(),
    };
}

function currentRecordingDuration() {
    if (!recordingTimerState.active) {
        return recordingTimerState.baseSeconds;
    }

    return recordingTimerState.baseSeconds + Math.floor(
        (performance.now() - recordingTimerState.synchronizedAt) / 1000
    );
}

function updateRecordingTimer() {
    if (!recordingTimerState.active) {
        return;
    }

    const seconds = currentRecordingDuration();
    const duration = formatDuration(seconds);

    if (window.dashboard?.recording) {
        window.dashboard.recording.duration = seconds;
    }

    updateValue("recording-duration", duration);
    updateValue("media-recording-duration", duration);

    const overlayDuration = document.getElementById("video-duration");
    if (overlayDuration) {
        overlayDuration.textContent = duration;
    }

    const recordingElement = document.getElementById(
        "video-recording-time"
    );
    if (recordingElement) {
        recordingElement.textContent = `⏺ REC ${duration}`;
    }
}

// ==========================================================
// Recording Refresh
// ==========================================================


// ==========================================================
// Recording UI
// ==========================================================

function updateRecordingUI(
    recording
) {

    if (!recording) {
        return;
    }

    // -----------------------------------------------------
// Event Log
// -----------------------------------------------------

if (lastRecordingState !== null) {

    if (
        !lastRecordingState &&
        recording.active
    ) {

        addEvent(
            "success",
            "⏺ Aufnahme gestartet"
        );

    }

    if (
        lastRecordingState &&
        !recording.active
    ) {

        addEvent(
            "warning",
            "⏹ Aufnahme beendet"
        );

    }

}

lastRecordingState =
    recording.active;

    const active =
        recording.active;

    synchronizeRecordingTimer(recording);

    const duration =
        formatDuration(
            recording.duration ?? 0
        );

    // -----------------------------------------------------
    // Dashboard synchron halten
    // -----------------------------------------------------

    if (window.dashboard) {

        window.dashboard.recording = {

            active: active,

            duration:
                recording.duration ?? 0,

            filename:
                recording.filename,

            pid:
                recording.pid,

            source_id:
                recording.source_id,

            source_name:
                recording.source_name,

        };

    }

    // -----------------------------------------------------
    // Sidebar
    // -----------------------------------------------------

    updateValue(

        "recording-status",

        active
            ? "🟢 Aktiv"
            : "⚪ Nicht aktiv"

    );

    updateValue(

        "recording-duration",

        duration

    );

    updateValue(

        "recording-file",

        recording.filename ?? "—"

    );

    // -----------------------------------------------------
    // Dashboard
    // -----------------------------------------------------

    updateValue(

        "status-recording",

        active
            ? "🟢 Aktiv"
            : "⚪ Nicht aktiv"

    );

    // -----------------------------------------------------
    // Video Overlay
    // -----------------------------------------------------

    const rec =
        document.getElementById(
            "video-rec"
        );

    if (rec) {

        rec.style.display =
            active
                ? ""
                : "none";

    }

    const overlayDuration =
        document.getElementById(
            "video-duration"
        );

    if (overlayDuration) {

        overlayDuration.style.display =
            active
                ? ""
                : "none";

        overlayDuration.textContent =
            duration;

    }

    // -----------------------------------------------------
    // Buttons
    // -----------------------------------------------------

    const toggle =
        document.getElementById(
            "recording-toggle"
        );

    if (toggle) {

        toggle.textContent =
            active
                ? "⏹ Aufnahme stoppen"
                : "⏺ Aufnahme starten";

        toggle.classList.toggle(
            "bos-button-red",
            active
        );

        toggle.classList.toggle(
            "bos-button",
            !active
        );

    }

    const mediaToggle = document.getElementById(
        "media-recording-toggle"
    );
    if (mediaToggle) {
        mediaToggle.textContent = active
            ? "⏹ Aufnahme stoppen"
            : "⏺ Aufnahme starten";
        mediaToggle.classList.toggle("bos-button-red", active);
    }

    updateValue(
        "media-recording-duration",
        active ? duration : ""
    );

    const selectedName = active
        ? recording.source_name
        : window.dashboard?.media_capture?.source_name;
    updateValue(
        "media-capture-source-name",
        selectedName || "Keine Quelle ausgewählt"
    );

    const startButton =
        document.getElementById(
            "sidebar-recording-start"
        );

    const stopButton =
        document.getElementById(
            "sidebar-recording-stop"
        );

    if (startButton) {

        startButton.style.display =
            active
                ? "none"
                : "";

    }

    if (stopButton) {

        stopButton.style.display =
            active
                ? ""
                : "none";

    }

}

// ==========================================================
// Toggle
// ==========================================================

async function toggleRecording() {

    const active =
        window.dashboard
            ?.recording
            ?.active;

    if (active) {

        await stopRecording();

    } else {

        await startRecording();

    }

}

// ==========================================================
// Start
// ==========================================================

async function startRecording() {

    const result =
        await api.startRecording();

    if (!result.success) {

        alert(

            result.error ??

            "Aufnahme konnte nicht gestartet werden."

        );

        return;

    }

    await refreshDashboard();

    await refreshRecordingLibrary();

}

// ==========================================================
// Stop
// ==========================================================

async function stopRecording() {

    const result =
        await api.stopRecording();

    if (!result.success) {

        alert(

            result.error ??

            "Aufnahme konnte nicht beendet werden."

        );

        return;

    }

    await refreshDashboard();

    await refreshRecordingLibrary();

}
