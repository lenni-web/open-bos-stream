class OBSApi {

    // ---------------------------------------------------------
    // HTTP Helper
    // ---------------------------------------------------------

    async get(url) {

        const response = await fetch(url);
		
		if (!response.ok) {

		    const error = await response.json();

		    console.error(error);

		    throw new Error(
		        error.detail?.[0]?.msg ??
		        "Request failed",
		    );

		}

        return await response.json();

    }

	async post(url, body = null) {

	    const options = {
	        method: "POST",
	    };

	    if (body !== null) {

	        options.headers = {
	            "Content-Type": "application/json",
	        };

	        options.body = JSON.stringify(body);

	    }

	    const response = await fetch(url, options);

	    const json = await response.json();

	    return json;

	}

    async put(url, body) {

        const response = await fetch(url, {

            method: "PUT",

            headers: {
                "Content-Type": "application/json",
            },

            body: JSON.stringify(body),

        });

        return await response.json();

    }

    async delete(url) {

        const response = await fetch(url, {

            method: "DELETE",

        });

        return await response.json();

    }

    // ---------------------------------------------------------
    // Dashboard
    // ---------------------------------------------------------

    async dashboard() {

        return await this.get(
            "/dashboard/status"
        );

    }

    // ---------------------------------------------------------
    // Stream
    // ---------------------------------------------------------

    async status() {

        return await this.get(
            "/stream/status"
        );

    }

    async start() {

        return await this.post(
            "/stream/start"
        );

    }

    async stop() {

        return await this.post(
            "/stream/stop"
        );

    }

    // ---------------------------------------------------------
    // Health
    // ---------------------------------------------------------

    async health() {

        return await this.get(
            "/system/health"
        );

    }

    // ---------------------------------------------------------
    // Recording
    // ---------------------------------------------------------

    async recordingStatus() {

        return await this.get(
            "/recording/status"
        );

    }

    async startRecording() {

        return await this.post(
            "/recording/start"
        );

    }

    async stopRecording() {

        return await this.post(
            "/recording/stop"
        );

    }

    async recordingFiles() {

        return await this.get(
            "/recording/files"
        );

    }

    async deleteRecording(filename) {

        return await this.delete(
            "/recording/" + filename
        );

    }

    // ---------------------------------------------------------
    // Snapshot
    // ---------------------------------------------------------

    async snapshotStatus() {

        return await this.get(
            "/snapshot/status"
        );

    }

    async createSnapshot() {

        return await this.post(
            "/snapshot/create"
        );

    }

    async snapshotFiles() {

        return await this.get(
            "/snapshot/files"
        );

    }

    async deleteSnapshot(filename) {

        return await this.delete(
            "/snapshot/" + filename
        );

    }

    snapshotUrl(filename) {

        return "/snapshot/view/" + filename;

    }

    // ---------------------------------------------------------
    // Configuration
    // ---------------------------------------------------------

    async config() {

        return await this.get(
            "/config/"
        );

    }

	async mediaFiles() {

	    return this.get(
	        "/media/files"
	    );

	}

    async saveConfig(config) {

        return await this.put(
            "/config/",
            config
        );

    }

	async encoders(source) {

	    return await this.post(
	        "/encoder/",
	        source,
	    );

	}
}

async function apiStartStreamOutput(name) {

    const response = await fetch(

        `/stream-output/${encodeURIComponent(name)}/start`,

        {
            method: "POST",
        },

    );

    if (!response.ok) {

        throw new Error(
            "Streaming Output konnte nicht gestartet werden."
        );

    }

}

async function apiStopStreamOutput(name) {

    const response = await fetch(

        `/stream-output/${encodeURIComponent(name)}/stop`,

        {
            method: "POST",
        },

    );

    if (!response.ok) {

        throw new Error(
            "Streaming Output konnte nicht gestoppt werden."
        );

    }

}



const api = new OBSApi();