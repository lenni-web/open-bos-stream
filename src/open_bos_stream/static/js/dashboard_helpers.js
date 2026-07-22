// ==========================================================
// Dashboard Helper
// ==========================================================

function formatBytes(
    bytes
) {

    if (
        bytes == null ||
        bytes <= 0
    ) {

        return "0 B";

    }

    const units = [

        "B",
        "KB",
        "MB",
        "GB",
        "TB",

    ];

    let value =
        bytes;

    let unit = 0;

    while (

        value >= 1024 &&
        unit < units.length - 1

    ) {

        value /= 1024;

        unit++;

    }

    return (

        value.toFixed(
            value >= 100
                ? 0
                : 1
        ) +

        " " +

        units[unit]

    );

}

function formatBitrate(

    currentBytes,

    previousBytes,

    elapsedSeconds

) {

    if (

        previousBytes == null ||

        elapsedSeconds <= 0

    ) {

        return "—";

    }

    const bitrate =

        (currentBytes - previousBytes) *

        8 /

        elapsedSeconds;

    return (

        formatBytes(
            bitrate
        ) +

        "/s"

    );

}

function formatUptime(

    onlineTime

) {

    if (!onlineTime) {

        return "—";

    }

    const start =
        new Date(
            onlineTime
        );

    const now =
        new Date();

    const seconds =
        Math.floor(
            (
                now - start
            ) / 1000
        );

    const h =
        Math.floor(
            seconds / 3600
        );

    const m =
        Math.floor(
            (
                seconds % 3600
            ) / 60
        );

    const s =
        seconds % 60;

    return (

        String(h).padStart(
            2,
            "0"
        ) +

        ":" +

        String(m).padStart(
            2,
            "0"
        ) +

        ":" +

        String(s).padStart(
            2,
            "0"
        )

    );

}

function formatStreamSource(
    source
) {

    switch (source) {

        case "rtspSession":
            return "RTSP";

        case "publisher":
            return "Publisher";

        case "rpiCamera":
            return "Raspberry Pi Kamera";

        case "redirect":
            return "Redirect";

        default:
            return source ?? "—";

    }

}

function streamLabel(
    stream
) {

    if (!stream.running) {

        return "🔴 Offline";

    }

    return "🟢 Stream aktiv";

}

