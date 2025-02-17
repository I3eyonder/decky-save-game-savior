import { GameInfo } from "./GameInfo";

/**
 * A result object from do_backup or get_saveinfos
 */

export interface SaveInfo {
    game_info: GameInfo;
    timestamp: number;
    filename: string;
    is_undo: boolean;
}
