async function refreshSnapshotLibrary() {

    try {

        const files = await api.snapshotFiles();

        renderMediaLibrary(
            "snapshot-library",
            files,
            file => `
                ${createMediaButton(
                    "🖼",
                    "Anzeigen",
                    `showSnapshot('${file.name}')`
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
            `
        );

    } catch (err) {

        console.error("Snapshot Library:", err);

    }

}

function showSnapshot(filename) {

    showImage(

        "📸 " + filename,

        "/snapshot/view/" + filename

    );

    addEvent(
        "info",
        "🖼 Snapshot geöffnet"
    );

}

function downloadSnapshot(filename) {

    window.location =
        "/snapshot/download/" + filename;

}

async function deleteSnapshot(filename) {

    if (!confirm(
        "Snapshot wirklich löschen?"
    )) {
        return;
    }

    const result =
        await api.deleteSnapshot(filename);

    if (result.success) {

        refreshSnapshotLibrary();

        addEvent(
            "warning",
            "🗑 Snapshot gelöscht"
        );

    } else {

    addEvent(
        "error",
        "🗑 Snapshot konnte nicht gelöscht werden"
    );

}

}
