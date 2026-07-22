// ==========================================================
// Health
// ==========================================================

function updateDashboardHealth(data) {

    updateDashboardHeader(
        data.services,
        data.system
    );

    updateDashboardServices(
        data.services
    );

    updateDashboardSystem(
        data.system
    );

}

// ==========================================================
// Header
// ==========================================================

function updateDashboardHeader(
    services,
    system
) {

    if (!services || !system) {
        return;
    }

    updateClass(
        "mediamtx-dot",
        services.mediamtx.online
            ? "status-dot status-green"
            : "status-dot status-red"
    );

    updateValue(
        "mediamtx-text",
        services.mediamtx.online
            ? "MediaMTX"
            : "Offline"
    );

    updateValue(
        "header-cpu",
        "CPU " +
        system.cpu.toFixed(1) +
        "%"
    );

    updateValue(
        "header-ram",
        "RAM " +
        system.ram.toFixed(1) +
        "%"
    );

    updateValue(
        "header-temp",
        system.temperature.toFixed(1) +
        " °C"
    );

}

// ==========================================================
// Services
// ==========================================================

function updateDashboardServices(
    services
) {

    if (!services) {
        return;
    }

    updateValue(
        "system-capture",
        (services.capture.online ? "🟢 " : "🔴 ") +
        services.capture.name
    );

    updateValue(
        "system-ffmpeg",
        (services.ffmpeg.online ? "🟢 " : "🔴 ") +
        services.ffmpeg.name
    );

    updateValue(
        "system-mediamtx",
        (services.mediamtx.online ? "🟢 " : "🔴 ") +
        "MediaMTX"
    );

}

// ==========================================================
// System
// ==========================================================

function updateDashboardSystem(
    system
) {

    if (!system) {
        return;
    }

    updateValue(
        "system-cpu",
        system.cpu.toFixed(1) +
        " %"
    );

    updateValue(
        "system-ram",
        system.ram.toFixed(1) +
        " %"
    );

    updateValue(
        "system-temp",
        system.temperature.toFixed(1) +
        " °C"
    );

}

