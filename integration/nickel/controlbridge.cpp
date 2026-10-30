// SPDX-License-Identifier: MIT
#include "controlbridge.h"
#include <QApplication>
#include <QDir>
#include <QEvent>
#include <QElapsedTimer>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTimer>
#include <cerrno>
#include <cstring>
#include <dlfcn.h>
#include <fcntl.h>
#include <linux/input.h>
#include <sys/ioctl.h>
#include <unistd.h>

namespace {
bool sessionButtonDevice(int fd, bool includePower) {
    unsigned char keys[(KEY_MAX + 8) / 8] = {};
    const auto hasKey = [&keys](unsigned key) {
        return keys[key / 8] & (1U << (key % 8));
    };
    return ioctl(fd, EVIOCGBIT(EV_KEY, sizeof(keys)), keys) >= 0 &&
        ((hasKey(193) && hasKey(194)) || (includePower && hasKey(KEY_POWER))) &&
        !hasKey(KEY_A);
}

int setGrab(int fd, bool grab) {
    int result;
    do {
        result = ioctl(fd, EVIOCGRAB, grab ? 1 : 0);
    } while (result < 0 && errno == EINTR);
    return result;
}
}

template<typename T> static T symbol(const char *name) {
    return reinterpret_cast<T>(dlsym(RTLD_DEFAULT, name));
}

static QObject *instance(const char *name) {
    auto fn = symbol<QObject *(*)()>(name);
    return fn ? fn() : nullptr;
}

ControlBridge::ControlBridge(QObject *parent) : QObject(parent) {
    const QString path = QStringLiteral("/var/run/k2-nickel.sock");
    QLocalServer::removeServer(path);
    if (!server.listen(path)) {
        qWarning("k2: could not start the native control bridge");
        return;
    }
    QFile::setPermissions(path, QFile::ReadOwner | QFile::WriteOwner);
    connect(&server, SIGNAL(newConnection()), this, SLOT(accept()));
    qApp->installEventFilter(this);
}

ControlBridge::~ControlBridge() {
    finish();
}

void ControlBridge::accept() {
    while (server.hasPendingConnections()) {
        auto *socket = server.nextPendingConnection();
        connect(socket, SIGNAL(readyRead()), this, SLOT(read()));
        connect(socket, SIGNAL(disconnected()), this, SLOT(release()));
        connect(socket, SIGNAL(disconnected()), socket, SLOT(deleteLater()));
    }
}

void ControlBridge::freeze(QWidget *widget) {
    if (widget->isWindow() && widget->updatesEnabled()) {
        frozen.append(widget);
        widget->setUpdatesEnabled(false);
    }
}

bool ControlBridge::begin(QLocalSocket *socket, bool sleepAllowed) {
    if (owner)
        return false;
    struct Source { const char *factory; const char *signal; } sources[] = {
        {"_ZN12PowerManager14sharedInstanceEv", SIGNAL(aboutToSuspend(PermissionRequest*))},
        {"_ZN16WirelessWatchdog14sharedInstanceEv", SIGNAL(aboutToKillWifi(PermissionRequest*))},
    };
    allowSleep = sleepAllowed;
    for (const auto &source : sources) {
        auto *object = instance(source.factory);
        if (!object || !connect(object, source.signal, this, SLOT(veto(PermissionRequest*)), Qt::DirectConnection)) {
            finish();
            return false;
        }
        vetoSources.append(object);
    }
    powerWorkflow = instance("_ZN22N3PowerWorkflowManager14sharedInstanceEv");
    if (!powerWorkflow ||
        !connect(powerWorkflow, SIGNAL(aboutToShowSleep(PermissionRequest*)),
                 this, SLOT(sleep(PermissionRequest*)), Qt::DirectConnection)) {
        finish();
        return false;
    }
    vetoSources.append(powerWorkflow);
    if (allowSleep &&
        (!symbol<bool (*)(QObject *)>("_ZNK22N3PowerWorkflowManager8sleepingEv") ||
         !symbol<bool (*)(QObject *)>("_ZNK22N3PowerWorkflowManager16sleepViewVisibleEv") ||
         !symbol<int (*)()>("_ZN9TimeEvent9eventTypeEv") ||
         !symbol<bool (*)(QObject *, QObject *, QEvent *)>("_ZN12PowerManager6filterEP7QObjectP6QEvent") ||
         !connect(powerWorkflow, SIGNAL(resumedFromSleep()), this, SLOT(resume()), Qt::QueuedConnection))) {
        finish();
        return false;
    }
    if (!lendButtons()) {
        finish();
        return false;
    }
    owner = socket;
    for (auto *widget : QApplication::topLevelWidgets())
        freeze(widget);
    if (allowSleep) activity();
    return true;
}

bool ControlBridge::lendButtons() {
    const QDir descriptors(QStringLiteral("/proc/self/fd"));
    if (!descriptors.exists()) {
        qWarning("k2: could not inspect native input descriptors");
        return false;
    }
    const auto names = descriptors.entryList(QDir::AllEntries | QDir::NoDotAndDotDot | QDir::System);
    for (const auto &name : names) {
        bool numeric;
        const int fd = name.toInt(&numeric);
        // App-coordinated sleep needs the power button as well as page keys.
        // Stock reader sessions keep Nickel's power-button ownership.
        if (!numeric || !sessionButtonDevice(fd, !allowSleep))
            continue;
        const int held = fcntl(fd, F_DUPFD_CLOEXEC, 0);
        if (held < 0) {
            qWarning("k2: could not retain native button descriptor: %s", strerror(errno));
            return false;
        }
        // A duplicate holds the same evdev client even if Nickel closes or
        // reuses its original descriptor while another app owns the display.
        if (!sessionButtonDevice(held, !allowSleep)) {
            close(held);
            continue;
        }
        if (setGrab(held, false) == 0) {
            buttonGrabs.append(held);
        } else {
            const int error = errno;
            close(held);
            // Only the client owning the existing grab may release it.
            if (error != EINVAL) {
                qWarning("k2: could not lend native buttons: %s", strerror(error));
                return false;
            }
        }
    }
    return true;
}

void ControlBridge::restoreButtons() {
    for (const int fd : buttonGrabs) {
        if (setGrab(fd, true) < 0)
            qWarning("k2: could not restore native button grab: %s", strerror(errno));
        close(fd);
    }
    buttonGrabs.clear();
}

void ControlBridge::veto(PermissionRequest *allow) {
    // Reader sessions leave suspend to Nickel. Wi-Fi may stay available while
    // reading, but must be allowed to shut down for the stock sleep workflow.
    if (owner && allow && (!allowSleep ||
        (!sleeping && sender() != instance("_ZN12PowerManager14sharedInstanceEv"))))
        *allow = false;
}

void ControlBridge::activity() {
    if (!owner || !allowSleep || sleeping) return;
    auto *power = instance("_ZN12PowerManager14sharedInstanceEv");
    auto filter = symbol<bool (*)(QObject *, QObject *, QEvent *)>("_ZN12PowerManager6filterEP7QObjectP6QEvent");
    auto eventType = symbol<int (*)()>("_ZN9TimeEvent9eventTypeEv");
    // Nickel accounts user activity through TimeEvent, not Qt mouse events.
    // Feed only the power filter, without dispatching input to its hidden UI.
    if (power && filter && eventType) {
        QEvent used(static_cast<QEvent::Type>(eventType()));
        QEvent update(QEvent::UpdateRequest);
        filter(power, qApp, &used);
        filter(power, qApp, &update);
    }
}

bool ControlBridge::pauseDisplay() {
    if (!display) return false;
    auto *socket = display.data();
    // This permission callback must finish before Nickel paints its sleep
    // screen. Wait for the app to drain panel updates and release its touch grab.
    socket->blockSignals(true);
    socket->write("{\"event\":\"sleep\"}\n");
    socket->flush();
    QElapsedTimer deadline;
    deadline.start();
    bool paused = false;
    while (deadline.elapsed() < 3000 && socket->state() == QLocalSocket::ConnectedState) {
        if (!socket->canReadLine() && !socket->waitForReadyRead(3000 - deadline.elapsed()))
            break;
        while (socket->canReadLine()) {
            const auto reply = QJsonDocument::fromJson(socket->readLine()).object();
            if (reply.value(QStringLiteral("command")).toString() == QStringLiteral("sleeping")) {
                paused = true;
                break;
            }
        }
        if (paused) break;
    }
    socket->blockSignals(false);
    return paused;
}

void ControlBridge::sleep(PermissionRequest *allow) {
    if (!owner || !allow) return;
    if (!allowSleep) { *allow = false; return; }
    if (sleeping || !*allow) return;
    if (!display) { *allow = false; return; }
    if (!pauseDisplay()) {
        *allow = false;
        // A lost or stalled app cannot safely retain the display. Disconnect
        // its session and let the supervisor terminate it before the next sleep.
        auto *session = owner.data();
        finish();
        session->disconnectFromServer();
        return;
    }
    sleeping = true;
    restoreButtons();
    thaw();
    // Another permission handler can veto this attempt after ours returns.
    QTimer::singleShot(0, this, SLOT(resume()));
}

void ControlBridge::resume() {
    if (!owner || !allowSleep || !sleeping || !powerWorkflow) return;
    auto isSleeping = symbol<bool (*)(QObject *)>("_ZNK22N3PowerWorkflowManager8sleepingEv");
    auto sleepVisible = symbol<bool (*)(QObject *)>("_ZNK22N3PowerWorkflowManager16sleepViewVisibleEv");
    if (isSleeping(powerWorkflow) || sleepVisible(powerWorkflow)) return;
    if (!lendButtons()) {
        auto *session = owner.data();
        finish();
        session->disconnectFromServer();
        return;
    }
    sleeping = false;
    for (auto *widget : QApplication::topLevelWidgets()) freeze(widget);
    if (display) {
        display->write("{\"event\":\"wake\"}\n");
        display->flush();
    }
}

bool ControlBridge::eventFilter(QObject *object, QEvent *event) {
    if (!owner || sleeping)
        return false;
    switch (event->type()) {
    case QEvent::Show:
        if (auto *widget = qobject_cast<QWidget *>(object)) freeze(widget);
        break;
    case QEvent::Paint:
    case QEvent::UpdateRequest:
    case QEvent::KeyPress:
    case QEvent::KeyRelease:
    case QEvent::MouseButtonPress:
    case QEvent::MouseButtonRelease:
    case QEvent::MouseMove:
    case QEvent::TouchBegin:
    case QEvent::TouchUpdate:
    case QEvent::TouchEnd:
        return true;
    default:
        break;
    }
    return false;
}

void ControlBridge::release() {
    if (sender() == display) {
        // Qt closes this connection during normal UI teardown. The supervisor
        // keeps ownership until the child has exited and released its fds.
        display.clear();
        return;
    }
    if (sender() != owner)
        return;
    finish();
}

void ControlBridge::finish() {
    // Sharing the node keeps Nickel's power/cover handling alive during the
    // session. Restore only grabs that this bridge successfully released.
    restoreButtons();
    owner.clear();
    if (display) {
        display->disconnectFromServer();
        display.clear();
    }
    for (const auto &object : vetoSources) {
        if (object)
            disconnect(object, nullptr, this, nullptr);
    }
    vetoSources.clear();
    powerWorkflow.clear();
    sleeping = false;
    allowSleep = false;
    thaw();
}

void ControlBridge::thaw() {
    for (const auto &widget : frozen) {
        if (widget) {
            widget->setUpdatesEnabled(true);
            widget->update();
        }
    }
    frozen.clear();
}

void ControlBridge::read() {
    auto *socket = qobject_cast<QLocalSocket *>(sender());
    if (!socket) return;
    if (socket->bytesAvailable() > 4096) { socket->disconnectFromServer(); return; }
    while (socket->canReadLine()) {
        const auto request = QJsonDocument::fromJson(socket->readLine()).object();
        const auto command = request.value(QStringLiteral("command")).toString();
        QJsonObject result;
        if (command == QStringLiteral("begin")) {
            if (!begin(socket, request.value(QStringLiteral("allowSleep")).toBool())) result.insert(QStringLiteral("error"), QStringLiteral("The reader is busy or this firmware cannot lend its display safely."));
            else result.insert(QStringLiteral("active"), true);
        } else if (command == QStringLiteral("watch_sleep") && owner && allowSleep && !display) {
            display = socket;
            result.insert(QStringLiteral("active"), true);
        } else if (command == QStringLiteral("activity") && socket == display) {
            activity();
            continue;
        } else if (command == QStringLiteral("end") && socket == owner) {
            release();
            result.insert(QStringLiteral("active"), false);
        } else if (command == QStringLiteral("wifi") || command == QStringLiteral("set_wifi")) {
            auto *workflow = instance("_ZN23WirelessWorkflowManager14sharedInstanceEv");
            auto *wireless = instance("_ZN15WirelessManager14sharedInstanceEv");
            auto airplane = symbol<bool (*)(QObject *)>("_ZN23WirelessWorkflowManager14isAirplaneModeEv");
            auto setAirplane = symbol<void (*)(QObject *, bool)>("_ZN23WirelessWorkflowManager15setAirplaneModeEb");
            auto connectSilent = symbol<void (*)(QObject *)>("_ZN23WirelessWorkflowManager23connectWirelessSilentlyEv");
            auto connected = symbol<bool (*)(QObject *)>("_ZN15WirelessManager9connectedEv");
            auto ssid = symbol<QString (*)(QObject *)>("_ZN15WirelessManager7getSsidEv");
            if (!workflow || !wireless || !airplane || !setAirplane || !connectSilent || !connected || !ssid) {
                result.insert(QStringLiteral("error"), QStringLiteral("Wi-Fi control is unavailable on this firmware."));
            } else {
                if (command == QStringLiteral("set_wifi")) {
                    const bool enable = request.value(QStringLiteral("enabled")).toBool();
                    setAirplane(workflow, !enable);
                    if (enable) connectSilent(workflow);
                }
                result.insert(QStringLiteral("available"), true);
                result.insert(QStringLiteral("enabled"), !airplane(workflow));
                result.insert(QStringLiteral("connected"), connected(wireless));
                result.insert(QStringLiteral("ssid"), connected(wireless) ? ssid(wireless) : QString());
            }
        } else {
            result.insert(QStringLiteral("error"), QStringLiteral("Unknown native control request."));
        }
        socket->write(QJsonDocument(result).toJson(QJsonDocument::Compact) + '\n');
        socket->flush();
    }
}
