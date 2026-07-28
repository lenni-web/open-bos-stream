class LivePlayer {

    constructor() {

        this.mode = null;
		this.resetting = false;
		this.currentStream = null;
		this.webrtc = null;
		this.state = "idle";
		this.stateListeners = [];
		this.video =
            document.getElementById(
                "live-video"
            );
			
		this.video.addEventListener(
		    "playing",
		    () => {

		        console.log("▶ playing");

		        this.setState("playing");

		    }
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

	    //
	    // Stream läuft bereits
	    //
	    if (this.video.src === url) {
	        return;
	    }

	    console.log(
	        "Start HLS:",
	        url
	    );

	    this.video.src = url;

	    this.video.play().catch(
	        console.error
	    );

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

			},

	        onTrack: (evt) => {

	            this.video.srcObject =
	                evt.streams[0];

	            this.video.play()
	                .catch(console.error);

	        }

	    });

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

	    this.video.pause();

	    this.video.removeAttribute("src");
	    this.video.srcObject = null;

	    // this.video.load();
        this.resetting = false;
	}
	
	stop() {

	    this.reset();

	    this.mode = null;
	    this.currentStream = null;

	    this.setState("idle");

	}
}

window.livePlayer =
    new LivePlayer();