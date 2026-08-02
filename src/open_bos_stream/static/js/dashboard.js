// ==========================================================
// Dashboard Refresh
// ==========================================================

const sourceProbeResults = new Map();
let sourceProbeRunning = null;

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

    updateMultiSources(
        data.sources ?? []
    );

    updateSourceDiagnostics(data.sources ?? []);

    updateViewerDiagnostics();

    updateTestLogging(data);

	checkServiceEvents(
	    data.services
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

    updateMediaCaptureBar(data.media_capture);

    updateStreamOutputs(
        data.stream_outputs
    );

}

function updateMediaCaptureBar(mediaCapture) {
    const bar = document.getElementById("media-capture-bar");
    if (!bar) {
        return;
    }
    bar.hidden = false;
    updateValue(
        "media-capture-source-name",
        mediaCapture?.source_name || "Keine Quelle ausgewählt"
    );
    const snapshot = document.getElementById("media-snapshot-button");
    const recording = document.getElementById("media-recording-toggle");
    if (snapshot) snapshot.disabled = !mediaCapture?.ready;
    if (recording && !window.dashboard?.recording?.active) {
        recording.disabled = !mediaCapture?.ready;
    }
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
    if ((window.dashboard?.system?.temperature ?? 0) >= 75) {
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

    const playerDiagnostics =
        window.sourcePlayerDiagnostics?.() ?? {};
    container.innerHTML = sources.map(source => {
        const state = source.ready
            ? "Bereit"
            : (source.online ? "Signal erkannt" : "Offline");
        const signal = source.ready
            ? `${source.codec || "Stream"} · ` +
              `${source.width || "?"}×${source.height || "?"}`
            : "Kein ausgabefähiges Signal";
        const runtime = source.runtime;
        const health = source.health || {
            code: "unknown",
            label: "Status unbekannt",
            message: "Keine Gesundheitsbewertung verfügbar.",
        };
        const probeState = sourceProbeResults.get(source.id);
        const player = playerDiagnostics[source.id];
        let runtimeState = "FFmpeg-Daten nicht verfügbar";
        let runtimeMetrics = "";
        let restartMetric = "";
        let playerMetrics = "";
        if (!source.managed) {
            runtimeState = "Direkter MediaMTX-Empfang";
        } else if (runtime) {
            const states = {
                running: "FFmpeg verarbeitet",
                starting: "FFmpeg startet",
                restarting: "FFmpeg wird neu gestartet",
                waiting_restart: "Wartet auf Neustart",
            };
            runtimeState = states[runtime.state] || "FFmpeg-Status unbekannt";
            if (runtime.state === "running" || runtime.state === "restarting") {
                const lastProgress = Number(runtime.last_progress_at);
                const age = Number.isFinite(lastProgress) && lastProgress > 0
                    ? Math.max(0, Math.round(Date.now() / 1000 - lastProgress))
                    : null;
                runtimeMetrics = `
                    <span title="Von FFmpeg gemeldete Bildrate">${Number(runtime.fps || 0).toFixed(1)} FPS</span>
                    <span title="FFmpeg-Verarbeitungsgeschwindigkeit">${Number(runtime.speed || 0).toFixed(2)}×</span>
                    <span title="Seit Prozessstart verworfene Frames">Drop ${Number(runtime.drop_frames || 0)}</span>
                    <span title="Seit Prozessstart duplizierte Frames">Dup ${Number(runtime.dup_frames || 0)}</span>
                    <span title="CPU-Auslastung dieses FFmpeg-Prozesses">CPU ${Number(runtime.cpu_percent || 0).toFixed(1)} %</span>
                    <span title="Arbeitsspeicher dieses FFmpeg-Prozesses">RAM ${formatBytes(Number(runtime.memory_bytes || 0))}</span>
                    <span title="Letzter tatsächlicher Medienfortschritt">${age === null ? "Fortschritt —" : `vor ${age} s`}</span>
                `;
            } else if (runtime.state === "waiting_restart") {
                runtimeMetrics = `
                    <span>Neustart in ${Math.ceil(Number(runtime.restart_in || 0))} s</span>
                `;
            }
            if (Number(runtime.restart_count || 0) > 0) {
                const rawReason = String(runtime.last_restart_reason || "");
                const reason = rawReason === "stale"
                    ? "kein Fortschritt"
                    : (rawReason === "start_failed"
                        ? "Startfehler"
                        : (rawReason.startsWith("exit_")
                            ? `Exit ${rawReason.slice(5)}`
                            : "unbekannt"));
                const restartAt = Number(runtime.last_restart_at);
                const restartAge = Number.isFinite(restartAt) && restartAt > 0
                    ? Math.max(0, Math.round(Date.now() / 1000 - restartAt))
                    : null;
                restartMetric = `
                    <span title="Neustarts seit Start des Streamer-Dienstes">
                        Neustarts ${Number(runtime.restart_count)} ·
                        ${escapeHTML(reason)}${restartAge === null ? "" : ` · vor ${restartAge} s`}
                    </span>
                `;
            }
        }
        if (player?.protocol === "webrtc") {
            const received = Number(player.packets_received || 0);
            const lost = Number(player.packets_lost || 0);
            const totalPackets = received + lost;
            const lossPercent = totalPackets > 0
                ? lost / totalPackets * 100
                : 0;
            const frameProgressAge = player.last_frame_progress_at
                ? Math.max(
                    0,
                    Math.round(
                        (Date.now() - player.last_frame_progress_at) / 1000
                    )
                )
                : null;
            const reconnectAge = player.last_reconnect_at
                ? Math.max(
                    0,
                    Math.round(
                        (Date.now() - player.last_reconnect_at) / 1000
                    )
                )
                : null;
            playerMetrics = `
                <div class="source-player-summary">
                    <strong>Browserplayer · ${escapeHTML(player.connection_state || player.player_state || "unbekannt")}</strong>
                    <span title="Im Browser empfangene WebRTC-Bitrate">${formatBitsPerSecond(Number(player.bitrate_bps || 0))}</span>
                    <span title="Verlorene WebRTC-Pakete">Verlust ${lossPercent.toFixed(2)} % (${lost})</span>
                    <span title="Vom Browser verworfene Videoframes">Drop ${Number(player.frames_dropped || 0)}</span>
                    <span title="Letzter dekodierter Bildfortschritt">${frameProgressAge === null ? "Bildfortschritt —" : `Bild vor ${frameProgressAge} s`}</span>
                    <span title="Automatische Neuverbindungen dieses Browserplayers">Reconnects ${Number(player.reconnect_count || 0)}</span>
                    ${player.last_reconnect_reason ? `<span title="Letzte automatische Neuverbindung">${escapeHTML(player.last_reconnect_reason)}${reconnectAge === null ? "" : ` · vor ${reconnectAge} s`}</span>` : ""}
                </div>
            `;
        }
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
                <div class="source-runtime-summary">
                    <strong
                        class="source-health is-${escapeHTML(health.code)}"
                        title="${escapeHTML(health.message)}">
                        ● ${escapeHTML(health.label)} · ${escapeHTML(runtimeState)}
                    </strong>
                    ${runtimeMetrics}
                    ${restartMetric}
                </div>
                ${playerMetrics}
                <div class="source-probe-actions">
                    <button
                        class="bos-button bos-button-small source-probe-button"
                        type="button"
                        data-source-probe="${escapeHTML(source.id)}"
                        ${!source.ready || sourceProbeRunning !== null ? "disabled" : ""}>
                        ${sourceProbeRunning === source.id ? "Messung läuft …" : "Tiefendiagnose"}
                    </button>
                    <small>${source.ready ? "2 Sekunden · Ergebnis 60 Sekunden gecacht" : "Erst bei verfügbarem Signal möglich"}</small>
                </div>
                ${sourceProbeResultMarkup(source, probeState)}
            </article>
        `;
    }).join("");

    for (const button of container.querySelectorAll("[data-source-probe]")) {
        button.addEventListener("click", () => {
            runSourceProbe(button.dataset.sourceProbe);
        });
    }
}

function sourceProbeResultMarkup(source, state) {
    if (!state) {
        return "";
    }
    if (state.loading) {
        return '<div class="source-probe-result is-loading">Paket- und Zeitstempel werden gemessen …</div>';
    }
    if (state.error) {
        return `<div class="source-probe-result is-error">${escapeHTML(state.error)}</div>`;
    }

    const result = state.result;
    if (!result?.available) {
        return `<div class="source-probe-result is-error">${escapeHTML(result?.error || "Keine Messdaten verfügbar.")}</div>`;
    }
    const measured = result.measured_at
        ? new Date(result.measured_at).toLocaleTimeString("de-DE")
        : "—";
    const warningCodes = new Set(
        (result.warnings || []).map(warning => warning.code)
    );
    const recommendation = warningCodes.size > 0 && source.profile !== "copy_repair"
        ? '<strong>Empfehlung: Profil „Copy mit Zeitstempel-Korrektur“ prüfen.</strong>'
        : "";
    const warnings = (result.warnings || []).length
        ? `<ul>${result.warnings.map(warning => `<li>${escapeHTML(warning.message)}</li>`).join("")}</ul>`
        : "<p>Keine Zeitstempelwarnung im Messfenster.</p>";

    return `
        <div class="source-probe-result">
            <header>
                <strong>Messung ${escapeHTML(measured)}</strong>
                <span>${result.cached ? `Cache · ${Number(result.cache_age_seconds || 0)} s alt` : "Neu gemessen"}</span>
            </header>
            <dl>
                <div><dt>Bildrate</dt><dd>${Number(result.average_fps || 0).toFixed(2)} FPS</dd></div>
                <div><dt>Bitrate</dt><dd>${formatBitsPerSecond(Number(result.bitrate_bps || 0))}</dd></div>
                <div><dt>Pakete / DTS</dt><dd>${Number(result.packets_checked || 0)} / ${Number(result.backwards_dts || 0)} rückwärts</dd></div>
                <div><dt>Timing</dt><dd>${Number(result.timing_jitter_ms || 0).toFixed(1)} ms Jitter · max. ${Number(result.max_gap_ms || 0).toFixed(0)} ms</dd></div>
            </dl>
            ${warnings}
            ${recommendation}
        </div>
    `;
}

async function runSourceProbe(sourceId) {
    if (!sourceId || sourceProbeRunning !== null) {
        return;
    }
    sourceProbeRunning = sourceId;
    sourceProbeResults.set(sourceId, {loading: true});
    updateSourceDiagnostics(window.dashboard?.sources ?? []);

    try {
        const result = await api.probeSource(sourceId);
        sourceProbeResults.set(sourceId, {result});
    } catch (error) {
        sourceProbeResults.set(sourceId, {
            error: error.message || "Tiefendiagnose ist fehlgeschlagen.",
        });
    } finally {
        sourceProbeRunning = null;
        updateSourceDiagnostics(window.dashboard?.sources ?? []);
    }
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

    updateSystemWebAccess(info);

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

function updateSystemWebAccess(info) {
    const card = document.getElementById("service-card-web-access");
    const serverAccess = info.server_access ?? {};
    const isServer = info.installation_profile === "server";
    const https = serverAccess.https_enabled === "yes";
    const host = serverAccess.public_domain || info.network?.ipv4;
    const text = isServer
        ? (
            https
                ? `HTTPS erreichbar · ${host || "Domain nicht konfiguriert"}`
                : `HTTP erreichbar · ${host || "Server-IP"}:8000`
        )
        : `HTTP erreichbar · ${host || "Geräte-IP"}:8000`;

    updateValue("system-web-access", text);
    if (card) {
        card.classList.remove("is-offline");
        card.classList.add("is-online");
    }
}
