let mediaLibraryFiles = [];

// Dateien entfernter oder nicht erkennbarer Drohnen (sehen nur Admins).
const MEDIA_WITHOUT_SOURCE = "none";

// Die Auswahl bietet nur Drohnen an, von denen es Dateien gibt.
function updateMediaSourceFilter() {
    const select =
        document.getElementById(
            "media-source-filter"
        );

    if (!select) {
        return;
    }

    const selected = select.value;
    const sources = new Map();
    let withoutSource = false;

    for (const file of mediaLibraryFiles) {
        if (file.source_id) {
            sources.set(file.source_id, file.source_name || file.source_id);
        } else {
            withoutSource = true;
        }
    }

    const options = [new Option("Alle Drohnen", "all")];

    [...sources]
        .sort((a, b) => a[1].localeCompare(b[1], "de-DE", { numeric: true }))
        .forEach(([id, name]) => options.push(new Option(name, `source:${id}`)));

    if (withoutSource) {
        options.push(new Option("Ohne zugeordnete Drohne", MEDIA_WITHOUT_SOURCE));
    }

    select.replaceChildren(...options);
    select.value = options.some(option => option.value === selected)
        ? selected
        : "all";
}

function matchesMediaSource(file, source) {
    if (source === "all") {
        return true;
    }
    if (source === MEDIA_WITHOUT_SOURCE) {
        return !file.source_id;
    }
    return source === `source:${file.source_id}`;
}

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

    const source =
        document.getElementById(
            "media-source-filter"
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

        return (
            matchesType &&
            matchesQuery &&
            matchesMediaSource(file, source)
        );
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
            const protect = createProtectionButton(file);
            const open = file.type === "recording"
                ? createMediaButton("▶", "Abspielen", "play", file)
                : createMediaButton("🖼", "Anzeigen", "show", file);
            return `
                ${open}
                ${createMediaButton("⬇", "Download", "download", file)}
                ${protect}
                ${file.can_delete === false ? "" : createMediaButton("🗑", "Löschen", "delete", file)}
            `;
        }
    );
}

function createProtectionButton(file) {
    const title = file.protected
        ? "Behalten aufheben"
        : "Behalten (nicht automatisch löschen)";
    return `
        <button
            class="library-button${file.protected ? " is-protected" : ""}"
            type="button"
            title="${escapeHTML(title)}"
            aria-pressed="${file.protected ? "true" : "false"}"
            data-media-action="protect"
            data-media-name="${escapeHTML(file.name)}"
            data-media-type="${escapeHTML(file.type)}"
            data-media-protect="${file.protected ? "false" : "true"}">
            ${file.protected ? "🔒" : "🔓"}
        </button>
    `;
}

async function toggleMediaProtection(type, filename, protectedFlag) {
    try {
        if (type === "recording") {
            await api.setRecordingProtected(filename, protectedFlag);
        } else {
            await api.setSnapshotProtected(filename, protectedFlag);
        }
        const file = mediaLibraryFiles.find(
            item => item.type === type && item.name === filename
        );
        if (file) {
            file.protected = protectedFlag;
        }
        renderFilteredMediaLibrary();
        addEvent(
            "info",
            protectedFlag
                ? "🔒 Medium wird behalten"
                : "🔓 Medium kann automatisch gelöscht werden"
        );
    } catch (err) {
        addEvent(
            "error",
            "🔒 Markierung konnte nicht geändert werden: " + err.message
        );
    }
}

function bindMediaFilters() {
    for (const id of [
        "media-search",
        "media-source-filter",
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

        updateMediaSourceFilter();
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
