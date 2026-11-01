// The only bridge into the page: open the data folder or the logs folder. No arguments cross it,
// and it is exposed on the game page only (the /toolkit popup never gets it).
import { contextBridge, ipcRenderer } from 'electron'

if (location.pathname.startsWith('/play/')) {
  contextBridge.exposeInMainWorld('neqDesktop', {
    openDataFolder: () => ipcRenderer.invoke('neq:open-data-folder'),
    openLogs: () => ipcRenderer.invoke('neq:open-logs'),
  })
}
