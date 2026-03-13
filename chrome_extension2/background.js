const DISTRACTING_SITES = [
  "tiktok.com",
  "instagram.com",
  "twitter.com",
  "x.com",
  "facebook.com",
  "reddit.com",
  "youtube.com",
  "twitch.tv",
  "netflix.com",
  "9gag.com"
];

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status !== "complete" || !tab.url) return;
  try {
    const url = new URL(tab.url);
    const isDistracting = DISTRACTING_SITES.some(site => url.hostname.includes(site));
    if (isDistracting) {
      chrome.tabs.sendMessage(tabId, { action: "showMascot", site: url.hostname });
    }
  } catch (e) {}
});
