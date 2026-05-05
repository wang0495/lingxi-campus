const { app, BrowserWindow, shell, session } = require('electron');
const path = require('path');

function createWindow() {
  // 自动批准麦克风权限，消除系统确认弹窗
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    if (permission === 'media') {
      callback(true);
    } else {
      callback(false);
    }
  });

  const win = new BrowserWindow({
    width: 1200,
    height: 800,
    minWidth: 800,
    minHeight: 600,
    title: '灵犀·校园',
    icon: path.join(__dirname, 'assets', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // 白屏诊断：错误监听
  win.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
    console.error('[Electron] Page load failed:', errorCode, errorDescription);
  });
  win.webContents.on('console-message', (event, level, message) => {
    if (level >= 2) console.error('[Electron] Renderer error:', message);
  });
  win.webContents.on('crashed', () => {
    console.error('[Electron] Renderer process crashed');
  });

  win.loadFile(path.join(__dirname, '..', 'frontend', 'index.html'));

  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://') || url.startsWith('https://')) {
      shell.openExternal(url);
    }
    return { action: 'deny' };
  });

  win.setMenuBarVisibility(false);
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
