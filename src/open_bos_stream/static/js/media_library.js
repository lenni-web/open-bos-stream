let mediaLibraryFiles = [];

function filteredMediaFiles() {
    const query = (
        document.getElementById(
            "media-search"
        )?.value ?? ""
    ).trim().toLocaleLowerCase("de-DE");

    const type =
        document.getElementById(
            "media-type-filter"
        )?.value ?? "all";

    return mediaLibraryFiles.filter(file => {
        const matchesType =
            type === "all" ||
            file.type === type;
        const matchesQuery =
            query === "" ||
            file.name
                .toLocaleLowerCase("de-DE")
                .includes(query);

        return matchesType && matchesQuery;
    });
}

function renderFilteredMediaLibrary() {
    const files = filteredMediaFiles();
    const count =
        document.getElementById(
            "media-count"
        );

    if (count) {
        count.textContent =
            files.length === mediaLibraryFiles.length
                ? String(files.length)
                : `${files.length}/${mediaLibraryFiles.length}`;
    }

    renderMediaLibrary(
        "media-library",
        files,
        file => {
            if (file.type === "recording") {
                return `
                    ${createMediaButton(
                        "▶",
                        "Abspielen",
                        `setActiveMediaEntry(this.closest('.library-entry')); playRecording('${file.name}')`
                    )}
                    ${createMediaButton(
                        "⬇",
                        "Download",
                        `downloadRecording('${file.name}')`
                    )}
                    ${createMediaButton(
                        "🗑",
                        "Löschen",
                        `deleteRecording('${file.name}')`
                    )}
                `;
            }

            return `
                ${createMediaButton(
                    "🖼",
                    "Anzeigen",
                    `setActiveMediaEntry(this.closest('.library-entry')); showSnapshot('${file.name}')`
                )}
                ${createMediaButton(
                    "⬇",
                    "Download",
                    `downloadSnapshot('${file.name}')`
                )}
                ${createMediaButton(
                    "🗑",
                    "Löschen",
                    `deleteSnapshot('${file.name}')`
                )}
            `;
        }
    );
}

function bindMediaFilters() {
    for (const id of [
        "media-search",
        "media-type-filter",
    ]) {
        const element =
            document.getElementById(id);

        if (!element || element.dataset.filterBound) {
            continue;
        }

        element.dataset.filterBound = "true";
        element.addEventListener(
            "input",
            renderFilteredMediaLibrary
        );
        element.addEventListener(
            "change",
            renderFilteredMediaLibrary
        );
    }
}

async function refreshMediaLibrary() {

    try {

        mediaLibraryFiles =
            await api.mediaFiles();

        renderFilteredMediaLibrary();

    } catch (err) {

        console.error(
            "Media Library:",
            err
        );

        const container =
            document.getElementById("media-library");

        if (container) {
            container.innerHTML = `
                <div class="media-error" role="alert">
                    Mediathek konnte nicht geladen werden.
                </div>
            `;
        }

    }

}

bindMediaFilters();
