class OBSApi {

    // ---------------------------------------------------------
    // HTTP Helper
    // ---------------------------------------------------------

    async request(url, options = {}) {
        let response;

        try {
            response = await fetch(url, options);
        } catch (error) {
            if (error.name === "AbortError") {
                throw error;
            }

            throw new Error(
                "Verbindung zur Anwendung fehlgeschlagen."
            );
        }

        const contentType =
            response.headers.get("content-type") ?? "";

        let payload = null;

        if (contentType.includes("application/json")) {
            payload = await response.json();
        } else {
            payload = await response.text();
        }

        if (!response.ok) {
            const detail = payload?.detail;
            const message =
                detail?.message ??
                detail?.[0]?.msg ??
                (
                    typeof detail === "string"
                        ? detail
                        : null
                ) ??
                payload?.error ??
                `Anfrage fehlgeschlagen (HTTP ${response.status}).`;

            const error = new Error(message);
            error.status = response.status;
            error.url = url;
            throw error;
        }

        return payload;
    }

    async get(url) {
        return await this.request(url);
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

        return await this.request(url, options);
    }

    async put(url, body) {

        return await this.request(url, {
            method: "PUT",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify(body),
        });
    }

    async testConfig(config) {
        return await this.post(
            "/config/test",
            config
        );
    }

    async restoreConfig() {
        return await this.post(
            "/config/restore"
        );
    }

    async delete(url) {

        return await this.request(url, {
            method: "DELETE",
        });
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

    async displayConfig() {
        return await this.get(
            "/display/config"
        );
    }

    async displayStatus() {
        return await this.get(
            "/display/status"
        );
    }

    async saveDisplayConfig(config) {
        return await this.put(
            "/display/config",
            config
        );
    }
}

async function apiStartStreamOutput(name) {
    return await api.post(
        `/stream-output/${encodeURIComponent(name)}/start`,
    );
}

async function apiStopStreamOutput(name) {
    return await api.post(
        `/stream-output/${encodeURIComponent(name)}/stop`,
    );
}



const api = new OBSApi();
