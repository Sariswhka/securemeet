// background.js — SecureMeet Chrome Extension
// Monitors tabs for meeting URLs and updates the extension badge

const MEETING_PATTERNS = [
  { regex: /meet\.google\.com/, name: 'Meet' },
  { regex: /zoom\.(us|com)\/(j|wc)\//, name: 'Zoom' },
  { regex: /teams\.microsoft\.com.*meeting/, name: 'Teams' }
];

// Track active meeting tabs
let activeMeetingTabId = null;

chrome.runtime.onInstalled.addListener(() => {
  console.log('SecureMeet: Extension installed');
  chrome.storage.local.set({ meetings: [] });
  // Clear any existing badge
  chrome.action.setBadgeText({ text: '' });
});

// Listen for tab updates to detect meetings
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status !== 'complete' || !tab.url) return;

  const isMeeting = MEETING_PATTERNS.some(p => p.regex.test(tab.url));

  if (isMeeting) {
    activeMeetingTabId = tabId;
    chrome.action.setBadgeText({ text: 'REC' });
    chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
  } else if (tabId === activeMeetingTabId) {
    // Meeting tab navigated away
    activeMeetingTabId = null;
    chrome.action.setBadgeText({ text: '' });
  }
});

// Listen for tab closures
chrome.tabs.onRemoved.addListener((tabId) => {
  if (tabId === activeMeetingTabId) {
    activeMeetingTabId = null;
    chrome.action.setBadgeText({ text: '' });
  }
});

// Listen for messages from content script or popup
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.action === 'meetingDetected') {
    activeMeetingTabId = sender.tab?.id || null;
    chrome.action.setBadgeText({ text: 'REC' });
    chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
    sendResponse({ success: true });
  }

  if (request.action === 'getActiveMeeting') {
    sendResponse({
      hasMeeting: activeMeetingTabId !== null,
      tabId: activeMeetingTabId
    });
  }

  // Popup tells us to start watching for results (called after Stop Recording)
  if (request.action === 'startResultPolling') {
    chrome.storage.local.set({ summaryReady: false, polling: true });
    // Set badge to show processing
    chrome.action.setBadgeText({ text: '...' });
    chrome.action.setBadgeBackgroundColor({ color: '#FF9800' });
    // Create a repeating alarm every 0.5 minutes (30s) to check for results
    chrome.alarms.create('pollResults', { periodInMinutes: 0.5 });
    sendResponse({ success: true });
  }

  return true;
});

// Handle alarm — check if transcription/summary is ready
chrome.alarms.onAlarm.addListener(async (alarm) => {
  if (alarm.name !== 'pollResults') return;

  try {
    const response = await fetch('http://127.0.0.1:8765/status');
    const data = await response.json();

    if (data.has_summary) {
      // Clear the alarm — we're done
      chrome.alarms.clear('pollResults');
      chrome.storage.local.set({ summaryReady: true, polling: false });

      // Update badge to green checkmark
      chrome.action.setBadgeText({ text: 'NEW' });
      chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });

      // Show Chrome notification
      chrome.notifications.create('summaryReady', {
        type: 'basic',
        iconUrl: 'icon48.png',
        title: 'SecureMeet — Summary Ready',
        message: 'Your meeting summary is ready. Click the SecureMeet icon to view it.'
      });
    }
  } catch (e) {
    // Desktop app not reachable — stop polling
    chrome.alarms.clear('pollResults');
    chrome.storage.local.set({ polling: false });
    chrome.action.setBadgeText({ text: '' });
  }
});
