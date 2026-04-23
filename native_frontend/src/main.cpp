#include "app/applicationcontroller.h"
#include "models/recordlistmodel.h"

#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <QQuickStyle>

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);
    QGuiApplication::setApplicationName(QStringLiteral("LAP COACH Native"));
    QGuiApplication::setOrganizationName(QStringLiteral("LAP COACH"));
    QQuickStyle::setStyle(QStringLiteral("Basic"));

    qmlRegisterUncreatableType<RecordListModel>("LapCoachDesktop", 1, 0, "RecordListModel",
                                                QStringLiteral("RecordListModel is exposed by ApplicationController."));

    ApplicationController controller;

    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty(QStringLiteral("appController"), &controller);
    engine.loadFromModule(QStringLiteral("LapCoachDesktop"), QStringLiteral("Main"));
    if (engine.rootObjects().isEmpty()) {
        return -1;
    }

    controller.start();
    return app.exec();
}
