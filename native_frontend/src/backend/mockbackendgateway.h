#pragma once

#include "backend/backendgateway.h"

#include <QTimer>

class MockBackendGateway final : public BackendGateway
{
    Q_OBJECT

public:
    explicit MockBackendGateway(QObject *parent = nullptr);

    void start() override;
    void requestBootstrap() override;
    void sendRequest(const QString &method, const QJsonObject &params = {}) override;

private:
    void emitBootstrap();
    void emitShellState();
    void emitDashboardState();
    void emitLiveState();
    void emitLogsState();
    void emitHistoryState();
    void emitReviewState();
    void emitOverlayState();

    QTimer m_tickTimer;
    bool m_monitoringActive = true;
    int m_tick = 0;
};
