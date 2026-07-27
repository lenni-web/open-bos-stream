class LivePlayer {

    constructor() {

        this.mode = null;
		this.currentStream = null;
		this.webrtc = null;
		
		this.video =
            document.getElementById(
                "live-video"
            );
			
		this.video.addEventListener(
		    "playing",
		    () => console.log("▶ playing")
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

		    }
		);

    }

	play(streamName, protocol = "hls") {

		if (
		    this.mode === protocol &&
		    this.currentStream === streamName
		) {
		    return;
		}

		this.stop();

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
	        window.location.protocol +
	        "//" +
	        window.location.hostname +
	        ":8888/" +
	        streamName +
	        "/index.m3u8";

	    //
	    // Stream läuft bereits
	    //
	    if (this.video.src === url) {
	        return;
	    }

	    //
	    // alten Stream stoppen
	    //
	    this.stop();

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
	        `http://${window.location.hostname}:8889/${streamName}/whep`;

	    console.log("Verbinde WebRTC:", url);

	    this.webrtc = new MediaMTXWebRTCReader({

	        url: url,

	        onError: (err) => {
	            console.error("WebRTC:", err);
	        },

	        onTrack: (evt) => {

	            this.video.srcObject =
	                evt.streams[0];

	            this.video.play()
	                .catch(console.error);

	        }

	    });

	}

	stop() {

	    if (!this.video) {
	        return;
	    }

	    this.video.pause();

	    this.video.removeAttribute(
	        "src"
	    );

	    this.video.load();
		this.mode = null;
		this.currentStream = null;

		if (this.webrtc) {
		    this.webrtc.close();
		    this.webrtc = null;
		}
		
		if (this.hls) {
		    this.hls.destroy();
		    this.hls = null;
		}

	}
}

window.livePlayer =
    new LivePlayer();