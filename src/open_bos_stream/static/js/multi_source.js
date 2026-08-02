const multiSourcePlayers = new Map();
const PLAYER_RECOVERY_STATES = new Set([
    "offline",
    "connecting",
    "recovering",
    "restart_loop",
    "stalled",
]);
const PLAYER_HEALTHY_STATES = new Set([
    "stable",
    "under_load",
    "timing_issue",
]);
const PLAYER_STALL_TIMEOUT_MS = 8000;
const PLAYER_STABLE_RESET_MS = 10000;
const PLAYER_RECONNECT_MAX_MS = 15000;

function sourceCardIsFullscreen(entry) {
    return (
        document.fullscreenElement === entry.card ||
        entry.card.contains(document.fullscreenElement) ||
        entry.card.querySelector("video")?.webkitDisplayingFullscreen === true
    );
}

function resumeSourcePlayback(entry, reason) {
    const video = entry?.card?.querySelector("video");
    if (
        !video ||
        !entry.lastInput?.ready ||
        !entry.player.currentStream ||
        !video.paused
    ) {
        return;
    }
    window.setTimeout(() => {
        if (!video.paused || !entry.lastInput?.ready) {
            return;
        }
        video.play().catch(() => {
            entry.player.reconnect(reason);
        });
    }, 100);
}

function resumePlayersAfterFullscreen() {
    for (const entry of multiSourcePlayers.values()) {
        const fullscreen = sourceCardIsFullscreen(entry);
        updateSourceFullscreenButton(entry);
        if (fullscreen) {
            prepareFullscreenStream(entry);
        } else {
            releaseFullscreenStream(entry);
        }
        if (fullscreen) {
            continue;
        }
        resumeSourcePlayback(entry, "Vollbildmodus beendet");
    }
}

document.addEventListener(
    "fullscreenchange",
    resumePlayersAfterFullscreen
);
document.addEventListener(
    "webkitfullscreenchange",
    resumePlayersAfterFullscreen
);
document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") {
        resumePlayersAfterFullscreen();
    }
});

function playerRecoveryState() {
    return {
        attempts: 0,
        nextReconnectAt: 0,
        lastHealth: null,
        lastRestartCount: null,
        lastFramesDecoded: 0,
        lastPacketsReceived: 0,
        lastFrameProgressAt: null,
        playingSince: null,
        reconnectingUntil: 0,
        pendingReason: null,
        reconnectCount: 0,
        lastReconnectAt: null,
        lastReconnectReason: null,
    };
}

function reconnectDelay(attempts) {
    return Math.min(
        1000 * (2 ** Math.max(0, attempts - 1)),
        PLAYER_RECONNECT_MAX_MS
    );
}

function playerRecoveryReason(entry, input, now) {
    const recovery = entry.recovery;
    const health = input.health?.code ?? (
        input.ready ? "stable" : "offline"
    );
    const restartCount = Number(
        input.runtime?.restart_count ?? 0
    );
    const diagnostics = entry.player.diagnostics();
    let reason = null;
    const frameAdvanced = Number(
        diagnostics.frames_decoded || 0
    ) > recovery.lastFramesDecoded;

    if (
        input.ready &&
        recovery.lastHealth !== null &&
        PLAYER_RECOVERY_STATES.has(recovery.lastHealth) &&
        PLAYER_HEALTHY_STATES.has(health) &&
        entry.player.state !== "playing"
    ) {
        reason = "Quelle wieder verfügbar";
    }
    if (
        input.ready &&
        recovery.lastRestartCount !== null &&
        restartCount > recovery.lastRestartCount
    ) {
        reason = "Quellenprozess neu gestartet";
    }

    const frames = Number(diagnostics.frames_decoded || 0);
    const packets = Number(diagnostics.packets_received || 0);
    if (frameAdvanced) {
        recovery.lastFrameProgressAt = now;
    } else if (
        input.ready &&
        packets > recovery.lastPacketsReceived &&
        recovery.lastFrameProgressAt !== null &&
        now - recovery.lastFrameProgressAt >= PLAYER_STALL_TIMEOUT_MS
    ) {
        reason = "Browser-Decoder ohne Bildfortschritt";
    }
    recovery.lastFramesDecoded = frames;
    recovery.lastPacketsReceived = packets;
    recovery.lastHealth = health;
    recovery.lastRestartCount = restartCount;

    const connectionFailed = [
        "failed",
        "disconnected",
        "closed",
    ].includes(diagnostics.connection_state);
    if (
        input.ready &&
        (entry.player.state === "error" || connectionFailed)
    ) {
        reason = "WebRTC-Verbindung unterbrochen";
    }

    if (entry.player.state === "playing") {
        recovery.playingSince ??= now;
        if (
            now - recovery.playingSince >= PLAYER_STABLE_RESET_MS &&
            frameAdvanced
        ) {
            recovery.attempts = 0;
            recovery.nextReconnectAt = 0;
        }
    } else {
        recovery.playingSince = null;
    }

    return reason;
}

function recoverSourcePlayer(entry, input, now) {
    const detectedReason = playerRecoveryReason(entry, input, now);
    const reason = detectedReason ?? entry.recovery.pendingReason;
    if (reason && sourceCardIsFullscreen(entry)) {
        entry.recovery.pendingReason = reason;
        return false;
    }
    if (
        !reason ||
        !input.ready ||
        now < entry.recovery.nextReconnectAt
    ) {
        return false;
    }

    entry.recovery.attempts += 1;
    entry.recovery.nextReconnectAt =
        now + reconnectDelay(entry.recovery.attempts);
    entry.recovery.reconnectingUntil = now + 4000;
    entry.recovery.lastFrameProgressAt = now;
    entry.recovery.lastFramesDecoded = 0;
    entry.recovery.lastPacketsReceived = 0;
    entry.recovery.pendingReason = null;
    const reconnected = entry.player.reconnect(reason);
    if (reconnected) {
        entry.recovery.reconnectCount += 1;
        entry.recovery.lastReconnectAt = now;
        entry.recovery.lastReconnectReason = reason;
        window.dispatchEvent(new CustomEvent(
            "open-bos:player-reconnect",
            {
                detail: {
                    sourceId: input.id,
                    sourceName: input.name,
                    reason,
                    count: entry.recovery.reconnectCount,
                },
            }
        ));
    }
    return reconnected;
}

function sourcePlayerDiagnostics() {
    const result = Object.create(null);
    for (const [sourceId, entry] of multiSourcePlayers) {
        result[sourceId] = {
            ...entry.player.diagnostics(),
            player_state: entry.player.state,
            last_frame_progress_at:
                entry.recovery.lastFrameProgressAt,
            reconnect_count: entry.recovery.reconnectCount,
            last_reconnect_at: entry.recovery.lastReconnectAt,
            last_reconnect_reason:
                entry.recovery.lastReconnectReason,
        };
    }
    return result;
}

function switchSourceFullscreenStream(entry, fullscreen) {
    const target = fullscreen
        ? entry.fullscreenViewerPath
        : entry.viewerPath;
    if (
        !entry.lastInput?.ready ||
        !target ||
        entry.player.currentStream === target
    ) {
        return;
    }
    entry.player.play(target, "webrtc");
}

function updateSourceFullscreenButton(entry) {
    const button = entry.card.querySelector(".multi-source-fullscreen");
    if (!button) {
        return;
    }
    const fullscreen = sourceCardIsFullscreen(entry);
    button.textContent = fullscreen ? "⛶ Vollbild beenden" : "⛶ Vollbild";
    button.title = fullscreen
        ? "Vollbildmodus beenden"
        : "Quelle im Vollbild anzeigen";
    button.setAttribute("aria-label", button.title);
}

function fullscreenRelayUrl(entry) {
    const sourceId = encodeURIComponent(entry.lastInput.id);
    const lease = entry.fullscreenLease
        ? `/${encodeURIComponent(entry.fullscreenLease)}`
        : "";
    return `/dashboard/sources/${sourceId}/fullscreen${lease}`;
}

async function fullscreenRelayRequest(entry, method) {
    const response = await fetch(fullscreenRelayUrl(entry), {method});
    if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        throw new Error(payload.detail ?? `HTTP ${response.status}`);
    }
    return response.json();
}

async function prepareFullscreenStream(entry) {
    if (
        entry.fullscreenViewerPath === entry.viewerPath ||
        entry.fullscreenMainReady ||
        entry.fullscreenPreparing
    ) {
        if (entry.fullscreenMainReady) {
            switchSourceFullscreenStream(entry, true);
        }
        return;
    }
    entry.fullscreenPreparing = true;
    try {
        let status = entry.fullscreenLease
            ? await fullscreenRelayRequest(entry, "GET")
            : await fullscreenRelayRequest(entry, "POST");
        entry.fullscreenLease = status.lease_id;
        for (let attempt = 0; attempt < 20; attempt += 1) {
            if (!sourceCardIsFullscreen(entry)) {
                return;
            }
            if (status.ready) {
                entry.fullscreenMainReady = true;
                entry.fullscreenFormat = {
                    width: Number(status.width || 0),
                    height: Number(status.height || 0),
                    codec: status.codec ?? null,
                };
                switchSourceFullscreenStream(entry, true);
                entry.fullscreenHeartbeat ??= window.setInterval(
                    () => fullscreenRelayRequest(entry, "GET").catch(
                        () => releaseFullscreenStream(entry)
                    ),
                    10000
                );
                return;
            }
            await new Promise(resolve => window.setTimeout(resolve, 400));
            status = await fullscreenRelayRequest(entry, "GET");
        }
        throw new Error("Hauptstream ist nicht rechtzeitig bereit.");
    } catch (error) {
        console.warn("Hauptstream nicht verfügbar, Vorschau bleibt aktiv:", error);
        entry.fullscreenMainReady = false;
        entry.fullscreenErrorUntil = Date.now() + 5000;
        switchSourceFullscreenStream(entry, false);
    } finally {
        entry.fullscreenPreparing = false;
    }
}

function releaseFullscreenStream(entry) {
    if (entry.fullscreenHeartbeat) {
        window.clearInterval(entry.fullscreenHeartbeat);
        entry.fullscreenHeartbeat = null;
    }
    if (entry.fullscreenLease) {
        fetch(fullscreenRelayUrl(entry), {
            method: "DELETE",
            keepalive: true,
        }).catch(() => {});
    }
    entry.fullscreenLease = null;
    entry.fullscreenMainReady = false;
    entry.fullscreenFormat = null;
    switchSourceFullscreenStream(entry, false);
}

async function closeSourceFullscreen(entry) {
    const video = entry.card.querySelector("video");
    if (document.fullscreenElement && document.exitFullscreen) {
        await document.exitFullscreen();
        return;
    }
    if (video?.webkitDisplayingFullscreen && video.webkitExitFullscreen) {
        video.webkitExitFullscreen();
    }
}

async function openSourceFullscreen(entry) {
    const {card} = entry;
    const video = card.querySelector("video");
    prepareFullscreenStream(entry);
    if (typeof card.requestFullscreen === "function") {
        try {
            await card.requestFullscreen();
            return;
        } catch (error) {
            console.debug(
                "Karten-Vollbild nicht verfügbar:",
                error
            );
        }
    }
    if (
        !video.hidden &&
        typeof video.webkitEnterFullscreen === "function"
    ) {
        try {
            video.webkitEnterFullscreen();
            return;
        } catch (error) {
            console.debug(
                "Safari-Video-Vollbild nicht verfügbar:",
                error
            );
        }
    }
    if (typeof video.requestFullscreen === "function") {
        try {
            await video.requestFullscreen();
            return;
        } catch (error) {
            console.debug(
                "Video-Vollbild nicht verfügbar:",
                error
            );
        }
    }
    console.error(
        "Quellen-Vollbild wird von diesem Browser nicht unterstützt."
    );
    releaseFullscreenStream(entry);
}

function toggleSourceFullscreen(entry) {
    if (sourceCardIsFullscreen(entry)) {
        closeSourceFullscreen(entry).catch(error => {
            console.debug("Vollbild konnte nicht beendet werden:", error);
        });
        return;
    }
    openSourceFullscreen(entry);
}

function multiSourceCard(input) {
    const card = document.createElement("article");
    card.className = "multi-source-card";
    card.dataset.sourceId = input.id;
    card.innerHTML = `
        <header class="multi-source-card-header">
            <div>
                <strong>${escapeHTML(input.name)}</strong>
                <small>${escapeHTML(input.type)} · ${escapeHTML(input.profile)}</small>
            </div>
            <span class="multi-source-state">Offline</span>
        </header>
        <div class="multi-source-frame">
            <video
                class="multi-source-video"
                autoplay
                muted
                playsinline>
            </video>
            <div class="multi-source-placeholder">
                <strong>Kein Eingangssignal</strong>
                <small>${escapeHTML(input.publish_url)}</small>
            </div>
        </div>
        <footer class="multi-source-meta">
            <span data-value="format">—</span>
            <span data-value="viewers">0 Viewer</span>
            <button
                class="multi-source-fullscreen bos-button bos-button-small"
                type="button"
                title="Quelle im Vollbild anzeigen"
                aria-label="Quelle im Vollbild anzeigen">
                ⛶ Vollbild
            </button>
        </footer>
    `;
    const video = card.querySelector("video");
    video.muted = true;
    video.defaultMuted = true;
    return card;
}

function removeStaleMultiSources(activeIds) {
    for (const [id, entry] of multiSourcePlayers) {
        if (activeIds.has(id)) {
            continue;
        }
        releaseFullscreenStream(entry);
        entry.player.destroy();
        entry.card.remove();
        multiSourcePlayers.delete(id);
    }
}

function updateMultiSources(inputs = []) {
    const panel =
        document.getElementById("multi-source-panel");
    const grid =
        document.getElementById("multi-source-grid");
    const offlineGrid =
        document.getElementById("offline-source-grid");
    const offlineSection =
        document.getElementById("offline-source-section");
    const active = inputs.length > 0;
    window.multiSourceActive = active;

    if (!panel || !grid || !offlineGrid || !offlineSection) {
        return;
    }

    panel.hidden = !active;

    if (!active) {
        removeStaleMultiSources(new Set());
        return;
    }

    const activeIds = new Set(
        inputs.map(input => input.id)
    );
    removeStaleMultiSources(activeIds);

    let onlineCount = 0;
    const onlineOrder = [];
    const offlineOrder = [];

    for (const input of inputs) {
        let entry = multiSourcePlayers.get(input.id);
        if (
            entry &&
            entry.viewerPath !== input.viewer_path
        ) {
            entry.player.destroy();
            entry.card.remove();
            multiSourcePlayers.delete(input.id);
            entry = null;
        }

        if (!entry) {
            const card = multiSourceCard(input);
            grid.appendChild(card);
            const video = card.querySelector("video");
            entry = {
                card,
                player: new window.LivePlayer(video),
                viewerPath: input.viewer_path,
                fullscreenViewerPath:
                    input.fullscreen_viewer_path ?? input.viewer_path,
                fullscreenLease: null,
                fullscreenMainReady: false,
                fullscreenPreparing: false,
                fullscreenHeartbeat: null,
                fullscreenErrorUntil: 0,
                fullscreenFormat: null,
                recovery: playerRecoveryState(),
                lastInput: input,
            };
            card.querySelector(
                ".multi-source-fullscreen"
            ).addEventListener(
                "click",
                () => toggleSourceFullscreen(entry)
            );
            video.addEventListener(
                "webkitbeginfullscreen",
                () => prepareFullscreenStream(entry)
            );
            video.addEventListener(
                "webkitendfullscreen",
                () => {
                    releaseFullscreenStream(entry);
                    resumeSourcePlayback(
                        entry,
                        "Safari-Vollbildmodus beendet"
                    );
                }
            );
            multiSourcePlayers.set(input.id, entry);
        }

        entry.lastInput = input;
        entry.fullscreenViewerPath =
            input.fullscreen_viewer_path ?? input.viewer_path;
        updateSourceFullscreenButton(entry);

        entry.card.querySelector(
            ".multi-source-card-header strong"
        ).textContent = input.name;
        entry.card.querySelector(
            ".multi-source-card-header small"
        ).textContent =
            `${input.type} · ${input.profile}` +
            (input.preview_active ? " · Vorschau" : "");
        entry.card.querySelector(
            ".multi-source-placeholder small"
        ).textContent = input.publish_url;

        const state =
            entry.card.querySelector(
                ".multi-source-state"
            );
        const placeholder =
            entry.card.querySelector(
                ".multi-source-placeholder"
            );
        const video =
            entry.card.querySelector("video");

        entry.card.classList.toggle(
            "is-online",
            input.ready
        );
        state.textContent =
            input.ready ? "Online" : "Offline";
        if (entry.fullscreenPreparing) {
            state.textContent = "Hauptstream wird geladen";
        } else if (Date.now() < entry.fullscreenErrorUntil) {
            state.textContent = "Vorschau aktiv · Hauptstream nicht verfügbar";
        } else if (entry.fullscreenMainReady) {
            state.textContent = "Hauptstream aktiv";
        }

        let displayedOnline = input.ready;
        if (input.ready) {
            onlineCount += 1;
            placeholder.hidden = true;
            video.hidden = false;
            const desiredViewerPath = sourceCardIsFullscreen(entry)
                && entry.fullscreenMainReady
                ? entry.fullscreenViewerPath
                : entry.viewerPath;
            const playerNeedsStart =
                entry.player.mode !== "webrtc" ||
                entry.player.currentStream !== desiredViewerPath;
            entry.player.play(
                desiredViewerPath,
                "webrtc"
            );
            const recoveryNow = Date.now();
            if (playerNeedsStart) {
                // Den neuen Playerzustand erfassen, ohne die gerade
                // aufgebaute Verbindung sofort ein zweites Mal zu öffnen.
                playerRecoveryReason(entry, input, recoveryNow);
            } else {
                recoverSourcePlayer(entry, input, recoveryNow);
            }
            if (
                recoveryNow < entry.recovery.reconnectingUntil
            ) {
                state.textContent = "Player verbindet neu";
            }
        } else {
            const awaitingSignal =
                entry.player.deferUnavailableStop(4000);
            displayedOnline = awaitingSignal;
            placeholder.hidden = awaitingSignal;
            video.hidden = !awaitingSignal;
            state.textContent = awaitingSignal
                ? "Signal wird geprüft"
                : "Offline";
        }
        entry.card.classList.toggle(
            "is-compact-offline",
            !displayedOnline
        );
        (displayedOnline ? onlineOrder : offlineOrder).push(input.id);

        const visibleFormat = (
            sourceCardIsFullscreen(entry) &&
            entry.fullscreenMainReady &&
            entry.fullscreenFormat
        ) ? entry.fullscreenFormat : input;
        const format = visibleFormat.width > 0
            ? `${visibleFormat.width} × ${visibleFormat.height} · ` +
                `${visibleFormat.codec ?? "Video"}`
            : (visibleFormat.codec ?? "—");
        entry.card.querySelector(
            '[data-value="format"]'
        ).textContent = format;
        entry.card.querySelector(
            '[data-value="viewers"]'
        ).textContent =
            `${input.viewers} Viewer`;
    }

    // Bestehende Player nicht bei jedem Statusabruf neu in den DOM hängen:
    // Das beendet natives Vollbild und kann die Videodarstellung unterbrechen.
    if (!document.fullscreenElement) {
        for (const [target, order] of [
            [grid, onlineOrder],
            [offlineGrid, offlineOrder],
        ]) {
            const currentOrder = Array.from(target.children).map(
                card => card.dataset.sourceId
            );
            const orderChanged =
                currentOrder.length !== order.length ||
                order.some(
                    (id, index) => currentOrder[index] !== id
                );
            if (orderChanged) {
                for (const id of order) {
                    const entry = multiSourcePlayers.get(id);
                    if (entry) {
                        target.appendChild(entry.card);
                    }
                }
            }
        }
    }
    offlineSection.hidden = offlineOrder.length === 0;

    const summary =
        document.getElementById(
            "multi-source-summary"
        );
    if (summary) {
        summary.textContent =
            `${onlineCount} von ${inputs.length} online`;
    }
}

window.updateMultiSources = updateMultiSources;
window.sourcePlayerDiagnostics = sourcePlayerDiagnostics;
