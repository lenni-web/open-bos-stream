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
        data.media_storage,
        data.sources ?? []
    );

    updateSourceDiagnostics(data.sources ?? []);

    updateViewerDiagnostics();

	checkServiceEvents(
	    data.services
	);

    updateMultiSources(
        data.sources ?? []
    );

    checkSourceEvents(
        data.sources ?? []
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

function updateStreamDiagnostics(stream, storage, sources = []) {
    const diagnostics = stream?.diagnostics;

    updateValue(
        "stream-diagnostic-primary",
        sources[0]?.name || "Keine aktive Quelle"
    );

    if (diagnostics) {
        updateValue(
            "stream-diagnostic-mode",
            diagnostics.mode === "rtmp_copy_repair"
                ? "RTMP Copy mit Zeitstempel-Reparatur"
                : (
                    diagnostics.mode === "managed_ffmpeg"
                        ? "Interner FFmpeg-Dienst"
                        : "MediaMTX direkt"
                )
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
            diagnostics.restart_count_total !==
                diagnostics.restart_count
                ? (
                    `${diagnostics.restart_count} aktuell · ` +
                    `${diagnostics.restart_count_total} gesamt`
                )
                : String(diagnostics.restart_count)
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

        const probe = diagnostics.probe;
        updateValue(
            "stream-probe-fps",
            probe?.available
                ? (
                    `${probe.average_fps.toFixed(2)} fps ` +
                    `(nominal ${probe.nominal_fps.toFixed(2)})`
                )
                : "Noch keine Messung"
        );
        updateValue(
            "stream-probe-timebase",
            probe?.time_base || "—"
        );
        updateValue(
            "stream-probe-timestamps",
            probe?.available
                ? (
                    probe.backwards_dts > 0
                        ? `${probe.backwards_dts} rückwärts`
                        : `${probe.packets_checked} Pakete geprüft`
                )
                : "—"
        );
        updateValue(
            "stream-probe-bitrate",
            probe?.available
                ? formatBitsPerSecond(probe.bitrate_bps)
                : "—"
        );
        updateValue(
            "stream-probe-packet-timing",
            probe?.available
                ? (
                    `${probe.packet_gaps} Lücken · ` +
                    `${probe.timing_jitter_ms.toFixed(1)} ms Jitter · ` +
                    `max. ${probe.max_gap_ms.toFixed(0)} ms`
                )
                : "—"
        );
        updateValue(
            "stream-stable-for",
            diagnostics.stable_for_seconds > 0
                ? formatRecordingDuration(
                    diagnostics.stable_for_seconds
                )
                : "Noch nicht stabil"
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
    for (
        const warning
        of diagnostics?.probe?.warnings || []
    ) {
        alerts.push(warning.message);
    }
    const timestampProblem =
        (diagnostics?.probe?.warnings || []).some(
            warning => [
                "non_monotonic_dts",
                "missing_dts",
                "implausible_frame_rate",
                "irregular_packet_timing",
            ].includes(warning.code)
        );
    if (
        timestampProblem &&
        diagnostics?.mode !== "rtmp_copy_repair"
    ) {
        alerts.push(
            "Empfehlung: Quellenprofil „RTMP Copy mit " +
            "Zeitstempel-Reparatur“ aktivieren."
        );
    }

    const alertBox = document.getElementById("system-alerts");
    if (alertBox) {
        alertBox.hidden = alerts.length === 0;
        alertBox.textContent = alerts.join(" ");
    }
}

function updateSourceDiagnostics(sources) {
    const container = document.getElementById(
        "source-diagnostic-list"
    );
    if (!container) {
        return;
    }
    if (!sources.length) {
        container.innerHTML =
            '<p class="empty-state">Keine aktive Quelle konfiguriert.</p>';
        return;
    }

    container.innerHTML = sources.map(source => {
        const state = source.ready
            ? "Bereit"
            : (source.online ? "Signal erkannt" : "Offline");
        const signal = source.ready
            ? `${source.codec || "Stream"} · ` +
              `${source.width || "?"}×${source.height || "?"}`
            : "Kein ausgabefähiges Signal";
        return `
            <article class="source-diagnostic-item">
                <div>
                    <strong>${escapeHTML(source.name)}</strong>
                    <small>${escapeHTML(source.drone_type || "Drohnen-Typ nicht angegeben")}</small>
                </div>
                <dl>
                    <div><dt>Status</dt><dd>${escapeHTML(state)}</dd></div>
                    <div><dt>Typ / Profil</dt><dd>${escapeHTML(source.type)} · ${escapeHTML(source.profile)}</dd></div>
                    <div><dt>Signal</dt><dd>${escapeHTML(signal)}</dd></div>
                    <div><dt>Viewer</dt><dd>${Number(source.viewers || 0)}</dd></div>
                </dl>
            </article>
        `;
    }).join("");
}

function updateViewerDiagnostics() {
    const diagnostics =
        window.livePlayer?.diagnostics?.();

    if (!diagnostics) {
        return;
    }

    updateValue(
        "viewer-connection-state",
        diagnostics.protocol
            ? `${diagnostics.protocol.toUpperCase()} · ` +
                diagnostics.connection_state
            : "Kein Player aktiv"
    );
    updateValue(
        "viewer-network",
        diagnostics.protocol === "webrtc"
            ? (
                `${diagnostics.packets_lost} verloren / ` +
                `${diagnostics.packets_received} empfangen · ` +
                `${diagnostics.jitter_ms.toFixed(1)} ms · ` +
                formatBitsPerSecond(diagnostics.bitrate_bps)
            )
            : "Nur für WebRTC verfügbar"
    );
    updateValue(
        "viewer-dropped-frames",
        `${diagnostics.frames_dropped} von ` +
        `${diagnostics.frames_decoded}`
    );
}

function updateDashboardSystemInfo(info) {

    if (!info) {
        return;
    }

    document.getElementById("system-app-name").textContent =
        info.application.name;

    document.getElementById("system-app-version").textContent =
        info.application.version;

    document.getElementById("system-installation-profile").textContent =
        info.installation_profile === "server"
            ? "Server"
            : "Lokal / Raspberry Pi";

    const serverAccess = info.server_access ?? {};
    document.getElementById("system-public-domain").textContent =
        serverAccess.public_domain || "Nicht konfiguriert";
    document.getElementById("system-https-mode").textContent =
        serverAccess.https_enabled === "yes" ? "Caddy aktiv" : "Deaktiviert";
    document.getElementById("system-webrtc-mode").textContent =
        serverAccess.webrtc_mode === "public" ? "Öffentlich" : "Lokal";
    document.getElementById("system-firewall-mode").textContent =
        serverAccess.firewall_mode === "configure"
            ? "Durch Open BOS verwaltet"
            : "Extern / unverändert";

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
