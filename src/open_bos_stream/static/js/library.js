async function refreshRecordingLibrary() {

    try {

        const files = await api.recordingFiles();

        renderMediaLibrary(
            "recording-library",
            files,
            file => `
                ${createMediaButton(
                    "▶",
                    "Abspielen",
                    `playRecording('${file.name}')`
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
            `
        );

    } catch (err) {

        console.error("Library:", err);

    }

}

function downloadRecording(filename) {

    window.location =
        "/recording/download/" + filename;

}

function playRecording(filename) {

    showVideo(

        "🎬 " + filename,

        "/recording/play-compatible/" + filename

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

        refreshRecordingLibrary();
        refreshMediaLibrary();

        if (activeMediaName === filename) {
            stopMediaPreview();
        }

        addEvent(
            "warning",
            "🗑 Aufzeichnung gelöscht"
        );

    } else {

        addEvent(
            "error",
            "🗑 Aufzeichnung konnte nicht gelöscht werden"
        );

    }

}
