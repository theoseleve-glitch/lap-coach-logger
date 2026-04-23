#pragma once

#include "models/recordlistmodel.h"

#include <QJsonObject>
#include <QObject>
#include <QVariantMap>

class BackendGateway;

class ApplicationController final : public QObject
{
    Q_OBJECT
    Q_PROPERTY(QString currentScreen READ currentScreen NOTIFY currentScreenChanged)
    Q_PROPERTY(QString statusLabel READ statusLabel NOTIFY shellStateChanged)
    Q_PROPERTY(QString statusDetail READ statusDetail NOTIFY shellStateChanged)
    Q_PROPERTY(QString connectionLabel READ connectionLabel NOTIFY shellStateChanged)
    Q_PROPERTY(bool monitoringActive READ monitoringActive NOTIFY shellStateChanged)
    Q_PROPERTY(QVariantMap dashboardState READ dashboardState NOTIFY dashboardStateChanged)
    Q_PROPERTY(QVariantMap liveState READ liveState NOTIFY liveStateChanged)
    Q_PROPERTY(QVariantMap overlayState READ overlayState NOTIFY overlayStateChanged)
    Q_PROPERTY(QVariantMap reviewState READ reviewState NOTIFY reviewStateChanged)
    Q_PROPERTY(RecordListModel *navigationModel READ navigationModel CONSTANT)
    Q_PROPERTY(RecordListModel *overlayCategoryModel READ overlayCategoryModel CONSTANT)
    Q_PROPERTY(RecordListModel *overlayLibraryModel READ overlayLibraryModel CONSTANT)
    Q_PROPERTY(RecordListModel *overlayLayoutModel READ overlayLayoutModel CONSTANT)
    Q_PROPERTY(RecordListModel *logModel READ logModel CONSTANT)
    Q_PROPERTY(RecordListModel *historyModel READ historyModel CONSTANT)

public:
    explicit ApplicationController(QObject *parent = nullptr);

    QString currentScreen() const;
    QString statusLabel() const;
    QString statusDetail() const;
    QString connectionLabel() const;
    bool monitoringActive() const;
    QVariantMap dashboardState() const;
    QVariantMap liveState() const;
    QVariantMap overlayState() const;
    QVariantMap reviewState() const;

    RecordListModel *navigationModel();
    RecordListModel *overlayCategoryModel();
    RecordListModel *overlayLibraryModel();
    RecordListModel *overlayLayoutModel();
    RecordListModel *logModel();
    RecordListModel *historyModel();

    Q_INVOKABLE void start();
    Q_INVOKABLE void navigate(const QString &screenId);
    Q_INVOKABLE void startMonitoring();
    Q_INVOKABLE void stopMonitoring();
    Q_INVOKABLE void selectOverlay(const QString &overlayId);
    Q_INVOKABLE void selectOverlayCategory(const QString &category);
    Q_INVOKABLE void selectOverlayLayout(const QString &layoutId);
    Q_INVOKABLE void setOverlaySearchQuery(const QString &query);
    Q_INVOKABLE void runOverlayAction(const QString &actionId);
    Q_INVOKABLE void applyOverlaySetting(const QString &fieldKey, const QVariant &value);

signals:
    void currentScreenChanged();
    void shellStateChanged();
    void dashboardStateChanged();
    void liveStateChanged();
    void overlayStateChanged();
    void reviewStateChanged();
    void toastRequested(const QString &message, const QString &tone);

private:
    void seedNavigation();
    void connectGateway();
    void sendSimpleRequest(const QString &method, const QJsonObject &params = {});
    void updateShellState(const QJsonObject &payload);
    void updateDashboardState(const QJsonObject &payload);
    void updateLiveState(const QJsonObject &payload);
    void updateLogsState(const QJsonObject &payload);
    void updateHistoryState(const QJsonObject &payload);
    void updateReviewState(const QJsonObject &payload);
    void updateOverlayState(const QJsonObject &payload);

    QString m_currentScreen = QStringLiteral("overlay");
    QString m_statusLabel = QStringLiteral("Connecting");
    QString m_statusDetail = QStringLiteral("Starting backend bridge");
    QString m_connectionLabel = QStringLiteral("Disconnected");
    bool m_monitoringActive = false;
    QVariantMap m_dashboardState;
    QVariantMap m_liveState;
    QVariantMap m_overlayState;
    QVariantMap m_reviewState;
    RecordListModel m_navigationModel;
    RecordListModel m_overlayCategoryModel;
    RecordListModel m_overlayLibraryModel;
    RecordListModel m_overlayLayoutModel;
    RecordListModel m_logModel;
    RecordListModel m_historyModel;
    BackendGateway *m_gateway = nullptr;
};
