"""Star Wars–inspired holographic theme — rounded edges everywhere."""

APP_STYLESHEET = """
QWidget {
    background-color: #0b0e0c;
    color: #e0e0e0;
    font-family: "Segoe UI", "Cascadia Code", "Consolas", sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #0b0e0c;
}

QLabel#brandTitle {
    font-size: 20px;
    font-weight: 900;
    color: #f2c94c;
    letter-spacing: 3px;
}

QLabel#brandTag {
    font-size: 11px;
    font-weight: 700;
    color: #3ddc84;
    letter-spacing: 1px;
}

QLabel#statusLive {
    font-size: 12px;
    font-weight: 800;
    color: #4ade80;
    letter-spacing: 1px;
}

QLabel#sectionTitle {
    font-size: 12px;
    font-weight: 900;
    color: #3ddc84;
    letter-spacing: 2px;
}

QLabel#metricHero {
    font-size: 24px;
    font-weight: 900;
    color: #f2c94c;
}

QLabel#metricHeroAccent {
    font-size: 24px;
    font-weight: 900;
    color: #3ddc84;
}

QLabel#metricSecondary {
    font-size: 11px;
    color: #7f9c8b;
}

QLabel#metricInline {
    font-size: 13px;
    color: #c9efd9;
}

QLabel#controlLabel {
    font-size: 11px;
    font-weight: 800;
    color: #3ddc84;
    letter-spacing: 1px;
}

QFrame#headerBar {
    background-color: rgba(0, 20, 40, 180);
    border: 1px solid #225c3d;
    border-bottom: 2px solid #3ddc84;
    border-radius: 8px;
}

QFrame#panel, QFrame#panelCool {
    background-color: #141816;
    border: 1px solid #2d332e;
    border-radius: 12px;
}

QProgressBar {
    background-color: #0a1c12;
    border: 1px solid #2d332e;
    border-radius: 6px;
    text-align: center;
    color: #e2f2e8;
    min-height: 14px;
    max-height: 14px;
}

QProgressBar::chunk {
    background-color: #f2c94c;
    border-radius: 6px;
}

QProgressBar#cool::chunk {
    background-color: #3ddc84;
}

QProgressBar#warn::chunk {
    background-color: #ff9f1a;
}

QProgressBar#crit::chunk {
    background-color: #ff2a2a;
}

QSlider#scanSlider::groove:horizontal {
    border: 1px solid #2d332e;
    height: 8px;
    background: #0a1c12;
    border-radius: 4px;
}

QSlider#scanSlider::handle:horizontal {
    background: #f2c94c;
    border: 1px solid #f2c94c;
    width: 16px;
    margin: -4px 0;
    border-radius: 8px;
}

QSlider#scanSlider::sub-page:horizontal {
    background: #3ddc84;
    border: 1px solid #2d332e;
    border-radius: 4px;
}

QSpinBox#scanSpin {
    background-color: #1c211e;
    border: 1px solid #3ddc84;
    color: #3ddc84;
    font-weight: 800;
    padding: 4px 8px;
    min-width: 100px;
    font-size: 12px;
    border-radius: 6px;
}

QSpinBox#scanSpin::up-button, QSpinBox#scanSpin::down-button {
    background: #0a2236;
    border-left: 1px solid #225c3d;
    width: 20px;
    border-radius: 6px;
}

QTableWidget {
    background-color: #141816;
    alternate-background-color: #161a18;
    gridline-color: transparent;
    border: 1px solid #2d332e;
    border-radius: 8px;
    selection-background-color: #202522;
    selection-color: #f2c94c;
}

QHeaderView::section {
    background-color: #161a18;
    color: #3ddc84;
    padding: 6px 10px;
    border: none;
    border-bottom: 1px solid #2d332e;
    font-size: 11px;
    font-weight: 900;
    letter-spacing: 1px;
}

QScrollBar:vertical, QScrollBar:horizontal {
    width: 10px;
    height: 10px;
    background: #0b0e0c;
}

QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #2d332e;
    border-radius: 5px;
}

QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background: #3ddc84;
}

QPushButton#micButton {
    background-color: #1c211e;
    border: 1px solid #3ddc84;
    color: #3ddc84;
    font-weight: 900;
    letter-spacing: 1px;
    padding: 8px 16px;
    min-width: 150px;
    font-size: 13px;
    border-radius: 8px;
}

QPushButton#micButton:hover {
    background-color: #212623;
    border-color: #f2c94c;
    color: #f2c94c;
}

QPushButton#micButton:pressed {
    background-color: #122a40;
}

#chatPanel {
    background-color: #0b0e0c;
    border: 1px solid #2d332e;
    border-radius: 12px;
}

#chatHeader {
    background-color: #141816;
    border-bottom: 1px solid #2d332e;
    border-radius: 12px 12px 0 0;
    padding: 12px;
}

#chatControlLabel {
    color: #3ddc84;
    font-weight: 900;
    font-size: 11px;
    letter-spacing: 1px;
    background-color: #141816;
    border: none;
    padding: 4px 2px;
}

#chatStatus {
    color: #4ade80;
    font-weight: 800;
    font-size: 12px;
}

#chatStatus[state="offline"] {
    color: #ff2a2a;
    font-weight: 800;
    font-size: 12px;
}

#chatStatus[state="loading"] {
    color: #f2c94c;
    font-weight: 800;
    font-size: 12px;
}

#chatMemLabel {
    color: #7f9c8b;
    font-size: 12px;
}

#chatScroll {
    background-color: #0b0e0c;
    border: none;
}

#messageBubble {
    background-color: transparent;
    border: none;
}

#messageBubble[temporary="true"] {
    color: #8e8e8e;
}

#messageRole {
    color: #3ddc84;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
    padding-bottom: 4px;
}

#messageContent {
    color: #e0e0e0;
    font-size: 14px;
    line-height: 1.5;
    background-color: transparent;
    border: none;
    font-family: "Cascadia Code", "Consolas", monospace;
}

#userBubble {
    background-color: #1c211e;
    border: 1px solid #2d332e;
    border-radius: 10px;
    border-bottom-right-radius: 3px;
}

#assistantBubble {
    background-color: #141816;
    border: 1px solid #2d332e;
    border-radius: 10px;
    border-bottom-left-radius: 3px;
}

#chatInputFrame {
    background-color: #141816;
    border-top: 1px solid #2d332e;
    padding: 14px;
    border-radius: 0 0 12px 12px;
}

#chatInput {
    background-color: #1c211e;
    border: 1px solid #2d332e;
    color: #e0e0e0;
    padding: 12px 18px;
    font-size: 14px;
    font-family: "Cascadia Code", "Consolas", monospace;
    border-radius: 8px;
    min-height: 40px;
}

#chatInput:focus {
    border-color: #3ddc84;
}

#chatSendButton {
    background-color: #1c211e;
    border: 1px solid #3ddc84;
    color: #3ddc84;
    font-weight: 900;
    letter-spacing: 1px;
    padding: 10px 22px;
    min-width: 95px;
    font-size: 13px;
    border-radius: 8px;
}

#chatSendButton:hover {
    background-color: #212623;
    border-color: #f2c94c;
    color: #f2c94c;
}

#chatSendButton:disabled {
    background-color: #161a18;
    border-color: #3a3a3a;
    color: #7f9c8b;
}

#chatStopButton {
    background-color: #2d1b1b;
    border: 1px solid #ff2a2a;
    color: #ff2a2a;
    font-weight: 900;
    letter-spacing: 1px;
    padding: 10px 22px;
    min-width: 95px;
    font-size: 13px;
    border-radius: 8px;
}

#chatStopButton:hover {
    background-color: #3a2525;
    border-color: #ff9f1a;
    color: #ff9f1a;
}

#chatStopButton:disabled {
    background-color: #161a18;
    border-color: #3a3a3a;
    color: #7f9c8b;
}

#chatLoadButton {
    background-color: #1c211e;
    border: 1px solid #2d332e;
    color: #e0e0e0;
    font-weight: 900;
    letter-spacing: 1px;
    padding: 10px 20px;
    /* Wide enough for the longest label ("LOAD OPENCODE"); a smaller
       min-width let the layout clip it to "OAD OPENCODE". */
    min-width: 190px;
    font-size: 13px;
    border-radius: 8px;
}

#chatLoadButton:hover {
    background-color: #212623;
    border-color: #f2c94c;
    color: #f2c94c;
}

#chatLoadButton:disabled {
    background-color: #161a18;
    border-color: #3a3a3a;
    color: #7f9c8b;
}

#chatLoadButton[loaded="true"] {
    background-color: #2d1b1b;
    border-color: #ff2a2a;
    color: #ff9f1a;
}

#chatLoadButton[loaded="true"]:hover {
    background-color: #3a2525;
    border-color: #ff9f1a;
    color: #f2c94c;
}

#chatThinkButton {
    background-color: #1c211e;
    border: 1px solid #2d332e;
    color: #7f9c8b;
    font-weight: 900;
    letter-spacing: 1px;
    padding: 10px 16px;
    min-width: 130px;
    font-size: 12px;
    border-radius: 8px;
}

/* ---- model capabilities (TOOLS · VISION · REASONING) ---- */
#chatCapabilityLabel {
    color: #4ade80;
    background-color: #14251a;
    border: 1px solid #255030;
    border-radius: 7px;
    font-size: 10px;
    font-weight: 900;
    letter-spacing: 1px;
    padding: 4px 10px;
}

/* ---- a folded answer ---- */
QPushButton#messageMoreButton {
    background-color: transparent;
    border: 1px solid #2d332e;
    border-radius: 8px;
    color: #7f9c8b;
    font-size: 11px;
    font-weight: 700;
    padding: 5px 12px;
    text-align: left;
}
QPushButton#messageMoreButton:hover {
    background-color: #161a18;
    border-color: #3ddc84;
    color: #3ddc84;
}

/* ---- the gear in the bottom-left corner of the sidebar ---- */
#aiSidebarSettingsBtn {
    background-color: #161a18;
    border: 1px solid #2d332e;
    border-radius: 9px;
    color: #9fb8a9;
    font-size: 15px;
    padding: 0;
}
#aiSidebarSettingsBtn:hover {
    background-color: #1e2620;
    border-color: #3ddc84;
    color: #3ddc84;
}

/* ---- the settings page ---- */
#settingsPage {
    background-color: #0b0e0c;
}

#settingsPageHeader {
    background-color: #101311;
    border-bottom: 1px solid #1e2b23;
}

#settingsPageTitle {
    color: #eef4f0;
    font-size: 17px;
    font-weight: 800;
    letter-spacing: 3px;
}

#settingsBackBtn {
    background-color: #1c211e;
    border: 1px solid #2d332e;
    border-radius: 8px;
    color: #c9efd9;
    font-weight: 800;
    letter-spacing: 1px;
    padding: 8px 16px;
    font-size: 12px;
}
#settingsBackBtn:hover {
    background-color: #212623;
    border-color: #3ddc84;
    color: #3ddc84;
}

#settingsPageScroll, #settingsPageBody {
    background-color: #0b0e0c;
}

#providerCard {
    background-color: #141816;
    border: 1px solid #2d332e;
    border-radius: 10px;
}
#providerCard[selected="true"] {
    border-color: #3ddc84;
    background-color: #16201a;
}

#providerName {
    color: #eef4f0;
    font-size: 14px;
    font-weight: 800;
}

#providerBadge {
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 900;
    letter-spacing: 1px;
    color: #9fb8a9;
    background-color: #1c211e;
    border: 1px solid #2d332e;
}
#providerBadge[tier="free-tier"] {
    color: #3ddc84;
    background-color: #14251a;
    border-color: #255030;
}
#providerBadge[tier="free-+-paid"] {
    color: #f2c94c;
    background-color: #241f10;
    border-color: #4a3f1e;
}
#providerBadge[tier="paid"] {
    color: #9fb8a9;
}

#providerNotes {
    color: #7f9c8b;
    font-size: 11px;
}

/* ---- the menu bar ---- */
QPushButton#updateButton {
    background-color: #1c211e;
    border: 1px solid #225c3d;
    border-radius: 6px;
    color: #7f9c8b;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
    padding: 4px 10px;
    margin-right: 8px;
}

QPushButton#updateButton[available="true"] {
    border-color: #3ddc84;
    color: #3ddc84;
    background-color: #0a1c12;
}

QPushButton#updateButton:hover {
    border-color: #f2c94c;
    color: #f2c94c;
    background-color: #212623;
}

#updatesPanel {
    background-color: #141816;
    border: 1px solid #225c3d;
    border-radius: 8px;
}
#updatesRow {
    background: transparent;
}
#updatesTitle {
    color: #3ddc84;
    font-size: 11px;
    font-weight: 900;
    letter-spacing: 2px;
    background: transparent;
}
#updatesCurrent {
    color: #3ddc84;
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 0.4px;
    background: transparent;
}
#updatesAvailable {
    color: #f2c94c;
    font-size: 13px;
    font-weight: 800;
    letter-spacing: 0.4px;
    background: transparent;
}
#updatesDetail {
    color: #c9efd9;
    font-size: 12px;
    background: transparent;
}
#updatesNote {
    color: #7f9c8b;
    font-size: 11px;
    background: transparent;
}
QPushButton#updatesAction {
    background-color: #1c211e;
    border: 1px solid #3ddc84;
    border-radius: 8px;
    color: #3ddc84;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 0.6px;
    padding: 8px 12px;
    text-align: left;
}
QPushButton#updatesAction:hover {
    background-color: #212623;
    border-color: #f2c94c;
    color: #f2c94c;
}
#updateProgress {
    background-color: #141816;
}
QProgressBar#updateBar {
    background-color: #0b0e0c;
    border: 1px solid #225c3d;
    border-radius: 6px;
    color: #c9efd9;
    text-align: center;
    min-height: 18px;
}
QProgressBar#updateBar::chunk {
    background-color: #3ddc84;
    border-radius: 5px;
}

#mainMenuBar {    background-color: #101311;
    border-bottom: 1px solid #1e2b23;
}
#mainMenuBar::item {
    background: transparent;
    padding: 5px 11px;
    color: #c9d6ce;
    font-size: 13px;
}
#mainMenuBar::item:selected {
    background-color: #1d2620;
    color: #3ddc84;
}
QMenu {
    background-color: #151a17;
    border: 1px solid #212a24;
    color: #e6ece8;
    padding: 4px;
}
QMenu::item {
    padding: 7px 26px 7px 20px;
    border-radius: 6px;
}
QMenu::item:selected {
    background-color: #23302a;
    color: #3ddc84;
}
QMenu::separator {
    height: 1px;
    background: #212a24;
    margin: 4px 8px;
}

/* ---- a tool call in the chat ---- */
#chatToolLine {
    color: #7f9c8b;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    padding: 2px 4px;
    background: transparent;
}

/* ---- attach an image ---- */
QPushButton#chatAttachButton {
    background-color: #1c211e;
    border: 1px solid #2d332e;
    color: #c9efd9;
    font-size: 15px;
    padding: 8px 12px;
    border-radius: 8px;
}
QPushButton#chatAttachButton:hover:enabled {
    background-color: #212623;
    border-color: #3ddc84;
}
QPushButton#chatAttachButton:disabled {
    color: #4a4a4a;
    border-color: #262b27;
}

/* ---- images waiting to be sent ---- */
#chatImageStrip {
    background: transparent;
}
#chatImageChip {
    color: #8ee8b4;
    background-color: #0f2620;
    border: 1px solid #1e4a33;
    border-radius: 6px;
    font-size: 11px;
    padding: 3px 8px;
}

/* ---- the chat composer ---- */
#chatComposer {
    background-color: #101010;
    border-top: 1px solid #2d332e;
}

#composerCombo {
    background-color: #1c211e;
    border: 1px solid #2d332e;
    color: #e0e0e0;
    padding: 7px 12px;
    font-size: 13px;
    font-weight: 700;
    border-radius: 8px;
    min-width: 130px;
}
#composerCombo:hover { border-color: #3ddc84; }

#composerModelCombo {
    background-color: transparent;
    border: 1px solid transparent;
    color: #c9efd9;
    padding: 5px 10px;
    font-size: 13px;
    font-weight: 700;
    border-radius: 8px;
    min-width: 140px;
}
#composerModelCombo:hover { background-color: #212623; border-color: #2d332e; }

#composerBox {
    background-color: #181d1a;
    border: 1px solid #2d332e;
    border-radius: 14px;
}
#composerBox:focus-within { border-color: #356a4c; }

#composerInput {
    background-color: transparent;
    border: none;
    color: #e0e0e0;
    font-size: 15px;
    font-family: "Segoe UI", "Cascadia Code", "Consolas", sans-serif;
    selection-background-color: #264f78;
}
#composerInput:focus { outline: none; }
#composerInput::placeholder { color: #6b6b6b; }

QPushButton#composerIconBtn {
    background-color: transparent;
    border: 1px solid #2d332e;
    color: #c9efd9;
    font-size: 15px;
    min-width: 30px;
    max-width: 30px;
    padding: 5px;
    border-radius: 15px;
}
QPushButton#composerIconBtn:hover { background-color: #212623; border-color: #3ddc84; }
QPushButton#composerIconBtn:disabled { color: #4a4a4a; border-color: #262b27; }

QPushButton#composerRoundBtn {
    background-color: #212623;
    border: 1px solid #2d332e;
    font-size: 14px;
    min-width: 30px;
    max-width: 30px;
    padding: 5px;
    border-radius: 15px;
}
QPushButton#composerRoundBtn:hover { background-color: #2d332e; border-color: #3ddc84; }

QPushButton#composerSendBtn {
    background-color: #1f3a2a;
    border: 1px solid #3ddc84;
    color: #7df3b1;
    font-weight: 900;
    letter-spacing: 1px;
    font-size: 11px;
    padding: 6px 16px;
    border-radius: 8px;
}
QPushButton#composerSendBtn:hover { background-color: #25492f; color: #b6ffd4; }
QPushButton#composerSendBtn:disabled { background-color: #1a1f1b; border-color: #262b27; color: #4a4a4a; }

QPushButton#composerStopBtn {
    background-color: #2d1b1b;
    border: 1px solid #e5484d;
    color: #ff6b6b;
    font-weight: 900;
    letter-spacing: 1px;
    font-size: 11px;
    padding: 6px 14px;
    border-radius: 8px;
}
QPushButton#composerStopBtn:hover { background-color: #3a1414; }

QPushButton#composerChip {
    background-color: #181d1a;
    border: 1px solid #2d332e;
    color: #c8c8c8;
    font-size: 12px;
    font-weight: 700;
    padding: 7px 14px;
    border-radius: 14px;
}
QPushButton#composerChip:hover { background-color: #212623; border-color: #3ddc84; color: #e0e0e0; }

/* ---- the sidebar search field and icon buttons ---- */
QLineEdit#aiSidebarSearch {
    background-color: #181d1a;
    border: 1px solid #2d332e;
    border-radius: 8px;
    color: #e0e0e0;
    padding: 7px 12px;
    font-size: 12px;
}
QLineEdit#aiSidebarSearch:focus { border-color: #3ddc84; }

QPushButton#aiSidebarIconBtn {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: #a3c9b2;
    font-size: 14px;
    min-width: 28px;
    max-width: 28px;
    min-height: 28px;
    max-height: 28px;
    padding: 0;
}
QPushButton#aiSidebarIconBtn:hover {
    background-color: #212623;
    color: #e0e0e0;
}

QPushButton#aiNavItem {
    background-color: transparent;
    border: none;
    border-radius: 6px;
    color: #e0e0e0;
    font-size: 13px;
    font-weight: 600;
    text-align: left;
    padding: 6px 10px;
}
QPushButton#aiNavItem:hover {
    background-color: #1c1c1c;
}

QPushButton#aiSectionAction {
    background: transparent;
    border: none;
    color: #7f9c8b;
    font-size: 16px;
    font-weight: 600;
    padding: 0;
}
QPushButton#aiSectionAction:hover {
    color: #e0e0e0;
    background-color: #212623;
    border-radius: 4px;
}

QPushButton#aiSidebarExpandBtn {
    background-color: #141816;
    border: none;
    border-right: 1px solid #2d332e;
    color: #a3c9b2;
    font-size: 16px;
    min-width: 20px;
    max-width: 20px;
    padding: 0;
}
QPushButton#aiSidebarExpandBtn:hover { background-color: #1c211e; color: #3ddc84; }

/* ---- cloud provider bar (free cloud LLM providers) ---- */
#cloudSettingsBar {
    background-color: #161a18;
    border-top: 1px solid #2d332e;
    border-bottom: 1px solid #2d332e;
}

/* ---- settings dialog ---- */
#settingsDialog {
    background-color: #0b0e0c;
    border: 1px solid #2d332e;
    border-radius: 12px;
}

#settingsSection {
    background-color: #141816;
    border: 1px solid #2d332e;
    border-radius: 10px;
}

#settingsSectionTitle {
    color: #f2c94c;
    font-size: 12px;
    font-weight: 900;
    letter-spacing: 2px;
    padding-bottom: 6px;
}

#settingsCombo {
    background-color: #1c211e;
    border: 1px solid #2d332e;
    color: #e0e0e0;
    padding: 7px 12px;
    font-size: 13px;
    font-weight: 700;
    border-radius: 8px;
    min-width: 200px;
}
#settingsCombo:hover { border-color: #3ddc84; }

#settingsKeyEdit, #settingsBaseEdit {
    background-color: #1c211e;
    border: 1px solid #2d332e;
    color: #e0e0e0;
    padding: 8px 12px;
    font-size: 13px;
    border-radius: 8px;
}
#settingsKeyEdit:focus, #settingsBaseEdit:focus {
    border-color: #3ddc84;
}

#settingsSaveBtn {
    background-color: #1c211e;
    border: 1px solid #3ddc84;
    color: #3ddc84;
    font-weight: 900;
    letter-spacing: 1px;
    padding: 8px 16px;
    min-width: 120px;
    font-size: 12px;
    border-radius: 8px;
}
#settingsSaveBtn:hover {
    background-color: #212623;
    border-color: #f2c94c;
    color: #f2c94c;
}
#settingsSaveBtn:disabled {
    background-color: #161a18;
    border-color: #3a3a3a;
    color: #7f9c8b;
}

#settingsClearBtn {
    background-color: #1c211e;
    border: 1px solid #2d332e;
    color: #e0e0e0;
    font-weight: 900;
    letter-spacing: 1px;
    padding: 8px 16px;
    min-width: 90px;
    font-size: 12px;
    border-radius: 8px;
}
#settingsClearBtn:hover {
    background-color: #212623;
    border-color: #f2c94c;
    color: #f2c94c;
}

#settingsLinkBtn {
    background-color: #1c211e;
    border: 1px solid #2d332e;
    color: #4de1ff;
    font-weight: 900;
    letter-spacing: 1px;
    padding: 8px 16px;
    min-width: 130px;
    font-size: 12px;
    border-radius: 8px;
}
#settingsLinkBtn:hover {
    background-color: #212623;
    border-color: #4de1ff;
    color: #f2c94c;
}

#settingsHint {
    color: #7f9c8b;
    font-size: 11px;
    font-style: italic;
    padding-top: 4px;
}

#settingsKeyStatus {
    font-size: 11px;
    font-weight: 800;
    padding-top: 2px;
}
#settingsKeyStatus[state="stored"] {
    color: #4ade80;
}
#settingsKeyStatus[state="none"] {
    color: #ff2a2a;
}

#settingsModelInfo {
    color: #c9efd9;
    font-size: 12px;
    font-family: "Cascadia Code", "Consolas", monospace;
    padding-top: 4px;
    line-height: 1.5;
}

#settingsAbout {
    color: #7f9c8b;
    font-size: 12px;
    line-height: 1.6;
}

#settingsButtons {
    background: transparent;
    border: none;
    padding-top: 10px;
}

/* ---- settings button in chat bottom bar ---- */
#settingsBottomBar {
    background-color: #141816;
    border-top: 1px solid #2d332e;
    border-radius: 0 0 12px 12px;
}

#settingsBottomBtn {
    background-color: #1c211e;
    border: 1px solid #2d332e;
    color: #c9efd9;
    font-weight: 900;
    letter-spacing: 1px;
    padding: 6px 14px;
    font-size: 12px;
    border-radius: 8px;
}
#settingsBottomBtn:hover {
    background-color: #212623;
    border-color: #3ddc84;
    color: #f2c94c;
}

#chatModelIndicator {
    color: #7f9c8b;
    font-size: 12px;
    font-weight: 800;
    font-family: "Cascadia Code", "Consolas", monospace;
    padding: 4px 10px;
    border-radius: 6px;
    background-color: #181d1a;
    border: 1px solid #2d332e;
}
#chatModelIndicator[provider="cloud"] {
    color: #4de1ff;
    border-color: #2d4a5a;
}
#chatModelIndicator[provider="ollama"] {
    color: #3ddc84;
    border-color: #1e4a2a;
}
#chatModelIndicator[provider="opencode"] {
    color: #ffe81f;
    border-color: #4a4a1e;
}
QLineEdit#chatModelCombo {
    background-color: #1c211e;
    border: 1px solid #2d332e;
    color: #e0e0e0;
    padding: 8px 12px;
    font-size: 13px;
    border-radius: 8px;
}
QLineEdit#chatModelCombo:focus {
    border-color: #3ddc84;
}

#chatThinkButton:hover {
    background-color: #212623;
    border-color: #3ddc84;
    color: #3ddc84;
}

#chatThinkButton:checked {
    background-color: #17251d;
    border-color: #4ade80;
    color: #4ade80;
}

#chatThinkButton:checked:hover {
    background-color: #1d3327;
    color: #f2c94c;
}

#chatModelCombo {
    background-color: #141816;
    border: 1px solid #2d332e;
    color: #e0e0e0;
    padding: 10px 16px;
    font-size: 13px;
    font-weight: 800;
    min-height: 40px;
    border-radius: 8px;
}

#chatModelCombo:hover {
    border-color: #3ddc84;
}

#chatModelCombo:focus {
    border-color: #3ddc84;
}

#chatModelCombo::drop-down {
    background-color: #141816;
    border: none;
    width: 24px;
    border-radius: 8px;
}

#chatModelCombo::down-arrow {
    color: #3ddc84;
    width: 16px;
    height: 16px;
}

QComboBox QAbstractItemView {
    background-color: #141816;
    color: #e0e0e0;
    border: 1px solid #2d332e;
    selection-background-color: #202522;
    selection-color: #f2c94c;
    border-radius: 8px;
    padding: 4px;
    outline: none;
}
QComboBox QAbstractItemView::item {
    padding: 6px 12px;
    min-height: 22px;
}

#loadingSpinner {
    background: transparent;
    border: none;
}

QPushButton#micButtonMuted {
    background-color: #2d1b1b;
    border: 1px solid #ff2a2a;
    color: #ff2a2a;
    font-weight: 900;
    letter-spacing: 1px;
    padding: 8px 16px;
    min-width: 150px;
    font-size: 13px;
    border-radius: 8px;
}

QPushButton#micButtonMuted:hover {
    background-color: #3a2525;
    border-color: #ff9f1a;
    color: #ff9f1a;
}

#aiWorkspacePanel {
    background-color: #0b0e0c;
}

#aiSidebar {
    background-color: #0f0f0f;
    border-right: 1px solid #2d332e;
    border-radius: 0;
}

#aiSidebarTitle {
    color: #f2c94c;
    font-size: 18px;
    font-weight: 900;
    letter-spacing: 3px;
    padding-bottom: 6px;
    qproperty-alignment: AlignCenter;
    background-color: transparent;
    border: none;
    margin-bottom: 4px;
}

#aiSectionLabel {
    color: #8a8a8a;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0px;
    margin: 0;
    padding: 0;
    background: transparent;
    border: none;
}

#aiSectionHeader {
    background: transparent;
    border: none;
}

#aiWorkspaceList, #aiProjectList, #aiConvList {
    background-color: #141816;
    border: 1px solid #2d332e;
    color: #e0e0e0;
    font-size: 13px;
    outline: none;
    border-radius: 8px;
}

#aiSectionScroll {
    background: transparent;
    border: none;
}

#aiSectionBody {
    background: transparent;
}

/* ---- sidebar rows (workspaces / projects / conversations) ---- */

#aiRow {
    background-color: transparent;
    border: none;
    border-radius: 6px;
}

#aiRow[selected="true"] {
    background-color: #2a2a2a;
    border: none;
}

#aiRow[hovered="true"] {
    background-color: #1c1c1c;
    border: none;
}

#aiRow[selected="true"][hovered="true"] {
    background-color: #333333;
    border: none;
}

#aiRowTitle {
    color: #e0e0e0;
    font-size: 13px;
    font-weight: 500;
    background: transparent;
    border: none;
}

#aiRowMark, #aiRowMeta {
    color: #8a8a8a;
    font-size: 11px;
    font-weight: 500;
    background: transparent;
    border: none;
}

#aiRow[selected="true"] #aiRowTitle {
    color: #f2f2f2;
}

/* Red trash bin — only appears when the row is hovered, so the list stays clean. */
#rowDeleteBtn {
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    color: transparent;
    font-size: 12px;
    padding: 0px;
}

#rowDeleteBtn:hover {
    background-color: #3a1414;
    border: 1px solid #e5484d;
    color: #ff6b6b;
}

#aiRow[hovered="true"] #rowDeleteBtn,
#aiRow[selected="true"] #rowDeleteBtn {
    color: #b0b0b0;
}

#aiSidebarButton {
    background-color: #1c211e;
    border: 1px solid #2d332e;
    color: #c9efd9;
    font-weight: 800;
    letter-spacing: 1px;
    padding: 10px 16px;
    font-size: 13px;
    text-align: left;
    border-radius: 8px;
}

#aiSidebarButton:hover {
    background-color: #212623;
    border-color: #3ddc84;
    color: #f2c94c;
}

#aiSidebarButtonPrimary {
    background-color: #1c211e;
    border: 1px solid #3ddc84;
    color: #3ddc84;
    font-weight: 900;
    letter-spacing: 1px;
    padding: 12px 18px;
    font-size: 13px;
    text-align: left;
    border-radius: 8px;
}

#aiSidebarButtonPrimary:hover {
    background-color: #212623;
    border-color: #f2c94c;
    color: #f2c94c;
}

#opencodeConsole {
    background-color: #141816;
    border: 1px solid #2d332e;
    border-top: none;
    border-radius: 0 0 12px 12px;
}

#opencodeConsoleHeader {
    background-color: #161a18;
    border-bottom: 1px solid #2d332e;
    border-radius: 0;
}

#opencodeConsoleLabel {
    color: #3ddc84;
    font-weight: 900;
    font-size: 12px;
    letter-spacing: 1px;
    background: transparent;
}

#opencodeConsoleHeaderBtn {
    background-color: #1c211e;
    border: 1px solid #2d332e;
    color: #c9efd9;
    font-weight: 800;
    font-size: 11px;
    letter-spacing: 1px;
    padding: 5px 12px;
    border-radius: 7px;
}

#opencodeConsoleHeaderBtn:hover {
    background-color: #212623;
    border-color: #3ddc84;
    color: #f2c94c;
}

#opencodeStack {
    background-color: #141816;
    border: none;
    border-radius: 0 0 12px 12px;
}

/* The real OpenCode web app renders itself; Qt only supplies the frame. */
#opencodeWebView {
    background-color: #141816;
    border: none;
    border-radius: 0 0 12px 12px;
}

#opencodePlaceholder {
    background-color: #0e0e0e;
    border: none;
    border-radius: 0 0 12px 12px;
}

#opencodeHint {
    color: #7f9c8b;
    font-size: 13px;
    font-weight: 600;
    background: transparent;
}

/* Administrator badge in the console header. */
#opencodeAdminBadge {
    color: #6b6b6b;
    background-color: #1c211e;
    border: 1px solid #2d332e;
    border-radius: 7px;
    font-size: 10px;
    font-weight: 900;
    letter-spacing: 1px;
    padding: 4px 10px;
}

#opencodeAdminBadge[admin="true"] {
    color: #4ade80;
    border-color: #4ade80;
    background-color: #14251a;
}

/* The embedded terminal: a real, dark, monospace terminal surface. */
#terminalWidget {
    background-color: #0d100e;
    color: #e0e0e0;
    border: none;
    border-radius: 0 0 12px 12px;
    selection-background-color: #264f78;
}

/* ------------------------------------------------------------------
   Inline AI status indicator (@connecting / @reasoning / @generating)
   ------------------------------------------------------------------ */

#statusBubble {
    background-color: transparent;
    border: none;
}

#statusCard {
    background-color: #0e1620;
    border: 1px solid #1f3b4d;
    border-left: 3px solid #3ddc84;
    border-radius: 10px;
}

#statusBubble[state="thinking"] #statusCard {
    background-color: #17130e;
    border: 1px solid #4a3a1a;
    border-left: 3px solid #f2c94c;
}

#statusBubble[state="generating"] #statusCard {
    background-color: #0f1a14;
    border: 1px solid #1e4a2a;
    border-left: 3px solid #4ade80;
}

#statusBubble[state="done"] #statusCard {
    background-color: #101010;
    border: 1px solid #2d332e;
    border-left: 3px solid #3ddc84;
}

#statusBubble[state="error"] #statusCard {
    background-color: #1c1111;
    border: 1px solid #5a2020;
    border-left: 3px solid #ff2a2a;
}

#statusBubble[state="stopped"] #statusCard {
    background-color: #181d1a;
    border: 1px solid #3a3a3a;
    border-left: 3px solid #ff9f1a;
}

#statusTitle {
    color: #3ddc84;
    font-size: 13px;
    font-weight: 900;
    letter-spacing: 1px;
}

#statusBubble[state="thinking"] #statusTitle {
    color: #f2c94c;
}

#statusBubble[state="generating"] #statusTitle {
    color: #4ade80;
}

#statusBubble[state="error"] #statusTitle {
    color: #ff2a2a;
}

#statusBubble[state="stopped"] #statusTitle {
    color: #ff9f1a;
}

#statusStats {
    color: #7f9c8b;
    font-size: 11px;
    font-weight: 700;
    font-family: "Cascadia Code", "Consolas", monospace;
}

#statusSpinner {
    color: #3ddc84;
    font-size: 15px;
    font-weight: 900;
}

#statusBubble[state="thinking"] #statusSpinner {
    color: #f2c94c;
}

#statusBubble[state="generating"] #statusSpinner {
    color: #4ade80;
}

#statusBubble[state="error"] #statusSpinner {
    color: #ff2a2a;
}

#statusReasonBox {
    background-color: #0b0e0c;
    border: 1px solid #2d332e;
    border-radius: 8px;
}

#statusReason {
    color: #9fb3c0;
    font-size: 12px;
    line-height: 1.45;
    font-family: "Cascadia Code", "Consolas", monospace;
    background-color: transparent;
    border: none;
}

#statusToggle {
    background-color: transparent;
    border: none;
    color: #3ddc84;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 1px;
    padding: 2px 4px;
    text-align: left;
}

#statusToggle:hover {
    color: #f2c94c;
}

/* ------------------------------------------------------------------
   Header status lamp (● OLLAMA) and the VRAM / RAM gauges
   ------------------------------------------------------------------ */

#statusLampBox {
    background-color: #141816;
    border: none;
}

#statusLamp {
    background-color: #4ade80;
    border: 1px solid #0b0e0c;
    border-radius: 7px;
}

#statusLamp[state="offline"] {
    background-color: #ff2a2a;
}

#statusLamp[state="loading"] {
    background-color: #f2c94c;
}

#statusLampText {
    color: #4ade80;
    font-weight: 900;
    font-size: 12px;
    letter-spacing: 2px;
    background-color: #141816;
    border: none;
}

#statusLampText[state="offline"] {
    color: #ff2a2a;
}

#statusLampText[state="loading"] {
    color: #f2c94c;
}

#memGauge {
    background-color: #141816;
    border: none;
}

#memGaugeRow {
    background-color: #141816;
    border: none;
}

#memGaugeCaption {
    color: #7f9c8b;
    font-size: 10px;
    font-weight: 900;
    letter-spacing: 1px;
    background-color: #141816;
    border: none;
}

#memGaugeBar {
    background-color: #0b0e0c;
    border: 1px solid #2d332e;
    border-radius: 4px;
    max-height: 7px;
    min-height: 7px;
}

#memGaugeBar::chunk {
    background-color: #3ddc84;
    border-radius: 3px;
}

#memGaugeBar[state="warn"]::chunk {
    background-color: #ff9f1a;
}

#memGaugeBar[state="crit"]::chunk {
    background-color: #ff2a2a;
}

#memGaugeValue {
    color: #c9efd9;
    font-size: 11px;
    font-weight: 700;
    font-family: "Cascadia Code", "Consolas", monospace;
    background-color: #141816;
    border: none;
}

/* ------------------------------------------------------------------
   Draggable splitter between the chat area and the OpenCode console
   ------------------------------------------------------------------ */

#chatSplitter {
    background-color: #0b0e0c;
    border: none;
}

#chatSplitter::handle {
    background-color: #141816;
    border-top: 1px solid #2d332e;
    border-bottom: 1px solid #3ddc84;
}

#chatSplitter::handle:hover {
    background-color: #16242e;
    border-top: 1px solid #3ddc84;
}

#chatSplitterHandle {
    background-color: #141816;
    border-top: 1px solid #2d332e;
    border-bottom: 1px solid #3ddc84;
}

#chatSplitterHandle:hover {
    background-color: #16242e;
}

#splitterGrip {
    background-color: #3a3a3a;
    border-radius: 3px;
}

#splitterGripLine {
    background-color: #8fb6cc;
    border-radius: 1px;
}

#chatSplitterHandle:hover #splitterGrip {
    background-color: #3ddc84;
}

#chatSplitterHandle:hover #splitterGripLine {
    background-color: #0b0e0c;
}

/* ------------------------------------------------------------------
   Collapsible code blocks inside a chat message
   ------------------------------------------------------------------ */

#codeBlock {
    background-color: #0b0e0c;
    border: 1px solid #2d332e;
    border-radius: 8px;
}

#codeBlockHeader {
    background-color: #161a18;
    border: none;
    border-bottom: 1px solid #2d332e;
    border-radius: 8px 8px 0 0;
}

#codeBlockToggle {
    background-color: transparent;
    border: none;
    color: #3ddc84;
    font-size: 12px;
    font-weight: 900;
    letter-spacing: 1px;
    text-align: left;
    padding: 2px 4px;
}

#codeBlockToggle:hover {
    color: #f2c94c;
}

#codeBlockCopy {
    background-color: #1c211e;
    border: 1px solid #2d332e;
    color: #7f9c8b;
    font-size: 10px;
    font-weight: 900;
    letter-spacing: 1px;
    padding: 3px 10px;
    border-radius: 6px;
}

#codeBlockCopy:hover {
    border-color: #3ddc84;
    color: #3ddc84;
}

#codeBlockContent {
    background-color: #080808;
    color: #e2f2e8;
    font-family: "Cascadia Code", "Consolas", monospace;
    font-size: 12px;
    line-height: 1.45;
    border: none;
    border-radius: 0 0 8px 8px;
    padding: 8px;
    selection-background-color: #202522;
}
"""
