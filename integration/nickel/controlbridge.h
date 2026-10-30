// SPDX-License-Identifier: MIT
#pragma once
#include <QObject>
#include <QLocalServer>
#include <QLocalSocket>
#include <QPointer>
#include <QList>
#include <QWidget>

typedef bool PermissionRequest;

// The open session socket owns all temporary restrictions. No power or network
// configuration is rewritten to lend the display to k2.
class ControlBridge : public QObject {
    Q_OBJECT
public:
    explicit ControlBridge(QObject *parent);
    ~ControlBridge() override;
    bool eventFilter(QObject *object, QEvent *event) override;
private slots:
    void accept();
    void read();
    void release();
    void veto(PermissionRequest *allow);
    void sleep(PermissionRequest *allow);
    void resume();
private:
    bool begin(QLocalSocket *socket, bool allowSleep);
    void thaw();
    void activity();
    bool pauseDisplay();
    bool lendButtons();
    QObject *light();
    void restoreButtons();
    void finish();
    void freeze(QWidget *widget);
    QLocalServer server;
    QPointer<QLocalSocket> owner;
    QPointer<QLocalSocket> display;
    QPointer<QObject> powerWorkflow;
    QPointer<QObject> frontLight;
    bool allowSleep = false;
    bool sleeping = false;
    QList<QPointer<QWidget>> frozen;
    QList<QPointer<QObject>> vetoSources;
    QList<int> buttonGrabs;
};
