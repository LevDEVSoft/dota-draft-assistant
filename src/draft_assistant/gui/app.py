"""PySide6 application entry point."""
import sys
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication,QCheckBox,QComboBox,QFrame,QHBoxLayout,QLabel,QLineEdit,QListWidget,QMainWindow,QPushButton,QVBoxLayout,QWidget
from .state import DraftState
from draft_assistant.cli import format_explanation

class Window(QMainWindow):
 def __init__(self):
  super().__init__(); self.state=DraftState(); self.setWindowTitle("Dota Draft Assistant"); self.resize(620,650); self.setFont(QFont("Segoe UI", 10)); self.setStyleSheet("QWidget{background:#171a20;color:#e7eaf0} QLineEdit,QComboBox,QListWidget{background:#232832;border:1px solid #3b4352;border-radius:5px;padding:6px} QPushButton{background:#303846;border:0;border-radius:5px;padding:7px}")
  root=QWidget(); self.setCentralWidget(root); box=QVBoxLayout(root); top=QHBoxLayout(); box.addLayout(top)
  top.addWidget(QLabel("Dota Draft Assistant")); self.role=QComboBox(); self.role.addItems(["carry","mid","offlane","support","hard_support"]); self.mode=QComboBox(); self.mode.addItems(["manual","stats","hybrid"]); self.mode.setCurrentText("hybrid"); self.count=QComboBox(); self.count.addItems(["3","5","10"]); self.count.setCurrentText("5"); self.pin=QCheckBox("Always on top"); [top.addWidget(x) for x in (self.role,self.mode,self.count,self.pin)]
  self.enemy=self.section(box,"Enemy heroes","enemy"); self.ally=self.section(box,"Allied heroes","ally"); box.addWidget(QLabel("Recommendations")); self.recs=QListWidget(); box.addWidget(self.recs); actions=QHBoxLayout(); self.explain=QPushButton("Explain selected"); clear=QPushButton("Clear draft"); save=QPushButton("Save draft"); [actions.addWidget(x) for x in (self.explain,clear,save)]; box.addLayout(actions); self.detail=QLabel(); self.detail.setWordWrap(True); self.detail.setFrameShape(QFrame.Shape.StyledPanel); box.addWidget(self.detail); self.status=QLabel(); box.addWidget(self.status)
  self.role.currentTextChanged.connect(self.refresh); self.mode.currentTextChanged.connect(self.refresh); self.count.currentTextChanged.connect(self.refresh); self.pin.toggled.connect(lambda x:self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint,x) or self.show()); clear.clicked.connect(lambda:self.state.clear() or self.refresh()); self.explain.clicked.connect(self.show_explain); self.recs.itemSelectionChanged.connect(self.show_explain); self.refresh()
 def section(self,box,title,side):
  box.addWidget(QLabel(title)); row=QHBoxLayout(); inp=QLineEdit(); inp.setPlaceholderText("Type hero alias, press Enter"); chips=QLabel(); row.addWidget(inp); row.addWidget(chips); box.addLayout(row)
  def add():
   try:self.state.add(inp.text(),side); inp.clear(); self.refresh()
   except ValueError as e:self.status.setText(str(e))
  inp.returnPressed.connect(add); setattr(self,side+"chips",chips); return inp
 def refresh(self):
  self.state.role=self.role.currentText(); self.state.mode=self.mode.currentText(); self.state.top=int(self.count.currentText()); r=self.state.recommendations(); self.recs.clear(); [self.recs.addItem(f"#{i}  {x.hero.display_name:<20} {x.score:+.2f}") for i,x in enumerate(r,1)]; self.current=r; self.enemychips.setText("  ".join(self.state.enemies)); self.allychips.setText("  ".join(self.state.allies)); self.status.setText(f"{len(self.state.heroes)} heroes · {self.state.mode} · local snapshots only")
 def show_explain(self):
  if self.recs.currentRow()>=0:self.detail.setText(format_explanation(self.current[self.recs.currentRow()],self.state.heroes))
def main():
 app=QApplication(sys.argv); w=Window(); w.show(); return app.exec()
if __name__=="__main__": raise SystemExit(main())
