// Früher eigene Liste; heute zeigt die Seite „Aufnahmen“ alles gemeinsam.
function refreshSnapshotLibrary() {
    if (typeof refreshMediaLibrary === "function") {
        return refreshMediaLibrary();
    }
    return undefined;
}

function showSnapshot(filename) {

    showImage(

        "📸 " + filename,

        "/snapshot/view/" + encodeURIComponent(filename)

    );

    addEvent(
        "info",
        "🖼 Snapshot geöffnet"
    );

}

function downloadSnapshot(filename) {

    window.location =
        "/snapshot/download/" + encodeURIComponent(filename);

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

        refreshMediaLibrary();

        if (activeMediaName === filename) {
            stopMediaPreview();
        }


    } else {

    addEvent(
        "error",
        "🗑 Snapshot konnte nicht gelöscht werden"
    );

}

}
