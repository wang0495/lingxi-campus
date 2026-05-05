const { app, BrowserWindow, shell, session } = require('electron');
const path = require('path');
const http = require('http');
const fs = require('fs');

// 打包后 frontend 在 asar 根目录，开发时在 ../frontend
const FRONTEND_DIR = app.isPackaged
  ? path.join(__dirname)
  : path.join(__dirname, '..', 'frontend');
const MIME = {
  '.html': 'text/html', '.css': 'text/css', '.js': 'application/javascript',
  '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml', '.ico': 'image/x-icon', '.woff2': 'font/woff2',
};

let server;
const EMBED_PORT = 19876;

function startLocalServer() {
  return new Promise((resolve) => {
    server = http.createServer((req, res) => {
      let url = req.url.split('?')[0];
      if (url === '/') url = '/index.html';
      const filePath = path.join(FRONTEND_DIR, url);
      const ext = path.extname(filePath);
      fs.readFile(filePath, (err, data) => {
        if (err) { res.writeHead(404); res.end('Not found'); return; }
        res.writeHead(200, { 'Content-Type': MIME[ext] || 'application/octet-stream' });
        res.end(data);
      });
    });
    server.listen(EMBED_PORT, '127.0.0.1', () => resolve());
  });
}

function createWindow() {
  // 自动批准麦克风/摄像头权限
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

  // 通过 localhost HTTP 加载（getUserMedia 需要安全上下文）
  win.loadURL(`http://127.0.0.1:${EMBED_PORT}/`);

  win.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith('http://') || url.startsWith('https://')) {
      shell.openExternal(url);
    }
    return { action: 'deny' };
  });

  win.setMenuBarVisibility(false);
}

app.whenReady().then(async () => {
  await startLocalServer();
  createWindow();
});

app.on('window-all-closed', () => {
  if (server) server.close();
  app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
