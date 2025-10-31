# 🎯 Quick Start Guide: State Management Feature

## What's New?

You can now **save and restore** your work! When you zoom into an image and draw annotations, your work is automatically saved. Next time you load the same image, you can choose to restore everything exactly as you left it.

---

## 🖼️ Visual Guide

### 1️⃣ Selection Page - New Options

When you open the application, you'll see:

```
┌─────────────────────────────────────────────┐
│  🔹 Select Here (click any number of images)│
│                                             │
│  ☐ 1161_Panel2_in_idx                      │
│  ☐ 1177_Panel1_in_idx                      │
│  ☐ Another_Image                           │
│                                             │
│  ## Load Options                            │
│  ◉ Load New State     ○ Load Last State    │  ← NEW!
│                                             │
│  [  Load Selected Slices  ]                │
└─────────────────────────────────────────────┘
```

**Two new options**:
- **Load New State** 🆕: Fresh start (default zoom, no drawings)
- **Load Last State** 🔄: Restore your previous session

---

## 📖 Step-by-Step Usage

### Scenario A: First Time Viewing an Image

1. **Select your image**: Click on "1161_Panel2_in_idx"
2. **Choose**: Select **"Load New State"** (default)
3. **Load**: Click "Load Selected Slices"
4. **Work**: 
   - Zoom into interesting regions
   - Draw annotations with the freehand tool
   - Pan around the image
5. **Save**: Click **"⬅️ Back"** button
   - ✅ Your state is automatically saved!
   - Console shows: `✓ Saved state for 1161_Panel2_in_idx`

### Scenario B: Continuing Previous Work

1. **Select same image**: Click on "1161_Panel2_in_idx" again
2. **Choose**: Select **"Load Last State"** ← Important!
3. **Load**: Click "Load Selected Slices"
4. **Restored!** 🎉
   - Your zoom level is restored
   - Your viewport position is the same
   - All your drawings are back!
   - Console shows: `✓ Restored saved state for 1161_Panel2_in_idx`

---

## ⏱️ Auto-Save Feature

Your work is **automatically saved every 2 seconds** when:
- ✅ You zoom in or out
- ✅ You pan to a different area
- ✅ You draw new annotations
- ✅ You modify existing drawings

**You don't need to do anything!** Just work normally and your progress is saved.

---

## 🎨 What Gets Saved?

Every time you save, the system stores:

| Data | Description | Example |
|------|-------------|---------|
| **Viewport** | What part of the image you're viewing | `[x: 6594, y: 12742, w: 20075, h: 7705]` |
| **Zoom Level** | How zoomed in you are | `150.5%` |
| **Drawings** | All your freehand annotations | Multiple stroke paths |
| **Timestamp** | When it was saved | `2025-10-29 15:45:42` |

---

## 💡 Use Cases

### Use Case 1: Long Analysis Session
```
Day 1: Find interesting region → Draw annotations → Click Back
       ✓ State saved automatically

Day 2: Select same image → Choose "Load Last State"
       ✓ Continue exactly where you left off!
```

### Use Case 2: Comparing Fresh vs. Annotated Views
```
Session A: Load New State → Fresh clean view
Session B: Load Last State → View with your annotations
```

### Use Case 3: Multiple Images
```
Image A: Work → Save → Back
Image B: Work → Save → Back
Image C: Work → Save → Back

Later: Load any image with "Load Last State"
       → Each image restores independently!
```

---

## 🔔 Console Messages

Watch for these helpful messages in the browser console:

### ✅ Success Messages:
```
✓ Auto-save enabled for 1161_Panel2_in_idx
✓ Restored saved state for 1161_Panel2_in_idx
✓ Saved state for 1161_Panel2_in_idx
```

### ℹ️ Info Messages:
```
ℹ No saved state found for 1161_Panel2_in_idx
  (This is normal for images you haven't worked with yet)
```

### ⚠️ Warning Messages:
```
⚠ Failed to restore state for 1161_Panel2_in_idx
  (Check console for details)
```

---

## 📁 Where Are States Stored?

States are saved as JSON files in:
```
app_magicscan/state_logs/
├── 1161_Panel2_in_idx_state.json
├── 1177_Panel1_in_idx_state.json
└── Another_Image_state.json
```

Each image has its own state file!

---

## 🛠️ Advanced: Viewing Your State File

Want to see what's saved? Run:

```bash
# In Docker container:
docker exec syncview_1177_p11-syncview-1 \
  cat /usr/local/lib/python3.10/site-packages/openvisuspy/app_magicscan/state_logs/1161_Panel2_in_idx_state.json
```

Example output:
```json
{
  "viewport": [6594.867, 12742.889, 20075.802, 7705.734],
  "zoom_level": 150.5,
  "drawings": {
    "xs": [[100, 120, 140, 160], [200, 220]],
    "ys": [[150, 155, 160, 165], [250, 255]]
  },
  "timestamp": 1761753042.826,
  "image_path": "/home/.../1161_Panel2_in_idx/visus.idx"
}
```

---

## ❓ FAQ

### Q: Do I need to manually save?
**A:** No! Auto-save runs every 2 seconds. Just click "Back" when you're done.

### Q: What if I want a fresh start on an image I've worked on?
**A:** Just select "Load New State" instead of "Load Last State"!

### Q: Can I have multiple saved states for one image?
**A:** Currently, only the most recent state is kept per image.

### Q: What happens if I close the browser without clicking "Back"?
**A:** Your last auto-save (within 2 seconds) is preserved. But clicking "Back" ensures everything is saved!

### Q: Do drawings from other tools get saved?
**A:** Currently, only freehand drawings (green tool) are saved.

### Q: Can I delete a saved state?
**A:** Yes, manually delete the file from `state_logs/` or use the container:
```bash
docker exec syncview_1177_p11-syncview-1 \
  rm /usr/local/.../state_logs/IMAGE_NAME_state.json
```

### Q: How big are state files?
**A:** Usually very small (< 10 KB) unless you have hundreds of drawing strokes.

### Q: Does this work with multiple images at once?
**A:** Yes! Each image tracks and restores its state independently.

---

## 🚨 Troubleshooting

### Problem: State not saving
**Check**:
1. Do you see "✓ Auto-save enabled" in console?
2. Is the `state_logs/` directory writable?
3. Any error messages in console?

### Problem: State not restoring
**Check**:
1. Did you select "Load Last State"?
2. Does the state file exist in `state_logs/`?
3. Do you see "✓ Restored saved state" message?

### Problem: Drawings missing after restore
**Check**:
1. Were drawings made with the freehand tool (green)?
2. Did you click "Back" to force final save?
3. Check state file for `"xs"` and `"ys"` arrays with data

---

## 🎓 Pro Tips

1. **Always click "Back"** before closing your browser to ensure the final save
2. **Use descriptive workflows**: "Load New State" for fresh analysis, "Load Last State" to continue
3. **Check console messages** to confirm your saves are working
4. **State files are text (JSON)** so you can inspect or backup manually
5. **Each image is independent** - no conflicts between different images

---

## 🎉 Benefits

✅ **No more losing work** - Everything is saved automatically  
✅ **Resume anytime** - Pick up exactly where you left off  
✅ **Multiple sessions** - Work on different images independently  
✅ **Peace of mind** - Auto-save every 2 seconds  
✅ **Flexible** - Choose new state or last state each time  

---

## 📞 Need Help?

1. Check console for error messages (F12 → Console)
2. View logs: `docker logs syncview_1177_p11-syncview-1`
3. Run tests: `./test_state_management.sh`
4. Read full docs: `STATE_MANAGEMENT_README.md`

---

**Happy annotating! Your work is now safe and restorable! 🎉**
