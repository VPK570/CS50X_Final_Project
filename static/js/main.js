document.addEventListener('DOMContentLoaded', () => {
    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');
    const btnSave = document.getElementById('btn-save');
    
    const fileInput = document.getElementById('torrent-file');
    const logWindow = document.getElementById('log-window');
    
    const els = {
        status: document.getElementById('status-badge'),
        speed: document.getElementById('speed'),
        peers: document.getElementById('peers'),
        downloaded: document.getElementById('downloaded'),
        total: document.getElementById('total'),
        filename: document.getElementById('filename'),
        percent: document.getElementById('percent'),
        bar: document.getElementById('progress-fill')
    };

    const toMB = (bytes) => (bytes / (1024 * 1024)).toFixed(2);

    const evtSource = new EventSource("/stream");
    
    evtSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        els.status.textContent = data.status;
        els.filename.textContent = data.filename || "No file active";
        els.speed.textContent = data.speed_kbps;
        els.peers.textContent = data.peers_connected;
        els.downloaded.textContent = toMB(data.downloaded_bytes);
        els.total.textContent = toMB(data.total_size);
        els.percent.textContent = data.progress_percent + "%";
        els.bar.style.width = data.progress_percent + "%";

        if (data.status === 'RUNNING') {
            btnStart.disabled = true;
            btnStop.disabled = false;
            btnSave.disabled = true;
            els.status.style.color = '#22c55e';
        } else if (data.status === 'COMPLETED') {
            btnStart.disabled = false;
            btnStop.disabled = true;
            btnSave.disabled = false;
            els.status.style.color = '#3b82f6';
        } else {
            btnStart.disabled = false;
            btnStop.disabled = true;
            btnSave.disabled = true;
            els.status.style.color = data.status === 'ERROR' ? '#ef4444' : '#fff';
        }

        if (data.logs && data.logs.length > 0) {
            data.logs.forEach(log => {
                const div = document.createElement('div');
                div.className = 'log-entry';
                div.textContent = `> ${log}`;
                logWindow.appendChild(div);
            });
            logWindow.scrollTop = logWindow.scrollHeight;
        }
    };

    btnStart.addEventListener('click', async () => {
        if (!fileInput.files[0]) {
            alert("Please select a .torrent file first");
            return;
        }

        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        
        btnSave.disabled = true;

        try {
            const res = await fetch('/start', {
                method: 'POST',
                body: formData
            });
            const result = await res.json();
            if (!res.ok) alert(result.error);
        } catch (err) {
            console.error(err);
        }
    });

    btnStop.addEventListener('click', async () => {
        await fetch('/stop', { method: 'POST' });
    });

    btnSave.addEventListener('click', () => {
        window.location.href = '/get_file';
    });
});