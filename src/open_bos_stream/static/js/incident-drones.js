"use strict";

// Einsatzseite: Drohnendaten zuordnen, Kennzahlen und Download.

function renderIncidentTelemetry(detail) {
    const incident = detail.incident;
    const summary = detail.telemetry || [];
    const data = incidentState.drones?.id === incident.id ? incidentState.drones.data : null;
    const active = (data?.drones || []).filter(item => item.active);
    const available = data?.available || [];
    const base = `/api/incidents/${Number(incident.id)}`;
    const meters = value => value === null || value === undefined ? "–" : `${Math.round(value)} m`;
    if (!active.length && !available.length && !summary.length) {
        return "";
    }
    return `
        <section class="bos-card incident-section">
            <h3>Drohnendaten (DJI)</h3>
            ${active.length ? `<ul class="org-memberships">${active.map(item => `
                <li>
                    <span><strong>${escapeHTML(item.name)}</strong>
                        <small class="is-muted">${item.state.online ? "wird aufgezeichnet" : "derzeit keine Daten"}</small></span>
                    ${item.can_release ? `<button class="bos-button bos-button-small" type="button"
                        data-serial="${escapeHTML(item.serial)}"
                        onclick="setIncidentDrone(this.dataset.serial, false)">Aufzeichnung beenden</button>` : ""}
                </li>`).join("")}</ul>` : ""}
            ${available.length ? `
                <div class="org-inline-add">
                    <select id="incident-add-drone" class="bos-input" aria-label="Drohne">
                        ${available.map(item => `<option value="${escapeHTML(item.serial)}">
                            ${escapeHTML(item.name)}${item.online ? " (sendet)" : ""}</option>`).join("")}
                    </select>
                    <button class="bos-button bos-button-small" type="button"
                        onclick="setIncidentDrone(document.getElementById('incident-add-drone').value, true)">Aufzeichnen</button>
                </div>` : ""}
            ${summary.length ? `<ul class="org-memberships">${summary.map(item => `
                <li><span><strong>${escapeHTML(item.name)}</strong>
                    <small class="is-muted">${item.records} Meldungen ·
                        ${escapeHTML(incidentTime(item.first, false))}–${escapeHTML(incidentTime(item.last, false))}${item.aircraft
                            ? ` · max. ${meters(item.max_elevation)} hoch, ${meters(item.max_home_distance)} entfernt` : ""}</small>
                </span></li>`).join("")}</ul>
                <div class="org-form-actions">
                    <a class="bos-button bos-button-small" href="${base}/telemetry.csv" download>Flugwerte (CSV)</a>
                    <a class="bos-button bos-button-small" href="${base}/telemetry.jsonl" download>Alle Daten (JSONL)</a>
                </div>` : '<p class="incident-empty">Noch keine Daten aufgezeichnet.</p>'}
        </section>`;
}

async function loadIncidentDrones(id) {
    try {
        incidentState.drones = {id, data: await api.get(`/api/incidents/${id}/drones`)};
    } catch (error) {
        console.debug("Drohnendaten:", error);
    }
}

async function setIncidentDrone(serial, record) {
    const url = incidentUrl(`/drones/${encodeURIComponent(serial)}`);
    const id = incidentState.openId;
    try {
        incidentState.drones = {id, data: await api.request(url, {method: record ? "POST" : "DELETE"})};
        setIncidentMessage(record ? "Aufzeichnung läuft." : "Aufzeichnung beendet.");
    } catch (error) {
        setIncidentMessage(error.message, true);
    }
    await loadIncidentDetail(id, {quiet: true});
}
