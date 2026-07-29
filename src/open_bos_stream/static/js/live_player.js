class LivePlayer {

    constructor() {

        this.mode = null;
		this.resetting = false;
		this.currentStream = null;
		this.hls = null;
		this.webrtc = null;
		this.state = "idle";
		this.stateListeners = [];
        this.transportDiagnostics = {
            protocol: null,
            connection_state: "idle",
            packets_received: 0,
            packets_lost: 0,
            jitter_ms: 0,
            bitrate_bps: 0,
            frames_decoded: 0,
            frames_dropped: 0,
        };
        this.previousTransportSample = null;
		this.video =
            document.getElementById(
                "live-video"
            );
			
		this.video.addEventListener(
		    "playing",
		    () => {

		        console.log("▶ playing");

		        this.setState("playing");
                if (this.mode === "hls") {
                    this.transportDiagnostics.connection_state =
                        "playing";
                }

		    }
		);

        window.setInterval(
            () => this.refreshTransportDiagnostics(),
            2000
        );

		this.video.addEventListener(
		    "pause",
		    () => console.log("⏸ pause")
		);

		this.video.addEventListener(
		    "ended",
		    () => console.log("■ ended")
		);

		this.video.addEventListener(
		    "error",
		    () => {

		        console.error(
		            "Video error:",
		            this.video.error
		        );

		        console.log(
		            "Quelle:",
		            this.video.currentSrc
		        );

		        this.setState("error");

		    }
		);

    }

	setState(state) {

	    if (this.state === state) {
	        return;
	    }

	    const previousState =
	        this.state;

	    this.state = state;

	    console.debug(
	        `[LivePlayer] ${previousState} → ${state}`
	    );

	    for (const listener of this.stateListeners) {

	        try {

	            listener({
	                state: this.state,
	                previousState: previousState,
	                protocol: this.mode,
	                stream: this.currentStream
	            });

	        } catch (err) {

	            console.error(err);

	        }

	    }

	}
	
	onStateChanged(listener) {

	    this.stateListeners.push(listener);

	}
	
	getStreamUrl(streamName, protocol) {

	    const host = window.location.hostname;

	    switch (protocol) {

	        case "webrtc":
	            return `http://${host}:8889/${streamName}/whep`;

	        case "hls":
	        default:
	            return `http://${host}:8888/${streamName}/index.m3u8`;

	    }

	}
	
	play(streamName, protocol = "hls") {

		if (
		    this.mode === protocol &&
		    this.currentStream === streamName
		) {
		    return;
		}

		this.reset();
        this.setState("connecting");
		this.mode = protocol;
		this.currentStream = streamName;
        this.transportDiagnostics = {
            protocol: protocol,
            connection_state: "connecting",
            packets_received: 0,
            packets_lost: 0,
            jitter_ms: 0,
            bitrate_bps: 0,
            frames_decoded: 0,
            frames_dropped: 0,
        };
		
		switch (protocol) {

	        case "webrtc":

	            this.playWebRTC(streamName);
	            break;

	        case "hls":

	        default:

	            this.playHls(streamName);
	            break;

	    }

	}
	
	playHls(streamName) {

	    if (!this.video) {
	        return;
	    }

	const url =
	    this.getStreamUrl(
	        streamName,
	        "hls"
	    );

	    console.log(
	        "Start HLS:",
	        url
	    );

	    //
	    // Safari unterstützt HLS direkt.
	    //
	    if (
	        this.video.canPlayType(
	            "application/vnd.apple.mpegurl"
	        )
	    ) {
	        this.video.src = url;
	        this.video.play().catch(
	            console.error
	        );
	        return;
	    }

	    //
	    // Chromium und Firefox verwenden hls.js.
	    //
	    if (
	        typeof Hls !== "undefined" &&
	        Hls.isSupported()
	    ) {
	        this.hls = new Hls({
	            lowLatencyMode: true,
	        });

	        this.hls.on(
	            Hls.Events.MANIFEST_PARSED,
	            () => {
	                this.video.play().catch(
	                    console.error
	                );
	            }
	        );

	        this.hls.on(
	            Hls.Events.ERROR,
	            (_event, data) => {
	                console.error(
	                    "HLS:",
	                    data
	                );

	                if (data.fatal) {
	                    this.setState("error");
	                }
	            }
	        );

	        this.hls.loadSource(url);
	        this.hls.attachMedia(this.video);
	        return;
	    }

	    console.error(
	        "HLS wird von diesem Browser nicht unterstützt."
	    );
	    this.setState("error");

	}

	playWebRTC(streamName) {

	const url =
	    this.getStreamUrl(
	        streamName,
	        "webrtc"
	    );

	    console.log("Verbinde WebRTC:", url);

	    this.webrtc = new MediaMTXWebRTCReader({

	        url: url,

			onError: (err) => {

			    console.error(
			        "WebRTC:",
			        err
			    );

			    this.setState("error");
                this.transportDiagnostics.connection_state =
                    "reconnecting";

			},

            onState: state => {
                this.transportDiagnostics.connection_state =
                    state;
                if (state === "connected") {
                    this.setState("playing");
                } else if (
                    state === "connecting" ||
                    state === "new"
                ) {
                    this.setState("connecting");
                }
            },

	        onTrack: (evt) => {

	            this.video.srcObject =
	                evt.streams[0];

	            this.video.play()
	                .catch(console.error);

	        }

	    });

	}

    async refreshTransportDiagnostics() {
        const quality =
            this.video?.getVideoPlaybackQuality?.();

        if (quality) {
            this.transportDiagnostics.frames_decoded =
                quality.totalVideoFrames ?? 0;
            this.transportDiagnostics.frames_dropped =
                quality.droppedVideoFrames ?? 0;
        }

        if (!this.webrtc) {
            return;
        }

        try {
            const sample = await this.webrtc.stats();
            const now = Date.now();
            let bitrate = 0;

            if (
                this.previousTransportSample &&
                sample.bytesReceived >=
                    this.previousTransportSample.bytes
            ) {
                const seconds =
                    (now - this.previousTransportSample.time) /
                    1000;
                if (seconds > 0) {
                    bitrate =
                        (
                            sample.bytesReceived -
                            this.previousTransportSample.bytes
                        ) * 8 / seconds;
                }
            }

            this.previousTransportSample = {
                bytes: sample.bytesReceived,
                time: now,
            };
            this.transportDiagnostics = {
                protocol: "webrtc",
                connection_state: sample.connectionState,
                packets_received: sample.packetsReceived,
                packets_lost: sample.packetsLost,
                jitter_ms: sample.jitterMs,
                bitrate_bps: bitrate,
                frames_decoded: sample.framesDecoded,
                frames_dropped: sample.framesDropped,
            };
        } catch (error) {
            console.debug(
                "WebRTC-Diagnose nicht verfügbar:",
                error
            );
        }
    }

    diagnostics() {
        return {...this.transportDiagnostics};
    }

	reset() {

		this.resetting = true;
	    if (this.hls) {
	        this.hls.destroy();
	        this.hls = null;
	    }

	    if (this.webrtc) {
	        this.webrtc.close();
	        this.webrtc = null;
	    }
        this.previousTransportSample = null;

	    this.video.pause();

	    this.video.removeAttribute("src");
	    this.video.srcObject = null;
	    this.video.load();
        this.resetting = false;
	}
	
	stop() {

	    this.reset();

	    this.mode = null;
	    this.currentStream = null;

	    this.setState("idle");
        this.transportDiagnostics.protocol = null;
        this.transportDiagnostics.connection_state = "idle";

	}
}

window.livePlayer =
    new LivePlayer();
