# Keyboard Shortcuts - Testing Guide

## ✅ Implementation Complete

Keyboard shortcuts have been added to your application. The shortcuts will be activated when you load images for viewing.

## 🎹 Available Keyboard Shortcuts

| Shortcut | Action | Button Triggered | Description |
|----------|--------|------------------|-------------|
| **Shift+S** | 💾 Save State | Save State | Manually save the current viewport and drawings |
| **Ctrl+Z** | ↩️ Undo | Undo | Navigate backward through live tracking auto-saves |
| **Ctrl+Y** | ↪️ Redo | Redo | Navigate forward through live tracking auto-saves |
| **Alt+Left** | ⬅️ Load Prev | Load Prev | Load the previous manually saved state |
| **Alt+Right** | ➡️ Load Next | Load Next | Load the next manually saved state |
| **[** | ⬅️ Load Prev | Load Prev | Alternative key for Load Prev |
| **]** | ➡️ Load Next | Load Next | Alternative key for Load Next |

## 🧪 How to Test

1. **Open the Application**
   - Navigate to: http://localhost:11110/app_magicscan
   - Or use your server's IP with port 11110

2. **Load an Image**
   - Select an image from the file list
   - Click "Load" to view it

3. **Open Browser Console** (to see keyboard shortcut logs)
   - Press **F12** on your keyboard
   - Click on the "Console" tab
   - You should see: `🎹 Keyboard shortcuts registered!`

4. **Test Each Shortcut**

   **a) Test Save State (Shift+S)**
   - Move or zoom the image
   - Press **Shift+S**
   - Console should log: `Keyboard shortcut detected: s Ctrl: false Shift: true Alt: false`
   - Console should log: `Triggering Save State button`
   - State should be saved

   **b) Test Undo/Redo (Ctrl+Z / Ctrl+Y)**
   - Wait a few seconds for live tracking to create auto-saves
   - Press **Ctrl+Z** (Undo) - should go back to previous viewport
   - Press **Ctrl+Y** (Redo) - should go forward to next viewport
   - Each press logs to console

   **c) Test Load Prev/Next (Alt+Arrow or [ ])**
   - Press **Shift+S** a few times after moving the image to create saved states
   - Press **Alt+Left Arrow** or **[** - loads previous saved state
   - Press **Alt+Right Arrow** or **]** - loads next saved state
   - Each press logs to console

5. **Verify in Console**
   - Each keyboard shortcut press should show logs in the browser console
   - Example logs:
     ```
     Keyboard shortcut detected: s Ctrl: false Shift: true Alt: false
     Triggering Save State button
     ```

## 🐛 Troubleshooting

**Shortcuts not working?**
1. Make sure you've loaded an image (shortcuts only work when viewing images)
2. Check browser console (F12) for JavaScript errors
3. Ensure browser focus is on the application window
4. Try clicking on the image viewer area first

**Console not showing logs?**
1. Open browser Developer Tools (F12)
2. Look in the "Console" tab
3. Check for the initial message: `🎹 Keyboard shortcuts registered!`

**Some shortcuts conflict with browser?**
- **Ctrl+S** (browser save) - That's why we use **Shift+S** instead
- **Ctrl+Z/Y** might trigger browser undo/redo - the JavaScript prevents this
- If issues persist, use the alternative keys **[** and **]**

## 📍 Code Location

The keyboard shortcuts are implemented in:
- **File**: `/home/sampad/home/save_current_state/magicvisuspy_dashboard/openvisuspy/app_magicscan/main.py`
- **Method**: `_setup_keyboard_shortcuts()` (lines ~1269-1354)
- **Called from**: `load_slices()` method (line ~753)

## 🔧 Customization

To modify shortcuts, edit the `_setup_keyboard_shortcuts()` method:
- Change key combinations in the JavaScript code
- Add new shortcuts by following the existing pattern
- Restart Docker container after changes: `docker-compose restart`

## ✨ Features

- ✅ Shortcuts work globally when viewing images
- ✅ Prevents browser default actions for these key combinations
- ✅ Console logs show which shortcut was triggered
- ✅ Simulates actual button clicks (same behavior as clicking with mouse)
- ✅ Alternative keys provided for easier access ([ and ])
- ✅ No additional dependencies required

---

**Need Help?** Check the browser console for error messages or confirmation logs.
