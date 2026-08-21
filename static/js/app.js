document.addEventListener('DOMContentLoaded', () => {
    const urlInput = document.getElementById('urlInput');
    const clearBtn = document.getElementById('clearBtn');
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

    const step1 = document.getElementById('step1');
    const step2 = document.getElementById('step2');
    const step3 = document.getElementById('step3');
    const step4 = document.getElementById('step4');
    const line1 = document.getElementById('line1');
    const line2 = document.getElementById('line2');
    const line3 = document.getElementById('line3');

    const historyList = document.getElementById('historyList');
    const searchInput = document.getElementById('searchInput');

    const playerModal = document.getElementById('playerModal');
    const modalTitle = document.getElementById('modalTitle');
    const modalClose = document.getElementById('modalClose');
    const modalVideo = document.getElementById('modalVideo');
    const modalAudio = document.getElementById('modalAudio');

    let activeEventSource = null;
    let fetchedVideoInfo = null;

    // Toggle Inline Clear Button
    function toggleClearBtn() {
        if (urlInput.value.trim().length > 0) {
            clearBtn.style.display = 'flex';
        } else {
            clearBtn.style.display = 'none';
        }
    }

    urlInput.addEventListener('input', toggleClearBtn);

    clearBtn.addEventListener('click', () => {
        urlInput.value = '';
        toggleClearBtn();
        urlInput.focus();
        previewCard.style.display = 'none';
    });

    // Toast notification helper
    function showToast(message, type = 'info', duration = 4000) {
        let container = document.getElementById('toastContainer');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toastContainer';
            container.className = 'toast-container';
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = message;
        container.appendChild(toast);

        requestAnimationFrame(() => {
            toast.classList.add('show');
        });

        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, duration);
    }

    // Clipboard Auto-Paste
    pasteBtn.addEventListener('click', async () => {
        // Direct automatic clipboard reading
        if (navigator.clipboard && typeof navigator.clipboard.readText === 'function') {
            try {
                const text = await navigator.clipboard.readText();
                if (text && text.trim().length > 0) {
                    urlInput.value = text.trim();
                    toggleClearBtn();
                    urlInput.focus();
                    showToast('📋 Link pasted automatically!', 'success', 2000);
                    return;
                }
            } catch (err) {
                console.log('Clipboard read blocked:', err);
            }
        }

        // If running on HTTP without secure origin flag, browser blocks background clipboard reads
        urlInput.focus();
        showToast('🔒 Browser blocks automatic paste on HTTP. Use HTTPS or enable Chrome Secure Origin flag.', 'warning', 5000);
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

        inspectBtn.innerText = '⏳ Inspecting Formats...';
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
            inspectBtn.innerText = '⚙️ Format Inspector (4K, 720p, FLAC)';
            inspectBtn.disabled = false;
        }
    });

    // Stepper UI Manager
    function updateStepper(currentStep) {
        // Reset all steps
        [step1, step2, step3, step4].forEach(s => s.classList.remove('active', 'completed'));
        [line1, line2, line3].forEach(l => l.classList.remove('completed'));

        if (currentStep >= 1) {
            step1.classList.add(currentStep > 1 ? 'completed' : 'active');
        }
        if (currentStep >= 2) {
            line1.classList.add('completed');
            step2.classList.add(currentStep > 2 ? 'completed' : 'active');
        }
        if (currentStep >= 3) {
            line2.classList.add('completed');
            step3.classList.add(currentStep > 3 ? 'completed' : 'active');
        }
        if (currentStep >= 4) {
            line3.classList.add('completed');
            step4.classList.add('completed');
        }
    }

    // Start Download Function
    async function startDownload(url, preset, customFormatId = null) {
        if (activeEventSource) {
            activeEventSource.close();
        }

        progressCard.style.display = 'block';
        updateStepper(1); // Step 1: Fetching metadata
        progressStatus.innerText = 'Step 1: Fetching video metadata...';
        progressPercent.innerText = '5%';
        progressBarFill.style.width = '5%';
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
            
            if (data.status === 'starting') {
                updateStepper(1);
                progressStatus.innerText = 'Step 1: Preparing download queue...';
                progressPercent.innerText = '10%';
                progressBarFill.style.width = '10%';
            } else if (data.status === 'downloading') {
                updateStepper(2); // Step 2: Downloading
                progressStatus.innerText = 'Step 2: Downloading media fragments...';
                progressPercent.innerText = `${data.percent}%`;
                progressBarFill.style.width = `${data.percent}%`;
                progressSpeed.innerText = data.speed_str || '0 MB/s';
                progressDownloaded.innerText = `${data.downloaded_str} / ${data.total_str}`;
                progressEta.innerText = data.eta_str ? (data.eta_str.startsWith('ETA') ? data.eta_str : `ETA: ${data.eta_str}`) : 'ETA: Calculating...';
            } else if (data.status === 'converting') {
                updateStepper(3); // Step 3: Converting / Merging
                progressStatus.innerText = 'Step 3: Merging & converting audio/video...';
                progressPercent.innerText = '95%';
                progressBarFill.style.width = '95%';
                progressEta.innerText = 'FFmpeg processing...';
            } else if (data.status === 'completed') {
                updateStepper(4); // Step 4: Complete & Save
                progressStatus.innerText = 'Step 4: Complete! Downloading to your device...';
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
                progressStatus.innerText = `❌ Failed: ${data.error}`;
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
                <div style="text-align: center; color: var(--text-muted); padding: 16px;">
                    No history yet. Paste a YouTube link above!
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
                        ${sizeStr ? `• <span>${sizeStr}</span>` : ''}
                        ${dateStr ? `• <span>${dateStr}</span>` : ''}
                    </div>
                </div>
                <div class="history-actions">
                    <button type="button" class="btn-action download-btn" title="Save to Device" data-file="${escapeHtml(item.filename)}">
                        📥
                    </button>
                    <button type="button" class="btn-action play-btn" title="Play Preview" data-file="${escapeHtml(item.filename)}" data-title="${escapeHtml(item.title)}" data-audio="${item.is_audio}">
                        ▶️
                    </button>
                    <button type="button" class="btn-action delete-btn" title="Delete" data-id="${item.id}">
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
                if (confirm(`Delete "${item.title}"?`)) {
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
    toggleClearBtn();
});
