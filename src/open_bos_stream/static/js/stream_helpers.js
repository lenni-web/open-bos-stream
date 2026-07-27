// ==========================================================
// Stream Helper
// ==========================================================

function streamViewerUrl(stream) {

    const protocol =
        stream.viewer?.protocol ??
        "webrtc";

    const port =
        protocol === "hls"
            ? 8888
            : 8889;

    const params =
        new URLSearchParams({
            muted: "false",
            controls: "true",
            autoplay: "true",
            playsInline: "true",
        });

    return (
        window.location.protocol +
        "//" +
        window.location.hostname +
        ":" +
        port +
        "/" +
        stream.name +
        "/?" +
        params.toString()
    );

}