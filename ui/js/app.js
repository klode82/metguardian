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

    // ---- Generic dialog (Franken UI uk-modal) ---------------------------
    // showDialog({ icon, title, body, buttons }) → Promise<key|null>
    //
    // icon    : "warning" | "info" | null   (maps to a pre-rendered icon slot)
    // title   : string
    // body    : HTML string (caller is responsible for escaping user data)
    // buttons : [{ key, label, cls }]  — injected into #mg-dialog-footer
    //           cls defaults to "uk-btn-secondary"
    //           key is the string resolved by the Promise when clicked
    //
    // Clicking the UIkit backdrop / pressing Esc resolves with null.
    // There must be at most one dialog open at a time (typical for modals).

    var dialogResolve = null;

    function showDialog(opts) {
        return new Promise(function (resolve) {
            dialogResolve = resolve;

            // Show the right icon; hide the others.
            $all("[data-dialog-icon]").forEach(function (el) { el.hidden = true; });
            if (opts.icon) {
                var iconEl = $("[data-dialog-icon='" + opts.icon + "']");
                if (iconEl) iconEl.hidden = false;
            }

            // Title and body.
            $("#mg-dialog-title").textContent = opts.title || "";
            $("#mg-dialog-body").innerHTML = opts.body || "";

            // Buttons.
            var footer = $("#mg-dialog-footer");
            footer.innerHTML = "";
            var btns = opts.buttons || [{ key: "ok", label: "OK", cls: "uk-btn-primary" }];
            btns.forEach(function (btn) {
                var b = document.createElement("button");
                b.type = "button";
                b.className = "uk-btn " + (btn.cls || "uk-btn-secondary");
                b.textContent = btn.label;
                b.addEventListener("click", function () {
                    UIkit.modal("#mg-dialog").hide();
                    if (dialogResolve) {
                        var r = dialogResolve;
                        dialogResolve = null;
                        r(btn.key);
                    }
                });
                footer.appendChild(b);
            });

            UIkit.modal("#mg-dialog").show();
        });
    }

    // When the UIkit modal is hidden by any means (backdrop click, Esc, or our
    // button handler) resolve the promise with null if it hasn't been resolved yet.
    document.getElementById("mg-dialog").addEventListener("hidden", function () {
        if (dialogResolve) {
            var r = dialogResolve;
            dialogResolve = null;
            r(null);
        }
    });

    // ---- Detail modal -------------------------------------------------------
    // openDetail(number, backupPath) → calls get_detail on the bridge, renders
    // the result into #mg-detail-modal and opens it.
    //
    // backupPath should be passed for archive rows (the temp file no longer
    // exists); it is null for active rows (bridge tries the temp file first).

    function _fmtBytes(n) {
        if (n == null || n < 0) return "—";
        if (n >= 1073741824) return (n / 1073741824).toFixed(2) + " GB";
        if (n >= 1048576)    return (n / 1048576).toFixed(2) + " MB";
        if (n >= 1024)       return (n / 1024).toFixed(2) + " KB";
        return n + " B";
    }

    function _detailRow(label, valueHtml, rawHtml) {
        return '<div class="mg-detail-label">' + escapeHtml(label) + '</div>' +
               '<div class="mg-detail-value">' + (rawHtml ? valueHtml : escapeHtml(String(valueHtml || "—"))) + '</div>';
    }

    function renderDetailContent(detail) {
        var html = "";

        // ---- File info ----
        var sourceBadge = detail.source === "temp"
            ? '<span class="mg-detail-source-badge mg-detail-source-badge--temp">live file</span>'
            : '<span class="mg-detail-source-badge mg-detail-source-badge--backup">backup (last valid)</span>';

        html += '<div class="mg-detail-section">';
        html += '<h3 class="mg-detail-section-title">File info</h3>';
        html += '<div class="mg-detail-grid">';
        html += _detailRow("Source",    sourceBadge, true);
        html += _detailRow("Filename",  detail.filename || "—");
        if (detail.partfilename) html += _detailRow("Part file", detail.partfilename);
        html += _detailRow("Hash (MD4)", '<span class="mg-mono">' + escapeHtml(detail.file_hash) + '</span>', true);
        html += _detailRow("Size",      detail.filesize_str);
        html += _detailRow("Date",      detail.date);
        html += _detailRow("Version",   detail.version);
        html += _detailRow("Parts",     String(detail.num_parts));
        html += '</div></div>';

        // ---- Download progress ----
        if (detail.filesize > 0) {
            var pct = detail.percent_done || 0;
            html += '<div class="mg-detail-section">';
            html += '<h3 class="mg-detail-section-title">Download progress</h3>';
            html += '<div class="mg-detail-progress-bar">';
            html += '<div class="mg-detail-progress-fill" style="width:' + Math.min(100, pct).toFixed(1) + '%"></div>';
            html += '</div>';
            html += '<div class="mg-detail-progress-labels">';
            html += '<span>' + escapeHtml(detail.downloaded_str) + ' downloaded (' + pct.toFixed(1) + '%)</span>';
            html += '<span>' + (detail.missing > 0 ? escapeHtml(detail.missing_str) + ' missing' : 'Complete') + '</span>';
            html += '</div>';

            if (detail.gaps && detail.gaps.length) {
                var shown = detail.gaps.slice(0, 25);
                html += '<div class="mg-detail-gap-list">';
                shown.forEach(function (g) {
                    html += '<div class="mg-detail-gap-item">' +
                        '<span class="mg-detail-gap-range">' +
                        g.start.toLocaleString() + ' &ndash; ' + g.end.toLocaleString() +
                        '</span>' +
                        '<span>' + escapeHtml(_fmtBytes(g.size)) + '</span>' +
                        '</div>';
                });
                if (detail.gaps.length > 25) {
                    html += '<div class="mg-muted" style="font-size:12px;margin-top:4px;">… and ' +
                        (detail.gaps.length - 25) + ' more gaps</div>';
                }
                html += '</div>';
            } else {
                html += '<p class="mg-muted" style="font-size:12.5px;margin:0">' +
                    'No gaps — file may be fully downloaded or gap data is unavailable.</p>';
            }
            html += '</div>';
        }

        // ---- Additional tags ----
        var tagKeys = Object.keys(detail.tags || {});
        if (tagKeys.length) {
            html += '<div class="mg-detail-section">';
            html += '<h3 class="mg-detail-section-title">Tags</h3>';
            html += '<table class="mg-detail-tag-table">';
            tagKeys.forEach(function (k) {
                var v = detail.tags[k];
                html += '<tr><td>' + escapeHtml(k) + '</td>' +
                    '<td class="mg-detail-tag-value">' + escapeHtml(String(v)) + '</td></tr>';
            });
            html += '</table></div>';
        }

        return html;
    }

    async function openDetail(number, backupPath) {
        var a = api();
        if (!a) return;

        // Open modal immediately with a loading placeholder.
        $("#mg-detail-title").textContent = "File #" + number;
        $("#mg-detail-body").innerHTML = '<p class="mg-muted" style="padding:8px 0">Loading…</p>';
        UIkit.modal("#mg-detail-modal").show();

        try {
            var response = await a.get_detail(number, backupPath || null);
            if (!response || !response.ok) {
                $("#mg-detail-body").innerHTML =
                    '<p style="color:hsl(var(--destructive))">⚠ ' +
                    escapeHtml((response && response.error) || "Unknown error") + '</p>';
                return;
            }
            var detail = response.detail;
            $("#mg-detail-title").textContent = "File #" + number +
                (detail.filename ? "  ·  " + detail.filename : "");
            $("#mg-detail-body").innerHTML = renderDetailContent(detail);
        } catch (err) {
            console.error("get_detail failed:", err);
            $("#mg-detail-body").innerHTML =
                '<p style="color:hsl(var(--destructive))">⚠ Failed to load detail: ' +
                escapeHtml(String(err)) + '</p>';
        }
    }

    // ---- UI refresh helper -----------------------------------------------
    // Call this whenever dynamic HTML containing UIkit components (icons,
    // tooltips, dropdowns) is injected into an existing node. UIkit's
    // MutationObserver doesn't always catch innerHTML replacements; update()
    // forces a re-scan of the subtree.
    function refreshUI(el) {
        if (window.UIkit) UIkit.update(el || document.body);
    }

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

    // ---- Theme ----------------------------------------------------------
    // The theme color is a product decision, fixed to Teal; it is not exposed
    // to the user. Only dark mode is user-toggleable. The theme is applied as
    // a class on <html>: uk-theme-teal (+ "dark").
    const FIXED_THEME_COLOR = "teal";
    const DEFAULT_DARK = false;

    let currentDark = DEFAULT_DARK;

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

    // ---- Restore state --------------------------------------------------
    // restorableNumbers : slot numbers the bridge marked as restorable
    //                     (DAMAGED + backup physically on disk)
    // checkedNumbers    : Set of slot numbers currently checked in the table

    var restorableNumbers = [];
    var checkedNumbers = new Set();

    function updateRestoreBar() {
        var bar = $("#restore-bar");
        var selBtn = $("#restore-selected-btn");
        if (!restorableNumbers.length) {
            bar.hidden = true;
            return;
        }
        bar.hidden = false;
        selBtn.disabled = checkedNumbers.size === 0;
    }

    // ---- Rendering -------------------------------------------------------

    function renderActive(rows) {
        var body = $("#active-rows");
        var empty = $("#active-empty");
        $("#count-active").textContent = rows.length;

        // Preserve checkbox selections across refreshes: keep only numbers
        // that are still present and still restorable.
        var prevChecked = new Set(checkedNumbers);
        checkedNumbers.clear();
        restorableNumbers = rows
            .filter(function (r) { return r.restorable; })
            .map(function (r) { return r.number; });
        restorableNumbers.forEach(function (n) {
            if (prevChecked.has(n)) checkedNumbers.add(n);
        });

        if (!rows.length) {
            body.innerHTML = "";
            empty.hidden = false;
            updateRestoreBar();
            return;
        }
        empty.hidden = true;
        body.innerHTML = rows.map(function (r) {
            var checkCell = r.restorable
                ? '<td class="mg-col-check"><input type="checkbox" class="mg-restore-check"' +
                  ' data-number="' + escapeHtml(r.number) + '"' +
                  (checkedNumbers.has(r.number) ? " checked" : "") + "></td>"
                : '<td class="mg-col-check"></td>';
            return "<tr>" +
                checkCell +
                '<td class="mg-mono">' + escapeHtml(r.number) + "</td>" +
                '<td><div class="mg-filename" title="' + escapeHtml(r.file_name) + '">' +
                    (r.file_name ? escapeHtml(r.file_name) : '<span class="mg-muted">—</span>') + "</div></td>" +
                "<td>" + statusPill(r.state) + "</td>" +
                '<td class="mg-mono mg-muted" title="' + escapeHtml(r.file_hash) + '">' + escapeHtml(shortHash(r.file_hash)) + "</td>" +
                '<td class="mg-muted">' + formatTime(r.last_updated) + "</td>" +
                '<td class="mg-col-detail"><button class="uk-btn uk-btn-secondary uk-btn-sm mg-detail-btn"' +
                    ' data-number="' + escapeHtml(r.number) + '" type="button">Detail</button></td>' +
                "</tr>";
        }).join("");

        updateRestoreBar();
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
                '<td class="mg-col-detail"><button class="uk-btn uk-btn-secondary uk-btn-sm mg-detail-btn"' +
                    ' data-number="' + escapeHtml(r.number) + '"' +
                    ' data-backup-path="' + escapeHtml(r.backup_path || "") + '" type="button">Detail</button></td>' +
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

    // ---- Restore actions ------------------------------------------------

    async function openRestoreConfirm(numbers) {
        var count = numbers.length;
        var fileList = numbers.map(function (n) { return "#" + n; }).join(", ");
        var key = await showDialog({
            icon: "warning",
            title: "Before restoring",
            body:
                "<p>Make sure <strong>eMule is closed</strong> before proceeding.</p>" +
                "<p class=\"mg-muted\">MetGuardian monitors a folder, not a process &mdash; " +
                "the temp folder may be on a different machine or VM. " +
                "Restoring while eMule is open may corrupt the file again.</p>" +
                "<p class=\"mg-muted\">" +
                count + (count === 1 ? " file" : " files") +
                " to restore: <strong>" + escapeHtml(fileList) + "</strong></p>",
            buttons: [
                { key: "cancel",  label: "Cancel",  cls: "uk-btn-secondary" },
                { key: "confirm", label: "Restore", cls: "uk-btn-destructive" },
            ],
        });
        if (key === "confirm") {
            doRestore(numbers);
        }
    }

    async function doRestore(numbers) {
        var a = api();
        if (!a || !numbers.length) return;

        var resultsDiv = $("#restore-results");
        resultsDiv.innerHTML = "<div class=\"mg-restore-working\">Restoring " + numbers.length + " file(s)…</div>";
        resultsDiv.hidden = false;

        // Disable both restore buttons during the operation.
        $("#restore-selected-btn").disabled = true;
        $("#restore-all-btn").disabled = true;

        try {
            var response = await a.restore_files(numbers);
            if (!response || !response.ok) {
                resultsDiv.innerHTML =
                    "<div class=\"mg-restore-global-error\">⚠ " +
                    escapeHtml((response && response.error) || "Unknown error") + "</div>";
                updateRestoreBar();
                return;
            }
            var results = response.results || {};
            resultsDiv.innerHTML = numbers.map(function (n) {
                var r = results[n] || {};
                if (r.ok) {
                    return "<div class=\"mg-restore-item mg-restore-item--ok\">" +
                        "<span uk-icon=\"icon: check; ratio: 0.85\"></span> #" +
                        escapeHtml(n) + ": restored successfully.</div>";
                }
                return "<div class=\"mg-restore-item mg-restore-item--err\">" +
                    "<span uk-icon=\"icon: warning; ratio: 0.85\"></span> #" +
                    escapeHtml(n) + ": " + escapeHtml(r.error || "Unknown error") + "</div>";
            }).join("");
            refreshUI(resultsDiv);

            checkedNumbers.clear();
            // refreshAll() picks up the new states; the scan triggered by the
            // bridge's restore_files() will also fire a scan-complete event.
            await refreshAll();
        } catch (err) {
            console.error("restore_files failed:", err);
            resultsDiv.innerHTML =
                "<div class=\"mg-restore-global-error\">⚠ Restore failed: " +
                escapeHtml(String(err)) + "</div>";
            updateRestoreBar();
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

    // ---- Theme + Settings ------------------------------------------------

    function applyTheme(dark) {
        currentDark = !!dark;
        document.documentElement.className =
            "uk-theme-" + FIXED_THEME_COLOR + (dark ? " dark" : "");
    }

    function loadSettings(config) {
        // Folders
        $("#set-temp").value = config.temp_folder || "";
        $("#set-backup").value = config.backup_folder || "";
        // Interval: stored in seconds, shown in minutes.
        const secs = parseInt(config.scan_interval_seconds, 10);
        $("#set-interval").value = isFinite(secs) ? Math.max(1, Math.round(secs / 60)) : 5;
        // Appearance: dark mode only (color is fixed to Teal).
        const dark = config.dark_mode === "1" || config.dark_mode === "true";
        $("#set-dark").checked = dark;
        applyTheme(dark);
    }

    async function browseFolder(targetInputId) {
        const a = api();
        if (!a) return;
        try {
            const res = await a.pick_folder("Select a folder");
            if (res && res.ok && res.path) {
                $(targetInputId).value = res.path;
            }
        } catch (err) {
            console.error("pick_folder failed:", err);
        }
    }

    async function saveSettings() {
        const a = api();
        if (!a) return;
        const btn = $("#save-settings");
        const status = $("#save-status");
        const warnBox = $("#settings-warnings");
        const mins = Math.max(1, parseInt($("#set-interval").value, 10) || 5);

        const payload = {
            temp_folder: $("#set-temp").value.trim(),
            backup_folder: $("#set-backup").value.trim(),
            scan_interval_seconds: String(mins * 60),
            dark_mode: $("#set-dark").checked ? "1" : "0",
        };

        btn.disabled = true;
        status.textContent = "Saving…";
        warnBox.hidden = true;
        try {
            const result = await a.save_config(payload);
            if (result && result.ok) {
                status.textContent = "Saved";
                if (result.warnings && result.warnings.length) {
                    warnBox.innerHTML = result.warnings.map(function (w) {
                        return "<div>⚠ " + escapeHtml(w) + "</div>";
                    }).join("");
                    warnBox.hidden = false;
                }
                await refreshAll();
            } else {
                status.textContent = "Error";
                warnBox.innerHTML = "<div>⚠ " + escapeHtml(result && result.error ? result.error : "Unknown error") + "</div>";
                warnBox.hidden = false;
            }
        } catch (err) {
            console.error("save_config failed:", err);
            status.textContent = "Error";
        } finally {
            btn.disabled = false;
            setTimeout(function () { status.textContent = ""; }, 3000);
        }
    }

    // ---- Wiring ----------------------------------------------------------

    function wireEvents() {
        $("#scan-now-btn").addEventListener("click", scanNow);

        $("#tabs").addEventListener("click", function (e) {
            const tab = e.target.closest(".mg-tab");
            if (tab) switchTab(tab.dataset.tab);
        });

        // Settings: folder pickers.
        $("#browse-temp").addEventListener("click", function () { browseFolder("#set-temp"); });
        $("#browse-backup").addEventListener("click", function () { browseFolder("#set-backup"); });

        // Settings: save.
        $("#save-settings").addEventListener("click", saveSettings);

        // Settings: dark mode -> live preview.
        $("#set-dark").addEventListener("change", function (e) {
            applyTheme(e.target.checked);
        });

        // Restore: checkbox toggles (event delegation on the tbody).
        $("#active-rows").addEventListener("change", function (e) {
            var cb = e.target.closest(".mg-restore-check");
            if (!cb) return;
            var number = cb.dataset.number;
            if (cb.checked) {
                checkedNumbers.add(number);
            } else {
                checkedNumbers.delete(number);
            }
            updateRestoreBar();
        });

        // Restore selected.
        $("#restore-selected-btn").addEventListener("click", function () {
            var selected = Array.from(checkedNumbers);
            if (selected.length) openRestoreConfirm(selected);
        });

        // Restore all damaged.
        $("#restore-all-btn").addEventListener("click", function () {
            if (restorableNumbers.length) openRestoreConfirm(restorableNumbers.slice());
        });

        // Detail button — active rows (event delegation).
        $("#active-rows").addEventListener("click", function (e) {
            var btn = e.target.closest(".mg-detail-btn");
            if (btn) openDetail(btn.dataset.number, null);
        });

        // Detail button — archive rows (event delegation).
        $("#archive-rows").addEventListener("click", function (e) {
            var btn = e.target.closest(".mg-detail-btn");
            if (btn) openDetail(btn.dataset.number, btn.dataset.backupPath || null);
        });

        // Detail modal close button.
        $("#mg-detail-close").addEventListener("click", function () {
            UIkit.modal("#mg-detail-modal").hide();
        });

        // The bridge pushes this after every scan (periodic or manual).
        window.addEventListener("metguardian:scan-complete", function () {
            refreshAll();
        });
    }

    async function start() {
        wireEvents();
        const a = api();
        if (a) {
            try {
                const config = await a.get_config();
                loadSettings(config);   // also applies the saved theme
            } catch (err) {
                console.error("get_config failed:", err);
                applyTheme(DEFAULT_DARK);
            }
        }
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
