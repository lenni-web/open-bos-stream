// ==========================================================
// Stream Helper
// ==========================================================

function streamViewerUrl(stream) {

    const protocol =
        stream.viewer?.protocol ??
        "webrtc";

    const path = stream.name
        .split("/")
        .map(segment => encodeURIComponent(segment))
        .join("/");

    const params =
        new URLSearchParams({
            muted: "false",
            controls: "true",
            autoplay: "true",
            playsInline: "true",
        });

    if (window.location.protocol === "https:") {
        const prefix = protocol === "hls" ? "hls" : "whep";
        return `${window.location.origin}/${prefix}/${path}/?${params}`;
    }

    const port = protocol === "hls" ? 8888 : 8889;
    return `http://${window.location.hostname}:${port}/${path}/?${params}`;

}
