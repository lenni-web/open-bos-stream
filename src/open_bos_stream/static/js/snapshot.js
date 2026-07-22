async function refreshSnapshot() {

    try {

        const snapshot = await api.snapshotStatus();

        const lastSnapshot =
            snapshot.last_snapshot ?? "Kein Snapshot";

        /* Alte Snapshot-Karte */

        const snapshotFile =
            document.getElementById("snapshot-file");

        if (snapshotFile) {

            snapshotFile.textContent =
                lastSnapshot;

        }

        /* Sidebar */

        const snapshotLast =
            document.getElementById("snapshot-last");

        if (snapshotLast) {

            snapshotLast.textContent =
                lastSnapshot;

        }

        const snapshotCount =
            document.getElementById("snapshot-count");

        if (snapshotCount) {

            snapshotCount.textContent =
                snapshot.count;

        }

        /* Dashboard */

        const dashboardSnapshot =
            document.getElementById("status-snapshot");

        if (dashboardSnapshot) {

            dashboardSnapshot.textContent =
                snapshot.count;

        }

    } catch (err) {

        console.error("Snapshot:", err);

    }

}

async function createSnapshot() {

    try {

        await api.createSnapshot();

        await refreshSnapshot();

        if (typeof refreshSnapshotLibrary === "function") {

            await refreshSnapshotLibrary();

        }

        addEvent(
            "info",
            "📸 Snapshot erstellt"
        );

    } catch (err) {

        console.error("Snapshot:", err);

        addEvent(
            "error",
            "❌ Snapshot fehlgeschlagen"
        );

    }

}

