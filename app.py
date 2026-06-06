import os
import sys
import ctypes
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QListWidget, QPushButton, QLineEdit, QLabel, QMessageBox, 
    QSplitter, QComboBox, QTextBrowser
)
from PyQt6.QtGui import *
from PyQt6.QtCore import *

# Storage Paths Setup
PROMPTS_DIR = os.path.join(os.getcwd(), "prompts")
INJECTIONS_DIR = os.path.join(os.getcwd(), "injections")
os.makedirs(PROMPTS_DIR, exist_ok=True)
os.makedirs(INJECTIONS_DIR, exist_ok=True)


class AdvancedPromptHighlighter(QSyntaxHighlighter):
    """Parses structural nodes and dynamically mutes marked implemented code blocks."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rules = []

        # Color Formats Definition
        dodger_blue = QTextCharFormat()
        dodger_blue.setForeground(QColor("#1e90ff"))
        dodger_blue.setFontWeight(QFont.Weight.Bold)

        muted_gray = QTextCharFormat()
        muted_gray.setForeground(QColor("#555555")) # Faded text

        # Syntax Token Matching Rules
        self.rules.append((QRegularExpression(r"(\s|^)-{2,}.*"), dodger_blue))  # -- Token rules
        self.rules.append((QRegularExpression(r"(\s|^)-{1}\s.*"), dodger_blue)) # - Bullet rules
        self.rules.append((QRegularExpression(r"={3,}"), dodger_blue))          # === Day Dividers

        # Implemented state rule: captures everything bounded by target comments
        self.done_start_regex = QRegularExpression(r"--\s*Done")
        self.done_end_regex = QRegularExpression(r"--\s*Done")
        self.muted_format = muted_gray

    def highlightBlock(self, text):
        # 1. Base syntax highlights
        for expression, char_format in self.rules:
            iterator = expression.globalMatch(text)
            while iterator.hasNext():
                match = iterator.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), char_format)

        # 2. Multi-block states to mute finalized texts
        self.setCurrentBlockState(0)
        startIndex = 0
        if self.previousBlockState() == 1:
            startIndex = 0
        else:
            match = self.done_start_regex.match(text)
            startIndex = match.capturedEnd() if match.hasMatch() else -1

        while startIndex >= 0:
            match = self.done_end_regex.match(text, startIndex)
            endIndex = match.capturedStart() if match.hasMatch() else -1

            if endIndex == -1:
                self.setCurrentBlockState(1)
                self.setFormat(startIndex, len(text) - startIndex, self.muted_format)
                break
            else:
                self.setFormat(startIndex, endIndex - startIndex, self.muted_format)
                startIndex = endIndex + match.capturedLength()
                match = self.done_start_regex.match(text, startIndex)
                startIndex = match.capturedEnd() if match.hasMatch() else -1


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.code_editor = editor

    def sizeHint(self):
        return QSize(self.code_editor.line_number_area_width(), 0)

    def paintEvent(self, event):
        self.code_editor.line_number_area_paint_event(event)


class PromptCodeEditor(QTextEdit):
    """Custom Monospace Editor with Gutter Lines and Smart Drag Selections."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.line_number_area = LineNumberArea(self)

        self.document().blockCountChanged.connect(self.update_line_number_area_width)
        self.verticalScrollBar().valueChanged.connect(self.update_line_number_area)
        self.cursorPositionChanged.connect(self.update_line_number_area)
        self.update_line_number_area_width()

        self.setFont(QFont("Consolas", 11) if sys.platform == "win32" else QFont("Monospace", 11))
        self.setAcceptRichText(False)

    def line_number_area_width(self):
        digits = 1
        max_blocks = max(1, self.document().blockCount())
        while max_blocks >= 10:
            max_blocks /= 10
            digits += 1
        return 18 + self.fontMetrics().horizontalAdvance('9') * digits

    def update_line_number_area_width(self):
        self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

    def update_line_number_area(self):
        self.line_number_area.update()
        rect = self.contentsRect()
        self.line_number_area.setGeometry(QRect(rect.left(), rect.top(), self.line_number_area_width(), rect.height()))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_line_number_area()

    def line_number_area_paint_event(self, event):
        painter = QPainter(self.line_number_area)
        painter.fillRect(event.rect(), QColor("#1e1e1e"))

        cursor = self.cursorForPosition(QPoint(0, 0))
        block = cursor.block()
        top = int(self.document().documentLayout().blockBoundingRect(block).top() - self.verticalScrollBar().value())
        bottom = top + int(self.document().documentLayout().blockBoundingRect(block).height())

        font_metrics = self.fontMetrics()
        painter.setPen(QColor("#71717a"))
        painter.setFont(self.font())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block.blockNumber() + 1)
                painter.drawText(0, top, self.line_number_area_width() - 8, font_metrics.height(),
                                 Qt.AlignmentFlag.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.document().documentLayout().blockBoundingRect(block).height())


class Prompteen(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_file = None
        self.init_ui()
        self.load_prompt_list()
        self.load_active_injection()

    def init_ui(self):
        self.setWindowTitle("Prompteen — Advanced Prompts Studio *V1.1-Beta (AFL) QStudios-Product")
        self.setGeometry(30, 30, 982, 550)
        self.setWindowIcon(QIcon('icon.ico'))

        # Style Engine Configuration
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; }
            QLabel { 
                color: #bbbbbb; font-family: 'Segoe UI', sans-serif; font-size: 11px; 
                text-transform: uppercase; font-weight: bold; letter-spacing: 0.6px; padding-bottom: 2px;
            }
            QLineEdit, QTextEdit, QListWidget, QComboBox { 
                background-color: #252526; color: #cccccc; border: 1px solid #3c3c3c; 
                border-radius: 0px; padding: 6px; font-family: 'Segoe UI', sans-serif;
            }
            QLineEdit:focus, QTextEdit:focus, QComboBox:focus { border: 1px solid #1e90ff; }
            QListWidget::item { padding: 6px 10px; color: #cccccc; }
            QListWidget::item:hover { background-color: #2a2d2e; }
            QListWidget::item:selected { background-color: #37373d; color: #ffffff; border-left: 2px solid #1e90ff; }
            
            QPushButton { 
                background-color: #333333; color: #cccccc; border: 1px solid #444444; 
                border-radius: 0px; padding: 6px 12px; font-family: 'Segoe UI', sans-serif; font-size: 12px;
            }
            QPushButton:hover { background-color: #444444; color: #ffffff; }
            QPushButton#actionBtn { background-color: #0e639c; color: #ffffff; border: 1px solid #1177bb; }
            QPushButton#actionBtn:hover { background-color: #1177bb; }
            
            QPushButton#toolBtn { 
                background-color: #252526; color: #1e90ff; border: 1px solid #3c3c3c; 
                text-align: left; padding: 8px; font-family: 'Segoe UI', sans-serif; font-size: 11px;
            }
            QPushButton#toolBtn:hover { background-color: #2d2d30; color: #63b3ff; border: 1px solid #1e90ff; }
            QSplitter::handle { background-color: #1e1e1e; }
            QSplitter::handle:hover { background-color: #1e90ff; }
            QMessageBox {
                background-color: #1e1e1e;
            }
            QStatusBar { color: dodgerblue; }
        """)

        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(5)

        # ================= PANE 1: LEFT EXPLORER BAR =================
        left_pane = QWidget()
        left_layout = QVBoxLayout(left_pane)
        left_layout.setContentsMargins(0, 0, 5, 0)
        left_layout.setSpacing(8)

        left_layout.addWidget(QLabel("EXPLORER: PROMPTS"))
        self.prompt_list = QListWidget()
        self.prompt_list.itemClicked.connect(self.load_prompt)
        left_layout.addWidget(self.prompt_list)
        
        self.delete_btn = QPushButton("Delete File")
        self.delete_btn.clicked.connect(self.delete_prompt)
        left_layout.addWidget(self.delete_btn)

        # ================= PANE 2: CENTER WORKSPACE =================
        center_pane = QWidget()
        center_layout = QVBoxLayout(center_pane)
        center_layout.setContentsMargins(5, 0, 5, 0)
        center_layout.setSpacing(8)
        
        center_layout.addWidget(QLabel("PROMPT TITLE"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Enter file template identification handle...")
        center_layout.addWidget(self.name_input)
        
        center_layout.addWidget(QLabel("WORKSPACE CONSOLE (Drag over lines to select for Smart Copy)"))
        self.editor = PromptCodeEditor()
        self.editor.setPlaceholderText("// Write prompts here.\n-- Target Module\n - subtask feature\n===\nUse {{inject}} anywhere to map active footers.")
        center_layout.addWidget(self.editor)
        
        self.highlighter = AdvancedPromptHighlighter(self.editor.document())

        # Control panel layout
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        
        self.clear_btn = QPushButton("Clear View *(Ctrl+L)")
        self.clear_btn.clicked.connect(self.clear_editor)
        btn_layout.addWidget(self.clear_btn)

        self.save_btn = QPushButton("Save Prompt *(Ctrl+S)")
        self.save_btn.clicked.connect(self.save_prompt)
        btn_layout.addWidget(self.save_btn)
        
        self.copy_btn = QPushButton("Smart Copy *(Ctrl+C)")
        self.copy_btn.setObjectName("actionBtn")
        self.copy_btn.clicked.connect(self.smart_copy_to_clipboard)
        btn_layout.addWidget(self.copy_btn)

        self.apply_btn = QPushButton("Apply Injections *(Ctrl+M)")
        self.apply_btn.setObjectName("actionBtn")
        self.apply_btn.clicked.connect(self.apply_inject)
        btn_layout.addWidget(self.apply_btn)
        
        btn_layout.addStretch()
        center_layout.addLayout(btn_layout)

        # ================= PANE 3: RIGHT SYSTEM TOOLBOX =================
        right_pane = QWidget()
        right_layout = QVBoxLayout(right_pane)
        right_layout.setContentsMargins(5, 0, 0, 0)
        right_layout.setSpacing(8)

        right_layout.addWidget(QLabel("MUTE / IMPLEMENTATION ACTION"))
        self.mute_btn = QPushButton("Mark Done *(Ctrl+G)")
        self.mute_btn.setObjectName("toolBtn")
        self.mute_btn.clicked.connect(self.toggle_implemented_markup)
        right_layout.addWidget(self.mute_btn)

        right_layout.addWidget(QLabel("FAST STRUCTURAL SYNTAX"))
        
        self.mk_dash = QPushButton("-- Task *(Ctrl+H)")
        self.mk_dash.setObjectName("toolBtn")
        self.mk_dash.clicked.connect(lambda: self.insert_syntax("-- "))
        right_layout.addWidget(self.mk_dash)

        self.mk_bullet = QPushButton("- Subtask *(Ctrl+J)")
        self.mk_bullet.setObjectName("toolBtn")
        self.mk_bullet.clicked.connect(lambda: self.insert_syntax("\n\t- "))
        right_layout.addWidget(self.mk_bullet)

        self.mk_div = QPushButton("=== Split *(Ctrl+K)")
        self.mk_div.setObjectName("toolBtn")
        self.mk_div.clicked.connect(lambda: self.insert_syntax("\n===================================================\n\n"))
        right_layout.addWidget(self.mk_div)

        # Permanent separation line boundary
        right_layout.addSpacing(10)
        right_layout.addWidget(QLabel("ACTIVE STORAGE INJECTIONS"))

        self.injection_selector = QComboBox()
        self.injection_selector.addItems([f"Injection Slot {i}" for i in range(1, 6)])
        self.injection_selector.currentIndexChanged.connect(self.load_active_injection)
        right_layout.addWidget(self.injection_selector)

        right_layout.addWidget(QLabel("EDIT INJECTION CONTENT"))
        self.injection_editor = QTextEdit()
        self.injection_editor.setPlaceholderText("e.g., Make this code smarter, and error free")
        self.injection_editor.textChanged.connect(self.save_active_injection)
        right_layout.addWidget(self.injection_editor)

        # Build Pane Structures
        splitter.addWidget(left_pane)
        splitter.addWidget(center_pane)
        splitter.addWidget(right_pane)
        
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 4)
        splitter.setStretchFactor(2, 1)
        splitter.setSizes([180, 800, 260])

        main_layout.addWidget(splitter)
        self.setCentralWidget(central_widget)

        # Global Hotkeys Settings Map
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_prompt)
        QShortcut(QKeySequence("Ctrl+I"), self, self.injection_point)
        QShortcut(QKeySequence("Ctrl+T"), self, self.smart_copy_to_clipboard)
        QShortcut(QKeySequence("Ctrl+D"), self, self.delete_prompt)
        QShortcut(QKeySequence("Ctrl+M"), self, self.apply_inject)
        QShortcut(QKeySequence("Ctrl+G"), self, self.toggle_implemented_markup)
        QShortcut(QKeySequence("Ctrl+H"), self, self.fh1)
        QShortcut(QKeySequence("Ctrl+J"), self, self.fh2)
        QShortcut(QKeySequence("Ctrl+K"), self, self.fh3)
        QShortcut(QKeySequence("Ctrl+L"), self, self.clear_editor)
        # QShortcut(QKeySequence("Ctrl+Q"), self, self.)

    def fh1(self): self.insert_syntax("-- ")
    def fh2(self): self.insert_syntax("\n\t- ")
    def fh3(self): self.insert_syntax("\n===================================================\n\n")
    # --- Core Mechanics Engine ---
    def insert_syntax(self, val):
        cursor = self.editor.textCursor()
        cursor.insertText(val)
        self.editor.setFocus()

    def toggle_implemented_markup(self):
        """Wraps selected lines inside block tags to toggle grey/muted visibility status."""
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            QMessageBox.critical(self, "Selection Required", "Highlight a section to flag as implemented.")
            return

        selected_text = cursor.selectedText()
        
        # Clean clean reversal check if block is already isolated by done markers
        if selected_text.startswith("-- Done\n") and selected_text.endswith("\n-- Done"):
            # Strip tags to restore active style states
            inner_content = selected_text[8:-8]
            cursor.insertText(inner_content)
        else:
            # Inject Done borders
            cursor.beginEditBlock()
            cursor.insertText(f"-- Done\n{selected_text}\n-- Done")
            cursor.endEditBlock()

    def smart_copy_to_clipboard(self):
        """Copies targeted content block and dynamic template variables to clipboard layout."""
        cursor = self.editor.textCursor()
        
        # Pull highlighted segment, or fallback to the complete layout scope
        raw_text = cursor.selectedText() if cursor.hasSelection() else self.editor.toPlainText()
        raw_text = raw_text.replace('\u2029', '\n') # Clean line boundary conversions
        
        injection_text = self.injection_editor.toPlainText().strip()
        
        # Explicit template injection formatting lookup engine replacement
        if "{{inject}}" in raw_text:
            processed_text = raw_text.replace("{{inject}}", injection_text)
        else:
            # Append seamlessly to root baseline text configuration if variable wasn't manually typed
            processed_text = f"{raw_text}\n\n{injection_text}" if injection_text else raw_text

        if processed_text.strip():
            QApplication.clipboard().setText(processed_text)
            self.statusBar().showMessage("✓ Clipboard populated (Injections processing complete)", 2500)

    def apply_inject(self):
        """Copies targeted content block and dynamic template variables to clipboard layout."""
        cursor = self.editor.textCursor()
        
        # Pull highlighted segment, or fallback to the complete layout scope
        raw_text = self.editor.toPlainText()
        raw_text = raw_text.replace('\u2029', '\n') # Clean line boundary conversions
        
        injection_text = self.injection_editor.toPlainText().strip()
        
        # Explicit template injection formatting lookup engine replacement
        if "{{inject}}" in raw_text:
            processed_text = raw_text.replace("{{inject}}", injection_text)
        else:
            # Append seamlessly to root baseline text configuration if variable wasn't manually typed
            processed_text = f"{raw_text}\n\n{injection_text}" if injection_text else raw_text

        if processed_text.strip():
           self.editor.clear()
           self.insert_syntax(processed_text)


    # --- File/IO Subsystems Storage Management ---

    def get_injection_path(self):
        slot = self.injection_selector.currentIndex() + 1
        return os.path.join(INJECTIONS_DIR, f"{slot}.inject")

    def load_active_injection(self):
        self.injection_editor.blockSignals(True)
        path = self.get_injection_path()
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                self.injection_editor.setPlainText(f.read())
        else:
            self.injection_editor.clear()
        self.injection_editor.blockSignals(False)

    def save_active_injection(self):
        path = self.get_injection_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.injection_editor.toPlainText())
        except Exception as e:
            print(f"Error saving injection mapping: {e}")

    def load_prompt_list(self):
        self.prompt_list.clear()
        if os.path.exists(PROMPTS_DIR):
            files = [f for f in os.listdir(PROMPTS_DIR) if f.endswith(".prompt")]
            self.prompt_list.addItems([os.path.splitext(f)[0] for f in files])

    def injection_point(self):
        self.insert_syntax(' {{inject}} ')

    def save_prompt(self):
        title = self.name_input.text().strip()
        content = self.editor.toPlainText()
        if not title:
            QMessageBox.warning(self, "Title Incomplete", "Please assign file tracking label to configuration.")
            return

        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '_', '-')).rstrip()
        filename = f"{safe_title}.prompt"
        file_path = os.path.join(PROMPTS_DIR, filename)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            self.current_file = filename
            self.load_prompt_list()
            self.statusBar().showMessage(f"✓ Config Synchronized: prompts/{filename}", 3000)
        except Exception as e:
            QMessageBox.critical(self, "System Write Halt", f"Transaction interrupted: {e}")

    def load_prompt(self, item):
        filename = f"{item.text()}.prompt"
        file_path = os.path.join(PROMPTS_DIR, filename)
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                self.name_input.setText(item.text())
                self.editor.setPlainText(content)
                self.current_file = filename
            except Exception as e:
                QMessageBox.critical(self, "IO Error", f"Access Denied: {e}")

    def delete_prompt(self):
        selected_item = self.prompt_list.currentItem()
        if not selected_item:
            return
        filename = f"{selected_item.text()}.prompt"
        file_path = os.path.join(PROMPTS_DIR, filename)
        
        reply = QMessageBox.question(self, "Confirm action", f"Delete '{selected_item.text()}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.remove(file_path)
                self.clear_editor()
                self.load_prompt_list()
                self.statusBar().showMessage("File unlinked.", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to drop node: {e}")

    def clear_editor(self):
        self.name_input.clear()
        self.editor.clear()
        self.current_file = None
        self.prompt_list.clearSelection()


if __name__ == "__main__":
    # --- Windows Administrator Elevation Check ---
    if sys.platform == "win32":
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except:
            is_admin = False

        if not is_admin:
            # Re-run the program with admin rights. 
            # 'runas' triggers the Windows UAC prompt.
            print("Requesting administrator privileges...")
            try:
                ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", sys.executable, " ".join(sys.argv), None, 1
                )
            except Exception as e:
                print(f"Failed to elevate privileges: {e}")
            sys.exit(0)  # Exit the current non-admin process safely

    # --- Standard Application Startup ---
    app = QApplication(sys.argv)
    window = Prompteen()
    window.show()
    sys.exit(app.exec())