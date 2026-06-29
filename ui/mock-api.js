/* Development mock for window.pywebview.api.
 * Load this BEFORE app.js to simulate the Python bridge in a plain browser.
 * Never ship this file — it is only for UI development/debugging.
 */
window.pywebview = {
    api: {
        get_status: function () {
            return Promise.resolve({
                scheduler_running: true,
                active_count: 3,
                archive_count: 1,
                scan_interval_seconds: "300",
                temp_folder: "/home/user/eMule/Temp",
                backup_folder: "/home/user/eMule/Backup",
            });
        },
        get_active_files: function () {
            return Promise.resolve([
                {
                    number: "001",
                    file_name: "Concordia_s1x01 - (1080p).mkv",
                    state: "OK",
                    file_hash: "63e7228cb0c7a1f2e3d4b5c6a7890abc",
                    last_updated: "2026-06-29 10:15:00",
                    restorable: false,
                    backup_path: null,
                },
                {
                    number: "032",
                    file_name: "Matematica in azione.rar",
                    state: "DAMAGED",
                    file_hash: null,
                    last_updated: "2026-06-29 09:50:00",
                    restorable: true,
                    backup_path: "/home/user/eMule/Backup/abc123.met",
                },
                {
                    number: "099",
                    file_name: "Document sans titre.pdf",
                    state: "INACCESSIBLE",
                    file_hash: "deefcf8a90f5112233445566778899aa",
                    last_updated: "2026-06-29 09:00:00",
                    restorable: false,
                    backup_path: null,
                },
            ]);
        },
        get_archive: function () {
            return Promise.resolve([
                {
                    number: "002",
                    file_name: "!Arriesgate! - Mario Borghino.pdf",
                    file_hash: "e402e6d613208f1a2b3c4d5e6f708192",
                    reason: "REMOVED_OR_COMPLETED",
                    archived_at: "2026-06-28 18:30:00",
                    backup_path: "/home/user/eMule/Backup/e402e6d6.met",
                },
            ]);
        },
        get_log: function () {
            return Promise.resolve([
                {
                    timestamp: "2026-06-29 09:50:00",
                    number: "032",
                    file_hash: null,
                    previous_state: "OK",
                    new_state: "DAMAGED",
                    message: "032: damaged (OK -> DAMAGED)",
                },
                {
                    timestamp: "2026-06-28 18:30:00",
                    number: "002",
                    file_hash: "e402e6d6",
                    previous_state: "OK",
                    new_state: "ARCHIVED",
                    message: "002: removed or completed",
                },
            ]);
        },
        get_config: function () {
            return Promise.resolve({
                temp_folder: "/home/user/eMule/Temp",
                backup_folder: "/home/user/eMule/Backup",
                scan_interval_seconds: "300",
                mtime_guard_seconds: "10",
                dark_mode: "0",
            });
        },
        get_detail: function (number) {
            return Promise.resolve({
                ok: true,
                detail: {
                    source: "temp",
                    source_path: "/home/user/eMule/Temp/001.part.met",
                    version: "0xE0",
                    file_hash: "63e7228cb0c7a1f2e3d4b5c6a7890abc",
                    filename: "Concordia_s1x01 - (1080p).mkv",
                    partfilename: "001.part",
                    filesize: 1725595648,
                    filesize_str: "1.61 GB",
                    date: "2026-06-29 10:15:00 UTC",
                    num_parts: 13,
                    parts_hash: [],
                    gaps: [
                        { start: 0,         end: 104857600,  size: 104857600  },
                        { start: 209715200, end: 314572800,  size: 104857600  },
                        { start: 524288000, end: 629145600,  size: 104857600  },
                        { start: 943718400, end: 1048576000, size: 104857600  },
                        { start: 1258291200,end: 1363148800, size: 104857600  },
                    ],
                    gap_count: 5,
                    downloaded: 1200253648,
                    downloaded_str: "1.12 GB",
                    missing: 524288000,
                    missing_str: "500.00 MB",
                    percent_done: 69.6,
                    tags: {
                        dl_priority:  2,
                        shared_upload: 5,
                        status:       93914,
                        transferred:  928961408,
                        aich_hash:    "CV6VUAGOUNBW6PCEIOT5VMKJZ2MBJMN7",
                    },
                },
            });
        },
        save_config:   function (s) { return Promise.resolve({ ok: true, config: s, warnings: [], scan: null }); },
        scan_now:      function ()  { return Promise.resolve({ ran: true, scanned: 3 }); },
        restore_files: function ()  { return Promise.resolve({ ok: true, results: {} }); },
        pick_folder:   function ()  { return Promise.resolve({ ok: true, path: null }); },
    },
};

// Simulate pywebviewready so app.js starts normally.
window.dispatchEvent(new Event("pywebviewready"));
