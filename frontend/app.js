const LOG_URL =
    "https://ovpvsooxntcmrzarvwie.supabase.co/storage/v1/object/public/VYUH-%20Assets/alert_log.csv";

const SNAPSHOT_BASE_URL =
    "https://ovpvsooxntcmrzarvwie.supabase.co/storage/v1/object/public/VYUH-%20Assets/snapshots/";


const video = document.getElementById("mainVideo");

const totalAlertsElement = document.getElementById("totalAlerts");
const uniqueObjectsElement = document.getElementById("uniqueObjects");
const objectClassesElement = document.getElementById("objectClasses");

const timelineElement = document.getElementById("timeline");
const summaryElement = document.getElementById("summary");
const snapshotsElement = document.getElementById("snapshots");
const snapshotCountElement = document.getElementById("snapshotCount");

const lightbox = document.getElementById("lightbox");
const lightboxImage = document.getElementById("lightboxImage");
const lightboxCaption = document.getElementById("lightboxCaption");

const closeLightboxButton =
    document.getElementById("closeLightbox");

const jumpToVideoButton =
    document.getElementById("jumpToVideo");


let currentSnapshotTimestamp = 0;


// ------------------------------------------------------------
// CSV parser
// ------------------------------------------------------------

function parseCSV(text) {

    const lines = text
        .trim()
        .split(/\r?\n/);

    if (lines.length < 2) {
        return [];
    }

    const headers = parseCSVLine(lines[0]);

    return lines
        .slice(1)
        .map(line => {

            const values = parseCSVLine(line);

            const row = {};

            headers.forEach((header, index) => {
                row[header.trim()] =
                    values[index]?.trim() ?? "";
            });

            return row;
        });
}


function parseCSVLine(line) {

    const result = [];

    let current = "";
    let insideQuotes = false;

    for (let i = 0; i < line.length; i++) {

        const char = line[i];

        if (char === '"') {

            if (
                insideQuotes &&
                line[i + 1] === '"'
            ) {
                current += '"';
                i++;
            } else {
                insideQuotes = !insideQuotes;
            }

        } else if (
            char === "," &&
            !insideQuotes
        ) {

            result.push(current);
            current = "";

        } else {

            current += char;
        }
    }

    result.push(current);

    return result;
}


// ------------------------------------------------------------
// Load activity log
// ------------------------------------------------------------

async function loadActivityLog() {

    try {

        const response =
            await fetch(LOG_URL);

        if (!response.ok) {
            throw new Error(
                `HTTP ${response.status}`
            );
        }

        const csvText =
            await response.text();

        const rows =
            parseCSV(csvText);

        renderStatistics(rows);

        renderTimeline(rows);

        renderSummary(rows);

        renderSnapshots(rows);

    } catch (error) {

        console.error(
            "Failed to load alert log:",
            error
        );

        timelineElement.innerHTML =
            `<div class="loading">
                Failed to load activity log.
            </div>`;

        summaryElement.innerHTML =
            `<div class="loading">
                Failed to load detection summary.
            </div>`;

        snapshotsElement.innerHTML =
            `<div class="loading">
                Failed to load snapshots.
            </div>`;
    }
}


// ------------------------------------------------------------
// Statistics
// ------------------------------------------------------------

function renderStatistics(rows) {

    const totalAlerts =
        rows.length;

    const uniqueTrackIds =
        new Set(
            rows
                .map(row => row.track_id)
                .filter(id =>
                    id &&
                    id !== "-1"
                )
        );

    const uniqueLabels =
        new Set(
            rows
                .map(row => row.label)
                .filter(Boolean)
        );

    totalAlertsElement.textContent =
        totalAlerts;

    uniqueObjectsElement.textContent =
        uniqueTrackIds.size;

    objectClassesElement.textContent =
        uniqueLabels.size;
}


// ------------------------------------------------------------
// Timeline
// ------------------------------------------------------------

function renderTimeline(rows) {

    if (!rows.length) {

        timelineElement.innerHTML =
            `<div class="loading">
                No events found.
            </div>`;

        return;
    }

    const sortedRows =
        [...rows].sort(
            (a, b) =>
                Number(a.timestamp_sec) -
                Number(b.timestamp_sec)
        );

    timelineElement.innerHTML =
        sortedRows
            .map(row => {

                const timestamp =
                    Number(row.timestamp_sec) || 0;

                const label =
                    escapeHTML(row.label);

                const event =
                    escapeHTML(row.event);

                const trackId =
                    escapeHTML(row.track_id);

                const frame =
                    escapeHTML(row.frame);

                return `
                    <div
                        class="timeline-row"
                        onclick="seekTo(${timestamp})"
                    >

                        <div class="timeline-time">
                            ${timestamp.toFixed(1)}s
                        </div>

                        <div class="timeline-dot"></div>

                        <div class="timeline-info">

                            <div class="timeline-main">
                                ${label}
                            </div>

                            <div class="timeline-sub">
                                ${event}
                                · ID ${trackId}
                                · frame ${frame}
                            </div>

                        </div>

                    </div>
                `;
            })
            .join("");
}


// ------------------------------------------------------------
// Detection summary
// ------------------------------------------------------------

function renderSummary(rows) {

    if (!rows.length) {

        summaryElement.innerHTML =
            `<div class="loading">
                No detections found.
            </div>`;

        return;
    }

    const counts = {};

    rows.forEach(row => {

        const label =
            row.label || "unknown";

        counts[label] =
            (counts[label] || 0) + 1;
    });

    const sorted =
        Object.entries(counts)
            .sort(
                (a, b) =>
                    b[1] - a[1]
            );

    summaryElement.innerHTML =
        sorted
            .map(([label, count]) => {

                return `
                    <div class="summary-row">

                        <span>
                            ${escapeHTML(label)}
                        </span>

                        <span>
                            ${count}
                        </span>

                    </div>
                `;

            })
            .join("");
}


// ------------------------------------------------------------
// Snapshots
// ------------------------------------------------------------

function renderSnapshots(rows) {

    const snapshotRows =
        rows.filter(
            row =>
                row.snapshot_file &&
                row.snapshot_file.trim() !== ""
        );

    snapshotCountElement.textContent =
        `${snapshotRows.length} SNAPSHOTS`;

    if (!snapshotRows.length) {

        snapshotsElement.innerHTML =
            `<div class="loading">
                No snapshots found.
            </div>`;

        return;
    }

    snapshotsElement.innerHTML =
        snapshotRows
            .map(row => {

                const timestamp =
                    Number(row.timestamp_sec) || 0;

                const filename =
                    row.snapshot_file.trim();

                const imageURL =
                    SNAPSHOT_BASE_URL +
                    encodeURIComponent(filename);

                return `
                    <div
                        class="snapshot-card"
                        onclick='openSnapshot(
                            ${JSON.stringify(imageURL)},
                            ${JSON.stringify(
                                row.label
                            )},
                            ${JSON.stringify(
                                row.event
                            )},
                            ${timestamp}
                        )'
                    >

                        <img
                            src="${imageURL}"
                            alt="Detection snapshot"
                            loading="lazy"
                            onerror="this.style.display='none'"
                        >

                        <div class="snapshot-info">

                            <div class="snapshot-title">
                                ${escapeHTML(
                                    row.label
                                )}
                            </div>

                            <div class="snapshot-meta">
                                ID ${escapeHTML(
                                    row.track_id
                                )}
                                ·
                                ${escapeHTML(
                                    row.event
                                )}
                                ·
                                ${timestamp.toFixed(1)}s
                            </div>

                        </div>

                    </div>
                `;
            })
            .join("");
}


// ------------------------------------------------------------
// Video seeking
// ------------------------------------------------------------

function seekTo(seconds) {

    video.currentTime =
        Number(seconds);

    video.play().catch(() => {});
}


// ------------------------------------------------------------
// Snapshot lightbox
// ------------------------------------------------------------

function openSnapshot(
    imageURL,
    label,
    event,
    timestamp
) {

    currentSnapshotTimestamp =
        Number(timestamp);

    lightboxImage.src =
        imageURL;

    lightboxCaption.textContent =
        `${label} · ${event} · ${currentSnapshotTimestamp.toFixed(1)}s`;

    lightbox.classList.add("open");
}


function closeLightbox() {

    lightbox.classList.remove("open");

    lightboxImage.src = "";
}


closeLightboxButton.addEventListener(
    "click",
    closeLightbox
);


jumpToVideoButton.addEventListener(
    "click",
    () => {

        seekTo(
            currentSnapshotTimestamp
        );

        closeLightbox();
    }
);


lightbox.addEventListener(
    "click",
    event => {

        if (
            event.target === lightbox
        ) {
            closeLightbox();
        }
    }
);


document.addEventListener(
    "keydown",
    event => {

        if (
            event.key === "Escape"
        ) {
            closeLightbox();
        }
    }
);


// ------------------------------------------------------------
// Security helper
// ------------------------------------------------------------

function escapeHTML(value) {

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


// ------------------------------------------------------------
// Start application
// ------------------------------------------------------------

loadActivityLog();
