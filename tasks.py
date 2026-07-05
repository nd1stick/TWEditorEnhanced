"""Background tasks.  Ports of LoadFile, LoadTemplates, UnpackSave,
PackFile and SaveFile.

Each task runs on its own thread, reports progress through the
ProgressDialog and signals completion with close_dialog.  Only the
dialog's thread-safe methods are touched from here; all widget work
happens on the main thread inside the dialog poll.
"""

import os
import threading

from . import context
from .database import Database
from .dbmodel import DBElement, ElementType, DBList
from .entries import ResourceEntry
from .errors import DBException
from .model import ItemTemplate, Quest
from .resourcedb import ResourceDatabase
from .savedb import SaveDatabase


def _copy_to_file(in_stream, path):
    if os.path.exists(path):
        os.remove(path)
    with open(path, "wb") as out:
        while True:
            chunk = in_stream.read(4096)
            if not chunk:
                break
            out.write(chunk)


def _prune_corrupted_nodes(element):
    """Recursively walks the database tree and removes any structs tagged as corrupted."""
    if element is None:
        return
        
    if element.type in (ElementType.STRUCT, ElementType.LIST):
        old_list = element.value
        if old_list is None:
            return
            
        clean_elements = []
        for i in range(old_list.element_count()):
            child = old_list.get_element_at(i)
            
            # Check if this child is a STRUCT that contains our passive tag
            is_corrupt = False
            if child.type == ElementType.STRUCT:
                for j in range(child.value.element_count()):
                    if getattr(child.value.get_element_at(j), "_is_corrupted_id", False):
                        is_corrupt = True
                        break
            
            # If it's clean, keep it and recurse deeper
            if not is_corrupt:
                _prune_corrupted_nodes(child) 
                clean_elements.append(child)
                
        # Rebuild the DBList if we removed anything
        if len(clean_elements) != old_list.element_count():
            new_list = DBList(len(clean_elements))
            for el in clean_elements:
                new_list.add_element(el)
            element.value = new_list


class LoadFile(threading.Thread):
    def __init__(self, dialog, path):
        super().__init__()
        self.dialog = dialog
        self.path = path
        self.success = False

    def run(self):
        try:
            save_database = SaveDatabase(self.path)
            save_database.load()
            self.dialog.update_progress(25)
            save_name = save_database.get_name()
            context.save_prefix = save_name + context.file_separator

            sep = save_name.find(" ")
            if sep != 6 or not save_name[0:1].isdigit():
                raise DBException(
                    "Save name is not formatted correctly")
            context.smm_name = "save_" + save_name[0:6] + ".smm"
            entry = save_database.get_entry(context.smm_name)
            if entry is None:
                raise DBException(
                    "Save does not contain " + context.smm_name)
            _copy_to_file(entry.get_input_stream(),
                          context.smm_file)
            smm_database = Database(context.smm_file)
            smm_database.load()
            self.dialog.update_progress(35)

            top = smm_database.top_level_struct.value
            starting_mod = top.get_string("StartingMod")
            if len(starting_mod) == 0:
                raise DBException(
                    "StartingMod not found in SMM database")
            element = top.get_element("QuestBase_list")
            if element is None or element.type != ElementType.LIST:
                raise DBException(
                    "QuestBaseList not found in SMM database")
            quest_list = element.value
            if quest_list.element_count() == 0:
                raise DBException(
                    "No quest list found in SMM database")
            fields = quest_list.get_element_at(0).value
            quest_db_name = fields.get_string("QuestBase")
            if len(quest_db_name) == 0:
                raise DBException(
                    "No quest database name found in SMM database")

            context.mod_name = starting_mod + ".sav"
            entry = save_database.get_entry(context.mod_name)
            if entry is None:
                raise DBException(
                    "Save does not contain " + context.mod_name)
            _copy_to_file(entry.get_input_stream(),
                          context.mod_file)
            self.dialog.update_progress(50)

            mod_database = ResourceDatabase(context.mod_file)
            mod_database.load()
            self.dialog.update_progress(60)

            resource_entry = mod_database.get_entry("module.ifo")
            if resource_entry is None:
                raise DBException(
                    "Save does not contain module.ifo")
            _copy_to_file(resource_entry.get_input_stream(),
                          context.database_file)
            self.dialog.update_progress(75)

            database = Database(context.database_file)
            database.load()
            top = database.top_level_struct.value
            element = top.get_element("Mod_PlayerList")
            if element is None or element.type != ElementType.LIST:
                raise DBException(
                    "module.ifo does not contain Mod_PlayerList")
            top = element.value
            if top.element_count() == 0:
                raise DBException("Mod_PlayerList is empty")
            self.dialog.update_progress(80)

            file_name = quest_db_name + ".qdb"
            entry = save_database.get_entry(file_name)
            if entry is None:
                raise DBException(
                    "Save does not contain " + file_name)
            quest_database = Database()
            quest_database.load_stream(entry.get_input_stream())
            top = quest_database.top_level_struct.value
            element = top.get_element("Quests")
            if element is None or element.type != ElementType.LIST:
                raise DBException(
                    "Quests not found in quest database")
            quest_list = element.value
            self.dialog.update_progress(85)

            count = quest_list.element_count()
            context.quests = []
            for i in range(count):
                fields = quest_list.get_element_at(i).value
                resource_name = fields.get_string("File")
                file_name = resource_name + ".qst"
                entry = save_database.get_entry(file_name)
                if entry is None:
                    raise DBException(
                        "Save does not contain " + file_name)
                quest_database = Database()
                quest_database.load_stream(
                    entry.get_input_stream())
                quest = Quest(resource_name, quest_database)
                if len(quest.quest_name) > 0:
                    context.quests.append(quest)

            context.player_name = "player.utc"
            entry = save_database.get_entry(context.player_name)
            if entry is None:
                raise DBException(
                    "Save does not contain " + context.player_name)
            _copy_to_file(entry.get_input_stream(),
                          context.player_file)
            player_database = Database(context.player_file)
            player_database.load()
            self.dialog.update_progress(100)

            context.save_database = save_database
            context.mod_database = mod_database
            context.database = database
            context.player_database = player_database
            context.smm_database = smm_database

            # --- CORRUPTION CLEANUP ---
            # Prune garbage data from the main module and player databases
            _prune_corrupted_nodes(database.top_level_struct)
            _prune_corrupted_nodes(player_database.top_level_struct)
            # --------------------------

            self.success = True
        except DBException as exc:
            context.log_exception(
                "Save file structure is not valid", exc)
        except OSError as exc:
            context.log_exception("Unable to read save file", exc)
        except Exception as exc:
            context.log_exception(
                "Exception while opening save file", exc)

        self.dialog.close_dialog(self.success)


class LoadTemplates(threading.Thread):
    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog
        self.success = False

    def run(self):
        try:
            items = list(context.resource_files.items())
            entry_count = len(items)
            context.item_templates = []
            processed = 0
            current = 0

            for _, entry_object in items:
                resource_name = None
                in_stream = None
                if isinstance(entry_object, str):
                    name = os.path.basename(entry_object).lower()
                    dot = name.rfind(".")
                    if dot > 0 and name[dot:] == ".uti":
                        resource_name = name[:dot]
                        in_stream = open(entry_object, "rb")
                else:
                    name = entry_object.file_name.lower()
                    dot = name.rfind(".")
                    if dot > 0 and name[dot:] == ".uti":
                        resource_name = entry_object.resource_name
                        in_stream = entry_object.get_input_stream()

                if in_stream is not None:
                    database = Database()
                    database.load_stream(in_stream)
                    in_stream.close()
                    fields = database.top_level_struct.value
                    item_name = fields.get_string("LocalizedName")
                    description = fields.get_string("Description")
                    if len(item_name) > 0 \
                            and len(description) > 0:
                        resource_element = DBElement(
                            ElementType.RESOURCE, 0,
                            "TemplateResRef", resource_name)
                        fields.set_element(
                            "TemplateResRef", resource_element)
                        context.item_templates.append(
                            ItemTemplate(fields))

                processed += 1
                new_progress = processed * 100 // entry_count
                if new_progress > current + 9:
                    current = new_progress
                    self.dialog.update_progress(current)

            self.success = True
        except DBException as exc:
            context.log_exception(
                "Database error while loading inventory templates",
                exc)
        except OSError as exc:
            context.log_exception(
                "I/O error while loading inventory templates", exc)
        except Exception as exc:
            context.log_exception(
                "Exception while loading inventory templates", exc)

        self.dialog.close_dialog(self.success)


class UnpackSave(threading.Thread):
    def __init__(self, dialog, directory):
        super().__init__()
        self.dialog = dialog
        self.directory = directory
        self.success = False

    def run(self):
        try:
            entries = context.save_database.get_entries()
            total = len(entries)
            processed = 0
            current = 0
            for entry in entries:
                path = os.path.join(self.directory,
                                    entry.resource_name)
                if os.path.exists(path):
                    os.remove(path)
                _copy_to_file(entry.get_input_stream(), path)
                processed += 1
                new_progress = processed * 100 // total
                if new_progress > current + 9:
                    current = new_progress
                    self.dialog.update_progress(current)
            self.success = True
        except OSError as exc:
            context.log_exception(
                "I/O error while unpacking save", exc)
        except Exception as exc:
            context.log_exception(
                "Exception while unpacking save", exc)

        self.dialog.close_dialog(self.success)


class PackFile(threading.Thread):
    def __init__(self, dialog, directory):
        super().__init__()
        self.dialog = dialog
        self.directory = directory
        self.success = False

    def run(self):
        try:
            entries = context.save_database.get_entries()
            for entry in entries:
                path = os.path.join(self.directory,
                                    entry.resource_name)
                if not os.path.isfile(path):
                    raise IOError(
                        "Resource '" + path + "' not found")
                if entry.compressed:
                    entry.set_on_disk(False)
                    entry.read_from_file(path)
                else:
                    entry.set_resource_file(
                        path, 0, os.path.getsize(path))
            context.save_database.save()
            self.success = True
        except OSError as exc:
            context.log_exception("Unable to save file", exc)
        except Exception as exc:
            context.log_exception(
                "Exception while saving file", exc)

        self.dialog.close_dialog(self.success)


class SaveFile(threading.Thread):
    def __init__(self, dialog):
        super().__init__()
        self.dialog = dialog
        self.success = False

    def run(self):
        try:
            context.database.save()
            self.dialog.update_progress(15)

            resource_entry = ResourceEntry(
                "module.ifo", context.database_file)
            context.mod_database.add_entry(resource_entry)
            context.mod_database.save()
            self.dialog.update_progress(30)

            mod_database = ResourceDatabase(
                context.mod_database.get_path())
            mod_database.load()
            context.mod_database = mod_database
            self.dialog.update_progress(45)

            context.save_database.add_entry_file(
                context.mod_name, context.mod_file)
            self.dialog.update_progress(60)

            context.player_database.save()
            context.save_database.add_entry_file(
                context.player_name, context.player_file)
            self.dialog.update_progress(65)

            self._save_modified_quests()
            self.dialog.update_progress(75)

            context.smm_database.save()
            context.save_database.add_entry_file(
                context.smm_name, context.smm_file)
            self.dialog.update_progress(80)

            context.save_database.save()
            self.dialog.update_progress(90)

            save_database = SaveDatabase(
                context.save_database.get_path())
            save_database.load()
            context.save_database = save_database
            self.dialog.update_progress(100)

            self.success = True
        except DBException as exc:
            context.log_exception(
                "Unable to update save database", exc)
        except OSError as exc:
            context.log_exception("Unable to save file", exc)
        except Exception as exc:
            context.log_exception(
                "Exception while saving file", exc)

        self.dialog.close_dialog(self.success)

    @staticmethod
    def _save_modified_quests():
        """Write each Quest whose quest_modified flag is set back
        into the save.  Each modified quest.database is serialized
        to a temporary .qst on disk, added to save_database via
        add_entry_file (which mirrors how the module, player and
        smm databases are added), and the temp file is removed.

        add_entry_file caches the bytes on the SaveEntry as an
        in-memory bytearray, so the temp file is no longer needed
        by the time save_database.save() runs.
        """
        quests = getattr(context, "quests", None)
        if not quests:
            return
        for quest in quests:
            if not quest.quest_modified:
                continue
            entry_name = quest.resource_name + ".qst"
            tmp_path = os.path.join(
                context.tmp_dir,
                "TWEditor_" + quest.resource_name + ".qst")
            try:
                with open(tmp_path, "wb") as out:
                    quest.database.save_stream(out)
                context.save_database.add_entry_file(
                    entry_name, tmp_path)
                quest.quest_modified = False
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
