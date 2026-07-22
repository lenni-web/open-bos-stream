async function refreshMediaLibrary() {

    try {

        const files =
            await api.mediaFiles();

        renderMediaLibrary(
            "media-library",
            files,
            file => {

                if (
                    file.type === "recording"
                ) {

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

    } catch (err) {

        console.error(
            "Media Library:",
            err
        );

    }

}