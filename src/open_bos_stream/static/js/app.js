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

    const initialSources =
        window.dashboard?.sources ?? [];
    const initialOnline =
        initialSources.filter(source => source.ready).length;
    addEvent(
        initialOnline > 0 ? "success" : "info",
        `📡 ${initialOnline} von ${initialSources.length} Quellen online`
    );

    refreshSnapshot();

    refreshMediaLibrary();

    await refreshConfig();

    await loadDisplayConfig();
    await loadWebAccessConfig();

    try {
        await loadEncoders();
    } catch (error) {
        console.error(
            "Encoder konnten nicht geladen werden:",
            error
        );
    }
	
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

    setInterval(
        refreshWebAccessStatus,
        3000
    );

});
