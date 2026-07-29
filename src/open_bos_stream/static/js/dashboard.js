// ==========================================================
// Dashboard Refresh
// ==========================================================

async function refreshDashboard() {

    try {

        const dashboard =
            await api.dashboard();

        window.dashboard = dashboard;

        updateDashboard(
            dashboard
        );

    } catch (err) {

        console.error(
            "Dashboard:",
            err
        );

        const refreshStatus =
            document.getElementById(
                "system-refresh-status"
            );

        if (refreshStatus) {
            refreshStatus.textContent =
                "Verbindung unterbrochen";
            refreshStatus.classList.add(
                "is-error"
            );
        }

    }

}

// ==========================================================
// Dashboard
// ==========================================================

function updateDashboard(data) {

    if (!data) {
        return;
    }

    const refreshStatus =
        document.getElementById(
            "system-refresh-status"
        );

    if (refreshStatus) {
        refreshStatus.textContent = "Live";
        refreshStatus.classList.remove(
            "is-error"
        );
    }

    updateDashboardHealth(
        data
    );

	updateDashboardSystemInfo(
	    data.system_info
	);

	checkServiceEvents(
	    data.services
	);

	updateDashboardStream(
	    data.stream,
	    data.recording
	);

	checkStreamEvents(
	    data.stream
	);

	checkStreamOutputEvents(
	    data.stream_outputs
	);

    updateRecordingUI(
        data.recording
    );

    updateStreamOutputs(
        data.stream_outputs
    );

}

function updateDashboardSystemInfo(info) {

    if (!info) {
        return;
    }

    document.getElementById("system-app-name").textContent =
        info.application.name;

    document.getElementById("system-app-version").textContent =
        info.application.version;

    document.getElementById("system-hardware-model").textContent =
        info.hardware.model;

    document.getElementById("system-hardware-arch").textContent =
        info.hardware.architecture;

    document.getElementById("system-os-system").textContent =
        info.operating_system.system;

    document.getElementById("system-os-distribution").textContent =
        info.operating_system.distribution;

    document.getElementById("system-os-kernel").textContent =
        info.operating_system.kernel;

    document.getElementById("system-runtime-python").textContent =
        info.runtime.python;

    document.getElementById("system-runtime-ffmpeg").textContent =
        info.runtime.ffmpeg;

	document.getElementById("system-network-hostname").textContent =
	    info.network.hostname;

	document.getElementById("system-network-interface").textContent =
	    info.network.interface;

	document.getElementById("system-network-ipv4").textContent =
	    info.network.ipv4;

	document.getElementById("system-network-mac").textContent =
	    info.network.mac;
}
