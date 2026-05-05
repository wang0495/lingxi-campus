const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('__LINGXI_CONFIG__', {
  apiBase: 'http://129.204.195.175:8002'
});
