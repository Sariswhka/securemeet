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

  return true;
});
