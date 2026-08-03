window.addEventListener("load", async () => {

    // Die Uhr darf nicht von Netzwerk-, Stream- oder Hardwareabfragen
    // abhängen. Sie startet deshalb vor allen asynchronen Initialisierungen.
    updateClock();

    setInterval(
        updateClock,
        1000
    );

    // Nur die sichtbare Aufnahmezeit lokal sekündlich fortschreiben.
    // Der Dashboard-Abruf bleibt bewusst im ressourcenschonenden 2-s-Takt.
    setInterval(
        updateRecordingTimer,
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

    if (window.currentUser?.role !== "viewer") {
        await refreshConfig();
        await loadUsers();
    }
    if (window.currentUser?.role === "superadmin") {
        refreshSnapshot();
        refreshMediaLibrary();
        if (window.installationProfile === "local") {
            await loadDisplayConfig();
            await loadWebAccessConfig();
        }
    }

    // ------------------------------------------------------
    // Regelmäßige Aktualisierung
    // ------------------------------------------------------

    setInterval(
        refreshDashboard,
        2000
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

    if (
        window.currentUser?.role === "superadmin" &&
        window.installationProfile === "local"
    ) {
        setInterval(refreshDisplayStatus, 3000);
        setInterval(refreshWebAccessStatus, 3000);
    }

});
