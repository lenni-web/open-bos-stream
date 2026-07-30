function loadStreamConfig() {
    const protocol = document.getElementById(
        "cfg-viewer-protocol"
    );
    if (!protocol) {
        return;
    }

    document.getElementById(
        "cfg-stream-name"
    ).value =
        currentConfig.stream.name;

    document.getElementById(
        "cfg-rtsp-url"
    ).value =
        currentConfig.stream.rtsp_url;

    document.getElementById(
        "cfg-viewer-protocol"
    ).value =
        currentConfig.stream.viewer.protocol;

    document.getElementById(
        "cfg-stream-passthrough"
    ).checked =
        currentConfig.stream.passthrough ?? false;

    const fixedProfile =
        currentConfig.source_profile ===
            "capture_card" ||
        currentConfig.source_profile ===
            "rtmp_passthrough" ||
        currentConfig.source_profile ===
            "rtmp_repair";

    document.getElementById(
        "cfg-stream-passthrough"
    ).disabled = fixedProfile;
}

function saveStreamConfig() {
    const protocol = document.getElementById(
        "cfg-viewer-protocol"
    );
    if (!protocol) {
        return;
    }

    currentConfig.stream.name =
        document.getElementById(
            "cfg-stream-name"
        ).value;

    currentConfig.stream.rtsp_url =
        document.getElementById(
            "cfg-rtsp-url"
        ).value;

    currentConfig.stream.viewer.protocol =
        document.getElementById(
            "cfg-viewer-protocol"
        ).value;

    const passthrough =
        document.getElementById(
            "cfg-stream-passthrough"
        ).checked;

    if (
        currentConfig.source_profile ===
        "custom"
    ) {
        currentConfig.stream.passthrough =
            passthrough;
    }

    if (passthrough) {

        const inputUrl =
            new URL(currentConfig.input.url);

        const mediaPath =
            inputUrl.pathname.replace(
                /^\/+/,
                ""
            );

        currentConfig.input.mode =
            "copy";

        currentConfig.encoder.codec =
            "copy";

        currentConfig.stream.name =
            mediaPath;

        currentConfig.stream.rtsp_url =
            `rtsp://127.0.0.1:8554/${mediaPath}`;

        currentConfig.stream.audio.source =
            "none";

        currentConfig.stream.audio.device =
            null;

        currentConfig.stream.overlay.source =
            "none";

    }
}
