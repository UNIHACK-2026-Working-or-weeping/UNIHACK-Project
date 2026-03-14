# Firefox Extension

This is the Firefox version of the Social Media Tracker extension, ported from Chrome using a cross-browser API abstraction layer.

## Key Differences from Chrome Version

1. **Manifest Version**: Uses Manifest V2 (Firefox support for V3 is limited)
2. **API Wrapper**: Uses `browser-api.js` for cross-browser compatibility
3. **Context Menus**: Firefox uses `browser.menus` API vs Chrome's `chrome.contextMenus`

## Installation

### Temporary Installation (Development)
1. Open Firefox and navigate to `about:debugging`
2. Click "This Firefox" in the sidebar
3. Click "Load Temporary Add-on"
4. Select `firefox_extension/manifest.json`
5. Extension will be loaded and available until Firefox restarts

### Permanent Installation
To permanently install, you'll need to package the extension:
1. Create a ZIP file of the `firefox_extension` directory
2. Open `about:addons` in Firefox
3. Click the gear icon → "Install Add-on From File"
4. Select the ZIP file
