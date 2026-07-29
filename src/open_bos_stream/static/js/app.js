window.addEventListener("load", async () => {

    // Die Uhr darf nicht von Netzwerk-, Stream- oder Hardwareabfragen
    // abhängen. Sie startet deshalb vor allen asynchronen Initialisierungen.
    updateClock();

    setInterval(
        updateClock,
        1000
    );

    // ------------------------------------------------------
    // UI-Zustand wiederherstellen
    // ------------------------------------------------------

    restorePage();
    restoreCards();

    // ------------------------------------------------------
    // Initiale Aktualisierung
    // ------------------------------------------------------

	await refreshDashboard();
	
    // ------------------------------------------------------
    // Event Log
    // ------------------------------------------------------

	addEvent(

	    "info",

	    "🚒 Open BOS Stream gestartet"

	);

	if (window.dashboard?.stream?.running) {

	    addEvent(

	        "success",

	        `📡 Stream aktiv (PID ${window.dashboard.stream.pid})`

	    );

	}

    refreshSnapshot();

    refreshMediaLibrary();

	await refreshConfig();

    await loadDisplayConfig();

	await loadEncoders();
	
	loadEncoderConfig();

    // ------------------------------------------------------
    // Regelmäßige Aktualisierung
    // ------------------------------------------------------

    setInterval(
        refreshDashboard,
        1000
    );

	setInterval(
	    () => {
	        if (
	            document
	                .getElementById("page-media")
	                ?.classList.contains("active")
	        ) {
	            refreshMediaLibrary();
	        }
	    },
	    2000
	);

    setInterval(
        refreshDisplayStatus,
        3000
    );

});
