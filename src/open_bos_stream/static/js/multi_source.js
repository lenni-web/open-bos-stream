const multiSourcePlayers = new Map();

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
                class="multi-source-audio bos-button bos-button-small"
                type="button"
                aria-pressed="false">
                🔇 Ton aus
            </button>
        </footer>
    `;
    const video = card.querySelector("video");
    const audioButton = card.querySelector(
        ".multi-source-audio"
    );
    video.muted = true;
    video.defaultMuted = true;
    audioButton.addEventListener("click", () => {
        video.muted = !video.muted;
        audioButton.textContent = video.muted
            ? "🔇 Ton aus"
            : "🔊 Ton an";
        audioButton.setAttribute(
            "aria-pressed",
            String(!video.muted)
        );
    });
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
    const active = inputs.length > 0;
    window.multiSourceActive = active;

    if (!panel || !grid) {
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

        // appendChild verschiebt bestehende Karten und übernimmt damit
        // die in den Einstellungen gespeicherte Quellenreihenfolge.
        grid.appendChild(entry.card);

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
