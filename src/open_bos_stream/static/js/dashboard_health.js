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

    const temperature = Number.isFinite(system.temperature)
        ? `${system.temperature.toFixed(1)} °C`
        : "Temperatur n/v";

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
        temperature
    );

    updateValue(
        "header-system-summary",
        "System · CPU " +
        system.cpu.toFixed(1) +
        " % · RAM " +
        system.ram.toFixed(1) +
        " % · " +
        temperature
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

    updateServiceCard(
        "capture",
        services.capture.online,
        services.capture.name
    );

    updateServiceCard(
        "ffmpeg",
        services.ffmpeg.online,
        services.ffmpeg.name
    );

    updateServiceCard(
        "mediamtx",
        services.mediamtx.online,
        services.mediamtx.online
            ? "Dienst erreichbar"
            : "Dienst nicht erreichbar"
    );

}

function updateServiceCard(
    service,
    online,
    description
) {
    const card =
        document.getElementById(
            `service-card-${service}`
        );

    if (card) {
        card.classList.toggle(
            "is-online",
            online
        );
        card.classList.toggle(
            "is-offline",
            !online
        );
    }

    updateValue(
        `system-${service}`,
        `${online ? "Online" : "Offline"} · ${description}`
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
        system.cpu > 0
            ? `${system.cpu.toFixed(1)} %`
            : "< 0,1 %"
    );

    updateValue(
        "system-ram",
        system.ram.toFixed(1) +
        " %"
    );

    updateValue(
        "system-temp",
        Number.isFinite(system.temperature)
            ? `${system.temperature.toFixed(1)} °C`
            : "Nicht verfügbar"
    );

}

async function copySystemDiagnostics() {
    const feedback =
        document.getElementById(
            "system-feedback"
        );

    if (!window.dashboard) {
        if (feedback) {
            feedback.textContent =
                "Diagnosedaten sind noch nicht verfügbar.";
        }
        return;
    }

    const diagnostics = {
        generated_at: new Date().toISOString(),
        application:
            window.dashboard.system_info?.application,
        hardware:
            window.dashboard.system_info?.hardware,
        operating_system:
            window.dashboard.system_info?.operating_system,
        runtime:
            window.dashboard.system_info?.runtime,
        network:
            window.dashboard.system_info?.network,
        services:
            window.dashboard.services,
        system:
            window.dashboard.system,
        stream:
            window.dashboard.stream,
        media_storage:
            window.dashboard.media_storage,
    };

    try {
        await navigator.clipboard.writeText(
            JSON.stringify(
                diagnostics,
                null,
                2
            )
        );

        if (feedback) {
            feedback.textContent =
                "Diagnoseinformationen wurden kopiert.";
        }
    } catch (error) {
        if (feedback) {
            feedback.textContent =
                "Diagnoseinformationen konnten nicht kopiert werden.";
        }
    }
}

function downloadSystemDiagnostics() {
    window.location.href = "/dashboard/diagnostics";
}
