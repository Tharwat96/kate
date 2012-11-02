/*  This file is part of the Kate project.
 *
 *  Copyright (C) 2010-2012 Dominik Haumann <dhaumann kde org>
 *  Copyright (C) 2010 Diana-Victoria Tiriplica <diana.tiriplica@gmail.com>
 *
 *  This library is free software; you can redistribute it and/or
 *  modify it under the terms of the GNU Library General Public
 *  License as published by the Free Software Foundation; either
 *  version 2 of the License, or (at your option) any later version.
 *
 *  This library is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 *  Library General Public License for more details.
 *
 *  You should have received a copy of the GNU Library General Public License
 *  along with this library; see the file COPYING.LIB.  If not, write to
 *  the Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor,
 *  Boston, MA 02110-1301, USA.
 */

#ifndef _KATE_RECOVER_H__
#define _KATE_RECOVER_H__

#include "kateviewhelpers.h"

#include <QByteArray>
#include <QAction>
#include <KTemporaryFile>

class KProcess;
class KateView;
class KateDocument;

class KateRecoverBar : public KateViewBarWidget
{
  Q_OBJECT

  public:
    explicit KateRecoverBar(KateView *view, QWidget *parent = 0);
    ~KateRecoverBar ();

  protected Q_SLOTS:
    void viewDiff();

  private:
    KateView *const m_view;
    QAction* m_diffAction;

  protected Q_SLOTS:
    void slotDataAvailable();
    void slotDiffFinished();

  private:
    KProcess* m_proc;
    KTemporaryFile m_originalFile;
    KTemporaryFile m_recoveredFile;
    KTemporaryFile m_diffFile;
};

#endif //_KATE_RECOVER_H__

// kate: space-indent on; indent-width 2; replace-tabs on;
