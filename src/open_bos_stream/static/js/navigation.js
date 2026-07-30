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

	if (page === "map" && typeof initMapPage === "function") {
	    initMapPage();
	}

}

function restorePage() {

    const page =
        localStorage.getItem("currentPage")
        ?? "dashboard";

    showPage(page);

}
