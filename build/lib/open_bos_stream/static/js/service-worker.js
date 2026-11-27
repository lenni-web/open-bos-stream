// ==========================================================
// Service Worker: Push-Benachrichtigungen
// ==========================================================
// Bewusst ohne Offline-Zwischenspeicher: Lagebild, Livebilder und Karte
// sollen immer aktuell vom Server kommen.

self.addEventListener("install", () => {
    self.skipWaiting();
});

self.addEventListener("activate", event => {
    event.waitUntil(self.clients.claim());
});

self.addEventListener("push", event => {
    let data = {};
    try {
        data = event.data ? event.data.json() : {};
    } catch (error) {
        data = {body: event.data ? event.data.text() : ""};
    }
    const title = data.title || "Open BOS Drohnen";
    const options = {
        body: data.body || "",
        icon: "/static/icons/open-bos-stream-192.png",
        badge: "/static/icons/open-bos-stream-192.png",
        tag: data.tag || undefined,
        // Eine Entwarnung ersetzt die Störung still, eine Störung meldet sich.
        renotify: Boolean(data.tag) && !data.recovery,
        data: {url: data.url || "/"},
    };
    event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", event => {
    event.notification.close();
    const target = new URL(
        event.notification.data?.url || "/",
        self.location.origin
    );
    if (target.origin !== self.location.origin) {
        return;
    }
    event.waitUntil((async () => {
        const windows = await self.clients.matchAll({
            type: "window",
            includeUncontrolled: true,
        });
        for (const client of windows) {
            if (new URL(client.url).origin === target.origin) {
                await client.focus();
                if ("navigate" in client && client.url !== target.href) {
                    try {
                        await client.navigate(target.href);
                    } catch (error) {
                        // Seite gehört nicht zu diesem Worker; fokussiert reicht.
                    }
                }
                return;
            }
        }
        await self.clients.openWindow(target.href);
    })());
});

// Der Push-Dienst hat das Abo erneuert (z. B. abgelaufene Schlüssel).
self.addEventListener("pushsubscriptionchange", event => {
    const subscription = event.newSubscription;
    if (!subscription) {
        return;
    }
    event.waitUntil(fetch("/api/push/subscriptions", {
        method: "POST",
        credentials: "same-origin",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
            ...subscription.toJSON(),
            replaces: event.oldSubscription?.endpoint || null,
        }),
    }).catch(() => {}));
});
