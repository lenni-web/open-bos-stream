const multiSourcePlayers = new Map();

function multiSourceCard(input) {
    const card = document.createElement("article");
    card.className = "multi-source-card";
    card.dataset.sourceId = input.id;
    card.innerHTML = `
        <header class="multi-source-card-header">
            <div>
                <strong>${escapeHTML(input.name)}</strong>
                <small>${escapeHTML(input.path)}</small>
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
        </footer>
    `;
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
    const legacy =
        document.getElementById("legacy-video-panel");

    const active = inputs.length > 0;
    window.multiSourceActive = active;

    if (!panel || !grid || !legacy) {
        return;
    }

    panel.hidden = !active;
    legacy.hidden = active;

    if (!active) {
        removeStaleMultiSources(new Set());
        return;
    }

    const activeIds = new Set(
        inputs.map(input => input.id)
    );
    removeStaleMultiSources(activeIds);

    let onlineCount = 0;

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
        ).textContent = input.path;
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

        if (input.ready) {
            onlineCount += 1;
            placeholder.hidden = true;
            video.hidden = false;
            entry.player.play(
                input.viewer_path,
                "webrtc"
            );
        } else {
            placeholder.hidden = false;
            video.hidden = true;
            if (entry.player.currentStream !== null) {
                entry.player.stop();
            }
        }

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
