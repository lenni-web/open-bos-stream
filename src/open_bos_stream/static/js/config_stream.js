function loadStreamConfig() {

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
}

function saveStreamConfig() {

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
}
