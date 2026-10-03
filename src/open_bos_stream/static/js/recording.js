// ==========================================================
// Recording Helper
// ==========================================================
let lastRecordingState = null;
let lastRecordingOutcome = null;
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
        !recording.active &&
        !recording.end_reason
    ) {

        addEvent(
            "warning",
            "⏹ Aufnahme beendet"
        );

    }

}

const outcomeKey = recording.finished_at
    ? `${recording.finished_at}:${recording.end_reason}`
    : null;
if (outcomeKey && outcomeKey !== lastRecordingOutcome) {
    if (recording.end_reason === "stream_interrupted") {
        addEvent(
            "warning",
            "⚠ Aufnahme durch Streamabbruch beendet und gespeichert"
        );
    } else if (recording.end_reason === "failed") {
        addEvent(
            "error",
            "⛔ Abgebrochene Aufnahme war nicht verwertbar"
        );
    } else if (recording.end_reason === "storage_low") {
        addEvent(
            "warning",
            "⚠ Aufnahme wegen Speichermangel beendet und gespeichert"
        );
    }
    lastRecordingOutcome = outcomeKey;
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

            end_reason:
                recording.end_reason,

            end_message:
                recording.end_message,

            completed_filename:
                recording.completed_filename,

            finished_at:
                recording.finished_at,

            mode:
                recording.mode ?? "manual",

            automatic_waiting:
                Boolean(recording.automatic_waiting),

            automatic_error:
                recording.automatic_error,

            full_quality:
                recording.full_quality,

        };

    }

    // -----------------------------------------------------
    // Sidebar
    // -----------------------------------------------------

    updateValue(

        "recording-status",

        active
            ? "🟢 Aktiv"
            : recording.end_reason === "stream_interrupted"
                ? "🟠 Durch Streamabbruch beendet"
                : recording.end_reason === "failed"
                    ? "🔴 Aufnahme fehlgeschlagen"
                    : recording.end_reason === "storage_low"
                        ? "🟠 Wegen Speichermangel beendet"
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

        const automatic = recording.mode === "automatic";

        toggle.textContent =
            automatic
                ? (active ? "⏺ Automatische Aufnahme" : "◷ Automatik wartet")
                : active
                ? "⏹ Aufnahme stoppen"
                : "⏺ Aufnahme starten";

        toggle.disabled = automatic;

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
        const automatic = recording.mode === "automatic";
        mediaToggle.textContent = automatic
            ? (active ? "⏺ Automatische Aufnahme" : "◷ Automatik wartet")
            : active
            ? "⏹ Aufnahme stoppen"
            : "⏺ Aufnahme starten";
        mediaToggle.disabled = automatic;
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
