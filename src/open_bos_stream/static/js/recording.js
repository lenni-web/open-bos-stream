// ==========================================================
// Snapshot und manuelle Aufnahme je Drohnenkachel (Drohnenteam)
// ==========================================================

let mediaStorageState = null;

function updateMediaStorageHint(storage) {
    mediaStorageState = storage ?? null;
    const hint = document.getElementById("media-storage-hint");
    if (!hint) {
        return;
    }
    hint.hidden = !storage || storage.level === "ok";
    hint.classList.toggle("is-warning", storage?.level === "warning");
    hint.textContent = storage?.blocked
        ? storage.blocked_message
        : storage?.level === "warning"
            ? `Speicher wird knapp: ${storage.free_percent.toFixed(1)} % frei.`
            : "";
}

function updateSourceCaptureButtons(card, input) {
    const snapshot = card.querySelector(".multi-source-snapshot");
    const record = card.querySelector(".multi-source-record");
    if (!snapshot || !record) {
        return;
    }
    // Das Recht gilt je Drohne und kommt mit dem Status.
    card.querySelector(".multi-source-capture").hidden = !input.can_capture;
    const active = Boolean(input.recording?.active);
    const automatic = Boolean(input.recording?.automatic);
    const blocked = Boolean(mediaStorageState?.blocked);

    snapshot.disabled =
        Boolean(snapshot.dataset.busy) || blocked || !input.ready;

    // Automatische Aufnahmen steuert allein das Eingangssignal.
    record.hidden = automatic;
    record.dataset.active = active ? "true" : "";
    record.classList.toggle("bos-button-red", active);
    if (!record.dataset.busy) {
        record.textContent = active ? "⏹ Stoppen" : "⏺ Aufnehmen";
        record.disabled = !active && (blocked || !input.ready);
    }
}

async function runCaptureAction(button, busyText, action) {
    const idleText = button.textContent;
    button.dataset.busy = "true";
    button.disabled = true;
    button.textContent = busyText;
    try {
        const result = await action();
        if (result?.success === false) {
            throw new Error(result.error ?? "Aktion fehlgeschlagen.");
        }
        if (typeof refreshMediaLibrary === "function") {
            refreshMediaLibrary();
        }
    } catch (err) {
        console.error("Aufnahme:", err);
        alert(err.message);
    } finally {
        delete button.dataset.busy;
        button.textContent = idleText;
        button.disabled = false;
        await refreshDashboard();
    }
}

function bindSourceCaptureButtons(card, sourceId) {
    const snapshot = card.querySelector(".multi-source-snapshot");
    const record = card.querySelector(".multi-source-record");
    snapshot?.addEventListener("click", () => runCaptureAction(
        snapshot,
        "Wird erstellt …",
        () => api.createSnapshot(sourceId)
    ));
    record?.addEventListener("click", () => {
        const active = Boolean(record.dataset.active);
        runCaptureAction(
            record,
            active ? "Wird beendet …" : "Wird gestartet …",
            () => active
                ? api.stopRecording(sourceId)
                : api.startRecording(sourceId)
        );
    });
}
