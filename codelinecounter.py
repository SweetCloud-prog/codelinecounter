import sys
import os
from pathlib import Path
from collections import defaultdict
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QTreeWidget, QTreeWidgetItem,
    QProgressBar, QFrame, QGraphicsDropShadowEffect, QHeaderView,
    QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal, QSize
from PySide6.QtGui import QFont, QColor, QIcon, QPalette, QLinearGradient, QPainter


# ─── Extensions supportées avec catégories ───────────────────────────────────
EXTENSIONS = {
    # Langages de programmation
    '.py': ('Python', '#3776AB'),
    '.js': ('JavaScript', '#F7DF1E'),
    '.ts': ('TypeScript', '#3178C6'),
    '.jsx': ('React JSX', '#61DAFB'),
    '.tsx': ('React TSX', '#61DAFB'),
    '.java': ('Java', '#ED8B00'),
    '.c': ('C', '#A8B9CC'),
    '.cpp': ('C++', '#00599C'),
    '.h': ('C/C++ Header', '#A8B9CC'),
    '.hpp': ('C++ Header', '#00599C'),
    '.cs': ('C#', '#239120'),
    '.go': ('Go', '#00ADD8'),
    '.rs': ('Rust', '#CE422B'),
    '.rb': ('Ruby', '#CC342D'),
    '.php': ('PHP', '#777BB4'),
    '.swift': ('Swift', '#FA7343'),
    '.kt': ('Kotlin', '#7F52FF'),
    '.scala': ('Scala', '#DC322F'),
    '.r': ('R', '#276DC3'),
    '.lua': ('Lua', '#2C2D72'),
    '.dart': ('Dart', '#0175C2'),
    '.pl': ('Perl', '#39457E'),
    '.sh': ('Shell', '#89E051'),
    '.bash': ('Bash', '#89E051'),
    '.ps1': ('PowerShell', '#012456'),
    '.bat': ('Batch', '#C1F12E'),

    # Web
    '.html': ('HTML', '#E34F26'),
    '.htm': ('HTML', '#E34F26'),
    '.css': ('CSS', '#1572B6'),
    '.scss': ('SCSS', '#CC6699'),
    '.sass': ('Sass', '#CC6699'),
    '.less': ('Less', '#1D365D'),
    '.vue': ('Vue', '#4FC08D'),
    '.svelte': ('Svelte', '#FF3E00'),

    # Data / Config
    '.json': ('JSON', '#000000'),
    '.xml': ('XML', '#FF6600'),
    '.yaml': ('YAML', '#CB171E'),
    '.yml': ('YAML', '#CB171E'),
    '.toml': ('TOML', '#9C4121'),
    '.ini': ('INI', '#6A737D'),
    '.cfg': ('Config', '#6A737D'),
    '.env': ('Env', '#ECD53F'),

    # Markdown / Docs
    '.md': ('Markdown', '#083FA1'),
    '.rst': ('reStructuredText', '#141414'),
    '.txt': ('Text', '#6A737D'),

    # SQL
    '.sql': ('SQL', '#E38C00'),

    # Autres
    '.dockerfile': ('Dockerfile', '#2496ED'),
    '.graphql': ('GraphQL', '#E10098'),
    '.proto': ('Protobuf', '#4285F4'),
}

IGNORED_DIRS = {
    'node_modules', '.git', '__pycache__', '.venv', 'venv', 'env',
    '.idea', '.vscode', 'dist', 'build', '.next', '.nuxt',
    'vendor', 'target', 'bin', 'obj', '.cache', 'coverage',
    '.tox', 'eggs', '.eggs', '*.egg-info', '.mypy_cache',
}


# ─── Thread de scan ──────────────────────────────────────────────────────────
class ScanThread(QThread):
    progress = Signal(str)          # fichier en cours
    file_found = Signal(str, str, int, int)  # chemin, ext, lignes, lignes non vides
    finished_scan = Signal(dict, dict, dict, int, int)  # résultats finaux

    def __init__(self, folder_path):
        super().__init__()
        self.folder_path = folder_path
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        lines_by_ext = defaultdict(int)
        non_empty_by_ext = defaultdict(int)
        files_by_ext = defaultdict(int)
        total_files = 0
        total_lines = 0

        for root, dirs, files in os.walk(self.folder_path):
            if self._is_cancelled:
                return

            # Filtrer les dossiers ignorés
            dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]

            for filename in files:
                if self._is_cancelled:
                    return

                filepath = os.path.join(root, filename)
                ext = Path(filename).suffix.lower()

                # Cas spécial pour Dockerfile
                if filename.lower() == 'dockerfile':
                    ext = '.dockerfile'

                if ext not in EXTENSIONS:
                    continue

                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        content_lines = f.readlines()
                        line_count = len(content_lines)
                        non_empty_count = sum(1 for line in content_lines if line.strip())

                        lines_by_ext[ext] += line_count
                        non_empty_by_ext[ext] += non_empty_count
                        files_by_ext[ext] += 1
                        total_files += 1
                        total_lines += line_count

                        rel_path = os.path.relpath(filepath, self.folder_path)
                        self.progress.emit(rel_path)
                        self.file_found.emit(rel_path, ext, line_count, non_empty_count)

                except (PermissionError, OSError):
                    continue

        self.finished_scan.emit(
            dict(lines_by_ext), dict(non_empty_by_ext),
            dict(files_by_ext), total_files, total_lines
        )


# ─── Bar chart widget custom ─────────────────────────────────────────────────
class BarChartWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.data = []  # list of (label, value, color)
        self.setMinimumHeight(200)

    def set_data(self, data):
        self.data = sorted(data, key=lambda x: x[1], reverse=True)[:15]
        self.update()

    def paintEvent(self, event):
        if not self.data:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w = self.width()
        h = self.height()
        margin_left = 120
        margin_right = 80
        margin_top = 10
        margin_bottom = 10
        bar_area_w = w - margin_left - margin_right
        bar_height = max(12, min(28, (h - margin_top - margin_bottom) // max(len(self.data), 1) - 4))
        spacing = 4

        max_val = max(d[1] for d in self.data) if self.data else 1

        for i, (label, value, color) in enumerate(self.data):
            y = margin_top + i * (bar_height + spacing)
            if y + bar_height > h:
                break

            # Label
            painter.setPen(QColor('#E0E0E0'))
            painter.setFont(QFont('Segoe UI', 9))
            painter.drawText(0, y, margin_left - 10, bar_height,
                             Qt.AlignRight | Qt.AlignVCenter, label)

            # Bar
            bar_w = int((value / max_val) * bar_area_w) if max_val > 0 else 0
            bar_w = max(bar_w, 3)

            gradient = QLinearGradient(margin_left, y, margin_left + bar_w, y)
            gradient.setColorAt(0, QColor(color))
            gradient.setColorAt(1, QColor(color).lighter(130))
            painter.setBrush(gradient)
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(margin_left, y + 2, bar_w, bar_height - 4, 4, 4)

            # Value
            painter.setPen(QColor('#B0B0B0'))
            painter.setFont(QFont('Segoe UI', 8))
            painter.drawText(margin_left + bar_w + 8, y, margin_right - 10, bar_height,
                             Qt.AlignLeft | Qt.AlignVCenter, f"{value:,}")

        painter.end()


# ─── Widget carte stat ───────────────────────────────────────────────────────
class StatCard(QFrame):
    def __init__(self, title, value="0", accent_color="#6C63FF"):
        super().__init__()
        self.setObjectName("statCard")
        self.setStyleSheet(f"""
            #statCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1E1E2E, stop:1 #2A2A3E);
                border: 1px solid {accent_color}40;
                border-radius: 12px;
                padding: 16px;
            }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setFont(QFont('Segoe UI', 9))
        title_label.setStyleSheet(f"color: {accent_color}; border: none; background: transparent;")

        self.value_label = QLabel(value)
        self.value_label.setFont(QFont('Segoe UI', 24, QFont.Bold))
        self.value_label.setStyleSheet("color: #FFFFFF; border: none; background: transparent;")

        layout.addWidget(title_label)
        layout.addWidget(self.value_label)

        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

    def set_value(self, value):
        self.value_label.setText(value)


# ─── Fenêtre principale ──────────────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("⚡ Code Line Counter")
        self.setMinimumSize(1100, 750)
        self.resize(1300, 850)
        self.scan_thread = None

        self.setup_style()
        self.setup_ui()

    def setup_style(self):
        self.setStyleSheet("""
            QMainWindow {
                background-color: #13111C;
            }
            QWidget {
                color: #E0E0E0;
                font-family: 'Segoe UI', 'Arial';
            }
            QLabel {
                background: transparent;
            }
            QPushButton#browseBtn {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6C63FF, stop:1 #A855F7);
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 28px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton#browseBtn:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #7C73FF, stop:1 #B865FF);
            }
            QPushButton#browseBtn:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #5C53EF, stop:1 #9845E7);
            }
            QPushButton#cancelBtn {
                background: #DC2626;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 28px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton#cancelBtn:hover {
                background: #EF4444;
            }
            QTreeWidget {
                background-color: #1A1825;
                border: 1px solid #2A2840;
                border-radius: 10px;
                padding: 8px;
                font-size: 12px;
                outline: none;
            }
            QTreeWidget::item {
                padding: 5px 4px;
                border-radius: 4px;
            }
            QTreeWidget::item:hover {
                background-color: #2A2845;
            }
            QTreeWidget::item:selected {
                background-color: #6C63FF30;
            }
            QHeaderView::section {
                background-color: #1E1C30;
                color: #A0A0B0;
                padding: 8px 12px;
                border: none;
                border-bottom: 2px solid #6C63FF;
                font-weight: bold;
                font-size: 11px;
            }
            QProgressBar {
                background-color: #1A1825;
                border: 1px solid #2A2840;
                border-radius: 8px;
                text-align: center;
                color: #E0E0E0;
                font-size: 11px;
                height: 20px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #6C63FF, stop:1 #A855F7);
                border-radius: 7px;
            }
            QFrame#separator {
                background-color: #2A2840;
                max-height: 1px;
            }
        """)

    def setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # ── Header ──
        header_layout = QVBoxLayout()
        header_layout.setSpacing(4)

        title = QLabel("⚡ Code Line Counter")
        title.setFont(QFont('Segoe UI', 26, QFont.Bold))
        title.setStyleSheet("color: #FFFFFF;")

        subtitle = QLabel("Analysez votre codebase en un clic — comptez chaque ligne qui compte.")
        subtitle.setFont(QFont('Segoe UI', 11))
        subtitle.setStyleSheet("color: #8888AA;")

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        main_layout.addLayout(header_layout)

        # ── Sélection dossier ──
        folder_layout = QHBoxLayout()
        folder_layout.setSpacing(12)

        self.path_label = QLabel("Aucun dossier sélectionné")
        self.path_label.setFont(QFont('Segoe UI', 11))
        self.path_label.setStyleSheet("""
            background: #1A1825;
            border: 1px solid #2A2840;
            border-radius: 10px;
            padding: 12px 16px;
            color: #8888AA;
        """)

        self.browse_btn = QPushButton("📂  Parcourir")
        self.browse_btn.setObjectName("browseBtn")
        self.browse_btn.setCursor(Qt.PointingHandCursor)
        self.browse_btn.clicked.connect(self.browse_folder)

        self.cancel_btn = QPushButton("✕  Annuler")
        self.cancel_btn.setObjectName("cancelBtn")
        self.cancel_btn.setCursor(Qt.PointingHandCursor)
        self.cancel_btn.setVisible(False)
        self.cancel_btn.clicked.connect(self.cancel_scan)

        folder_layout.addWidget(self.path_label, 1)
        folder_layout.addWidget(self.cancel_btn)
        folder_layout.addWidget(self.browse_btn)
        main_layout.addLayout(folder_layout)

        # ── Progress ──
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(22)
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setFont(QFont('Segoe UI', 9))
        self.status_label.setStyleSheet("color: #6C63FF;")
        self.status_label.setVisible(False)
        main_layout.addWidget(self.status_label)

        # ── Stat cards ──
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        self.card_total_lines = StatCard("TOTAL LIGNES", "—", "#6C63FF")
        self.card_code_lines = StatCard("LIGNES DE CODE", "—", "#10B981")
        self.card_files = StatCard("FICHIERS", "—", "#F59E0B")
        self.card_languages = StatCard("LANGAGES", "—", "#EC4899")

        cards_layout.addWidget(self.card_total_lines)
        cards_layout.addWidget(self.card_code_lines)
        cards_layout.addWidget(self.card_files)
        cards_layout.addWidget(self.card_languages)
        main_layout.addLayout(cards_layout)

        # ── Splitter : tableau + graphique ──
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background: #2A2840;
                width: 2px;
                margin: 0 8px;
            }
        """)

        # Tableau récap par langage
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        summary_title = QLabel("📊  Résumé par langage")
        summary_title.setFont(QFont('Segoe UI', 13, QFont.Bold))
        left_layout.addWidget(summary_title)

        self.summary_tree = QTreeWidget()
        self.summary_tree.setHeaderLabels(["Langage", "Fichiers", "Total lignes", "Lignes de code", "% du total"])
        self.summary_tree.setRootIsDecorated(False)
        self.summary_tree.setAlternatingRowColors(False)
        header = self.summary_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 5):
            header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        left_layout.addWidget(self.summary_tree)

        # Graphique
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(8)

        chart_title = QLabel("📈  Répartition visuelle")
        chart_title.setFont(QFont('Segoe UI', 13, QFont.Bold))
        right_layout.addWidget(chart_title)

        self.chart = BarChartWidget()
        self.chart.setStyleSheet("""
            background: #1A1825;
            border: 1px solid #2A2840;
            border-radius: 10px;
        """)
        right_layout.addWidget(self.chart)

        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setSizes([600, 500])
        main_layout.addWidget(splitter, 1)

        # ── Arbre des fichiers ──
        files_title = QLabel("📁  Détail des fichiers")
        files_title.setFont(QFont('Segoe UI', 13, QFont.Bold))
        main_layout.addWidget(files_title)

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["Fichier", "Langage", "Total lignes", "Lignes de code"])
        self.file_tree.setRootIsDecorated(False)
        self.file_tree.setMaximumHeight(250)
        file_header = self.file_tree.header()
        file_header.setStretchLastSection(False)
        file_header.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, 4):
            file_header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        main_layout.addWidget(self.file_tree)

    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Sélectionner un dossier de code",
            os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        if folder:
            self.start_scan(folder)

    def start_scan(self, folder):
        self.path_label.setText(f"📂  {folder}")
        self.path_label.setStyleSheet("""
            background: #1A1825;
            border: 1px solid #6C63FF50;
            border-radius: 10px;
            padding: 12px 16px;
            color: #E0E0E0;
        """)

        # Reset UI
        self.summary_tree.clear()
        self.file_tree.clear()
        self.card_total_lines.set_value("...")
        self.card_code_lines.set_value("...")
        self.card_files.set_value("...")
        self.card_languages.set_value("...")
        self.chart.set_data([])

        self.progress_bar.setVisible(True)
        self.status_label.setVisible(True)
        self.cancel_btn.setVisible(True)
        self.browse_btn.setEnabled(False)

        self.scan_thread = ScanThread(folder)
        self.scan_thread.progress.connect(self.on_progress)
        self.scan_thread.file_found.connect(self.on_file_found)
        self.scan_thread.finished_scan.connect(self.on_scan_finished)
        self.scan_thread.start()

    def cancel_scan(self):
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.cancel()
            self.scan_thread.wait()
        self.progress_bar.setVisible(False)
        self.status_label.setText("❌ Scan annulé")
        self.cancel_btn.setVisible(False)
        self.browse_btn.setEnabled(True)

    def on_progress(self, filepath):
        self.status_label.setText(f"🔍  {filepath}")

    def on_file_found(self, filepath, ext, lines, non_empty):
        lang_name, color = EXTENSIONS.get(ext, ('Unknown', '#888888'))
        item = QTreeWidgetItem([filepath, lang_name, f"{lines:,}", f"{non_empty:,}"])
        item.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
        item.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)
        item.setForeground(1, QColor(color))
        self.file_tree.addTopLevelItem(item)

    def on_scan_finished(self, lines_by_ext, non_empty_by_ext, files_by_ext, total_files, total_lines):
        self.progress_bar.setVisible(False)
        self.cancel_btn.setVisible(False)
        self.browse_btn.setEnabled(True)

        total_non_empty = sum(non_empty_by_ext.values())
        num_languages = len(lines_by_ext)

        self.card_total_lines.set_value(f"{total_lines:,}")
        self.card_code_lines.set_value(f"{total_non_empty:,}")
        self.card_files.set_value(f"{total_files:,}")
        self.card_languages.set_value(str(num_languages))

        self.status_label.setText(f"✅  Scan terminé — {total_files:,} fichiers analysés")
        self.status_label.setStyleSheet("color: #10B981;")

        # Remplir le résumé
        chart_data = []
        for ext in sorted(lines_by_ext, key=lambda e: lines_by_ext[e], reverse=True):
            lang_name, color = EXTENSIONS.get(ext, ('Unknown', '#888888'))
            lines = lines_by_ext[ext]
            non_empty = non_empty_by_ext[ext]
            files = files_by_ext[ext]
            pct = (lines / total_lines * 100) if total_lines > 0 else 0

            item = QTreeWidgetItem([
                f"  {lang_name}",
                f"{files:,}",
                f"{lines:,}",
                f"{non_empty:,}",
                f"{pct:.1f}%"
            ])
            item.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
            item.setTextAlignment(2, Qt.AlignRight | Qt.AlignVCenter)
            item.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)
            item.setTextAlignment(4, Qt.AlignRight | Qt.AlignVCenter)
            item.setForeground(0, QColor(color))
            self.summary_tree.addTopLevelItem(item)

            chart_data.append((lang_name, lines, color))

        self.chart.set_data(chart_data)

    def closeEvent(self, event):
        if self.scan_thread and self.scan_thread.isRunning():
            self.scan_thread.cancel()
            self.scan_thread.wait()
        event.accept()


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Dark palette globale
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#13111C"))
    palette.setColor(QPalette.WindowText, QColor("#E0E0E0"))
    palette.setColor(QPalette.Base, QColor("#1A1825"))
    palette.setColor(QPalette.AlternateBase, QColor("#1E1C30"))
    palette.setColor(QPalette.Text, QColor("#E0E0E0"))
    palette.setColor(QPalette.Button, QColor("#1E1C30"))
    palette.setColor(QPalette.ButtonText, QColor("#E0E0E0"))
    palette.setColor(QPalette.Highlight, QColor("#6C63FF"))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
