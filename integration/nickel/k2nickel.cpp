// SPDX-License-Identifier: MIT
// Nickel loads image-format plugins on startup. This plugin adds a native rail
// button when MainNavView is shown; it does not replace or configure NickelMenu.
#include <QApplication>
#include <QEvent>
#include <QHBoxLayout>
#include <QImageIOPlugin>
#include <QPointer>
#include <QProcess>
#include <QTimer>
#include <QWidget>
#include <dlfcn.h>
#include <new>
#include "controlbridge.h"

class Rail : public QObject {
    Q_OBJECT
public:
    explicit Rail(QObject *parent) : QObject(parent) {
        qApp->installEventFilter(this);
        QTimer::singleShot(0, this, SLOT(scan()));
    }

    bool eventFilter(QObject *object, QEvent *event) override {
        if (event->type() == QEvent::Show && object->inherits("MainNavView")) {
            pending = qobject_cast<QWidget *>(object);
            QTimer::singleShot(0, this, SLOT(addButton()));
        }
        return false;
    }

private slots:
    void scan() {
        foreach (QWidget *widget, QApplication::allWidgets()) {
            if (widget->inherits("MainNavView")) {
                pending = widget;
                addButton();
            }
        }
    }

    void addButton() {
        if (!pending || pending->property("k2RailAdded").toBool())
            return;
        auto *layout = pending->findChild<QHBoxLayout *>();
        if (!layout)
            return;
        // The same native MainNavButton ABI used by NickelMenu on FW 4.23+.
        typedef void (*Construct)(QWidget *, QWidget *);
        typedef void (*SetText)(QWidget *, const QString &);
        auto construct = reinterpret_cast<Construct>(dlsym(RTLD_DEFAULT, "_ZN13MainNavButtonC1EP7QWidget"));
        auto setText = reinterpret_cast<SetText>(dlsym(RTLD_DEFAULT, "_ZN13MainNavButton7setTextERK7QString"));
        auto setPixmap = reinterpret_cast<SetText>(dlsym(RTLD_DEFAULT, "_ZN13MainNavButton9setPixmapERK7QString"));
        auto setActivePixmap = reinterpret_cast<SetText>(dlsym(RTLD_DEFAULT, "_ZN13MainNavButton15setActivePixmapERK7QString"));
        if (!construct || !setText || !setPixmap || !setActivePixmap) {
            qWarning("k2: unsupported Nickel MainNavButton ABI");
            return;
        }
        // Nickel does not publish its class definition. Leave ample storage
        // for the firmware object (NickelMenu reserves 256 bytes for it).
        auto *button = static_cast<QWidget *>(::operator new(1024));
        construct(button, pending);
        button->setObjectName("k2RailButton");
        setText(button, QStringLiteral("k2"));
        setPixmap(button, QStringLiteral(":/images/home/main_nav_more.png"));
        setActivePixmap(button, QStringLiteral(":/images/home/main_nav_more_active.png"));
        if (!connect(button, SIGNAL(tapped()), this, SLOT(launch()))) {
            delete button;
            qWarning("k2: could not connect the rail button");
            return;
        }
        layout->addWidget(button, 1);
        pending->setProperty("k2RailAdded", true);
        pending->ensurePolished();
    }

    void launch() {
        if (!QProcess::startDetached(QStringLiteral("/bin/sh"), QStringList()
                << QStringLiteral("/mnt/onboard/.eink-sdk/control/run")
                << QStringLiteral("/bin/sh")
                << QStringLiteral("/var/run/eink-sdk/usr/bin/k2")))
            qWarning("k2: launcher failed");
    }

private:
    QPointer<QWidget> pending;
};

class K2Plugin : public QImageIOPlugin {
    Q_OBJECT
    Q_PLUGIN_METADATA(IID "org.qt-project.Qt.QImageIOHandlerFactoryInterface" FILE "k2nickel.json")
public:
    K2Plugin() { if (qApp) { new Rail(this); new ControlBridge(this); } }
    Capabilities capabilities(QIODevice *, const QByteArray &) const override { return Capabilities(); }
    QImageIOHandler *create(QIODevice *, const QByteArray &) const override { return nullptr; }
};

#include "k2nickel.moc"
