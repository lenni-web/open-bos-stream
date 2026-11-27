// Früher eigene Liste; heute zeigt die Seite „Aufnahmen“ alles gemeinsam.
function refreshRecordingLibrary() {
    if (typeof refreshMediaLibrary === "function") {
        return refreshMediaLibrary();
    }
    return undefined;
}

function downloadRecording(filename) {

    window.location =
        "/recording/download/" + encodeURIComponent(filename);

}

function playRecording(filename) {

    showVideo(

        "🎬 " + filename,

        "/recording/play-compatible/" + encodeURIComponent(filename)

    );

    addEvent(
        "info",
        "🎬 Aufzeichnung geöffnet"
    );

}


async function deleteRecording(filename) {

    if (!confirm(
        "Aufzeichnung wirklich löschen?"
    )) {
        return;
    }

    const result =
        await api.deleteRecording(filename);

    if (result.success) {

        refreshMediaLibrary();

        if (activeMediaName === filename) {
            stopMediaPreview();
        }


    } else {

        addEvent(
            "error",
            "🗑 Aufzeichnung konnte nicht gelöscht werden"
        );

    }

}
