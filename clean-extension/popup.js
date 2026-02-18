// popup.js — SecureMeet Chrome Extension
// Connects to Desktop app via localhost:8765

const API_BASE = 'http://127.0.0.1:8765';

// DOM Elements
let connectionBadge, meetingStatus, deviceSelect, recordBtn, timer, levelBar;
let statusMsg, resultsSection, resultsArea, copyBtn, refreshBtn;

// State
let isConnected = false;
let isRecording = false;
let pollInterval = null;
let timerInterval = null;
let recordingStartTime = null;

document.addEventListener('DOMContentLoaded', () => {
  // Grab DOM elements
  connectionBadge = document.getElementById('connectionBadge');
  meetingStatus = document.getElementById('meetingStatus');
  deviceSelect = document.getElementById('deviceSelect');
  recordBtn = document.getElementById('recordBtn');
  timer = document.getElementById('timer');
  levelBar = document.getElementById('levelBar');
  statusMsg = document.getElementById('statusMsg');
  resultsSection = document.getElementById('resultsSection');
  resultsArea = document.getElementById('resultsArea');
  copyBtn = document.getElementById('copyBtn');
  refreshBtn = document.getElementById('refreshBtn');

  // Event listeners
  recordBtn.addEventListener('click', toggleRecording);
  copyBtn.addEventListener('click', copySummary);
  refreshBtn.addEventListener('click', fetchResults);

  // Initial checks
  checkConnection();
  detectMeeting();

  // Poll status every 2 seconds while popup is open
  pollInterval = setInterval(pollStatus, 2000);
});

// --- API Helpers ---

async function apiGet(endpoint) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json' }
  });
  return response.json();
}

async function apiPost(endpoint, body = {}) {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
  return response.json();
}

// --- Connection ---

async function checkConnection() {
  try {
    const data = await apiGet('/status');
    isConnected = true;
    isRecording = data.recording;

    connectionBadge.textContent = 'Connected';
    connectionBadge.className = 'connection-badge badge-connected';

    recordBtn.disabled = false;
    updateRecordButton();

    if (data.recording) {
      statusMsg.textContent = 'Recording in progress...';
      statusMsg.className = 'status-msg processing';
      startTimerUI();
    } else {
      statusMsg.textContent = 'Ready to record';
      statusMsg.className = 'status-msg';
    }

    // Check for available results
    if (data.has_transcript || data.has_summary) {
      fetchResults();
    }

    // Load devices
    loadDevices();

  } catch (e) {
    isConnected = false;
    connectionBadge.textContent = 'Disconnected';
    connectionBadge.className = 'connection-badge badge-disconnected';
    recordBtn.disabled = true;
    statusMsg.textContent = 'Launch SecureMeet Desktop to begin';
    statusMsg.className = 'status-msg error';
  }
}

// --- Polling ---

async function pollStatus() {
  if (!isConnected) {
    // Retry connection
    await checkConnection();
    return;
  }

  try {
    const data = await apiGet('/status');

    // Detect state changes
    if (data.recording && !isRecording) {
      // Recording started (possibly from Desktop app)
      isRecording = true;
      updateRecordButton();
      startTimerUI();
      statusMsg.textContent = 'Recording in progress...';
      statusMsg.className = 'status-msg processing';
    } else if (!data.recording && isRecording) {
      // Recording stopped
      isRecording = false;
      updateRecordButton();
      stopTimerUI();
      statusMsg.textContent = 'Processing...';
      statusMsg.className = 'status-msg processing';
      // Start polling for results
      pollForResults();
    }

    // Update audio level during recording
    if (data.recording && data.audio_level !== undefined) {
      const level = Math.min(data.audio_level * 500, 100);
      levelBar.style.width = level + '%';
    }

    // Update timer from server duration
    if (data.recording && data.duration) {
      updateTimerDisplay(data.duration);
    }

  } catch (e) {
    // Lost connection
    isConnected = false;
    connectionBadge.textContent = 'Disconnected';
    connectionBadge.className = 'connection-badge badge-disconnected';
    recordBtn.disabled = true;
    statusMsg.textContent = 'Desktop app disconnected';
    statusMsg.className = 'status-msg error';
  }
}

// --- Recording ---

async function toggleRecording() {
  if (!isConnected) return;

  if (!isRecording) {
    await startRecording();
  } else {
    await stopRecording();
  }
}

async function startRecording() {
  try {
    recordBtn.disabled = true;
    statusMsg.textContent = 'Starting recording...';
    statusMsg.className = 'status-msg processing';

    const deviceId = deviceSelect.value || undefined;
    const data = await apiPost('/start', { device_id: deviceId });

    if (data.success) {
      isRecording = true;
      updateRecordButton();
      startTimerUI();
      statusMsg.textContent = 'Recording... Audio stays on your device';
      statusMsg.className = 'status-msg processing';
    } else {
      statusMsg.textContent = data.error || 'Failed to start recording';
      statusMsg.className = 'status-msg error';
    }

    recordBtn.disabled = false;
  } catch (e) {
    statusMsg.textContent = 'Error: ' + e.message;
    statusMsg.className = 'status-msg error';
    recordBtn.disabled = false;
  }
}

async function stopRecording() {
  try {
    recordBtn.disabled = true;
    statusMsg.textContent = 'Stopping recording...';
    statusMsg.className = 'status-msg processing';

    const data = await apiPost('/stop');

    isRecording = false;
    updateRecordButton();
    stopTimerUI();

    if (data.success) {
      statusMsg.textContent = 'Transcribing locally...';
      statusMsg.className = 'status-msg processing';
      // Poll for transcript/summary results
      pollForResults();
    } else {
      statusMsg.textContent = data.error || 'Failed to stop recording';
      statusMsg.className = 'status-msg error';
    }

    recordBtn.disabled = false;
  } catch (e) {
    statusMsg.textContent = 'Error: ' + e.message;
    statusMsg.className = 'status-msg error';
    recordBtn.disabled = false;
  }
}

function updateRecordButton() {
  if (isRecording) {
    recordBtn.textContent = 'Stop Recording';
    recordBtn.className = 'record-btn recording';
  } else {
    recordBtn.textContent = 'Start Recording';
    recordBtn.className = 'record-btn ready';
  }
}

// --- Timer ---

function startTimerUI() {
  recordingStartTime = Date.now();
}

function stopTimerUI() {
  recordingStartTime = null;
  levelBar.style.width = '0%';
}

function updateTimerDisplay(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  timer.textContent =
    String(h).padStart(2, '0') + ':' +
    String(m).padStart(2, '0') + ':' +
    String(s).padStart(2, '0');
}

// --- Devices ---

async function loadDevices() {
  try {
    const data = await apiGet('/devices');
    deviceSelect.innerHTML = '';

    if (data.devices && data.devices.length > 0) {
      data.devices.forEach(device => {
        const option = document.createElement('option');
        option.value = device.id;
        option.textContent = device.is_loopback
          ? `System Audio (Recommended)`
          : device.name;
        deviceSelect.appendChild(option);
      });
    } else {
      const option = document.createElement('option');
      option.value = '';
      option.textContent = 'No audio devices found';
      deviceSelect.appendChild(option);
    }
  } catch (e) {
    deviceSelect.innerHTML = '<option value="">Could not load devices</option>';
  }
}

// --- Results ---

async function pollForResults() {
  let attempts = 0;
  const maxAttempts = 150; // Poll for up to 5 minutes (long recordings take time)

  const resultPoll = setInterval(async () => {
    attempts++;

    try {
      const status = await apiGet('/status');

      if (status.has_summary) {
        clearInterval(resultPoll);
        statusMsg.textContent = 'Summary ready!';
        statusMsg.className = 'status-msg';
        fetchResults();
        return;
      }

      if (status.has_transcript && !status.has_summary) {
        statusMsg.textContent = 'Generating summary...';
        statusMsg.className = 'status-msg processing';
      } else if (!status.has_transcript && !status.has_summary) {
        const elapsed = Math.round(attempts * 2);
        statusMsg.textContent = `Transcribing locally... (${elapsed}s elapsed)`;
        statusMsg.className = 'status-msg processing';
      }

    } catch (e) {
      // Connection lost during polling
    }

    if (attempts >= maxAttempts) {
      clearInterval(resultPoll);
      statusMsg.textContent = 'No speech detected. Ensure audio is playing and Stereo Mix is enabled in Windows Sound settings.';
      statusMsg.className = 'status-msg error';
    }
  }, 2000);
}

async function fetchResults() {
  try {
    const [transcriptData, summaryData] = await Promise.all([
      apiGet('/transcript'),
      apiGet('/summary')
    ]);

    resultsArea.innerHTML = '';

    // Show summary if available
    if (summaryData.ready) {
      resultsSection.classList.remove('hidden');

      // Executive summary
      if (summaryData.executive_summary) {
        const card = createResultCard('Summary', summaryData.executive_summary);
        resultsArea.appendChild(card);
      }

      // Key discussion points
      if (summaryData.key_discussion_points && summaryData.key_discussion_points.length > 0) {
        const card = createResultCard('Key Points', null, summaryData.key_discussion_points);
        resultsArea.appendChild(card);
      }

      // Action items
      if (summaryData.action_items && summaryData.action_items.length > 0) {
        const card = createResultCard('Action Items', null, summaryData.action_items);
        resultsArea.appendChild(card);
      }

      // Decisions
      if (summaryData.decisions_made && summaryData.decisions_made.length > 0) {
        const card = createResultCard('Decisions', null, summaryData.decisions_made);
        resultsArea.appendChild(card);
      }

      // Next steps
      if (summaryData.next_steps && summaryData.next_steps.length > 0) {
        const card = createResultCard('Next Steps', null, summaryData.next_steps);
        resultsArea.appendChild(card);
      }

      statusMsg.textContent = `Summary ready (${summaryData.model_used || 'local'})`;
      statusMsg.className = 'status-msg';
    }
    // Show transcript preview if no summary yet
    else if (transcriptData.ready) {
      resultsSection.classList.remove('hidden');
      const preview = transcriptData.full_text.substring(0, 500) + '...';
      const card = createResultCard(
        `Transcript (${transcriptData.duration?.toFixed(0) || '?'}s)`,
        preview
      );
      resultsArea.appendChild(card);
      statusMsg.textContent = 'Transcript ready, waiting for summary...';
      statusMsg.className = 'status-msg processing';
    }

  } catch (e) {
    console.error('Failed to fetch results:', e);
  }
}

function createResultCard(title, text, list) {
  const card = document.createElement('div');
  card.className = 'result-card';

  const h3 = document.createElement('h3');
  h3.textContent = title;
  card.appendChild(h3);

  if (text) {
    const p = document.createElement('p');
    p.textContent = text;
    card.appendChild(p);
  }

  if (list && list.length > 0) {
    const ul = document.createElement('ul');
    list.forEach(item => {
      const li = document.createElement('li');
      li.textContent = item;
      ul.appendChild(li);
    });
    card.appendChild(ul);
  }

  return card;
}

// --- Copy ---

async function copySummary() {
  try {
    const data = await apiGet('/summary');
    if (!data.ready) {
      statusMsg.textContent = 'No summary to copy';
      statusMsg.className = 'status-msg error';
      return;
    }

    let text = `# ${data.meeting_title || 'Meeting Summary'}\n\n`;
    text += `## Summary\n${data.executive_summary || ''}\n\n`;

    if (data.key_discussion_points?.length > 0) {
      text += `## Key Points\n`;
      data.key_discussion_points.forEach(p => text += `- ${p}\n`);
      text += '\n';
    }

    if (data.action_items?.length > 0) {
      text += `## Action Items\n`;
      data.action_items.forEach(a => text += `- [ ] ${a}\n`);
      text += '\n';
    }

    if (data.decisions_made?.length > 0) {
      text += `## Decisions\n`;
      data.decisions_made.forEach(d => text += `- ${d}\n`);
      text += '\n';
    }

    if (data.next_steps?.length > 0) {
      text += `## Next Steps\n`;
      data.next_steps.forEach(s => text += `- ${s}\n`);
    }

    await navigator.clipboard.writeText(text);
    statusMsg.textContent = 'Copied to clipboard!';
    statusMsg.className = 'status-msg';

    // Reset message after 2 seconds
    setTimeout(() => {
      statusMsg.textContent = 'Summary ready';
      statusMsg.className = 'status-msg';
    }, 2000);

  } catch (e) {
    statusMsg.textContent = 'Failed to copy';
    statusMsg.className = 'status-msg error';
  }
}

// --- Meeting Detection ---

async function detectMeeting() {
  try {
    const tabs = await chrome.tabs.query({ active: true, currentWindow: true });
    const tab = tabs[0];
    const url = tab?.url || '';

    const meetings = [
      { pattern: 'meet.google.com', name: 'Google Meet' },
      { pattern: 'zoom.us/j/', name: 'Zoom' },
      { pattern: 'zoom.us/wc/', name: 'Zoom' },
      { pattern: 'zoom.com/j/', name: 'Zoom' },
      { pattern: 'zoom.com/wc/', name: 'Zoom' },
      { pattern: 'teams.microsoft.com', name: 'Teams' }
    ];

    for (const m of meetings) {
      if (url.includes(m.pattern)) {
        meetingStatus.textContent = `${m.name} meeting detected`;
        meetingStatus.className = 'meeting-badge meeting-detected';
        // Notify background
        chrome.runtime.sendMessage({ action: 'meetingDetected', platform: m.name });
        return;
      }
    }

    meetingStatus.textContent = 'No meeting detected (record anytime)';
    meetingStatus.className = 'meeting-badge meeting-none';

  } catch (e) {
    meetingStatus.textContent = 'No meeting detected (record anytime)';
    meetingStatus.className = 'meeting-badge meeting-none';
  }
}
