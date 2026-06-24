/* MetGuardian - front-end logic.
 *
 * I talk to Python through the pywebview bridge (window.pywebview.api.*). Every
 * call returns a Promise. The bridge also pushes a "metguardian:scan-complete"
 * event after each scan, which I listen for to refresh the screen and surface
 * any newly damaged files.
 *
 * All rendering is plain DOM building; I escape every value that comes from a
 * file (names can contain characters that would otherwise break the markup).
 */

(function () {
    "use strict";

    // ---- Status display mapping -----------------------------------------
    // The DB stores OK / INACCESSIBLE / DAMAGED. "INACCESSIBLE" is shown to the
    // user as "Pending", which reads better for a file we simply could not
    // read this time around.
    const STATUS_LABEL = {
        OK: "OK",
        INACCESSIBLE: "Pending",
        DAMAGED: "Damaged",
    };
    const STATUS_CLASS = {
        OK: "mg-status--ok",
        INACCESSIBLE: "mg-status--pending",
        DAMAGED: "mg-status--damaged",
    };
    const REASON_LABEL = {
        REPLACED: "Replaced",
        REMOVED_OR_COMPLETED: "Removed / completed",
    };

    // ---- Tiny DOM helpers -----------------------------------------------

    function $(sel) { return document.querySelector(sel); }
    function $all(sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); }

    function escapeHtml(value) {
        if (value === null || value === undefined) return "";
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function shortHash(hash) {
        if (!hash) return "—";
        return hash.length > 14 ? hash.slice(0, 12) + "…" : hash;
    }

    // Turn the DB's UTC "YYYY-MM-DD HH:MM:SS" into the user's local time.
    function formatTime(value) {
        if (!value) return "—";
        const iso = value.indexOf("T") === -1 ? value.replace(" ", "T") + "Z" : value;
        const d = new Date(iso);
        if (isNaN(d.getTime())) return escapeHtml(value);
        return d.toLocaleString();
    }

    function statusPill(state) {
        const label = STATUS_LABEL[state] || state || "—";
        const cls = STATUS_CLASS[state] || "mg-status--archived";
        return '<span class="mg-status ' + cls + '">' + escapeHtml(label) + "</span>";
    }

    // ---- Bridge access ---------------------------------------------------

    function api() {
        return window.pywebview && window.pywebview.api ? window.pywebview.api : null;
    }

    // ---- Rendering -------------------------------------------------------

    function renderActive(rows) {
        const body = $("#active-rows");
        const empty = $("#active-empty");
        $("#count-active").textContent = rows.length;
        if (!rows.length) {
            body.innerHTML = "";
            empty.hidden = false;
            return;
        }
        empty.hidden = true;
        body.innerHTML = rows.map(function (r) {
            return "<tr>" +
                '<td class="mg-mono">' + escapeHtml(r.number) + "</td>" +
                '<td><div class="mg-filename" title="' + escapeHtml(r.file_name) + '">' +
                    (r.file_name ? escapeHtml(r.file_name) : '<span class="mg-muted">—</span>') + "</div></td>" +
                "<td>" + statusPill(r.state) + "</td>" +
                '<td class="mg-mono mg-muted" title="' + escapeHtml(r.file_hash) + '">' + escapeHtml(shortHash(r.file_hash)) + "</td>" +
                '<td class="mg-muted">' + formatTime(r.last_updated) + "</td>" +
                "</tr>";
        }).join("");
    }

    function renderArchive(rows) {
        const body = $("#archive-rows");
        const empty = $("#archive-empty");
        $("#count-archive").textContent = rows.length;
        if (!rows.length) {
            body.innerHTML = "";
            empty.hidden = false;
            return;
        }
        empty.hidden = true;
        body.innerHTML = rows.map(function (r) {
            return "<tr>" +
                '<td class="mg-mono">' + escapeHtml(r.number) + "</td>" +
                '<td><div class="mg-filename" title="' + escapeHtml(r.file_name) + '">' +
                    (r.file_name ? escapeHtml(r.file_name) : '<span class="mg-muted">—</span>') + "</div></td>" +
                '<td class="mg-mono mg-muted" title="' + escapeHtml(r.file_hash) + '">' + escapeHtml(shortHash(r.file_hash)) + "</td>" +
                "<td>" + escapeHtml(REASON_LABEL[r.reason] || r.reason) + "</td>" +
                '<td class="mg-muted">' + formatTime(r.archived_at) + "</td>" +
                "</tr>";
        }).join("");
    }

    function renderLog(rows) {
        const body = $("#log-rows");
        const empty = $("#log-empty");
        if (!rows.length) {
            body.innerHTML = "";
            empty.hidden = false;
            return;
        }
        empty.hidden = true;
        body.innerHTML = rows.map(function (r) {
            const change = (r.previous_state ? r.previous_state : "—") + " \u2192 " + r.new_state;
            return "<tr>" +
                '<td class="mg-muted">' + formatTime(r.timestamp) + "</td>" +
                '<td class="mg-mono">' + escapeHtml(r.number) + "</td>" +
                '<td class="mg-mono mg-muted">' + escapeHtml(change) + "</td>" +
                "<td>" + escapeHtml(r.message) + "</td>" +
                "</tr>";
        }).join("");
    }

    function renderStatus(status) {
        const dot = $("#status-dot");
        const text = $("#status-text");
        if (status.scheduler_running) {
            dot.className = "mg-dot is-running";
            const every = parseInt(status.scan_interval_seconds, 10);
            const mins = isFinite(every) ? Math.round(every / 60) : null;
            text.textContent = "Watching" + (mins ? " · every " + mins + " min" : "");
        } else {
            dot.className = "mg-dot is-idle";
            text.textContent = "Idle";
        }
    }

    function renderDamagedBanner(activeRows) {
        const damaged = activeRows.filter(function (r) { return r.state === "DAMAGED"; });
        const banner = $("#damaged-banner");
        if (!damaged.length) {
            banner.hidden = true;
            return;
        }
        const numbers = damaged.map(function (r) { return "#" + r.number; }).join(", ");
        const n = damaged.length;
        $("#damaged-banner-text").textContent =
            n + (n === 1 ? " file is" : " files are") + " damaged in the temp folder (" + numbers +
            "). Earlier valid backups are kept and can be used to recover.";
        banner.hidden = false;
    }

    // ---- Data refresh ----------------------------------------------------

    let refreshing = false;

    async function refreshAll() {
        const a = api();
        if (!a || refreshing) return;
        refreshing = true;
        try {
            const [status, active, archive, log] = await Promise.all([
                a.get_status(),
                a.get_active_files(),
                a.get_archive(),
                a.get_log(200),
            ]);
            renderStatus(status);
            renderActive(active);
            renderArchive(archive);
            renderLog(log);
            renderDamagedBanner(active);
        } catch (err) {
            console.error("Refresh failed:", err);
        } finally {
            refreshing = false;
        }
    }

    // ---- Actions ---------------------------------------------------------

    async function scanNow() {
        const a = api();
        const btn = $("#scan-now-btn");
        if (!a) return;
        btn.disabled = true;
        try {
            await a.scan_now();
            await refreshAll();
        } catch (err) {
            console.error("Scan failed:", err);
        } finally {
            btn.disabled = false;
        }
    }

    function switchTab(name) {
        $all(".mg-tab").forEach(function (t) {
            t.classList.toggle("is-active", t.dataset.tab === name);
        });
        $all(".mg-panel").forEach(function (p) {
            p.hidden = p.dataset.panel !== name;
        });
    }

    // ---- Wiring ----------------------------------------------------------

    function wireEvents() {
        $("#scan-now-btn").addEventListener("click", scanNow);

        $("#tabs").addEventListener("click", function (e) {
            const tab = e.target.closest(".mg-tab");
            if (tab) switchTab(tab.dataset.tab);
        });

        // The bridge pushes this after every scan (periodic or manual).
        window.addEventListener("metguardian:scan-complete", function () {
            refreshAll();
        });
    }

    function start() {
        wireEvents();
        refreshAll();
    }

    // pywebview injects the API asynchronously; wait for it. If the event has
    // already fired (fast start), the api() check in start() still holds.
    if (api()) {
        document.addEventListener("DOMContentLoaded", start);
    } else {
        window.addEventListener("pywebviewready", function () {
            if (document.readyState === "loading") {
                document.addEventListener("DOMContentLoaded", start);
            } else {
                start();
            }
        });
    }
})();
