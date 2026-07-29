// ==========================================================
// Dashboard Refresh
// ==========================================================

async function refreshDashboard() {

    try {

        const dashboard =
            await api.dashboard();

        window.dashboard = dashboard;

        updateDashboard(
            dashboard
        );

    } catch (err) {

        console.error(
            "Dashboard:",
            err
        );

        const refreshStatus =
            document.getElementById(
                "system-refresh-status"
            );

        if (refreshStatus) {
            refreshStatus.textContent =
                "Verbindung unterbrochen";
            refreshStatus.classList.add(
                "is-error"
            );
        }

    }

}

// ==========================================================
// Dashboard
// ==========================================================

function updateDashboard(data) {

    if (!data) {
        return;
    }

    const refreshStatus =
        document.getElementById(
            "system-refresh-status"
        );

    if (refreshStatus) {
        refreshStatus.textContent = "Live";
        refreshStatus.classList.remove(
            "is-error"
        );
    }

    updateDashboardHealth(
        data
    );

	updateDashboardSystemInfo(
	    data.system_info
	);

    updateStreamDiagnostics(
        data.stream,
        data.media_storage
    );

	checkServiceEvents(
	    data.services
	);

	updateDashboardStream(
	    data.stream,
	    data.recording
	);

	checkStreamEvents(
	    data.stream
	);

	checkStreamOutputEvents(
	    data.stream_outputs
	);

    updateRecordingUI(
        data.recording
    );

    updateStreamOutputs(
        data.stream_outputs
    );

}

function updateStreamDiagnostics(stream, storage) {
    const diagnostics = stream?.diagnostics;

    if (diagnostics) {
        updateValue(
            "stream-diagnostic-mode",
            diagnostics.mode === "managed_ffmpeg"
                ? "Interner FFmpeg-Dienst"
                : "MediaMTX direkt"
        );
        updateValue(
            "stream-diagnostic-input",
            diagnostics.input || "Nicht konfiguriert"
        );
        updateValue(
            "stream-diagnostic-signal",
            `${diagnostics.configured_width}×` +
            `${diagnostics.configured_height} · ` +
            `${diagnostics.configured_fps} fps · ` +
            `${diagnostics.configured_format}`
        );
        updateValue(
            "stream-diagnostic-encoder",
            diagnostics.encoder
        );
        updateValue(
            "stream-diagnostic-output",
            diagnostics.output
        );
        updateValue(
            "stream-diagnostic-restarts",
            String(diagnostics.restart_count)
        );
        updateValue(
            "stream-diagnostic-exit",
            diagnostics.exit_status === null
                ? "—"
                : String(diagnostics.exit_status)
        );
        updateValue(
            "stream-diagnostic-mediamtx",
            stream.ready
                ? `${stream.codec || "Stream"} · ` +
                    `${stream.width}×${stream.height} · ` +
                    `${stream.viewers} Leser`
                : "Kein Publisher erkannt"
        );

        const state =
            document.getElementById(
                "stream-diagnostic-state"
            );
        if (state) {
            state.textContent =
                `${diagnostics.active_state} / ` +
                diagnostics.sub_state;
            state.classList.toggle(
                "is-error",
                Boolean(diagnostics.last_error) &&
                !stream.running
            );
        }

        const error =
            document.getElementById(
                "stream-diagnostic-error"
            );
        if (error) {
            const details = diagnostics.last_error_details;
            error.hidden = !details;
            error.textContent = details
                ? `${details.timestamp} · ${details.category}: ` +
                    `${details.message} — ${details.advice}`
                : "";
        }
    }

    if (storage) {
        updateValue(
            "system-storage-free",
            formatBytes(storage.free_bytes)
        );
        updateValue(
            "system-storage-percent",
            `${storage.used_percent.toFixed(1)} % belegt`
        );
        updateValue(
            "system-storage-usage",
            `${formatBytes(storage.used_bytes)} von ` +
            `${formatBytes(storage.total_bytes)} belegt`
        );
        updateValue(
            "system-storage-media",
            `${storage.recordings} Aufnahmen · ` +
            `${storage.snapshots} Snapshots · ` +
            formatBytes(storage.media_bytes)
        );

        const bar =
            document.getElementById(
                "system-storage-bar"
            );
        if (bar) {
            bar.style.width =
                `${Math.min(storage.used_percent, 100)}%`;
            bar.classList.toggle(
                "is-warning",
                storage.used_percent >= 85
            );
        }
    }

    const alerts = [];
    if ((diagnostics?.restart_count || 0) >= 5) {
        alerts.push(
            `${diagnostics.restart_count} Dienstneustarts erkannt.`
        );
    }
    if ((window.dashboard?.system?.temperature || 0) >= 75) {
        alerts.push("Systemtemperatur ist kritisch hoch.");
    }
    if ((storage?.used_percent || 0) >= 85) {
        alerts.push("Weniger als 15 % Speicherplatz verfügbar.");
    }

    const alertBox = document.getElementById("system-alerts");
    if (alertBox) {
        alertBox.hidden = alerts.length === 0;
        alertBox.textContent = alerts.join(" ");
    }
}

function updateDashboardSystemInfo(info) {

    if (!info) {
        return;
    }

    document.getElementById("system-app-name").textContent =
        info.application.name;

    document.getElementById("system-app-version").textContent =
        info.application.version;

    document.getElementById("system-hardware-model").textContent =
        info.hardware.model;

    document.getElementById("system-hardware-arch").textContent =
        info.hardware.architecture;

    document.getElementById("system-os-system").textContent =
        info.operating_system.system;

    document.getElementById("system-os-distribution").textContent =
        info.operating_system.distribution;

    document.getElementById("system-os-kernel").textContent =
        info.operating_system.kernel;

    document.getElementById("system-runtime-python").textContent =
        info.runtime.python;

    document.getElementById("system-runtime-ffmpeg").textContent =
        info.runtime.ffmpeg;

	document.getElementById("system-network-hostname").textContent =
	    info.network.hostname;

	document.getElementById("system-network-interface").textContent =
	    info.network.interface;

	document.getElementById("system-network-ipv4").textContent =
	    info.network.ipv4;

	document.getElementById("system-network-mac").textContent =
	    info.network.mac;
}
