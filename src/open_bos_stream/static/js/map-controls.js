"use strict";


window.OpenBosStream =
    window.OpenBosStream || {};


let fullscreenBound = false;


function isPseudoFullscreen(
    container
) {
    return container.classList.contains(
        "map-mobile-fullscreen"
    );
}


function updateFullscreenButton(
    fullscreenButton,
    container
) {
    const fullscreen =
        document.fullscreenElement === container ||
        isPseudoFullscreen(container);


    fullscreenButton.textContent =
        fullscreen
            ? "🗗"
            : "⛶";


    fullscreenButton.title =
        fullscreen
            ? "Vollbild verlassen"
            : "Vollbild";


    fullscreenButton.setAttribute(
        "aria-label",
        fullscreen
            ? "Vollbild verlassen"
            : "Karte im Vollbild anzeigen"
    );


    fullscreenButton.setAttribute(
        "aria-pressed",
        fullscreen
            ? "true"
            : "false"
    );
}


function resizeFullscreenMap() {
    const map =
        window.OpenBosStream.map;


    if (!map) {
        return;
    }


    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            map.resize();
        });
    });
}


function enterPseudoFullscreen(
    container,
    fullscreenButton
) {
    container.classList.add(
        "map-mobile-fullscreen"
    );


    document.documentElement.classList.add(
        "map-fullscreen-active"
    );


    document.body.classList.add(
        "map-fullscreen-active"
    );


    updateFullscreenButton(
        fullscreenButton,
        container
    );


    resizeFullscreenMap();
}


function exitPseudoFullscreen(
    container,
    fullscreenButton
) {
    container.classList.remove(
        "map-mobile-fullscreen"
    );


    document.documentElement.classList.remove(
        "map-fullscreen-active"
    );


    document.body.classList.remove(
        "map-fullscreen-active"
    );


    updateFullscreenButton(
        fullscreenButton,
        container
    );


    resizeFullscreenMap();
}


function shouldUsePseudoFullscreen() {
    return (
        window.matchMedia(
            "(pointer: coarse)"
        ).matches ||
        window.matchMedia(
            "(max-width: 900px)"
        ).matches
    );
}


function bindFullscreenButton() {

    if (fullscreenBound) {
        return;
    }


    const fullscreenButton =
        document.getElementById(
            "map-fullscreen-btn"
        );


    const container =
        document.getElementById(
            "map-container"
        );


    if (!fullscreenButton || !container) {
        console.warn(
            "Die Vollbildsteuerung konnte nicht initialisiert werden."
        );

        return;
    }


    fullscreenButton.addEventListener(
        "click",
        async () => {

            /*
             * Bereits aktives CSS-Vollbild immer direkt beenden.
             */
            if (isPseudoFullscreen(container)) {
                exitPseudoFullscreen(
                    container,
                    fullscreenButton
                );

                return;
            }


            /*
             * Aktives natives Vollbild beenden.
             */
            if (document.fullscreenElement) {
                try {
                    await document.exitFullscreen();
                } catch (error) {
                    console.warn(
                        "Nativer Vollbildmodus konnte nicht beendet werden:",
                        error
                    );
                }

                return;
            }


            /*
             * Mobile und touchbasierte Geräte verwenden bewusst das
             * robuste CSS-Vollbild.
             */
            if (shouldUsePseudoFullscreen()) {
                enterPseudoFullscreen(
                    container,
                    fullscreenButton
                );

                return;
            }


            /*
             * Auf Desktop zunächst natives Fullscreen versuchen.
             * Falls der Browser dies ablehnt, automatisch auf das
             * CSS-Vollbild zurückfallen.
             */
            if (
                typeof container.requestFullscreen ===
                "function"
            ) {
                try {
                    await container.requestFullscreen();
                    return;
                } catch (error) {
                    console.warn(
                        "Nativer Vollbildmodus nicht verfügbar; " +
                        "CSS-Vollbild wird verwendet.",
                        error
                    );
                }
            }


            enterPseudoFullscreen(
                container,
                fullscreenButton
            );

        }
    );


    document.addEventListener(
        "fullscreenchange",
        () => {

            updateFullscreenButton(
                fullscreenButton,
                container
            );


            resizeFullscreenMap();

        }
    );


    document.addEventListener(
        "fullscreenerror",
        event => {

            console.warn(
                "Fehler beim nativen Vollbildmodus:",
                event
            );


            if (!isPseudoFullscreen(container)) {
                enterPseudoFullscreen(
                    container,
                    fullscreenButton
                );
            }

        }
    );


    updateFullscreenButton(
        fullscreenButton,
        container
    );


    fullscreenBound = true;

}