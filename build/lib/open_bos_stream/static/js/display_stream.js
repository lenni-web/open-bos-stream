const displayParams =
    new URLSearchParams(window.location.search);

if (displayParams.get("display") === "1") {
    document.documentElement.classList.add(
        "display-mode"
    );
}

let displayedStream = null;

async function refreshDisplayStream() {
    const message =
        document.getElementById(
            "display-message"
        );
    const state =
        document.getElementById(
            "display-state"
        );

    try {
        const response = await fetch(
            "/dashboard/status"
        );
        const dashboard = await response.json();
        const stream = dashboard.stream;

        if (stream.ready) {
            message.classList.add("hidden");

            if (
                displayedStream !== stream.name ||
                window.livePlayer.currentStream !==
                    stream.name
            ) {
                displayedStream = stream.name;
                window.livePlayer.play(
                    stream.name,
                    "webrtc"
                );
            }
            return;
        }

        const holdCurrentPicture =
            window.livePlayer.deferUnavailableStop(
                6000
            );
        if (!holdCurrentPicture) {
            displayedStream = null;
            message.classList.remove("hidden");
            state.textContent =
                stream.message ??
                "Warte auf Stream …";
        }

    } catch (error) {
        const holdCurrentPicture =
            window.livePlayer.deferUnavailableStop(
                6000
            );
        if (!holdCurrentPicture) {
            displayedStream = null;
            message.classList.remove("hidden");
            state.textContent =
                "Verbindung zum StreamPi wird hergestellt …";
        }
    }
}

refreshDisplayStream();
setInterval(refreshDisplayStream, 1000);
