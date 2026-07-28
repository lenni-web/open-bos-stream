window.addEventListener("load", async () => {

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

    updateClock();

    // ------------------------------------------------------
    // Regelmäßige Aktualisierung
    // ------------------------------------------------------

    setInterval(
        refreshDashboard,
        1000
    );

    setInterval(
        updateClock,
        1000
    );

	setInterval(
	    refreshMediaLibrary,
	    2000
	);

    setInterval(
        refreshDisplayStatus,
        3000
    );

});
