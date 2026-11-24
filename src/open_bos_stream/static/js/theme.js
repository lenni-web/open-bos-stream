/*
 * Farbschema (Hell, Dunkel oder automatisch nach Systemeinstellung).
 * Wird im <head> geladen, damit beim Seitenaufbau nichts aufblitzt.
 * Das wirksame Schema steht in <html data-color-scheme="light|dark">.
 */
(function () {
    const STORAGE_KEY = "openBosTheme";
    const CHOICES = ["auto", "light", "dark"];
    const media = window.matchMedia
        ? window.matchMedia("(prefers-color-scheme: dark)")
        : null;

    function preference() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            return CHOICES.includes(stored) ? stored : "auto";
        } catch (error) {
            return "auto";
        }
    }

    function apply() {
        const choice = preference();
        const dark = choice === "dark" ||
            (choice === "auto" && Boolean(media && media.matches));
        const root = document.documentElement;
        root.dataset.colorScheme = dark ? "dark" : "light";
        root.dataset.themePreference = choice;
        const meta = document.querySelector('meta[name="theme-color"]');
        if (meta) {
            meta.setAttribute("content", dark ? "#121820" : "#c9202f");
        }
    }

    window.OpenBosTheme = {
        preference,
        set(choice) {
            if (!CHOICES.includes(choice)) {
                return;
            }
            try {
                localStorage.setItem(STORAGE_KEY, choice);
            } catch (error) {
                // Ohne Speicher gilt die Auswahl nur bis zum Neuladen.
            }
            apply();
            document.dispatchEvent(
                new CustomEvent("open-bos:theme", { detail: choice })
            );
        },
    };

    if (media) {
        if (media.addEventListener) {
            media.addEventListener("change", apply);
        } else if (media.addListener) {
            media.addListener(apply);
        }
    }

    apply();
})();
