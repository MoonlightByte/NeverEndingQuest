import { app, dialog, Menu, shell, type MenuItemConstructorOptions } from 'electron'

const REPO = 'https://github.com/MoonlightByte/NeverEndingQuest'

export interface MenuActions {
  dataDir: string
  logsDir: string
  serverVersion(): string
  quit(): void
  forceQuit(): void
  closing(): boolean
}

export function buildMenu(a: MenuActions): Menu {
  const template: MenuItemConstructorOptions[] = [
    {
      label: 'Game',
      submenu: [
        { label: 'Open data folder', click: () => void shell.openPath(a.dataDir) },
        { label: 'Open logs', click: () => void shell.openPath(a.logsDir) },
        { type: 'separator' },
        { label: 'Force quit', click: () => void confirmForceQuit(a) },
        { label: 'Quit', accelerator: 'CmdOrCtrl+Q', click: () => a.quit() },
      ],
    },
    { role: 'editMenu' },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
        ...(app.isPackaged ? [] : [{ role: 'toggleDevTools' } as MenuItemConstructorOptions]),
      ],
    },
    {
      label: 'Help',
      submenu: [
        { label: 'README', click: () => void shell.openExternal(`${REPO}#readme`) },
        { label: 'Report a problem', click: () => void shell.openExternal(`${REPO}/issues/new`) },
        { type: 'separator' },
        {
          label: 'About NeverEndingQuest',
          click: () => void dialog.showMessageBox({
            type: 'info',
            title: 'About NeverEndingQuest',
            message: 'NeverEndingQuest',
            detail: `App ${app.getVersion()}\nGame server ${a.serverVersion() || 'not started yet'}`,
          }),
        },
      ],
    },
  ]
  return Menu.buildFromTemplate(template)
}

async function confirmForceQuit(a: MenuActions): Promise<void> {
  const detail = a.closing()
    ? 'The game is still saving. Force quit stops it now; anything not yet saved is lost.'
    : 'Force quit stops the game server now without saving. Use Quit to save and close.'
  const { response } = await dialog.showMessageBox({
    type: 'warning',
    title: 'Force quit',
    message: 'Stop the game now?',
    detail,
    buttons: ['Keep waiting', 'Force quit'],
    defaultId: 0,
    cancelId: 0,
  })
  if (response === 1) a.forceQuit()
}
