/*
 * Open BOS Stream
 *
 * Karten-Overlay-Registry und Verwaltung
 *
 * Jedes Overlay definiert:
 * - Datenquelle
 * - Darstellung
 * - Sichtbarkeit
 * - UI-Bezeichnung
 *
 * Neue BOS-Kartenebenen werden hier registriert.
 */

"use strict";


window.OpenBosStream =
    window.OpenBosStream || {};

	function createOverlayControls(
	    overlays
	) {

	    const container =
	        document.getElementById(
	            "map-overlay-controls"
	        );


	    if (!container) {

	        console.warn(
	            "Overlay-Control Container fehlt."
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


	        checkbox.type =
	            "checkbox";


	        checkbox.id =
	            `overlay-${overlay.id}`;


	        checkbox.checked =
	            overlay.defaultVisible !== false;


	        checkbox.dataset.overlay =
	            overlay.id;


	        label.appendChild(
	            checkbox
	        );


	        label.append(
	            " " +
	            (overlay.icon || "") +
	            " " +
	            overlay.title
	        );


	        container.appendChild(
	            label
	        );


	    }

	}

window.OpenBosStream.mapOverlays = [

	{
	    id: "water_sources",

	    title:
	        "Löschwasserquellen",

	    category:
	        "infrastructure",

	    type:
	        "circle",

	    icon:
	        "💧",

	    endpoint:
	        "/api/map/layers/water_sources",

	    defaultVisible:
	        true,

	    paint:
	    {
	        "circle-radius": 6,
	        "circle-color": "#0066ff",
	        "circle-stroke-width": 2,
	        "circle-stroke-color": "#ffffff"
	    }
	}

];



async function addOverlayLayer(
    mapInstance,
    overlay
) {
	if (
	    mapInstance.getLayer(
	        overlay.id
	    )
	) {

	    console.warn(
	        "Overlay existiert bereits:",
	        overlay.id
	    );

	    return;

	}
	
    const response = await fetch(
        overlay.endpoint,
        {
            cache: "no-store"
        }
    );


    if (!response.ok) {

        throw new Error(
            `Overlay ${overlay.id} konnte nicht geladen werden`
        );

    }


    const data =
        await response.json();



    mapInstance.addSource(
        overlay.id,
        {
            type: "geojson",
            data: data
        }
    );


	const layerDefinition = {

	    id:
	        overlay.id,

	    type:
	        overlay.type || "circle",

	    source:
	        overlay.id,

	    paint:
	        overlay.paint || {}

	};


	if (overlay.layout) {

	    layerDefinition.layout =
	        overlay.layout;

	}


	if (overlay.minzoom) {

	    layerDefinition.minzoom =
	        overlay.minzoom;

	}


	if (overlay.maxzoom) {

	    layerDefinition.maxzoom =
	        overlay.maxzoom;

	}


	mapInstance.addLayer(
	    layerDefinition
	);

}



function createOverlayControls(
    overlays
) {

    const container =
        document.getElementById(
            "map-layer-control"
        );


    if (!container) {

        console.warn(
            "Layer-Control nicht gefunden."
        );

        return;

    }


    for (const overlay of overlays) {


        const label =
            document.createElement(
                "label"
            );


        label.innerHTML = `

            <input
                type="checkbox"
                id="layer-toggle-${overlay.id}"
                ${overlay.defaultVisible ? "checked" : ""}
            >

            ${overlay.title}

        `;


        container.appendChild(
            label
        );

    }

}

function bindOverlayToggle(
    overlay
) {

    const checkbox =
        document.getElementById(
            `overlay-${overlay.id}`
        );


    if (!checkbox) {

        console.warn(
            "Overlay-Schalter fehlt:",
            overlay.id
        );

        return;

    }


    checkbox.addEventListener(
        "change",
        () => {


            if (!map.getLayer(overlay.id)) {
                return;
            }


            map.setLayoutProperty(
                overlay.id,
                "visibility",
                checkbox.checked
                    ? "visible"
                    : "none"
            );


        }
    );

}