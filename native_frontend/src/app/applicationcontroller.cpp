#include "app/applicationcontroller.h"

#include "backend/backendgateway.h"
#include "backend/mockbackendgateway.h"
#include "backend/processbackendgateway.h"

#include <QJsonObject>
#include <QJsonValue>
#include <QProcessEnvironment>

ApplicationController::ApplicationController(QObject *parent)
    : QObject(parent)
{
    const bool useMock = QProcessEnvironment::systemEnvironment().value(QStringLiteral("LAP_COACH_NATIVE_USE_MOCK"))
                             == QStringLiteral("1");
    if (useMock) {
        m_gateway = new MockBackendGateway(this);
    } else {
        m_gateway = new ProcessBackendGateway(this);
    }

    seedNavigation();
    connectGateway();
}

QString ApplicationController::currentScreen() const { return m_currentScreen; }
QString ApplicationController::statusLabel() const { return m_statusLabel; }
QString ApplicationController::statusDetail() const { return m_statusDetail; }
QString ApplicationController::connectionLabel() const { return m_connectionLabel; }
bool ApplicationController::monitoringActive() const { return m_monitoringActive; }
QVariantMap ApplicationController::dashboardState() const { return m_dashboardState; }
QVariantMap ApplicationController::liveState() const { return m_liveState; }
QVariantMap ApplicationController::overlayState() const { return m_overlayState; }
QVariantMap ApplicationController::reviewState() const { return m_reviewState; }
RecordListModel *ApplicationController::navigationModel() { return &m_navigationModel; }
RecordListModel *ApplicationController::overlayCategoryModel() { return &m_overlayCategoryModel; }
RecordListModel *ApplicationController::overlayLibraryModel() { return &m_overlayLibraryModel; }
RecordListModel *ApplicationController::overlayLayoutModel() { return &m_overlayLayoutModel; }
RecordListModel *ApplicationController::logModel() { return &m_logModel; }
RecordListModel *ApplicationController::historyModel() { return &m_historyModel; }

void ApplicationController::start()
{
    m_gateway->start();
}

void ApplicationController::navigate(const QString &screenId)
{
    const QString normalized = screenId.trimmed().toLower();
    if (normalized.isEmpty() || normalized == m_currentScreen) {
        return;
    }
    m_currentScreen = normalized;
    emit currentScreenChanged();
}

void ApplicationController::startMonitoring()
{
    sendSimpleRequest(QStringLiteral("service.startMonitoring"));
}

void ApplicationController::stopMonitoring()
{
    sendSimpleRequest(QStringLiteral("service.stopMonitoring"));
}

void ApplicationController::selectOverlay(const QString &overlayId)
{
    sendSimpleRequest(QStringLiteral("overlay.selectOverlay"), QJsonObject{{QStringLiteral("overlayId"), overlayId}});
}

void ApplicationController::selectOverlayCategory(const QString &category)
{
    sendSimpleRequest(QStringLiteral("overlay.selectCategory"), QJsonObject{{QStringLiteral("category"), category}});
}

void ApplicationController::selectOverlayLayout(const QString &layoutId)
{
    sendSimpleRequest(QStringLiteral("overlay.selectLayout"), QJsonObject{{QStringLiteral("layoutId"), layoutId}});
}

void ApplicationController::setOverlaySearchQuery(const QString &query)
{
    sendSimpleRequest(QStringLiteral("overlay.setSearchQuery"), QJsonObject{{QStringLiteral("query"), query}});
}

void ApplicationController::runOverlayAction(const QString &actionId)
{
    sendSimpleRequest(QStringLiteral("overlay.runAction"), QJsonObject{{QStringLiteral("actionId"), actionId}});
}

void ApplicationController::applyOverlaySetting(const QString &fieldKey, const QVariant &value)
{
    sendSimpleRequest(
        QStringLiteral("overlay.applySettingChanges"),
        QJsonObject{
            {QStringLiteral("changes"), QJsonObject{{fieldKey, QJsonValue::fromVariant(value)}}},
        });
}

void ApplicationController::seedNavigation()
{
    m_navigationModel.setRows(
        QVariantList{
            QVariantMap{{QStringLiteral("screenId"), QStringLiteral("dashboard")}, {QStringLiteral("label"), QStringLiteral("Dashboard")}},
            QVariantMap{{QStringLiteral("screenId"), QStringLiteral("live")}, {QStringLiteral("label"), QStringLiteral("Live")}},
            QVariantMap{{QStringLiteral("screenId"), QStringLiteral("logs")}, {QStringLiteral("label"), QStringLiteral("Logs")}},
            QVariantMap{{QStringLiteral("screenId"), QStringLiteral("history")}, {QStringLiteral("label"), QStringLiteral("History")}},
            QVariantMap{{QStringLiteral("screenId"), QStringLiteral("overlay")}, {QStringLiteral("label"), QStringLiteral("Overlay")}},
            QVariantMap{{QStringLiteral("screenId"), QStringLiteral("review")}, {QStringLiteral("label"), QStringLiteral("Review")}},
        });
}

void ApplicationController::connectGateway()
{
    connect(m_gateway, &BackendGateway::connectionStateChanged, this, [this](bool, const QString &detail) {
        m_connectionLabel = detail;
        emit shellStateChanged();
    });

    connect(m_gateway, &BackendGateway::eventReceived, this, [this](const QString &eventName, const QJsonObject &payload) {
        if (eventName == QStringLiteral("shell/state")) {
            updateShellState(payload);
        } else if (eventName == QStringLiteral("screen/dashboard")) {
            updateDashboardState(payload);
        } else if (eventName == QStringLiteral("screen/live")) {
            updateLiveState(payload);
        } else if (eventName == QStringLiteral("screen/logs")) {
            updateLogsState(payload);
        } else if (eventName == QStringLiteral("screen/history")) {
            updateHistoryState(payload);
        } else if (eventName == QStringLiteral("screen/review")) {
            updateReviewState(payload);
        } else if (eventName == QStringLiteral("screen/overlay")) {
            updateOverlayState(payload);
        } else if (eventName == QStringLiteral("ui/message")) {
            emit toastRequested(payload.value(QStringLiteral("message")).toString(),
                                payload.value(QStringLiteral("tone")).toString(QStringLiteral("neutral")));
        }
    });

    connect(m_gateway, &BackendGateway::responseReceived, this, [this](const QString &, bool ok, const QJsonValue &, const QString &error) {
        if (!ok && !error.isEmpty()) {
            emit toastRequested(error, QStringLiteral("error"));
        }
    });
}

void ApplicationController::sendSimpleRequest(const QString &method, const QJsonObject &params)
{
    m_gateway->sendRequest(method, params);
}

void ApplicationController::updateShellState(const QJsonObject &payload)
{
    m_statusLabel = payload.value(QStringLiteral("status")).toString(m_statusLabel);
    m_statusDetail = payload.value(QStringLiteral("statusDetail")).toString(m_statusDetail);
    m_connectionLabel = payload.value(QStringLiteral("connectionLabel")).toString(m_connectionLabel);
    m_monitoringActive = payload.value(QStringLiteral("monitoringActive")).toBool(m_monitoringActive);
    emit shellStateChanged();
}

void ApplicationController::updateDashboardState(const QJsonObject &payload)
{
    m_dashboardState = payload.toVariantMap();
    emit dashboardStateChanged();
}

void ApplicationController::updateLiveState(const QJsonObject &payload)
{
    m_liveState = payload.toVariantMap();
    emit liveStateChanged();
}

void ApplicationController::updateLogsState(const QJsonObject &payload)
{
    m_logModel.setRows(payload.value(QStringLiteral("rows")).toArray());
}

void ApplicationController::updateHistoryState(const QJsonObject &payload)
{
    m_historyModel.setRows(payload.value(QStringLiteral("rows")).toArray());
}

void ApplicationController::updateReviewState(const QJsonObject &payload)
{
    m_reviewState = payload.toVariantMap();
    emit reviewStateChanged();
}

void ApplicationController::updateOverlayState(const QJsonObject &payload)
{
    m_overlayState = payload.toVariantMap();
    m_overlayCategoryModel.setRows(payload.value(QStringLiteral("categories")).toArray());
    m_overlayLibraryModel.setRows(payload.value(QStringLiteral("overlays")).toArray());
    m_overlayLayoutModel.setRows(payload.value(QStringLiteral("layouts")).toArray());
    emit overlayStateChanged();
}
