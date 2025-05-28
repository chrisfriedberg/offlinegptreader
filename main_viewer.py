from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QTextBrowser,
    QLabel, QPushButton, QFileDialog, QCheckBox, QMenuBar, QMenu, QScrollArea, QGroupBox, QFormLayout, QLineEdit,
    QComboBox, QToolButton, QDateEdit, QMessageBox, QInputDialog, QStyle  # <-- Add QStyle
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QIcon  # Add this import
from ui_constants import ButtonConstants
import os
import csv
import re
import markdown  # NEW: proper markdown rendering
import subprocess

INDEX_CSV = 'feralcat_index.csv'
EXPORT_DIR = 'markdown_exports'

class FeralCatViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Offline GPT Reader")
        self.resize(1000, 700)
        self.active_tags = set()
        self.date_range = (None, None)  # (start_date, end_date)
        self.last_search_query = ""  # Store last search query for highlighting
        self.setup_ui()
        self.load_index()
        self.load_theme()  # Load the theme on startup

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Menu bar
        menubar = QMenuBar()
        file_menu = QMenu("File", self)
        tools_menu = QMenu("Tools", self)
        help_menu = QMenu("Help", self)

        file_menu.addAction("Open Directory", self.select_directory)
        file_menu.addAction("Exit", self.close)
        tools_menu.addAction("Refresh Index", self.load_index)
        tools_menu.addAction("Run Parser", self.run_parser_script)
        tools_menu.addAction("Toggle Dark Mode", self.toggle_dark_mode)
        # Add "Load Icon" to Tools menu
        tools_menu.addAction("Load Icon", self.load_icon)
        tools_menu.addAction("Copy Tags to Clipboard", self.copy_tags_to_clipboard)
        help_menu.addAction("About", self.show_about)

        menubar.addMenu(file_menu)
        menubar.addMenu(tools_menu)
        menubar.addMenu(help_menu)
        layout.setMenuBar(menubar)

        # Main layout
        body = QHBoxLayout()

        # Left Sidebar: Tag Filters + List + Search
        sidebar_container = QVBoxLayout()

        # --- Tag filter dropdown and clear button ---
        self.tag_search_box = QComboBox()
        self.tag_search_box.setEditable(True)
        self.tag_search_box.setInsertPolicy(QComboBox.NoInsert)
        self.tag_search_box.addItem("Tags...")  # Add placeholder
        self.tag_search_box.setCurrentIndex(0)
        self.tag_search_box.activated[int].connect(self._on_tag_activated)

        self.clear_tag_button = QToolButton()
        self.clear_tag_button.setText("✖")
        self.clear_tag_button.clicked.connect(self.clear_active_tag)

        # NEW: Copy Tag Content button
        self.copy_tag_content_button = QPushButton("Copy Tag Content")
        self.copy_tag_content_button.clicked.connect(self.copy_tag_content)

        tag_bar = QHBoxLayout()
        tag_bar.addWidget(self.tag_search_box)
        tag_bar.addWidget(self.clear_tag_button)
        tag_bar.addWidget(self.copy_tag_content_button)  # Add the new button
        sidebar_container.addLayout(tag_bar)

        # --- Date range filter ---
        date_bar = QHBoxLayout()
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.start_date_edit.setDate(QDate.currentDate())  # Set to today by default
        self.start_date_edit.dateChanged.connect(self._on_date_range_changed)

        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.end_date_edit.setDate(QDate.currentDate())  # Set to today by default
        self.end_date_edit.dateChanged.connect(self._on_date_range_changed)

        self.clear_date_button = QPushButton("Clear Date Filter")
        self.clear_date_button.clicked.connect(self.clear_date_filter)

        date_bar.addWidget(QLabel("From:"))
        date_bar.addWidget(self.start_date_edit)
        date_bar.addWidget(QLabel("To:"))
        date_bar.addWidget(self.end_date_edit)
        date_bar.addWidget(self.clear_date_button)
        sidebar_container.addLayout(date_bar)
        # --- END date range filter ---

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Search titles...")
        self.search_box.textChanged.connect(self.apply_filters)

        self.sidebar = QListWidget()
        self.sidebar.currentItemChanged.connect(self.load_selected_convo)

        sidebar_container.addWidget(self.search_box)
        sidebar_container.addWidget(self.sidebar)

        # Right Panel: Viewer + Meta
        right_panel = QVBoxLayout()
        self.meta_label = QLabel("Select a conversation to view metadata.")
        self.viewer = QTextBrowser()
        self.viewer.setOpenExternalLinks(True)

        self.copy_button = QPushButton("Copy to Clipboard")
        self.copy_button.clicked.connect(self.copy_to_clipboard)

        self.close_button = QPushButton(ButtonConstants.CLOSE)
        self.close_button.clicked.connect(self.close)

        # --- Tag Editor for the selected conversation ---
        self.tag_edit_label = QLabel("Edit tags for this conversation:")
        self.tag_edit_box = QLineEdit()
        self.tag_edit_box.setPlaceholderText("Comma-separated tags (e.g. tag1, tag2)")
        self.save_tag_button = QPushButton("Save Tags")
        self.save_tag_button.clicked.connect(self.save_tags_for_selected)

        # NEW: Remove Tags button
        self.remove_tag_button = QPushButton("Remove Tags")
        self.remove_tag_button.clicked.connect(self.remove_tags_for_selected)

        tag_edit_bar = QHBoxLayout()
        tag_edit_bar.addWidget(self.tag_edit_box)
        tag_edit_bar.addWidget(self.save_tag_button)
        tag_edit_bar.addWidget(self.remove_tag_button)  # Add to layout

        right_panel.addWidget(self.meta_label)
        right_panel.addWidget(self.viewer)
        right_panel.addWidget(self.copy_button)
        right_panel.addWidget(self.close_button)
        right_panel.addWidget(self.tag_edit_label)
        right_panel.addLayout(tag_edit_bar)

        body.addLayout(sidebar_container, 3)
        body.addLayout(right_panel, 5)
        layout.addLayout(body)

        # Set default icon if no custom icon is loaded yet
        self.icon_path = os.path.join(os.path.dirname(__file__), "feralcat_icon.ico")
        if os.path.exists(self.icon_path):
            icon = QIcon(self.icon_path)
        else:
            icon = self.style().standardIcon(QStyle.SP_DesktopIcon)
        self.setWindowIcon(icon)
        menubar.setWindowIcon(icon)

    # ✅ 2. Add these methods to your class:
    def set_active_tag(self, tag):
        self.active_tags = {tag}
        self.apply_filters()

    def clear_active_tag(self):
        self.active_tags.clear()
        self.tag_search_box.setCurrentIndex(-1)
        self.apply_filters()

    def load_index(self):
        self.sidebar.clear()
        self.index = []
        tag_counts = {}

        if not os.path.exists(INDEX_CSV):
            return

        with open(INDEX_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.index.append(row)
                # Count tags
                match = re.findall(r'#(\w+)', row.get('title', ''))
                for tag in match:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # Clear and re-add placeholder
        self.tag_search_box.clear()
        self.tag_search_box.addItem("Tags...")  # Placeholder
        for tag in sorted(tag_counts):
            self.tag_search_box.addItem(tag)
        self.tag_search_box.setCurrentIndex(0)  # Default to placeholder

        self.apply_filters()

    def filter_by_tags(self):
        # Only filter if a tag is selected
        pass  # Filtering now handled in apply_filters

    def apply_filters(self):
        query = self.search_box.text().strip().lower()
        self.last_search_query = query  # Store for highlighting
        self.sidebar.clear()
        start, end = self.date_range
        self.filtered_rows = []  # Store filtered rows for later access

        for row in self.index:
            tags_in_title = set(re.findall(r'#(\w+)', row['title']))
            date_str = row.get('date', '')
            date_ok = True
            if start and end and date_str:
                try:
                    row_date = QDate.fromString(date_str, "yyyy-MM-dd")
                    date_ok = (not start or row_date >= start) and (not end or row_date <= end)
                except Exception:
                    date_ok = True

            full_title = f"{row['date']} - {row['title']}"
            title_match = query in full_title.lower() if query else True
            content_match = False

            # Always check content if searching
            if query:
                filepath = os.path.join(EXPORT_DIR, row['filename'])
                if os.path.exists(filepath):
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read().lower()
                            content_match = query in content
                    except Exception:
                        content_match = False

            # Show if tag/date filter passes, and either title or content matches (or no query)
            if (not self.active_tags or self.active_tags.issubset(tags_in_title)) and date_ok:
                if (not query) or title_match or content_match:
                    self.sidebar.addItem(full_title)
                    self.filtered_rows.append(row)

        # If nothing is shown, show a message in the viewer
        if not self.filtered_rows:
            self.viewer.setText("No conversations found. Try refreshing the index or check your filters.")

    def load_selected_convo(self, current, _):
        idx = self.sidebar.currentRow()
        if idx < 0 or idx >= len(self.filtered_rows):
            self.viewer.setText("")
            self.meta_label.setText("Select a conversation to view metadata.")
            return

        meta = self.filtered_rows[idx]
        filepath = os.path.join(EXPORT_DIR, meta['filename'])
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if content:
                html = self.markdown_to_html(content)
                query = self.last_search_query
                if query:
                    # Highlight all occurrences (case-insensitive) in the HTML
                    def highlight_match(m):
                        return f"<span style='background-color: yellow; color: black;'>{m.group(0)}</span>"
                    # Use regex to highlight all matches, even across HTML tags
                    pattern = re.compile(re.escape(query), re.IGNORECASE)
                    html = pattern.sub(highlight_match, html)
                self.viewer.setHtml(html)
            else:
                self.viewer.setText("[No content found in this Markdown file.]")
            self.meta_label.setText(f"Tags & Metadata:\nFile: {meta['filename']} | Words: {meta.get('word_count', '?')}")
        else:
            self.viewer.setText("[Missing .md file]")
            self.meta_label.setText(f"Tags & Metadata:\nFile: {meta['filename']} (missing)")

    def markdown_to_html(self, markdown_text):
        html_body = markdown.markdown(markdown_text)
        return f"<div style='font-family: Consolas; font-size: 14px;'>{html_body}</div>"

    def copy_to_clipboard(self):
        text = self.viewer.toPlainText()
        QApplication.clipboard().setText(text)
        QMessageBox.information(self, "Copied", "Copied to clipboard.")

    def select_directory(self):
        QFileDialog.getExistingDirectory(self, "This feature is reserved for future bulk import.")

    def show_about(self):
        self.viewer.setText("Offline GPT Reader\n\nThis tool helps you rediscover and reuse your GPT convos, offline and organized.")

    def run_parser_script(self):
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Select conversations.json")
        file_dialog.setNameFilter("JSON files (*.json)")
        file_dialog.setFileMode(QFileDialog.ExistingFile)

        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            convo_path = selected_files[0]

            try:
                result = subprocess.run(
                    ['python', 'conversation_parser.py', convo_path],
                    cwd=os.path.dirname(__file__),  # where the script lives
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    # Clear tags and sidebar before loading new index to prevent ghost tags
                    self.active_tags.clear()
                    self.tag_search_box.clear()
                    self.sidebar.clear()
                    self.load_index()
                    self.viewer.setText("✅ Parser ran successfully.\n\n" + result.stdout)
                else:
                    self.viewer.setText("❌ Parser failed.\n\n" + result.stderr)
            except Exception as e:
                self.viewer.setText(f"⚠️ Error running parser:\n{str(e)}")

    def _on_tag_activated(self, index):
        if index == 0:
            self.clear_active_tag()
            return
        tag = self.tag_search_box.itemText(index)
        self.set_active_tag(tag)

    def _on_date_range_changed(self):
        start = self.start_date_edit.date() if self.start_date_edit.date().isValid() else None
        end = self.end_date_edit.date() if self.end_date_edit.date().isValid() else None
        self.date_range = (start, end)
        self.apply_filters()

    def save_tags_for_selected(self):
        idx = self.sidebar.currentRow()
        if idx < 0 or idx >= len(self.filtered_rows):
            return
        meta = self.filtered_rows[idx]
        # Get new tags from the editor
        new_tags = [t.strip() for t in self.tag_edit_box.text().split(",") if t.strip()]
        # Remove old tags from title, add new ones
        title_wo_tags = re.sub(r'#\w+', '', meta['title']).strip()
        if new_tags:
            meta['title'] = f"{title_wo_tags} " + " ".join(f"#{t}" for t in new_tags)
        else:
            meta['title'] = title_wo_tags
        # Save changes back to CSV
        self._save_index_to_csv()
        self.load_index()
        self.sidebar.setCurrentRow(idx)
        # Show popup and clear tag box
        QMessageBox.information(self, "Tags Updated", f"{len(new_tags)} tag(s) added.")
        self.tag_edit_box.clear()

    def remove_tags_for_selected(self):
        idx = self.sidebar.currentRow()
        if idx < 0:
            QMessageBox.information(self, "No Selection", "Please select a conversation before removing tags.")
            return
        # Find the filtered index as in load_selected_convo
        filtered_index = [row for row in self.index if not self.active_tags or self.active_tags.issubset(set(re.findall(r'#(\w+)', row['title'])))]
        filtered_index = [row for row in filtered_index if self.search_box.text().strip().lower() in f"{row['date']} - {row['title']}".lower()]
        if idx >= len(filtered_index):
            return
        meta = filtered_index[idx]
        # Get current tags
        tags_in_title = re.findall(r'#(\w+)', meta['title'])
        if not tags_in_title:
            QMessageBox.information(self, "Remove Tags", "No tags to remove for this conversation.")
            return
        # Show editable popup using QInputDialog
        tag_str = ", ".join(tags_in_title)
        new_tag_str, ok = QInputDialog.getText(self, "Remove Tags", "Edit tags (comma-separated):", text=tag_str)
        if ok:
            new_tags = [t.strip() for t in new_tag_str.split(",") if t.strip()]
            # Remove old tags from title, add new ones
            title_wo_tags = re.sub(r'#\w+', '', meta['title']).strip()
            if new_tags:
                meta['title'] = f"{title_wo_tags} " + " ".join(f"#{t}" for t in new_tags)
                msg = f"Tags updated to: {', '.join(new_tags)}"
            else:
                meta['title'] = title_wo_tags
                msg = "All tags removed."
            # Save changes back to CSV
            self._save_index_to_csv()
            self.load_index()
            self.sidebar.setCurrentRow(idx)
            QMessageBox.information(self, "Tags Updated", msg)
            self.tag_edit_box.clear()

    def save_index(self):
        with open(INDEX_CSV, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.index[0].keys())
            writer.writeheader()
            writer.writerows(self.index)

    def _save_index_to_csv(self):
        with open(INDEX_CSV, "w", encoding="utf-8", newline="") as csvfile:
            if not self.index:
                return
            writer = csv.DictWriter(csvfile, fieldnames=self.index[0].keys())
            writer.writeheader()
            for row in self.index:
                writer.writerow(row)

    def toggle_dark_mode(self):
        app = QApplication.instance()
        # Check if dark mode is currently enabled by checking the config file
        cfg_path = os.path.join(os.path.dirname(__file__), "theme.cfg")
        dark_mode = False
        if os.path.exists(cfg_path):
            with open(cfg_path, "r") as f:
                mode = f.read().strip()
                dark_mode = (mode == "dark")
        # Toggle mode
        if dark_mode:
            self.apply_light_mode()
            self.save_theme(False)
        else:
            self.apply_dark_mode()
            self.save_theme(True)

    def save_theme(self, dark: bool):
        cfg_path = os.path.join(os.path.dirname(__file__), "theme.cfg")
        with open(cfg_path, "w") as f:
            f.write("dark" if dark else "light")

    def load_theme(self):
        cfg_path = os.path.join(os.path.dirname(__file__), "theme.cfg")
        if os.path.exists(cfg_path):
            with open(cfg_path, "r") as f:
                mode = f.read().strip()
                if mode == "dark":
                    self.apply_dark_mode()
                else:
                    self.apply_light_mode()
        else:
            self.apply_light_mode()

    def apply_dark_mode(self):
        dark_stylesheet = """
            QWidget {
                background-color: #232629;
                color: #f0f0f0;
            }
            QLineEdit, QTextEdit, QTextBrowser, QComboBox, QListWidget, QDateEdit {
                background-color: #2b2b2b;
                color: #f0f0f0;
                border: 1px solid #444;
            }
            QPushButton {
                background-color: #444;
                color: #f0f0f0;
                border: 1px solid #666;
            }
            QMenuBar, QMenu {
                background-color: #232629;
                color: #f0f0f0;
            }
            QMenuBar::item {
                background: transparent;
                color: #f0f0f0;
            }
            QMenuBar::item:selected {
                background: #444;
            }
            QScrollBar:vertical, QScrollBar:horizontal {
                background: #232629;
            }
        """
        QApplication.instance().setStyleSheet(dark_stylesheet)

    def apply_light_mode(self):
        QApplication.instance().setStyleSheet("")

    def load_icon(self):
        file_dialog = QFileDialog(self)
        file_dialog.setWindowTitle("Select Icon (.ico)")
        file_dialog.setNameFilter("ICO files (*.ico)")
        file_dialog.setFileMode(QFileDialog.ExistingFile)

        if file_dialog.exec():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                src_icon_path = selected_files[0]
                dest_icon_path = os.path.join(os.path.dirname(__file__), "feralcat_icon.ico")
                try:
                    # Copy the selected icon to the project folder
                    with open(src_icon_path, "rb") as src, open(dest_icon_path, "wb") as dst:
                        dst.write(src.read())
                    icon = QIcon(dest_icon_path)
                    self.setWindowIcon(icon)
                    # Optionally set on menubar if supported
                    self.parentWidget().setWindowIcon(icon) if self.parentWidget() else None
                    QMessageBox.information(self, "Icon Loaded", "Custom icon loaded and applied.")
                except Exception as e:
                    QMessageBox.warning(self, "Error", f"Failed to load icon: {e}")

    def clear_date_filter(self):
        # Reset the date edits to today, but clear the filter by setting date_range to (None, None)
        self.start_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setDate(QDate.currentDate())
        self.date_range = (None, None)
        self.apply_filters()

    def copy_tags_to_clipboard(self):
        tags = [self.tag_search_box.itemText(i) for i in range(self.tag_search_box.count())]
        tag_str = ", ".join(tags)
        QApplication.clipboard().setText(tag_str)
        QMessageBox.information(self, "Copied", "All tags copied to clipboard.")

    def copy_tag_content(self):
        """Copy all filtered conversations' content to clipboard."""
        if not self.filtered_rows:
            QMessageBox.information(self, "No Conversations", "No conversations to copy for this tag.")
            return
        all_content = []
        for row in self.filtered_rows:
            filepath = os.path.join(EXPORT_DIR, row['filename'])
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read().strip()
                        # Optionally add a separator and title for clarity
                        all_content.append(f"## {row['date']} - {row['title']}\n\n{content}")
                except Exception:
                    continue
        if all_content:
            QApplication.clipboard().setText("\n\n---\n\n".join(all_content))
            QMessageBox.information(self, "Tag Conversations Copied", "Tag Conversations Copied")
        else:
            QMessageBox.information(self, "No Content", "No content found for the filtered conversations.")

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    viewer = FeralCatViewer()
    viewer.show()
    sys.exit(app.exec())