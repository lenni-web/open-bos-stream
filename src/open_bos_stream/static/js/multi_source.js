const multiSourcePlayers = new Map();

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
            entry.player.play(
                input.viewer_path,
                "webrtc"
            );
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
