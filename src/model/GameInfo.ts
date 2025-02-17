/**
 * Used to provide context to do_backup
 */
export interface GameInfo {
    game_id: number;
    game_name: string; // The display name for this game (required by python install directory search)
    install_root: string; // where the files are installed.  Normally from SteamClient.InstallFolder.GetInstallFolders()
    save_games_root?: string; // only populated by python, optional when generated in javascript
}
