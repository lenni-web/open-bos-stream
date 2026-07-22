"use strict";

let map = null;
let mapInitPromise = null;

async function loadMapStyle() {
    const response = await fetch(
        "/api/map/style",
        {
            cache: "no-store"
        }
    );

    if (!response.ok) {
        throw new Error(
            `Kartenstil konnte nicht geladen werden: HTTP ${response.status}`
        );
    }

    return await response.json();
}


function bindOverlayToggle(overlay) {

    const toggle =
        document.getElementById(
            `layer-toggle-${overlay.id}`
        );

    if (!toggle) {
        console.warn(
            `Overlay-Schalter fehlt: ${overlay.id}`
        );
        return;
    }


    toggle.addEventListener(
        "change",
        () => {

            if (!map || !map.getLayer(overlay.id)) {
                return;
            }


            map.setLayoutProperty(
                overlay.id,
                "visibility",
                toggle.checked
                    ? "visible"
                    : "none"
            );

        }
    );
}

function createOverlayControls(overlays) {

    const container =
        document.getElementById(
            "map-layer-list"
        );


    if (!container) {
        console.warn(
            "Layer-Control Container fehlt."
        );
        return;
    }


    container.innerHTML = "";


    for (const overlay of overlays) {


        const label =
            document.createElement(
                "label"
            );


        const checkbox =
            document.createElement(
                "input"
            );


        checkbox.type = "checkbox";
        checkbox.checked =
            overlay.visible !== false;


        checkbox.id =
            `layer-toggle-${overlay.id}`;


        checkbox.dataset.layer =
            overlay.id;


        label.appendChild(
            checkbox
        );


        label.appendChild(
            document.createTextNode(
                " " + overlay.title
            )
        );


        container.appendChild(
            label
        );


    }

}

async function createMap() {
    const container = document.getElementById("map-container");

    if (!container) {
        throw new Error(
            "Der Kartencontainer #map-container wurde nicht gefunden."
        );
    }

    if (typeof maplibregl === "undefined") {
        throw new Error(
            "MapLibre GL JS wurde nicht geladen."
        );
    }

    const configResponse = await fetch(
        "/api/map/config",
        {
            cache: "no-store"
        }
    );

    if (!configResponse.ok) {
        throw new Error(
            "Kartenkonfiguration konnte nicht geladen werden: " +
            `HTTP ${configResponse.status}`
        );
    }

    const config = await configResponse.json();
    const style = await loadMapStyle();

    const center = config.metadata.center;

    map = new maplibregl.Map({
        container: "map",
        style: style,
        center: center.slice(0, 2),
        zoom: center[2] ?? 7,
        minZoom: Number(config.metadata.min_zoom),
        maxZoom: Number(config.metadata.max_zoom),
        attributionControl: false
    });
	
	bindFullscreenButton();

    map.addControl(
        new maplibregl.NavigationControl(),
        "top-right"
    );

    map.addControl(
        new maplibregl.AttributionControl({
            compact: true,
            customAttribution:
                "© OpenStreetMap-Mitwirkende | OpenMapTiles"
        })
    );

    map.on("error", event => {
        console.error(
            "MapLibre-Fehler:",
            event.error ?? event
        );
    });

	map.once("load", async () => {
	    try {

	        const overlays =
	            window.OpenBosStream?.mapOverlays;


	        if (!Array.isArray(overlays)) {
	            throw new Error(
	                "Die Overlay-Registry wurde nicht geladen."
	            );
	        }


	        createOverlayControls(
	            overlays
	        );


			for (const overlay of overlays) {

			    await addOverlayLayer(
			        map,
			        overlay
			    );

			}


	        for (const overlay of overlays) {

	            bindOverlayToggle(
	                overlay
	            );

	        }


	        requestAnimationFrame(() => {
	            map.resize();
	        });


	    } catch (error) {

	        console.error(
	            "Kartenlayer konnten nicht geladen werden:",
	            error
	        );

	    }
	});
}

function resizeMap() {
    if (!map) {
        return;
    }

    /*
     * Der Kartenbereich wurde von showPage() gerade erst sichtbar gemacht.
     * Zwei Render-Zyklen geben dem Browser Zeit, das Layout vollständig
     * zu berechnen, bevor MapLibre seine Größe neu bestimmt.
     */
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            map.resize();
        });
    });
}


async function initMapPage() {
    const container = document.getElementById("map-container");

    if (!container) {
        console.error(
            "Karte konnte nicht initialisiert werden: " +
            "#map-container wurde nicht gefunden."
        );
        return;
    }

    /*
     * Die Karte existiert bereits. Bei einem erneuten Aufruf der
     * Kartenseite darf keine zweite MapLibre-Instanz entstehen.
     */
    if (map) {
        resizeMap();
        return;
    }

    /*
     * Eine Initialisierung läuft bereits. Das kann beispielsweise
     * durch schnelle Seitenwechsel oder mehrere Aufrufe von showPage()
     * passieren.
     */
    if (mapInitPromise) {
        try {
            await mapInitPromise;
            resizeMap();
        } catch (error) {
            console.error(
                "Die laufende Karteninitialisierung ist fehlgeschlagen:",
                error
            );
        }

        return;
    }

    mapInitPromise = createMap();

    try {
        await mapInitPromise;
        resizeMap();
    } catch (error) {
        console.error(
            "Karte konnte nicht initialisiert werden:",
            error
        );

        /*
         * Nach einem Fehler darf ein späterer Aufruf erneut versuchen,
         * die Karte zu initialisieren.
         */
        map = null;
    } finally {
        mapInitPromise = null;
    }
}
