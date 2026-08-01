// ==========================================================
// System Card
// ==========================================================

function updateSystemCard(health) {

    const ffmpeg =
        document.getElementById(
            "system-ffmpeg"
        );

    const mediamtx =
        document.getElementById(
            "system-mediamtx"
        );

    const capture =
        document.getElementById(
            "system-capture"
        );

    if (!ffmpeg) {
        return;
    }

    ffmpeg.textContent =
        (health.ffmpeg.online ? "🟢 " : "🔴 ") +
        health.ffmpeg.name;

    mediamtx.textContent =
        (health.mediamtx.online ? "🟢 " : "🔴 ") +
        "MediaMTX";

    capture.textContent =
        (health.capture.online ? "🟢 " : "🔴 ") +
        health.capture.name;

    document.getElementById(
        "system-cpu"
    ).textContent =
        health.system.cpu > 0
            ? health.system.cpu + " %"
            : "< 0,1 %";

    document.getElementById(
        "system-ram"
    ).textContent =
        health.system.ram +
        " %";

    document.getElementById(
        "system-temp"
    ).textContent =
        Number.isFinite(health.system.temperature)
            ? health.system.temperature + " °C"
            : "Nicht verfügbar";

}

// ==========================================================
// Dashboard Metrics
// ==========================================================

function updateStatusCard(health) {

    const cpu =
        document.getElementById(
            "status-cpu"
        );

    if (!cpu) {
        return;
    }

    document.getElementById(
        "status-cpu"
    ).textContent =
        health.system.cpu +
        " %";

    document.getElementById(
        "status-ram"
    ).textContent =
        health.system.ram +
        " %";

    document.getElementById(
        "status-temp"
    ).textContent =
        Number.isFinite(health.system.temperature)
            ? health.system.temperature + " °C"
            : "Nicht verfügbar";

}

// ==========================================================
// Refresh
// ==========================================================

async function refreshHealth() {

    try {

        const health =
            await api.health();

        updateSystemCard(
            health
        );

        updateStatusCard(
            health
        );

    } catch (err) {

        console.error(
            "Health:",
            err
        );

    }

}
