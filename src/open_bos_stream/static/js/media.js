let activeMediaEntry = null;

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
                Keine Dateien vorhanden.
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

        row.innerHTML = `
            <div class="library-row">

                <div class="library-meta">

                    <div
                        class="library-title"
                        title="${file.name}">

                        ${mediaTitle(file)}

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
        placeholder.style.display = "none";
    }

    video.style.display = "block";

    video.src = src;

    video.load();

    video.play();

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

    image.style.display = "block";

    if (placeholder) {
        placeholder.style.display = "none";
    }

}
