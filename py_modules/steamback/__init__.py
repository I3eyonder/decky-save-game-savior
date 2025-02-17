#!python3

from typing import NamedTuple
import re
import json
import time
import os
import shutil
import logging
import traceback
import glob
from pathlib import Path


logger = None

"""Try to parse a valve vdf file.  Returning all key/value pairs it finds as string pairs.
If no matching keys are found or we fail reading the file, an empty dict will be returned
Note: this doesn't preserve hierarchy - only keys are checked
"""


def _parse_vcf(path: str) -> dict:
    kvMatch = re.compile('\s*"(.+)"\s+"(.+)"\s*')
    d = {}
    try:
        with open(path) as f:
            for line in f:
                # ignore leading/trailing space.  Now ideal like looks like "key"   "value"
                m = kvMatch.fullmatch(line)
                if m:
                    d[m.group(1)] = m.group(2)
    except FileNotFoundError:
        logger.warning(f'App for { path } is not currently mounted, skipping')
    except Exception:
        logger.error(
            f'Failed parsing vcf { path } due to exception { traceback.format_exc() }')
    return d


def _parse_libs(path: str) -> list[str]:
    kvMatch = re.compile('\s*"path"\s+"(.+)"\s*')
    d = []
    with open(path) as f:
        for line in f:
            # ignore leading/trailing space.  Now ideal like looks like "key"   "value"
            m = kvMatch.fullmatch(line)
            if m:
                d.append(m.group(1))
    return d


class Config(NamedTuple):
    logger: logging.Logger
    app_data_dir: str  # where app specific data files are stored
    steam_dir: str  # the root of the Steam data files


class Engine:
    def __init__(self, config: Config):
        global logger
        logger = config.logger
        # logger.setLevel(logging.INFO) # can be changed to logging.DEBUG for debugging issues
        # can be changed to logging.DEBUG for debugging issues

        self.config = config
        # try:
        #    os.environ["DECKY_PLUGIN_RUNTIME_DIR"]
        #    logger.info('Running under decky')
        # except:

        logger.info(f'Decky Save Game Savior engine created: { config }')

        # a dict from gameid -> gameinfo for all installed games.  ONLY USED ON DESKTOP not DECKY
        self.all_games = None
        self.account_ids: set[int] = set()
        self.dry_run = False  # Set to true to suppress 'real' writes to directories
        self.max_saves = 50  # default to a max of ten saves

        # don't generate backups if the files haven't changed since last backup
        self.ignore_unchanged = True
        self.last_used_save_info = None

    def add_account_id(self, id_num: int):
        logger.debug(f'Setting account id { id_num } on { self }')
        self.account_ids.add(id_num)

    """Find the steam account ID for the current user (and)

    We look for a directory in userdata/accountname.  If there are multiple account names we currently throw an exception
    eventually we could look at the config file in each of those dirs to see which one was touched most recently.
    """

    def auto_set_account_id(self) -> list[int]:
        files = os.listdir(os.path.join(self.get_steam_root(), "userdata"))
        ids = list(filter(lambda i: i is not None, map(
            lambda f: int(f) if f.isnumeric() and f != "0" else None, files)))
        for id in ids:
            self.add_account_id(id)
        return ids

    """
    Return the saves directory path (creating it if necessary)
    """

    def _get_savesdir(self) -> str:
        # we now use a new directory for saves (because metaformat changed) - original version was never released
        p = os.path.join(self.config.app_data_dir, "saves2")
        if not os.path.exists(p):
            os.makedirs(p)
        # logger.debug(f'Using saves directory { p }')
        return p

    """
    Return the steam root directory
    """

    def get_steam_root(self) -> str:
        return self.config.steam_dir

    """
    Return the path to the game directory for a specified game
    """

    def _get_gamedir(self, game_id: int) -> list[str]:
        assert len(self.account_ids) > 0  # better be set by now
        return [
            os.path.join(
                self.get_steam_root(), "userdata", str(account_id), str(game_id)
            )
            for account_id in self.account_ids
        ]

    """return true if the game is installed on external storage
    """

    def _is_on_mmc(self, game_info: dict) -> bool:
        assert game_info["install_root"]
        return game_info["install_root"].startswith("/run")

    """read installdir from appmanifest_gameid.vdf and return it

    is_system_dir is True if instead of the game install loc you'd like us to search the system steam data
    """

    def _get_steamapps_dir(self, game_info: dict, is_system_dir: bool = False) -> str:
        assert game_info["install_root"]
        d = game_info["install_root"] if not is_system_dir else self.get_steam_root()
        steamApps = os.path.join(d, "steamapps")
        return steamApps

    """read installdir from appmanifest_gameid.vdf and return it (or None if not found)
    """

    def _parse_installdir(self, game_info: dict) -> str:
        app_dir = self._get_steamapps_dir(game_info)
        vcf = _parse_vcf(os.path.join(
            app_dir, f'appmanifest_{ game_info["game_id"] }.acf'))
        install_dir = vcf.get("installdir", None)
        return install_dir

    """get all library path based on libraryfolders.vdf file
    """

    def _get_all_library(self) -> list[str]:
        steam_dir = self.get_steam_root()
        app_dir = os.path.join(steam_dir, "steamapps")
        return _parse_libs(os.path.join(app_dir, "libraryfolders.vdf"))

    """Return all games that can be found on this system (only used for python apps - when in Decky this comes from JS)
    """

    def find_all_game_info(self) -> list[dict]:
        r = []
        rdict = {}  # a dict from game id int to the gameinfo object
        for steam_dir in self._get_all_library():
            app_dir = os.path.join(steam_dir, "steamapps")
            files = []  # default to assume no files
            try:
                files = filter(lambda f: f.startswith("appmanifest_")
                               and f.endswith(".acf"), os.listdir(app_dir))
            except Exception as e:
                logger.warning(
                    f'Skipping invalid library directory { app_dir } due to { e }')

            for f in files:
                vcf = _parse_vcf(os.path.join(app_dir, f))
                id = vcf.get("appid", None)
                name = vcf.get("name", None)
                if id and name:
                    id = int(id)
                    info = {
                        # On a real steamdeck there may be multiple install_roots (main vs sdcard etc) (but only one per game)
                        "install_root": steam_dir,
                        "game_id": id,
                        "game_name": name,
                    }
                    r.append(info)
                    rdict[id] = info

        self.all_games = rdict
        return r

    """
    Find the root directory for where savegames might be found for either windows or linux

    is_system_dir is True if instead of the game install loc you'd like us to search the system steam data
    """

    def _get_game_saves_root(self, game_info: dict, is_linux_game: bool, is_system_dir: bool = False) -> str:
        steamApps = self._get_steamapps_dir(game_info, is_system_dir)

        if is_linux_game:
            installdir = self._parse_installdir(game_info)
            # FIXME 2/2024 valve seems to have moved the saves on desktop linux to $HOME/.local/share.  Also they are now
            # munging the name of that directory to change spaces to underscore.  NOTE: This change is not used on steamdeck.
            # See Baba Is You for an example of this bug.
            rootdir = os.path.join(steamApps, "common", installdir)
        else:
            rootdir = os.path.join(
                steamApps, 'compatdata', str(game_info["game_id"]), 'pfx', 'drive_c', 'users', 'steamuser')

        return rootdir

    """
    Find all directories that contain steam_autocloud.vdf files or None
    """

    def _find_autoclouds(self, game_info: dict, is_linux_game: bool) -> list[str]:
        root_dir = self._get_game_saves_root(game_info, is_linux_game)

        p = Path(root_dir)
        files = p.rglob("steam_autocloud.vdf")
        # we want the directories that contained the autocloud
        dirs = list(map(lambda f: str(f.parent), files))

        logger.debug(f'Autoclouds in { root_dir } are { dirs }')
        return dirs

    """
    Try to figure out where this game stores its save files. return that path or None
    """

    def _find_save_root_from_autoclouds(self, game_info, rcf, autocloud: str) -> str:

        if len(rcf) < 1:
            return None     # No backup files in the rcf, we can't even do the scan

        # Find any common prefix (which is a directory path) that is shared by all entries in the rcf filenames
        prevR = rcf[0]
        firstDifference = len(prevR)
        for r in rcf:
            # find index of first differing char (or None if no differences)
            index = next(
                (i for i in range(min(len(prevR), len(r))) if prevR[i] != r[i]), None)

            if index is not None and firstDifference > index:
                firstDifference = index

            prevR = r

        # common prefix for all files in rdf (could be empty if files were all backed up from autocloud dir)
        rPrefix = prevR[:firstDifference]

        # at this point rPrefix is _probably_ a directory like "SNAppData/SavedGames/" but it also could be
        # "SNAppData/SavedGames/commonPrefix" (in the case where all the backup files started with commonPrefix)
        # therefore scan backwards from end of string to find first / and then we KNOW everything left of that
        # is a directory.  If we don't find such a slash, that means none of the backup files are using directories
        # and we should just use the existing autocloud dir.
        # FIXME what about paths where someone used / in the filename!
        # NOTE: This has been confirmed to also work on Windows - on that platform also Valve uses / as the path
        # separator.
        dirSplit = rPrefix.rfind('/')
        if dirSplit != -1:
            # throw away everything after the last slash (and the slash itself)
            rPrefix = rPrefix[:dirSplit]

            # check the last n characters of autocloud and if they match our prefix, strip them to find the new root
            autoTail = autocloud[-len(rPrefix):]
            if autoTail == rPrefix:
                autocloud = autocloud[:-len(rPrefix)]

        # possibly convert / to \ if necessary for windows
        return os.path.normpath(autocloud)

    """
    Look in the likely locations for savegame files (per the rcf list). return a (possibly empty) list of paths
    """

    def _search_likely_locations(self, game_info: dict, rcf: list[str]) -> list[str]:
        roots = []

        def addRoots(is_system_dir: bool):
            # try relative to the linux root
            roots.append(self._get_game_saves_root(
                game_info, is_linux_game=True, is_system_dir=is_system_dir))

            # try relative to Documents or application data on windows
            r = self._get_game_saves_root(
                game_info, is_linux_game=False, is_system_dir=is_system_dir)
            windowsRoots = ['Documents',
                            'Application Data', os.path.join('AppData', 'LocalLow'), os.path.join('Local Settings', 'Application Data')]
            for subdir in windowsRoots:
                d = os.path.join(r, subdir)
                roots.append(d)

        # look in the system directory first (if we might also have savegames on the mmc)
        if (self._is_on_mmc(game_info)):
            addRoots(True)

        addRoots(False)

        logger.debug(f'Searching roots { roots }')
        foundDirs = []
        for r in roots:
            if self._rcf_is_valid(r, rcf):
                foundDirs.append(r)

        return foundDirs

    """
    Try to figure out where this game stores its save files. return a (possibly empty) list of candidate directories we found
    """

    def _find_save_games(self, game_info, rcf: list[str]) -> list[str]:
        dirs = self._get_gamedir(game_info["game_id"])

        foundDirs = []
        for d in dirs:
            # First check to see if the game uses the 'new' "remote" directory approach to save files (i.e. they used the steam backup API from the app)
            fullRemotes = (
                os.path.join(d, x)
                for x in ["remote", os.path.join("ac", "LinuxXdgDataHome")]
            )
            remotesFound = (x for x in fullRemotes if os.path.isdir(x))

            # Store the savegames directory for this game
            foundDirs.extend(remotesFound)

        # finding saves only work if we have already found the installdir for this game...
        if not self._parse_installdir(game_info):
            logger.error(f"Invalid game_info, not installdir { game_info }")
            return foundDirs

        # okay - now check the standard doc roots for games - do this before looking for autoclouds because it is more often the match
        likely = self._search_likely_locations(game_info, rcf)
        foundDirs.extend(likely)

        # Alas, now we need to scan the install dir to look for steam_autocloud.vdf files.  If found that means the dev is doing the 'lazy'
        # way of just saying "backup all files due to some path we enter in our web admin console".

        # FIXME, cache this expensive result
        autoclouds = self._find_autoclouds(game_info, is_linux_game=True)

        # Not found on linux, try looking in windows
        if len(autoclouds) < 1:
            autoclouds = self._find_autoclouds(game_info, is_linux_game=False)

        # Convert the autocloud file locations to the correct file root location for backup/restore (based on paths mentioned in the rcf file)
        # FIXME, I don't know the python equivalent of flatmap.
        autoRoots = []
        for f in autoclouds:
            r = self._find_save_root_from_autoclouds(game_info, rcf, f)
            if r:
                logger.debug(
                    f"Mapping autocloud { f } to { r } root directory")
                autoRoots.append(r)

        # Add the autocloud dirs to the simple directories we found
        foundDirs.extend(autoRoots)

        # remove any duplicates (by briefly converting into a dict, which preserves order)
        foundDirs = list(dict.fromkeys(foundDirs))
        return foundDirs

    """ 
    confirm that at least one savegame exists, to validate our assumptions about where they are being stored
    if no savegame found claim we can't back this app up.
    """

    def _rcf_is_valid(self, root_dir: str, rcf: list[str]):
        for f in rcf:
            full = os.path.join(root_dir, f)
            if os.path.isfile(full):
                logger.debug(f'RCF is valid { root_dir }')
                return True
            else:
                # logger.debug(f'RCF file not found { full }')
                pass
        # logger.debug(f'RCF invalid { root_dir }')
        return False

    """
    Read the rcf file for the specified game, or if not found return None
    """

    def _read_rcf(self, game_info: dict) -> list[str]:
        dirs = self._get_gamedir(game_info["game_id"])
        paths = [os.path.join(d, "remotecache.vdf") for d in dirs]
        # logger.debug(f'Read rcf {path}')

        rcf = []
        for path in paths:
            if os.path.isfile(path):
                with open(path) as f:
                    s = f.read()  # read full file as a string
                    lines = s.split("\n")
                    # logger.debug(f'file is {lines}')

                    # drop first two lines because they are "gameid" {
                    lines = lines[2:]
                    # We look for lines containing quotes and immediately preceeding lines with just an open brace
                    prevl = None

                    skipping = False
                    for l in lines:
                        s = l.strip()
                        if skipping:  # skip the contents of {} records
                            if s == "}":
                                skipping = False
                        elif s == "{":
                            if prevl:
                                # prevl will have quote chars as first and last of string.  Remove them
                                filename = (prevl[1:])[:-1]
                                rcf.append(filename)
                                prevl = None

                            # Now skip until we get a close brace
                            skipping = True
                        else:
                            prevl = s
            else:
                logger.debug(f"No rcf {path}")

        logger.debug(f'Read rcf with { len(rcf) } entries')

        # If we haven't already found where the savegames for this app live, do so now (or fail if not findable)
        if "save_games_roots" not in game_info:
            saveRoots = self._find_save_games(game_info, rcf)
            if len(saveRoots) < 1:
                logger.warning(
                    f'Unable to backup { game_info }: not yet supported')
                return None

            # remove save_game roots which don't seem to match any filenames in the existing rcf data from valve
            # confirm that at least one savegame exists, to validate our assumptions about where they are being stored
            # if no savegame found claim we can't back this app up.
            saveRoots = list(
                filter(lambda root: self._rcf_is_valid(root, rcf), saveRoots))
            if len(saveRoots) < 1:
                logger.warning(
                    f'RCF seems invalid, not backing up { game_info }')
                return None

            # For legacy purposes, use the first found entry as save_games_root, we store this as a dict mapping
            # directory name in game to the suffix used on our backup dir.  To keep compatibility with old rev1
            # steamback we use emptystring for the first found root and _n for everyone after.
            rootsDict = {}
            for idx, dir in enumerate(saveRoots):
                rootsDict[dir] = "" if idx == 0 else f"_{ idx }"
            game_info["save_games_roots"] = rootsDict

        # logger.debug(f'rcf files are {r}')
        return rcf

    """Get the root directory this game uses for its save files
    """

    def _get_game_roots(self, game_info: dict) -> dict:
        return game_info["save_games_roots"]

    """
    Parse valve rcf json objects and copy named files.  Given one particular source and one particular dest directory

    {
	"ChangeNumber"		"-6703994677807818784"
	"ostype"		"-184"
	"my games/XCOM2/XComGame/SaveData/profile.bin"
	{
		"root"		"2"
		"size"		"15741"
		"localtime"		"1671427173"
		"time"		"1671427172"
		"remotetime"		"1671427172"
		"sha"		"df59d8d7b2f0c7ddd25e966493d61c1b107f9b7a"
		"syncstate"		"1"
		"persiststate"		"0"
		"platformstosync2"		"-1"
	}
    """

    def _copy_by_rcf(self, rcf: list, src_dir: str, dest_dir: str):
        numCopied = 0
        for k in rcf:
            spath = os.path.join(src_dir, k)

            # if the filename contains directories - create them
            if os.path.exists(spath):
                numCopied = numCopied + 1
                dpath = os.path.join(dest_dir, k)
                # logger.debug(f'Copying file { k }')
                if not self.dry_run:
                    dir = os.path.dirname(dpath)
                    os.makedirs(dir, exist_ok=True)
                    shutil.copy2(spath, dpath)
            else:
                # logger.warning(f'Not copying missing file { k }')
                pass
        logger.info(
            f'Copied { numCopied } files from { src_dir } to { dest_dir }')

    """
    Find the timestamp of the most recently updated file in a directory
    """

    def _get_directory_timestamp(self, rcf: list, src_dir: str) -> int:
        # Get full paths to existing files mentioned in rcf.
        paths = map(lambda k: os.path.join(src_dir, k), rcf)
        full = list(filter(lambda p: os.path.exists(p), paths))

        m_times = list(map(lambda f: os.path.getmtime(f), full))
        max_time = int(round(max(m_times) * 1000))  # we use msecs not secs
        return max_time

    """
    Find the timestamp of the most recently updated file in a rcf
    """

    def _get_rcf_timestamp(self, rcf: list, game_info: dict) -> int:
        src_dirs = self._get_game_roots(game_info).keys()

        # for each directory, get the max time, then find the max of those times
        dir_times = map(
            lambda dir: self._get_directory_timestamp(rcf, dir), src_dirs)
        max_time = max(dir_times)

        return max_time

    """
    Create a save file directory save-GAMEID-timestamp and return SaveInfo object
    Also write the sister save-GAMEID-timestamp.json metadata file
    """

    def _create_savedir(self, game_info: dict, is_undo: bool = False) -> dict:
        game_id = game_info["game_id"]
        # This better be populated by now!
        assert game_info["save_games_roots"]
        ts = int(round(time.time() * 1000))  # msecs since 1970

        si = {
            "game_info": game_info,
            "timestamp": ts,
            "filename": f'{ "undo" if is_undo else "save" }_{ game_id }_{ ts }',
            "is_undo": is_undo
        }

        path = self._saveinfo_to_dir(si)
        logger.debug(f'Creating savedir JSON {path}, {si}')
        if not self.dry_run:
            with open(path + ".json", 'w') as fp:
                json.dump(si, fp, indent=1)

        return si

    """
    Load a savesaveinfo.json from the saves directory
    """

    def _file_to_saveinfo(self, filename: str) -> dict:
        dir = self._get_savesdir()
        with open(os.path.join(dir, filename)) as j:
            try:
                si = json.load(j)
                # logger.debug(f'Parsed filename {filename} as {si}')

                # convert old pre version 2 files to have valid metadata
                gi = si["game_info"]
                if "save_games_roots" not in gi:
                    logger.warning("Saveinfo is old format, upgrading...")
                    gi["save_games_roots"] = {gi["save_games_root"]: ""}
                    del gi["save_games_root"]
            except json.JSONDecodeError as e:
                logger.error(
                    f'Corrupted JSON for {filename}, attempting delete of bad json file, {e}')
                try:
                    os.remove(j)
                except OSError:
                    pass
                raise  # still call this a failure for the parent to deal with.  The next time they scan the bogus JSON will be gone
            return si

    """ delete the savedir and associated json
    """

    def _delete_savedir(self, filename):
        root = self._get_savesdir()

        # Make sure saves dir is a valid absolute path before we start doing dangerous things
        assert root[0] == '/'

        filepath = os.path.join(root, filename) + "*"
        files = glob.glob(filepath)
        for f in files:
            logger.debug(f'Deleting {f}')
            try:
                if os.path.isfile(f):
                    os.remove(f)
                elif os.path.isdir(f):
                    shutil.rmtree(f, ignore_errors=True)
            except OSError:
                pass

    """
    we keep only the most recent undo and the most recent 10 saves
    """
    async def _cull_old_saves(self):
        infos = await self.get_saveinfos()

        undos = list(filter(lambda i: i["is_undo"], infos))
        saves = list(filter(lambda i: not i["is_undo"], infos))

        def delete_oldest(files, to_keep):
            while len(files) > to_keep:
                todel = files.pop()
                logger.info(f'Culling { todel }')
                # if not self.dry_run: we ignore dryrun for culling otherwise our test system dir fills up
                self._delete_savedir(todel["filename"])

        delete_oldest(undos, 1)
        delete_oldest(saves, self.max_saves)

    """
    Given a save_info return a full pathname to that directory
    """

    def _saveinfo_to_dir(self, save_info: dict) -> str:
        d = self._get_savesdir()
        return os.path.join(d, save_info["filename"])

    """
    Get the newest saveinfo for a specified game (or None if not found)
    """
    async def _get_newest_save(self, game_id):
        infos = await self.get_saveinfos()

        # Find first matching item or None
        newest = next(
            (x for x in infos if x["game_info"]["game_id"] == game_id and not x["is_undo"]), None)
        return newest

    """
    Copy all savegame info from the game into our mirror (might have multiple save root directories)
    """

    def _copy_all_to_saveinfo(self, save_info: dict, rcf: list[str]):
        try:
            game_info = save_info["game_info"]
            dest_basename = self._saveinfo_to_dir(save_info)
            gameRoots = self._get_game_roots(game_info)
            for src_dir, suffix in gameRoots.items():
                dest_dir = dest_basename + suffix
                # logger.debug(f'copying gamedir { src_dir } to { dest_dir }')
                self._copy_by_rcf(rcf, src_dir, dest_dir)
        except:
            # Don't keep old directory/json around if we encounter an exception
            self._delete_savedir(save_info["filename"])
            raise  # rethrow

    """
    Copy all savegame info from our mirror into the game
    """

    def _copy_all_from_saveinfo(self, save_info: dict, rcf: list[str]):
        game_info = save_info["game_info"]
        mirror_basename = self._saveinfo_to_dir(save_info)
        gameRoots = self._get_game_roots(game_info)
        for dest_dir, suffix in gameRoots.items():
            src_dir = mirror_basename + suffix
            # logger.debug(f'copying backup dir { src_dir } to { dest_dir }')
            self._copy_by_rcf(rcf, src_dir, dest_dir)

    """
    Backup a particular game.

    Returns a new SaveInfo object or None if no backup was needed or possible
    SaveInfo is a dict with filename, game_id, timestamp, is_undo
    game_info is a dict of game_id and install_root
    """
    async def do_backup(self, game_info: dict, apply_last_used: bool = False, dry_run: bool = False) -> dict:
        logger.info(f'Attempting backup of { game_info }')
        rcf = self._read_rcf(game_info)

        if not rcf:
            return None

        game_id = game_info["game_id"]
        newest_save = await self._get_newest_save(game_id)
        if newest_save and self.ignore_unchanged:
            game_timestamp = self._get_rcf_timestamp(rcf, game_info)
            if newest_save["timestamp"] > game_timestamp:
                logger.warning(
                    f'Skipping backup for { game_id } - no changed files')
                return None

        if not dry_run:
            saveInfo = self._create_savedir(game_info)
            self._copy_all_to_saveinfo(saveInfo, rcf)
            if apply_last_used:
                self.last_used_save_info = saveInfo
            await self._cull_old_saves()
            return saveInfo
        else:
            return {}  # For dryruns return a placeholder empty dict to indicate 'would have backed up'

    """
    Restore a particular savegame using the saveinfo object
    """
    async def do_restore(self, save_info: dict):
        # logger.debug(f'In do_restore for { save_info }')
        game_info = save_info["game_info"]
        rcf = self._read_rcf(game_info)
        assert rcf

        # first make the backup (unless restoring from an undo already)
        if not save_info["is_undo"]:
            logger.info('Generating undo files')
            undoInfo = self._create_savedir(game_info, is_undo=True)
            self._copy_all_to_saveinfo(undoInfo, rcf)

        # then restore from our old snapshot
        logger.info(f'Attempting restore of { save_info }')
        self._copy_all_from_saveinfo(save_info, rcf)

        # we now might have too many undos, so possibly delete one
        await self._cull_old_saves()
        self.last_used_save_info = save_info

    """
    Given a list of game_infos, return a list of game_infos which are supported for backups
    """
    async def find_supported(self, game_infos: list) -> list[dict]:
        # if we get any sort of exception while scanning a particular game info, keep trying the others
        def try_rcf(info):
            try:
                # logger.debug(f'try_rcf { info }')
                return self._read_rcf(info)
            except FileNotFoundError:
                logger.warning(
                    f'RCF file not found in scan of {info}, probably an unmounted SD card')
                return None
            except Exception:
                logger.error(
                    f'Error scanning rcf for {info}, exception { traceback.format_exc() }')
                return None

        # logger.debug(f'find supported { game_infos }')
        supported = list(filter(try_rcf, game_infos))
        return supported

    """
    Given a list of directory names, return a list of directories that are actually mounted
    """
    async def find_mounted(self, dirs: list) -> list[str]:
        # if we get any sort of exception while scanning a particular game info, keep trying the others
        def try_mount(f):
            try:
                return os.path.exists(f)
            except Exception:
                logger.error(
                    f'Error finding mount for {f}, exception { traceback.format_exc() }')
                return None

        mounted = list(filter(try_mount, dirs))
        # logger.debug(f'find mount { dirs } -> { mounted }')
        return mounted

    """
    Return all available saves, newest save first and undo as the absolute first

    Returns an array of SaveInfo objects
    """
    async def get_saveinfos(self) -> list[dict]:
        dir = self._get_savesdir()
        files = filter(lambda f: f.endswith(".json"), os.listdir(dir))

        def attempt_saveinfo(f: str) -> dict:
            try:
                si = self._file_to_saveinfo(f)
                return si
            except Exception as e:
                logger.error(f'Error reading JSON for {f}, {e}')
                return None

        infos = list(filter(lambda f: f is not None, map(
            lambda f: attempt_saveinfo(f), files)))

        # Sort by timestamp, newest first
        infos.sort(key=lambda i: i["timestamp"], reverse=True)

        # put undos first
        undos = list(filter(lambda i: i["is_undo"], infos))
        saves = list(filter(lambda i: not i["is_undo"], infos))
        infos = undos + saves
        return infos

    async def get_last_used_save_info(self) -> dict:
        logger.info('Attempting get last used save info')
        return self.last_used_save_info
    
    async def do_reuse(self):
        logger.debug(f'In do_reuse')
        save_info = self.last_used_save_info
        if save_info == None:
            return
        game_info = save_info["game_info"]
        rcf = self._read_rcf(game_info)
        assert rcf
        # copy last used save to steam
        self._copy_all_from_saveinfo(save_info, rcf)
        # make new save info
        logger.info('Generating new save files for reuse')
        reuse_info = self._create_savedir(game_info)
        # copy from steam to new reuse_info
        self._copy_all_to_saveinfo(reuse_info, rcf)
        # set new generated reuse_info to last used save
        self.last_used_save_info = reuse_info
        # delete previous last used save
        await self.do_delete(save_info)

    async def do_delete(self, save_info: dict):
        logger.debug(f'In do_delete { save_info }')
        self._delete_savedir(save_info["filename"])