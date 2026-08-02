let activeMediaEntry = null;
let activeMediaName = null;

function formatFileSize(bytes) {

    if (bytes < 1024) {

        return bytes + " B";

    }

    if (bytes < 1024 * 1024) {

        return (bytes / 1024).toFixed(1) + " kB";

    }

    if (bytes < 1024 * 1024 * 1024) {

        return (bytes / 1024 / 1024).toFixed(1) + " MB";

    }

    return (bytes / 1024 / 1024 / 1024).toFixed(1) + " GB";

}

function formatMediaDate(timestamp) {

    const date = new Date(timestamp * 1000);

    return date.toLocaleString(
        "de-DE",
        {
            day: "2-digit",
            month: "2-digit",
            year: "numeric",
            hour: "2-digit",
            minute: "2-digit",
        }
    );

}

function setActiveMediaEntry(entry) {

    if (activeMediaEntry) {

        activeMediaEntry.classList.remove(
            "library-entry-active"
        );

    }

    activeMediaEntry = entry;

    if (activeMediaEntry) {

        activeMediaEntry.classList.add(
            "library-entry-active"
        );

        activeMediaName =
            activeMediaEntry.dataset.filename ??
            null;

    }

}

function createMediaButton(icon, title, onclick) {

    return `
        <button
            class="library-button"
            title="${title}"
            onclick="${onclick}">

            ${icon}

        </button>
    `;

}

function mediaGroup(timestamp) {

    const date = new Date(timestamp * 1000);

    const today = new Date();

    const yesterday = new Date();

    yesterday.setDate(today.getDate() - 1);

    if (date.toDateString() === today.toDateString()) {

        return "Heute";

    }

    if (date.toDateString() === yesterday.toDateString()) {

        return "Gestern";

    }

    return date.toLocaleDateString("de-DE");

}

function mediaTitle(file) {

    if (file.type === "recording") {

        return `
            <span class="media-recording">
                🎬 Aufnahme
            </span>
        `;

    }

    return `
        <span class="media-snapshot">
            📸 Snapshot
        </span>
    `;

}

function renderMediaLibrary(containerId, files, actions) {

    const container =
        document.getElementById(containerId);

    if (!container) {
        return;
    }

    if (files.length === 0) {

        container.innerHTML = `
            <div class="library-entry">
                Keine passenden Medien gefunden.
            </div>
        `;

        return;

    }

    container.innerHTML = "";

    let currentGroup = "";

    files.forEach(file => {

        const group =
            mediaGroup(file.modified);

        if (group !== currentGroup) {

            currentGroup = group;

            const heading =
                document.createElement("div");

            heading.className =
                "library-group";

            heading.textContent =
                group;

            container.appendChild(heading);

        }

        const row =
            document.createElement("div");

		row.addEventListener("click", () => {

		    setActiveMediaEntry(row);

		});

        row.className =
            "library-entry";
        row.dataset.filename = file.name;

        if (file.name === activeMediaName) {
            row.classList.add(
                "library-entry-active"
            );
            activeMediaEntry = row;
        }

        row.innerHTML = `
            <div class="library-row">

                <div class="library-meta">

                    <div
                        class="library-title"
                        title="${file.name}">

                        ${mediaTitle(file)}

                    </div>

                    <div
                        class="library-filename"
                        title="${file.name}">
                        ${file.name}
                    </div>

                    <div class="library-info">

                        ${formatMediaDate(file.modified)}
                        &nbsp;•&nbsp;
                        ${formatFileSize(file.size)}

                    </div>

                </div>

                <div class="library-actions">

                    ${actions(file, row)}

                </div>

            </div>
        `;

        container.appendChild(row);

    });

}

function showVideo(title, src) {

    const video =
        document.getElementById("media-video");

    const image =
        document.getElementById("media-image");

    const placeholder =
        document.getElementById("media-placeholder");

    const heading =
        document.getElementById("media-title");

    if (!video) {
        return;
    }

    heading.textContent = title;

    if (image) {
        image.style.display = "none";
    }

    if (placeholder) {
        placeholder.style.display = "flex";
        placeholder.innerHTML = `
            <span class="empty-state-icon" aria-hidden="true">…</span>
            <strong>Video wird vorbereitet</strong>
            <span>
                Die browserkompatible Wiedergabedatei wird geladen. Bei der
                ersten Wiedergabe kann dies einen Moment dauern.
            </span>
        `;
    }

    video.style.display = "none";
    video.setAttribute(
        "aria-label",
        title
    );

    video.dataset.originalSrc = src;
    video.dataset.compatibilityAttempted = "false";
    video.src = src;

    video.load();

    video.play().catch(error => {

        if (["AbortError", "NotAllowedError"].includes(error.name)) {
            return;
        }

        console.error(
            "Medienwiedergabe:",
            error
        );

        if (error.name === "NotSupportedError") {
            tryCompatibleMediaPlayback(video);
        }

    });

}

function showMediaPlaybackError(video) {
    video.style.display = "none";
    const placeholder = document.getElementById("media-placeholder");
    if (placeholder) {
        placeholder.style.display = "flex";
        placeholder.innerHTML = `
            <span class="empty-state-icon" aria-hidden="true">!</span>
            <strong>Video kann nicht wiedergegeben werden</strong>
            <span>
                Die Datei ist nicht verfügbar, beschädigt oder konnte nicht
                in ein browserkompatibles Format umgewandelt werden.
            </span>
        `;
    }
}

function tryCompatibleMediaPlayback(video) {
    const original = video.dataset.originalSrc ?? "";
    if (
        !original.startsWith("/recording/play/")
    ) {
        showMediaPlaybackError(video);
        return;
    }
    if (video.dataset.compatibilityAttempted === "true") {
        // Ein verspätetes Fehler-/Promise-Ereignis der Originalquelle darf
        // den gerade gestarteten Kompatibilitätsstream nicht überdecken.
        if (!video.error) {
            return;
        }
        showMediaPlaybackError(video);
        return;
    }
    video.dataset.compatibilityAttempted = "true";
    const filename = original.slice("/recording/play/".length);
    video.src = `/recording/play-compatible/${filename}`;
    video.load();
    video.play().catch(error => {
        if (!["AbortError", "NotAllowedError"].includes(error.name)) {
            console.error("Kompatible Medienwiedergabe:", error);
        }
    });
}

function bindMediaVideoErrors() {
    const video = document.getElementById("media-video");
    if (!video || video.dataset.errorBound) {
        return;
    }
    video.dataset.errorBound = "true";
    video.addEventListener("error", () => tryCompatibleMediaPlayback(video));
    video.addEventListener("canplay", () => {
        video.style.display = "block";
        const placeholder = document.getElementById("media-placeholder");
        if (placeholder) {
            placeholder.style.display = "none";
        }
    });
}

function showImage(title, src) {

    const video =
        document.getElementById("media-video");

    const image =
        document.getElementById("media-image");

    const placeholder =
        document.getElementById("media-placeholder");

    const heading =
        document.getElementById("media-title");

    if (!image) {
        return;
    }

    if (video) {

        video.pause();

        video.removeAttribute("src");

        video.load();

        video.style.display = "none";

    }

    heading.textContent = title;

    image.src = src;
    image.alt = title;

    image.style.display = "block";

    if (placeholder) {
        placeholder.style.display = "none";
    }

}

function resetMediaPlaceholder() {
    const placeholder =
        document.getElementById(
            "media-placeholder"
        );

    if (!placeholder) {
        return;
    }

    placeholder.innerHTML = `
        <span class="empty-state-icon" aria-hidden="true">▧</span>
        <strong>Keine Vorschau geöffnet</strong>
        <span>
            Wähle links eine Aufnahme oder einen Snapshot aus.
        </span>
    `;
    placeholder.style.display = "flex";
}

function stopMediaPreview() {
    const video =
        document.getElementById(
            "media-video"
        );
    const image =
        document.getElementById(
            "media-image"
        );
    const heading =
        document.getElementById(
            "media-title"
        );

    if (video) {
        video.pause();
        video.removeAttribute("src");
        video.load();
        video.style.display = "none";
    }

    if (image) {
        image.removeAttribute("src");
        image.alt = "";
        image.style.display = "none";
    }

    if (heading) {
        heading.textContent =
            "Medium auswählen";
    }

    activeMediaName = null;
    setActiveMediaEntry(null);
    resetMediaPlaceholder();
}

function bindMediaPreviewErrors() {
    const image =
        document.getElementById(
            "media-image"
        );

    if (!image || image.dataset.errorBound) {
        return;
    }

    image.dataset.errorBound = "true";
    image.addEventListener(
        "error",
        () => {
            image.style.display = "none";

            const placeholder =
                document.getElementById(
                    "media-placeholder"
                );

            if (placeholder) {
                placeholder.style.display = "flex";
                placeholder.innerHTML = `
                    <span class="empty-state-icon" aria-hidden="true">!</span>
                    <strong>Bild kann nicht geladen werden</strong>
                    <span>
                        Die Datei ist nicht mehr verfügbar oder beschädigt.
                    </span>
                `;
            }
        }
    );
}

bindMediaPreviewErrors();
bindMediaVideoErrors();
