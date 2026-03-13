const socialMediaDomains = [
  "facebook.com",
  "twitter.com",
  "x.com",
  "instagram.com",
  "linkedin.com",
  "tiktok.com",
  "reddit.com",
  "snapchat.com",
  "pinterest.com",
  "youtube.com",
  "twitch.tv",
];

async function sendPostRequest() {
  try {
    await fetch("http://localhost:8000/image/teeth", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
    });
  } catch (error) {
    console.error("Failed to send POST request:", error);
  }
}

function isSocialMediaUrl(url) {
  if (!url) return false;
  try {
    const hostname = new URL(url).hostname.toLowerCase();
    return socialMediaDomains.some((domain) => hostname.includes(domain));
  } catch {
    return false;
  }
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab.url) {
    if (isSocialMediaUrl(tab.url)) {
      sendPostRequest();
    }
  }
});

chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    if (tab.url && isSocialMediaUrl(tab.url)) {
      sendPostRequest();
    }
  } catch (error) {
    console.error("Failed to get tab info:", error);
  }
});
