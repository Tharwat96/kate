/* This file is part of the KDE project
   Copyright (C) 2001 Christoph Cullmann <cullmann@kde.org>
   Copyright (C) 2001 Joseph Wenninger <jowenn@kde.org>
   Copyright (C) 2001 Anders Lund <anders.lund@lund.tdcadsl.dk>

   This library is free software; you can redistribute it and/or
   modify it under the terms of the GNU Library General Public
   License version 2 as published by the Free Software Foundation.

   This library is distributed in the hope that it will be useful,
   but WITHOUT ANY WARRANTY; without even the implied warranty of
   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
   Library General Public License for more details.

   You should have received a copy of the GNU Library General Public License
   along with this library; see the file COPYING.LIB.  If not, write to
   the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
   Boston, MA 02110-1301, USA.
*/

#ifndef KWRITE_MAIN_H
#define KWRITE_MAIN_H

#include <ktexteditor/document.h>
#include <ktexteditor/mainwindow.h>
#include <ktexteditor/view.h>

#include <KConfigGroup>
#include <KParts/MainWindow>
#include <KSharedConfig>

class QLabel;

namespace KActivities
{
class ResourceInstance;
}

class KToggleAction;
class KRecentFilesAction;
class KSqueezedTextLabel;
class KWriteApplication;

class KWrite : public KParts::MainWindow
{
    Q_OBJECT

public:
    KWrite(KTextEditor::Document * = nullptr, KWriteApplication *app = nullptr);
    ~KWrite() override;

    void loadURL(const QUrl &url);

private:
    void setupActions();

    void addMenuBarActionToContextMenu();
    void removeMenuBarActionFromContextMenu();

    bool queryClose() override;

    void dragEnterEvent(QDragEnterEvent *) override;
    void dropEvent(QDropEvent *) override;

public Q_SLOTS:
    void slotNew();
    void slotFlush();
    void slotOpen();
    void slotOpen(const QUrl &url);
    void newView();
    void toggleStatusBar();
    void toggleMenuBar(bool showMessage = true);
    void editKeys();
    void editToolbars();
    void aboutEditor();
    void modifiedChanged();

private Q_SLOTS:
    void slotNewToolbarConfig();

public Q_SLOTS:
    void slotDropEvent(QDropEvent *);

    void slotEnableActions(bool enable);

    /**
     * adds a changed URL to the recent files
     */
    void urlChanged();

    /**
     * Overwrite size hint for better default window sizes
     * @return size hint
     */
    QSize sizeHint() const override;

    // config file functions
public:
    void readConfig(KSharedConfigPtr);
    void writeConfig(KSharedConfigPtr);

    void readConfig();
    void writeConfig();

    // session management
public:
    void restore(KConfig *, int);

public:
    KTextEditor::MainWindow *mainWindow()
    {
        return &m_mainWindow;
    }

public Q_SLOTS:
    QWidget *window()
    {
        return this;
    }
    QList<KTextEditor::View *> views();
    KTextEditor::View *activeView()
    {
        return m_view;
    }
    KTextEditor::View *activateView(KTextEditor::Document *document);

private:
    void readProperties(const KConfigGroup &) override;
    void saveProperties(KConfigGroup &) override;
    void saveGlobalProperties(KConfig *) override;

private:
    KTextEditor::View *m_view = nullptr;

    KRecentFilesAction *m_recentFiles = nullptr;
    KToggleAction *m_paShowPath = nullptr;
    KToggleAction *m_paShowMenuBar = nullptr;
    KToggleAction *m_paShowStatusBar = nullptr;
    QAction *m_closeAction;
    KActivities::ResourceInstance *m_activityResource = nullptr;
    KWriteApplication *m_app;
    KTextEditor::MainWindow m_mainWindow;

public Q_SLOTS:
    void documentNameChanged();

protected:
    /**
     * Event filter for QApplication to handle mac os like file open
     */
    bool eventFilter(QObject *obj, QEvent *event) override;
};

#endif
