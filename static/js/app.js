document.addEventListener('DOMContentLoaded', () => {
    const urlInput = document.getElementById('urlInput');
    const pasteBtn = document.getElementById('pasteBtn');
    const inspectBtn = document.getElementById('inspectBtn');
    const previewCard = document.getElementById('previewCard');
    const previewThumb = document.getElementById('previewThumb');
    const previewTitle = document.getElementById('previewTitle');
    const previewMeta = document.getElementById('previewMeta');
    const formatOptions = document.getElementById('formatOptions');

    const progressCard = document.getElementById('progressCard');
    const progressStatus = document.getElementById('progressStatus');
    const progressPercent = document.getElementById('progressPercent');
    const progressBarFill = document.getElementById('progressBarFill');
    const progressSpeed = document.getElementById('progressSpeed');
    const progressDownloaded = document.getElementById('progressDownloaded');
    const progressEta = document.getElementById('progressEta');

    const historyList = document.getElementById('historyList');
    const searchInput = document.getElementById('searchInput');

    const playerModal = document.getElementById('playerModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalClose = document.getElementById('modalClose');
    const modalVideo = document.getElementById('modalVideo');
    const modalAudio = document.getElementById('modalAudio');

    let activeEventSource = null;
    let fetchedVideoInfo = null;

    // Clipboard Auto-Paste with fallback for HTTP / Tailscale contexts
    pasteBtn.addEventListener('click', async () => {
        // 1. Try modern Clipboard API
        if (navigator.clipboard && typeof navigator.clipboard.readText === 'function') {
            try {
                const text = await navigator.clipboard.readText();
                if (text) {
                    urlInput.value = text.trim();
                    urlInput.focus();
                    return;
                }
            } catch (err) {
                console.warn('Clipboard API restricted or denied:', err);
            }
        }

        // 2. Fallback for HTTP / Tailscale IP (browsers restrict clipboard.readText on non-HTTPS)
        urlInput.focus();
        urlInput.select();

        // 3. Simple fallback prompt for 1-tap paste if API is blocked by browser
        const pasted = prompt('Paste YouTube link:');
        if (pasted) {
            urlInput.value = pasted.trim();
        }
    });

    // Preset Buttons (1-Tap Download)
    document.querySelectorAll('.btn-preset').forEach(btn => {
        btn.addEventListener('click', () => {
            const preset = btn.getAttribute('data-preset');
            const url = urlInput.value.trim();
            if (!url) {
                alert('Please paste a YouTube URL first!');
                urlInput.focus();
                return;
            }
            startDownload(url, preset);
        });
    });

    // Inspect Formats
    inspectBtn.addEventListener('click', async () => {
        const url = urlInput.value.trim();
        if (!url) {
            alert('Please paste a YouTube URL first!');
            urlInput.focus();
            return;
        }

        inspectBtn.innerText = '⏳ Fetching Formats...';
        inspectBtn.disabled = true;

        try {
            const res = await fetch('/api/info', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to inspect formats');
            }

            fetchedVideoInfo = await res.json();

            // Display preview card
            previewThumb.src = fetchedVideoInfo.thumbnail || '';
            previewTitle.innerText = fetchedVideoInfo.title || 'Video Title';
            previewMeta.innerText = `${fetchedVideoInfo.uploader} • ${fetchedVideoInfo.duration_str}`;
            
            formatOptions.innerHTML = '';
            
            // Add Format Chips
            if (fetchedVideoInfo.formats && fetchedVideoInfo.formats.length > 0) {
                fetchedVideoInfo.formats.forEach(f => {
                    const chip = document.createElement('div');
                    chip.className = 'chip-format';
                    chip.innerText = `${f.resolution} (${f.ext.toUpperCase()})`;
                    chip.addEventListener('click', () => {
                        startDownload(url, 'custom', f.format_id);
                    });
                    formatOptions.appendChild(chip);
                });
            }

            previewCard.style.display = 'block';
        } catch (err) {
            alert(`Error: ${err.message}`);
        } finally {
            inspectBtn.innerText = '⚙️ Advanced Formats (4K, 720p, FLAC)';
            inspectBtn.disabled = false;
        }
    });

    // Start Download Function
    async function startDownload(url, preset, customFormatId = null) {
        if (activeEventSource) {
            activeEventSource.close();
        }

        progressCard.style.display = 'block';
        progressStatus.innerText = 'Starting download on server...';
        progressPercent.innerText = '0%';
        progressBarFill.style.width = '0%';
        progressSpeed.innerText = '0 MB/s';
        progressDownloaded.innerText = '0 MB / 0 MB';
        progressEta.innerText = 'Calculating...';

        try {
            const res = await fetch('/api/download', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: url,
                    preset: preset,
                    format_id: customFormatId
                })
            });

            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail || 'Failed to start download');
            }

            const data = await res.json();
            const taskId = data.task_id;

            // Subscribe to SSE real-time progress
            trackProgress(taskId);
        } catch (err) {
            progressStatus.innerText = `Error: ${err.message}`;
            progressStatus.style.color = 'var(--accent-danger)';
        }
    }

    // SSE Progress Tracker
    function trackProgress(taskId) {
        activeEventSource = new EventSource(`/api/progress/${taskId}`);

        activeEventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.status === 'downloading') {
                progressStatus.innerText = 'Downloading on server...';
                progressPercent.innerText = `${data.percent}%`;
                progressBarFill.style.width = `${data.percent}%`;
                progressSpeed.innerText = data.speed_str || '0 MB/s';
                progressDownloaded.innerText = `${data.downloaded_str} / ${data.total_str}`;
                progressEta.innerText = `ETA: ${data.eta_str}`;
            } else if (data.status === 'converting') {
                progressStatus.innerText = 'Converting & finalizing...';
                progressPercent.innerText = '99%';
                progressBarFill.style.width = '99%';
                progressEta.innerText = 'Finalizing file...';
            } else if (data.status === 'completed') {
                progressStatus.innerText = '✅ Complete! Saving to phone...';
                progressPercent.innerText = '100%';
                progressBarFill.style.width = '100%';
                progressEta.innerText = 'Saved!';

                activeEventSource.close();

                // AUTO-TRIGGER DIRECT DOWNLOAD TO USER'S DEVICE
                if (data.filename) {
                    triggerDeviceDownload(data.filename);
                }

                // Refresh history
                loadHistory();
            } else if (data.status === 'failed') {
                progressStatus.innerText = `❌ Download Failed: ${data.error}`;
                progressStatus.style.color = 'var(--accent-danger)';
                activeEventSource.close();
            }
        };

        activeEventSource.onerror = () => {
            activeEventSource.close();
        };
    }

    // Trigger Device File Download
    function triggerDeviceDownload(filename) {
        const downloadUrl = `/api/files/${encodeURIComponent(filename)}/download`;
        
        // Create invisible anchor link to trigger browser native download prompt on iOS/Android/PC
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    // Load History
    async function loadHistory(query = '') {
        try {
            const endpoint = query ? `/api/history?q=${encodeURIComponent(query)}` : '/api/history';
            const res = await fetch(endpoint);
            if (!res.ok) return;

            const records = await res.json();
            renderHistory(records);
        } catch (err) {
            console.error('Failed to load history', err);
        }
    }

    // Render History List
    function renderHistory(records) {
        historyList.innerHTML = '';

        if (!records || records.length === 0) {
            historyList.innerHTML = `
                <div style="text-align: center; color: var(--text-muted); padding: 20px;">
                    No download history yet. Paste a link above to get started!
                </div>
            `;
            return;
        }

        records.forEach(item => {
            const el = document.createElement('div');
            el.className = 'history-item';
            
            const dateStr = item.timestamp ? new Date(item.timestamp).toLocaleDateString() : '';
            const sizeStr = item.filesize ? formatBytes(item.filesize) : '';

            el.innerHTML = `
                <img class="history-thumb" src="${item.thumbnail || ''}" alt="Thumbnail" onerror="this.src=''">
                <div class="history-details">
                    <div class="history-title" title="${escapeHtml(item.title)}">${escapeHtml(item.title)}</div>
                    <div class="history-sub">
                        <span class="tag-format">${escapeHtml(item.format_note || 'Media')}</span>
                        <span>${escapeHtml(item.uploader)}</span>
                        ${sizeStr ? `• <span>${sizeStr}</span>` : ''}
                        ${dateStr ? `• <span>${dateStr}</span>` : ''}
                    </div>
                </div>
                <div class="history-actions">
                    <button type="button" class="btn-action download-btn" title="Download to Device" data-file="${escapeHtml(item.filename)}">
                        📥
                    </button>
                    <button type="button" class="btn-action play-btn" title="Play Preview" data-file="${escapeHtml(item.filename)}" data-title="${escapeHtml(item.title)}" data-audio="${item.is_audio}">
                        ▶️
                    </button>
                    <button type="button" class="btn-action delete-btn" title="Delete Entry" data-id="${item.id}">
                        🗑️
                    </button>
                </div>
            `;

            // Download Button Handler
            el.querySelector('.download-btn').addEventListener('click', () => {
                triggerDeviceDownload(item.filename);
            });

            // Play Button Handler
            el.querySelector('.play-btn').addEventListener('click', () => {
                openPlayerModal(item.filename, item.title, item.is_audio);
            });

            // Delete Button Handler
            el.querySelector('.delete-btn').addEventListener('click', async () => {
                if (confirm(`Delete "${item.title}" from history?`)) {
                    await fetch(`/api/history/${item.id}`, { method: 'DELETE' });
                    loadHistory(searchInput.value.trim());
                }
            });

            historyList.appendChild(el);
        });
    }

    // Search Input Listener
    searchInput.addEventListener('input', () => {
        loadHistory(searchInput.value.trim());
    });

    // Player Modal Functions
    function openPlayerModal(filename, title, isAudio) {
        modalTitle.innerText = title;
        const streamUrl = `/api/files/${encodeURIComponent(filename)}/stream`;

        if (isAudio) {
            modalVideo.style.display = 'none';
            modalVideo.pause();
            modalAudio.style.display = 'block';
            modalAudio.src = streamUrl;
            modalAudio.play();
        } else {
            modalAudio.style.display = 'none';
            modalAudio.pause();
            modalVideo.style.display = 'block';
            modalVideo.src = streamUrl;
            modalVideo.play();
        }

        playerModal.style.display = 'flex';
    }

    modalClose.addEventListener('click', () => {
        playerModal.style.display = 'none';
        modalVideo.pause();
        modalAudio.pause();
    });

    playerModal.addEventListener('click', (e) => {
        if (e.target === playerModal) {
            playerModal.style.display = 'none';
            modalVideo.pause();
            modalAudio.pause();
        }
    });

    // Helper functions
    function formatBytes(bytes) {
        if (!bytes) return '';
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(1024));
        return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${sizes[i]}`;
    }

    function escapeHtml(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    // Initial load
    loadHistory();
});
