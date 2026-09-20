# Aurum Browser

A compact desktop browser built with Python, PySide6, and Qt WebEngine.

Aurum keeps the browser chrome deliberately small: the sidebar is local HTML/CSS/JavaScript, while Chromium handles web content, networking, JavaScript, WebGL, storage, and media.

## What It Includes

- Tabbed browsing with reorder, close, back, forward, reload, and keyboard shortcuts
- Search or direct URL navigation
- Local HTML/CSS/JavaScript sidebar connected through Qt WebChannel
- Persistent browsing profile with disk cache
- Guest mode with an off-the-record profile and memory cache
- WebGL and accelerated 2D canvas support
- Back/forward cache enabled for faster history navigation
- Microphone and camera permission prompts
- Favicon display beside tab names
- Downloads through a native save dialog
- Bundled local fonts and application icon

## Stack

- Python 3.10+
- PySide6 6.6+
- Qt WebEngine / Chromium
- PyInstaller for Windows packaging
- `uv` for environment and dependency management

## Project Layout

```text
browser/
  backend/
    bridge.py       Qt WebChannel API exposed to the sidebar
    engine.py       Profiles, tabs, navigation, permissions, downloads
    main.py         Application window and sidebar WebEngine view
  frontend/
    index.html      Sidebar UI
    home.html       New-tab page
    settings.html   Browser settings
  fonts/            Local Inter and Allura font files

AurumBrowser.spec  PyInstaller build definition
pyproject.toml     Project metadata and dependencies
uv.lock            Locked Python dependencies
```

## Run From Source

Install dependencies with `uv`:

```powershell
uv sync
```

Start the browser:

```powershell
uv run python browser/backend/main.py
```

The application expects to be started from the repository root. The source entry point resolves the frontend and logo from the project tree.

## Build the Windows Application

Build the distributable directory with:

```powershell
uv run pyinstaller --noconsole --noconfirm `
  --name "AurumBrowser" `
  --icon="logo.png" `
  --add-data "browser/frontend;frontend" `
  --add-data "browser/fonts;fonts" `
  --add-data "logo.png;." `
  browser/backend/main.py
```

The result is written to:

```text
dist/AurumBrowser/
```

Run:

```text
dist/AurumBrowser/AurumBrowser.exe
```

The `browser/fonts` data entry matters: the internal pages reference the bundled font files at runtime.

## Browser Profiles

Normal tabs use a named `AurumBrowser` profile. Cookies, local storage, permissions, and the disk HTTP cache belong to that profile.

Guest mode uses an off-the-record profile. Its cookies and cache are held in memory and are discarded when the guest profile is destroyed.

## Permissions

When a page requests microphone or camera access, Qt WebEngine emits a permission request. Aurum shows a native confirmation dialog containing the requesting origin. Choosing **Yes** grants the requested media permission; choosing **No** denies it.

Media permissions are intentionally handled by the application rather than silently granted to every page.

## Sidebar Communication

The sidebar is a local WebEngine page. `BrowserBridge` exposes the browser actions and signals through `QWebChannel`:

- navigation and tab actions are sent from JavaScript to Python
- tab state is sent to JavaScript as JSON
- title, URL, and favicon changes are emitted as focused signals

Favicons are converted to small PNG data URLs in the backend before being sent to the sidebar, so the sidebar does not need to fetch them separately.

## Keyboard Shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl+L` | Focus the address field |
| `Ctrl+T` | Open a new tab |
| `Ctrl+W` | Close the active tab |
| `Ctrl+B` | Toggle the sidebar |
| `Alt+Left` | Go back |
| `Alt+Right` | Go forward |
| `F5` | Reload the active tab |


## License

MIT License. See [LICENSE](LICENSE) for details.
