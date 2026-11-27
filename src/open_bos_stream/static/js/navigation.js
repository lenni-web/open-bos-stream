function showPage(page) {
    if (!document.getElementById("page-" + page)) {
        page = "dashboard";
    }
    const previousPage =
        document.querySelector(
            ".page.active"
        )?.id?.replace("page-", "");

    if (
        previousPage === "media" &&
        page !== "media" &&
        typeof stopMediaPreview === "function"
    ) {
        stopMediaPreview();
    }

    document
        .querySelectorAll(".page")
        .forEach(element => {

            element.classList.remove("active");

        });

    document
        .querySelectorAll(".bos-nav-item")
        .forEach(element => {

            element.classList.remove("active");

        });

    document
        .getElementById("page-" + page)
        ?.classList.add("active");

    document
        .getElementById("nav-" + page)
        ?.classList.add("active");

    document
        .getElementById("nav-" + page)
        ?.setAttribute("aria-current", "page");

    document
        .querySelectorAll(
            `.bos-nav-item:not(#nav-${page})`
        )
        .forEach(element => {
            element.removeAttribute("aria-current");
        });

    localStorage.setItem(
        "currentPage",
        page
    );

    if (typeof updateTopbarTitle === "function") {
        updateTopbarTitle(page);
    }

    // „Mehr“ markieren, wenn die Seite dort einsortiert ist (Smartphone).
    const inMoreSheet = Boolean(
        document.querySelector(`#app-more-sheet [data-page="${page}"]`)
    );
    document.getElementById("nav-more")?.classList.toggle("active", inMoreSheet);
    document.querySelectorAll("#app-more-sheet .app-more-item").forEach(item => {
        item.classList.toggle("active", item.dataset.page === page);
    });

    placeConfigActionbar(page);

    if (typeof setDjiDevicesActive === "function") {
        setDjiDevicesActive(page === "drones");
    }
    if (page === "map" && typeof initMapPage === "function") {
        initMapPage();
    }

    if (typeof setStreamsPageActive === "function") {
        setStreamsPageActive(page === "streams");
    }

    if (typeof setWeatherPageActive === "function") {
        setWeatherPageActive(page === "weather");
    }

    // Einsatz-Link in der Adresse nur auf der Einsatzseite behalten.
    if (page !== "incidents" && window.location.hash.startsWith("#incidents")) {
        history.replaceState(null, "", window.location.pathname);
    }

    if (typeof setChecklistsPageActive === "function") {
        setChecklistsPageActive(page === "checklists");
    }

    if (typeof setIncidentsPageActive === "function") {
        setIncidentsPageActive(page === "incidents");
    }

}

// Eine Speichern-Leiste für „Drohnen“ und „Einstellungen“: Sie wandert zur
// geöffneten Seite, damit ihre Schaltflächen und IDs nur einmal vorkommen.
function placeConfigActionbar(page) {
    const bar = document.querySelector(".settings-actionbar");
    const slot = document.querySelector(`[data-config-actionbar-slot="${page}"]`);
    if (bar && slot && bar.parentElement !== slot) {
        slot.appendChild(bar);
    }
}

function restorePage() {

    // Direkter Link auf einen Einsatz (z. B. aus einer Push-Nachricht).
    if (typeof incidentFromHash === "function" && incidentFromHash()) {
        return;
    }

    const page =
        localStorage.getItem("currentPage")
        ?? "dashboard";

    showPage(page);

}
