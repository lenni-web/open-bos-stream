const TEST_LOG_STORAGE_KEY = "open-bos-stream:test-session:v1";
const TEST_LOG_SAMPLE_INTERVAL_MS = 5000;
const TEST_LOG_PERSIST_INTERVAL_MS = 30000;
const TEST_LOG_MAX_SAMPLES = 1000;
const TEST_LOG_MAX_EVENTS = 500;
let testLogSession = loadTestLogSession();
let lastTestSourceStates = Object.create(null);

function loadTestLogSession() {
    try {
        const raw = window.localStorage.getItem(TEST_LOG_STORAGE_KEY);
        if (!raw) return null;
        const session = JSON.parse(raw);
        if (
            session?.schema !== 1 ||
            !Array.isArray(session.samples) ||
            !Array.isArray(session.events)
        ) {
            return null;
        }
        return session;
    } catch (error) {
        console.warn("Testprotokoll konnte nicht geladen werden:", error);
        return null;
    }
}

function saveTestLogSession() {
    if (!testLogSession) return;
    try {
        window.localStorage.setItem(
            TEST_LOG_STORAGE_KEY,
            JSON.stringify(testLogSession)
        );
    } catch (error) {
        // Bei knappem Browser-Speicher ältere Messpunkte kontrolliert abbauen.
        testLogSession.samples = testLogSession.samples.slice(-500);
        try {
            window.localStorage.setItem(
                TEST_LOG_STORAGE_KEY,
                JSON.stringify(testLogSession)
            );
            setTestLogFeedback(
                "Browserspeicher knapp; ältere Messpunkte wurden verdichtet.",
                true
            );
        } catch (retryError) {
            testLogSession.active = false;
            testLogSession.stopped_at = new Date().toISOString();
            setTestLogFeedback(
                "Testprotokoll gestoppt: Browserspeicher ist voll.",
                true
            );
            console.error(retryError);
        }
    }
}

function testLogId() {
    return new Date().toISOString().replace(/[:.]/g, "-");
}

function startTestLogging() {
    const now = new Date().toISOString();
    testLogSession = {
        schema: 1,
        id: testLogId(),
        active: true,
        started_at: now,
        stopped_at: null,
        origin: window.location.origin,
        browser: navigator.userAgent,
        application_version:
            window.dashboard?.system_info?.application?.version ?? null,
        sample_interval_seconds: TEST_LOG_SAMPLE_INTERVAL_MS / 1000,
        samples: [],
        events: [{timestamp: now, type: "test_started"}],
        last_sample_at: 0,
        last_persist_at: 0,
    };
    lastTestSourceStates = Object.create(null);
    saveTestLogSession();
    updateTestLogging(window.dashboard, true);
    setTestLogFeedback("Testprotokoll läuft.");
}

function stopTestLogging() {
    if (!testLogSession?.active) return;
    const now = new Date().toISOString();
    testLogSession.active = false;
    testLogSession.stopped_at = now;
    recordTestLogEvent("test_stopped", {}, now, false);
    saveTestLogSession();
    refreshTestLoggingUI();
    setTestLogFeedback("Testprotokoll beendet und zum Download bereit.");
}

function clearTestLogging() {
    testLogSession = null;
    lastTestSourceStates = Object.create(null);
    window.localStorage.removeItem(TEST_LOG_STORAGE_KEY);
    refreshTestLoggingUI();
    setTestLogFeedback("Testprotokoll verworfen.");
}

function recordTestLogEvent(
    type,
    detail = {},
    timestamp = new Date().toISOString(),
    persist = true
) {
    if (!testLogSession?.active && type !== "test_stopped") return;
    testLogSession.events.push({timestamp, type, ...detail});
    testLogSession.events = testLogSession.events.slice(
        -TEST_LOG_MAX_EVENTS
    );
    if (persist) saveTestLogSession();
    refreshTestLoggingUI();
}

function compactRuntime(runtime) {
    if (!runtime) return null;
    return {
        state: runtime.state ?? null,
        fps: Number(runtime.fps || 0),
        speed: Number(runtime.speed || 0),
        drop_frames: Number(runtime.drop_frames || 0),
        dup_frames: Number(runtime.dup_frames || 0),
        cpu_percent: Number(runtime.cpu_percent || 0),
        memory_bytes: Number(runtime.memory_bytes || 0),
        last_progress_at: Number(runtime.last_progress_at || 0),
        restart_count: Number(runtime.restart_count || 0),
        last_restart_reason: runtime.last_restart_reason ?? null,
    };
}

function compactPlayer(player) {
    if (!player) return null;
    return {
        state: player.player_state ?? null,
        connection_state: player.connection_state ?? null,
        bitrate_bps: Number(player.bitrate_bps || 0),
        packets_received: Number(player.packets_received || 0),
        packets_lost: Number(player.packets_lost || 0),
        jitter_ms: Number(player.jitter_ms || 0),
        frames_decoded: Number(player.frames_decoded || 0),
        frames_dropped: Number(player.frames_dropped || 0),
        last_frame_progress_at: player.last_frame_progress_at ?? null,
        reconnect_count: Number(player.reconnect_count || 0),
        last_reconnect_at: player.last_reconnect_at ?? null,
        last_reconnect_reason: player.last_reconnect_reason ?? null,
    };
}

function buildTestLogSample(dashboard, timestamp) {
    const players = window.sourcePlayerDiagnostics?.() ?? {};
    return {
        timestamp,
        page_visible: document.visibilityState === "visible",
        browser_online: navigator.onLine,
        system: {
            cpu_percent: Number(dashboard.system?.cpu || 0),
            ram_percent: Number(dashboard.system?.ram || 0),
            temperature_c: Number(dashboard.system?.temperature || 0),
        },
        sources: (dashboard.sources ?? []).map(source => ({
            id: source.id,
            name: source.name,
            ready: Boolean(source.ready),
            online: Boolean(source.online),
            viewers: Number(source.viewers || 0),
            codec: source.codec ?? null,
            width: Number(source.width || 0),
            height: Number(source.height || 0),
            health: source.health?.code ?? null,
            runtime: compactRuntime(source.runtime),
            player: compactPlayer(players[source.id]),
        })),
    };
}

function captureSourceStateEvents(sources) {
    for (const source of sources ?? []) {
        const ready = Boolean(source.ready);
        if (
            Object.prototype.hasOwnProperty.call(
                lastTestSourceStates,
                source.id
            ) &&
            lastTestSourceStates[source.id] !== ready
        ) {
            recordTestLogEvent(
                ready ? "source_online" : "source_offline",
                {source_id: source.id, source_name: source.name},
                new Date().toISOString(),
                false
            );
        }
        lastTestSourceStates[source.id] = ready;
    }
}

function updateTestLogging(dashboard, force = false) {
    refreshTestLoggingUI();
    if (!testLogSession?.active || !dashboard) return;
    const now = Date.now();
    if (
        !force &&
        now - Number(testLogSession.last_sample_at || 0) <
            TEST_LOG_SAMPLE_INTERVAL_MS
    ) {
        return;
    }
    captureSourceStateEvents(dashboard.sources);
    testLogSession.samples.push(
        buildTestLogSample(dashboard, new Date(now).toISOString())
    );
    testLogSession.samples = testLogSession.samples.slice(
        -TEST_LOG_MAX_SAMPLES
    );
    testLogSession.last_sample_at = now;
    if (
        now - Number(testLogSession.last_persist_at || 0) >=
            TEST_LOG_PERSIST_INTERVAL_MS
    ) {
        testLogSession.last_persist_at = now;
        saveTestLogSession();
    }
    refreshTestLoggingUI();
}

function testSessionDurationSeconds() {
    if (!testLogSession) return 0;
    const end = testLogSession.active
        ? Date.now()
        : Date.parse(testLogSession.stopped_at || testLogSession.started_at);
    return Math.max(
        0,
        Math.round((end - Date.parse(testLogSession.started_at)) / 1000)
    );
}

function refreshTestLoggingUI() {
    const state = document.getElementById("test-session-state");
    if (!state) return;
    const active = Boolean(testLogSession?.active);
    state.textContent = active
        ? "Aufzeichnung läuft"
        : (testLogSession ? "Beendet" : "Nicht gestartet");
    state.classList.toggle("is-recording", active);
    updateValue(
        "test-session-duration",
        testLogSession
            ? `Laufzeit ${formatRecordingDuration(testSessionDurationSeconds())}`
            : "Laufzeit —"
    );
    updateValue(
        "test-session-samples",
        `${testLogSession?.samples?.length ?? 0} Messpunkte`
    );
    updateValue(
        "test-session-events",
        `${testLogSession?.events?.length ?? 0} Ereignisse`
    );
    document.getElementById("test-session-start").disabled = active;
    document.getElementById("test-session-stop").disabled = !active;
    document.getElementById("test-session-download").disabled =
        !testLogSession || testLogSession.samples.length === 0;
    document.getElementById("test-session-clear").disabled =
        !testLogSession || active;
}

function setTestLogFeedback(message, isError = false) {
    const feedback = document.getElementById("test-session-feedback");
    if (!feedback) return;
    feedback.textContent = message;
    feedback.classList.toggle("is-error", isError);
}

function downloadTestLogging() {
    if (!testLogSession) return;
    const payload = {
        ...testLogSession,
        exported_at: new Date().toISOString(),
    };
    const blob = new Blob(
        [JSON.stringify(payload, null, 2)],
        {type: "application/json"}
    );
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `open-bos-test-${testLogSession.id}.json`;
    link.click();
    window.setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}

window.addEventListener("open-bos:player-reconnect", event => {
    recordTestLogEvent("player_reconnect", event.detail ?? {});
});
window.addEventListener("online", () => recordTestLogEvent("browser_online"));
window.addEventListener("offline", () => recordTestLogEvent("browser_offline"));
document.addEventListener("visibilitychange", () => {
    recordTestLogEvent("visibility_changed", {
        visibility: document.visibilityState,
    });
});
window.addEventListener("load", () => {
    document.getElementById("test-session-start")?.addEventListener(
        "click", startTestLogging
    );
    document.getElementById("test-session-stop")?.addEventListener(
        "click", stopTestLogging
    );
    document.getElementById("test-session-download")?.addEventListener(
        "click", downloadTestLogging
    );
    document.getElementById("test-session-clear")?.addEventListener(
        "click", clearTestLogging
    );
    if (testLogSession?.active) {
        recordTestLogEvent("page_reloaded");
    }
    refreshTestLoggingUI();
});

window.updateTestLogging = updateTestLogging;
