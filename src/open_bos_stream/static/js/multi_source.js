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
    return entry.player.reconnect(reason);
}

async function openSourceFullscreen(card, video) {
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
    card.querySelector(
        ".multi-source-fullscreen"
    ).addEventListener(
        "click",
        () => openSourceFullscreen(card, video)
    );
    return card;
}

function removeStaleMultiSources(activeIds) {
    for (const [id, entry] of multiSourcePlayers) {
        if (activeIds.has(id)) {
            continue;
        }
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
                recovery: playerRecoveryState(),
            };
            multiSourcePlayers.set(input.id, entry);
        }

        entry.card.querySelector(
            ".multi-source-card-header strong"
        ).textContent = input.name;
        entry.card.querySelector(
            ".multi-source-card-header small"
        ).textContent =
            `${input.type} · ${input.profile}`;
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

        let displayedOnline = input.ready;
        if (input.ready) {
            onlineCount += 1;
            placeholder.hidden = true;
            video.hidden = false;
            const playerNeedsStart =
                entry.player.mode !== "webrtc" ||
                entry.player.currentStream !== input.viewer_path;
            entry.player.play(
                input.viewer_path,
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

        const format =
            input.width > 0
                ? `${input.width} × ${input.height} · ${input.codec ?? "Video"}`
                : (input.codec ?? "—");
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
