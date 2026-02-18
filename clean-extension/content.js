// content.js — SecureMeet Chrome Extension
// Auto-detects meeting pages and notifies the background script

(function() {
  // Prevent duplicate injection
  if (window.__securemeet_loaded) return;
  window.__securemeet_loaded = true;

  const url = window.location.href;

  // Detect meeting platform
  const meetings = [
    { pattern: 'meet.google.com', name: 'Google Meet' },
    { pattern: 'zoom.us/j/', name: 'Zoom' },
    { pattern: 'zoom.us/wc/', name: 'Zoom' },
    { pattern: 'zoom.com/j/', name: 'Zoom' },
    { pattern: 'zoom.com/wc/', name: 'Zoom' },
    { pattern: 'teams.microsoft.com', name: 'Teams' }
  ];

  let detectedPlatform = null;

  for (const m of meetings) {
    if (url.includes(m.pattern)) {
      detectedPlatform = m.name;
      break;
    }
  }

  if (detectedPlatform) {
    console.log(`SecureMeet: ${detectedPlatform} meeting detected on ${url}`);

    // Notify background script that a meeting page is active
    chrome.runtime.sendMessage({
      action: 'meetingDetected',
      platform: detectedPlatform,
      url: url
    }).catch(() => {
      // Background might not be ready yet, that's ok
    });
  }

  // Listen for messages from popup or background
  chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'checkMeeting') {
      sendResponse({
        isMeeting: detectedPlatform !== null,
        platform: detectedPlatform,
        url: url
      });
    }
    return true;
  });
})();
