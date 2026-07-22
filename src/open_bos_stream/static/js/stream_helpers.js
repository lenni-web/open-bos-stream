// ==========================================================
// Stream Helper
// ==========================================================

function streamViewerUrl(stream) {

    return (
        window.location.protocol +
        "//" +
        window.location.hostname +
        ":8889/" +
        stream.name +
        "/"
    );

}
